"""IngestAPI — POST /events (엣지 수신), GET /events (이력 조회)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..ml.identifier import identifier
from ..models import CoughEvent

router = APIRouter(tags=["events"])

AUDIO_DIR = Path("audio_store")
AUDIO_DIR.mkdir(exist_ok=True)


@router.post("/events", status_code=201)
async def create_event(
    audio: UploadFile = File(...),
    meta: str = Form(...),
    db: Session = Depends(get_db),
):
    m = json.loads(meta)
    wav_path = AUDIO_DIR / f"{uuid.uuid4().hex}.wav"
    wav_path.write_bytes(await audio.read())

    result = identifier.identify(str(wav_path))  # P2: 항상 unknown

    event = CoughEvent(
        device_id=m.get("device_id", "unknown"),
        captured_at=datetime.fromisoformat(m["captured_at"]),
        person_id=result.person_id,
        similarity=result.similarity,
        peak_rms=m.get("peak_rms"),
        audio_path=str(wav_path),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    # P5에서 여기에 AlertEngine.evaluate() + WebSocket 브로드캐스트 추가
    return {"id": event.id, "person_id": event.person_id, "similarity": event.similarity}


@router.get("/events")
def list_events(
    limit: int = 50,
    unknown: bool | None = None,
    person: int | None = None,
    db: Session = Depends(get_db),
):
    q = select(CoughEvent).order_by(CoughEvent.received_at.desc()).limit(limit)
    if unknown:
        q = q.where(CoughEvent.person_id.is_(None))
    if person is not None:
        q = q.where(CoughEvent.person_id == person)
    rows = db.scalars(q).all()
    return [
        {
            "id": e.id,
            "device_id": e.device_id,
            "captured_at": e.captured_at.isoformat(),
            "received_at": e.received_at.isoformat(),
            "person_id": e.person_id,
            "similarity": e.similarity,
            "peak_rms": e.peak_rms,
        }
        for e in rows
    ]
