from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql

from chat_history.domain.entities import ChatSession
from chat_history.infrastructure.sqlalchemy_history import (
    SqlAlchemyChatHistoryRepository,
)
from chat_history.service.history import ChatHistoryService


_OWNER_ID = UUID("00000000-0000-0000-0000-000000000001")
_OTHER_USER_ID = UUID("00000000-0000-0000-0000-000000000002")
_SESSION_ID = "session-abc"


def _session(user_id: UUID) -> ChatSession:
    now = datetime.now(UTC)
    return ChatSession(
        session_id=_SESSION_ID,
        user_id=user_id,
        title="Existing session",
        created_at=now,
        updated_at=now,
    )


def _service_fixture() -> tuple[ChatHistoryService, AsyncMock, MagicMock]:
    db = AsyncMock()
    db.__aenter__ = AsyncMock(return_value=db)
    db.__aexit__ = AsyncMock(return_value=None)
    session_factory = MagicMock(return_value=db)
    return ChatHistoryService(session_factory), db, MagicMock()


@pytest.mark.asyncio
async def test_sync_turn_creates_and_appends_to_new_session() -> None:
    service, db, repo = _service_fixture()
    repo.get_session = AsyncMock(return_value=None)
    repo.create_session = AsyncMock()
    repo.touch_session = AsyncMock()
    repo.append_messages = AsyncMock()

    with patch(
        "chat_history.service.history.SqlAlchemyChatHistoryRepository",
        return_value=repo,
    ):
        await service.sync_turn(
            user_id=_OWNER_ID,
            session_id=_SESSION_ID,
            human_message="Hello",
            ai_reply="Hi",
        )

    repo.create_session.assert_awaited_once_with(
        session_id=_SESSION_ID,
        user_id=_OWNER_ID,
        title="Hello",
    )
    repo.touch_session.assert_not_awaited()
    repo.append_messages.assert_awaited_once_with(
        session_id=_SESSION_ID,
        human_content="Hello",
        ai_content="Hi",
    )
    db.commit.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_sync_turn_touches_and_appends_to_owned_session() -> None:
    service, db, repo = _service_fixture()
    repo.get_session = AsyncMock(return_value=_session(_OWNER_ID))
    repo.create_session = AsyncMock()
    repo.touch_session = AsyncMock()
    repo.append_messages = AsyncMock()

    with patch(
        "chat_history.service.history.SqlAlchemyChatHistoryRepository",
        return_value=repo,
    ):
        await service.sync_turn(
            user_id=_OWNER_ID,
            session_id=_SESSION_ID,
            human_message="Hello again",
            ai_reply="Welcome back",
        )

    repo.create_session.assert_not_awaited()
    repo.touch_session.assert_awaited_once_with(
        user_id=_OWNER_ID,
        session_id=_SESSION_ID,
    )
    repo.append_messages.assert_awaited_once_with(
        session_id=_SESSION_ID,
        human_content="Hello again",
        ai_content="Welcome back",
    )
    db.commit.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_sync_turn_rejects_session_owned_by_another_user() -> None:
    service, db, repo = _service_fixture()
    repo.get_session = AsyncMock(return_value=_session(_OWNER_ID))
    repo.create_session = AsyncMock()
    repo.touch_session = AsyncMock()
    repo.append_messages = AsyncMock()

    with patch(
        "chat_history.service.history.SqlAlchemyChatHistoryRepository",
        return_value=repo,
    ):
        await service.sync_turn(
            user_id=_OTHER_USER_ID,
            session_id=_SESSION_ID,
            human_message="Unauthorized message",
            ai_reply="Unauthorized reply",
        )

    repo.create_session.assert_not_awaited()
    repo.touch_session.assert_not_awaited()
    repo.append_messages.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_clear_session_passes_owner_scope_to_repository() -> None:
    service, db, repo = _service_fixture()
    repo.delete_session = AsyncMock()

    with patch(
        "chat_history.service.history.SqlAlchemyChatHistoryRepository",
        return_value=repo,
    ):
        await service.clear_session(
            user_id=_OWNER_ID,
            session_id=_SESSION_ID,
        )

    repo.delete_session.assert_awaited_once_with(
        user_id=_OWNER_ID,
        session_id=_SESSION_ID,
    )
    db.commit.assert_awaited_once_with()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["touch", "delete"])
async def test_repository_mutations_scope_by_owner_and_session(operation: str) -> None:
    db = AsyncMock()
    repository = SqlAlchemyChatHistoryRepository(db)

    if operation == "touch":
        await repository.touch_session(
            user_id=_OWNER_ID,
            session_id=_SESSION_ID,
        )
    else:
        await repository.delete_session(
            user_id=_OWNER_ID,
            session_id=_SESSION_ID,
        )

    statement = db.execute.await_args.args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)

    assert "chat_sessions.user_id =" in sql
    assert "chat_sessions.session_id =" in sql
    assert _OWNER_ID in compiled.params.values()
    assert _SESSION_ID in compiled.params.values()
