#!/bin/bash
# 서버 배포: 키 있는 PC에서 실행
# 사용: ./deploy-to-server.sh

set -e
# 키 파일: 데스크탑에 둔 경우
KEY="$HOME/Desktop/uniroad-server_key_fixed.pem"
HOST="azureuser@52.141.16.217"
REPO_DIR="/home/azureuser/uniroad"

echo "==> 서버 배포 시작 ($HOST)"
ssh -o StrictHostKeyChecking=accept-new -i "$KEY" "$HOST" bash -s << 'REMOTE'
set -e
cd /home/azureuser/uniroad || { echo "오류: 프로젝트 경로 없음"; exit 1; }
echo "==> git pull origin main"
git fetch origin
git pull origin main
echo "==> 프론트엔드 빌드"
cd frontend && npm install && npm run build && cd ..
echo "==> 백엔드 재시작"
sudo systemctl restart uniroad-backend
echo "==> 상태 확인"
sudo systemctl is-active uniroad-backend
echo "==> 배포 완료"
REMOTE
echo ""
echo "배포 끝. 확인: curl -s http://52.141.16.217/api/health 2>/dev/null || curl -s http://52.141.16.217/"
