#!/bin/bash

# 유니로드 AWS 배포 자동화 스크립트
# 사용법: ./deploy-aws.sh

set -e  # 오류 발생 시 중단

echo "🚀 유니로드 AWS 서버 자동 배포 시작"
echo "=================================="
echo ""

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1단계: 시스템 업데이트
echo "📦 1단계: 시스템 업데이트..."
sudo apt update
sudo apt upgrade -y

# 2단계: 필수 패키지 설치
echo ""
echo "📦 2단계: 필수 패키지 설치..."

# Python 3.11+ 확인 및 설치
if ! command -v python3 &> /dev/null; then
    echo "   Python3 설치 중..."
    sudo apt install -y python3 python3-pip python3-venv
fi

# Node.js 18+ 확인 및 설치
if ! command -v node &> /dev/null; then
    echo "   Node.js 설치 중..."
    curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
    sudo apt install -y nodejs
fi

# Nginx 설치
if ! command -v nginx &> /dev/null; then
    echo "   Nginx 설치 중..."
    sudo apt install -y nginx
fi

# 기타 유틸리티
sudo apt install -y git build-essential libssl-dev

echo ""
echo "✅ 설치된 버전:"
python3 --version
node --version
npm --version
nginx -v

# 3단계: 프로젝트 클론 또는 업데이트
echo ""
echo "📥 3단계: 프로젝트 가져오기..."

PROJECT_DIR="/home/ubuntu/Uniroad"

if [ -d "$PROJECT_DIR" ]; then
    echo "   기존 프로젝트 업데이트..."
    cd $PROJECT_DIR
    git pull origin main
else
    echo "   프로젝트 클론..."
    cd /home/ubuntu
    git clone https://github.com/rlaxogns100-oss/Uniroad.git
    cd Uniroad
fi

# 4단계: 환경변수 확인
echo ""
echo "🔐 4단계: 환경변수 확인..."

if [ ! -f "$PROJECT_DIR/backend/.env" ]; then
    echo -e "${RED}❌ backend/.env 파일이 없습니다!${NC}"
    echo ""
    echo "다음 내용으로 파일을 생성하세요:"
    echo "--------------------------------------"
    cat << 'EOF'
SUPABASE_URL=https://rnitmphvahpkosvxjshw.supabase.co
SUPABASE_KEY=여기에_service_key_입력
SUPABASE_JWT_SECRET=여기에_jwt_secret_입력
GEMINI_API_KEY=여기에_gemini_key_입력
BACKEND_PORT=8000
FRONTEND_URL=http://3.107.178.26
EOF
    echo "--------------------------------------"
    echo ""
    read -p "Enter키를 눌러 nano 에디터로 .env 파일을 생성하세요..." 
    nano $PROJECT_DIR/backend/.env
fi

if [ ! -f "$PROJECT_DIR/frontend/.env" ]; then
    echo -e "${RED}❌ frontend/.env 파일이 없습니다!${NC}"
    echo ""
    echo "다음 내용으로 파일을 생성하세요:"
    echo "--------------------------------------"
    cat << 'EOF'
VITE_SUPABASE_URL=https://rnitmphvahpkosvxjshw.supabase.co
VITE_SUPABASE_ANON_KEY=여기에_anon_key_입력
EOF
    echo "--------------------------------------"
    echo ""
    read -p "Enter키를 눌러 nano 에디터로 .env 파일을 생성하세요..." 
    nano $PROJECT_DIR/frontend/.env
fi

# 5단계: 백엔드 설치
echo ""
echo "🐍 5단계: 백엔드 설치..."
cd $PROJECT_DIR/backend

# 가상환경 생성
if [ ! -d "venv" ]; then
    echo "   Python 가상환경 생성..."
    python3 -m venv venv
fi

# 가상환경 활성화 및 패키지 설치
echo "   패키지 설치..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install email-validator

echo "✅ 백엔드 설치 완료"

# 6단계: 프론트엔드 빌드
echo ""
echo "🎨 6단계: 프론트엔드 빌드..."
cd $PROJECT_DIR/frontend

echo "   패키지 설치..."
npm install

echo "   빌드 중..."
npm run build

echo "✅ 프론트엔드 빌드 완료 (dist/ 폴더)"

# 7단계: Systemd 서비스 생성
echo ""
echo "⚙️  7단계: 백엔드 서비스 등록..."

sudo tee /etc/systemd/system/uniroad-backend.service > /dev/null << EOF
[Unit]
Description=Uniroad Backend API
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$PROJECT_DIR/backend
Environment="PATH=$PROJECT_DIR/backend/venv/bin"
ExecStart=$PROJECT_DIR/backend/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable uniroad-backend
sudo systemctl restart uniroad-backend

echo "✅ 백엔드 서비스 등록 완료"

# 8단계: Nginx 설정
echo ""
echo "🌐 8단계: Nginx 설정..."

sudo tee /etc/nginx/sites-available/uniroad > /dev/null << 'EOF'
# Rate Limiting Zone 정의 (http 블록에 포함되도록 nginx.conf에도 추가 필요)
# 이 부분은 /etc/nginx/nginx.conf의 http 블록에 수동으로 추가해야 합니다:
# limit_req_zone $binary_remote_addr zone=chat_limit:10m rate=5r/s;

server {
    listen 80;
    server_name 3.107.178.26;

    # 프론트엔드 정적 파일
    location / {
        root /home/ubuntu/Uniroad/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # 백엔드 Chat API (Rate Limiting 적용)
    location /api/chat/ {
        # Rate Limiting: 1초 5회, burst 10회까지 허용
        limit_req zone=chat_limit burst=10 nodelay;
        limit_req_status 503;
        
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        
        # SSE 지원
        proxy_buffering off;
        proxy_read_timeout 3600s;
        proxy_connect_timeout 3600s;
        proxy_send_timeout 3600s;
    }

    # 백엔드 API 프록시 (다른 API - Rate Limit 없음)
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        
        # SSE 지원
        proxy_buffering off;
        proxy_read_timeout 3600s;
        proxy_connect_timeout 3600s;
        proxy_send_timeout 3600s;
    }

    # API 문서
    location /docs {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /openapi.json {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

# Nginx 심볼릭 링크 생성
if [ ! -L /etc/nginx/sites-enabled/uniroad ]; then
    sudo ln -s /etc/nginx/sites-available/uniroad /etc/nginx/sites-enabled/
fi

# 기본 사이트 비활성화
if [ -L /etc/nginx/sites-enabled/default ]; then
    sudo rm /etc/nginx/sites-enabled/default
fi

# Nginx 설정 테스트 및 재시작
echo "   Nginx 설정 테스트..."
sudo nginx -t

echo "   Nginx 재시작..."
sudo systemctl restart nginx

echo "✅ Nginx 설정 완료"

# 9단계: 상태 확인
echo ""
echo "🔍 9단계: 서비스 상태 확인..."
echo ""

echo "백엔드 서비스:"
sudo systemctl status uniroad-backend --no-pager | head -10

echo ""
echo "Nginx 서비스:"
sudo systemctl status nginx --no-pager | head -10

echo ""
echo "백엔드 API 테스트:"
curl -s http://localhost:8000/ | python3 -m json.tool || echo "백엔드 응답 대기 중..."

# 10단계: 완료
echo ""
echo "=================================="
echo -e "${GREEN}✅ 배포 완료!${NC}"
echo "=================================="
echo ""
echo "📍 접속 주소:"
echo "   웹사이트: http://3.107.178.26"
echo "   API 문서: http://3.107.178.26/docs"
echo ""
echo "📊 유용한 명령어:"
echo "   백엔드 로그: sudo journalctl -u uniroad-backend -f"
echo "   백엔드 재시작: sudo systemctl restart uniroad-backend"
echo "   Nginx 재시작: sudo systemctl restart nginx"
echo "   Nginx 로그: sudo tail -f /var/log/nginx/error.log"
echo ""
echo "🔧 업데이트 방법:"
echo "   cd $PROJECT_DIR && git pull origin main"
echo "   ./deploy-aws.sh (이 스크립트 재실행)"
echo ""
