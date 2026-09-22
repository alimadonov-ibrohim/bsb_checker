from datetime import datetime, timezone
from sqlalchemy import BigInteger, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from database.database import Base


class BotState(Base):
    """Persistent FSM storage for serverless (Vercel) environments."""

    __tablename__ = "bot_states"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    state: Mapped[str | None] = mapped_column(String(120), nullable=True)
    data_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )