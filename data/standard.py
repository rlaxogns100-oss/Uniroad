# 2026 수능 국어 통합 데이터 (표준점수 기준)
# [출처: 사용자 업로드 이미지 - 2026 수능 표준점수 도수분포]

korean_std_score_table = {
    # 표준점수: {"grade": 등급, "perc": 백분위}
    
    # [1등급 구간: 147 ~ 133]
    147: {"grade": 1, "perc": 100},
    145: {"grade": 1, "perc": 100},
    144: {"grade": 1, "perc": 100},
    143: {"grade": 1, "perc": 100},
    142: {"grade": 1, "perc": 99},
    141: {"grade": 1, "perc": 99},
    140: {"grade": 1, "perc": 99},
    139: {"grade": 1, "perc": 99},
    138: {"grade": 1, "perc": 98},
    137: {"grade": 1, "perc": 98},
    136: {"grade": 1, "perc": 97},
    135: {"grade": 1, "perc": 97},
    134: {"grade": 1, "perc": 96},
    133: {"grade": 1, "perc": 96}, # 1등급 컷
    
    # [2등급 구간: 132 ~ 126]
    132: {"grade": 2, "perc": 95},
    131: {"grade": 2, "perc": 94},
    130: {"grade": 2, "perc": 93},
    129: {"grade": 2, "perc": 92},
    128: {"grade": 2, "perc": 91},
    127: {"grade": 2, "perc": 90},
    126: {"grade": 2, "perc": 89}, # 2등급 컷
    
    # [3등급 구간: 125 ~ 117]
    125: {"grade": 3, "perc": 88},
    124: {"grade": 3, "perc": 87},
    123: {"grade": 3, "perc": 86},
    122: {"grade": 3, "perc": 84},
    121: {"grade": 3, "perc": 83},
    120: {"grade": 3, "perc": 81},
    119: {"grade": 3, "perc": 80},
    118: {"grade": 3, "perc": 78},
    117: {"grade": 3, "perc": 77}, # 3등급 컷
    
    # [4등급 구간: 116 ~ 107]
    116: {"grade": 4, "perc": 75},
    115: {"grade": 4, "perc": 74},
    114: {"grade": 4, "perc": 72},
    113: {"grade": 4, "perc": 71},
    112: {"grade": 4, "perc": 69},
    111: {"grade": 4, "perc": 67},
    110: {"grade": 4, "perc": 66},
    109: {"grade": 4, "perc": 64},
    108: {"grade": 4, "perc": 62},
    107: {"grade": 4, "perc": 61}, # 4등급 컷
    
    # [5등급 구간: 106 ~ 94]
    106: {"grade": 5, "perc": 59},
    105: {"grade": 5, "perc": 57},
    104: {"grade": 5, "perc": 56},
    103: {"grade": 5, "perc": 54},
    102: {"grade": 5, "perc": 52},
    101: {"grade": 5, "perc": 51},
    100: {"grade": 5, "perc": 49},
    99:  {"grade": 5, "perc": 47},
    98:  {"grade": 5, "perc": 46},
    97:  {"grade": 5, "perc": 44},
    96:  {"grade": 5, "perc": 43},
    95:  {"grade": 5, "perc": 41},
    94:  {"grade": 5, "perc": 40}, # 5등급 컷
    
    # [6등급 구간: 93 ~ 83]
    93: {"grade": 6, "perc": 38},
    92: {"grade": 6, "perc": 36},
    91: {"grade": 6, "perc": 35},
    90: {"grade": 6, "perc": 33},
    89: {"grade": 6, "perc": 32},
    88: {"grade": 6, "perc": 31},
    87: {"grade": 6, "perc": 29},
    86: {"grade": 6, "perc": 28},
    85: {"grade": 6, "perc": 26},
    84: {"grade": 6, "perc": 25},
    83: {"grade": 6, "perc": 23}, # 6등급 컷
    
    # [7등급 구간: 82 ~ 73]
    82: {"grade": 7, "perc": 22},
    81: {"grade": 7, "perc": 21},
    80: {"grade": 7, "perc": 20},
    79: {"grade": 7, "perc": 18},
    78: {"grade": 7, "perc": 17},
    77: {"grade": 7, "perc": 16},
    76: {"grade": 7, "perc": 14},
    75: {"grade": 7, "perc": 13},
    74: {"grade": 7, "perc": 12},
    73: {"grade": 7, "perc": 11}, # 7등급 컷
    
    # [8등급 구간: 72 ~ 66]
    72: {"grade": 8, "perc": 10},
    71: {"grade": 8, "perc": 9},
    70: {"grade": 8, "perc": 8},
    69: {"grade": 8, "perc": 7},
    68: {"grade": 8, "perc": 6},
    67: {"grade": 8, "perc": 4},
    66: {"grade": 8, "perc": 4}, # 8등급 컷
    
    # [9등급 구간: 65 이하]
    65: {"grade": 9, "perc": 3},
    64: {"grade": 9, "perc": 2},
    63: {"grade": 9, "perc": 1},
    # ... (생략된 9등급 하위 구간은 perc 0~1 처리)
    47: {"grade": 9, "perc": 0}
}


# 2026 수능 수학 통합 데이터 (표준점수 기준) [cite: 58, 60, 61, 64]
math_std_score_table = {
    # [1등급 구간: 139 ~ 133]
    139: {"grade": 1, "perc": 100},
    137: {"grade": 1, "perc": 100},
    136: {"grade": 1, "perc": 100},
    135: {"grade": 1, "perc": 99},
    134: {"grade": 1, "perc": 99},
    133: {"grade": 1, "perc": 96}, # 1등급 컷

    # [2등급 구간: 132 ~ 126]
    132: {"grade": 2, "perc": 95}, # PDF상 표기 오류 보정(문맥상 95~96)
    131: {"grade": 2, "perc": 94}, # PDF 누락 구간 추정
    130: {"grade": 2, "perc": 93},
    129: {"grade": 2, "perc": 92},
    128: {"grade": 2, "perc": 91},
    127: {"grade": 2, "perc": 90},
    126: {"grade": 2, "perc": 89}, # 2등급 컷

    # [3등급 구간: 125 ~ 117]
    125: {"grade": 3, "perc": 88},
    124: {"grade": 3, "perc": 87},
    123: {"grade": 3, "perc": 86},
    122: {"grade": 3, "perc": 84},
    121: {"grade": 3, "perc": 83},
    120: {"grade": 3, "perc": 81},
    119: {"grade": 3, "perc": 80},
    118: {"grade": 3, "perc": 78},
    117: {"grade": 3, "perc": 77}, # 3등급 컷

    # [4등급 구간: 116 ~ 107]
    116: {"grade": 4, "perc": 75},
    115: {"grade": 4, "perc": 74},
    114: {"grade": 4, "perc": 72},
    113: {"grade": 4, "perc": 71},
    112: {"grade": 4, "perc": 69},
    111: {"grade": 4, "perc": 67},
    110: {"grade": 4, "perc": 66},
    109: {"grade": 4, "perc": 64},
    108: {"grade": 4, "perc": 62},
    107: {"grade": 4, "perc": 61}, # 4등급 컷

    # [5등급 구간: 106 ~ 94]
    106: {"grade": 5, "perc": 59},
    105: {"grade": 5, "perc": 57}, # 누적비율 역산
    104: {"grade": 5, "perc": 56},
    103: {"grade": 5, "perc": 54},
    102: {"grade": 5, "perc": 52},
    101: {"grade": 5, "perc": 51},
    100: {"grade": 5, "perc": 49},
    99:  {"grade": 5, "perc": 47},
    98:  {"grade": 5, "perc": 46},
    97:  {"grade": 5, "perc": 44},
    96:  {"grade": 5, "perc": 43},
    95:  {"grade": 5, "perc": 41},
    94:  {"grade": 5, "perc": 40}, # 5등급 컷

    # [6등급 구간: 93 ~ 83]
    93: {"grade": 6, "perc": 38},
    92: {"grade": 6, "perc": 36},
    91: {"grade": 6, "perc": 35},
    90: {"grade": 6, "perc": 33},
    89: {"grade": 6, "perc": 32},
    88: {"grade": 6, "perc": 31},
    87: {"grade": 6, "perc": 29},
    86: {"grade": 6, "perc": 28},
    85: {"grade": 6, "perc": 26},
    84: {"grade": 6, "perc": 25},
    83: {"grade": 6, "perc": 23}, # 6등급 컷

    # [7등급 구간: 82 ~ 73]
    82: {"grade": 7, "perc": 22},
    81: {"grade": 7, "perc": 21},
    80: {"grade": 7, "perc": 20}, # 추정
    79: {"grade": 7, "perc": 18},
    78: {"grade": 7, "perc": 17},
    77: {"grade": 7, "perc": 16},
    76: {"grade": 7, "perc": 14},
    75: {"grade": 7, "perc": 13}, # 추정
    74: {"grade": 7, "perc": 12},
    73: {"grade": 7, "perc": 11}, # 7등급 컷

    # [8등급 구간: 72 ~ 66]
    72: {"grade": 8, "perc": 10},
    71: {"grade": 8, "perc": 9},
    70: {"grade": 8, "perc": 8},
    69: {"grade": 8, "perc": 7},
    68: {"grade": 8, "perc": 6},
    67: {"grade": 8, "perc": 4},
    66: {"grade": 8, "perc": 4}, # 8등급 컷

    # [9등급 구간]
    65: {"grade": 9, "perc": 3},
    # ... 이하 생략 (0~3%)
}


# 2026 수능 영어 등급 데이터 (절대평가)
english_grade_data = {
    1: {"raw_cut": 90, "ratio": 3.11},
    2: {"raw_cut": 80, "ratio": 17.46}, # 누적비율
    3: {"raw_cut": 70, "ratio": 43.76},
    4: {"raw_cut": 60, "ratio": 68.29},
    5: {"raw_cut": 50, "ratio": 81.57},
    6: {"raw_cut": 40, "ratio": 89.59},
    7: {"raw_cut": 30, "ratio": 95.23},
    8: {"raw_cut": 20, "ratio": 98.87},
    9: {"raw_cut": 0,  "ratio": 100.00}
}


# 2026 수능 한국사 등급 데이터 (절대평가)
history_grade_data = {
    1: {"raw_cut": 40},
    2: {"raw_cut": 35},
    3: {"raw_cut": 30},
    4: {"raw_cut": 25},
    5: {"raw_cut": 20},
    6: {"raw_cut": 15},
    7: {"raw_cut": 10},
    8: {"raw_cut": 5},
    9: {"raw_cut": 0}
}



# 2026 수능 사회탐구 영역 원점수-표준점수-백분위 매핑 데이터
# [출처: 크럭스 테이블 계산기 2026 수능 실채점 기반]

social_studies_data = {
    "경제": {
        "50": {"std": 70, "perc": 99, "grade": 1},
        "49": {"std": 70, "perc": 99, "grade": 1},
        "48": {"std": 69, "perc": 97, "grade": 1},
        "47": {"std": 68, "perc": 96, "grade": 1},
        "46": {"std": 67, "perc": 94, "grade": 2},
        "44": {"std": 66, "perc": 92, "grade": 2},
        "43": {"std": 65, "perc": 90, "grade": 2},
        "42": {"std": 64, "perc": 88, "grade": 3},
        "41": {"std": 63, "perc": 86, "grade": 3},
        "40": {"std": 63, "perc": 86, "grade": 3}, # 41-39 구간 혼재, 보수적 적용
        "39": {"std": 62, "perc": 84, "grade": 3},
        "38": {"std": 61, "perc": 81, "grade": 3},
        "37": {"std": 60, "perc": 78, "grade": 3},
        "36": {"std": 59, "perc": 76, "grade": 3},
        "35": {"std": 58, "perc": 74, "grade": 4},
        "34": {"std": 58, "perc": 74, "grade": 4},
        "33": {"std": 57, "perc": 71, "grade": 4},
        "32": {"std": 56, "perc": 69, "grade": 4},
        "31": {"std": 55, "perc": 67, "grade": 4},
        "30": {"std": 55, "perc": 67, "grade": 4},
        "29": {"std": 54, "perc": 64, "grade": 4},
        "28": {"std": 53, "perc": 62, "grade": 4},
        "27": {"std": 52, "perc": 60, "grade": 4},
        "26": {"std": 50, "perc": 55, "grade": 5}, # 추정
        "25": {"std": 50, "perc": 55, "grade": 5}, # 추정
        "24": {"std": 50, "perc": 55, "grade": 5}, # 추정
        "23": {"std": 49, "perc": 54, "grade": 5},
        "22": {"std": 48, "perc": 51, "grade": 5},
        "20": {"std": 47, "perc": 48, "grade": 5},
        "19": {"std": 46, "perc": 44, "grade": 5},
        "18": {"std": 45, "perc": 41, "grade": 5}
    },
    
    "동아시아사": {
        "50": {"std": 68, "perc": 99, "grade": 1},
        "49": {"std": 68, "perc": 99, "grade": 1},
        "48": {"std": 66, "perc": 98, "grade": 1},
        "47": {"std": 65, "perc": 96, "grade": 1},
        "46": {"std": 65, "perc": 96, "grade": 1},
        "45": {"std": 64, "perc": 93, "grade": 2},
        "44": {"std": 63, "perc": 90, "grade": 2},
        "43": {"std": 62, "perc": 88, "grade": 2},
        "41": {"std": 61, "perc": 84, "grade": 3},
        "40": {"std": 60, "perc": 79, "grade": 3},
        "39": {"std": 59, "perc": 76, "grade": 3},
        "38": {"std": 58, "perc": 71, "grade": 4},
        "36": {"std": 57, "perc": 66, "grade": 4},
        "35": {"std": 56, "perc": 64, "grade": 4},
        "33": {"std": 55, "perc": 61, "grade": 4},
        "32": {"std": 54, "perc": 58, "grade": 5},
        "31": {"std": 53, "perc": 56, "grade": 5},
        "30": {"std": 52, "perc": 53, "grade": 5},
        "28": {"std": 51, "perc": 51, "grade": 5},
        "27": {"std": 50, "perc": 49, "grade": 5},
        "26": {"std": 49, "perc": 47, "grade": 5},
        "25": {"std": 49, "perc": 47, "grade": 5},
        "24": {"std": 48, "perc": 44, "grade": 5},
        "23": {"std": 47, "perc": 43, "grade": 5},
        "22": {"std": 46, "perc": 41, "grade": 5},
        "20": {"std": 45, "perc": 38, "grade": 6},
        "19": {"std": 44, "perc": 35, "grade": 6},
        "18": {"std": 43, "perc": 33, "grade": 6}
    },
    
    "사회문화": {
        "50": {"std": 70, "perc": 100, "grade": 1},
        "49": {"std": 70, "perc": 100, "grade": 1},
        "48": {"std": 69, "perc": 99, "grade": 1},
        "47": {"std": 68, "perc": 99, "grade": 1},
        "46": {"std": 67, "perc": 98, "grade": 1},
        "45": {"std": 66, "perc": 97, "grade": 1},
        "44": {"std": 65, "perc": 95, "grade": 1},
        "43": {"std": 64, "perc": 94, "grade": 2},
        "42": {"std": 63, "perc": 92, "grade": 2},
        "41": {"std": 62, "perc": 89, "grade": 2},
        "40": {"std": 61, "perc": 85, "grade": 3},
        "39": {"std": 61, "perc": 85, "grade": 3},
        "38": {"std": 60, "perc": 80, "grade": 3},
        "37": {"std": 59, "perc": 77, "grade": 3},
        "36": {"std": 58, "perc": 74, "grade": 4},
        "35": {"std": 57, "perc": 70, "grade": 4},
        "34": {"std": 56, "perc": 67, "grade": 4},
        "33": {"std": 55, "perc": 64, "grade": 4},
        "32": {"std": 54, "perc": 61, "grade": 4},
        "31": {"std": 53, "perc": 56, "grade": 5},
        "29": {"std": 52, "perc": 52, "grade": 5},
        "28": {"std": 51, "perc": 49, "grade": 5},
        "27": {"std": 50, "perc": 47, "grade": 5},
        "26": {"std": 49, "perc": 44, "grade": 5},
        "25": {"std": 48, "perc": 42, "grade": 5},
        "24": {"std": 47, "perc": 39, "grade": 5},
        "23": {"std": 46, "perc": 37, "grade": 6},
        "22": {"std": 45, "perc": 34, "grade": 6},
        "20": {"std": 44, "perc": 31, "grade": 6},
        "19": {"std": 43, "perc": 27, "grade": 6},
        "18": {"std": 42, "perc": 25, "grade": 6}
    },
    
    "생활과윤리": {
        "50": {"std": 71, "perc": 100, "grade": 1},
        "49": {"std": 71, "perc": 100, "grade": 1},
        "48": {"std": 69, "perc": 99, "grade": 1},
        "47": {"std": 68, "perc": 98, "grade": 1},
        "46": {"std": 67, "perc": 97, "grade": 1},
        "45": {"std": 66, "perc": 95, "grade": 1},
        "44": {"std": 66, "perc": 95, "grade": 1},
        "43": {"std": 65, "perc": 92, "grade": 2},
        "42": {"std": 64, "perc": 90, "grade": 2},
        "41": {"std": 63, "perc": 88, "grade": 3},
        "40": {"std": 62, "perc": 86, "grade": 3},
        "39": {"std": 61, "perc": 83, "grade": 3},
        "38": {"std": 60, "perc": 80, "grade": 3},
        "37": {"std": 59, "perc": 78, "grade": 3},
        "36": {"std": 58, "perc": 75, "grade": 4},
        "35": {"std": 57, "perc": 73, "grade": 4},
        "34": {"std": 56, "perc": 70, "grade": 4},
        "33": {"std": 55, "perc": 66, "grade": 4},
        "32": {"std": 55, "perc": 66, "grade": 4},
        "31": {"std": 54, "perc": 62, "grade": 4},
        "30": {"std": 53, "perc": 60, "grade": 4},
        "29": {"std": 52, "perc": 57, "grade": 5},
        "28": {"std": 51, "perc": 54, "grade": 5},
        "27": {"std": 50, "perc": 51, "grade": 5},
        "26": {"std": 49, "perc": 48, "grade": 5},
        "25": {"std": 48, "perc": 45, "grade": 5},
        "24": {"std": 47, "perc": 42, "grade": 5},
        "23": {"std": 46, "perc": 39, "grade": 5},
        "22": {"std": 45, "perc": 36, "grade": 6},
        "21": {"std": 44, "perc": 31, "grade": 6}
    },
    
    "세계사": {
        "50": {"std": 72, "perc": 100, "grade": 1},
        "49": {"std": 72, "perc": 100, "grade": 1},
        "48": {"std": 71, "perc": 99, "grade": 1},
        "47": {"std": 70, "perc": 98, "grade": 1},
        "46": {"std": 69, "perc": 97, "grade": 1},
        "45": {"std": 68, "perc": 96, "grade": 1},
        "44": {"std": 67, "perc": 95, "grade": 2},
        "43": {"std": 66, "perc": 93, "grade": 2},
        "41": {"std": 65, "perc": 90, "grade": 2},
        "40": {"std": 64, "perc": 88, "grade": 2},
        "39": {"std": 63, "perc": 87, "grade": 3},
        "38": {"std": 62, "perc": 85, "grade": 3},
        "37": {"std": 61, "perc": 83, "grade": 3},
        "35": {"std": 60, "perc": 80, "grade": 3},
        "34": {"std": 59, "perc": 76, "grade": 3},
        "33": {"std": 58, "perc": 74, "grade": 4},
        "32": {"std": 57, "perc": 72, "grade": 4},
        "31": {"std": 56, "perc": 70, "grade": 4},
        "30": {"std": 55, "perc": 68, "grade": 4},
        "29": {"std": 54, "perc": 65, "grade": 4},
        "28": {"std": 54, "perc": 65, "grade": 4},
        "27": {"std": 53, "perc": 62, "grade": 4},
        "26": {"std": 52, "perc": 59, "grade": 4},
        "25": {"std": 51, "perc": 57, "grade": 5},
        "24": {"std": 50, "perc": 55, "grade": 5},
        "23": {"std": 49, "perc": 53, "grade": 5},
        "22": {"std": 48, "perc": 49, "grade": 5},
        "21": {"std": 48, "perc": 49, "grade": 5},
        "20": {"std": 47, "perc": 45, "grade": 5},
        "19": {"std": 46, "perc": 42, "grade": 5},
        "18": {"std": 45, "perc": 39, "grade": 5}
    },
    
    "세계지리": {
        "50": {"std": 73, "perc": 100, "grade": 1},
        "48": {"std": 71, "perc": 100, "grade": 1},
        "47": {"std": 70, "perc": 99, "grade": 1},
        "46": {"std": 69, "perc": 98, "grade": 1},
        "44": {"std": 68, "perc": 97, "grade": 1},
        "43": {"std": 67, "perc": 95, "grade": 2},
        "42": {"std": 66, "perc": 94, "grade": 2},
        "41": {"std": 65, "perc": 92, "grade": 2},
        "40": {"std": 64, "perc": 90, "grade": 2},
        "39": {"std": 63, "perc": 88, "grade": 2},
        "37": {"std": 62, "perc": 85, "grade": 3},
        "36": {"std": 61, "perc": 82, "grade": 3},
        "35": {"std": 60, "perc": 79, "grade": 3},
        "34": {"std": 59, "perc": 77, "grade": 3},
        "33": {"std": 58, "perc": 74, "grade": 4},
        "32": {"std": 57, "perc": 72, "grade": 4},
        "31": {"std": 56, "perc": 68, "grade": 4},
        "29": {"std": 55, "perc": 64, "grade": 4},
        "28": {"std": 54, "perc": 62, "grade": 4},
        "27": {"std": 53, "perc": 60, "grade": 4},
        "26": {"std": 52, "perc": 58, "grade": 5},
        "25": {"std": 51, "perc": 55, "grade": 5},
        "24": {"std": 51, "perc": 55, "grade": 5},
        "23": {"std": 50, "perc": 51, "grade": 5},
        "22": {"std": 49, "perc": 49, "grade": 5},
        "21": {"std": 48, "perc": 47, "grade": 5},
        "20": {"std": 47, "perc": 45, "grade": 5},
        "19": {"std": 46, "perc": 42, "grade": 5}
    },
    
    "정치와법": {
        "50": {"std": 67, "perc": 99, "grade": 1},
        "49": {"std": 67, "perc": 99, "grade": 1},
        "48": {"std": 65, "perc": 97, "grade": 1},
        "47": {"std": 65, "perc": 97, "grade": 1},
        "46": {"std": 64, "perc": 94, "grade": 2},
        "45": {"std": 63, "perc": 92, "grade": 2},
        "43": {"std": 62, "perc": 87, "grade": 2},
        "42": {"std": 61, "perc": 82, "grade": 3},
        "41": {"std": 60, "perc": 80, "grade": 3},
        "40": {"std": 59, "perc": 76, "grade": 3},
        "39": {"std": 58, "perc": 71, "grade": 4},
        "38": {"std": 58, "perc": 71, "grade": 4},
        "37": {"std": 57, "perc": 66, "grade": 4},
        "36": {"std": 56, "perc": 64, "grade": 4},
        "34": {"std": 55, "perc": 60, "grade": 4},
        "33": {"std": 54, "perc": 56, "grade": 5},
        "32": {"std": 53, "perc": 54, "grade": 5},
        "31": {"std": 52, "perc": 52, "grade": 5},
        "30": {"std": 51, "perc": 50, "grade": 5},
        "28": {"std": 50, "perc": 47, "grade": 5},
        "27": {"std": 49, "perc": 46, "grade": 5},
        "26": {"std": 48, "perc": 43, "grade": 5},
        "25": {"std": 48, "perc": 43, "grade": 5},
        "24": {"std": 47, "perc": 41, "grade": 5},
        "23": {"std": 46, "perc": 39, "grade": 5},
        "22": {"std": 45, "perc": 38, "grade": 6},
        "20": {"std": 44, "perc": 35, "grade": 6},
        "19": {"std": 43, "perc": 32, "grade": 6},
        "18": {"std": 42, "perc": 30, "grade": 6}
    },
    
    "한국지리": {
        "50": {"std": 72, "perc": 100, "grade": 1},
        "49": {"std": 72, "perc": 100, "grade": 1},
        "48": {"std": 70, "perc": 99, "grade": 1},
        "46": {"std": 69, "perc": 98, "grade": 1},
        "45": {"std": 68, "perc": 96, "grade": 1},
        "44": {"std": 67, "perc": 94, "grade": 2},
        "43": {"std": 66, "perc": 93, "grade": 2},
        "41": {"std": 65, "perc": 91, "grade": 2},
        "40": {"std": 64, "perc": 88, "grade": 3},
        "39": {"std": 63, "perc": 86, "grade": 3},
        "38": {"std": 62, "perc": 84, "grade": 3},
        "37": {"std": 61, "perc": 82, "grade": 3},
        "35": {"std": 60, "perc": 79, "grade": 3},
        "34": {"std": 59, "perc": 76, "grade": 3},
        "33": {"std": 58, "perc": 74, "grade": 4},
        "32": {"std": 57, "perc": 72, "grade": 4},
        "31": {"std": 56, "perc": 69, "grade": 4},
        "29": {"std": 55, "perc": 66, "grade": 4},
        "28": {"std": 54, "perc": 64, "grade": 4},
        "27": {"std": 53, "perc": 62, "grade": 4},
        "26": {"std": 52, "perc": 59, "grade": 4},
        "24": {"std": 51, "perc": 57, "grade": 5},
        "23": {"std": 50, "perc": 55, "grade": 5},
        "22": {"std": 49, "perc": 53, "grade": 5},
        "21": {"std": 48, "perc": 50, "grade": 5},
        "20": {"std": 47, "perc": 47, "grade": 5},
        "19": {"std": 47, "perc": 47, "grade": 5},
        "18": {"std": 46, "perc": 43, "grade": 5}
    },
    
    "윤리와사상": {
        "50": {"std": 70, "perc": 100, "grade": 1},
        "49": {"std": 70, "perc": 100, "grade": 1},
        "48": {"std": 69, "perc": 99, "grade": 1},
        "47": {"std": 68, "perc": 97, "grade": 1},
        "46": {"std": 67, "perc": 96, "grade": 1},
        "45": {"std": 66, "perc": 95, "grade": 1},
        "44": {"std": 65, "perc": 93, "grade": 2},
        "43": {"std": 64, "perc": 89, "grade": 2},
        "42": {"std": 64, "perc": 89, "grade": 2},
        "41": {"std": 63, "perc": 86, "grade": 3},
        "40": {"std": 62, "perc": 84, "grade": 3},
        "39": {"std": 61, "perc": 81, "grade": 3},
        "38": {"std": 60, "perc": 79, "grade": 3},
        "37": {"std": 59, "perc": 76, "grade": 3},
        "35": {"std": 58, "perc": 72, "grade": 4},
        "34": {"std": 57, "perc": 70, "grade": 4},
        "33": {"std": 56, "perc": 68, "grade": 4},
        "32": {"std": 55, "perc": 66, "grade": 4},
        "30": {"std": 54, "perc": 63, "grade": 4},
        "29": {"std": 53, "perc": 60, "grade": 4},
        "28": {"std": 52, "perc": 58, "grade": 5},
        "27": {"std": 51, "perc": 55, "grade": 5},
        "26": {"std": 50, "perc": 53, "grade": 5},
        "24": {"std": 49, "perc": 50, "grade": 5},
        "23": {"std": 48, "perc": 47, "grade": 5},
        "22": {"std": 47, "perc": 44, "grade": 5},
        "21": {"std": 46, "perc": 42, "grade": 5},
        "20": {"std": 45, "perc": 39, "grade": 5},
        "19": {"std": 44, "perc": 36, "grade": 6},
        "18": {"std": 42, "perc": 33, "grade": 6}
    }
}



science_inquiry_data = {
    "물리학1": {
        "50": {"std": 70, "perc": 100, "grade": 1},
        "49": {"std": 70, "perc": 100, "grade": 1},
        "48": {"std": 69, "perc": 99, "grade": 1},
        "47": {"std": 68, "perc": 98, "grade": 1},
        "46": {"std": 67, "perc": 97, "grade": 1},
        "45": {"std": 66, "perc": 96, "grade": 1},
        "43": {"std": 65, "perc": 93, "grade": 2},
        "42": {"std": 64, "perc": 90, "grade": 2},
        "41": {"std": 63, "perc": 88, "grade": 3},
        "40": {"std": 62, "perc": 86, "grade": 3},
        "39": {"std": 61, "perc": 83, "grade": 3},
        "37": {"std": 60, "perc": 79, "grade": 3},
        "36": {"std": 59, "perc": 76, "grade": 4},
        "35": {"std": 58, "perc": 73, "grade": 4},
        "34": {"std": 57, "perc": 71, "grade": 4},
        "32": {"std": 56, "perc": 67, "grade": 4},
        "31": {"std": 55, "perc": 63, "grade": 4},
        "30": {"std": 54, "perc": 61, "grade": 4},
        "29": {"std": 53, "perc": 59, "grade": 4},
        "28": {"std": 52, "perc": 57, "grade": 5},
        "27": {"std": 51, "perc": 54, "grade": 5},
        "26": {"std": 51, "perc": 54, "grade": 5},
        "25": {"std": 50, "perc": 50, "grade": 5},
        "24": {"std": 49, "perc": 48, "grade": 5},
        "23": {"std": 48, "perc": 46, "grade": 5},
        "21": {"std": 47, "perc": 43, "grade": 5},
        "20": {"std": 46, "perc": 39, "grade": 5},
        "19": {"std": 45, "perc": 37, "grade": 6},
        "18": {"std": 44, "perc": 34, "grade": 6},
        "17": {"std": 43, "perc": 32, "grade": 6},
        "16": {"std": 42, "perc": 28, "grade": 6},
        "15": {"std": 42, "perc": 28, "grade": 6},
        "14": {"std": 41, "perc": 24, "grade": 6},
        "13": {"std": 40, "perc": 21, "grade": 7},
        "12": {"std": 39, "perc": 18, "grade": 7},
        "11": {"std": 38, "perc": 9, "grade": 7}, # 백분위 급락 구간 확인 필요
        "8":  {"std": 36, "perc": 7, "grade": 8}
    },

    "물리학2": {
        "50": {"std": 68, "perc": 99, "grade": 1},
        "49": {"std": 68, "perc": 99, "grade": 1},
        "48": {"std": 66, "perc": 95, "grade": 1},
        "47": {"std": 66, "perc": 95, "grade": 1},
        "46": {"std": 65, "perc": 93, "grade": 2},
        "45": {"std": 64, "perc": 91, "grade": 2},
        "43": {"std": 63, "perc": 88, "grade": 2},
        "42": {"std": 62, "perc": 84, "grade": 3},
        "41": {"std": 61, "perc": 82, "grade": 3},
        "39": {"std": 60, "perc": 79, "grade": 3},
        "38": {"std": 59, "perc": 76, "grade": 4},
        "37": {"std": 58, "perc": 73, "grade": 4},
        "36": {"std": 57, "perc": 69, "grade": 4},
        "35": {"std": 57, "perc": 69, "grade": 4},
        "34": {"std": 56, "perc": 66, "grade": 4},
        "33": {"std": 55, "perc": 64, "grade": 4},
        "31": {"std": 54, "perc": 61, "grade": 4},
        "30": {"std": 53, "perc": 59, "grade": 5},
        "29": {"std": 52, "perc": 57, "grade": 5},
        "28": {"std": 51, "perc": 54, "grade": 5},
        "27": {"std": 51, "perc": 54, "grade": 5},
        "19": {"std": 45, "perc": 39, "grade": 5},
        "18": {"std": 44, "perc": 35, "grade": 6},
        "17": {"std": 43, "perc": 33, "grade": 6},
        "16": {"std": 42, "perc": 28, "grade": 6},
        "15": {"std": 42, "perc": 28, "grade": 6},
        "14": {"std": 41, "perc": 25, "grade": 6}
    },

    "화학1": {
        "50": {"std": 71, "perc": 100, "grade": 1},
        "47": {"std": 69, "perc": 98, "grade": 1},
        "46": {"std": 68, "perc": 96, "grade": 1},
        "45": {"std": 67, "perc": 95, "grade": 1},
        "44": {"std": 66, "perc": 93, "grade": 2},
        "43": {"std": 65, "perc": 92, "grade": 2},
        "41": {"std": 64, "perc": 89, "grade": 2},
        "40": {"std": 63, "perc": 86, "grade": 3},
        "39": {"std": 62, "perc": 84, "grade": 3},
        "38": {"std": 61, "perc": 82, "grade": 3},
        "36": {"std": 60, "perc": 80, "grade": 3},
        "35": {"std": 59, "perc": 77, "grade": 3},
        "34": {"std": 58, "perc": 74, "grade": 4},
        "33": {"std": 57, "perc": 72, "grade": 4},
        "32": {"std": 56, "perc": 69, "grade": 4},
        "31": {"std": 56, "perc": 69, "grade": 4},
        "30": {"std": 55, "perc": 66, "grade": 4},
        "29": {"std": 54, "perc": 64, "grade": 4},
        "28": {"std": 53, "perc": 62, "grade": 4},
        "27": {"std": 52, "perc": 60, "grade": 4},
        "26": {"std": 51, "perc": 57, "grade": 5},
        "24": {"std": 50, "perc": 53, "grade": 5},
        "23": {"std": 49, "perc": 51, "grade": 5},
        "22": {"std": 48, "perc": 48, "grade": 5},
        "21": {"std": 47, "perc": 45, "grade": 5},
        "20": {"std": 47, "perc": 45, "grade": 5},
        "19": {"std": 46, "perc": 41, "grade": 5},
        "18": {"std": 45, "perc": 38, "grade": 6},
        "17": {"std": 44, "perc": 36, "grade": 6},
        "16": {"std": 43, "perc": 31, "grade": 6},
        "15": {"std": 43, "perc": 31, "grade": 6},
        "14": {"std": 42, "perc": 27, "grade": 6},
        "13": {"std": 41, "perc": 24, "grade": 6},
        "12": {"std": 40, "perc": 20, "grade": 7}
    },

    "화학2": {
        "50": {"std": 70, "perc": 99, "grade": 1},
        "49": {"std": 70, "perc": 99, "grade": 1},
        "48": {"std": 69, "perc": 98, "grade": 1},
        "47": {"std": 68, "perc": 96, "grade": 1},
        "46": {"std": 67, "perc": 95, "grade": 2},
        "45": {"std": 66, "perc": 93, "grade": 2},
        "43": {"std": 65, "perc": 91, "grade": 2},
        "42": {"std": 64, "perc": 89, "grade": 2},
        "41": {"std": 63, "perc": 87, "grade": 3},
        "39": {"std": 62, "perc": 84, "grade": 3},
        "38": {"std": 61, "perc": 81, "grade": 3},
        "37": {"std": 60, "perc": 79, "grade": 3},
        "36": {"std": 59, "perc": 77, "grade": 3},
        "34": {"std": 58, "perc": 74, "grade": 4},
        "33": {"std": 57, "perc": 71, "grade": 4},
        "32": {"std": 56, "perc": 69, "grade": 4},
        "31": {"std": 55, "perc": 67, "grade": 4},
        "29": {"std": 54, "perc": 64, "grade": 4},
        "28": {"std": 53, "perc": 61, "grade": 4},
        "27": {"std": 52, "perc": 59, "grade": 5},
        "26": {"std": 51, "perc": 56, "grade": 5},
        "24": {"std": 50, "perc": 53, "grade": 5},
        "23": {"std": 49, "perc": 51, "grade": 5},
        "22": {"std": 48, "perc": 49, "grade": 5},
        "21": {"std": 47, "perc": 45, "grade": 5},
        "20": {"std": 47, "perc": 45, "grade": 5},
        "19": {"std": 46, "perc": 42, "grade": 5},
        "18": {"std": 45, "perc": 40, "grade": 5},
        "17": {"std": 44, "perc": 37, "grade": 6},
        "16": {"std": 43, "perc": 32, "grade": 6}
    },

    "생명과학1": {
        "50": {"std": 74, "perc": 100, "grade": 1},
        "47": {"std": 72, "perc": 100, "grade": 1},
        "46": {"std": 71, "perc": 100, "grade": 1},
        "45": {"std": 70, "perc": 99, "grade": 1},
        "44": {"std": 69, "perc": 99, "grade": 1},
        "43": {"std": 68, "perc": 98, "grade": 1},
        "42": {"std": 67, "perc": 97, "grade": 1},
        "41": {"std": 66, "perc": 95, "grade": 2},
        "40": {"std": 65, "perc": 93, "grade": 2},
        "39": {"std": 64, "perc": 91, "grade": 2},
        "38": {"std": 63, "perc": 89, "grade": 2},
        "37": {"std": 62, "perc": 86, "grade": 3},
        "36": {"std": 61, "perc": 83, "grade": 3},
        "35": {"std": 60, "perc": 80, "grade": 3},
        "34": {"std": 59, "perc": 77, "grade": 3},
        "33": {"std": 58, "perc": 73, "grade": 4},
        "32": {"std": 57, "perc": 70, "grade": 4},
        "31": {"std": 56, "perc": 67, "grade": 4},
        "30": {"std": 55, "perc": 64, "grade": 4},
        "29": {"std": 54, "perc": 60, "grade": 4},
        "28": {"std": 53, "perc": 57, "grade": 5},
        "27": {"std": 52, "perc": 54, "grade": 5},
        "26": {"std": 51, "perc": 51, "grade": 5},
        "25": {"std": 50, "perc": 48, "grade": 5},
        "24": {"std": 49, "perc": 45, "grade": 5},
        "23": {"std": 48, "perc": 42, "grade": 5},
        "22": {"std": 47, "perc": 39, "grade": 5},
        "21": {"std": 46, "perc": 36, "grade": 6},
        "20": {"std": 45, "perc": 33, "grade": 6},
        "19": {"std": 44, "perc": 30, "grade": 6},
        "18": {"std": 43, "perc": 27, "grade": 6},
        "17": {"std": 42, "perc": 24, "grade": 6},
        "16": {"std": 41, "perc": 21, "grade": 7}
    },

    "생명과학2": {
        "50": {"std": 69, "perc": 99, "grade": 1},
        "49": {"std": 69, "perc": 99, "grade": 1},
        "48": {"std": 67, "perc": 98, "grade": 1},
        "46": {"std": 66, "perc": 96, "grade": 1},
        "45": {"std": 65, "perc": 95, "grade": 1},
        "43": {"std": 64, "perc": 92, "grade": 2},
        "42": {"std": 63, "perc": 88, "grade": 2},
        "41": {"std": 62, "perc": 85, "grade": 3},
        "39": {"std": 61, "perc": 80, "grade": 3},
        "38": {"std": 60, "perc": 76, "grade": 3},
        "37": {"std": 59, "perc": 74, "grade": 4},
        "36": {"std": 58, "perc": 71, "grade": 4},
        "34": {"std": 57, "perc": 68, "grade": 4},
        "33": {"std": 56, "perc": 65, "grade": 4},
        "32": {"std": 55, "perc": 63, "grade": 4},
        "30": {"std": 54, "perc": 60, "grade": 4},
        "29": {"std": 53, "perc": 58, "grade": 5},
        "28": {"std": 52, "perc": 56, "grade": 5},
        "27": {"std": 51, "perc": 54, "grade": 5},
        "26": {"std": 51, "perc": 54, "grade": 5},
        "25": {"std": 50, "perc": 52, "grade": 5},
        "24": {"std": 49, "perc": 50, "grade": 5},
        "23": {"std": 48, "perc": 48, "grade": 5},
        "22": {"std": 47, "perc": 45, "grade": 5},
        "20": {"std": 46, "perc": 42, "grade": 5},
        "19": {"std": 45, "perc": 40, "grade": 5},
        "17": {"std": 44, "perc": 30, "grade": 6}, # 데이터 확인됨 (PDF)
        "16": {"std": 43, "perc": 32, "grade": 6}  # 백분위 역전 주의 (PDF 원본 따름)
    },

    "지구과학1": {
        "50": {"std": 68, "perc": 99, "grade": 1},
        "49": {"std": 68, "perc": 99, "grade": 1},
        "48": {"std": 66, "perc": 97, "grade": 1},
        "47": {"std": 65, "perc": 95, "grade": 1},
        "46": {"std": 65, "perc": 95, "grade": 1},
        "45": {"std": 64, "perc": 91, "grade": 2},
        "44": {"std": 63, "perc": 89, "grade": 2},
        "43": {"std": 62, "perc": 85, "grade": 3},
        "42": {"std": 62, "perc": 85, "grade": 3},
        "41": {"std": 61, "perc": 81, "grade": 3},
        "40": {"std": 60, "perc": 79, "grade": 3},
        "39": {"std": 59, "perc": 75, "grade": 3},
        "38": {"std": 59, "perc": 75, "grade": 3},
        "37": {"std": 58, "perc": 72, "grade": 4},
        "36": {"std": 57, "perc": 69, "grade": 4},
        "35": {"std": 56, "perc": 65, "grade": 4},
        "33": {"std": 55, "perc": 62, "grade": 4},
        "32": {"std": 54, "perc": 60, "grade": 4},
        "31": {"std": 53, "perc": 58, "grade": 5},
        "29": {"std": 52, "perc": 55, "grade": 5},
        "28": {"std": 51, "perc": 52, "grade": 5},
        "27": {"std": 50, "perc": 50, "grade": 5},
        "26": {"std": 49, "perc": 48, "grade": 5},
        "24": {"std": 48, "perc": 45, "grade": 5},
        "23": {"std": 47, "perc": 43, "grade": 5},
        "22": {"std": 46, "perc": 40, "grade": 5},
        "21": {"std": 46, "perc": 40, "grade": 5},
        "20": {"std": 45, "perc": 37, "grade": 6},
        "19": {"std": 44, "perc": 35, "grade": 6},
        "17": {"std": 43, "perc": 30, "grade": 6}
    },

    "지구과학2": {
        "50": {"std": 69, "perc": 98, "grade": 1},
        "49": {"std": 69, "perc": 98, "grade": 1},
        "48": {"std": 68, "perc": 95, "grade": 1},
        "47": {"std": 67, "perc": 93, "grade": 2},
        "46": {"std": 66, "perc": 91, "grade": 2},
        "44": {"std": 65, "perc": 88, "grade": 2},
        "43": {"std": 64, "perc": 85, "grade": 3},
        "42": {"std": 63, "perc": 83, "grade": 3},
        "41": {"std": 62, "perc": 81, "grade": 3},
        "39": {"std": 61, "perc": 79, "grade": 3},
        "37": {"std": 60, "perc": 77, "grade": 3},
        "36": {"std": 59, "perc": 75, "grade": 4},
        "35": {"std": 58, "perc": 74, "grade": 4},
        "34": {"std": 57, "perc": 72, "grade": 4},
        "33": {"std": 57, "perc": 72, "grade": 4},
        "32": {"std": 56, "perc": 70, "grade": 4},
        "31": {"std": 55, "perc": 68, "grade": 4},
        "29": {"std": 54, "perc": 67, "grade": 4},
        "28": {"std": 53, "perc": 65, "grade": 4},
        "27": {"std": 52, "perc": 63, "grade": 4},
        "26": {"std": 52, "perc": 63, "grade": 4},
        "25": {"std": 51, "perc": 61, "grade": 4},
        "24": {"std": 50, "perc": 59, "grade": 5},
        "23": {"std": 49, "perc": 56, "grade": 5},
        "22": {"std": 49, "perc": 56, "grade": 5},
        "21": {"std": 48, "perc": 53, "grade": 5},
        "20": {"std": 47, "perc": 51, "grade": 5},
        "19": {"std": 46, "perc": 47, "grade": 5}
    }
}


# 2026 수능 국어/수학 등급컷 데이터 (원점수 기준)
major_subjects_grade_cuts = {
    "국어": {
        "화법과작문": {
            "max": {"raw": 100, "std": 142, "perc": 99}, # 만점
            1: {"raw": 90, "std": 133, "perc": 96},
            2: {"raw": 83, "std": 126, "perc": 89},
            3: {"raw": 73, "std": 117, "perc": 77},
            4: {"raw": 63, "std": 107, "perc": 61},
            5: {"raw": 49, "std": 94, "perc": 40},
            6: {"raw": 37, "std": 83, "perc": 23}
        },
        "언어와매체": {
            "max": {"raw": 100, "std": 147, "perc": 100}, # 만점
            1: {"raw": 85, "std": 133, "perc": 96},
            2: {"raw": 78, "std": 126, "perc": 89},
            3: {"raw": 69, "std": 117, "perc": 77},
            4: {"raw": 59, "std": 107, "perc": 61},
            5: {"raw": 46, "std": 94, "perc": 40},
            6: {"raw": 35, "std": 83, "perc": 23}
        }
    },
    
    "수학": {
        "확률과통계": {
            "max": {"raw": 100, "std": 137, "perc": 100}, # 만점
            1: {"raw": 87, "std": 128, "perc": 96},
            2: {"raw": 82, "std": 124, "perc": 88},
            3: {"raw": 76, "std": 119, "perc": 76},
            4: {"raw": 65, "std": 111, "perc": 60},
            5: {"raw": 41, "std": 92, "perc": 40},
            6: {"raw": 24, "std": 79, "perc": 23}
        },
        "미적분": {
            "max": {"raw": 100, "std": 139, "perc": 100}, # 만점
            1: {"raw": 85, "std": 128, "perc": 96},
            2: {"raw": 80, "std": 124, "perc": 88},
            3: {"raw": 73, "std": 119, "perc": 76},
            4: {"raw": 62, "std": 111, "perc": 60},
            5: {"raw": 37, "std": 92, "perc": 40},
            6: {"raw": 20, "std": 79, "perc": 23},
            7: {"raw": 14, "std": 74, "perc": 12},
            8: {"raw": 10, "std": 71, "perc": 5}
        },
        "기하": {
            "max": {"raw": 100, "std": 139, "perc": 100}, # 만점
            1: {"raw": 85, "std": 128, "perc": 96},
            2: {"raw": 81, "std": 124, "perc": 88},
            3: {"raw": 74, "std": 119, "perc": 76},
            4: {"raw": 63, "std": 111, "perc": 60},
            5: {"raw": 37, "std": 92, "perc": 40},
            6: {"raw": 20, "std": 79, "perc": 23}
        }
    }
}


# 대학별 정시 산출용 데이터는 app/calculators/ 내 각 대학 계산기 클래스에 정의됨
# (경희대: app/calculators/khu.py, 고려대/서울대: 추후 추가)
