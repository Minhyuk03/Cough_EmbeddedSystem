"""EventSender — 기침 클립을 서버 POST /events로 전송. 실패 시 디스크 큐 + 지수 백오프 재시도 (TC-05)."""
from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests

QUEUE_DIR = Path(__file__).parent / "queue"


class EventSender:
    def __init__(
        self,
        server_url: str,               # 예: http://<서버IP>:8000
        device_id: str = "rpi5-01",
        timeout: float = 5.0,
        max_backoff: float = 60.0,
    ):
        self.endpoint = server_url.rstrip("/") + "/events"
        self.device_id = device_id
        self.timeout = timeout
        self.max_backoff = max_backoff
        QUEUE_DIR.mkdir(exist_ok=True)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._retry_loop, daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------
    def send(self, wav_bytes: bytes, peak_rms: float) -> None:
        meta = {
            "device_id": self.device_id,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "peak_rms": round(peak_rms, 4),
        }
        if not self._post(wav_bytes, meta):
            self._enqueue(wav_bytes, meta)

    def stop(self) -> None:
        self._stop.set()

    # ------------------------------------------------------------------
    def _post(self, wav_bytes: bytes, meta: dict) -> bool:
        try:
            r = requests.post(
                self.endpoint,
                files={"audio": ("cough.wav", wav_bytes, "audio/wav")},
                data={"meta": json.dumps(meta)},
                timeout=self.timeout,
            )
            ok = r.status_code < 300
            print(f"[sender] POST {r.status_code} {r.text[:120]}", flush=True)
            return ok
        except requests.RequestException as e:
            print(f"[sender] 전송 실패: {e}", flush=True)
            return False

    def _enqueue(self, wav_bytes: bytes, meta: dict) -> None:
        stem = QUEUE_DIR / uuid.uuid4().hex
        stem.with_suffix(".wav").write_bytes(wav_bytes)
        stem.with_suffix(".json").write_text(json.dumps(meta))
        print(f"[sender] 큐 적재: {stem.name}", flush=True)

    def _retry_loop(self) -> None:
        backoff = 2.0
        while not self._stop.is_set():
            pending = sorted(QUEUE_DIR.glob("*.json"))
            if not pending:
                backoff = 2.0
                time.sleep(2)
                continue
            sent_any = False
            for meta_path in pending:
                wav_path = meta_path.with_suffix(".wav")
                if not wav_path.exists():
                    meta_path.unlink(missing_ok=True)
                    continue
                meta = json.loads(meta_path.read_text())
                if self._post(wav_path.read_bytes(), meta):
                    wav_path.unlink(missing_ok=True)
                    meta_path.unlink(missing_ok=True)
                    sent_any = True
                else:
                    break  # 서버 아직 다운 → 백오프
            if sent_any:
                backoff = 2.0
            else:
                time.sleep(backoff)
                backoff = min(backoff * 2, self.max_backoff)
