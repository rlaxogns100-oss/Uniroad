"""
Logic Layer: ScoreConverter 클래스
수능 점수 변환 로직을 담당합니다.
"""
from typing import Dict, Optional, Any

from .data.standard import (
    korean_std_score_table,
    math_std_score_table,
    social_studies_data,
    science_inquiry_data,
    major_subjects_grade_cuts
)


class ScoreConverter:
    """수능 점수 변환 클래스"""
    
    def __init__(self):
        self.korean_data = korean_std_score_table
        self.math_data = math_std_score_table
        self.social_data = social_studies_data
        self.science_data = science_inquiry_data
        self.major_grade_cuts = major_subjects_grade_cuts
        
        # 등급별 대표 백분위 (등급만 입력 들어왔을 때 추정용)
        self.grade_median_percentile = {
            1: 98, 2: 92, 3: 83, 4: 68, 5: 50, 6: 31, 7: 17, 8: 7, 9: 2
        }

    def get_score_by_standard(self, subject: str, standard_score: int, elective: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        표준점수로부터 등급과 백분위를 조회합니다.
        """
        # 국어 처리
        if subject == "국어":
            if standard_score in self.korean_data:
                result = self.korean_data[standard_score].copy()
                result["standard_score"] = standard_score
                if "perc" in result:
                    result["percentile"] = result.pop("perc")
                return result
            closest_std = min(self.korean_data.keys(), key=lambda x: abs(x - standard_score))
            result = self.korean_data[closest_std].copy()
            result["standard_score"] = standard_score
            if "perc" in result:
                result["percentile"] = result.pop("perc")
            result["note"] = "보간값"
            return result
        
        # 수학 처리
        elif subject == "수학":
            if standard_score in self.math_data:
                result = self.math_data[standard_score].copy()
                result["standard_score"] = standard_score
                if "perc" in result:
                    result["percentile"] = result.pop("perc")
                return result
            closest_std = min(self.math_data.keys(), key=lambda x: abs(x - standard_score))
            result = self.math_data[closest_std].copy()
            result["standard_score"] = standard_score
            if "perc" in result:
                result["percentile"] = result.pop("perc")
            result["note"] = "보간값"
            return result
        
        # 탐구 과목 처리
        elif subject in self.social_data:
            data_dict = self.social_data[subject]
            best_match = None
            min_diff = float('inf')
            for raw_str, info in data_dict.items():
                diff = abs(info["std"] - standard_score)
                if diff < min_diff:
                    min_diff = diff
                    best_match = {"raw": int(raw_str), **info}
            if best_match:
                best_match["standard_score"] = standard_score
                if "perc" in best_match:
                    best_match["percentile"] = best_match.pop("perc")
                best_match["note"] = "역추적값"
                return best_match
        
        elif subject in self.science_data:
            data_dict = self.science_data[subject]
            best_match = None
            min_diff = float('inf')
            for raw_str, info in data_dict.items():
                diff = abs(info["std"] - standard_score)
                if diff < min_diff:
                    min_diff = diff
                    best_match = {"raw": int(raw_str), **info}
            if best_match:
                best_match["standard_score"] = standard_score
                if "perc" in best_match:
                    best_match["percentile"] = best_match.pop("perc")
                best_match["note"] = "역추적값"
                return best_match
        
        return None

    def get_score_by_raw(self, subject: str, raw_score: int, elective: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        원점수로부터 표준점수, 등급, 백분위를 조회합니다.
        """
        # 탐구 과목 처리
        if subject in self.social_data:
            data_dict = self.social_data[subject]
            raw_str = str(raw_score)
            if raw_str in data_dict:
                result = data_dict[raw_str].copy()
                result["raw"] = raw_score
                if "perc" in result:
                    result["percentile"] = result.pop("perc")
                if "std" in result:
                    result["standard_score"] = result.pop("std")
                return result
            closest_raw = min(data_dict.keys(), key=lambda x: abs(int(x) - raw_score))
            result = data_dict[closest_raw].copy()
            result["raw"] = raw_score
            if "perc" in result:
                result["percentile"] = result.pop("perc")
            if "std" in result:
                result["standard_score"] = result.pop("std")
            result["note"] = "보간값"
            return result
        
        elif subject in self.science_data:
            data_dict = self.science_data[subject]
            raw_str = str(raw_score)
            if raw_str in data_dict:
                result = data_dict[raw_str].copy()
                result["raw"] = raw_score
                if "perc" in result:
                    result["percentile"] = result.pop("perc")
                if "std" in result:
                    result["standard_score"] = result.pop("std")
                return result
            closest_raw = min(data_dict.keys(), key=lambda x: abs(int(x) - raw_score))
            result = data_dict[closest_raw].copy()
            result["raw"] = raw_score
            if "perc" in result:
                result["percentile"] = result.pop("perc")
            if "std" in result:
                result["standard_score"] = result.pop("std")
            result["note"] = "보간값"
            return result
        
        # 국어/수학은 등급컷 데이터로 처리
        if subject == "국어" and elective:
            if elective in self.major_grade_cuts.get("국어", {}):
                grade_cuts = self.major_grade_cuts["국어"][elective]
                for grade, cut_info in grade_cuts.items():
                    if grade == "max":
                        continue
                    if raw_score >= cut_info["raw"]:
                        return {
                            "raw": raw_score,
                            "standard_score": cut_info["std"],
                            "percentile": cut_info["perc"],
                            "grade": grade,
                            "note": "등급컷기반"
                        }
                return {
                    "raw": raw_score,
                    "standard_score": grade_cuts[3]["std"],
                    "percentile": grade_cuts[3]["perc"],
                    "grade": 4,
                    "note": "등급컷기반"
                }
        
        elif subject == "수학" and elective:
            if elective in self.major_grade_cuts.get("수학", {}):
                grade_cuts = self.major_grade_cuts["수학"][elective]
                for grade, cut_info in grade_cuts.items():
                    if grade == "max":
                        continue
                    if raw_score >= cut_info["raw"]:
                        return {
                            "raw": raw_score,
                            "standard_score": cut_info["std"],
                            "percentile": cut_info["perc"],
                            "grade": grade,
                            "note": "등급컷기반"
                        }
                return {
                    "raw": raw_score,
                    "standard_score": grade_cuts[2]["std"],
                    "percentile": grade_cuts[2]["perc"],
                    "grade": 3,
                    "note": "등급컷기반"
                }
        
        return None

    def estimate_score_by_grade(self, subject: str, grade: int, elective: Optional[str] = None) -> Dict[str, Any]:
        """
        등급만 주어졌을 때, 해당 등급의 중간 백분위를 이용하여 표준점수를 역추적/추정합니다.
        """
        target_perc = self.grade_median_percentile.get(grade, 50)
        
        result = self.find_closest_by_percentile(subject, target_perc, elective)
        
        if result:
            result['note'] = "등급기반추정"
            result['grade'] = grade
            return result
            
        default_std = 100 + (5 - grade) * 10
        return {
            "standard_score": default_std,
            "percentile": target_perc,
            "grade": grade,
            "note": "단순추정"
        }

    def find_closest_by_percentile(self, subject: str, percentile: int, elective: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        백분위와 가장 가까운 점수 찾기
        """
        candidates = []
        
        if subject in self.social_data:
            data_dict = self.social_data[subject]
            for raw_str, info in data_dict.items():
                temp = info.copy()
                temp['raw'] = int(raw_str)
                candidates.append(temp)
        
        elif subject in self.science_data:
            data_dict = self.science_data[subject]
            for raw_str, info in data_dict.items():
                temp = info.copy()
                temp['raw'] = int(raw_str)
                candidates.append(temp)
        
        elif subject == "국어":
            for std, info in self.korean_data.items():
                temp = info.copy()
                temp['standard_score'] = std
                candidates.append(temp)
        
        elif subject == "수학":
            for std, info in self.math_data.items():
                temp = info.copy()
                temp['standard_score'] = std
                candidates.append(temp)
                
        if not candidates:
            return None
            
        closest = min(candidates, key=lambda x: abs(x.get('perc', 0) - percentile))
        result = {
            "percentile": closest.get('perc', closest.get('percentile', 0)),
            "grade": closest.get('grade')
        }
        
        if 'standard_score' in closest:
            result['standard_score'] = closest['standard_score']
        elif 'std' in closest:
            result['standard_score'] = closest['std']
        
        if 'raw' in closest:
            result['raw'] = closest['raw']
            
        return result
