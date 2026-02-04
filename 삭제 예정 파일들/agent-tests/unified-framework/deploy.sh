#!/bin/bash
set -e

# 배포 설정
SERVER="ubuntu@your-server-ip"  # 여기에 실제 서버 IP 입력
REMOTE_PATH="/home/ubuntu/uniroad/agent-tests/unified-framework"

echo "📦 Agent Testing Framework - AWS 배포"
echo "======================================"
echo ""

# 서버 IP 확인
if [ "$SERVER" == "ubuntu@your-server-ip" ]; then
    echo "❌ 에러: SERVER 변수를 실제 서버 IP로 수정하세요!"
    echo "   파일: deploy.sh"
    echo "   예시: SERVER=\"ubuntu@13.124.123.45\""
    exit 1
fi

# 1. Frontend 업로드
echo "📤 [1/4] Uploading frontend..."
rsync -avz --progress \
  index.html \
  ${SERVER}:${REMOTE_PATH}/

# 2. Backend 업로드
echo ""
echo "📤 [2/4] Uploading backend..."
rsync -avz --progress \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude 'storage' \
  --exclude '.env' \
  backend/ \
  ${SERVER}:${REMOTE_PATH}/backend/

# 3. 의존성 설치 (처음 배포 시만 필요)
echo ""
read -p "🤔 의존성을 설치하시겠습니까? (처음 배포 시 'y') [y/N]: " install_deps
if [[ $install_deps =~ ^[Yy]$ ]]; then
    echo "📦 [3/4] Installing dependencies..."
    ssh ${SERVER} "cd ${REMOTE_PATH}/backend && pip3 install -r requirements.txt"
else
    echo "⏭️  [3/4] Skipping dependency installation..."
fi

# 4. Backend 재시작
echo ""
echo "🔄 [4/4] Restarting backend service..."
ssh ${SERVER} "sudo systemctl restart agent-test-api"

# 잠시 대기
sleep 2

# 5. 상태 확인
echo ""
echo "✅ Deployment complete!"
echo ""
echo "🔍 Checking service status..."
ssh ${SERVER} "sudo systemctl status agent-test-api --no-pager | head -20"

# 6. 접속 정보 출력
echo ""
echo "======================================"
echo "🎉 배포 성공!"
echo "======================================"
echo ""
echo "📍 Frontend: https://uni2road.com/agent-test"
echo "📍 API Health: https://uni2road.com/api/health"
echo ""
echo "💡 테스트 명령어:"
echo "   curl https://uni2road.com/api/health"
echo ""
echo "📋 로그 확인:"
echo "   ssh ${SERVER} 'sudo journalctl -u agent-test-api -f'"
echo ""
