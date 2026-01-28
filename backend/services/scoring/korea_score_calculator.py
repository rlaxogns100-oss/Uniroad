"""
고려대학교 2026학년도 정시 환산 점수 계산기
- 1000점 환산형
- 인문: 560점 기준 (국1/수1/탐0.8)
- 자연: 640점 기준 (국1/수1.2/탐1)
- 탐구 변환표준점수표
"""

from typing import Dict, Any, Optional


class KoreaUnivScoreCalculator:
    """고려대 2026 환산 점수 계산기 (1000점 환산)"""
    
    # 사회탐구 변환표
    SOCIAL_TABLE = {
        100: 67.22, 99: 67.05, 98: 66.88, 97: 66.71, 96: 66.54,
        95: 66.30, 94: 66.05, 93: 65.80, 92: 65.55, 91: 65.30,
        90: 65.05, 89: 64.80, 88: 64.55, 87: 64.30, 86: 64.05,
        85: 63.80, 84: 63.55, 83: 63.30, 82: 63.05, 81: 62.80,
        80: 62.55, 75: 61.30, 70: 60.05, 65: 58.80, 60: 57.55
    }
    
    # 과학탐구 변환표
    SCIENCE_TABLE = {
        100: 69.50, 99: 69.10, 98: 68.70, 97: 68.30, 96: 67.90,
        95: 67.50, 94: 67.10, 93: 66.70, 92: 66.30, 91: 65.90,
        90: 65.50, 89: 65.10, 88: 64.70, 87: 64.30, 86: 63.90,
        85: 63.50, 84: 63.10, 83: 62.70, 82: 62.30, 81: 61.90,
        80: 61.50, 75: 59.50, 70: 57.50, 65: 55.50, 60: 53.50
    }
    
    TRACK_TYPES = {
        "인문": {
            "name": "인문 (경영/정경/문과/통계 등)",
            "kor_weight": 1.0,
            "math_weight": 1.0,
            "inq_weight": 0.8,
            "base_score": 560.0
        },
        "자연": {
            "name": "자연 (의대/공대/이과 등)",
            "kor_weight": 1.0,
            "math_weight": 1.2,
            "inq_weight": 1.0,
            "base_score": 640.0
        }
    }
    
    def __init__(self):
        pass
    
    def _get_conv_score(self, percentile: float, is_science: bool) -> float:
        """백분위를 변환표준점수로 변환 (선형 보간)"""
        table = self.SCIENCE_TABLE if is_science else self.SOCIAL_TABLE
        percentile_int = int(round(percentile))
        
        if percentile_int in table:
            return table[percentile_int]
        
        keys = sorted(table.keys())
        
        # 범위 밖
        if percentile_int < keys[0]:
            return table[keys[0]] - (keys[0] - percentile_int) * 0.5
        
        # 선형 보간
        for i in range(len(keys) - 1):
            if keys[i] < percentile_int < keys[i + 1]:
                low_k, high_k = keys[i], keys[i + 1]
                low_v, high_v = table[low_k], table[high_k]
                return low_v + (high_v - low_v) * ((percentile_int - low_k) / (high_k - low_k))
        
        return 0
    
    def _is_science_inquiry(self, normalized_scores: Dict) -> bool:
        """과학탐구 응시 여부 판단"""
        inquiry_infer = normalized_scores.get("선택과목", {}).get("탐구_추론", "")
        return "자연계" in inquiry_infer
    
    def calculate_track_score(
        self,
        track_type: str,
        normalized_scores: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """특정 모집단위의 환산 점수 계산"""
        if track_type not in self.TRACK_TYPES:
            return None
        
        config = self.TRACK_TYPES[track_type]
        subjects = normalized_scores.get("과목별_성적", {})
        
        result = {
            "모집단위": config["name"],
            "국어_표준점수": None,
            "수학_표준점수": None,
            "탐구_변환합계": None,
            "영어_감점": 0.0,
            "한국사_감점": 0.0,
            "원점수": None,
            "최종점수": None,
            "계산_가능": False,
            "오류": None
        }
        
        # 1. 국어 표준점수
        kor_data = subjects.get("국어")
        if not kor_data or kor_data.get("표준점수") is None:
            result["오류"] = "국어 표준점수 없음"
            return result
        
        kor_std = kor_data["표준점수"]
        result["국어_표준점수"] = kor_std
        
        # 2. 수학 표준점수
        math_data = subjects.get("수학")
        if not math_data or math_data.get("표준점수") is None:
            result["오류"] = "수학 표준점수 없음"
            return result
        
        math_std = math_data["표준점수"]
        result["수학_표준점수"] = math_std
        
        # 3. 탐구 변환점수
        is_science = self._is_science_inquiry(normalized_scores)
        
        inq1_data = subjects.get("탐구1")
        inq2_data = subjects.get("탐구2")
        
        if not inq1_data or inq1_data.get("백분위") is None:
            result["오류"] = "탐구1 백분위 없음"
            return result
        if not inq2_data or inq2_data.get("백분위") is None:
            result["오류"] = "탐구2 백분위 없음"
            return result
        
        t1_conv = self._get_conv_score(inq1_data["백분위"], is_science)
        t2_conv = self._get_conv_score(inq2_data["백분위"], is_science)
        tam_total = t1_conv + t2_conv
        result["탐구_변환합계"] = round(tam_total, 2)
        
        # 4. 영어 감점 (2등급부터 -3점씩)
        eng_data = subjects.get("영어")
        eng_grade = eng_data.get("등급", 1) if eng_data else 1
        eng_deduction = (eng_grade - 1) * 3 if eng_grade >= 2 else 0
        result["영어_감점"] = -eng_deduction
        
        # 5. 한국사 감점 (5등급부터 -0.2씩)
        hist_data = subjects.get("한국사")
        hist_grade = hist_data.get("등급", 1) if hist_data else 1
        hist_deduction = (hist_grade - 4) * 0.2 if hist_grade >= 5 else 0
        result["한국사_감점"] = -hist_deduction
        
        # 6. 원점수 계산
        tam_weighted = tam_total * config["inq_weight"]
        math_weighted = math_std * config["math_weight"]
        
        raw_score = kor_std + math_weighted + tam_weighted - eng_deduction - hist_deduction
        result["원점수"] = round(raw_score, 2)
        
        # 7. 1000점 환산
        final_1000 = (raw_score / config["base_score"]) * 1000
        result["최종점수"] = round(final_1000, 2)
        result["계산_가능"] = True
        
        return result
    
    def calculate_all_tracks(
        self,
        normalized_scores: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """모든 모집단위의 환산 점수 계산"""
        results = {}
        
        for track_type in self.TRACK_TYPES.keys():
            track_result = self.calculate_track_score(track_type, normalized_scores)
            if track_result:
                results[track_type] = track_result
        
        return results


def calculate_korea_score(normalized_scores: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """정규화된 성적을 고려대 환산 점수로 변환"""
    calculator = KoreaUnivScoreCalculator()
    return calculator.calculate_all_tracks(normalized_scores)


if __name__ == "__main__":
    test_data = {
        "과목별_성적": {
            "국어": {"등급": 1, "표준점수": 140, "백분위": 99},
            "수학": {"등급": 1, "표준점수": 135, "백분위": 99},
            "영어": {"등급": 1, "백분위": 97},
            "한국사": {"등급": 1},
            "탐구1": {"등급": 1, "표준점수": 70, "백분위": 99},
            "탐구2": {"등급": 1, "표준점수": 66, "백분위": 95}
        },
        "선택과목": {"탐구_추론": "자연계"}
    }
    
    print("="*60)
    print("고려대 2026 환산 점수 테스트 (1000점 만점)")
    print("="*60)
    
    results = calculate_korea_score(test_data)
    for track, data in results.items():
        if data["계산_가능"]:
            print(f"{track}: {data['최종점수']:.1f}점 (원점수: {data['원점수']:.1f})")
