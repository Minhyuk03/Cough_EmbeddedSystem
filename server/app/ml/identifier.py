"""SpeakerIdentifier 스텁 — P3에서 ECAPA-TDNN 임베딩 + 코사인 매칭으로 교체.

인터페이스만 확정해 두어 API 코드는 P3 이후에도 무수정.
"""
from __future__ import annotations


class IdentifyResult:
    def __init__(self, person_id: int | None, similarity: float | None):
        self.person_id = person_id
        self.similarity = similarity


class SpeakerIdentifier:
    """P2 스텁: 항상 unknown 반환 (FR-05의 unknown 경로)."""

    def identify(self, wav_path: str) -> IdentifyResult:
        return IdentifyResult(person_id=None, similarity=None)


identifier = SpeakerIdentifier()  # 싱글턴 — P3에서 모델 로딩 비용 1회
