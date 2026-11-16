"""Database helper behaviour that does not need a live database."""

import pytest
from sqlalchemy.exc import OperationalError

from cartiq_api import db


def test_ping_returns_false_when_unreachable(monkeypatch):
    class Boom:
        def connect(self):  # noqa: ANN202
            raise OperationalError("SELECT 1", {}, Exception("no server"))

    monkeypatch.setattr(db, "get_engine", lambda: Boom())
    assert db.ping() is False


def test_engine_is_reused(monkeypatch):
    monkeypatch.setattr(db, "_engine", None)
    first = db.get_engine()
    assert db.get_engine() is first


def test_session_scope_commits_and_closes(monkeypatch):
    calls: list[str] = []

    class FakeSession:
        def commit(self) -> None:
            calls.append("commit")

        def rollback(self) -> None:
            calls.append("rollback")

        def close(self) -> None:
            calls.append("close")

    monkeypatch.setattr(db, "sessionmaker", lambda **_: lambda: FakeSession())
    monkeypatch.setattr(db, "get_engine", lambda: object())

    with db.session_scope() as session:
        assert isinstance(session, FakeSession)
    assert calls == ["commit", "close"]


def test_session_scope_rolls_back_on_error(monkeypatch):
    calls: list[str] = []

    class FakeSession:
        def commit(self) -> None:
            calls.append("commit")

        def rollback(self) -> None:
            calls.append("rollback")

        def close(self) -> None:
            calls.append("close")

    monkeypatch.setattr(db, "sessionmaker", lambda **_: lambda: FakeSession())
    monkeypatch.setattr(db, "get_engine", lambda: object())

    with pytest.raises(RuntimeError), db.session_scope():
        raise RuntimeError("boom")
    assert calls == ["rollback", "close"]
