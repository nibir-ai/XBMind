"""Wikipedia tool.

Fetches article summaries from the Wikipedia REST API.
"""

from __future__ import annotations

from typing import Any

import httpx

from xbmind.llm.base import ToolDefinition
from xbmind.llm.tools.base_tool import BaseTool
from xbmind.utils.logger import get_logger

log = get_logger(__name__)

_WIKI_API_URL = "https://en.wikipedia.org/api/rest_v1/page/summary"


class WikipediaTool(BaseTool):
    """Fetches article summaries from Wikipedia.

    Example::

        tool = WikipediaTool()
        result = await tool.execute(query="Python programming language")
    """

    @property
    def definition(self) -> ToolDefinition:
        """Tool definition for the LLM."""
        return ToolDefinition(
            name="wikipedia",
            description=(
                "Look up information on Wikipedia. Returns a summary of the "
                "article for the given query/topic."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The topic or article title to search for",
                    },
                },
                "required": ["query"],
            },
        )

    async def execute(self, **kwargs: Any) -> str:
        """Fetch a Wikipedia article summary.

        Args:
            **kwargs: Must include ``query`` (str).

        Returns:
            Article summary or error message.
        """
        query = kwargs.get("query", "")
        if not query:
            return "Error: No query provided."

        # Normalise query for URL
        title = query.strip().replace(" ", "_")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{_WIKI_API_URL}/{title}",
                    headers={
                        "User-Agent": "XBMind/0.1 (Voice Assistant)",
                        "Accept": "application/json",
                    },
                    follow_redirects=True,
                )

                if response.status_code == 404:
                    # Try search API as fallback
                    return await self._search_fallback(client, query)

                response.raise_for_status()
                data = response.json()

            page_title = data.get("title", query)
            extract = data.get("extract", "")
            description = data.get("description", "")
            # page_url available via data["content_urls"]["desktop"]["page"]

            if not extract:
                return f"No Wikipedia article found for '{query}'."

            result = f"Wikipedia: {page_title}"
            if description:
                result += f" — {description}"
            result += f"\n\n{extract}"

            # Truncate if too long
            if len(result) > 2000:
                result = result[:1997] + "..."

            log.info("tool.wikipedia.found", title=page_title, length=len(extract))
            return result

        except httpx.TimeoutException:
            log.error("tool.wikipedia.timeout", query=query)
            return "Error: Wikipedia request timed out."
        except httpx.HTTPStatusError as exc:
            log.exception("tool.wikipedia.http_error", query=query)
            return f"Error looking up Wikipedia: HTTP {exc.response.status_code}"

    async def _search_fallback(self, client: httpx.AsyncClient, query: str) -> str:
        """Search Wikipedia when direct title lookup fails.

        Args:
            client: HTTP client instance.
            query: Search query string.

        Returns:
            Summary of the best matching article, or an error message.
        """
        search_url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": "1",
            "format": "json",
        }

        response = await client.get(search_url, params=params, follow_redirects=True)
        response.raise_for_status()
        data = response.json()

        results = data.get("query", {}).get("search", [])
        if not results:
            return f"No Wikipedia article found for '{query}'."

        # Get the summary for the first result
        title = results[0]["title"].replace(" ", "_")
        summary_response = await client.get(
            f"{_WIKI_API_URL}/{title}",
            headers={"User-Agent": "XBMind/0.1"},
            follow_redirects=True,
        )

        if summary_response.status_code != 200:
            return f"Found '{results[0]['title']}' but couldn't load the summary."

        data = summary_response.json()
        extract = data.get("extract", "No content available.")

        result = f"Wikipedia: {data.get('title', query)}\n\n{extract}"
        if len(result) > 2000:
            result = result[:1997] + "..."

        return result
