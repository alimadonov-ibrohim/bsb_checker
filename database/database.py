from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from dotenv import load_dotenv
import os

load_dotenv()


def _clean_db_url(url: str) -> str:
    url = url.strip().strip('"').strip("'")
    if "?" in url:
        base, _, query = url.partition("?")
        params = []
        for part in query.split("&"):
            part = part.strip()
            if "=" in part:
                key, _, value = part.partition("=")
                params.append(f"{key.strip()}={value.strip()}")
            elif part:
                params.append(part)
        url = base + "?" + "&".join(params)
    return url


DATABASE_URL = _clean_db_url(
    os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:password@localhost:5432/bsb_checker",
    )
)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncSession:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    from . import models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
