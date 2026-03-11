"""
Summary Agent
- 채팅 공유 시 핵심 요약 생성
- Model: Gemini (router_agent와 동일)
"""

import os
import re
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Gemini API 설정
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Gemini 모델 초기화
model = None
try:
    model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')
    print("[Summary Agent] Gemini 모델 초기화 완료 (gemini-3.1-flash-lite-preview)")
except Exception as e:
    print(f"[Summary Agent] Gemini 모델 초기화 실패: {e}")
    model = None


SUMMARY_SYSTEM_PROMPT = """당신은 입시 상담의 핵심 내용을 요약하는 에이전트입니다.

사용자의 질문에 대해 당신이 요약한 '핵심 내용'과 완전한 답변이 포함된 링크가 전송됩니다.

주어진 질문과 답변을 읽고, 사용자가 즉각적으로 핵심을 파악할 수 있도록 3-5줄로 요약해주세요.

## 요약 규칙
1. 첫 줄: 사용자의 상황을 포함하여 답변의 핵심 내용 및 판단 전달(해요체)
2. 나머지: 답변의 핵심 포인트를 글머리 기호(•)로 정리
3. 구체적인 대학명, 학과명, 점수, 전형명 등은 반드시 포함. 수치가 있다면 객관적인 수치 위주로 설명
4. 불필요한 인사말, 격려 문구는 제외
5. 마크다운 문법 사용 금지 (**, ## 등)
6. 총 5줄 이내로 작성

## 출력 예시
내신 2.4등급의 일반고 학생이라면 주로 학생부교과 전형으로 안정적인 합격을 노리는 것이 유리해요.
• 충남대학교: 수학교육과(2.31), 응용화학공학과(2.33), 경영학부(2.5) 적정
• 용인대학교: 경영학과(2.3), 문화콘텐츠학과(2.3), 바이오생명공학과(2.3) 적정
• 전남대학교: 수학교육과(2.329), 행정학과(2.531), 심리학과(2.548) 적정"""


async def generate_summary(user_query: str, assistant_response: str) -> str:
    """
    질문과 답변을 받아 핵심 요약 생성
    
    Args:
        user_query: 사용자 질문
        assistant_response: AI 답변
        
    Returns:
        요약된 텍스트 (3-5줄)
    """
    if not model:
        return "요약을 생성할 수 없습니다. (Gemini 연결 실패)"
    
    try:
        # 답변에서 마크다운/태그 정리
        cleaned_response = assistant_response
        # 섹션 마커 제거
        cleaned_response = re.sub(r'===SECTION_(START|END)(:\w+)?===', '', cleaned_response)
        # cite 태그 내용만 추출
        cleaned_response = re.sub(r'<cite[^>]*>([\s\S]*?)</cite>', r'\1', cleaned_response)
        # 볼드 마크다운 제거
        cleaned_response = re.sub(r'\*\*([^*]+)\*\*', r'\1', cleaned_response)
        # 대괄호 제거
        cleaned_response = re.sub(r'【([^】]+)】', r'\1', cleaned_response)
        
        prompt = f"""{SUMMARY_SYSTEM_PROMPT}

[질문]
{user_query}

[답변]
{cleaned_response}"""
        
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.3,
                "max_output_tokens": 500,
            }
        )
        
        result = response.text.strip()
        
        # 후처리: • 앞에 빈 줄 강제 추가 (첫 번째 • 제외하고)
        lines = result.split('\n')
        formatted_lines = []
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            # 첫 줄이 아니고 •로 시작하면 앞에 빈 줄 추가
            if line.startswith('•') and formatted_lines:
                formatted_lines.append('')
            formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)
    
    except Exception as e:
        print(f"❌ 요약 생성 실패: {e}")
        return "요약을 생성할 수 없습니다."
