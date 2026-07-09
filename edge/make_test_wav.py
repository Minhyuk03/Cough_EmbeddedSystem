"""테스트용 합성 기침 WAV 생성 — 무음 2초 + 0.3초 버스트 + 무음 2초 (16kHz).

사용: python make_test_wav.py [출력파일=test_cough.wav]
실제 기침 녹음이 있으면 그걸 쓰는 게 더 좋다 (P3 데이터 수집과 병행).
"""
import sys
import wave

import numpy as np

sr = 16000
out = sys.argv[1] if len(sys.argv) > 1 else "test_cough.wav"

sil = np.zeros(2 * sr)
burst = np.random.randn(int(0.3 * sr)) * 0.5
sig = np.concatenate([sil, burst, sil]).clip(-1, 1)
pcm = (sig * 32767).astype(np.int16)

with wave.open(out, "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(sr)
    w.writeframes(pcm.tobytes())

print(f"생성됨: {out} ({len(sig)/sr:.1f}초)")
