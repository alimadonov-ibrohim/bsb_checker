"""
Persistent FSM storage (SQLAlchemy / PostgreSQL) for serverless hosts.
Vercel may route consecutive updates to different instances, so in-memory
FSM (MemoryStorage) does NOT work — state must live in the database.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any, Mapping

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StorageKey
from aiogram.exceptions import DataNotDictLikeError

from database.database import async_session_maker
from database.models import BotState

logger = logging.getLogger(__name__)


_MISSING = object()


def _dumps(data: Mapping[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


class DBStorage(BaseStorage):
    """Store FSM state + data in the `bot_states` table."""

    async def _row(self, key: StorageKey) -> BotState | None:
        chat_id = key.chat_id
        user_id = key.user_id if key.user_id is not None else key.chat_id
        async with async_session_maker() as session:
            return await session.get(BotState, {"chat_id": chat_id, "user_id": user_id})

    async def _write(
        self,
        key: StorageKey,
        state: str | None | object = _MISSING,
        data: Mapping[str, Any] | None = None,
    ) -> None:
        chat_id = key.chat_id
        user_id = key.user_id if key.user_id is not None else key.chat_id
        async with async_session_maker() as session:
            row = await session.get(BotState, {"chat_id": chat_id, "user_id": user_id})
            if row is None:
                row = BotState(chat_id=chat_id, user_id=user_id)
                session.add(row)
            if state is not _MISSING:
                row.state = state if state is None else str(state)
            if data is not None:
                row.data_json = _dumps(data)
            row.updated_at = datetime.now(timezone.utc)
            await session.commit()

    async def set_state(self, key: StorageKey, state: State | str | None = None) -> None:
        if isinstance(state, State):
            state = state.state
        await self._write(key, state=state)

    async def get_state(self, key: StorageKey) -> str | None:
        row = await self._row(key)
        return row.state if row else None

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        if not isinstance(data, dict):
            raise DataNotDictLikeError(
                f"Data must be a dict or dict-like object, got {type(data).__name__}"
            )
        await self._write(key, data=data)

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        row = await self._row(key)
        if not row or not row.data_json:
            return {}
        try:
            parsed = json.loads(row.data_json)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            logger.error("Failed to decode FSM data for %s", key.user_id)
            return {}

    async def close(self) -> None:
        pass