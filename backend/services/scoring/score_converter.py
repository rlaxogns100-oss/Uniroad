"""
2026 수능 점수 변환 유틸리티
표준점수 또는 백분위를 입력하면 표준점수, 백분위, 등급을 반환합니다.
"""

from typing import Dict, Optional, Union, Tuple

try:
    # 패키지로 실행할 때
    from .data_standard import (
        korean_std_score_table,
        math_std_score_table,
        social_studies_data,
        science_inquiry_data,
        major_subjects_grade_cuts
    )
except ImportError:
    # 직접 실행할 때
    from data_standard import (
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
        
    def get_score_by_standard(
        self, 
        subject: str, 
        standard_score: int
    ) -> Optional[Dict[str, Union[int, float]]]:
        """
        표준점수로 백분위와 등급 조회
        
        Args:
            subject: 과목명 (예: "국어", "수학", "생활과윤리", "물리학1")
            standard_score: 표준점수
            
        Returns:
            {"standard_score": int, "percentile": int, "grade": int} 또는 None
        """
        if subject == "국어":
            if standard_score in self.korean_data:
                data = self.korean_data[standard_score]
                return {
                    "standard_score": standard_score,
                    "percentile": data["perc"],
                    "grade": data["grade"]
                }
                
        elif subject == "수학":
            if standard_score in self.math_data:
                data = self.math_data[standard_score]
                return {
                    "standard_score": standard_score,
                    "percentile": data["perc"],
                    "grade": data["grade"]
                }
                
        # 탐구 과목 처리
        elif subject in self.social_data or subject in self.science_data:
            data_dict = self.social_data if subject in self.social_data else self.science_data
            subject_data = data_dict[subject]
            
            # 원점수 -> 표준점수 매핑에서 표준점수로 검색
            for raw_score, score_info in subject_data.items():
                if score_info["std"] == standard_score:
                    return {
                        "standard_score": standard_score,
                        "percentile": score_info["perc"],
                        "grade": score_info["grade"],
                        "raw_score": int(raw_score)
                    }
        
        return None
    
    def _linear_interpolate(self, x: float, x1: float, x2: float, y1: float, y2: float) -> float:
        """
        선형 보간
        
        Args:
            x: 보간할 값
            x1, x2: 알려진 x 범위
            y1, y2: 알려진 y 값
            
        Returns:
            보간된 y 값
        """
        if x2 == x1:
            return y1
        return y1 + (y2 - y1) * (x - x1) / (x2 - x1)
    
    def get_score_by_raw(
        self,
        subject: str,
        raw_score: int,
        elective: Optional[str] = None
    ) -> Optional[Dict[str, Union[int, float]]]:
        """
        원점수로 표준점수, 백분위, 등급 조회 (국어/수학 선택과목용)
        등급컷 사이의 점수는 선형 보간으로 추정
        
        Args:
            subject: 과목명 ("국어" 또는 "수학")
            raw_score: 원점수 (0~100)
            elective: 선택과목 (국어: "화법과작문"/"언어와매체", 수학: "확률과통계"/"미적분"/"기하")
            
        Returns:
            {"standard_score": int, "percentile": int, "grade": int} 또는 None
        """
        if subject not in self.major_grade_cuts:
            return None
        
        if elective is None:
            return None
        
        if elective not in self.major_grade_cuts[subject]:
            return None
        
        grade_data = self.major_grade_cuts[subject][elective]
        
        # 만점 데이터
        max_data = grade_data["max"]
        
        # 등급컷 리스트 만들기 (원점수 내림차순)
        grade_points = [{
            "grade": 1,
            "raw": max_data["raw"],
            "std": max_data["std"],
            "perc": max_data["perc"]
        }]
        
        # 등급 순서대로 추가 (1등급 -> 2등급 -> ...)
        for grade_num in sorted([k for k in grade_data.keys() if k != "max"]):
            grade_points.append({
                "grade": grade_num,
                "raw": grade_data[grade_num]["raw"],
                "std": grade_data[grade_num]["std"],
                "perc": grade_data[grade_num]["perc"]
            })
        
        # 원점수가 범위를 벗어나는 경우
        if raw_score > max_data["raw"]:
            return {
                "standard_score": max_data["std"],
                "percentile": max_data["perc"],
                "grade": 1
            }
        
        if raw_score < grade_points[-1]["raw"]:
            # 최하위 등급컷보다 낮은 경우 - 최하위 등급 반환
            last_point = grade_points[-1]
            return {
                "standard_score": last_point["std"],
                "percentile": last_point["perc"],
                "grade": min(last_point["grade"] + 1, 9)
            }
        
        # 정확히 등급컷에 해당하는 경우
        for point in grade_points:
            if raw_score == point["raw"]:
                return {
                    "standard_score": point["std"],
                    "percentile": point["perc"],
                    "grade": point["grade"]
                }
        
        # 두 등급컷 사이에 있는 경우 - 선형 보간
        for i in range(len(grade_points) - 1):
            upper = grade_points[i]
            lower = grade_points[i + 1]
            
            if lower["raw"] <= raw_score <= upper["raw"]:
                # 선형 보간
                std_score = self._linear_interpolate(
                    raw_score, 
                    lower["raw"], upper["raw"],
                    lower["std"], upper["std"]
                )
                percentile = self._linear_interpolate(
                    raw_score,
                    lower["raw"], upper["raw"],
                    lower["perc"], upper["perc"]
                )
                
                # 등급 결정: 원점수가 upper(더 높은 등급컷)보다 낮으므로 lower의 등급
                # 예: 87점이 90점(1등급컷)과 83점(2등급컷) 사이에 있으면 2등급
                grade = lower["grade"]
                
                return {
                    "standard_score": round(std_score),
                    "percentile": round(percentile),
                    "grade": grade
                }
        
        return None
    
    def get_score_by_percentile(
        self, 
        subject: str, 
        percentile: int
    ) -> Optional[Dict[str, Union[int, float]]]:
        """
        백분위로 표준점수와 등급 조회
        
        Args:
            subject: 과목명
            percentile: 백분위
            
        Returns:
            {"standard_score": int, "percentile": int, "grade": int} 또는 None
        """
        if subject == "국어":
            for std_score, data in self.korean_data.items():
                if data["perc"] == percentile:
                    return {
                        "standard_score": std_score,
                        "percentile": percentile,
                        "grade": data["grade"]
                    }
                    
        elif subject == "수학":
            for std_score, data in self.math_data.items():
                if data["perc"] == percentile:
                    return {
                        "standard_score": std_score,
                        "percentile": percentile,
                        "grade": data["grade"]
                    }
                    
        # 탐구 과목 처리
        elif subject in self.social_data or subject in self.science_data:
            data_dict = self.social_data if subject in self.social_data else self.science_data
            subject_data = data_dict[subject]
            
            for raw_score, score_info in subject_data.items():
                if score_info["perc"] == percentile:
                    return {
                        "standard_score": score_info["std"],
                        "percentile": percentile,
                        "grade": score_info["grade"],
                        "raw_score": int(raw_score)
                    }
        
        return None
    
    def find_closest_by_standard(
        self, 
        subject: str, 
        standard_score: int
    ) -> Optional[Dict[str, Union[int, float]]]:
        """
        정확한 표준점수가 없을 때 가장 가까운 값 찾기
        
        Args:
            subject: 과목명
            standard_score: 표준점수
            
        Returns:
            가장 가까운 점수 정보
        """
        if subject == "국어":
            data_dict = self.korean_data
        elif subject == "수학":
            data_dict = self.math_data
        elif subject in self.social_data:
            # 탐구 과목은 std 값으로 검색
            subject_data = self.social_data[subject]
            closest_diff = float('inf')
            closest_result = None
            
            for raw_score, score_info in subject_data.items():
                diff = abs(score_info["std"] - standard_score)
                if diff < closest_diff:
                    closest_diff = diff
                    closest_result = {
                        "standard_score": score_info["std"],
                        "percentile": score_info["perc"],
                        "grade": score_info["grade"],
                        "raw_score": int(raw_score)
                    }
            return closest_result
            
        elif subject in self.science_data:
            subject_data = self.science_data[subject]
            closest_diff = float('inf')
            closest_result = None
            
            for raw_score, score_info in subject_data.items():
                diff = abs(score_info["std"] - standard_score)
                if diff < closest_diff:
                    closest_diff = diff
                    closest_result = {
                        "standard_score": score_info["std"],
                        "percentile": score_info["perc"],
                        "grade": score_info["grade"],
                        "raw_score": int(raw_score)
                    }
            return closest_result
        else:
            return None
        
        # 국어/수학 처리
        if not data_dict:
            return None
            
        closest_std = min(data_dict.keys(), key=lambda x: abs(x - standard_score))
        data = data_dict[closest_std]
        return {
            "standard_score": closest_std,
            "percentile": data["perc"],
            "grade": data["grade"]
        }
    
    def find_closest_by_percentile(
        self, 
        subject: str, 
        percentile: int
    ) -> Optional[Dict[str, Union[int, float]]]:
        """
        정확한 백분위가 없을 때 가장 가까운 값 찾기
        
        Args:
            subject: 과목명
            percentile: 백분위
            
        Returns:
            가장 가까운 점수 정보
        """
        if subject == "국어":
            data_dict = self.korean_data
        elif subject == "수학":
            data_dict = self.math_data
        elif subject in self.social_data:
            subject_data = self.social_data[subject]
            closest_diff = float('inf')
            closest_result = None
            
            for raw_score, score_info in subject_data.items():
                diff = abs(score_info["perc"] - percentile)
                if diff < closest_diff:
                    closest_diff = diff
                    closest_result = {
                        "standard_score": score_info["std"],
                        "percentile": score_info["perc"],
                        "grade": score_info["grade"],
                        "raw_score": int(raw_score)
                    }
            return closest_result
            
        elif subject in self.science_data:
            subject_data = self.science_data[subject]
            closest_diff = float('inf')
            closest_result = None
            
            for raw_score, score_info in subject_data.items():
                diff = abs(score_info["perc"] - percentile)
                if diff < closest_diff:
                    closest_diff = diff
                    closest_result = {
                        "standard_score": score_info["std"],
                        "percentile": score_info["perc"],
                        "grade": score_info["grade"],
                        "raw_score": int(raw_score)
                    }
            return closest_result
        else:
            return None
        
        # 국어/수학 처리
        if not data_dict:
            return None
            
        closest_std = min(
            data_dict.keys(), 
            key=lambda x: abs(data_dict[x]["perc"] - percentile)
        )
        data = data_dict[closest_std]
        return {
            "standard_score": closest_std,
            "percentile": data["perc"],
            "grade": data["grade"]
        }
    
    def convert_score(
        self, 
        subject: str, 
        standard_score: Optional[int] = None,
        percentile: Optional[int] = None,
        raw_score: Optional[int] = None,
        elective: Optional[str] = None,
        use_closest: bool = True
    ) -> Optional[Dict[str, Union[int, float]]]:
        """
        표준점수, 백분위 또는 원점수를 입력받아 모든 정보 반환
        
        Args:
            subject: 과목명
            standard_score: 표준점수 (선택)
            percentile: 백분위 (선택)
            raw_score: 원점수 (선택, 국어/수학만 지원)
            elective: 선택과목 (raw_score 사용 시 필수)
            use_closest: 정확한 값이 없을 때 가장 가까운 값 사용 여부
            
        Returns:
            {"standard_score": int, "percentile": int, "grade": int}
            
        Raises:
            ValueError: 입력값이 잘못된 경우
        """
        # 입력값 검증
        input_count = sum([
            standard_score is not None,
            percentile is not None,
            raw_score is not None
        ])
        
        if input_count == 0:
            raise ValueError("표준점수, 백분위, 원점수 중 하나를 입력해주세요.")
        
        if input_count > 1:
            raise ValueError("표준점수, 백분위, 원점수 중 하나만 입력해주세요.")
        
        # 원점수로 조회
        if raw_score is not None:
            if elective is None:
                raise ValueError("원점수 조회 시 선택과목(elective)을 반드시 입력해주세요.")
            return self.get_score_by_raw(subject, raw_score, elective)
        
        # 표준점수로 조회
        if standard_score is not None:
            result = self.get_score_by_standard(subject, standard_score)
            if result is None and use_closest:
                result = self.find_closest_by_standard(subject, standard_score)
            return result
        
        # 백분위로 조회
        result = self.get_score_by_percentile(subject, percentile)
        if result is None and use_closest:
            result = self.find_closest_by_percentile(subject, percentile)
        return result
    
    def get_available_subjects(self) -> Dict[str, list]:
        """
        사용 가능한 과목 목록 반환
        
        Returns:
            과목 분류별 목록
        """
        return {
            "국수영": ["국어", "수학"],
            "사회탐구": list(self.social_data.keys()),
            "과학탐구": list(self.science_data.keys())
        }


# 사용 예시
if __name__ == "__main__":
    converter = ScoreConverter()
    
    print("=== 사용 가능한 과목 ===")
    subjects = converter.get_available_subjects()
    for category, subject_list in subjects.items():
        print(f"\n{category}:")
        print(", ".join(subject_list))
    
    print("\n" + "="*50)
    print("=== 국어 표준점수 140으로 조회 ===")
    result = converter.convert_score("국어", standard_score=140)
    if result:
        print(f"표준점수: {result['standard_score']}")
        print(f"백분위: {result['percentile']}")
        print(f"등급: {result['grade']}")
    
    print("\n" + "="*50)
    print("=== 수학 백분위 95로 조회 ===")
    result = converter.convert_score("수학", percentile=95)
    if result:
        print(f"표준점수: {result['standard_score']}")
        print(f"백분위: {result['percentile']}")
        print(f"등급: {result['grade']}")
    
    print("\n" + "="*50)
    print("=== 생명과학1 표준점수 70으로 조회 ===")
    result = converter.convert_score("생명과학1", standard_score=70)
    if result:
        print(f"원점수: {result.get('raw_score', 'N/A')}")
        print(f"표준점수: {result['standard_score']}")
        print(f"백분위: {result['percentile']}")
        print(f"등급: {result['grade']}")
    
    print("\n" + "="*50)
    print("=== 사회문화 백분위 90으로 조회 ===")
    result = converter.convert_score("사회문화", percentile=90)
    if result:
        print(f"원점수: {result.get('raw_score', 'N/A')}")
        print(f"표준점수: {result['standard_score']}")
        print(f"백분위: {result['percentile']}")
        print(f"등급: {result['grade']}")
    
    print("\n" + "="*50)
    print("=== 국어 언어와매체 원점수 92로 조회 (선형 보간) ===")
    result = converter.convert_score("국어", raw_score=92, elective="언어와매체")
    if result:
        print(f"표준점수: {result['standard_score']}")
        print(f"백분위: {result['percentile']}")
        print(f"등급: {result['grade']}")
    
    print("\n" + "="*50)
    print("=== 수학 미적분 원점수 77로 조회 (선형 보간) ===")
    result = converter.convert_score("수학", raw_score=77, elective="미적분")
    if result:
        print(f"표준점수: {result['standard_score']}")
        print(f"백분위: {result['percentile']}")
        print(f"등급: {result['grade']}")
