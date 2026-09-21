import threading

from ek_agent.dispatch import MainThreadDispatcher


def test_background_notifications_execute_only_when_main_thread_drains() -> None:
    dispatcher = MainThreadDispatcher()
    received = []
    owner = threading.get_ident()

    def callback(message: str) -> None:
        received.append((threading.get_ident(), message))

    thread = threading.Thread(target=lambda: dispatcher.submit(callback, "connected"))
    thread.start()
    thread.join()
    assert received == []
    dispatcher.drain()
    assert received == [(owner, "connected")]


def test_callback_failure_does_not_stop_event_delivery() -> None:
    dispatcher = MainThreadDispatcher()
    received = []

    def fail() -> None:
        raise ValueError("failed callback")

    dispatcher.submit(fail)
    dispatcher.submit(received.append, "still running")
    dispatcher.drain()
    assert received == ["still running"]


def test_draining_on_a_worker_thread_is_rejected() -> None:
    dispatcher = MainThreadDispatcher()
    errors = []

    def drain() -> None:
        try:
            dispatcher.drain()
        except RuntimeError as error:
            errors.append(str(error))

    thread = threading.Thread(target=drain)
    thread.start()
    thread.join()
    assert errors == ["GUI callbacks must run on the main thread"]
