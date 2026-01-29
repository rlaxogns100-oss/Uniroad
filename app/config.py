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
    """점수 판정 임계값 (4점 단위)"""
    SAFE: int = 0       # 컷 이상: 안정
    MODERATE: int = 4   # 컷 - 4 이상: 적정
    RISKY: int = 8      # 컷 - 8 이상: 소신
    # 그 외: 상향


THRESHOLDS = ClassificationThresholds()


# ============================================================
# 판정 레이블
# ============================================================
class ClassificationLabel:
    SAFE = "🟢 안정"
    MODERATE = "🟡 적정"
    RISKY = "🔴 소신"
    REACH = "⚪ 상향"


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
    "type": "전형",
    "field": "계열",
    "cut_70_score": "70% 점수 컷",
    "cut_50_score": "50% 점수 컷",
    "my_score": "내 점수",
    "최종점수": "최종점수",
    "판정": "판정",
    "recruit_count": "모집",
    "competition_rate": "경쟁률",
}

DISPLAY_COLUMN_ORDER = [
    "univ", "major", "type", "field", 
    "cut_70_score", "cut_50_score", "my_score", "최종점수",
    "판정", "recruit_count", "competition_rate"
]
