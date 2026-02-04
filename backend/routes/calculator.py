from fastapi import APIRouter
from pydantic import BaseModel
import json
import os

calculator_bp = APIRouter()

class CalculateRequest(BaseModel):
    korean: float = 0
    math: float = 0
    tamgu1: float = 0
    tamgu2: float = 0
    english: int = 1
    history: int = 1
    gun: str = '가'

# 데이터 로드
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
CALCULATOR_DIR = os.path.join(BASE_DIR, 'suneung-calculator')

with open(os.path.join(CALCULATOR_DIR, 'universities.json'), 'r', encoding='utf-8') as f:
    universities = json.load(f)

with open(os.path.join(CALCULATOR_DIR, 'formulas_extracted.json'), 'r', encoding='utf-8') as f:
    formulas = json.load(f)

with open(os.path.join(CALCULATOR_DIR, 'deduction_tables.json'), 'r', encoding='utf-8') as f:
    deductions = json.load(f)

@calculator_bp.post('/calculate')
async def calculate(req: CalculateRequest):
    """환산점수 계산 API"""
    korean = req.korean
    math = req.math
    tamgu1 = req.tamgu1
    tamgu2 = req.tamgu2
    english = req.english
    history = req.history
    gun = req.gun
    
    results = []
    
    for univ in universities:
        if univ.get('gun') != gun:
            continue
        
        formula_id = str(univ['formulaId'])
        if formula_id not in formulas:
            continue
        
        formula = formulas[formula_id]
        deduction = deductions.get(formula_id, {})
        
        # 계산
        korean_score = korean * formula['koreanCoef']
        math_score = math * formula['mathCoef']
        tamgu1_score = tamgu1 * formula['tamguCoef'] + formula['tamguBonus']
        tamgu2_score = tamgu2 * formula['tamguCoef'] + formula['tamguBonus']
        
        english_score = deduction.get('englishDeduction', 0)
        history_score = deduction.get('historyDeductions', [0]*9)[history-1] if 1 <= history <= 9 else 0
        
        total = korean_score + math_score + tamgu1_score + tamgu2_score + english_score + history_score
        
        results.append({
            'id': univ['id'],
            'university': univ['university'],
            'department': univ['department'],
            'track': univ['track'],
            'myScore': round(total, 2),
            'safeScore': univ.get('safeScore'),
            'appropriateScore': univ.get('appropriateScore'),
            'expectedScore': univ.get('expectedScore'),
            'challengeScore': univ.get('challengeScore')
        })
    
    return results

@calculator_bp.get('/universities')
async def get_universities(gun: str = '가'):
    """대학 목록 조회"""
    filtered = [u for u in universities if u.get('gun') == gun]
    return filtered
