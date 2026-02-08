"""
Test Evaluate Router
- Excel 업로드 및 파싱
- Router/Main/Pipeline/Admin 평가 API
- 결과 Excel/Google Sheets 내보내기
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import json
import asyncio
import io
from datetime import datetime

# 기존 에이전트 직접 연결 (복사 X)
from services.multi_agent.router_agent import (
    route_query,
    set_router_prompt,
    get_router_prompt,
    reset_router_prompt,
    ROUTER_SYSTEM_PROMPT
)
from services.multi_agent.main_agent import generate_response
from services.multi_agent.functions import execute_function_calls
from services.multi_agent.admin_agent2 import (
    evaluate_router,
    evaluate_main,
    evaluate_pipeline
)

router = APIRouter()


# ============================================================
# Router 프롬프트 관리 API
# ============================================================

class PromptUpdateRequest(BaseModel):
    """프롬프트 업데이트 요청"""
    prompt: str


@router.get("/router-prompt")
async def get_prompt():
    """현재 Router 프롬프트 조회"""
    return {
        "prompt": get_router_prompt(),
        "is_default": get_router_prompt() == ROUTER_SYSTEM_PROMPT
    }


@router.post("/router-prompt")
async def update_prompt(request: PromptUpdateRequest):
    """Router 프롬프트 업데이트 (즉시 반영)"""
    try:
        set_router_prompt(request.prompt)
        return {
            "success": True,
            "message": "프롬프트가 업데이트되었습니다. 즉시 반영됩니다."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"프롬프트 업데이트 실패: {str(e)}")


@router.post("/router-prompt/reset")
async def reset_prompt():
    """Router 프롬프트를 기본값으로 리셋"""
    try:
        reset_router_prompt()
        return {
            "success": True,
            "message": "프롬프트가 기본값으로 리셋되었습니다."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"프롬프트 리셋 실패: {str(e)}")


@router.get("/router-prompt/default")
async def get_default_prompt():
    """기본 Router 프롬프트 조회"""
    return {
        "prompt": ROUTER_SYSTEM_PROMPT
    }


# ============================================================
# Request/Response 모델
# ============================================================

class ExcelRow(BaseModel):
    """Excel 행 데이터"""
    row_index: int
    history: Optional[str] = ""
    question: str
    router_output: Optional[str] = ""
    function_result: Optional[str] = ""
    final_answer: Optional[str] = ""


class RouterEvalRequest(BaseModel):
    """Router 평가 요청"""
    rows: List[ExcelRow]


class MainEvalRequest(BaseModel):
    """Main 평가 요청"""
    rows: List[ExcelRow]


class PipelineEvalRequest(BaseModel):
    """Pipeline 평가 요청"""
    rows: List[ExcelRow]


class AdminEvalRequest(BaseModel):
    """Admin 평가 요청 (입력 데이터만 평가)"""
    rows: List[ExcelRow]


class EvalResult(BaseModel):
    """평가 결과"""
    row_index: int
    history: str
    question: str
    router_output: str
    function_result: str
    final_answer: str
    router_score: Optional[int] = None
    main_score: Optional[int] = None
    total_score: Optional[int] = None
    router_eval: Optional[Dict[str, Any]] = None
    main_eval: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class BatchEvalResponse(BaseModel):
    """배치 평가 응답"""
    results: List[EvalResult]
    total_rows: int
    success_count: int
    error_count: int
    avg_router_score: Optional[float] = None
    avg_main_score: Optional[float] = None
    avg_total_score: Optional[float] = None


# ============================================================
# Excel 업로드 API
# ============================================================

@router.post("/upload-excel")
async def upload_excel(file: UploadFile = File(...)):
    """
    Excel 파일 업로드 및 파싱
    
    컬럼: 이전대화, 사용자질문, Router출력, Function결과, 최종답변
    """
    try:
        import pandas as pd
        
        # 파일 읽기
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        
        # 컬럼 매핑
        column_map = {
            "이전대화": "history",
            "사용자질문": "question",
            "Router출력": "router_output",
            "Function결과": "function_result",
            "최종답변": "final_answer"
        }
        
        rows = []
        for idx, row in df.iterrows():
            row_data = {
                "row_index": idx,
                "history": str(row.get("이전대화", "")) if pd.notna(row.get("이전대화")) else "",
                "question": str(row.get("사용자질문", "")) if pd.notna(row.get("사용자질문")) else "",
                "router_output": str(row.get("Router출력", "")) if pd.notna(row.get("Router출력")) else "",
                "function_result": str(row.get("Function결과", "")) if pd.notna(row.get("Function결과")) else "",
                "final_answer": str(row.get("최종답변", "")) if pd.notna(row.get("최종답변")) else ""
            }
            rows.append(row_data)
        
        return {
            "success": True,
            "total_rows": len(rows),
            "columns": list(df.columns),
            "rows": rows
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Excel 파싱 오류: {str(e)}")


# ============================================================
# Router 평가 API
# ============================================================

@router.post("/router-evaluate", response_model=BatchEvalResponse)
async def router_evaluate(request: RouterEvalRequest):
    """
    Router 평가 (배치)
    
    입력: 이전대화, 사용자질문
    출력: Router 출력 생성 + 5점 평가
    """
    semaphore = asyncio.Semaphore(20)  # 최대 20개 병렬
    total = len(request.rows)
    completed = [0]  # mutable for closure
    
    async def process_row(row: ExcelRow) -> EvalResult:
        async with semaphore:
            try:
                # 1. Router 실행
                history_list = _parse_history(row.history)
                router_result = await route_query(row.question, history_list)
                router_output = json.dumps(router_result, ensure_ascii=False)
                
                # 2. Router 평가
                eval_result = await evaluate_router(
                    row.history,
                    row.question,
                    router_output
                )
                
                completed[0] += 1
                print(f"[Router] {completed[0]}/{total} 완료")
                
                return EvalResult(
                    row_index=row.row_index,
                    history=row.history,
                    question=row.question,
                    router_output=router_output,
                    function_result="",
                    final_answer="",
                    router_score=eval_result.get("score", 0),
                    router_eval=eval_result
                )
                
            except Exception as e:
                return EvalResult(
                    row_index=row.row_index,
                    history=row.history,
                    question=row.question,
                    router_output="",
                    function_result="",
                    final_answer="",
                    error=str(e)
                )
    
    # 병렬 처리
    tasks = [process_row(row) for row in request.rows]
    results = await asyncio.gather(*tasks)
    
    # 통계 계산
    success_results = [r for r in results if r.error is None]
    error_results = [r for r in results if r.error is not None]
    
    avg_router = None
    if success_results:
        scores = [r.router_score for r in success_results if r.router_score is not None]
        if scores:
            avg_router = sum(scores) / len(scores)
    
    return BatchEvalResponse(
        results=results,
        total_rows=len(results),
        success_count=len(success_results),
        error_count=len(error_results),
        avg_router_score=avg_router
    )


# ============================================================
# Main 평가 API
# ============================================================

@router.post("/main-evaluate", response_model=BatchEvalResponse)
async def main_evaluate(request: MainEvalRequest):
    """
    Main 평가 (배치)
    
    입력: 이전대화, 사용자질문, Router출력, Function결과
    출력: 최종답변 생성 + 5점 평가
    """
    semaphore = asyncio.Semaphore(20)
    total = len(request.rows)
    completed = [0]
    
    async def process_row(row: ExcelRow) -> EvalResult:
        async with semaphore:
            try:
                # 1. Function 결과 파싱
                function_results = {}
                if row.function_result:
                    try:
                        function_results = json.loads(row.function_result)
                    except json.JSONDecodeError:
                        pass
                
                # 2. Main Agent 실행
                history_list = _parse_history(row.history)
                main_result = await generate_response(
                    message=row.question,
                    history=history_list,
                    function_results=function_results
                )
                final_answer = main_result.get("response", "")
                
                # 3. Main 평가
                eval_result = await evaluate_main(
                    row.history,
                    row.question,
                    row.router_output,
                    row.function_result,
                    final_answer
                )
                
                completed[0] += 1
                print(f"[Main] {completed[0]}/{total} 완료")
                
                return EvalResult(
                    row_index=row.row_index,
                    history=row.history,
                    question=row.question,
                    router_output=row.router_output,
                    function_result=row.function_result,
                    final_answer=final_answer,
                    main_score=eval_result.get("score", 0),
                    main_eval=eval_result
                )
                
            except Exception as e:
                return EvalResult(
                    row_index=row.row_index,
                    history=row.history,
                    question=row.question,
                    router_output=row.router_output,
                    function_result=row.function_result,
                    final_answer="",
                    error=str(e)
                )
    
    tasks = [process_row(row) for row in request.rows]
    results = await asyncio.gather(*tasks)
    
    success_results = [r for r in results if r.error is None]
    error_results = [r for r in results if r.error is not None]
    
    avg_main = None
    if success_results:
        scores = [r.main_score for r in success_results if r.main_score is not None]
        if scores:
            avg_main = sum(scores) / len(scores)
    
    return BatchEvalResponse(
        results=results,
        total_rows=len(results),
        success_count=len(success_results),
        error_count=len(error_results),
        avg_main_score=avg_main
    )


# ============================================================
# Pipeline 평가 API
# ============================================================

@router.post("/pipeline-evaluate", response_model=BatchEvalResponse)
async def pipeline_evaluate(request: PipelineEvalRequest):
    """
    Pipeline 평가 (배치)
    
    입력: 이전대화, 사용자질문
    출력: Router → Function → Main 전체 실행 + 10점 평가
    """
    semaphore = asyncio.Semaphore(10)  # 병렬 처리 수 증가
    total = len(request.rows)
    completed = [0]
    
    async def process_row(row: ExcelRow) -> EvalResult:
        async with semaphore:
            try:
                history_list = _parse_history(row.history)
                
                # 1. Router 실행
                router_result = await route_query(row.question, history_list)
                router_output = json.dumps(router_result, ensure_ascii=False)
                
                # 2. Function 실행
                function_calls = router_result.get("function_calls", [])
                function_results = {}
                if function_calls:
                    function_results = await execute_function_calls(function_calls)
                function_result_str = json.dumps(function_results, ensure_ascii=False)
                
                # 3. Main Agent 실행
                main_result = await generate_response(
                    message=row.question,
                    history=history_list,
                    function_results=function_results
                )
                final_answer = main_result.get("response", "")
                
                # 4. Pipeline 평가 (Router + Main)
                eval_result = await evaluate_pipeline(
                    row.history,
                    row.question,
                    router_output,
                    function_result_str,
                    final_answer
                )
                
                completed[0] += 1
                print(f"[Pipeline] {completed[0]}/{total} 완료")
                
                return EvalResult(
                    row_index=row.row_index,
                    history=row.history,
                    question=row.question,
                    router_output=router_output,
                    function_result=function_result_str,
                    final_answer=final_answer,
                    router_score=eval_result.get("router_score", 0),
                    main_score=eval_result.get("main_score", 0),
                    total_score=eval_result.get("total_score", 0),
                    router_eval=eval_result.get("router_eval"),
                    main_eval=eval_result.get("main_eval")
                )
                
            except Exception as e:
                import traceback
                return EvalResult(
                    row_index=row.row_index,
                    history=row.history,
                    question=row.question,
                    router_output="",
                    function_result="",
                    final_answer="",
                    error=f"{str(e)}\n{traceback.format_exc()}"
                )
    
    tasks = [process_row(row) for row in request.rows]
    results = await asyncio.gather(*tasks)
    
    success_results = [r for r in results if r.error is None]
    error_results = [r for r in results if r.error is not None]
    
    avg_router = avg_main = avg_total = None
    if success_results:
        router_scores = [r.router_score for r in success_results if r.router_score is not None]
        main_scores = [r.main_score for r in success_results if r.main_score is not None]
        total_scores = [r.total_score for r in success_results if r.total_score is not None]
        
        if router_scores:
            avg_router = sum(router_scores) / len(router_scores)
        if main_scores:
            avg_main = sum(main_scores) / len(main_scores)
        if total_scores:
            avg_total = sum(total_scores) / len(total_scores)
    
    return BatchEvalResponse(
        results=results,
        total_rows=len(results),
        success_count=len(success_results),
        error_count=len(error_results),
        avg_router_score=avg_router,
        avg_main_score=avg_main,
        avg_total_score=avg_total
    )


# ============================================================
# Admin 평가 API (입력 데이터만 평가)
# ============================================================

@router.post("/admin-evaluate", response_model=BatchEvalResponse)
async def admin_evaluate(request: AdminEvalRequest):
    """
    Admin 평가 (배치)
    
    입력: 이전대화, 사용자질문, Router출력, Function결과, 최종답변 (모두 입력됨)
    출력: 10점 평가만 수행 (생성 없음)
    """
    semaphore = asyncio.Semaphore(20)  # 평가만 하므로 더 많이 병렬 처리
    total = len(request.rows)
    completed = [0]
    
    async def process_row(row: ExcelRow) -> EvalResult:
        async with semaphore:
            try:
                # Pipeline 평가 (생성 없이 평가만)
                eval_result = await evaluate_pipeline(
                    row.history,
                    row.question,
                    row.router_output,
                    row.function_result,
                    row.final_answer
                )
                
                completed[0] += 1
                print(f"[Admin] {completed[0]}/{total} 완료")
                
                return EvalResult(
                    row_index=row.row_index,
                    history=row.history,
                    question=row.question,
                    router_output=row.router_output,
                    function_result=row.function_result,
                    final_answer=row.final_answer,
                    router_score=eval_result.get("router_score", 0),
                    main_score=eval_result.get("main_score", 0),
                    total_score=eval_result.get("total_score", 0),
                    router_eval=eval_result.get("router_eval"),
                    main_eval=eval_result.get("main_eval")
                )
                
            except Exception as e:
                return EvalResult(
                    row_index=row.row_index,
                    history=row.history,
                    question=row.question,
                    router_output=row.router_output,
                    function_result=row.function_result,
                    final_answer=row.final_answer,
                    error=str(e)
                )
    
    tasks = [process_row(row) for row in request.rows]
    results = await asyncio.gather(*tasks)
    
    success_results = [r for r in results if r.error is None]
    error_results = [r for r in results if r.error is not None]
    
    avg_router = avg_main = avg_total = None
    if success_results:
        router_scores = [r.router_score for r in success_results if r.router_score is not None]
        main_scores = [r.main_score for r in success_results if r.main_score is not None]
        total_scores = [r.total_score for r in success_results if r.total_score is not None]
        
        if router_scores:
            avg_router = sum(router_scores) / len(router_scores)
        if main_scores:
            avg_main = sum(main_scores) / len(main_scores)
        if total_scores:
            avg_total = sum(total_scores) / len(total_scores)
    
    return BatchEvalResponse(
        results=results,
        total_rows=len(results),
        success_count=len(success_results),
        error_count=len(error_results),
        avg_router_score=avg_router,
        avg_main_score=avg_main,
        avg_total_score=avg_total
    )


# ============================================================
# Excel 내보내기 API
# ============================================================

class ExportRequest(BaseModel):
    """내보내기 요청"""
    results: List[EvalResult]
    eval_type: str  # "router", "main", "pipeline", "admin"


@router.post("/export-excel")
async def export_excel(request: ExportRequest):
    """
    평가 결과 Excel 내보내기
    """
    try:
        import pandas as pd
        
        rows = []
        for r in request.results:
            row = {
                "행번호": r.row_index + 1,
                "이전대화": _truncate(r.history, 32000),
                "사용자질문": _truncate(r.question, 32000),
                "Router출력": _truncate(r.router_output, 32000),
            }
            
            if request.eval_type in ["main", "pipeline", "admin"]:
                row["Function결과"] = _truncate(r.function_result, 32000)
                row["최종답변"] = _truncate(r.final_answer, 32000)
            
            if request.eval_type == "router":
                row["점수(5)"] = r.router_score
                if r.router_eval:
                    row["의도파악"] = "O" if r.router_eval.get("intent_understanding") else "X"
                    row["함수선택"] = "O" if r.router_eval.get("function_selection") else "X"
                    row["쿼리변수"] = "O" if r.router_eval.get("query_params") else "X"
                    row["JSON형식"] = "O" if r.router_eval.get("json_format") else "X"
                    row["성적환산"] = "O" if r.router_eval.get("score_conversion") else "X"
                    row["코멘트"] = r.router_eval.get("comment", "")
            
            elif request.eval_type == "main":
                row["점수(5)"] = r.main_score
                if r.main_eval:
                    row["답변적절"] = "O" if r.main_eval.get("answer_relevance") else "X"
                    row["자료기반"] = "O" if r.main_eval.get("source_based") else "X"
                    row["출력형식"] = "O" if r.main_eval.get("output_format") else "X"
                    row["인용정확"] = "O" if r.main_eval.get("citation_accuracy") else "X"
                    row["혼동없음"] = "O" if r.main_eval.get("no_confusion") else "X"
                    row["코멘트"] = r.main_eval.get("comment", "")
            
            elif request.eval_type in ["pipeline", "admin"]:
                row["총점(10)"] = r.total_score
                row["Router점수(5)"] = r.router_score
                row["Main점수(5)"] = r.main_score
                
                if r.router_eval:
                    row["R_의도파악"] = "O" if r.router_eval.get("intent_understanding") else "X"
                    row["R_함수선택"] = "O" if r.router_eval.get("function_selection") else "X"
                    row["R_쿼리변수"] = "O" if r.router_eval.get("query_params") else "X"
                    row["R_JSON형식"] = "O" if r.router_eval.get("json_format") else "X"
                    row["R_성적환산"] = "O" if r.router_eval.get("score_conversion") else "X"
                
                if r.main_eval:
                    row["M_답변적절"] = "O" if r.main_eval.get("answer_relevance") else "X"
                    row["M_자료기반"] = "O" if r.main_eval.get("source_based") else "X"
                    row["M_출력형식"] = "O" if r.main_eval.get("output_format") else "X"
                    row["M_인용정확"] = "O" if r.main_eval.get("citation_accuracy") else "X"
                    row["M_혼동없음"] = "O" if r.main_eval.get("no_confusion") else "X"
            
            if r.error:
                row["오류"] = r.error
            
            rows.append(row)
        
        df = pd.DataFrame(rows)
        
        # Excel 파일 생성
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='평가결과')
        output.seek(0)
        
        filename = f"eval_{request.eval_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Excel 생성 오류: {str(e)}")


# ============================================================
# Google Sheets 내보내기 (CSV 다운로드)
# ============================================================

@router.post("/export-csv")
async def export_csv(request: ExportRequest):
    """
    평가 결과 CSV 내보내기 (Google Sheets 업로드용)
    """
    try:
        import pandas as pd
        
        rows = []
        for r in request.results:
            row = {
                "행번호": r.row_index + 1,
                "이전대화": r.history[:1000] if r.history else "",
                "사용자질문": r.question[:1000] if r.question else "",
                "Router출력": r.router_output[:1000] if r.router_output else "",
            }
            
            if request.eval_type in ["main", "pipeline", "admin"]:
                row["Function결과"] = r.function_result[:1000] if r.function_result else ""
                row["최종답변"] = r.final_answer[:1000] if r.final_answer else ""
            
            if request.eval_type == "router":
                row["점수"] = r.router_score
            elif request.eval_type == "main":
                row["점수"] = r.main_score
            else:
                row["총점"] = r.total_score
                row["Router점수"] = r.router_score
                row["Main점수"] = r.main_score
            
            rows.append(row)
        
        df = pd.DataFrame(rows)
        
        output = io.StringIO()
        df.to_csv(output, index=False, encoding='utf-8-sig')
        output.seek(0)
        
        filename = f"eval_{request.eval_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CSV 생성 오류: {str(e)}")


# ============================================================
# 유틸리티 함수
# ============================================================

def _parse_history(history_str: str) -> List[Dict[str, str]]:
    """
    이전 대화 문자열을 히스토리 리스트로 변환
    
    형식: "User: 질문1\nBot: 답변1\nUser: 질문2\nBot: 답변2"
    """
    if not history_str:
        return []
    
    history = []
    lines = history_str.strip().split('\n')
    
    current_role = None
    current_content = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if line.startswith("User:") or line.startswith("사용자:"):
            if current_role and current_content:
                history.append({
                    "role": current_role,
                    "content": "\n".join(current_content)
                })
            current_role = "user"
            content = line.split(":", 1)[1].strip() if ":" in line else ""
            current_content = [content] if content else []
        
        elif line.startswith("Bot:") or line.startswith("Assistant:") or line.startswith("봇:"):
            if current_role and current_content:
                history.append({
                    "role": current_role,
                    "content": "\n".join(current_content)
                })
            current_role = "assistant"
            content = line.split(":", 1)[1].strip() if ":" in line else ""
            current_content = [content] if content else []
        
        else:
            current_content.append(line)
    
    if current_role and current_content:
        history.append({
            "role": current_role,
            "content": "\n".join(current_content)
        })
    
    return history


def _truncate(text: str, max_length: int = 32000) -> str:
    """텍스트 길이 제한 (Excel 셀 제한)"""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "\n...[잘림]"
