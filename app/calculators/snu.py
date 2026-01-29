"""
서울대학교 2026학년도 정시 환산 점수 계산기
- 7개 모집단위 타입별 환산
- 1000점 스케일 환산 (수능 비율로 실기/기타 채움)
- 모집단위별 상이한 감점제
- 과학탐구 가산점 (I+II: 3점, II+II: 5점)
- 음악대학 특수 환산 공식
"""

from typing import Dict, Any, Optional, List


class SnuScoreCalculator:
    """서울대 2026 환산 점수 계산기 (1000점 스케일)"""
    
    # 모집단위별 점수 배분 (수능_max, 실기_max, 기타_max) -> 합계 1000
    SCORE_SCHEME = {
        "일반전형": (1000, 0, 0),    # 수능만
        "순수미술": (700, 300, 0),   # 수능 700 + 실기 300
        "디자인": (700, 300, 0),
        "체육교육": (700, 300, 0),
        "성악": (700, 300, 0),
        "작곡": (700, 300, 0),
        "음악학": (1000, 0, 0),      # 수능만
    }
    
    # 모집단위 타입
    TRACK_TYPES = {
        "일반전형": {
            "name": "일반전형 (인문/자연/공학/의약 등)",
            "formula": "국어 + (수학×1.2) + (탐구×0.8) + 과탐가산 - 감점",
            "uses_math_std": True,
            "inquiry_count": 2,
            "apply_science_bonus": True,
            "apply_fl_deduction": True  # 제2외국어 감점
        },
        "순수미술": {
            "name": "미술대학 - 순수미술 (동양화/서양화/조소/공예)",
            "formula": "국어 + 탐구 - 감점(수/영/한)",
            "uses_math_std": False,
            "inquiry_count": 2,
            "apply_science_bonus": False,
            "apply_fl_deduction": False
        },
        "디자인": {
            "name": "미술대학 - 디자인과",
            "formula": "국어 + 수학 + 탐구 + 과탐가산 - 감점",
            "uses_math_std": True,
            "inquiry_count": 2,
            "apply_science_bonus": True,
            "apply_fl_deduction": False
        },
        "체육교육": {
            "name": "사범대학 체육교육과",
            "formula": "국어 + (수학×1.2) + (탐구×0.8) + 과탐가산 - 감점",
            "uses_math_std": True,
            "inquiry_count": 2,
            "apply_science_bonus": True,
            "apply_fl_deduction": False
        },
        "성악": {
            "name": "음악대학 - 성악과",
            "formula": "{ (국+탐-감점) × 15.3/400 } + 35.7",
            "uses_math_std": False,
            "inquiry_count": 2,
            "apply_science_bonus": False,
            "apply_fl_deduction": False,
            "special_conversion": True
        },
        "작곡": {
            "name": "음악대학 - 작곡과",
            "formula": "{ (국+탐-감점) × 16.5/400 } + 38.5",
            "uses_math_std": False,
            "inquiry_count": 2,
            "apply_science_bonus": False,
            "apply_fl_deduction": False,
            "special_conversion": True
        },
        "음악학": {
            "name": "음악대학 - 음악학과",
            "formula": "{ (국+탐-감점) × 15/400 } + 35",
            "uses_math_std": False,
            "inquiry_count": 2,
            "apply_science_bonus": False,
            "apply_fl_deduction": False,
            "special_conversion": True
        }
    }
    
    # 과학탐구 II 과목 목록
    SCIENCE_II_SUBJECTS = ["물리학2", "화학2", "생명과학2", "지구과학2"]
    
    def __init__(self):
        pass
    
    def _calculate_deduction(
        self, 
        track_type: str, 
        math_grade: int, 
        eng_grade: int, 
        hist_grade: int
    ) -> Dict[str, float]:
        """
        모집단위별 감점 계산
        
        Returns:
            {"수학": float, "영어": float, "한국사": float}
        """
        math_d = 0.0
        eng_d = 0.0
        hist_d = 0.0
        
        # 1. 일반/순수미술/디자인/체육/음악학 그룹 (표준 감점)
        if track_type in ["일반전형", "순수미술", "디자인", "체육교육", "음악학"]:
            # 영어/수학 표준 감점: 1등급(0), 2등급(-0.5), 3등급(-2.0), 4등급 이상(-2.0 + (등급-3)×2.0)
            def std_deduction(grade):
                if grade == 1:
                    return 0
                elif grade == 2:
                    return 0.5
                else:
                    return 2.0 + (grade - 3) * 2.0
            
            # 수학 감점 (순수미술/성악/작곡/음악학은 등급제)
            if track_type in ["순수미술", "음악학"]:
                math_d = std_deduction(math_grade)
            
            # 영어 감점
            eng_d = std_deduction(eng_grade)
            
            # 한국사 감점: 4등급부터 -0.4씩
            if hist_grade >= 4:
                hist_d = (hist_grade - 3) * 0.4
        
        # 2. 성악과 (감점이 매우 후함)
        elif track_type == "성악":
            # 수학: 1~4등급 0점, 5등급부터 -0.4씩
            if math_grade >= 5:
                math_d = (math_grade - 4) * 0.4
            # 영어: 1~4등급 0점, 5등급부터 -0.5씩
            if eng_grade >= 5:
                eng_d = (eng_grade - 4) * 0.5
            # 한국사: 1~4등급 0점, 5등급부터 -0.4씩
            if hist_grade >= 5:
                hist_d = (hist_grade - 4) * 0.4
        
        # 3. 작곡과 (감점이 촘촘함 - 선형)
        elif track_type == "작곡":
            # 수/영/한 모두 2등급부터 -0.5, -1.0, -1.5 (등급당 0.5씩)
            if math_grade >= 2:
                math_d = (math_grade - 1) * 0.5
            if eng_grade >= 2:
                eng_d = (eng_grade - 1) * 0.5
            if hist_grade >= 2:
                hist_d = (hist_grade - 1) * 0.5
        
        return {
            "수학": round(math_d, 2),
            "영어": round(eng_d, 2),
            "한국사": round(hist_d, 2)
        }
    
    def _get_science_bonus(self, normalized_scores: Dict) -> int:
        """
        과학탐구 가산점 계산
        - I+I: 0점
        - I+II: 3점
        - II+II: 5점
        """
        subjects = normalized_scores.get("과목별_성적", {})
        
        # 탐구1, 탐구2가 과학탐구인지 확인
        inq1_is_science2 = False
        inq2_is_science2 = False
        
        # 탐구 과목명이 명시된 경우 (향후 확장용)
        for subject_key in subjects.keys():
            if any(sci in subject_key for sci in self.SCIENCE_II_SUBJECTS):
                if "탐구1" in subject_key:
                    inq1_is_science2 = True
                elif "탐구2" in subject_key:
                    inq2_is_science2 = True
        
        # 가산점 계산
        if inq1_is_science2 and inq2_is_science2:
            return 5  # II+II
        elif inq1_is_science2 or inq2_is_science2:
            return 3  # I+II
        else:
            return 0  # I+I
    
    def calculate_track_score(
        self,
        track_type: str,
        normalized_scores: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        특정 모집단위의 환산 점수 계산
        
        Args:
            track_type: 모집단위 타입 (일반전형/순수미술/디자인/체육교육/성악/작곡/음악학)
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
            "환산공식": config["formula"],
            "국어_표준점수": None,
            "수학_표준점수": None,
            "탐구1_표준점수": None,
            "탐구2_표준점수": None,
            "과탐_가산점": 0,
            "수학_감점": 0.0,
            "영어_감점": 0.0,
            "한국사_감점": 0.0,
            "제2외국어_감점": 0.0,
            "raw_score": None,
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
        
        # 2. 수학 표준점수 (일반/디자인/체육만)
        math_std = 0
        math_grade = 1  # 기본값
        
        if config["uses_math_std"]:
            math_data = subjects.get("수학")
            if not math_data or math_data.get("표준점수") is None:
                result["오류"] = "수학 표준점수 없음"
                return result
            math_std = math_data["표준점수"]
            math_grade = math_data.get("등급", 1)
            result["수학_표준점수"] = math_std
        else:
            # 수학 등급만 필요 (감점용)
            math_data = subjects.get("수학")
            if math_data:
                math_grade = math_data.get("등급", 1)
        
        # 3. 탐구 표준점수
        inq1_data = subjects.get("탐구1")
        if not inq1_data or inq1_data.get("표준점수") is None:
            result["오류"] = "탐구1 표준점수 없음"
            return result
        
        inq1_std = inq1_data["표준점수"]
        result["탐구1_표준점수"] = inq1_std
        
        inq2_data = subjects.get("탐구2")
        if not inq2_data or inq2_data.get("표준점수") is None:
            result["오류"] = "탐구2 표준점수 없음"
            return result
        
        inq2_std = inq2_data["표준점수"]
        result["탐구2_표준점수"] = inq2_std
        
        # 4. 과학탐구 가산점 (일반/디자인/체육만)
        science_bonus = 0
        if config.get("apply_science_bonus", False):
            science_bonus = self._get_science_bonus(normalized_scores)
            result["과탐_가산점"] = science_bonus
        
        # 5. 감점 계산
        eng_data = subjects.get("영어")
        eng_grade = eng_data.get("등급", 1) if eng_data else 1
        
        hist_data = subjects.get("한국사")
        hist_grade = hist_data.get("등급", 1) if hist_data else 1
        
        deductions = self._calculate_deduction(track_type, math_grade, eng_grade, hist_grade)
        result["수학_감점"] = -deductions["수학"]
        result["영어_감점"] = -deductions["영어"]
        result["한국사_감점"] = -deductions["한국사"]
        
        total_deduction = deductions["수학"] + deductions["영어"] + deductions["한국사"]
        
        # 6. 제2외국어 감점 (일반전형만, 현재는 미구현 - 추후 확장)
        # if config.get("apply_fl_deduction", False):
        #     fl_data = subjects.get("제2외국어")
        #     if fl_data:
        #         fl_grade = fl_data.get("등급", 1)
        #         if fl_grade >= 3:
        #             fl_deduction = (fl_grade - 2) * 0.5
        #             result["제2외국어_감점"] = -fl_deduction
        #             total_deduction += fl_deduction
        
        # 7. Raw Score 계산
        raw_score = 0
        
        if track_type == "일반전형" or track_type == "체육교육":
            # 국어 + (수학×1.2) + (탐구×0.8) + 과탐가산 - 감점
            raw_score = kor_std + (math_std * 1.2) + ((inq1_std + inq2_std) * 0.8) + science_bonus - total_deduction
        
        elif track_type == "디자인":
            # 국어 + 수학 + 탐구 + 과탐가산 - 감점
            raw_score = kor_std + math_std + (inq1_std + inq2_std) + science_bonus - total_deduction
        
        elif track_type == "순수미술":
            # 국어 + 탐구 - 감점
            raw_score = kor_std + (inq1_std + inq2_std) - total_deduction
        
        elif track_type in ["성악", "작곡", "음악학"]:
            # 국어 + 탐구 - 감점
            raw_score = kor_std + (inq1_std + inq2_std) - total_deduction
        
        result["raw_score"] = round(raw_score, 2)
        
        # 8. 최종 점수 계산 (음악대학은 특수 환산)
        if track_type == "성악":
            # {성적 * (15.3/400)} + 35.7
            final_score = (raw_score * (15.3 / 400)) + 35.7
        elif track_type == "작곡":
            # {성적 * (16.5/400)} + 38.5
            final_score = (raw_score * (16.5 / 400)) + 38.5
        elif track_type == "음악학":
            # {성적 * (15/400)} + 35
            final_score = (raw_score * (15 / 400)) + 35
        else:
            # 일반/미대/체육은 raw_score 그대로
            final_score = raw_score
        
        result["최종점수"] = round(final_score, 2)
        
        # 9. 1000점 스케일 환산
        suneung_max, silgi_max, etc_max = self.SCORE_SCHEME.get(track_type, (1000, 0, 0))
        
        # 수능 파트 점수 (0 이상으로 클램프)
        suneung_part = max(0.0, raw_score)
        suneung_part = min(suneung_part, float(suneung_max))
        
        # 수능 달성 비율로 실기/기타 파트 채움
        ratio = suneung_part / float(suneung_max) if suneung_max > 0 else 0
        silgi_part = ratio * float(silgi_max)
        etc_part = ratio * float(etc_max)
        
        final_1000 = suneung_part + silgi_part + etc_part
        result["최종점수_1000"] = round(final_1000, 2)
        result["수능비율"] = round(ratio * 100, 1)
        
        result["계산_가능"] = True
        
        return result
    
    def calculate_all_tracks(
        self,
        normalized_scores: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """
        모든 모집단위의 환산 점수 계산
        
        Args:
            normalized_scores: ConsultingAgent의 정규화된 성적
            
        Returns:
            모집단위별 환산 점수
        """
        results = {}
        
        for track_type in self.TRACK_TYPES.keys():
            track_result = self.calculate_track_score(track_type, normalized_scores)
            if track_result:
                results[track_type] = track_result
        
        return results


def calculate_snu_score(normalized_scores: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    정규화된 성적을 서울대 환산 점수로 변환 (전체 모집단위)
    
    Args:
        normalized_scores: ConsultingAgent._normalize_scores()의 반환값
        
    Returns:
        7개 모집단위별 환산 점수
    """
    calculator = SnuScoreCalculator()
    return calculator.calculate_all_tracks(normalized_scores)


# 테스트용 메인
if __name__ == "__main__":
    # 테스트 데이터: 최상위권 학생
    test_normalized = {
        "과목별_성적": {
            "국어": {
                "등급": 1,
                "표준점수": 140,
                "백분위": 99,
                "선택과목": "언어와매체"
            },
            "수학": {
                "등급": 1,
                "표준점수": 135,
                "백분위": 99,
                "선택과목": "미적분"
            },
            "영어": {
                "등급": 1,
                "표준점수": None,
                "백분위": 97
            },
            "한국사": {
                "등급": 1
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
            "탐구_추론": "자연계 (물리학2/화학1)"
        }
    }
    
    print("="*80)
    print("서울대 2026 환산 점수 계산 테스트")
    print("="*80)
    
    results = calculate_snu_score(test_normalized)
    
    for track, data in results.items():
        print(f"\n【{data['모집단위']}】")
        if not data["계산_가능"]:
            print(f"  계산 불가: {data['오류']}")
            continue
        
        print(f"  환산공식: {data['환산공식']}")
        print(f"  국어 표준점수: {data['국어_표준점수']}")
        if data['수학_표준점수'] is not None:
            print(f"  수학 표준점수: {data['수학_표준점수']}")
        print(f"  탐구1 표준점수: {data['탐구1_표준점수']}")
        print(f"  탐구2 표준점수: {data['탐구2_표준점수']}")
        if data['과탐_가산점'] > 0:
            print(f"  과탐 가산점: +{data['과탐_가산점']}점")
        
        total_ded = data['수학_감점'] + data['영어_감점'] + data['한국사_감점']
        if total_ded < 0:
            print(f"  총 감점: {total_ded:.1f}점")
        
        if track in ["성악", "작곡", "음악학"]:
            print(f"  Raw Score: {data['raw_score']:.2f}점")
            print(f"  최종점수 (환산): {data['최종점수']:.2f}점")
        else:
            print(f"  최종점수: {data['최종점수']:.2f}점")
