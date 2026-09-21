import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse
from database.database import init_db, async_session_maker
from database.models import Admin, Setting
from passlib.context import CryptContext
from sqlalchemy import select

from backend.api import auth, users, tests, payments, processing, settings as settings_api, dashboard
from backend.admin import routes as admin_routes

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

TEMPLATES_DIR = ROOT / "admin_panel" / "templates"
STATIC_DIR = ROOT / "admin_panel" / "static"

# Telegram bot (lazy init for webhook)
_bot = None
_dp = None


def get_bot_and_dp():
    global _bot, _dp
    if _bot is not None:
        return _bot, _dp

    from aiogram import Bot, Dispatcher
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode
    from bot.handlers import get_all_routers
    from bot.middlewares.db import DbSessionMiddleware
    from bot.middlewares.auth import AuthMiddleware

    token = os.getenv("BOT_TOKEN")
    if not token:
        return None, None

    _bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    _dp = Dispatcher(storage=MemoryStorage())
    _dp.message.middleware(DbSessionMiddleware())
    _dp.callback_query.middleware(DbSessionMiddleware())
    _dp.message.middleware(AuthMiddleware())
    _dp.callback_query.middleware(AuthMiddleware())
    for r in get_all_routers():
        _dp.include_router(r)
    return _bot, _dp


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
        async with async_session_maker() as session:
            admin_user = os.getenv("ADMIN_USERNAME", "admin")
            admin_pass = os.getenv("ADMIN_PASSWORD", "admin123")
            admin = await session.scalar(
                select(Admin).where(Admin.username == admin_user)
            )
            if admin is not None:
                # Keep env credentials authoritative
                admin.password_hash = pwd_context.hash(admin_pass)
                admin.is_active = True
            else:
                admin = Admin(
                    username=admin_user,
                    password_hash=pwd_context.hash(admin_pass),
                )
                session.add(admin)

            defaults = {
                "free_daily_pdf_limit": os.getenv("FREE_DAILY_PDF_LIMIT", "3"),
                "premium_daily_pdf_limit": os.getenv("PREMIUM_DAILY_PDF_LIMIT", "6"),
                "premium_price_uzs": os.getenv("PREMIUM_PRICE_UZS", "35000"),
                "premium_duration_days": os.getenv("PREMIUM_DURATION_DAYS", "30"),
                "gemini_model": os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
                "max_file_size_mb": os.getenv("MAX_FILE_SIZE_MB", "50"),
            }
            for key, value in defaults.items():
                r = await session.execute(select(Setting).where(Setting.key == key))
                if not r.scalar_one_or_none():
                    session.add(Setting(key=key, value=value, description=key))
            await session.commit()

        # Set webhook if WEBHOOK_URL is configured (Vercel / production)
        webhook_url = os.getenv("WEBHOOK_URL", "").rstrip("/")
        bot, _ = get_bot_and_dp()
        if bot and webhook_url:
            secret = os.getenv("WEBHOOK_SECRET", "")
            full_url = f"{webhook_url}/api/telegram/webhook"
            await bot.set_webhook(
                url=full_url,
                secret_token=secret or None,
                drop_pending_updates=True,
            )
    except Exception as e:
        # On Vercel cold start, DB might not be ready — don't crash the whole app
        print(f"Lifespan init warning: {e}")
    yield
    bot, _ = get_bot_and_dp()
    if bot:
        try:
            await bot.session.close()
        except Exception:
            pass


app = FastAPI(
    title="BSB/CHSB Checker Admin",
    version="1.0.0",
    lifespan=lifespan,
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(tests.router, prefix="/api/tests", tags=["tests"])
app.include_router(payments.router, prefix="/api/payments", tags=["payments"])
app.include_router(processing.router, prefix="/api/processing", tags=["processing"])
app.include_router(settings_api.router, prefix="/api/settings", tags=["settings"])
app.include_router(admin_routes.router)


@app.get("/")
async def root():
    return RedirectResponse("/admin")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/telegram/webhook")
async def telegram_webhook(request: Request):
    """Telegram updates arrive here on Vercel (webhook mode)."""
    bot, dp = get_bot_and_dp()
    if not bot or not dp:
        return JSONResponse({"ok": False, "error": "BOT_TOKEN not set"}, status_code=500)

    secret = os.getenv("WEBHOOK_SECRET", "")
    if secret:
        header = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if header != secret:
            return JSONResponse({"ok": False}, status_code=403)

    from aiogram.types import Update
    data = await request.json()
    update = Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", "8000"))
    uvicorn.run("backend.main:app", host=host, port=port, reload=False)
