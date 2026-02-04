// 백엔드 계산 로직을 그대로 JavaScript로 변환
function calculateScoreBackend(univ, korean, math, tamgu1, tamgu2, english, history, formulas, deductions) {
    const formulaId = String(univ.formulaId);
    const formula = formulas[formulaId];
    
    if (!formula) {
        console.error('Formula not found:', formulaId);
        return 0;
    }
    
    // 계산
    const koreanScore = korean * formula.koreanCoef;
    const mathScore = math * formula.mathCoef;
    const tamgu1Score = tamgu1 * formula.tamguCoef + formula.tamguBonus;
    const tamgu2Score = tamgu2 * formula.tamguCoef + formula.tamguBonus;
    
    // 영어/한국사
    const deduction = deductions[formulaId] || {};
    const englishScore = deduction.englishDeduction || 0;
    const historyScore = (deduction.historyDeductions && history >= 1 && history <= 9) 
        ? (deduction.historyDeductions[history - 1] || 0) 
        : 0;
    
    const total = koreanScore + mathScore + tamgu1Score + tamgu2Score + englishScore + historyScore;
    
    return total;
}
