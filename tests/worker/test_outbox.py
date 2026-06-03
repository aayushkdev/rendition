from worker import outbox


class FakeSession:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakePublisher:
    pass


def test_publish_once_uses_configured_batch_size_and_closes_session(monkeypatch):
    session = FakeSession()
    publisher = FakePublisher()
    calls = []

    monkeypatch.setattr(outbox, "SessionLocal", lambda: session)
    monkeypatch.setattr(outbox, "get_job_queue_publisher", lambda: publisher)
    monkeypatch.setattr(outbox.settings, "OUTBOX_PUBLISH_BATCH_SIZE", 25)

    def publish_pending_outbox_messages(db, publisher, limit):
        calls.append({"db": db, "publisher": publisher, "limit": limit})
        return 3

    monkeypatch.setattr(
        outbox,
        "publish_pending_outbox_messages",
        publish_pending_outbox_messages,
    )

    published_count = outbox.publish_once()

    assert published_count == 3
    assert calls == [{"db": session, "publisher": publisher, "limit": 25}]
    assert session.closed is True


def test_publish_once_closes_session_when_publish_fails(monkeypatch):
    session = FakeSession()

    monkeypatch.setattr(outbox, "SessionLocal", lambda: session)
    monkeypatch.setattr(outbox, "get_job_queue_publisher", lambda: FakePublisher())

    def publish_pending_outbox_messages(*_args, **_kwargs):
        raise RuntimeError("publish failed")

    monkeypatch.setattr(
        outbox,
        "publish_pending_outbox_messages",
        publish_pending_outbox_messages,
    )

    try:
        outbox.publish_once()
    except RuntimeError as exc:
        assert str(exc) == "publish failed"

    assert session.closed is True
