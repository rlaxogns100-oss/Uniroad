"""
연세대학교 2026학년도 정시 환산 점수 계산기
- 1000점 만점 (수능 100%)
- 7개 모집단위 타입별 환산
- 탐구 변환표준점수표 (사탐/과탐 별도)
- 탐구 가산점 3% (인문: 사탐, 자연/의약: 과탐)
"""

from typing import Dict, Any, Optional


class YonseiScoreCalculator:
    """연세대 2026 환산 점수 계산기 (1000점 만점)"""
    
    # 사회탐구 변환표 (백분위 -> 변환표준점수)
    SOCIAL_TABLE = {
        100: 66.00, 99: 65.80, 98: 65.55, 97: 65.30, 96: 65.05,
        95: 64.80, 94: 64.55, 93: 64.30, 92: 64.05, 91: 63.80,
        90: 63.55, 89: 63.30, 88: 63.05, 87: 62.80, 86: 62.55,
        85: 62.30, 84: 62.05, 83: 61.80, 82: 61.55, 81: 61.30,
        80: 61.05, 79: 60.80, 78: 60.55, 77: 60.30, 76: 60.05,
        75: 59.80, 74: 59.55, 73: 59.30, 72: 59.05, 71: 58.80,
        70: 58.55, 69: 58.30, 68: 58.05, 67: 57.80, 66: 57.55,
        65: 57.30, 64: 57.05, 63: 56.80, 62: 56.55, 61: 56.30,
        60: 56.05
    }
    
    # 과학탐구 변환표 (백분위 -> 변환표준점수)
    SCIENCE_TABLE = {
        100: 68.00, 99: 67.75, 98: 67.50, 97: 67.25, 96: 67.00,
        95: 66.75, 94: 66.50, 93: 66.25, 92: 66.00, 91: 65.75,
        90: 65.50, 89: 65.25, 88: 65.00, 87: 64.75, 86: 64.50,
        85: 64.25, 84: 64.00, 83: 63.75, 82: 63.50, 81: 63.25,
        80: 63.00, 79: 62.75, 78: 62.50, 77: 62.25, 76: 62.00,
        75: 61.75, 74: 61.50, 73: 61.25, 72: 61.00, 71: 60.75,
        70: 60.50, 69: 60.25, 68: 60.00, 67: 59.75, 66: 59.50,
        65: 59.25, 64: 59.00, 63: 58.75, 62: 58.50, 61: 58.25,
        60: 58.00
    }
    
    # 영어 등급별 점수
    ENG_SCORES = {1: 100, 2: 95, 3: 87.5, 4: 75, 5: 60, 6: 40, 7: 25, 8: 12.5, 9: 5}
    
    # 모집단위별 설정
    TRACK_TYPES = {
        "인문": {
            "name": "인문 (문과대/상경대/신학대)",
            "kor_weight": 1.5,
            "math_weight": 1.0,
            "eng_weight": 1.0,
            "inq_weight": 1.0,
            "uses_math": True,
            "denom": 800.0,
            "bonus_type": "사탐"  # 사탐 3% 가산
        },
        "자연": {
            "name": "자연 (이과대/공과대/인공지능 등)",
            "kor_weight": 1.0,
            "math_weight": 1.5,
            "eng_weight": 1.0,
            "inq_weight": 1.5,
            "uses_math": True,
            "denom": 900.0,
            "bonus_type": "과탐"  # 과탐 3% 가산
        },
        "의약": {
            "name": "의약 (의예과/약학과)",
            "kor_weight": 1.0,
            "math_weight": 1.5,
            "eng_weight": 1.0,
            "inq_weight": 1.5,
            "uses_math": True,
            "denom": 900.0,
            "bonus_type": "과탐"
        },
        "통합": {
            "name": "통합 (생활과학대/간호대)",
            "kor_weight": 1.0,
            "math_weight": 1.0,
            "eng_weight": 1.0,
            "inq_weight": 0.5,
            "uses_math": True,
            "denom": 600.0,
            "bonus_type": None
        },
        "국제": {
            "name": "국제계열",
            "kor_weight": 1.0,
            "math_weight": 1.0,
            "eng_weight": 1.0,
            "inq_weight": 0.5,
            "uses_math": True,
            "denom": 600.0,
            "bonus_type": None
        },
        "체능": {
            "name": "체육교육/스포츠응용",
            "kor_weight": 1.0,
            "math_weight": 1.0,
            "eng_weight": 1.0,
            "inq_weight": 0.5,
            "uses_math": True,
            "denom": 600.0,
            "bonus_type": None
        },
        "음악": {
            "name": "음악대학",
            "kor_weight": 2.0,  # 66.7%
            "math_weight": 0.0,
            "eng_weight": 1.0,  # 33.3%
            "inq_weight": 0.0,
            "uses_math": False,
            "denom": 500.0,
            "bonus_type": None
        }
    }
    
    def __init__(self):
        pass
    
    def _get_conv_score(self, percentile: float, is_science: bool) -> float:
        """백분위를 변환표준점수로 변환"""
        table = self.SCIENCE_TABLE if is_science else self.SOCIAL_TABLE
        percentile_int = int(round(percentile))
        
        if percentile_int in table:
            return table[percentile_int]
        
        # 60 미만이면 보정
        if percentile_int < 60:
            return table[60] - ((60 - percentile_int) * 0.25)
        
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
        """
        특정 모집단위의 환산 점수 계산
        
        Args:
            track_type: 모집단위 타입
            normalized_scores: 정규화된 성적 정보
            
        Returns:
            환산 점수 정보
        """
        if track_type not in self.TRACK_TYPES:
            return None
        
        config = self.TRACK_TYPES[track_type]
        subjects = normalized_scores.get("과목별_성적", {})
        
        result = {
            "모집단위": config["name"],
            "국어_표준점수": None,
            "수학_표준점수": None,
            "탐구1_변환점수": None,
            "탐구2_변환점수": None,
            "탐구_합계": None,
            "영어_점수": None,
            "한국사_감점": 0.0,
            "탐구_가산": None,
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
        math_std = 0
        if config["uses_math"]:
            math_data = subjects.get("수학")
            if not math_data or math_data.get("표준점수") is None:
                result["오류"] = "수학 표준점수 없음"
                return result
            math_std = math_data["표준점수"]
            result["수학_표준점수"] = math_std
        
        # 3. 영어 점수
        eng_data = subjects.get("영어")
        eng_grade = eng_data.get("등급", 2) if eng_data else 2
        eng_score = self.ENG_SCORES.get(eng_grade, 0)
        result["영어_점수"] = eng_score
        
        # 4. 한국사 감점
        hist_data = subjects.get("한국사")
        hist_grade = hist_data.get("등급", 1) if hist_data else 1
        hist_deduction = 0.0
        if hist_grade >= 5:
            hist_deduction = (hist_grade - 4) * 0.2
        result["한국사_감점"] = -hist_deduction
        
        # 5. 탐구 변환점수 (음악 제외)
        tam_sum = 0.0
        bonus_desc = None
        
        if config["inq_weight"] > 0:
            is_science = self._is_science_inquiry(normalized_scores)
            
            inq1_data = subjects.get("탐구1")
            if not inq1_data or inq1_data.get("백분위") is None:
                result["오류"] = "탐구1 백분위 없음"
                return result
            
            inq2_data = subjects.get("탐구2")
            if not inq2_data or inq2_data.get("백분위") is None:
                result["오류"] = "탐구2 백분위 없음"
                return result
            
            t1_per = inq1_data["백분위"]
            t2_per = inq2_data["백분위"]
            
            t1_conv = self._get_conv_score(t1_per, is_science)
            t2_conv = self._get_conv_score(t2_per, is_science)
            
            result["탐구1_변환점수"] = round(t1_conv, 2)
            result["탐구2_변환점수"] = round(t2_conv, 2)
            
            # 탐구 가산점 3%
            t1_final = t1_conv
            t2_final = t2_conv
            
            if config["bonus_type"] == "사탐" and not is_science:
                t1_final *= 1.03
                t2_final *= 1.03
                bonus_desc = "사회탐구 3% 적용"
            elif config["bonus_type"] == "과탐" and is_science:
                t1_final *= 1.03
                t2_final *= 1.03
                bonus_desc = "과학탐구 3% 적용"
            
            tam_sum = t1_final + t2_final
            result["탐구_합계"] = round(tam_sum, 2)
            result["탐구_가산"] = bonus_desc
        
        # 6. 최종 점수 계산
        numerator = (kor_std * config["kor_weight"]) + \
                    (math_std * config["math_weight"]) + \
                    (eng_score * config["eng_weight"]) + \
                    (tam_sum * config["inq_weight"])
        
        final_score = (numerator / config["denom"]) * 1000 - hist_deduction
        
        result["최종점수"] = round(final_score, 2)
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


def calculate_yonsei_score(normalized_scores: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """정규화된 성적을 연세대 환산 점수로 변환"""
    calculator = YonseiScoreCalculator()
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
    print("연세대 2026 환산 점수 테스트 (1000점 만점)")
    print("="*60)
    
    results = calculate_yonsei_score(test_data)
    for track, data in results.items():
        if data["계산_가능"]:
            bonus = f" ({data['탐구_가산']})" if data.get('탐구_가산') else ""
            print(f"{track}: {data['최종점수']:.1f}점{bonus}")
