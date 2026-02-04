#!/bin/bash

echo "🛑 유니로드 서버 종료 중..."
echo ""

# 백엔드 프로세스 종료 (포트 8000)
BACKEND_PID=$(lsof -ti:8000)
if [ -n "$BACKEND_PID" ]; then
    echo "🔴 백엔드 서버 종료 중... (PID: $BACKEND_PID)"
    kill -9 $BACKEND_PID 2>/dev/null
    echo "✓ 백엔드 서버 종료 완료"
else
    echo "ℹ️  실행 중인 백엔드 서버가 없습니다"
fi

# 프론트엔드 프로세스 종료 (포트 5173)
FRONTEND_PID=$(lsof -ti:5173)
if [ -n "$FRONTEND_PID" ]; then
    echo "🔴 프론트엔드 서버 종료 중... (PID: $FRONTEND_PID)"
    kill -9 $FRONTEND_PID 2>/dev/null
    echo "✓ 프론트엔드 서버 종료 완료"
else
    echo "ℹ️  실행 중인 프론트엔드 서버가 없습니다"
fi

echo ""
echo "✅ 모든 서버가 종료되었습니다"
