from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
import contextlib
import ssl

from pysignalr.client import SignalRClient
from pysignalr.messages import Message, PingMessage
import pytest

from pyhilo.signalr import SignalRHub


async def _fake_negotiate() -> tuple[str, str]:
    return ("wss://example.invalid/hub", "fake-token")


class _FakeTransport:
    def __init__(self, callback: Callable[[Message], Awaitable[object]]) -> None:
        self._callback = callback


class _FakeSignalRClient:
    on_run: Callable[[_FakeSignalRClient], Awaitable[None]] | None = None
    instances: list[_FakeSignalRClient] = []

    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        retry_count: int = 0,
        ssl: ssl.SSLContext | None = None,
    ) -> None:
        self._message_handlers: dict[str, list[Callable[..., Awaitable[None]]]] = {}
        self.open_callback: Callable[[], Awaitable[None]] | None = None
        self.close_callback: Callable[[], Awaitable[None]] | None = None
        self.error_callback: Callable[[str], Awaitable[None]] | None = None
        self.sent: list[tuple[str, list[object]]] = []
        self._transport = _FakeTransport(self._default_message_callback)
        self.__class__.instances.append(self)

    async def _default_message_callback(self, message: Message) -> None:
        return None

    def on_open(self, callback: Callable[[], Awaitable[None]]) -> None:
        self.open_callback = callback

    def on_close(self, callback: Callable[[], Awaitable[None]]) -> None:
        self.close_callback = callback

    def on_error(self, callback: Callable[[str], Awaitable[None]]) -> None:
        self.error_callback = callback

    async def send(self, method: str, arguments: list[object]) -> None:
        self.sent.append((method, arguments))

    async def run(self) -> None:
        runner = self.__class__.on_run
        assert runner is not None
        await runner(self)


def _patch_client(
    monkeypatch: pytest.MonkeyPatch,
    runner: Callable[[_FakeSignalRClient], Awaitable[None]],
) -> list[_FakeSignalRClient]:
    clients: list[_FakeSignalRClient] = []
    monkeypatch.setattr(_FakeSignalRClient, "instances", clients)
    monkeypatch.setattr(_FakeSignalRClient, "on_run", runner)
    monkeypatch.setattr("pyhilo.signalr.SignalRClient", _FakeSignalRClient)
    monkeypatch.setattr("pyhilo.signalr.ssl.create_default_context", lambda: object())
    return clients


async def _server_close_runner(client: _FakeSignalRClient) -> None:
    assert client.open_callback is not None
    assert client.close_callback is not None
    await client.open_callback()
    await client.close_callback()
    # Simulate pysignalr's WebsocketTransport looping on stale credentials.
    await asyncio.Event().wait()


async def _silent_runner(client: _FakeSignalRClient) -> None:
    assert client.open_callback is not None
    await client.open_callback()
    await asyncio.Event().wait()


@contextlib.asynccontextmanager
async def _running_hub(hub: SignalRHub) -> AsyncIterator[asyncio.Task[None]]:
    task = asyncio.create_task(hub.run())
    try:
        yield task
    finally:
        await hub.disconnect()


@pytest.mark.asyncio
async def test_disconnect_cancels_running_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """disconnect() cancels the task awaiting run(), updates connected, and notifies once."""
    client_connected = asyncio.Event()
    disconnects = 0

    def on_disconnect() -> None:
        nonlocal disconnects
        disconnects += 1

    _patch_client(monkeypatch, _silent_runner)
    hub = SignalRHub(negotiate_callback=_fake_negotiate)
    hub.add_connect_callback(client_connected.set)
    hub.add_disconnect_callback(on_disconnect)
    task = asyncio.create_task(hub.run())

    await asyncio.wait_for(client_connected.wait(), timeout=5)
    assert hub.connected

    await hub.disconnect()

    assert task.done()
    assert not hub.connected
    assert disconnects == 1


@pytest.mark.asyncio
async def test_disconnect_without_a_running_task_is_a_no_op() -> None:
    """disconnect() before run() has ever been called should not raise."""
    hub = SignalRHub(negotiate_callback=_fake_negotiate)
    await hub.disconnect()
    assert not hub.connected


@pytest.mark.asyncio
async def test_connected_is_false_until_on_open_fires(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """hub.connected remains False until pysignalr invokes on_open."""
    before_open = asyncio.Event()
    proceed_open = asyncio.Event()
    after_open = asyncio.Event()
    connected_in_callback: list[bool] = []

    async def runner(client: _FakeSignalRClient) -> None:
        before_open.set()
        await proceed_open.wait()
        assert client.open_callback is not None
        await client.open_callback()
        after_open.set()
        await asyncio.Event().wait()

    _patch_client(monkeypatch, runner)
    hub = SignalRHub(negotiate_callback=_fake_negotiate)
    hub.add_connect_callback(lambda: connected_in_callback.append(hub.connected))
    async with _running_hub(hub):
        await asyncio.wait_for(before_open.wait(), timeout=5)
        assert not hub.connected

        proceed_open.set()
        await asyncio.wait_for(after_open.wait(), timeout=5)
        assert hub.connected
        assert connected_in_callback == [True]


@pytest.mark.asyncio
async def test_invoke_is_ignored_while_not_connected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """invoke() does not call client.send() before on_open marks the hub connected."""
    before_open = asyncio.Event()

    async def runner(_client: _FakeSignalRClient) -> None:
        before_open.set()
        await asyncio.Event().wait()

    clients = _patch_client(monkeypatch, runner)
    hub = SignalRHub(negotiate_callback=_fake_negotiate)
    async with _running_hub(hub):
        await asyncio.wait_for(before_open.wait(), timeout=5)
        await hub.invoke("SubscribeToLocation", [42])

        assert len(clients) == 1
        assert clients[0].sent == []


@pytest.mark.asyncio
async def test_invoke_forwards_when_connected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """invoke() delegates to client.send() once on_open has fired."""
    opened = asyncio.Event()

    clients = _patch_client(monkeypatch, _silent_runner)
    hub = SignalRHub(negotiate_callback=_fake_negotiate)
    hub.add_connect_callback(opened.set)
    async with _running_hub(hub):
        await asyncio.wait_for(opened.wait(), timeout=5)
        await hub.invoke("SubscribeToLocation", [42])

        assert len(clients) == 1
        assert clients[0].sent == [("SubscribeToLocation", [42])]


@pytest.mark.asyncio
async def test_on_close_exits_run_cleanly_and_fires_disconnect_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Server close exits hub.run() cleanly even if pysignalr keeps retrying afterwards."""
    disconnects = 0

    def on_disconnect() -> None:
        nonlocal disconnects
        disconnects += 1

    _patch_client(monkeypatch, _server_close_runner)
    hub = SignalRHub(negotiate_callback=_fake_negotiate)
    hub.add_disconnect_callback(on_disconnect)

    await asyncio.wait_for(hub.run(), timeout=5)

    assert not hub.connected
    assert disconnects == 1


@pytest.mark.asyncio
async def test_on_close_before_open_raises_connection_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Server close before on_open raises ConnectionError so callers back off."""
    disconnects = 0

    async def runner(client: _FakeSignalRClient) -> None:
        assert client.close_callback is not None
        await client.close_callback()
        await asyncio.Event().wait()

    def on_disconnect() -> None:
        nonlocal disconnects
        disconnects += 1

    _patch_client(monkeypatch, runner)
    hub = SignalRHub(negotiate_callback=_fake_negotiate)
    hub.add_disconnect_callback(on_disconnect)

    with pytest.raises(ConnectionError, match="closed before open"):
        await asyncio.wait_for(hub.run(), timeout=5)

    assert not hub.connected
    assert disconnects == 0


@pytest.mark.asyncio
async def test_client_error_after_open_marks_disconnected_and_notifies_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A client failure after open propagates while cleaning up and firing disconnect once."""
    disconnects = 0

    async def runner(client: _FakeSignalRClient) -> None:
        assert client.open_callback is not None
        await client.open_callback()
        raise RuntimeError("server close")

    def on_disconnect() -> None:
        nonlocal disconnects
        disconnects += 1

    _patch_client(monkeypatch, runner)
    hub = SignalRHub(negotiate_callback=_fake_negotiate)
    hub.add_disconnect_callback(on_disconnect)

    with pytest.raises(RuntimeError, match="server close"):
        await hub.run()

    assert not hub.connected
    assert disconnects == 1


@pytest.mark.asyncio
async def test_client_error_before_open_does_not_fire_disconnect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failure before on_open must not trigger disconnect callbacks."""
    disconnects = 0

    async def runner(_client: _FakeSignalRClient) -> None:
        raise RuntimeError("auth failed")

    def on_disconnect() -> None:
        nonlocal disconnects
        disconnects += 1

    _patch_client(monkeypatch, runner)
    hub = SignalRHub(negotiate_callback=_fake_negotiate)
    hub.add_disconnect_callback(on_disconnect)

    with pytest.raises(RuntimeError, match="auth failed"):
        await hub.run()

    assert not hub.connected
    assert disconnects == 0


@pytest.mark.asyncio
async def test_server_timeout_aborts_silent_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A silent connection raises TimeoutError after _SERVER_TIMEOUT and notifies once."""
    disconnects = 0

    def on_disconnect() -> None:
        nonlocal disconnects
        disconnects += 1

    _patch_client(monkeypatch, _silent_runner)
    monkeypatch.setattr(SignalRHub, "_SERVER_TIMEOUT", 0.05)
    hub = SignalRHub(negotiate_callback=_fake_negotiate)
    hub.add_disconnect_callback(on_disconnect)

    with pytest.raises(TimeoutError):
        await asyncio.wait_for(hub.run(), timeout=5)

    assert not hub.connected
    assert disconnects == 1


@pytest.mark.asyncio
async def test_inbound_messages_reset_server_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inbound SignalR messages (including PingMessage) reset the keepalive deadline."""
    keepalives_done = asyncio.Event()

    async def runner(client: _FakeSignalRClient) -> None:
        assert client.open_callback is not None
        await client.open_callback()
        for _ in range(5):
            await asyncio.sleep(0.025)
            await client._transport._callback(PingMessage())
        keepalives_done.set()
        await asyncio.Event().wait()

    _patch_client(monkeypatch, runner)
    monkeypatch.setattr(SignalRHub, "_SERVER_TIMEOUT", 0.08)
    hub = SignalRHub(negotiate_callback=_fake_negotiate)
    async with _running_hub(hub) as task:
        await asyncio.wait_for(keepalives_done.wait(), timeout=5)
        assert hub.connected
        assert not task.done()


@pytest.mark.parametrize(
    ("first_runner", "expected_first_exc"),
    [
        pytest.param(
            _server_close_runner,
            contextlib.nullcontext(),
            id="after-server-close",
        ),
        pytest.param(
            _silent_runner,
            pytest.raises(TimeoutError),
            id="after-server-timeout",
        ),
    ],
)
@pytest.mark.asyncio
async def test_run_resets_state_across_reconnect_cycles(
    monkeypatch: pytest.MonkeyPatch,
    first_runner: Callable[[_FakeSignalRClient], Awaitable[None]],
    expected_first_exc: contextlib.AbstractContextManager[object],
) -> None:
    """Subsequent run() calls on the same SignalRHub reset close/timeout state cleanly."""
    reconnected = asyncio.Event()
    monkeypatch.setattr(SignalRHub, "_SERVER_TIMEOUT", 0.05)
    hub = SignalRHub(negotiate_callback=_fake_negotiate)

    _patch_client(monkeypatch, first_runner)
    with expected_first_exc:
        await asyncio.wait_for(hub.run(), timeout=5)
    assert not hub.connected

    _patch_client(monkeypatch, _silent_runner)
    hub.add_connect_callback(reconnected.set)
    async with _running_hub(hub):
        await asyncio.wait_for(reconnected.wait(), timeout=5)
        assert hub.connected


@pytest.mark.asyncio
async def test_pysignalr_exposes_transport_callback() -> None:
    """Guard SignalRHub's assumption that pysignalr exposes _transport._callback."""
    client = SignalRClient("wss://example.invalid/hub", retry_count=0)
    assert callable(client._transport._callback)
    await client._transport._callback(PingMessage())
