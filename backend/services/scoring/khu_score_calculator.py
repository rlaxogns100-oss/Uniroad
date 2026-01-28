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
    
    # 탐구 백분위 -> 변환표준점수 테이블
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
    
    # 2026학년도 영어 등급별 감점 (800점 기준)
    ENG_DEDUCTION_2026 = {
        1: 0, 2: 0, 3: -2, 4: -4, 5: -8, 6: -12, 7: -18, 8: -24, 9: -30
    }
    
    # 2026학년도 한국사 등급별 감점 (800점 기준)
    HIST_DEDUCTION_2026 = {
        1: 0, 2: 0, 3: 0, 4: 0, 5: -2, 6: -4, 7: -8, 8: -14, 9: -20
    }
    
    # 계열별 가중치
    WEIGHTS = {
        "인문": {"kor": 0.40, "math": 0.25, "inq": 0.35, "inq_n": 2},
        "사회": {"kor": 0.35, "math": 0.35, "inq": 0.30, "inq_n": 2},
        "자연": {"kor": 0.25, "math": 0.40, "inq": 0.35, "inq_n": 2},
        "예술체육": {"kor": 0.60, "math": 0.00, "inq": 0.40, "inq_n": 1},
    }
    
    # 과학탐구 과목 목록
    SCIENCE_INQUIRY_SUBJECTS = [
        "물리학1", "물리학2", "화학1", "화학2", 
        "생명과학1", "생명과학2", "지구과학1", "지구과학2"
    ]
    
    def __init__(self):
        pass
    
    def _convert_percentile_to_standard(self, percentile: float) -> float:
        """
        백분위를 경희대 변환표준점수로 변환
        정확한 값이 없으면 선형 보간
        """
        percentile_int = int(round(percentile))
        
        if percentile_int in self.CONVERSION_TABLE:
            return self.CONVERSION_TABLE[percentile_int]
        
        # 범위 밖인 경우
        if percentile_int > 100:
            return self.CONVERSION_TABLE[100]
        if percentile_int < 0:
            return self.CONVERSION_TABLE[0]
        
        # 선형 보간
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
        
        return self.CONVERSION_TABLE.get(50, 50.0)  # 기본값
    
    def _is_science_inquiry(self, normalized_scores: Dict) -> bool:
        """과학탐구 응시 여부 판단"""
        subjects = normalized_scores.get("과목별_성적", {})
        
        # 탐구1, 탐구2가 과학탐구인지 확인
        # 정규화된 성적에서 과목명이 명시되어 있지 않으면 선택과목 추론 정보 사용
        inquiry_infer = normalized_scores.get("선택과목", {}).get("탐구_추론", "")
        
        if "자연계" in inquiry_infer:
            return True
        
        # 과목명이 명시된 경우 (향후 확장)
        for subject_key in subjects.keys():
            if any(sci in subject_key for sci in self.SCIENCE_INQUIRY_SUBJECTS):
                return True
        
        return False
    
    def calculate_track_score(
        self, 
        track: str,
        normalized_scores: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        특정 계열의 환산 점수 계산
        
        Args:
            track: 계열명 (인문/사회/자연/예술체육)
            normalized_scores: 정규화된 성적 정보
            
        Returns:
            {
                "계열": str,
                "국어_표준점수": float,
                "수학_표준점수": float,
                "탐구1_변환표준점수": float,
                "탐구2_변환표준점수": float,
                "과탐_가산점": int,
                "Y_base": float,
                "기본점수_600": float,
                "영어_감점": float,
                "한국사_감점": float,
                "최종점수": float,
                "계산_가능": bool,
                "오류": str or None
            }
        """
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
        
        # 1. 국어 표준점수
        kor_data = subjects.get("국어")
        if not kor_data or kor_data.get("표준점수") is None:
            result["오류"] = "국어 표준점수 없음"
            return result
        
        kor_std = kor_data["표준점수"]
        result["국어_표준점수"] = kor_std
        
        # 2. 수학 표준점수 (예술체육은 수학 미반영)
        math_std = 0
        if w["math"] > 0:
            math_data = subjects.get("수학")
            if not math_data or math_data.get("표준점수") is None:
                result["오류"] = "수학 표준점수 없음"
                return result
            math_std = math_data["표준점수"]
            result["수학_표준점수"] = math_std
        
        # 3. 탐구 변환표준점수
        inq1_data = subjects.get("탐구1")
        if not inq1_data or inq1_data.get("백분위") is None:
            result["오류"] = "탐구1 백분위 없음"
            return result
        
        inq1_percentile = inq1_data["백분위"]
        inq1_converted = self._convert_percentile_to_standard(inq1_percentile)
        result["탐구1_변환표준점수"] = inq1_converted
        
        # 탐구2 (2과목 필요한 계열만)
        inq2_converted = 0
        if w["inq_n"] == 2:
            inq2_data = subjects.get("탐구2")
            if not inq2_data or inq2_data.get("백분위") is None:
                result["오류"] = "탐구2 백분위 없음"
                return result
            
            inq2_percentile = inq2_data["백분위"]
            inq2_converted = self._convert_percentile_to_standard(inq2_percentile)
            result["탐구2_변환표준점수"] = inq2_converted
        
        # 4. 과학탐구 가산점 (자연계만)
        bonus = 0
        if track == "자연" and w["inq_n"] == 2:
            if self._is_science_inquiry(normalized_scores):
                bonus = 4  # 과목당 4점
                inq1_converted += bonus
                inq2_converted += bonus
                result["과탐_가산점"] = bonus * 2  # 총 8점
        
        # 5. Y_base 계산
        inq_sum = inq1_converted + inq2_converted
        Y_base = (kor_std * w["kor"]) + (math_std * w["math"]) + (inq_sum * w["inq"])
        result["Y_base"] = round(Y_base, 3)
        
        # 6. 600점 만점으로 변환
        base_score_800 = Y_base * 4
        base_score_600 = base_score_800 * 0.75
        result["기본점수_600"] = round(base_score_600, 2)
        
        # 7. 영어 감점
        eng_data = subjects.get("영어")
        eng_grade = eng_data.get("등급", 2) if eng_data else 2  # 기본 2등급
        eng_deduction_800 = self.ENG_DEDUCTION_2026.get(eng_grade, 0)
        eng_deduction_600 = eng_deduction_800 * 0.75
        result["영어_감점"] = round(eng_deduction_600, 2)
        
        # 8. 한국사 감점
        hist_data = subjects.get("한국사")
        hist_grade = hist_data.get("등급", 2) if hist_data else 2  # 기본 2등급
        hist_deduction_800 = self.HIST_DEDUCTION_2026.get(hist_grade, 0)
        hist_deduction_600 = hist_deduction_800 * 0.75
        result["한국사_감점"] = round(hist_deduction_600, 2)
        
        # 9. 최종 점수
        final_score = base_score_600 + eng_deduction_600 + hist_deduction_600
        result["최종점수"] = round(final_score, 2)
        result["계산_가능"] = True
        
        return result
    
    def calculate_all_tracks(
        self, 
        normalized_scores: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """
        모든 계열의 환산 점수 계산
        
        Args:
            normalized_scores: ConsultingAgent의 정규화된 성적
            
        Returns:
            {
                "인문": {...},
                "사회": {...},
                "자연": {...},
                "예술체육": {...}
            }
        """
        results = {}
        
        for track in ["인문", "사회", "자연", "예술체육"]:
            track_result = self.calculate_track_score(track, normalized_scores)
            if track_result:
                results[track] = track_result
        
        return results


def calculate_khu_score(normalized_scores: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    정규화된 성적을 경희대 환산 점수로 변환 (전체 계열)
    
    Args:
        normalized_scores: ConsultingAgent._normalize_scores()의 반환값
        
    Returns:
        4개 계열별 환산 점수
    """
    calculator = KhuScoreCalculator()
    return calculator.calculate_all_tracks(normalized_scores)


# 테스트용 메인
if __name__ == "__main__":
    # 테스트 데이터: 국어 140, 수학 128, 영어 2등급, 탐구1 백분위 99, 탐구2 백분위 95
    test_normalized = {
        "과목별_성적": {
            "국어": {
                "등급": 1,
                "표준점수": 140,
                "백분위": 99,
                "선택과목": "언어와매체"
            },
            "수학": {
                "등급": 2,
                "표준점수": 128,
                "백분위": 92,
                "선택과목": "미적분"
            },
            "영어": {
                "등급": 2,
                "표준점수": None,
                "백분위": 96
            },
            "탐구1": {
                "등급": 1,
                "표준점수": 70,
                "백분위": 99
            },
            "탐구2": {
                "등급": 1,
                "표준점수": 66,
                "백분위": 95
            }
        },
        "선택과목": {
            "국어": "언어와매체",
            "수학": "미적분",
            "탐구_추론": "자연계 (지구과학1/생명과학1)"
        }
    }
    
    print("="*60)
    print("경희대 2026 환산 점수 계산 테스트")
    print("="*60)
    
    results = calculate_khu_score(test_normalized)
    
    for track, data in results.items():
        print(f"\n【{track} 계열】")
        if not data["계산_가능"]:
            print(f"  계산 불가: {data['오류']}")
            continue
        
        print(f"  국어 표준점수: {data['국어_표준점수']}")
        if data['수학_표준점수'] is not None:
            print(f"  수학 표준점수: {data['수학_표준점수']}")
        print(f"  탐구1 변환표준점수: {data['탐구1_변환표준점수']}")
        if data['탐구2_변환표준점수'] is not None:
            print(f"  탐구2 변환표준점수: {data['탐구2_변환표준점수']}")
        if data['과탐_가산점'] > 0:
            print(f"  과탐 가산점: +{data['과탐_가산점']}점")
        print(f"  Y_base: {data['Y_base']}")
        print(f"  기본점수 (600점): {data['기본점수_600']}")
        print(f"  영어 감점: {data['영어_감점']}")
        print(f"  한국사 감점: {data['한국사_감점']}")
        print(f"  최종점수: {data['최종점수']} / 600")
