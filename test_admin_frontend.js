// 브라우저 콘솔에서 실행할 테스트 코드
// Admin Agent Page (localhost:5174/adminagent)에서 실행하세요

// 1. 로컬스토리지 데이터 확인
console.log('=== 로컬스토리지 데이터 확인 ===')
const logs = JSON.parse(localStorage.getItem('admin_execution_logs') || '[]')
console.log('총 로그 개수:', logs.length)
if (logs.length > 0) {
  console.log('첫 번째 로그:', logs[0])
  console.log('routerOutput 타입:', typeof logs[0].routerOutput)
  console.log('routerOutput 값:', logs[0].routerOutput)
}

// 2. 재평가 API 직접 테스트
async function testReEvaluate() {
  if (logs.length === 0) {
    console.log('로그가 없습니다')
    return
  }
  
  const log = logs[0]
  console.log('\n=== 재평가 테스트 ===')
  console.log('로그 ID:', log.id)
  console.log('사용자 질문:', log.userQuestion)
  console.log('routerOutput 타입:', typeof log.routerOutput)
  
  // 문자열로 변환
  const routerOutputStr = typeof log.routerOutput === 'string'
    ? log.routerOutput
    : JSON.stringify(log.routerOutput, null, 2)
  
  console.log('변환된 문자열:', routerOutputStr)
  
  // API 호출
  try {
    const response = await fetch('/api/admin/evaluate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_question: log.userQuestion.replace(/^\[추가실행 \d+\] /, ''),
        router_output: routerOutputStr
      })
    })
    
    console.log('응답 상태:', response.status)
    
    if (response.ok) {
      const result = await response.json()
      console.log('평가 결과:', result)
    } else {
      const error = await response.text()
      console.error('에러 응답:', error)
    }
  } catch (error) {
    console.error('네트워크 오류:', error)
  }
}

// 실행
testReEvaluate()
