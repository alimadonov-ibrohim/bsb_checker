from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.database import Base


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    class_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    test = relationship("Test", back_populates="students")
    answers = relationship("StudentAnswer", back_populates="student", uselist=False, cascade="all, delete-orphan")
    result = relationship("Result", back_populates="student", uselist=False, cascade="all, delete-orphan")


class StudentAnswer(Base):
    __tablename__ = "student_answers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), unique=True, nullable=False)
    answers_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON: {"1": "A", "2": null, ...}
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    student = relationship("Student", back_populates="answers")


class Result(Base):
    __tablename__ = "results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), unique=True, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    incorrect_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    uncertain_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    percentage: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    details_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # per-question details
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    student = relationship("Student", back_populates="result")
