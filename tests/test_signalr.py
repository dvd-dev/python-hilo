import asyncio

import pytest

from pyhilo.signalr import SignalRHub


async def _fake_negotiate() -> tuple[str, str]:
    return ("wss://example.invalid/hub", "fake-token")


@pytest.mark.asyncio
async def test_disconnect_cancels_running_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """disconnect() must cancel the task running run(), not call client.stop().

    pysignalr.SignalRClient has no stop()/close() method -- its run()
    coroutine blocks until cancelled. Calling a nonexistent stop() method
    raised AttributeError on every Home Assistant shutdown.
    """

    client_connected = asyncio.Event()

    class FakeSignalRClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self._message_handlers: dict = {}

        def on_open(self, callback: object) -> None:
            pass

        def on_close(self, callback: object) -> None:
            pass

        def on_error(self, callback: object) -> None:
            pass

        async def run(self) -> None:
            # Block forever, like the real pysignalr transport's reconnect loop.
            client_connected.set()
            await asyncio.Event().wait()

    monkeypatch.setattr("pyhilo.signalr.SignalRClient", FakeSignalRClient)
    monkeypatch.setattr("pyhilo.signalr.ssl.create_default_context", lambda: object())

    hub = SignalRHub(negotiate_callback=_fake_negotiate)
    task = asyncio.create_task(hub.run())

    # Wait until run() has reached the blocking await inside
    # FakeSignalRClient.run() (negotiation and the executor hop for the SSL
    # context are real awaits, so a fixed number of sleep(0)s is fragile).
    await asyncio.wait_for(client_connected.wait(), timeout=5)
    assert hub.connected

    # Must not raise -- this previously called the nonexistent
    # SignalRClient.stop() and raised AttributeError.
    await hub.disconnect()

    assert task.done()
    assert not hub.connected


@pytest.mark.asyncio
async def test_disconnect_without_a_running_task_is_a_no_op() -> None:
    """disconnect() before run() has ever been called should not raise."""
    hub = SignalRHub(negotiate_callback=_fake_negotiate)
    await hub.disconnect()
    assert not hub.connected
