"""
프로젝트 전역 설정 및 상수 정의
"""
from typing import Dict, Callable, Any
from dataclasses import dataclass


# ============================================================
# 판정 기준 설정
# ============================================================
@dataclass(frozen=True)
class ClassificationThresholds:
    """점수 판정 임계값 (퍼센트 기반)"""
    UNDER_PERFORM: float = 1.0   # 컷 + 1% 이상: 하향
    SAFE: float = 0.0            # 컷 이상: 안정
    MODERATE: float = -1.0       # 컷 - 1% 이상: 적정
    REACH: float = -2.0          # 컷 - 2% 이상: 상향
    SNIPING: float = -3.0        # 컷 - 3% 이상: 스나이핑
    # 그 외: 불가능


THRESHOLDS = ClassificationThresholds()


# ============================================================
# 판정 레이블 (새 기준: 안정/적정/소신/도전/어려움)
# ============================================================
class ClassificationLabel:
    """
    새로운 판정 기준 (suneung-calculator 기반):
    - 안정: 내 점수 >= safeScore
    - 적정: 내 점수 >= appropriateScore
    - 소신: 내 점수 >= expectedScore
    - 도전: 내 점수 >= challengeScore
    - 어려움: 내 점수 < challengeScore
    """
    SAFE = "🟢 안정"
    APPROPRIATE = "🟡 적정"
    EXPECTED = "🟠 소신"
    CHALLENGE = "🔴 도전"
    DIFFICULT = "⚫ 어려움"
    
    # 기존 호환용 (deprecated)
    UNDER_PERFORM = "🔵 하향"
    MODERATE = "🟡 적정"
    REACH = "🟠 상향"
    SNIPING = "🔴 스나이핑"
    IMPOSSIBLE = "⚫ 불가능"


# ============================================================
# 대학별 설정
# ============================================================
@dataclass
class UniversityConfig:
    """대학별 환산 설정"""
    name: str                    # 대학명 (한글)
    calc_scale: float            # 계산기 출력 스케일
    use_raw_for_comparison: bool # 환산 없이 raw 비교 여부
    field_mapping: Dict[str, str] = None  # 입결 field → 계산기 track 매핑
    
    def __post_init__(self):
        if self.field_mapping is None:
            self.field_mapping = {}


UNIVERSITY_CONFIGS: Dict[str, UniversityConfig] = {
    "고려대학교": UniversityConfig(
        name="고려대학교",
        calc_scale=1000,
        use_raw_for_comparison=False,
        field_mapping={"인문": "인문", "자연": "자연"},
    ),
    "경희대학교": UniversityConfig(
        name="경희대학교",
        calc_scale=600,
        use_raw_for_comparison=False,
        field_mapping={"인문": "인문", "사회": "사회", "자연": "자연", "예술체육": "예술체육"},
    ),
    "서강대학교": UniversityConfig(
        name="서강대학교",
        calc_scale=600,
        use_raw_for_comparison=False,
        field_mapping={"인문": "인문", "상경": "인문", "자연": "자연"},
    ),
    "서울대학교": UniversityConfig(
        name="서울대학교",
        calc_scale=380,  # raw 점수 기준
        use_raw_for_comparison=True,  # 환산 없이 raw 비교
        field_mapping={},
    ),
    "연세대학교": UniversityConfig(
        name="연세대학교",
        calc_scale=1000,
        use_raw_for_comparison=False,
        field_mapping={"인문": "인문", "자연": "자연", "의약": "의약"},
    ),
}


# ============================================================
# 표시 컬럼 설정
# ============================================================
DISPLAY_COLUMNS = {
    "univ": "대학",
    "major": "학과",
    "gun": "군",
    "track": "계열",
    "my_score": "내 점수",
    "safe_score": "안정컷",
    "appropriate_score": "적정컷",
    "expected_score": "소신컷",
    "challenge_score": "도전컷",
    "판정": "판정",
    # 기존 호환
    "type": "전형",
    "field": "계열",
    "cut_70_score": "70% 점수 컷",
    "cut_50_score": "50% 점수 컷",
    "최종점수": "최종점수",
    "recruit_count": "모집",
    "competition_rate": "경쟁률",
}

DISPLAY_COLUMN_ORDER = [
    "univ", "major", "gun", "track",
    "my_score", "safe_score", "appropriate_score", "expected_score", "challenge_score",
    "판정"
]
