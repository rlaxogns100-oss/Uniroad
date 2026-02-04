# 무한사용 방지 설정 배포 가이드

## 📋 배포 순서

### 1. 로컬 코드 변경사항 커밋 & 푸시
```bash
cd /Users/rlaxogns100/Desktop/Projects/uniroad

git add .
git commit -m "feat: 무한사용 방지 설정 구현 (Rate Limiting)"
git push origin develop
```

---

### 2. 서버 SSH 접속
```bash
ssh -i "/Users/rlaxogns100/Desktop/김태훈/uniroad-server_key_fixed.pem" azureuser@52.141.16.217
```

---

### 3. 서버에서 코드 업데이트
```bash
cd /home/azureuser/Uniroad  # 또는 실제 프로젝트 경로
git pull origin develop
```

---

### 4. DB 마이그레이션 실행

#### 방법 A: Supabase 대시보드 사용 (권장)
1. https://supabase.com/dashboard 접속
2. 프로젝트 선택
3. SQL Editor 메뉴 클릭
4. `backend/migrations/08_create_usage_tracking.sql` 파일 내용 복사
5. 붙여넣기 후 실행 (Run 버튼)

#### 방법 B: psql CLI 사용
```bash
# Supabase 연결 정보는 환경변수에서 가져옴
cat backend/migrations/08_create_usage_tracking.sql | \
psql "postgresql://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres"
```

#### 마이그레이션 확인
```sql
-- Supabase SQL Editor에서 실행
SELECT table_name 
FROM information_schema.tables 
WHERE table_name = 'usage_tracking';

-- 테이블 구조 확인
\d usage_tracking
```

---

### 5. 백엔드 재시작
```bash
# 백엔드 서비스 재시작
sudo systemctl restart uniroad-backend

# 로그 확인 (오류 없는지 체크)
sudo journalctl -u uniroad-backend -f --lines=50
```

**중요**: Rate Limit 미들웨어가 정상 로드되는지 확인하세요.

---

### 6. Nginx Rate Limiting 설정

#### 6-1. Nginx 설정 파일 업데이트
```bash
# 기존 설정 백업
sudo cp /etc/nginx/sites-available/uniroad /etc/nginx/sites-available/uniroad.backup

# 새 설정 적용 (로컬에서 deploy-aws.sh 재실행하거나 수동 수정)
# 로컬에서:
./deploy-aws.sh

# 또는 서버에서 수동 수정:
sudo nano /etc/nginx/sites-available/uniroad
```

수정할 내용:
```nginx
# /api/chat/ 섹션을 찾아서 아래처럼 수정
location /api/chat/ {
    # Rate Limiting 추가
    limit_req zone=chat_limit burst=10 nodelay;
    limit_req_status 503;
    
    proxy_pass http://localhost:8000;
    # ... (나머지 설정 유지)
}
```

#### 6-2. Rate Limit Zone 추가
```bash
# nginx.conf 백업
sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup

# http 블록에 Rate Limit Zone 추가
sudo nano /etc/nginx/nginx.conf
```

`http {` 블록 안에 다음 라인 추가:
```nginx
http {
    # ... (기존 설정)
    
    # Rate Limiting Zone
    limit_req_zone $binary_remote_addr zone=chat_limit:10m rate=5r/s;
    
    # ... (나머지 설정)
}
```

또는 **자동 스크립트 사용**:
```bash
# 로컬에서 서버로 파일 전송
scp -i "/Users/rlaxogns100/Desktop/김태훈/uniroad-server_key_fixed.pem" \
    nginx-rate-limit-setup.sh \
    azureuser@52.141.16.217:/home/azureuser/

# 서버에서 실행
chmod +x /home/azureuser/nginx-rate-limit-setup.sh
/home/azureuser/nginx-rate-limit-setup.sh
```

#### 6-3. Nginx 설정 테스트 및 재시작
```bash
# 설정 테스트
sudo nginx -t

# 재시작 (설정 테스트 통과 시)
sudo systemctl reload nginx

# 또는
sudo systemctl restart nginx

# Nginx 상태 확인
sudo systemctl status nginx
```

---

### 7. 동작 테스트

#### 7-1. Nginx Rate Limit 테스트 (로컬에서 실행)
```bash
# 1초에 10번 요청 (5번 초과)
for i in {1..10}; do
  curl -X POST http://52.141.16.217/api/chat/v2/stream \
    -H "Content-Type: application/json" \
    -d '{"message": "test", "session_id": "test"}' &
done

# 예상 결과: 처음 5번(+burst 10) 성공, 나머지 503 Service Unavailable
```

#### 7-2. 로그인 유저 일일 제한 테스트 (50회)
```bash
# 로그인 후 토큰 획득 (프론트엔드에서 로그인 후 개발자 도구에서 확인)
TOKEN="YOUR_JWT_TOKEN_HERE"

# 51번 요청 (Nginx Rate Limit 회피를 위해 sleep 사용)
for i in {1..51}; do
  echo "요청 $i/51"
  curl -X POST http://52.141.16.217/api/chat/v2/stream \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"message\": \"test $i\", \"session_id\": \"test\"}"
  sleep 0.3
done

# 예상 결과: 50번까지 정상, 51번째 429 Too Many Requests
```

#### 7-3. 게스트 IP 제한 테스트 (10회)
```bash
# 토큰 없이 11번 요청
for i in {1..11}; do
  echo "요청 $i/11"
  curl -X POST http://52.141.16.217/api/chat/v2/stream \
    -H "Content-Type: application/json" \
    -d "{\"message\": \"test $i\", \"session_id\": \"guest\"}"
  sleep 0.3
done

# 예상 결과: 10번까지 정상, 11번째 429 Too Many Requests
```

#### 7-4. 로그 확인
```bash
# 백엔드 Rate Limit 로그
sudo journalctl -u uniroad-backend -f | grep -E "(Rate Limit|429)"

# Nginx Rate Limit 로그
sudo tail -f /var/log/nginx/error.log | grep "limiting requests"
```

---

### 8. DB에서 사용량 확인

Supabase SQL Editor에서 실행:

```sql
-- 오늘 사용량 통계
SELECT 
    CASE 
        WHEN user_id IS NOT NULL THEN '로그인 유저'
        ELSE '게스트 (IP: ' || ip_address || ')'
    END AS user_type,
    chat_count,
    last_reset_date,
    created_at
FROM usage_tracking
WHERE last_reset_date = CURRENT_DATE
ORDER BY chat_count DESC
LIMIT 20;

-- 가장 많이 사용한 유저 TOP 10
SELECT 
    u.email,
    ut.chat_count,
    ut.last_reset_date
FROM usage_tracking ut
JOIN auth.users u ON ut.user_id = u.id
WHERE ut.last_reset_date = CURRENT_DATE
ORDER BY ut.chat_count DESC
LIMIT 10;

-- 게스트 IP 사용량 TOP 10
SELECT 
    ip_address,
    chat_count,
    last_reset_date
FROM usage_tracking
WHERE user_id IS NULL
  AND last_reset_date = CURRENT_DATE
ORDER BY chat_count DESC
LIMIT 10;
```

---

## 🚨 문제 해결

### 문제 1: "Table usage_tracking does not exist"
```bash
# DB 마이그레이션이 실행되지 않았습니다.
# → 3단계(DB 마이그레이션)를 다시 실행하세요.
```

### 문제 2: Nginx 503 에러가 너무 자주 발생
```bash
# Rate Limit이 너무 엄격합니다.
# nginx.conf에서 rate 값 조정:
limit_req_zone $binary_remote_addr zone=chat_limit:10m rate=10r/s;  # 5r/s → 10r/s

# 또는 burst 값 증가:
limit_req zone=chat_limit burst=20 nodelay;  # 10 → 20
```

### 문제 3: IP가 "unknown"으로 표시됨
```bash
# Nginx에서 X-Real-IP 헤더를 제대로 전달하지 않습니다.
# /etc/nginx/sites-available/uniroad 확인:
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

# 설정 후 Nginx 재시작
sudo systemctl reload nginx
```

### 문제 4: 백엔드 서비스 시작 실패
```bash
# 로그 확인
sudo journalctl -u uniroad-backend -n 100 --no-pager

# Python 패키지 누락 가능성
cd /home/azureuser/Uniroad/backend
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart uniroad-backend
```

### 문제 5: 특정 유저 사용량 리셋 필요 (긴급)
```sql
-- Supabase SQL Editor에서 실행
UPDATE usage_tracking
SET chat_count = 0
WHERE user_id = 'USER_UUID' 
  AND last_reset_date = CURRENT_DATE;

-- 또는 IP 기반
UPDATE usage_tracking
SET chat_count = 0
WHERE ip_address = '123.45.67.89' 
  AND last_reset_date = CURRENT_DATE;
```

---

## 📊 모니터링

### 실시간 모니터링 명령어
```bash
# 백엔드 로그 실시간 확인
sudo journalctl -u uniroad-backend -f

# Nginx 에러 로그
sudo tail -f /var/log/nginx/error.log

# Nginx Rate Limit 차단 확인
sudo tail -f /var/log/nginx/error.log | grep "limiting requests"

# 백엔드 Rate Limit (429) 확인
sudo journalctl -u uniroad-backend -f | grep "429"
```

### 일일 통계 조회 (Cron Job 설정 가능)
```bash
# 매일 자정 1분 후 실행되도록 설정
crontab -e

# 추가할 내용:
1 0 * * * psql "postgresql://..." -c "SELECT COUNT(*), SUM(chat_count) FROM usage_tracking WHERE last_reset_date = CURRENT_DATE - INTERVAL '1 day';" >> /var/log/uniroad-daily-stats.log
```

---

## ✅ 배포 체크리스트

- [ ] 로컬 코드 변경사항 커밋 & 푸시
- [ ] 서버 SSH 접속 확인
- [ ] 서버에서 코드 업데이트 (git pull)
- [ ] DB 마이그레이션 실행 (usage_tracking 테이블 생성)
- [ ] DB 마이그레이션 확인 (테이블 존재 여부)
- [ ] 백엔드 재시작 및 로그 확인
- [ ] Nginx 설정 파일 업데이트 (/etc/nginx/sites-available/uniroad)
- [ ] Nginx nginx.conf에 Rate Limit Zone 추가
- [ ] Nginx 설정 테스트 (nginx -t)
- [ ] Nginx 재시작
- [ ] Nginx Rate Limit 테스트 (1초 10회 요청)
- [ ] 로그인 유저 제한 테스트 (51회 요청)
- [ ] 게스트 IP 제한 테스트 (11회 요청)
- [ ] 백엔드 로그 확인 (오류 없는지)
- [ ] Nginx 로그 확인 (Rate Limit 동작 확인)
- [ ] DB에서 usage_tracking 데이터 확인

---

## 📝 참고사항

- **자정 초기화**: 미들웨어에서 날짜 체크로 자동 리셋 (Cron Job 불필요)
- **게스트 제한**: 공유 IP(회사, 학교)는 여러 사용자가 10회 공유
- **프리미엄 유저**: 향후 확장 가능 (user_profiles.is_premium 필드 추가)
- **DB 레코드 정리**: 오래된 레코드는 수동 삭제 필요 (월 1회 권장)

```sql
-- 30일 이상 오래된 레코드 삭제
DELETE FROM usage_tracking 
WHERE last_reset_date < CURRENT_DATE - INTERVAL '30 days';
```
