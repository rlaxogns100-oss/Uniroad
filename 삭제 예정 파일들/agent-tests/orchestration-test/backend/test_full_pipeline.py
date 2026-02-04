"""
전체 파이프라인 테스트: Orchestration → Sub Agents → Final
extracted_scores가 제대로 전달되고 전처리되는지 확인
"""

import asyncio
import json
from main import run_orchestration_agent
from sub_agents import execute_sub_agents
from final_agent import generate_final_answer


async def test_full_pipeline():
    """전체 파이프라인 테스트"""
    print("\n" + "="*80)
    print("🚀 전체 파이프라인 테스트: extracted_scores 전달 확인")
    print("="*80)
    
    # 1단계: Orchestration
    message = "나 11232야 서울대 의대 갈 수 있어?"
    print(f"\n사용자 질문: {message}")
    print("\n" + "-"*80)
    print("1단계: Orchestration Agent")
    print("-"*80)
    
    orchestration_result = await run_orchestration_agent(message, "test_full")
    
    user_intent = orchestration_result.get("user_intent")
    extracted_scores = orchestration_result.get("extracted_scores", {})
    execution_plan = orchestration_result.get("execution_plan", [])
    answer_structure = orchestration_result.get("answer_structure", [])
    
    print(f"사용자 의도: {user_intent}")
    print(f"\nextracted_scores: {len(extracted_scores)}개 과목")
    for subject, info in extracted_scores.items():
        print(f"  - {subject}: {info}")
    
    print(f"\n실행 계획: {len(execution_plan)}개 step")
    for step in execution_plan:
        print(f"  Step {step.get('step')}: {step.get('agent')} - {step.get('query')[:50]}...")
    
    # 2단계: Sub Agents 실행
    print("\n" + "-"*80)
    print("2단계: Sub Agents 실행")
    print("-"*80)
    
    sub_agent_results = await execute_sub_agents(
        execution_plan,
        extracted_scores=extracted_scores
    )
    
    print(f"\nSub Agent 결과: {len(sub_agent_results)}개")
    for key, result in sub_agent_results.items():
        agent_name = result.get("agent", "Unknown")
        status = result.get("status", "unknown")
        print(f"  - {key}: {agent_name} ({status})")
        
        # 컨설팅 agent 결과 확인
        if "컨설팅" in agent_name:
            query_used = result.get("query", "")
            if "[전처리된 성적]" in query_used:
                print(f"    ✅ 전처리된 성적이 포함됨")
                # 전처리된 부분 미리보기
                preprocessed_part = query_used.split("[원본 쿼리]")[0]
                lines = preprocessed_part.split("\n")[:5]
                for line in lines:
                    if line.strip():
                        print(f"      {line[:70]}")
            else:
                print(f"    ❌ 전처리된 성적 없음")
    
    # 3단계: Final Agent
    print("\n" + "-"*80)
    print("3단계: Final Agent")
    print("-"*80)
    
    final_result = await generate_final_answer(
        user_question=message,
        answer_structure=answer_structure,
        sub_agent_results=sub_agent_results,
        notes=""
    )
    
    final_answer = final_result.get("final_answer", "")
    print(f"\n최종 답변 길이: {len(final_answer)}자")
    print(f"\n최종 답변 미리보기:")
    print("-"*80)
    print(final_answer[:500] + "..." if len(final_answer) > 500 else final_answer)
    print("-"*80)
    
    print("\n" + "="*80)
    print("✅ 전체 파이프라인 테스트 완료!")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
