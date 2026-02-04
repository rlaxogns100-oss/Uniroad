#!/bin/bash

echo "🚀 유니로드 설치 스크립트"
echo "=" 
echo ""

# 백엔드 설치
echo "📦 백엔드 설치 중..."
cd backend

# Python 가상환경 생성
if [ ! -d "venv" ]; then
    echo "   Python 가상환경 생성..."
    python3 -m venv venv
fi

# 가상환경 활성화
echo "   가상환경 활성화..."
source venv/bin/activate

# 패키지 설치
echo "   Python 패키지 설치..."
pip install --upgrade pip
pip install -r requirements.txt

# .env 파일 확인
if [ ! -f ".env" ]; then
    echo "   ⚠️  .env 파일이 없습니다. .env.example을 복사해서 수정하세요."
    cp .env.example .env
fi

cd ..

# 프론트엔드 설치
echo ""
echo "📦 프론트엔드 설치 중..."
cd frontend

if [ ! -d "node_modules" ]; then
    echo "   npm 패키지 설치..."
    npm install
else
    echo "   이미 설치되어 있습니다."
fi

cd ..

echo ""
echo "✅ 설치 완료!"
echo ""
echo "📝 다음 단계:"
echo "1. backend/.env 파일을 열어서 API 키를 입력하세요"
echo "2. ./start.sh 를 실행하여 서버를 시작하세요"
echo ""

