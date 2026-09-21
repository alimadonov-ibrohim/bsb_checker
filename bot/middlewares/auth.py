from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User
from datetime import datetime, timezone


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        session: AsyncSession = data.get("session")
        if session is None:
            return await handler(event, data)

        user_tg = None
        if isinstance(event, Message) and event.from_user:
            user_tg = event.from_user
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_tg = event.from_user

        if user_tg is None:
            return await handler(event, data)

        result = await session.execute(
            select(User).where(User.telegram_id == user_tg.id)
        )
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                telegram_id=user_tg.id,
                username=user_tg.username,
                first_name=user_tg.first_name,
                last_name=user_tg.last_name,
            )
            session.add(user)
            await session.flush()
        else:
            # Update profile info
            user.username = user_tg.username
            user.first_name = user_tg.first_name
            user.last_name = user_tg.last_name
            # Reset daily limit if needed
            user.reset_daily_limit_if_needed()
            # Expire premium if needed
            if user.plan == "premium" and not user.is_premium_active():
                user.plan = "free"

        if user.is_blocked:
            if isinstance(event, Message):
                await event.answer("⛔ Sizning akkauntingiz bloklangan. Admin bilan bog‘laning.")
            elif isinstance(event, CallbackQuery):
                await event.answer("⛔ Akkauntingiz bloklangan.", show_alert=True)
            return None

        data["user"] = user
        return await handler(event, data)
