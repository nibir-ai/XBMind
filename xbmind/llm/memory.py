"""SQLite conversation memory with auto-summarization.

Stores conversation history in a local SQLite database via ``aiosqlite``
and automatically summarizes older messages to manage context length.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiosqlite

from xbmind.llm.base import LLMMessage
from xbmind.utils.logger import get_logger

if TYPE_CHECKING:
    from xbmind.config import MemoryConfig

log = get_logger(__name__)

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    tool_call_id TEXT DEFAULT '',
    name TEXT DEFAULT '',
    metadata TEXT DEFAULT '{}',
    created_at REAL NOT NULL
);
"""

_CREATE_SUMMARIES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    summary TEXT NOT NULL,
    messages_summarized INTEGER NOT NULL,
    created_at REAL NOT NULL
);
"""

_CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_conversations_session
ON conversations(session_id, created_at);
"""


class ConversationMemory:
    """Persistent conversation memory backed by SQLite.

    Stores messages in a local database and supports automatic
    summarization of older messages to keep the context window
    manageable.

    Example::

        memory = ConversationMemory(config)
        await memory.start()
        await memory.add_message("session_1", LLMMessage(role="user", content="Hello"))
        messages = await memory.get_messages("session_1")
    """

    def __init__(self, config: MemoryConfig) -> None:
        """Initialise conversation memory.

        Args:
            config: Memory configuration section.
        """
        self._config = config
        self._db_path = Path(config.db_path)
        self._db: aiosqlite.Connection | None = None

    async def start(self) -> None:
        """Open the database and create tables if needed."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self._db_path))
        await self._db.execute(_CREATE_TABLE_SQL)
        await self._db.execute(_CREATE_SUMMARIES_TABLE_SQL)
        await self._db.execute(_CREATE_INDEX_SQL)
        await self._db.commit()
        log.info("memory.started", db_path=str(self._db_path))

    async def stop(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None
        log.info("memory.stopped")

    async def add_message(self, session_id: str, message: LLMMessage) -> None:
        """Add a message to the conversation history.

        Args:
            session_id: Unique session identifier.
            message: The message to store.
        """
        if self._db is None:
            raise RuntimeError("Memory not started — call start() first")

        metadata: dict[str, Any] = {}
        if message.tool_calls:
            metadata["tool_calls"] = [
                {"name": tc.name, "arguments": tc.arguments, "id": tc.id}
                for tc in message.tool_calls
            ]

        await self._db.execute(
            """INSERT INTO conversations
               (session_id, role, content, tool_call_id, name, metadata, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                message.role,
                message.content,
                message.tool_call_id,
                message.name,
                json.dumps(metadata),
                time.time(),
            ),
        )
        await self._db.commit()

    async def get_messages(self, session_id: str) -> list[LLMMessage]:
        """Retrieve conversation messages for a session.

        Returns the latest summary (if any) followed by the most recent
        messages up to the configured limit.

        Args:
            session_id: Unique session identifier.

        Returns:
            Ordered list of :class:`LLMMessage` objects.
        """
        if self._db is None:
            raise RuntimeError("Memory not started — call start() first")

        messages: list[LLMMessage] = []

        # Get latest summary
        summary = await self._get_latest_summary(session_id)
        if summary:
            messages.append(
                LLMMessage(
                    role="system",
                    content=f"Previous conversation summary:\n{summary}",
                )
            )

        # Get recent messages
        cursor = await self._db.execute(
            """SELECT role, content, tool_call_id, name, metadata
               FROM conversations
               WHERE session_id = ?
               ORDER BY created_at DESC
               LIMIT ?""",
            (session_id, self._config.keep_recent * 2),
        )
        rows = await cursor.fetchall()

        from xbmind.llm.base import ToolCall

        for row in reversed(rows):
            role, content, tool_call_id, name, metadata_str = row
            metadata = json.loads(metadata_str) if metadata_str else {}

            tool_calls: list[ToolCall] = []
            if "tool_calls" in metadata:
                for tc_data in metadata["tool_calls"]:
                    tool_calls.append(
                        ToolCall(
                            name=tc_data.get("name", ""),
                            arguments=tc_data.get("arguments", {}),
                            id=tc_data.get("id", ""),
                        )
                    )

            messages.append(
                LLMMessage(
                    role=role,
                    content=content,
                    tool_calls=tool_calls,
                    tool_call_id=tool_call_id or "",
                    name=name or "",
                )
            )

        return messages

    async def get_message_count(self, session_id: str) -> int:
        """Get the total number of messages in a session.

        Args:
            session_id: Unique session identifier.

        Returns:
            Number of messages.
        """
        if self._db is None:
            return 0

        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM conversations WHERE session_id = ?",
            (session_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def should_summarize(self, session_id: str) -> bool:
        """Check if the session needs summarization.

        Args:
            session_id: Unique session identifier.

        Returns:
            ``True`` if the message count exceeds the configured threshold.
        """
        if self._config.max_messages <= 0:
            return False
        count = await self.get_message_count(session_id)
        return count >= self._config.max_messages

    async def store_summary(self, session_id: str, summary: str) -> None:
        """Store a summary and prune older messages.

        Args:
            session_id: Unique session identifier.
            summary: The summary text to store.
        """
        if self._db is None:
            raise RuntimeError("Memory not started")

        # Store the summary
        await self._db.execute(
            """INSERT INTO summaries
               (session_id, summary, messages_summarized, created_at)
               VALUES (?, ?, ?, ?)""",
            (
                session_id,
                summary,
                await self.get_message_count(session_id),
                time.time(),
            ),
        )

        # Keep only recent messages
        cursor = await self._db.execute(
            """SELECT id FROM conversations
               WHERE session_id = ?
               ORDER BY created_at DESC
               LIMIT ?""",
            (session_id, self._config.keep_recent),
        )
        keep_rows = await cursor.fetchall()
        keep_ids = {row[0] for row in keep_rows}

        if keep_ids:
            placeholders = ",".join("?" * len(keep_ids))
            await self._db.execute(
                f"""DELETE FROM conversations
                    WHERE session_id = ? AND id NOT IN ({placeholders})""",
                (session_id, *keep_ids),
            )

        await self._db.commit()
        log.info("memory.summarized", session_id=session_id)

    async def _get_latest_summary(self, session_id: str) -> str | None:
        """Get the most recent summary for a session.

        Args:
            session_id: Unique session identifier.

        Returns:
            Summary text or ``None``.
        """
        if self._db is None:
            return None

        cursor = await self._db.execute(
            """SELECT summary FROM summaries
               WHERE session_id = ?
               ORDER BY created_at DESC
               LIMIT 1""",
            (session_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else None

    async def clear_session(self, session_id: str) -> None:
        """Delete all messages and summaries for a session.

        Args:
            session_id: Unique session identifier.
        """
        if self._db is None:
            return

        await self._db.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
        await self._db.execute("DELETE FROM summaries WHERE session_id = ?", (session_id,))
        await self._db.commit()
        log.info("memory.session_cleared", session_id=session_id)
