"""
Admin Logs Router
- 실행 로그 CRUD API
- Supabase에 저장/조회
"""

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import random
import string
from datetime import datetime

from services.supabase_client import supabase_service
from utils.admin_filter import should_skip_logging

router = APIRouter()


def generate_short_id(length: int = 6) -> str:
    """6자리 랜덤 ID 생성 (영문 대문자 + 숫자)"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=length))


class TimingInfo(BaseModel):
    router: int = 0
    function: int = 0
    main_agent: int = 0


class EvaluationInfo(BaseModel):
    routerStatus: str = 'pending'
    functionStatus: str = 'pending'
    answerStatus: str = 'pending'
    timeStatus: str = 'pending'
    routerComment: Optional[str] = None
    functionComment: Optional[str] = None
    answerComment: Optional[str] = None
    timeComment: Optional[str] = None


class CreateLogRequest(BaseModel):
    conversationHistory: List[str] = []
    userQuestion: str
    routerOutput: Optional[Any] = None
    functionResult: Optional[Any] = None
    finalAnswer: Optional[str] = None
    elapsedTime: int = 0
    timing: Optional[TimingInfo] = None
    userId: Optional[str] = None
    entryUrl: Optional[str] = None  # 진입한 랜딩 페이지 URL


class UpdateEvaluationRequest(BaseModel):
    routerStatus: Optional[str] = None
    functionStatus: Optional[str] = None
    answerStatus: Optional[str] = None
    timeStatus: Optional[str] = None
    routerComment: Optional[str] = None
    functionComment: Optional[str] = None
    answerComment: Optional[str] = None
    timeComment: Optional[str] = None


class LogResponse(BaseModel):
    id: str
    userId: Optional[str] = None
    timestamp: str
    conversationHistory: List[str]
    userQuestion: str
    routerOutput: Optional[Any] = None
    functionResult: Optional[Any] = None
    finalAnswer: Optional[str] = None
    elapsedTime: int
    entryUrl: Optional[str] = None
    timing: Optional[TimingInfo] = None
    evaluation: Optional[EvaluationInfo] = None


@router.get("/logs")
async def get_logs(limit: int = 500, offset: int = 0):
    """모든 로그 조회 (최신순). Excel 내보내기 시 limit=10000 등으로 요청 가능."""
    limit = min(max(1, limit), 10000)  # 1~10000 허용
    try:
        result = supabase_service.client.table('admin_logs') \
            .select('*') \
            .order('timestamp', desc=True) \
            .range(offset, offset + limit - 1) \
            .execute()
        
        logs = []
        for row in result.data:
            logs.append({
                'id': row['id'],
                'userId': row.get('user_id'),
                'timestamp': row['timestamp'],
                'conversationHistory': row.get('conversation_history', []),
                'userQuestion': row['user_question'],
                'routerOutput': row.get('router_output'),
                'functionResult': row.get('function_result'),
                'finalAnswer': row.get('final_answer'),
                'elapsedTime': row.get('elapsed_time', 0),
                'entryUrl': row.get('진입_url'),
                'timing': {
                    'router': row.get('timing_router', 0),
                    'function': row.get('timing_function', 0),
                    'main_agent': row.get('timing_main_agent', 0)
                },
                'evaluation': {
                    'routerStatus': row.get('eval_router_status', 'pending'),
                    'functionStatus': row.get('eval_function_status', 'pending'),
                    'answerStatus': row.get('eval_answer_status', 'pending'),
                    'timeStatus': row.get('eval_time_status', 'pending'),
                    'routerComment': row.get('eval_router_comment'),
                    'functionComment': row.get('eval_function_comment'),
                    'answerComment': row.get('eval_answer_comment'),
                    'timeComment': row.get('eval_time_comment')
                }
            })
        
        return {'logs': logs, 'total': len(logs)}
    
    except Exception as e:
        print(f"❌ 로그 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs/by-user")
async def get_logs_by_user(limit: int = 2000):
    """
    admin_logs를 user_id별로 묶어서 반환 (유저별 질문·답변 내역)
    - user_id가 null이면 비로그인 사용자
    """
    try:
        result = supabase_service.client.table('admin_logs') \
            .select('id, user_id, timestamp, user_question, final_answer') \
            .order('timestamp', desc=True) \
            .limit(limit) \
            .execute()
        
        # user_id별로 그룹화 (None → 'guest' 키로)
        by_user: Dict[str, List[Dict[str, Any]]] = {}
        for row in result.data or []:
            uid = row.get('user_id')
            key = str(uid) if uid else '__guest__'
            if key not in by_user:
                by_user[key] = []
            by_user[key].append({
                'id': row['id'],
                'timestamp': row.get('timestamp'),
                'userQuestion': row.get('user_question', ''),
                'finalAnswer': row.get('final_answer') or '',
            })
        
        # 리스트 형태로 반환 (비로그인 먼저, 그 다음 user_id 순)
        users = []
        if '__guest__' in by_user:
            users.append({
                'userId': None,
                'label': '비로그인',
                'logs': by_user['__guest__'],
                'count': len(by_user['__guest__']),
            })
        for uid, logs in by_user.items():
            if uid == '__guest__':
                continue
            users.append({
                'userId': uid,
                'label': uid[:8] + '…' if len(uid) > 8 else uid,
                'logs': logs,
                'count': len(logs),
            })
        
        return {'users': users, 'totalLogs': sum(len(u['logs']) for u in users)}
    
    except Exception as e:
        print(f"❌ 유저별 로그 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/logs")
async def create_log(request: CreateLogRequest):
    """새 로그 생성"""
    try:
        # 관리자 계정 확인 (로깅 제외)
        if should_skip_logging(user_id=request.userId):
            print(f"⏭️ 관리자 계정 - 로그 저장 건너뜀 (user_id: {request.userId})")
            return {
                'id': 'ADMIN_SKIPPED',
                'message': '관리자 계정은 로깅되지 않습니다.'
            }
        
        # 6자리 고유 ID 생성 (중복 체크)
        max_attempts = 10
        log_id = None
        for _ in range(max_attempts):
            candidate_id = generate_short_id(6)
            # 중복 체크
            existing = supabase_service.client.table('admin_logs') \
                .select('id') \
                .eq('id', candidate_id) \
                .execute()
            if len(existing.data) == 0:
                log_id = candidate_id
                break
        
        if not log_id:
            raise HTTPException(status_code=500, detail="ID 생성 실패")

        # 데이터 준비 (필수 컬럼만)
        data = {
            'id': log_id,
            'user_id': request.userId if request.userId else None,
            'conversation_history': request.conversationHistory,
            'user_question': request.userQuestion,
            'router_output': request.routerOutput,
            'function_result': request.functionResult,
            'final_answer': request.finalAnswer,
            'elapsed_time': request.elapsedTime,
            'timing_router': request.timing.router if request.timing else 0,
            'timing_function': request.timing.function if request.timing else 0,
            'timing_main_agent': request.timing.main_agent if request.timing else 0,
            'eval_router_status': 'pending',
            'eval_function_status': 'pending',
            'eval_answer_status': 'pending',
            'eval_time_status': 'pending',
            '진입_url': request.entryUrl,
        }

        # is_same_person: 컬럼이 있으면 설정 (없으면 제외하고 저장해 로그 유실 방지)
        try:
            if request.userId:
                prev = supabase_service.client.table('admin_logs') \
                    .select('id') \
                    .eq('user_id', request.userId) \
                    .limit(1) \
                    .execute()
                if prev.data and len(prev.data) > 0:
                    data['is_same_person'] = request.userId
                else:
                    data['is_same_person'] = None
        except Exception:
            pass  # is_same_person 조회 실패해도 로그 저장은 진행

        try:
            result = supabase_service.client.table('admin_logs').insert(data).execute()
        except Exception as insert_err:
            # is_same_person 컬럼 없음 등으로 실패 시 해당 필드 제거 후 재시도
            if 'is_same_person' in data:
                data.pop('is_same_person', None)
                result = supabase_service.client.table('admin_logs').insert(data).execute()
            else:
                raise insert_err

        if not result.data:
            raise HTTPException(status_code=500, detail="로그 저장 실패")
        
        row = result.data[0]
        return {
            'id': row['id'],
            'userId': row.get('user_id'),
            'timestamp': row['timestamp'],
            'conversationHistory': row.get('conversation_history', []),
            'userQuestion': row['user_question'],
            'routerOutput': row.get('router_output'),
            'functionResult': row.get('function_result'),
            'finalAnswer': row.get('final_answer'),
            'elapsedTime': row.get('elapsed_time', 0),
            'entryUrl': row.get('진입_url'),
            'timing': {
                'router': row.get('timing_router', 0),
                'function': row.get('timing_function', 0),
                'main_agent': row.get('timing_main_agent', 0)
            },
            'evaluation': {
                'routerStatus': 'pending',
                'functionStatus': 'pending',
                'answerStatus': 'pending',
                'timeStatus': 'pending'
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 로그 생성 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/logs/{log_id}/evaluation")
async def update_evaluation(log_id: str, request: UpdateEvaluationRequest):
    """로그 평가 결과 업데이트"""
    try:
        update_data = {}
        
        if request.routerStatus is not None:
            update_data['eval_router_status'] = request.routerStatus
        if request.functionStatus is not None:
            update_data['eval_function_status'] = request.functionStatus
        if request.answerStatus is not None:
            update_data['eval_answer_status'] = request.answerStatus
        if request.timeStatus is not None:
            update_data['eval_time_status'] = request.timeStatus
        if request.routerComment is not None:
            update_data['eval_router_comment'] = request.routerComment
        if request.functionComment is not None:
            update_data['eval_function_comment'] = request.functionComment
        if request.answerComment is not None:
            update_data['eval_answer_comment'] = request.answerComment
        if request.timeComment is not None:
            update_data['eval_time_comment'] = request.timeComment
        
        if not update_data:
            return {'status': 'no changes'}
        
        result = supabase_service.client.table('admin_logs') \
            .update(update_data) \
            .eq('id', log_id) \
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="로그를 찾을 수 없습니다")
        
        return {'status': 'success', 'id': log_id}
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 평가 업데이트 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/logs/{log_id}")
async def delete_log(log_id: str):
    """로그 삭제"""
    try:
        result = supabase_service.client.table('admin_logs') \
            .delete() \
            .eq('id', log_id) \
            .execute()
        
        return {'status': 'success', 'id': log_id}
    
    except Exception as e:
        print(f"❌ 로그 삭제 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/logs")
async def delete_all_logs():
    """모든 로그 삭제"""
    try:
        # 모든 로그 삭제 (id가 빈 문자열이 아닌 모든 행)
        result = supabase_service.client.table('admin_logs') \
            .delete() \
            .neq('id', '') \
            .execute()
        
        return {'status': 'success', 'deleted': len(result.data) if result.data else 0}
    
    except Exception as e:
        print(f"❌ 전체 로그 삭제 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/logs/migrate")
async def migrate_logs(logs: List[Dict[str, Any]]):
    """기존 localStorage 로그를 Supabase로 마이그레이션"""
    try:
        migrated = 0
        errors = []
        
        for log in logs:
            try:
                # 기존 ID에서 6자리 추출 또는 새로 생성
                old_id = log.get('id', '')
                # 기존 형식: log-1769752851504-abc123def
                # 타임스탬프 뒷자리 6자리 사용
                if old_id.startswith('log-') and len(old_id) > 10:
                    parts = old_id.split('-')
                    if len(parts) >= 2:
                        timestamp_part = parts[1]
                        new_id = timestamp_part[-6:] if len(timestamp_part) >= 6 else generate_short_id(6)
                    else:
                        new_id = generate_short_id(6)
                else:
                    new_id = generate_short_id(6)
                
                # 중복 체크 및 새 ID 생성
                existing = supabase_service.client.table('admin_logs') \
                    .select('id') \
                    .eq('id', new_id) \
                    .execute()
                if len(existing.data) > 0:
                    new_id = generate_short_id(6)
                
                timing = log.get('timing', {})
                evaluation = log.get('evaluation', {})
                
                data = {
                    'id': new_id,
                    'user_id': log.get('userId'),
                    'timestamp': log.get('timestamp', datetime.now().isoformat()),
                    'conversation_history': log.get('conversationHistory', []),
                    'user_question': log.get('userQuestion', ''),
                    'router_output': log.get('routerOutput'),
                    'function_result': log.get('functionResult'),
                    'final_answer': log.get('finalAnswer'),
                    'elapsed_time': log.get('elapsedTime', 0),
                    'timing_router': timing.get('router', 0),
                    'timing_function': timing.get('function', 0),
                    'timing_main_agent': timing.get('main_agent', 0),
                    'eval_router_status': evaluation.get('routerStatus', 'pending'),
                    'eval_function_status': evaluation.get('functionStatus', 'pending'),
                    'eval_answer_status': evaluation.get('answerStatus', 'pending'),
                    'eval_time_status': evaluation.get('timeStatus', 'pending'),
                    'eval_router_comment': evaluation.get('routerComment'),
                    'eval_function_comment': evaluation.get('functionComment'),
                    'eval_answer_comment': evaluation.get('answerComment'),
                    'eval_time_comment': evaluation.get('timeComment')
                }
                
                supabase_service.client.table('admin_logs').insert(data).execute()
                migrated += 1
                
            except Exception as e:
                errors.append({'id': log.get('id'), 'error': str(e)})
        
        return {
            'status': 'success',
            'migrated': migrated,
            'total': len(logs),
            'errors': errors[:10]  # 최대 10개 에러만 반환
        }
    
    except Exception as e:
        print(f"❌ 마이그레이션 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))
