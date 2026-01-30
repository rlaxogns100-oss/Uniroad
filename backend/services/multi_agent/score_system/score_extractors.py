"""
대학별 점수 추출 로직 (레지스트리 패턴)
"""
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

from .config import UNIVERSITY_CONFIGS, UniversityConfig


class ScoreExtractor(ABC):
    """점수 추출 추상 클래스"""
    
    @abstractmethod
    def extract(
        self, 
        calc_output: Dict[str, Any], 
        row: Dict[str, Any]
    ) -> Optional[float]:
        pass


class KoreaUnivExtractor(ScoreExtractor):
    """고려대학교 점수 추출"""
    
    def extract(self, calc_output: Dict[str, Any], row: Dict[str, Any]) -> Optional[float]:
        field = row.get("field")
        row_type = row.get("type", "일반")
        total_scale = row.get("total_scale") or 1000
        
        track = calc_output.get("track") or ""
        if field != track:
            return None
            
        if row_type == "교과우수":
            raw = calc_output.get("교과우수")
            calc_scale = 800
        else:
            raw = calc_output.get("일반")
            calc_scale = 1000
            
        if raw is None:
            return None
        return round((raw / calc_scale) * total_scale, 2)


class KhuExtractor(ScoreExtractor):
    """경희대학교 점수 추출"""
    
    def extract(self, calc_output: Dict[str, Any], row: Dict[str, Any]) -> Optional[float]:
        field = row.get("field")
        total_scale = row.get("total_scale") or 800
        
        계열별 = calc_output.get("계열별") or calc_output
        track_data = 계열별.get(field)
        
        if not track_data or not track_data.get("계산_가능"):
            return None
            
        raw = track_data.get("최종점수")
        if raw is None:
            return None
            
        calc_scale = 600
        return round((raw / calc_scale) * total_scale, 2)


class SogangExtractor(ScoreExtractor):
    """서강대학교 점수 추출"""
    
    FIELD_TO_TRACK = {"인문": "인문", "상경": "인문", "자연": "자연"}
    
    def extract(self, calc_output: Dict[str, Any], row: Dict[str, Any]) -> Optional[float]:
        field = row.get("field")
        total_scale = row.get("total_scale") or 600
        
        track = self.FIELD_TO_TRACK.get(field, field)
        계열별 = calc_output.get("계열별") or calc_output
        track_data = 계열별.get(track)
        
        if not track_data or not track_data.get("계산_가능"):
            return None
            
        raw = track_data.get("최종점수")
        if raw is None:
            return None
            
        calc_scale = 600
        return round((raw / calc_scale) * total_scale, 2)


class SnuExtractor(ScoreExtractor):
    """서울대학교 점수 추출"""
    
    def extract(self, calc_output: Dict[str, Any], row: Dict[str, Any]) -> Optional[float]:
        계열별 = calc_output.get("계열별") or calc_output
        track_data = 계열별.get("일반전형")
        
        if not track_data or not track_data.get("계산_가능"):
            return None
            
        raw = track_data.get("최종점수")
        if raw is None:
            raw = track_data.get("최종점수_1000")
        if raw is None:
            return None
            
        return round(raw, 2)
    
    def get_raw_final_score(self, calc_output: Dict[str, Any]) -> Optional[float]:
        """최종점수(raw) 반환"""
        계열별 = calc_output.get("계열별") or calc_output
        track_data = 계열별.get("일반전형") or {}
        return track_data.get("최종점수")


class YonseiExtractor(ScoreExtractor):
    """연세대학교 점수 추출"""
    
    def extract(self, calc_output: Dict[str, Any], row: Dict[str, Any]) -> Optional[float]:
        field = row.get("field")
        total_scale = row.get("total_scale") or 1000
        
        계열별 = calc_output.get("계열별") or calc_output
        track_data = 계열별.get(field)
        
        if not track_data or not track_data.get("계산_가능"):
            return None
            
        raw = track_data.get("최종점수")
        if raw is None:
            return None
            
        calc_scale = 1000
        return round((raw / calc_scale) * total_scale, 2)


# ============================================================
# 추출기 레지스트리
# ============================================================
EXTRACTOR_REGISTRY: Dict[str, ScoreExtractor] = {
    "고려대학교": KoreaUnivExtractor(),
    "경희대학교": KhuExtractor(),
    "서강대학교": SogangExtractor(),
    "서울대학교": SnuExtractor(),
    "연세대학교": YonseiExtractor(),
}


def get_extractor(univ_name: str) -> Optional[ScoreExtractor]:
    """대학명으로 점수 추출기 반환"""
    return EXTRACTOR_REGISTRY.get(univ_name)


def extract_score_for_comparison(
    univ: str, 
    calc_output: Dict[str, Any], 
    row: Dict[str, Any]
) -> Optional[float]:
    """대학별 계산 결과에서 비교용 점수 추출"""
    extractor = get_extractor(univ)
    if extractor is None:
        return None
    return extractor.extract(calc_output, row)
