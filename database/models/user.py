from datetime import datetime, timezone
from sqlalchemy import BigInteger, String, Boolean, Integer, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.database import Base
import enum


class PlanType(str, enum.Enum):
    FREE = "free"
    PREMIUM = "premium"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    plan: Mapped[str] = mapped_column(String(20), default=PlanType.FREE.value, nullable=False)
    premium_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    daily_pdf_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_limit_reset: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    tests = relationship("Test", back_populates="user", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="user", cascade="all, delete-orphan")
    processing_jobs = relationship("ProcessingJob", back_populates="user", cascade="all, delete-orphan")

    def is_premium_active(self) -> bool:
        if self.plan != PlanType.PREMIUM.value:
            return False
        if self.premium_until is None:
            return False
        now = datetime.now(timezone.utc)
        if self.premium_until.tzinfo is None:
            return self.premium_until > now.replace(tzinfo=None)
        return self.premium_until > now

    def get_daily_limit(self, free_limit: int = 3, premium_limit: int = 6) -> int:
        if self.is_premium_active():
            return premium_limit
        return free_limit

    def can_upload_pdf(self, free_limit: int = 3, premium_limit: int = 6) -> bool:
        self.reset_daily_limit_if_needed()
        return self.daily_pdf_used < self.get_daily_limit(free_limit, premium_limit)

    def reset_daily_limit_if_needed(self) -> None:
        now = datetime.now(timezone.utc)
        last = self.last_limit_reset
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if last.date() < now.date():
            self.daily_pdf_used = 0
            self.last_limit_reset = now
