"""
서울대학교 2026학년도 정시 환산 점수 계산기
- 7개 모집단위 타입별 환산
- 1000점 스케일 환산 (수능 비율로 실기/기타 채움)
"""

from typing import Dict, Any, Optional, List


class SnuScoreCalculator:
    """서울대 2026 환산 점수 계산기 (1000점 스케일)"""
    
    SCORE_SCHEME = {
        "일반전형": (1000, 0, 0),
        "순수미술": (700, 300, 0),
        "디자인": (700, 300, 0),
        "체육교육": (700, 300, 0),
        "성악": (700, 300, 0),
        "작곡": (700, 300, 0),
        "음악학": (1000, 0, 0),
    }
    
    TRACK_TYPES = {
        "일반전형": {
            "name": "일반전형 (인문/자연/공학/의약 등)",
            "formula": "국어 + (수학×1.2) + (탐구×0.8) + 과탐가산 - 감점",
            "uses_math_std": True,
            "inquiry_count": 2,
            "apply_science_bonus": True,
            "apply_fl_deduction": True
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
        math_d = 0.0
        eng_d = 0.0
        hist_d = 0.0
        
        if track_type in ["일반전형", "순수미술", "디자인", "체육교육", "음악학"]:
            def std_deduction(grade):
                if grade == 1:
                    return 0
                elif grade == 2:
                    return 0.5
                else:
                    return 2.0 + (grade - 3) * 2.0
            
            if track_type in ["순수미술", "음악학"]:
                math_d = std_deduction(math_grade)
            
            eng_d = std_deduction(eng_grade)
            
            if hist_grade >= 4:
                hist_d = (hist_grade - 3) * 0.4
        
        elif track_type == "성악":
            if math_grade >= 5:
                math_d = (math_grade - 4) * 0.4
            if eng_grade >= 5:
                eng_d = (eng_grade - 4) * 0.5
            if hist_grade >= 5:
                hist_d = (hist_grade - 4) * 0.4
        
        elif track_type == "작곡":
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
        subjects = normalized_scores.get("과목별_성적", {})
        
        inq1_is_science2 = False
        inq2_is_science2 = False
        
        for subject_key in subjects.keys():
            if any(sci in subject_key for sci in self.SCIENCE_II_SUBJECTS):
                if "탐구1" in subject_key:
                    inq1_is_science2 = True
                elif "탐구2" in subject_key:
                    inq2_is_science2 = True
        
        if inq1_is_science2 and inq2_is_science2:
            return 5
        elif inq1_is_science2 or inq2_is_science2:
            return 3
        else:
            return 0
    
    def calculate_track_score(
        self,
        track_type: str,
        normalized_scores: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
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
        
        kor_data = subjects.get("국어")
        if not kor_data or kor_data.get("표준점수") is None:
            result["오류"] = "국어 표준점수 없음"
            return result
        
        kor_std = kor_data["표준점수"]
        result["국어_표준점수"] = kor_std
        
        math_std = 0
        math_grade = 1
        
        if config["uses_math_std"]:
            math_data = subjects.get("수학")
            if not math_data or math_data.get("표준점수") is None:
                result["오류"] = "수학 표준점수 없음"
                return result
            math_std = math_data["표준점수"]
            math_grade = math_data.get("등급", 1)
            result["수학_표준점수"] = math_std
        else:
            math_data = subjects.get("수학")
            if math_data:
                math_grade = math_data.get("등급", 1)
        
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
        
        science_bonus = 0
        if config.get("apply_science_bonus", False):
            science_bonus = self._get_science_bonus(normalized_scores)
            result["과탐_가산점"] = science_bonus
        
        eng_data = subjects.get("영어")
        eng_grade = eng_data.get("등급", 1) if eng_data else 1
        
        hist_data = subjects.get("한국사")
        hist_grade = hist_data.get("등급", 1) if hist_data else 1
        
        deductions = self._calculate_deduction(track_type, math_grade, eng_grade, hist_grade)
        result["수학_감점"] = -deductions["수학"]
        result["영어_감점"] = -deductions["영어"]
        result["한국사_감점"] = -deductions["한국사"]
        
        total_deduction = deductions["수학"] + deductions["영어"] + deductions["한국사"]
        
        raw_score = 0
        
        if track_type == "일반전형" or track_type == "체육교육":
            raw_score = kor_std + (math_std * 1.2) + ((inq1_std + inq2_std) * 0.8) + science_bonus - total_deduction
        
        elif track_type == "디자인":
            raw_score = kor_std + math_std + (inq1_std + inq2_std) + science_bonus - total_deduction
        
        elif track_type == "순수미술":
            raw_score = kor_std + (inq1_std + inq2_std) - total_deduction
        
        elif track_type in ["성악", "작곡", "음악학"]:
            raw_score = kor_std + (inq1_std + inq2_std) - total_deduction
        
        result["raw_score"] = round(raw_score, 2)
        
        if track_type == "성악":
            final_score = (raw_score * (15.3 / 400)) + 35.7
        elif track_type == "작곡":
            final_score = (raw_score * (16.5 / 400)) + 38.5
        elif track_type == "음악학":
            final_score = (raw_score * (15 / 400)) + 35
        else:
            final_score = raw_score
        
        result["최종점수"] = round(final_score, 2)
        
        suneung_max, silgi_max, etc_max = self.SCORE_SCHEME.get(track_type, (1000, 0, 0))
        
        suneung_part = max(0.0, raw_score)
        suneung_part = min(suneung_part, float(suneung_max))
        
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
        results = {}
        
        for track_type in self.TRACK_TYPES.keys():
            track_result = self.calculate_track_score(track_type, normalized_scores)
            if track_result:
                results[track_type] = track_result
        
        return results


def calculate_snu_score(normalized_scores: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """정규화된 성적을 서울대 환산 점수로 변환"""
    calculator = SnuScoreCalculator()
    return calculator.calculate_all_tracks(normalized_scores)
