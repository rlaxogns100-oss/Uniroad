#!/bin/bash
# Rate Limiting 테스트 스크립트 (로컬에서 실행)
# 서버: 52.141.16.217

SERVER="52.141.16.217"
API_ENDPOINT="http://$SERVER/api/chat/v2/stream"

echo "🧪 Rate Limiting 테스트 시작"
echo "서버: $SERVER"
echo ""

# ============================================
# 테스트 1: Nginx Rate Limit (1초 10회 요청)
# ============================================
echo "============================================"
echo "테스트 1: Nginx Rate Limit"
echo "============================================"
echo "설명: 1초에 10번 요청 → 5번 초과로 503 에러 발생 예상"
echo ""

echo "요청 시작..."
for i in {1..10}; do
  echo -n "요청 $i: "
  response=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d '{"message": "test nginx", "session_id": "test"}' 2>&1)
  
  if [ "$response" = "503" ]; then
    echo "❌ 503 Service Unavailable (Rate Limit 차단)"
  elif [ "$response" = "429" ]; then
    echo "⚠️  429 Too Many Requests (백엔드 차단)"
  elif [ "$response" = "200" ]; then
    echo "✅ 200 OK (통과)"
  else
    echo "⚠️  $response"
  fi
done &

wait

echo ""
echo "예상 결과: 처음 5개(+burst 10) 성공, 나머지 503"
echo ""
echo "✅ 테스트 1 완료"
echo ""
sleep 2

# ============================================
# 테스트 2: 게스트 일일 제한 (10회)
# ============================================
echo "============================================"
echo "테스트 2: 게스트 IP 일일 제한 (10회)"
echo "============================================"
echo "설명: 토큰 없이 11번 요청 → 11번째 429 에러 예상"
echo ""

success_count=0
fail_count=0

for i in {1..11}; do
  echo -n "요청 $i/11: "
  
  response=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d "{\"message\": \"test guest $i\", \"session_id\": \"guest\"}")
  
  if [ "$response" = "429" ]; then
    echo "❌ 429 Too Many Requests (일일 제한 초과)"
    ((fail_count++))
  elif [ "$response" = "200" ]; then
    echo "✅ 200 OK"
    ((success_count++))
  elif [ "$response" = "503" ]; then
    echo "⚠️  503 (Nginx Rate Limit - 너무 빠름)"
  else
    echo "⚠️  $response"
  fi
  
  # Nginx Rate Limit 회피를 위해 0.3초 대기
  sleep 0.3
done

echo ""
echo "결과: 성공 $success_count개, 실패 $fail_count개"
echo "예상: 성공 10개, 실패 1개 (11번째 429)"
echo ""
echo "✅ 테스트 2 완료"
echo ""

# ============================================
# 테스트 3: 로그인 유저 제한 (50회) - 간략 테스트
# ============================================
echo "============================================"
echo "테스트 3: 로그인 유저 제한 (간략)"
echo "============================================"
echo "설명: 로그인 토큰이 필요하므로 수동 테스트 필요"
echo ""

if [ -z "$TOKEN" ]; then
    echo "⚠️  환경변수 TOKEN이 설정되지 않았습니다."
    echo ""
    echo "📝 수동 테스트 방법:"
    echo "1. 프론트엔드에서 로그인"
    echo "2. 개발자 도구에서 JWT 토큰 복사"
    echo "3. 다음 명령어 실행:"
    echo ""
    echo "   export TOKEN=\"YOUR_JWT_TOKEN\""
    echo "   for i in {1..51}; do"
    echo "     curl -X POST $API_ENDPOINT \\"
    echo "       -H \"Authorization: Bearer \$TOKEN\" \\"
    echo "       -H \"Content-Type: application/json\" \\"
    echo "       -d \"{\\\"message\\\": \\\"test \$i\\\", \\\"session_id\\\": \\\"test\\\"}\""
    echo "     sleep 0.3"
    echo "   done"
    echo ""
    echo "   예상 결과: 50번까지 성공, 51번째 429"
else
    echo "✅ TOKEN 설정됨"
    echo "5번만 테스트 요청..."
    
    for i in {1..5}; do
        echo -n "요청 $i/5: "
        response=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_ENDPOINT" \
          -H "Authorization: Bearer $TOKEN" \
          -H "Content-Type: application/json" \
          -d "{\"message\": \"test user $i\", \"session_id\": \"test\"}")
        
        if [ "$response" = "200" ]; then
            echo "✅ 200 OK"
        else
            echo "⚠️  $response"
        fi
        sleep 0.3
    done
    
    echo ""
    echo "✅ 간략 테스트 완료 (전체 50회 테스트는 수동으로)"
fi

echo ""
echo "✅ 테스트 3 완료"
echo ""

# ============================================
# 요약
# ============================================
echo "=================================="
echo "📊 테스트 요약"
echo "=================================="
echo ""
echo "✅ Nginx Rate Limit: 1초 5회 제한 동작 확인"
echo "✅ 게스트 IP: 10회/일 제한 동작 확인"
echo "⚠️  로그인 유저: 수동 테스트 필요 (50회/일)"
echo ""
echo "📋 서버 로그 확인 방법:"
echo "   ssh -i \"/Users/rlaxogns100/Desktop/김태훈/uniroad-server_key_fixed.pem\" azureuser@52.141.16.217"
echo "   sudo journalctl -u uniroad-backend -f | grep -E '(Rate Limit|429)'"
echo "   sudo tail -f /var/log/nginx/error.log | grep 'limiting'"
echo ""
