"""AudioCapture — 마이크(또는 WAV 파일)에서 오디오를 읽어 링버퍼에 유지.

두 가지 소스를 지원한다:
  - mic : sounddevice 입력 스트림 (I2S MEMS 마이크 포함, 32bit → float 변환 + 게인)
  - file: WAV 파일을 실시간처럼 흘려보내는 시뮬레이션 모드 (마이크 없이 개발용)
"""
from __future__ import annotations

import threading
import time
import wave
from collections import deque

import numpy as np

SAMPLE_RATE = 16000  # 파이프라인 전체 기준 샘플레이트


class RingBuffer:
    """최근 max_seconds 초의 오디오(float32 mono)를 유지."""

    def __init__(self, max_seconds: float, sample_rate: int = SAMPLE_RATE):
        self.sample_rate = sample_rate
        self.max_samples = int(max_seconds * sample_rate)
        self._buf: deque[np.ndarray] = deque()
        self._n = 0
        self._lock = threading.Lock()

    def push(self, chunk: np.ndarray) -> None:
        with self._lock:
            self._buf.append(chunk)
            self._n += len(chunk)
            while self._n > self.max_samples and self._buf:
                self._n -= len(self._buf.popleft())

    def read_last(self, seconds: float) -> np.ndarray:
        """최근 seconds 초 구간을 복사해 반환."""
        n = int(seconds * self.sample_rate)
        with self._lock:
            if not self._buf:
                return np.zeros(0, dtype=np.float32)
            data = np.concatenate(list(self._buf))
        return data[-n:] if len(data) > n else data


class AudioCapture:
    """오디오 소스를 열고 RingBuffer를 채운다. on_chunk 콜백으로 검출기에 전달."""

    def __init__(
        self,
        source: str = "mic",           # "mic" | "file"
        wav_path: str | None = None,   # source=="file"일 때
        device: int | str | None = None,
        gain: float = 1.0,             # I2S MEMS 마이크는 20~30 권장
        buffer_seconds: float = 10.0,
        chunk_ms: int = 100,
    ):
        self.source = source
        self.wav_path = wav_path
        self.device = device
        self.gain = gain
        self.ring = RingBuffer(buffer_seconds)
        self.chunk_samples = int(SAMPLE_RATE * chunk_ms / 1000)
        self.on_chunk = None  # callable(np.ndarray) — CoughDetector가 등록
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ---------------------------------------------------------- public
    def start(self) -> None:
        target = self._run_mic if self.source == "mic" else self._run_file
        self._thread = threading.Thread(target=target, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    # ---------------------------------------------------------- mic
    def _run_mic(self) -> None:
        import sounddevice as sd

        def callback(indata, frames, t, status):
            if status:
                print(f"[audio] {status}", flush=True)
            mono = indata[:, 0].astype(np.float32) * self.gain
            np.clip(mono, -1.0, 1.0, out=mono)
            self._emit(mono)

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=self.chunk_samples,
            device=self.device,
            callback=callback,
        ):
            while not self._stop.is_set():
                time.sleep(0.1)

    # ---------------------------------------------------------- file (개발용)
    def _run_file(self) -> None:
        assert self.wav_path, "source='file'이면 wav_path 필요"
        with wave.open(self.wav_path, "rb") as w:
            rate = w.getframerate()
            width = w.getsampwidth()
            nch = w.getnchannels()
            raw = w.readframes(w.getnframes())

        dtype = {1: np.int8, 2: np.int16, 4: np.int32}[width]
        data = np.frombuffer(raw, dtype=dtype).astype(np.float32)
        data /= float(np.iinfo(dtype).max)
        if nch > 1:
            data = data.reshape(-1, nch)[:, 0]
        if rate != SAMPLE_RATE:  # 단순 리샘플 (개발용으로 충분)
            idx = np.linspace(0, len(data) - 1, int(len(data) * SAMPLE_RATE / rate))
            data = data[idx.astype(np.int64)]

        chunk_dur = self.chunk_samples / SAMPLE_RATE
        for i in range(0, len(data), self.chunk_samples):
            if self._stop.is_set():
                return
            self._emit(data[i : i + self.chunk_samples])
            time.sleep(chunk_dur)  # 실시간 흉내

    # ---------------------------------------------------------- common
    def _emit(self, chunk: np.ndarray) -> None:
        self.ring.push(chunk)
        if self.on_chunk:
            self.on_chunk(chunk)
