"""
Google Gemini AI 통합 서비스
"""
import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool, content_types
from config import settings
from config.constants import GEMINI_FLASH_MODEL, GEMINI_LITE_MODEL
from config.logging_config import setup_logger
from typing import Optional, List, Dict, Any
import asyncio
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from utils.token_logger import log_token_usage

logger = setup_logger('gemini')


class GeminiService:
    """Gemini API 싱글톤 서비스"""

    _instance: Optional['GeminiService'] = None

    def __init__(self):
        """Gemini 초기화"""
        try:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.model = genai.GenerativeModel(GEMINI_FLASH_MODEL)
            self.lite_model = genai.GenerativeModel(GEMINI_LITE_MODEL)
            logger.info(f"Gemini 초기화 완료: {GEMINI_FLASH_MODEL} (대화), {GEMINI_LITE_MODEL} (문서처리)")
        except Exception as e:
            logger.error(f"Gemini 초기화 실패: {e}")
            raise

    @classmethod
    def get_instance(cls) -> 'GeminiService':
        """싱글톤 인스턴스 반환"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def generate(self, prompt: str, system_instruction: str = "", timing_logger=None, agent_name: str = None) -> str:
        """
        Gemini로 텍스트 생성 (Retry 로직 포함)

        Args:
            prompt: 프롬프트
            system_instruction: 시스템 지시사항 (선택)
            timing_logger: 타이밍 로거 (선택)
            agent_name: Agent 이름 (선택, timing_logger와 함께 사용)

        Returns:
            생성된 텍스트

        Raises:
            Exception: 생성 실패 시
        """
        max_retries = 3
        retry_delays = [2, 4, 8]  # Exponential backoff
        
        for attempt in range(max_retries):
            try:
                # 프롬프트 준비
                full_prompt = f"{system_instruction}\n\n{prompt}" if system_instruction else prompt
                
                if timing_logger and agent_name:
                    timing_logger.mark_agent(agent_name, "llm_prompt_ready")

                # request_options로 retry 비활성화 (직접 제어)
                request_options = genai.types.RequestOptions(
                    retry=None,
                    timeout=120.0  # 멀티에이전트 파이프라인을 위해 120초로 증가
                )
                
                if timing_logger and agent_name:
                    timing_logger.mark_agent(agent_name, "llm_api_sent")

                response = self.model.generate_content(full_prompt, request_options=request_options)
                
                if timing_logger and agent_name:
                    timing_logger.mark_agent(agent_name, "llm_api_received")

                # 토큰 사용량 기록
                if hasattr(response, 'usage_metadata'):
                    usage = response.usage_metadata
                    prompt_tokens = getattr(usage, 'prompt_token_count', 0)
                    output_tokens = getattr(usage, 'candidates_token_count', 0)
                    total_tokens = getattr(usage, 'total_token_count', 0)
                    
                    print(f"💰 토큰 사용량 (generate): {usage}")
                    logger.info(f"💰 토큰 사용량 - "
                              f"입력: {prompt_tokens}, "
                              f"출력: {output_tokens}, "
                              f"총합: {total_tokens}")
                    
                    # CSV에 기록
                    log_token_usage(
                        operation="텍스트생성",
                        prompt_tokens=prompt_tokens,
                        output_tokens=output_tokens,
                        total_tokens=total_tokens,
                        model=GEMINI_FLASH_MODEL,
                        details=""
                    )

                # 빈 응답 체크
                if not response.candidates or len(response.candidates) == 0:
                    logger.warning("Gemini generate: candidates가 없습니다")
                    return ""

                candidate = response.candidates[0]
                if not candidate.content or not candidate.content.parts or len(candidate.content.parts) == 0:
                    finish_reason = getattr(candidate, 'finish_reason', None)
                    logger.warning(f"Gemini generate: content.parts가 없습니다. finish_reason={finish_reason}")
                    return ""

                # 파싱 완료
                result = response.text.strip()
                
                if timing_logger and agent_name:
                    timing_logger.mark_agent(agent_name, "llm_parsed")
                
                return result
                
            except Exception as e:
                error_msg = str(e)
                
                # 503, 429 에러는 재시도
                if ("503" in error_msg or "429" in error_msg or "overloaded" in error_msg.lower() or "rate limit" in error_msg.lower()):
                    if attempt < max_retries - 1:
                        delay = retry_delays[attempt]
                        logger.warning(f"Gemini Rate Limit/Overload (시도 {attempt + 1}/{max_retries}) → {delay}초 후 재시도: {error_msg}")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.error(f"Gemini 최대 재시도 초과: {error_msg}")
                        raise
                else:
                    # 다른 에러는 즉시 raise
                    logger.error(f"Gemini 생성 오류: {e}")
                    raise
        
        raise Exception("Gemini generate 최대 재시도 초과")

    async def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[FunctionDeclaration],
        system_instruction: str = ""
    ) -> Dict[str, Any]:
        """
        Tool을 사용한 Gemini 대화 (Retry 로직 포함)

        Args:
            messages: 대화 히스토리 [{"role": "user/model", "parts": ["text"]}]
            tools: 사용 가능한 도구 목록
            system_instruction: 시스템 지시사항

        Returns:
            {
                "type": "text" | "function_call",
                "content": str (if text),
                "function_call": {"name": str, "args": dict} (if function_call),
                "raw_response": response (원본 응답)
            }
        """
        max_api_retries = 3
        retry_delays = [2, 4, 8]  # Exponential backoff
        
        for api_attempt in range(max_api_retries):
            try:
                # Tool 래핑
                tool_wrapper = Tool(function_declarations=tools)

                # 시스템 인스트럭션이 있는 모델 생성
                generation_config = {
                    "temperature": 0.7,
                    "top_p": 0.95,
                    "top_k": 40,
                    "max_output_tokens": 2048,
                }

                model = genai.GenerativeModel(
                    GEMINI_FLASH_MODEL,
                    tools=[tool_wrapper],
                    system_instruction=system_instruction if system_instruction else None,
                    generation_config=generation_config
                )

                # 대화 세션 시작
                chat = model.start_chat(history=messages[:-1] if len(messages) > 1 else [])

                # 마지막 메시지 전송 (retry 제거, timeout 설정)
                last_message = messages[-1]["parts"][0]

                # request_options로 retry 비활성화
                request_options = genai.types.RequestOptions(
                    retry=None,  # retry 비활성화
                    timeout=120.0  # 멀티에이전트 파이프라인을 위해 120초로 증가
                )

                # 빈 응답 재시도 로직 (최대 3회)
                max_retries = 3
                for attempt in range(max_retries):
                    if attempt > 0:
                        logger.info(f"빈 응답 재시도 중... ({attempt}/{max_retries})")
                        await asyncio.sleep(0.5)  # 짧은 대기

                    response = chat.send_message(last_message, request_options=request_options)

                    # 토큰 사용량 기록
                    if hasattr(response, 'usage_metadata'):
                        usage = response.usage_metadata
                        prompt_tokens = getattr(usage, 'prompt_token_count', 0)
                        output_tokens = getattr(usage, 'candidates_token_count', 0)
                        total_tokens = getattr(usage, 'total_token_count', 0)
                        
                        print(f"💰 토큰 사용량 (chat_with_tools): {usage}")
                        logger.info(f"💰 토큰 사용량 - "
                                  f"입력: {prompt_tokens}, "
                                  f"출력: {output_tokens}, "
                                  f"총합: {total_tokens}")
                        
                        # CSV에 기록
                        log_token_usage(
                            operation="대화생성(Tools)",
                            prompt_tokens=prompt_tokens,
                            output_tokens=output_tokens,
                            total_tokens=total_tokens,
                            model=GEMINI_FLASH_MODEL,
                            details=""
                        )

                    # 전체 응답 디버깅
                    logger.info(f"Gemini 전체 응답 (시도 {attempt + 1}): {response}")
                    if hasattr(response, 'prompt_feedback'):
                        logger.info(f"Gemini prompt_feedback: {response.prompt_feedback}")

                    # 응답 파싱 - 빈 응답 체크
                    if not response.candidates or len(response.candidates) == 0:
                        logger.warning(f"Gemini 응답에 candidates가 없습니다 (시도 {attempt + 1}/{max_retries})")
                        if attempt < max_retries - 1:
                            continue  # 재시도
                        return {
                            "type": "text",
                            "content": "죄송합니다. AI가 응답을 생성하지 못했습니다. 다시 시도해주세요.",
                            "raw_response": response
                        }

                    candidate = response.candidates[0]

                    # finish_reason 확인 (디버깅)
                    finish_reason = getattr(candidate, 'finish_reason', None)
                    logger.info(f"Gemini finish_reason: {finish_reason}")

                    if not candidate.content or not candidate.content.parts or len(candidate.content.parts) == 0:
                        # 왜 빈 응답인지 상세 로깅
                        safety_ratings = getattr(candidate, 'safety_ratings', [])
                        logger.warning(f"Gemini 응답에 content.parts가 없습니다. finish_reason={finish_reason}, safety_ratings={safety_ratings} (시도 {attempt + 1}/{max_retries})")

                        # SAFETY나 RECITATION으로 차단된 경우 - 재시도 없이 즉시 반환
                        if finish_reason and ('SAFETY' in str(finish_reason) or 'RECITATION' in str(finish_reason)):
                            logger.info(f"안전 필터링으로 차단됨 ({finish_reason}), 재시도하지 않음")
                            return {
                                "type": "text",
                                "content": "죄송합니다. 해당 질문에 대한 답변을 생성할 수 없습니다. 다른 방식으로 질문해주세요.",
                                "raw_response": response
                            }

                        # 빈 응답이지만 재시도 가능한 경우
                        if attempt < max_retries - 1:
                            continue  # 재시도

                        # 최종 실패 - 기본 메시지 반환
                        return {
                            "type": "text",
                            "content": "죄송합니다. AI가 응답을 생성하지 못했습니다. 다시 시도해주세요.",
                            "raw_response": response
                        }

                    # 정상 응답 수신 - 파싱
                    first_part = candidate.content.parts[0]
                    if hasattr(first_part, 'function_call') and first_part.function_call and first_part.function_call.name:
                        # Function Call 발생
                        fc = first_part.function_call
                        return {
                            "type": "function_call",
                            "function_call": {
                                "name": fc.name,
                                "args": dict(fc.args)
                            },
                            "raw_response": response  # 원본 응답 포함
                        }
                    else:
                        # 일반 텍스트 응답
                        return {
                            "type": "text",
                            "content": response.text.strip(),
                            "raw_response": response
                        }

                # 이론적으로 여기까지 도달하지 않지만 안전장치
                return {
                    "type": "text",
                    "content": "죄송합니다. AI가 응답을 생성하지 못했습니다. 다시 시도해주세요.",
                    "raw_response": None
                }

            except Exception as e:
                error_msg = str(e)
                
                # 503, 429 에러는 재시도
                if ("503" in error_msg or "429" in error_msg or "overloaded" in error_msg.lower() or "rate limit" in error_msg.lower()):
                    if api_attempt < max_api_retries - 1:
                        delay = retry_delays[api_attempt]
                        logger.warning(f"Gemini Rate Limit/Overload (시도 {api_attempt + 1}/{max_api_retries}) → {delay}초 후 재시도: {error_msg}")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.error(f"Gemini 최대 재시도 초과: {error_msg}")
                        raise
                else:
                    # 다른 에러는 즉시 raise
                    logger.error(f"Gemini chat_with_tools 오류: {e}")
                    raise
        
        raise Exception("Gemini chat_with_tools 최대 재시도 초과")

    async def extract_info_from_documents(
        self,
        query: str,
        documents: str,
        system_instruction: str = ""
    ) -> str:
        """
        Lite 모델로 대용량 문서에서 정보 추출 (빠른 처리, Retry 포함)

        Args:
            query: 검색 쿼리
            documents: 전체 문서 내용
            system_instruction: 시스템 지시사항

        Returns:
            추출된 정보 (요약/핵심 내용)
        """
        max_retries = 3
        retry_delays = [2, 4, 8]
        
        for attempt in range(max_retries):
            try:
                prompt = f"""다음 문서에서 '{query}'에 대한 핵심 정보를 추출해주세요.

문서:
{documents}

요구사항:
- 질문과 관련된 정보만 정확하게 추출
- 불필요한 내용은 제외
- 원문의 표현을 최대한 유지
- 간결하게 정리 (1000자 이내)

추출된 정보:"""

                if system_instruction:
                    full_prompt = f"{system_instruction}\n\n{prompt}"
                else:
                    full_prompt = prompt

                request_options = genai.types.RequestOptions(
                    retry=None,
                    timeout=120.0  # 대용량 문서 처리를 위해 120초로 증가
                )

                # Lite 모델로 빠르게 처리
                response = self.lite_model.generate_content(full_prompt, request_options=request_options)
                
                # 토큰 사용량 기록
                if hasattr(response, 'usage_metadata'):
                    usage = response.usage_metadata
                    prompt_tokens = getattr(usage, 'prompt_token_count', 0)
                    output_tokens = getattr(usage, 'candidates_token_count', 0)
                    total_tokens = getattr(usage, 'total_token_count', 0)
                    
                    print(f"💰 토큰 사용량 (extract_info): {usage}")
                    logger.info(f"💰 토큰 사용량 - "
                              f"입력: {prompt_tokens}, "
                              f"출력: {output_tokens}, "
                              f"총합: {total_tokens}")
                    
                    # CSV에 기록
                    log_token_usage(
                        operation="문서정보추출",
                        prompt_tokens=prompt_tokens,
                        output_tokens=output_tokens,
                        total_tokens=total_tokens,
                        model=GEMINI_LITE_MODEL,
                        details=""
                    )
                
                return response.text.strip()
                
            except Exception as e:
                error_msg = str(e)
                
                # 503, 429 에러는 재시도
                if ("503" in error_msg or "429" in error_msg or "overloaded" in error_msg.lower() or "rate limit" in error_msg.lower()):
                    if attempt < max_retries - 1:
                        delay = retry_delays[attempt]
                        logger.warning(f"문서 추출 Rate Limit (시도 {attempt + 1}/{max_retries}) → {delay}초 후 재시도: {error_msg}")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.error(f"문서 추출 최대 재시도 초과: {error_msg}")
                        raise
                else:
                    # 다른 에러는 즉시 raise
                    logger.error(f"Gemini extract_info_from_documents 오류: {e}")
                    raise
        
        raise Exception("문서 정보 추출 최대 재시도 초과")


# 전역 인스턴스
gemini_service = GeminiService.get_instance()
