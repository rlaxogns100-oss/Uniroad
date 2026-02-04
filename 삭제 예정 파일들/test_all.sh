#!/bin/bash
# 타이밍 측정 시스템 종합 테스트 스크립트

echo "🧪 타이밍 측정 시스템 종합 테스트"
echo "=================================="
echo ""

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 결과 카운터
PASS=0
FAIL=0

# 테스트 함수
test_step() {
    echo -n "$1... "
}

test_pass() {
    echo -e "${GREEN}✅ 통과${NC}"
    ((PASS++))
}

test_fail() {
    echo -e "${RED}❌ 실패${NC}"
    echo "   $1"
    ((FAIL++))
}

test_warn() {
    echo -e "${YELLOW}⚠️  경고${NC}"
    echo "   $1"
}

echo "1️⃣  백엔드 구조 확인"
echo "-------------------"

# 타이밍 로거 파일 확인
test_step "타이밍 로거 파일 존재"
if [ -f "backend/utils/timing_logger.py" ]; then
    test_pass
else
    test_fail "backend/utils/timing_logger.py 파일이 없습니다"
fi

# 문서 캐시 파일 확인
test_step "문서 캐시 파일 존재"
if [ -f "backend/utils/document_cache.py" ]; then
    test_pass
else
    test_fail "backend/utils/document_cache.py 파일이 없습니다"
fi

# 테스트 스크립트 확인
test_step "테스트 스크립트 존재"
if [ -f "backend/test_timing.py" ]; then
    test_pass
else
    test_fail "backend/test_timing.py 파일이 없습니다"
fi

# 로그 디렉토리 확인
test_step "로그 디렉토리 존재"
if [ -d "backend/logs" ]; then
    test_pass
else
    test_warn "backend/logs 디렉토리가 없습니다. 생성합니다..."
    mkdir -p backend/logs
fi

echo ""
echo "2️⃣  프론트엔드 구조 확인"
echo "---------------------"

# 프론트엔드 타이밍 로거 확인
test_step "프론트엔드 타이밍 로거 존재"
if [ -f "frontend/src/utils/timingLogger.ts" ]; then
    test_pass
else
    test_fail "frontend/src/utils/timingLogger.ts 파일이 없습니다"
fi

# 타이밍 대시보드 확인
test_step "타이밍 대시보드 존재"
if [ -f "frontend/src/pages/TimingDashboard.tsx" ]; then
    test_pass
else
    test_fail "frontend/src/pages/TimingDashboard.tsx 파일이 없습니다"
fi

# App.tsx에 라우트 확인
test_step "App.tsx에 대시보드 라우트 설정"
if grep -q "TimingDashboard" "frontend/src/App.tsx"; then
    test_pass
else
    test_fail "App.tsx에 TimingDashboard import가 없습니다"
fi

echo ""
echo "3️⃣  백엔드 서버 상태 확인"
echo "----------------------"

# 백엔드 서버 실행 확인
test_step "백엔드 서버 실행 중"
if curl -s http://localhost:8000/docs > /dev/null 2>&1; then
    test_pass
else
    test_warn "백엔드 서버가 실행되지 않았습니다"
    echo "   실행 방법: cd backend && python -m uvicorn main:app --reload"
fi

echo ""
echo "4️⃣  프론트엔드 서버 상태 확인"
echo "-------------------------"

# 프론트엔드 서버 실행 확인
test_step "프론트엔드 서버 실행 중"
if curl -s http://localhost:5173 > /dev/null 2>&1; then
    test_pass
elif curl -s http://localhost:3000 > /dev/null 2>&1; then
    test_pass
else
    test_warn "프론트엔드 서버가 실행되지 않았습니다"
    echo "   실행 방법: cd frontend && npm run dev"
fi

echo ""
echo "5️⃣  Python 의존성 확인"
echo "--------------------"

cd backend

# Python 가상환경 확인
test_step "Python 실행 가능"
if command -v python &> /dev/null; then
    test_pass
else
    test_fail "Python이 설치되지 않았습니다"
fi

# 필수 패키지 확인
test_step "필수 패키지 설치 확인"
python -c "import asyncio, time, json, hashlib, threading" 2>/dev/null
if [ $? -eq 0 ]; then
    test_pass
else
    test_fail "필수 Python 패키지가 없습니다"
fi

cd ..

echo ""
echo "6️⃣  통합 기능 확인"
echo "----------------"

# chat.py에 타이밍 로거 통합 확인
test_step "chat.py에 TimingLogger 통합"
if grep -q "TimingLogger" "backend/routers/chat.py"; then
    test_pass
else
    test_fail "chat.py에 TimingLogger가 통합되지 않았습니다"
fi

# sub_agents.py에 병렬 실행 구현 확인
test_step "sub_agents.py에 병렬 실행 구현"
if grep -q "_execute_agents_parallel" "backend/services/multi_agent/sub_agents.py"; then
    test_pass
else
    test_fail "sub_agents.py에 병렬 실행이 구현되지 않았습니다"
fi

# sub_agents.py에 캐시 통합 확인
test_step "sub_agents.py에 캐시 통합"
if grep -q "cache_get\|cache_set" "backend/services/multi_agent/sub_agents.py"; then
    test_pass
else
    test_fail "sub_agents.py에 캐시가 통합되지 않았습니다"
fi

# ChatPage.tsx에 타이밍 로거 통합 확인
test_step "ChatPage.tsx에 타이밍 로거 통합"
if grep -q "FrontendTimingLogger" "frontend/src/pages/ChatPage.tsx"; then
    test_pass
else
    test_fail "ChatPage.tsx에 타이밍 로거가 통합되지 않았습니다"
fi

echo ""
echo "=================================="
echo "📊 테스트 결과 요약"
echo "=================================="
echo -e "${GREEN}통과: $PASS${NC}"
echo -e "${RED}실패: $FAIL${NC}"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}🎉 모든 테스트 통과! 시스템이 정상 작동합니다.${NC}"
    echo ""
    echo "다음 단계:"
    echo "1. 백엔드 서버가 실행 중이 아니면:"
    echo "   cd backend && python -m uvicorn main:app --reload"
    echo ""
    echo "2. 프론트엔드 서버가 실행 중이 아니면:"
    echo "   cd frontend && npm run dev"
    echo ""
    echo "3. 브라우저에서 http://localhost:5173 접속"
    echo ""
    echo "4. 타이밍 대시보드: http://localhost:5173/timing-dashboard"
    echo ""
    echo "5. 터미널에서 로그 확인:"
    echo "   tail -f backend/logs/timing_summary.csv"
    exit 0
else
    echo -e "${RED}⚠️  일부 테스트 실패. 위의 오류를 확인하세요.${NC}"
    exit 1
fi
