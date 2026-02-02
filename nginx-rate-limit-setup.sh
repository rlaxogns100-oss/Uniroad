#!/bin/bash

# Nginx Rate Limiting 설정 스크립트
# SSH로 서버 접속 후 실행: ssh -i "/Users/rlaxogns100/Desktop/김태훈/uniroad-server_key_fixed.pem" azureuser@52.141.16.217

set -e

echo "🔧 Nginx Rate Limiting 설정 시작..."
echo ""

# 1. nginx.conf 백업
echo "📦 1. nginx.conf 백업 중..."
sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup.$(date +%Y%m%d_%H%M%S)
echo "✅ 백업 완료"
echo ""

# 2. Rate Limit Zone 추가 (http 블록 내부)
echo "⚙️  2. Rate Limit Zone 추가 중..."

# http 블록에 limit_req_zone이 이미 있는지 확인
if grep -q "limit_req_zone.*chat_limit" /etc/nginx/nginx.conf; then
    echo "ℹ️  Rate Limit Zone이 이미 설정되어 있습니다."
else
    # http 블록의 마지막 줄(닫는 괄호 바로 앞)에 추가
    sudo sed -i '/^http {/a \
    # Rate Limiting Zone for Chat API\
    limit_req_zone $binary_remote_addr zone=chat_limit:10m rate=5r/s;' /etc/nginx/nginx.conf
    
    echo "✅ Rate Limit Zone 추가 완료"
fi
echo ""

# 3. Nginx 설정 테스트
echo "🔍 3. Nginx 설정 테스트..."
if sudo nginx -t; then
    echo "✅ Nginx 설정 테스트 통과"
else
    echo "❌ Nginx 설정 오류! 백업 파일로 복구하세요:"
    echo "   sudo cp /etc/nginx/nginx.conf.backup.* /etc/nginx/nginx.conf"
    exit 1
fi
echo ""

# 4. Nginx 재시작
echo "🔄 4. Nginx 재시작..."
sudo systemctl reload nginx
echo "✅ Nginx 재시작 완료"
echo ""

# 5. 설정 확인
echo "📋 5. 최종 확인..."
echo ""
echo "=== Rate Limit Zone 설정 ==="
sudo grep -A 2 "limit_req_zone" /etc/nginx/nginx.conf || echo "⚠️  설정을 찾을 수 없습니다"
echo ""
echo "=== /api/chat/ Location 설정 ==="
sudo grep -A 5 "location /api/chat/" /etc/nginx/sites-available/uniroad || echo "⚠️  설정을 찾을 수 없습니다"
echo ""

echo "=================================="
echo "✅ Nginx Rate Limiting 설정 완료!"
echo "=================================="
echo ""
echo "📊 테스트 방법:"
echo "   1초에 10번 요청:"
echo "   for i in {1..10}; do curl -X POST http://52.141.16.217/api/chat/v2/stream -H \"Content-Type: application/json\" -d '{\"message\":\"test\"}' & done"
echo ""
echo "   예상 결과: 처음 5번(+burst 10) 성공, 나머지 503 에러"
echo ""
