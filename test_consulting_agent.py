"""
컨설팅 에이전트 테스트 스크립트 - 상세 로그 출력
"""
import asyncio
import sys
import os

# 경로 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from services.multi_agent.sub_agents import ConsultingAgent
from services.multi_agent.orchestration_agent import run_orchestration_agent
from services.multi_agent.final_agent import FinalAgent

async def test_full_pipeline():
    """전체 파이프라인 테스트"""
    query = "나 233322 정시로 이렇게 봤는데 어디로 갈 수 있어?"
    
    print("="*80)
    print("🚀 전체 파이프라인 테스트 시작")
    print("="*80)
    print(f"질문: {query}\n")
    
    # 1단계: Orchestration Agent
    print("\n" + "="*80)
    print("🎯 1단계: Orchestration Agent 실행")
    print("="*80)
    orchestration_result = await run_orchestration_agent(
        message=query,
        history=[]
    )
    print(f"\n✅ Orchestration 결과:")
    print(f"  - 실행 계획: {orchestration_result.get('execution_plan', {})}")
    print(f"  - 답변 구조: {orchestration_result.get('answer_structure', {})}")
    
    # 2단계: Sub Agents 실행
    print("\n" + "="*80)
    print("🎯 2단계: Sub Agents 실행")
    print("="*80)
    
    from services.multi_agent import execute_sub_agents
    sub_agent_results = await execute_sub_agents(
        execution_plan=orchestration_result.get('execution_plan', [])
    )
    
    print(f"\n✅ Sub Agents 결과:")
    for step_name, result in sub_agent_results.items():
        print(f"\n  📋 {step_name}:")
        if isinstance(result, dict):
            print(f"    - Agent: {result.get('agent', 'N/A')}")
            print(f"    - Status: {result.get('status', 'N/A')}")
            if 'normalized_scores' in result:
                print(f"    - 정규화된 점수: {result.get('normalized_scores', {})}")
            if 'admission_results' in result:
                print(f"    - 전형결과 데이터: {len(result.get('admission_results', {}).get('documents', []))}개 문서")
            if 'result' in result:
                result_text = result.get('result', '')
                print(f"    - 결과 텍스트 (처음 500자): {result_text[:500]}...")
    
    # 3단계: Final Agent
    print("\n" + "="*80)
    print("🎯 3단계: Final Agent 실행")
    print("="*80)
    
    final_agent = FinalAgent()
    final_result = await final_agent.generate_final_answer(
        user_question=query,
        answer_structure=orchestration_result.get('answer_structure', {}),
        sub_agent_results=sub_agent_results,
        history=[]
    )
    
    print(f"\n✅ Final Agent 결과:")
    print(f"  - 최종 답변: {final_result.get('answer', 'N/A')[:500]}...")
    
    print("\n" + "="*80)
    print("✅ 전체 파이프라인 테스트 완료")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(test_full_pipeline())

