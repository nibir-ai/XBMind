"""D-Bus Bluetooth manager.

Provides auto-discovery, pairing, and reconnection to a target Bluetooth
device using ``dbus-python``.  Implements exponential backoff for
reconnection attempts.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import dbus
import dbus.mainloop.glib
import dbus.service

from xbmind.utils.events import Event, EventBus, EventType
from xbmind.utils.logger import get_logger

if TYPE_CHECKING:
    from xbmind.config import BluetoothConfig

log = get_logger(__name__)

# D-Bus constants
_BLUEZ_SERVICE = "org.bluez"
_ADAPTER_IFACE = "org.bluez.Adapter1"
_DEVICE_IFACE = "org.bluez.Device1"
_PROPERTIES_IFACE = "org.freedesktop.DBus.Properties"
_OBJECT_MANAGER_IFACE = "org.freedesktop.DBus.ObjectManager"
_AGENT_IFACE = "org.bluez.Agent1"
_AGENT_MANAGER_IFACE = "org.bluez.AgentManager1"


class _AutoPairAgent(dbus.service.Object):
    """A minimal BlueZ agent that auto-accepts pairing requests."""

    CAPABILITY = "NoInputNoOutput"

    @dbus.service.method(_AGENT_IFACE, in_signature="", out_signature="")
    def Release(self) -> None:
        """Called when the agent is unregistered."""

    @dbus.service.method(_AGENT_IFACE, in_signature="os", out_signature="")
    def AuthorizeService(self, device: str, uuid: str) -> None:
        """Authorize a service connection.

        Args:
            device: D-Bus object path of the device.
            uuid: UUID of the service being authorized.
        """
        log.info("bt.authorize_service", device=device, uuid=uuid)

    @dbus.service.method(_AGENT_IFACE, in_signature="o", out_signature="")
    def RequestAuthorization(self, device: str) -> None:
        """Accept authorization request.

        Args:
            device: D-Bus object path of the device.
        """
        log.info("bt.request_authorization", device=device)

    @dbus.service.method(_AGENT_IFACE, in_signature="o", out_signature="u")
    def RequestPasskey(self, device: str) -> dbus.UInt32:
        """Provide a passkey for pairing.

        Args:
            device: D-Bus object path of the device.

        Returns:
            A default passkey of 0.
        """
        log.info("bt.request_passkey", device=device)
        return dbus.UInt32(0)

    @dbus.service.method(_AGENT_IFACE, in_signature="ouq", out_signature="")
    def DisplayPasskey(self, device: str, passkey: int, entered: int) -> None:
        """Display a passkey (no-op for headless operation).

        Args:
            device: D-Bus object path of the device.
            passkey: The passkey to display.
            entered: Number of digits entered so far.
        """

    @dbus.service.method(_AGENT_IFACE, in_signature="os", out_signature="")
    def DisplayPinCode(self, device: str, pincode: str) -> None:
        """Display a PIN code (no-op for headless operation).

        Args:
            device: D-Bus object path of the device.
            pincode: The PIN code to display.
        """

    @dbus.service.method(_AGENT_IFACE, in_signature="ou", out_signature="")
    def RequestConfirmation(self, device: str, passkey: int) -> None:
        """Confirm a passkey (auto-accept).

        Args:
            device: D-Bus object path of the device.
            passkey: The passkey to confirm.
        """
        log.info("bt.request_confirmation", device=device, passkey=passkey)

    @dbus.service.method(_AGENT_IFACE, in_signature="", out_signature="")
    def Cancel(self) -> None:
        """Cancel the current agent operation."""
        log.warning("bt.agent_cancelled")


class BluetoothManager:
    """Manages Bluetooth device discovery, pairing, and connection.

    Uses D-Bus to interact with BlueZ and provides exponential backoff
    reconnection for resilient operation.

    Example::

        manager = BluetoothManager(config, event_bus)
        await manager.start()
        # Device auto-discovered, paired, and connected
        await manager.stop()
    """

    def __init__(self, config: BluetoothConfig, event_bus: EventBus) -> None:
        """Initialise the Bluetooth manager.

        Args:
            config: Bluetooth configuration section.
            event_bus: The application event bus for publishing state changes.
        """
        self._config = config
        self._event_bus = event_bus
        self._bus: dbus.SystemBus | None = None
        self._adapter_path: str | None = None
        self._device_path: str | None = None
        self._connected: bool = False
        self._running: bool = False
        self._reconnect_task: asyncio.Task[None] | None = None
        self._agent: _AutoPairAgent | None = None

    @property
    def connected(self) -> bool:
        """Whether the target device is currently connected."""
        return self._connected

    @property
    def device_path(self) -> str | None:
        """D-Bus object path of the connected device."""
        return self._device_path

    async def start(self) -> None:
        """Start Bluetooth management: discover, pair, and connect.

        Runs D-Bus operations in a thread executor since ``dbus-python``
        is synchronous.
        """
        self._running = True
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._init_dbus)
        await loop.run_in_executor(None, self._discover_and_connect)

        if self._config.reconnect_enabled:
            self._reconnect_task = asyncio.create_task(
                self._reconnect_loop(), name="bt_reconnect"
            )

        log.info("bt.manager_started")

    async def stop(self) -> None:
        """Stop Bluetooth management and disconnect."""
        self._running = False
        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
            self._reconnect_task = None

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._disconnect)
        log.info("bt.manager_stopped")

    def _init_dbus(self) -> None:
        """Initialise the D-Bus system bus and register the pairing agent."""
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self._bus = dbus.SystemBus()

        # Find the default adapter
        obj_manager = dbus.Interface(
            self._bus.get_object(_BLUEZ_SERVICE, "/"),
            _OBJECT_MANAGER_IFACE,
        )
        objects = obj_manager.GetManagedObjects()

        for path, interfaces in objects.items():
            if _ADAPTER_IFACE in interfaces:
                self._adapter_path = str(path)
                break

        if not self._adapter_path:
            raise RuntimeError("No Bluetooth adapter found")

        log.info("bt.adapter_found", path=self._adapter_path)

        # Register auto-pair agent
        if self._config.auto_pair:
            self._agent = _AutoPairAgent(self._bus, "/xbmind/agent")
            agent_manager = dbus.Interface(
                self._bus.get_object(_BLUEZ_SERVICE, "/org/bluez"),
                _AGENT_MANAGER_IFACE,
            )
            agent_manager.RegisterAgent("/xbmind/agent", _AutoPairAgent.CAPABILITY)
            agent_manager.RequestDefaultAgent("/xbmind/agent")
            log.info("bt.agent_registered")

    def _discover_and_connect(self) -> None:
        """Discover the target device and connect to it."""
        if not self._bus or not self._adapter_path:
            return

        # Check if device is already known
        device_path = self._find_device()
        if device_path:
            self._device_path = device_path
            self._connect_device()
            return

        # Start discovery
        adapter = dbus.Interface(
            self._bus.get_object(_BLUEZ_SERVICE, self._adapter_path),
            _ADAPTER_IFACE,
        )

        log.info("bt.discovery_starting", target=self._config.device_name)
        adapter.StartDiscovery()

        import time
        # Poll for device for up to 30 seconds
        for _ in range(60):
            time.sleep(0.5)
            device_path = self._find_device()
            if device_path:
                self._device_path = device_path
                break

        try:
            adapter.StopDiscovery()
        except dbus.exceptions.DBusException:
            pass  # May already be stopped

        if self._device_path:
            self._connect_device()
        else:
            log.warning("bt.device_not_found", target=self._config.device_name)

    def _find_device(self) -> str | None:
        """Find the target device in known BlueZ objects.

        Returns:
            The D-Bus object path of the device, or ``None``.
        """
        if not self._bus:
            return None

        obj_manager = dbus.Interface(
            self._bus.get_object(_BLUEZ_SERVICE, "/"),
            _OBJECT_MANAGER_IFACE,
        )
        objects = obj_manager.GetManagedObjects()

        target_name = self._config.device_name.lower()
        target_mac = self._config.device_mac.upper().replace(":", "_")

        for path, interfaces in objects.items():
            if _DEVICE_IFACE not in interfaces:
                continue

            props = interfaces[_DEVICE_IFACE]
            name = str(props.get("Name", "")).lower()
            address = str(props.get("Address", "")).upper().replace(":", "_")

            if target_mac and target_mac in str(path).upper():
                return str(path)
            if target_name and target_name in name:
                return str(path)

        return None

    def _connect_device(self) -> None:
        """Connect to the target device and optionally pair first."""
        if not self._bus or not self._device_path:
            return

        device = dbus.Interface(
            self._bus.get_object(_BLUEZ_SERVICE, self._device_path),
            _DEVICE_IFACE,
        )
        props = dbus.Interface(
            self._bus.get_object(_BLUEZ_SERVICE, self._device_path),
            _PROPERTIES_IFACE,
        )

        # Pair if not already paired
        paired = bool(props.Get(_DEVICE_IFACE, "Paired"))
        if not paired and self._config.auto_pair:
            log.info("bt.pairing", device=self._device_path)
            try:
                device.Pair()
            except dbus.exceptions.DBusException as exc:
                if "AlreadyExists" not in str(exc):
                    log.exception("bt.pair_failed")
                    return

        # Trust the device
        try:
            props.Set(_DEVICE_IFACE, "Trusted", dbus.Boolean(True))
        except dbus.exceptions.DBusException:
            pass

        # Connect
        connected = bool(props.Get(_DEVICE_IFACE, "Connected"))
        if not connected:
            log.info("bt.connecting", device=self._device_path)
            try:
                device.Connect()
                self._connected = True
                self._event_bus.publish_nowait(
                    Event(EventType.BT_CONNECTED, data=self._device_path, source="bluetooth")
                )
                log.info("bt.connected", device=self._device_path)
            except dbus.exceptions.DBusException:
                log.exception("bt.connect_failed")
                self._connected = False
        else:
            self._connected = True
            log.info("bt.already_connected", device=self._device_path)

    def _disconnect(self) -> None:
        """Disconnect from the current device."""
        if not self._bus or not self._device_path:
            return

        try:
            device = dbus.Interface(
                self._bus.get_object(_BLUEZ_SERVICE, self._device_path),
                _DEVICE_IFACE,
            )
            device.Disconnect()
            self._connected = False
            log.info("bt.disconnected")
        except dbus.exceptions.DBusException:
            log.exception("bt.disconnect_error")

    def _check_connected(self) -> bool:
        """Check if the device is still connected via D-Bus properties.

        Returns:
            ``True`` if the device is connected.
        """
        if not self._bus or not self._device_path:
            return False

        try:
            props = dbus.Interface(
                self._bus.get_object(_BLUEZ_SERVICE, self._device_path),
                _PROPERTIES_IFACE,
            )
            return bool(props.Get(_DEVICE_IFACE, "Connected"))
        except dbus.exceptions.DBusException:
            return False

    async def _reconnect_loop(self) -> None:
        """Reconnection loop with exponential backoff."""
        delay = self._config.reconnect_base_delay
        attempts = 0

        while self._running:
            await asyncio.sleep(2.0)  # Check interval

            loop = asyncio.get_running_loop()
            still_connected = await loop.run_in_executor(None, self._check_connected)

            if still_connected:
                if not self._connected:
                    self._connected = True
                    await self._event_bus.publish(
                        Event(EventType.BT_CONNECTED, data=self._device_path, source="bluetooth")
                    )
                delay = self._config.reconnect_base_delay
                attempts = 0
                continue

            if self._connected:
                self._connected = False
                await self._event_bus.publish(
                    Event(EventType.BT_DISCONNECTED, data=self._device_path, source="bluetooth")
                )

            max_attempts = self._config.reconnect_max_attempts
            if max_attempts > 0 and attempts >= max_attempts:
                log.error("bt.reconnect_exhausted", attempts=attempts)
                break

            await self._event_bus.publish(
                Event(EventType.BT_RECONNECTING, data={"attempt": attempts + 1}, source="bluetooth")
            )

            log.info("bt.reconnecting", attempt=attempts + 1, delay=delay)
            await asyncio.sleep(delay)

            await loop.run_in_executor(None, self._discover_and_connect)
            attempts += 1
            delay = min(delay * 2, self._config.reconnect_max_delay)
