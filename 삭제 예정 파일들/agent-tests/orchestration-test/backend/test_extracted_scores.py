"""
Orchestration Agent의 extracted_scores 기능 테스트
"""

import asyncio
import json
from main import run_orchestration_agent


async def test_case_1():
    """테스트 1: 축약형 입력 (11232)"""
    print("\n" + "="*60)
    print("테스트 1: 축약형 입력")
    print("="*60)
    
    message = "나 11232야 서울대 의대 갈 수 있어?"
    print(f"입력: {message}")
    
    result = await run_orchestration_agent(message, "test_session_1")
    
    print(f"\n사용자 의도: {result.get('user_intent')}")
    
    extracted_scores = result.get('extracted_scores')
    if extracted_scores:
        print(f"\n✅ extracted_scores 생성됨:")
        print(json.dumps(extracted_scores, ensure_ascii=False, indent=2))
    else:
        print("\n❌ extracted_scores 없음")
    
    execution_plan = result.get('execution_plan', [])
    print(f"\n실행 계획: {len(execution_plan)}개 step")
    for step in execution_plan:
        print(f"  Step {step.get('step')}: {step.get('agent')}")


async def test_case_2():
    """테스트 2: 자연어 입력"""
    print("\n" + "="*60)
    print("테스트 2: 자연어 입력")
    print("="*60)
    
    message = "국어가 1등급이고 수학도 1등급인데요, 영어는 2등급이에요. 서울대 갈 수 있을까요?"
    print(f"입력: {message}")
    
    result = await run_orchestration_agent(message, "test_session_2")
    
    print(f"\n사용자 의도: {result.get('user_intent')}")
    
    extracted_scores = result.get('extracted_scores')
    if extracted_scores:
        print(f"\n✅ extracted_scores 생성됨:")
        print(json.dumps(extracted_scores, ensure_ascii=False, indent=2))
    else:
        print("\n❌ extracted_scores 없음")


async def test_case_3():
    """테스트 3: 혼합 형식 (표준점수 + 등급)"""
    print("\n" + "="*60)
    print("테스트 3: 혼합 형식")
    print("="*60)
    
    message = "국어 표준점수 140, 수학 미적분 145점, 영어 1등급인데 고려대 어때?"
    print(f"입력: {message}")
    
    result = await run_orchestration_agent(message, "test_session_3")
    
    print(f"\n사용자 의도: {result.get('user_intent')}")
    
    extracted_scores = result.get('extracted_scores')
    if extracted_scores:
        print(f"\n✅ extracted_scores 생성됨:")
        print(json.dumps(extracted_scores, ensure_ascii=False, indent=2))
        
        # 수학 선택과목 확인
        if "수학" in extracted_scores:
            math_elective = extracted_scores["수학"].get("선택과목")
            print(f"\n수학 선택과목: {math_elective}")
    else:
        print("\n❌ extracted_scores 없음")


async def test_case_4():
    """테스트 4: 성적 없는 경우 (extracted_scores 생성 안 됨)"""
    print("\n" + "="*60)
    print("테스트 4: 성적 없는 경우")
    print("="*60)
    
    message = "서울대 의대 입결이 어떻게 돼?"
    print(f"입력: {message}")
    
    result = await run_orchestration_agent(message, "test_session_4")
    
    print(f"\n사용자 의도: {result.get('user_intent')}")
    
    extracted_scores = result.get('extracted_scores')
    if extracted_scores:
        print(f"\n❌ 예상 외: extracted_scores가 생성됨")
        print(json.dumps(extracted_scores, ensure_ascii=False, indent=2))
    else:
        print("\n✅ 정상: extracted_scores 없음 (성적 정보 없는 질문)")


async def test_case_5():
    """테스트 5: 선생님 agent 호출 (extracted_scores 생성 안 됨)"""
    print("\n" + "="*60)
    print("테스트 5: 선생님 agent 호출")
    print("="*60)
    
    message = "나 11232인데 공부 계획 좀 세워줘"
    print(f"입력: {message}")
    
    result = await run_orchestration_agent(message, "test_session_5")
    
    print(f"\n사용자 의도: {result.get('user_intent')}")
    
    extracted_scores = result.get('extracted_scores')
    execution_plan = result.get('execution_plan', [])
    
    print(f"\n실행 계획:")
    for step in execution_plan:
        print(f"  Step {step.get('step')}: {step.get('agent')}")
    
    if extracted_scores:
        print(f"\n❌ 예상 외: extracted_scores가 생성됨 (선생님 agent는 불필요)")
        print(json.dumps(extracted_scores, ensure_ascii=False, indent=2))
    else:
        print("\n✅ 정상: extracted_scores 없음 (컨설팅 agent 미호출)")


async def main():
    print("\n🚀 Orchestration Agent extracted_scores 테스트 시작\n")
    
    try:
        await test_case_1()
        await test_case_2()
        await test_case_3()
        await test_case_4()
        await test_case_5()
        
        print("\n" + "="*60)
        print("✅ 모든 테스트 완료!")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
