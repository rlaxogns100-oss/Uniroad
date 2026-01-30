"""
경희대학교 2026학년도 정시 환산 점수 계산기
- 600점 만점 기준
- 4개 계열별 환산 (인문/사회/자연/예술체육)
- 영어/한국사 감점제
- 자연계 과학탐구 가산점
"""

from typing import Dict, Any, Optional


class KhuScoreCalculator:
    """경희대 2026 환산 점수 계산기"""
    
    CONVERSION_TABLE = {
        100: 70.12, 99: 69.18, 98: 68.09, 97: 67.36, 96: 66.76, 95: 66.16,
        94: 65.66, 93: 65.19, 92: 64.74, 91: 64.35, 90: 63.97,
        89: 63.57, 88: 63.19, 87: 62.79, 86: 62.44, 85: 62.08,
        84: 61.73, 83: 61.38, 82: 61.05, 81: 60.72, 80: 60.36,
        79: 60.00, 78: 59.65, 77: 59.30, 76: 58.97, 75: 58.62,
        74: 58.22, 73: 57.86, 72: 57.50, 71: 57.16, 70: 56.81,
        69: 56.46, 68: 56.12, 67: 55.75, 66: 55.43, 65: 55.06,
        64: 54.67, 63: 54.30, 62: 53.92, 61: 53.53, 60: 53.13,
        59: 52.72, 58: 52.31, 57: 51.93, 56: 51.57, 55: 51.21,
        54: 50.80, 53: 50.44, 52: 50.07, 51: 49.68, 50: 49.26,
        49: 48.88, 48: 48.50, 47: 48.15, 46: 47.79, 45: 47.47,
        44: 47.15, 43: 46.76, 42: 46.39, 41: 46.03, 40: 45.68,
        39: 45.35, 38: 44.99, 37: 44.65, 36: 44.35, 35: 44.07,
        34: 43.78, 33: 43.47, 32: 43.21, 31: 42.96, 30: 42.71,
        29: 42.47, 28: 42.24, 27: 41.99, 26: 41.71, 25: 41.42,
        24: 41.13, 23: 40.85, 22: 40.58, 21: 40.31, 20: 40.05,
        19: 39.78, 18: 39.52, 17: 39.24, 16: 38.96, 15: 38.68,
        14: 38.41, 13: 38.14, 12: 37.87, 11: 37.61, 10: 37.32,
        9: 37.05, 8: 36.73, 7: 36.32, 6: 35.91, 5: 35.47,
        4: 34.99, 3: 34.43, 2: 33.71, 1: 32.82, 0: 31.12
    }
    
    ENG_DEDUCTION_2026 = {
        1: 0, 2: 0, 3: -2, 4: -4, 5: -8, 6: -12, 7: -18, 8: -24, 9: -30
    }
    
    HIST_DEDUCTION_2026 = {
        1: 0, 2: 0, 3: 0, 4: 0, 5: -2, 6: -4, 7: -8, 8: -14, 9: -20
    }
    
    WEIGHTS = {
        "인문": {"kor": 0.40, "math": 0.25, "inq": 0.35, "inq_n": 2},
        "사회": {"kor": 0.35, "math": 0.35, "inq": 0.30, "inq_n": 2},
        "자연": {"kor": 0.25, "math": 0.40, "inq": 0.35, "inq_n": 2},
        "예술체육": {"kor": 0.60, "math": 0.00, "inq": 0.40, "inq_n": 1},
    }
    
    SCIENCE_INQUIRY_SUBJECTS = [
        "물리학1", "물리학2", "화학1", "화학2", 
        "생명과학1", "생명과학2", "지구과학1", "지구과학2"
    ]
    
    def __init__(self):
        pass
    
    def _convert_percentile_to_standard(self, percentile: float) -> float:
        percentile_int = int(round(percentile))
        
        if percentile_int in self.CONVERSION_TABLE:
            return self.CONVERSION_TABLE[percentile_int]
        
        if percentile_int > 100:
            return self.CONVERSION_TABLE[100]
        if percentile_int < 0:
            return self.CONVERSION_TABLE[0]
        
        lower = percentile_int
        upper = percentile_int + 1
        
        while lower >= 0 and lower not in self.CONVERSION_TABLE:
            lower -= 1
        while upper <= 100 and upper not in self.CONVERSION_TABLE:
            upper += 1
        
        if lower in self.CONVERSION_TABLE and upper in self.CONVERSION_TABLE:
            lower_val = self.CONVERSION_TABLE[lower]
            upper_val = self.CONVERSION_TABLE[upper]
            ratio = (percentile - lower) / (upper - lower)
            return lower_val + (upper_val - lower_val) * ratio
        
        return self.CONVERSION_TABLE.get(50, 50.0)
    
    def _is_science_inquiry(self, normalized_scores: Dict) -> bool:
        subjects = normalized_scores.get("과목별_성적", {})
        inquiry_infer = normalized_scores.get("선택과목", {}).get("탐구_추론", "")
        
        if "자연계" in inquiry_infer:
            return True
        
        for subject_key in subjects.keys():
            if any(sci in subject_key for sci in self.SCIENCE_INQUIRY_SUBJECTS):
                return True
        
        return False
    
    def calculate_track_score(
        self, 
        track: str,
        normalized_scores: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        if track not in self.WEIGHTS:
            return None
        
        w = self.WEIGHTS[track]
        subjects = normalized_scores.get("과목별_성적", {})
        
        result = {
            "계열": track,
            "국어_표준점수": None,
            "수학_표준점수": None,
            "탐구1_변환표준점수": None,
            "탐구2_변환표준점수": None,
            "과탐_가산점": 0,
            "Y_base": None,
            "기본점수_600": None,
            "영어_감점": 0.0,
            "한국사_감점": 0.0,
            "최종점수": None,
            "계산_가능": False,
            "오류": None
        }
        
        kor_data = subjects.get("국어")
        if not kor_data or kor_data.get("표준점수") is None:
            result["오류"] = "국어 표준점수 없음"
            return result
        
        kor_std = kor_data["표준점수"]
        result["국어_표준점수"] = kor_std
        
        math_std = 0
        if w["math"] > 0:
            math_data = subjects.get("수학")
            if not math_data or math_data.get("표준점수") is None:
                result["오류"] = "수학 표준점수 없음"
                return result
            math_std = math_data["표준점수"]
            result["수학_표준점수"] = math_std
        
        inq1_data = subjects.get("탐구1")
        if not inq1_data or inq1_data.get("백분위") is None:
            result["오류"] = "탐구1 백분위 없음"
            return result
        
        inq1_percentile = inq1_data["백분위"]
        inq1_converted = self._convert_percentile_to_standard(inq1_percentile)
        result["탐구1_변환표준점수"] = inq1_converted
        
        inq2_converted = 0
        if w["inq_n"] == 2:
            inq2_data = subjects.get("탐구2")
            if not inq2_data or inq2_data.get("백분위") is None:
                result["오류"] = "탐구2 백분위 없음"
                return result
            
            inq2_percentile = inq2_data["백분위"]
            inq2_converted = self._convert_percentile_to_standard(inq2_percentile)
            result["탐구2_변환표준점수"] = inq2_converted
        
        bonus = 0
        if track == "자연" and w["inq_n"] == 2:
            if self._is_science_inquiry(normalized_scores):
                bonus = 4
                inq1_converted += bonus
                inq2_converted += bonus
                result["과탐_가산점"] = bonus * 2
        
        inq_sum = inq1_converted + inq2_converted
        Y_base = (kor_std * w["kor"]) + (math_std * w["math"]) + (inq_sum * w["inq"])
        result["Y_base"] = round(Y_base, 3)
        
        base_score_800 = Y_base * 4
        base_score_600 = base_score_800 * 0.75
        result["기본점수_600"] = round(base_score_600, 2)
        
        eng_data = subjects.get("영어")
        eng_grade = eng_data.get("등급", 2) if eng_data else 2
        eng_deduction_800 = self.ENG_DEDUCTION_2026.get(eng_grade, 0)
        eng_deduction_600 = eng_deduction_800 * 0.75
        result["영어_감점"] = round(eng_deduction_600, 2)
        
        hist_data = subjects.get("한국사")
        hist_grade = hist_data.get("등급", 2) if hist_data else 2
        hist_deduction_800 = self.HIST_DEDUCTION_2026.get(hist_grade, 0)
        hist_deduction_600 = hist_deduction_800 * 0.75
        result["한국사_감점"] = round(hist_deduction_600, 2)
        
        final_score = base_score_600 + eng_deduction_600 + hist_deduction_600
        result["최종점수"] = round(final_score, 2)
        result["계산_가능"] = True
        
        return result
    
    def calculate_all_tracks(
        self, 
        normalized_scores: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        results = {}
        
        for track in ["인문", "사회", "자연", "예술체육"]:
            track_result = self.calculate_track_score(track, normalized_scores)
            if track_result:
                results[track] = track_result
        
        return results


def calculate_khu_score(normalized_scores: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """정규화된 성적을 경희대 환산 점수로 변환"""
    calculator = KhuScoreCalculator()
    return calculator.calculate_all_tracks(normalized_scores)
