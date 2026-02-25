from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from app.agents.completion_agent import CompletionAgent
from app.agents.extractor_agent import ExtractorAgent
from app.services.adiga_mapper import to_adiga_payload
from app.services.profile_repository import ProfileRepository


@dataclass
class ProfileAgentResult:
    user_id: str
    extracted_scores: Dict[str, Any]
    completed_scores: Dict[str, Any]
    adiga_input: Dict[str, str]
    estimated_subjects: list[str]
    db_record: Dict[str, str]
    agent_trace: list[str]


class ProfileAgentService:
    """추출 -> 보완/추정 -> adiga 변환 -> user_profile 저장 파이프라인."""

    def __init__(self, repository: ProfileRepository):
        self.repository = repository
        self.extractor = ExtractorAgent()
        self.completion = CompletionAgent()

    def process(self, user_id: str, message: str) -> ProfileAgentResult:
        trace = ["extractor_agent: 채팅에서 성적 후보 추출 시작"]
        extracted = self.extractor.extract(message)
        extracted_scores = extracted.get("scores", {})
        completion_input_scores = extracted.get("scores_for_completion", {})
        evidence_count = len(extracted.get("evidences", []))
        trace.append(f"extractor_agent: 과목 {len(completion_input_scores)}개 추출, 근거 {evidence_count}개")

        trace.append("completion_agent: 누락 과목 보완/추정 시작")
        completed_scores, estimated_subjects = self.completion.complete(completion_input_scores)
        trace.append(
            f"completion_agent: 보완 완료, 추정 과목 {len(estimated_subjects)}개({', '.join(estimated_subjects) or '없음'})"
        )

        trace.append("formatter_agent: adiga2 입력 스키마 변환")
        adiga_input = to_adiga_payload(completed_scores)
        trace.append("formatter_agent: 변환 완료")

        trace.append("storage_agent: user_profile DB upsert")
        db_record = self.repository.upsert_profile(
            user_id=user_id,
            adiga_payload=adiga_input,
            extracted_scores=extracted_scores,
            completed_scores=completed_scores,
            estimated_subjects=estimated_subjects,
            latest_message=message,
        )
        trace.append("storage_agent: 저장 완료")

        return ProfileAgentResult(
            user_id=user_id,
            extracted_scores=extracted_scores,
            completed_scores=completed_scores,
            adiga_input=adiga_input,
            estimated_subjects=estimated_subjects,
            db_record=db_record,
            agent_trace=trace,
        )

