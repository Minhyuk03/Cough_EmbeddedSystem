"""SQLAlchemy 모델 — Class 다이어그램의 Person·CoughEvent·Alert 대응."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Person(Base):
    __tablename__ = "persons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alias: Mapped[str] = mapped_column(String(50), unique=True)  # 실명 대신 alias (NFR-06)
    embedding_ref: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)  # 임베딩 평균
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    events: Mapped[List["CoughEvent"]] = relationship(back_populates="person")


class CoughEvent(Base):
    __tablename__ = "cough_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(50))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    person_id: Mapped[Optional[int]] = mapped_column(ForeignKey("persons.id"), nullable=True)  # None = unknown
    similarity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    peak_rms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    audio_path: Mapped[str] = mapped_column(String(255))  # 저장된 wav 경로

    person: Mapped[Optional[Person]] = relationship(back_populates="events")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[Optional[int]] = mapped_column(ForeignKey("persons.id"), nullable=True)
    rule: Mapped[str] = mapped_column(String(100))       # 예: "1h>=10"
    message: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
