"""
서강대학교 2026학년도 정시 환산 점수 계산기
- A형(수학가중)/B형(국어가중) 중 높은 점수 반영
- 탐구 변환표준점수표 (인문/자연/자유전공 별도)
- 영어/한국사 가산점 방식
"""

from typing import Dict, Any, Optional


class SogangScoreCalculator:
    """서강대 2026 환산 점수 계산기"""
    
    CONV_TABLE = {
        100: [70.00, 70.50, 71.00], 99: [69.52, 70.02, 70.60], 98: [69.05, 69.55, 70.13], 97: [68.71, 69.21, 69.81],
        96: [68.43, 68.93, 69.56], 95: [68.19, 68.69, 69.30], 94: [67.95, 68.34, 69.08], 93: [67.73, 68.01, 68.79],
        92: [67.46, 67.75, 68.50], 91: [67.22, 67.51, 68.26], 90: [66.99, 67.27, 68.02], 89: [66.74, 67.02, 67.77],
        88: [66.48, 66.77, 67.53], 87: [66.21, 66.50, 67.27], 86: [65.97, 66.26, 67.05], 85: [65.74, 66.03, 66.83],
        84: [65.43, 65.72, 66.54], 83: [65.17, 65.45, 66.25], 82: [64.91, 65.20, 65.97], 81: [64.65, 64.93, 65.70],
        80: [64.36, 64.65, 65.40], 79: [64.08, 64.37, 65.11], 78: [63.79, 64.08, 64.81], 77: [63.49, 63.78, 64.52],
        76: [63.22, 63.50, 64.25], 75: [62.93, 63.21, 63.96], 74: [62.62, 62.91, 63.62], 73: [62.32, 62.61, 63.32],
        72: [62.04, 62.33, 63.03], 71: [61.77, 62.06, 62.74], 70: [61.49, 61.78, 62.45], 69: [61.12, 61.40, 62.07],
        68: [60.74, 61.03, 61.69], 67: [60.39, 60.68, 61.29], 66: [60.05, 60.34, 60.93], 65: [59.64, 59.93, 60.53],
        64: [59.24, 59.52, 60.10], 63: [58.83, 59.12, 59.69], 62: [58.42, 58.71, 59.27], 61: [58.00, 58.29, 58.84],
        60: [57.61, 57.89, 58.40], 59: [57.20, 57.49, 57.95], 58: [56.76, 57.05, 57.50], 57: [56.37, 56.65, 57.08],
        56: [55.96, 56.24, 56.69], 55: [55.54, 55.83, 56.29], 54: [55.03, 55.32, 55.84], 53: [54.61, 54.89, 55.45],
        52: [54.23, 54.52, 55.04], 51: [53.84, 54.12, 54.61], 50: [53.43, 53.71, 54.16], 49: [53.02, 53.31, 53.73],
        48: [52.60, 52.89, 53.31], 47: [52.20, 52.48, 52.93], 46: [51.77, 52.05, 52.53], 45: [51.40, 51.69, 52.18],
        44: [51.06, 51.35, 51.83], 43: [50.58, 50.87, 51.40], 42: [50.13, 50.41, 50.99], 41: [49.73, 50.02, 50.59],
        40: [49.35, 49.63, 50.21], 39: [48.97, 49.26, 49.85], 38: [48.52, 48.81, 49.45], 37: [48.16, 48.45, 49.08],
        36: [47.83, 48.12, 48.75], 35: [47.53, 47.82, 48.44], 34: [47.20, 47.49, 48.12], 33: [46.87, 47.16, 47.78],
        32: [46.60, 46.88, 47.49], 31: [46.32, 46.61, 47.22], 30: [46.05, 46.33, 46.94], 29: [45.79, 46.08, 46.68],
        28: [45.56, 45.85, 46.43], 27: [45.32, 45.61, 46.15], 26: [45.01, 45.30, 45.84], 25: [44.67, 44.96, 45.52],
        24: [44.32, 44.61, 45.20], 23: [44.01, 44.30, 44.90], 22: [43.70, 43.99, 44.60], 21: [43.39, 43.67, 44.30],
        20: [43.11, 43.40, 44.02], 19: [42.82, 43.11, 43.72], 18: [42.54, 42.82, 43.43], 17: [42.21, 42.49, 43.13],
        16: [41.89, 42.18, 42.82], 15: [41.57, 41.86, 42.51], 14: [41.25, 41.54, 42.21], 13: [40.92, 41.21, 41.92],
        12: [40.59, 40.88, 41.62], 11: [40.32, 40.60, 41.33], 10: [40.01, 40.29, 41.01], 9: [39.69, 39.98, 40.72],
        8: [39.36, 39.65, 40.36], 7: [38.85, 39.14, 39.91], 6: [38.35, 38.63, 39.46], 5: [37.85, 38.14, 38.98],
        4: [37.32, 37.61, 38.45], 3: [36.73, 37.02, 37.83], 2: [35.96, 36.25, 37.04], 1: [34.98, 35.27, 36.06],
        0: [32.78, 33.07, 34.19]
    }
    
    ENG_SCORES = {1: 100.0, 2: 99.5, 3: 98.5, 4: 97.0, 5: 95.0, 6: 92.5, 7: 89.5, 8: 86.0, 9: 82.0}
    
    TRACK_TYPES = {
        "인문": {"name": "인문/지식융합", "dept_idx": 0},
        "자연": {"name": "자연계열", "dept_idx": 1},
        "자유전공": {"name": "자유전공", "dept_idx": 2}
    }
    
    def __init__(self):
        pass
    
    def _interpolate_conv_score(self, pct: float, dept_idx: int) -> float:
        pct = float(pct)
        pct = max(0.0, min(100.0, pct))
        
        pct_int = int(pct)
        if pct_int in self.CONV_TABLE:
            return float(self.CONV_TABLE[pct_int][dept_idx])
        
        keys = sorted(self.CONV_TABLE.keys())
        lo_key = max(k for k in keys if k <= pct)
        hi_key = min(k for k in keys if k >= pct)
        
        if lo_key == hi_key:
            return float(self.CONV_TABLE[lo_key][dept_idx])
        
        lo_val = float(self.CONV_TABLE[lo_key][dept_idx])
        hi_val = float(self.CONV_TABLE[hi_key][dept_idx])
        
        w = (pct - lo_key) / (hi_key - lo_key)
        return lo_val + w * (hi_val - lo_val)
    
    def calculate_track_score(
        self,
        track_type: str,
        normalized_scores: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        if track_type not in self.TRACK_TYPES:
            return None
        
        config = self.TRACK_TYPES[track_type]
        dept_idx = config["dept_idx"]
        subjects = normalized_scores.get("과목별_성적", {})
        
        result = {
            "모집단위": config["name"],
            "국어_표준점수": None,
            "수학_표준점수": None,
            "탐구1_변환점수": None,
            "탐구2_변환점수": None,
            "탐구_합계": None,
            "영어_가산": None,
            "한국사_가산": None,
            "A형_점수": None,
            "B형_점수": None,
            "적용방식": None,
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
        
        math_data = subjects.get("수학")
        if not math_data or math_data.get("표준점수") is None:
            result["오류"] = "수학 표준점수 없음"
            return result
        
        math_std = math_data["표준점수"]
        result["수학_표준점수"] = math_std
        
        inq1_data = subjects.get("탐구1")
        inq2_data = subjects.get("탐구2")
        
        if not inq1_data or inq1_data.get("백분위") is None:
            result["오류"] = "탐구1 백분위 없음"
            return result
        if not inq2_data or inq2_data.get("백분위") is None:
            result["오류"] = "탐구2 백분위 없음"
            return result
        
        t1_conv = self._interpolate_conv_score(inq1_data["백분위"], dept_idx)
        t2_conv = self._interpolate_conv_score(inq2_data["백분위"], dept_idx)
        tamgu_sum = t1_conv + t2_conv
        
        result["탐구1_변환점수"] = round(t1_conv, 2)
        result["탐구2_변환점수"] = round(t2_conv, 2)
        result["탐구_합계"] = round(tamgu_sum, 2)
        
        eng_data = subjects.get("영어")
        eng_grade = eng_data.get("등급", 1) if eng_data else 1
        eng_pt = self.ENG_SCORES.get(eng_grade, 82.0)
        result["영어_가산"] = eng_pt
        
        hist_data = subjects.get("한국사")
        hist_grade = hist_data.get("등급", 1) if hist_data else 1
        if hist_grade <= 4:
            hist_pt = 10.0
        else:
            hist_pt = 10.0 - (hist_grade - 4) * 0.5
        result["한국사_가산"] = hist_pt
        
        raw_a = (kor_std * 1.1) + (math_std * 1.3) + (tamgu_sum * 0.6) + eng_pt + hist_pt
        raw_b = (kor_std * 1.3) + (math_std * 1.1) + (tamgu_sum * 0.6) + eng_pt + hist_pt
        
        score_a = round(raw_a, 2)
        score_b = round(raw_b, 2)
        
        result["A형_점수"] = score_a
        result["B형_점수"] = score_b
        
        if score_a > score_b:
            result["최종점수"] = score_a
            result["적용방식"] = "A형 (수학가중)"
        elif score_b > score_a:
            result["최종점수"] = score_b
            result["적용방식"] = "B형 (국어가중)"
        else:
            result["최종점수"] = score_a
            result["적용방식"] = "A/B형 동점"
        
        result["계산_가능"] = True
        return result
    
    def calculate_all_tracks(
        self,
        normalized_scores: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        results = {}
        
        for track_type in self.TRACK_TYPES.keys():
            track_result = self.calculate_track_score(track_type, normalized_scores)
            if track_result:
                results[track_type] = track_result
        
        return results


def calculate_sogang_score(normalized_scores: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """정규화된 성적을 서강대 환산 점수로 변환"""
    calculator = SogangScoreCalculator()
    return calculator.calculate_all_tracks(normalized_scores)
