from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.database import Base
import enum


class TestType(str, enum.Enum):
    BSB = "BSB"
    CHSB = "CHSB"


class Test(Base):
    __tablename__ = "tests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    class_name: Mapped[str] = mapped_column(String(100), nullable=False)
    test_name: Mapped[str] = mapped_column(String(255), nullable=False)
    test_type: Mapped[str] = mapped_column(String(10), nullable=False)  # BSB / CHSB
    question_count: Mapped[int] = mapped_column(Integer, nullable=False)
    points_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: {"1": 2, "2": 1, ...} har bir savol bali
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    user = relationship("User", back_populates="tests")
    answer_key = relationship("AnswerKey", back_populates="test", uselist=False, cascade="all, delete-orphan")
    students = relationship("Student", back_populates="test", cascade="all, delete-orphan")
    processing_jobs = relationship("ProcessingJob", back_populates="test", cascade="all, delete-orphan")


class AnswerKey(Base):
    __tablename__ = "answer_keys"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"), unique=True, nullable=False)
    answers_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string: {"1": "A", "2": "C", ...}
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    test = relationship("Test", back_populates="answer_key")
