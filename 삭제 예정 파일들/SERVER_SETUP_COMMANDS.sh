#!/bin/bash
# 서버에서 실행할 Rate Limiting 설정 명령어 모음
# SSH 접속: ssh -i "/Users/rlaxogns100/Desktop/김태훈/uniroad-server_key_fixed.pem" azureuser@52.141.16.217

set -e

echo "🚀 Rate Limiting 배포 시작..."
echo ""

# ============================================
# 1단계: 백엔드 재시작
# ============================================
echo "📦 1단계: 백엔드 재시작"
echo "현재 상태 확인..."
sudo systemctl status uniroad-backend --no-pager | head -10 || true

echo ""
echo "백엔드 재시작 중..."
sudo systemctl restart uniroad-backend

echo ""
echo "재시작 후 5초 대기..."
sleep 5

echo ""
echo "백엔드 로그 확인 (최근 30줄):"
sudo journalctl -u uniroad-backend -n 30 --no-pager

echo ""
echo "✅ 1단계 완료"
echo ""

# ============================================
# 2단계: Nginx 설정 업데이트
# ============================================
echo "🌐 2단계: Nginx 설정 업데이트"

# 백업
echo "현재 설정 백업 중..."
sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup.$(date +%Y%m%d_%H%M%S)
sudo cp /etc/nginx/sites-available/uniroad /etc/nginx/sites-available/uniroad.backup.$(date +%Y%m%d_%H%M%S)

# Rate Limit Zone 추가 확인
echo ""
if grep -q "limit_req_zone.*chat_limit" /etc/nginx/nginx.conf; then
    echo "✅ Rate Limit Zone이 이미 설정되어 있습니다."
else
    echo "⚙️  Rate Limit Zone 추가 중..."
    # http 블록 시작 부분 다음 줄에 추가
    sudo sed -i '/^http {$/a\    # Rate Limiting Zone for Chat API\n    limit_req_zone $binary_remote_addr zone=chat_limit:10m rate=5r/s;' /etc/nginx/nginx.conf
    echo "✅ Rate Limit Zone 추가 완료"
fi

echo ""
echo "✅ 2단계 완료"
echo ""

# ============================================
# 3단계: Nginx sites-available/uniroad 업데이트
# ============================================
echo "📝 3단계: /api/chat/ location에 Rate Limiting 추가"

# /api/chat/ location이 이미 있는지 확인
if grep -q "location /api/chat/" /etc/nginx/sites-available/uniroad; then
    echo "⚠️  /api/chat/ location이 이미 존재합니다."
    echo "   수동으로 확인이 필요할 수 있습니다."
else
    echo "⚙️  /api/chat/ location 추가 중..."
    
    # /api/ location 앞에 /api/chat/ location 추가
    sudo sed -i '/location \/api\/ {/i\    # Chat API with Rate Limiting\n    location /api/chat/ {\n        limit_req zone=chat_limit burst=10 nodelay;\n        limit_req_status 503;\n        \n        proxy_pass http://localhost:8000;\n        proxy_http_version 1.1;\n        proxy_set_header Upgrade $http_upgrade;\n        proxy_set_header Connection '"'"'upgrade'"'"';\n        proxy_set_header Host $host;\n        proxy_cache_bypass $http_upgrade;\n        proxy_set_header X-Real-IP $remote_addr;\n        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n        \n        proxy_buffering off;\n        proxy_read_timeout 3600s;\n        proxy_connect_timeout 3600s;\n        proxy_send_timeout 3600s;\n    }\n' /etc/nginx/sites-available/uniroad
    
    echo "✅ /api/chat/ location 추가 완료"
fi

echo ""
echo "✅ 3단계 완료"
echo ""

# ============================================
# 4단계: Nginx 설정 테스트 및 재시작
# ============================================
echo "🔍 4단계: Nginx 설정 테스트 및 재시작"

echo "설정 테스트 중..."
if sudo nginx -t; then
    echo "✅ Nginx 설정 테스트 통과"
    
    echo ""
    echo "Nginx 재시작 중..."
    sudo systemctl reload nginx
    
    echo ""
    echo "Nginx 상태 확인:"
    sudo systemctl status nginx --no-pager | head -10
    
    echo ""
    echo "✅ Nginx 재시작 완료"
else
    echo "❌ Nginx 설정 오류!"
    echo "   백업 파일로 복구하세요:"
    echo "   sudo cp /etc/nginx/nginx.conf.backup.* /etc/nginx/nginx.conf"
    echo "   sudo cp /etc/nginx/sites-available/uniroad.backup.* /etc/nginx/sites-available/uniroad"
    exit 1
fi

echo ""
echo "✅ 4단계 완료"
echo ""

# ============================================
# 5단계: 최종 확인
# ============================================
echo "📋 5단계: 최종 설정 확인"
echo ""

echo "=== Rate Limit Zone 설정 ==="
sudo grep -A 1 "limit_req_zone.*chat_limit" /etc/nginx/nginx.conf || echo "⚠️  설정을 찾을 수 없습니다"

echo ""
echo "=== /api/chat/ Location 설정 ==="
sudo grep -A 15 "location /api/chat/" /etc/nginx/sites-available/uniroad || echo "⚠️  설정을 찾을 수 없습니다"

echo ""
echo "=== 백엔드 서비스 상태 ==="
sudo systemctl is-active uniroad-backend

echo ""
echo "=== Nginx 서비스 상태 ==="
sudo systemctl is-active nginx

echo ""
echo "=================================="
echo "✅ Rate Limiting 배포 완료!"
echo "=================================="
echo ""
echo "📊 테스트 방법 (로컬에서 실행):"
echo ""
echo "1. Nginx Rate Limit 테스트 (1초 10회 요청):"
echo "   for i in {1..10}; do curl -X POST http://52.141.16.217/api/chat/v2/stream -H \"Content-Type: application/json\" -d '{\"message\":\"test\"}' & done"
echo ""
echo "2. 백엔드 로그 실시간 확인:"
echo "   sudo journalctl -u uniroad-backend -f"
echo ""
echo "3. Nginx 로그 실시간 확인:"
echo "   sudo tail -f /var/log/nginx/error.log | grep 'limiting'"
echo ""
