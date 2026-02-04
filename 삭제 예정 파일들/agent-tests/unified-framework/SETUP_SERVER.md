# AWS 서버 초기 설정 가이드

## 1. 서버 접속

```bash
ssh ubuntu@your-server-ip
```

## 2. 시스템 업데이트

```bash
sudo apt update && sudo apt upgrade -y
```

## 3. 필수 패키지 설치

```bash
# Python 및 pip
sudo apt install -y python3 python3-pip python3-venv

# Git
sudo apt install -y git

# Nginx
sudo apt install -y nginx

# 기타 유틸리티
sudo apt install -y curl wget htop
```

## 4. 프로젝트 클론

```bash
cd /home/ubuntu
git clone https://github.com/your-username/uniroad.git
cd uniroad
```

## 5. 환경 변수 설정

```bash
# Backend .env 파일 생성
cd /home/ubuntu/uniroad/agent-tests/unified-framework/backend
nano .env
```

`.env` 파일 내용:
```
GEMINI_API_KEY=your_actual_gemini_api_key_here
```

## 6. Python 의존성 설치

```bash
cd /home/ubuntu/uniroad/agent-tests/unified-framework/backend
pip3 install -r requirements.txt
```

## 7. systemd 서비스 설정

```bash
# 서비스 파일 복사
sudo cp /home/ubuntu/uniroad/agent-tests/unified-framework/backend/agent-test-api.service \
  /etc/systemd/system/agent-test-api.service

# 서비스 파일 수정 (필요 시 경로 조정)
sudo nano /etc/systemd/system/agent-test-api.service

# 서비스 활성화
sudo systemctl daemon-reload
sudo systemctl enable agent-test-api
sudo systemctl start agent-test-api

# 상태 확인
sudo systemctl status agent-test-api
```

## 8. Nginx 설정

```bash
# Nginx 설정 파일 복사
sudo cp /home/ubuntu/uniroad/agent-tests/unified-framework/nginx.conf \
  /etc/nginx/sites-available/uni2road.com

# 심볼릭 링크 생성
sudo ln -s /etc/nginx/sites-available/uni2road.com \
  /etc/nginx/sites-enabled/uni2road.com

# 기본 설정 비활성화 (충돌 방지)
sudo rm -f /etc/nginx/sites-enabled/default

# 설정 테스트
sudo nginx -t

# Nginx 재시작
sudo systemctl restart nginx
```

## 9. SSL 인증서 설치 (Let's Encrypt)

```bash
# Certbot 설치
sudo apt install -y certbot python3-certbot-nginx

# SSL 인증서 발급
sudo certbot --nginx -d uni2road.com -d www.uni2road.com

# 이메일 입력 및 약관 동의 프롬프트 따라가기
```

## 10. 방화벽 설정 (AWS Security Group)

AWS 콘솔에서 Security Group 설정:

**Inbound Rules:**
- Type: HTTP (80) - Source: 0.0.0.0/0
- Type: HTTPS (443) - Source: 0.0.0.0/0
- Type: SSH (22) - Source: Your IP (보안상 특정 IP만 허용 권장)

**주의:** 포트 8095는 **열지 마세요** (Nginx를 통해서만 접근)

## 11. 테스트

### Backend API 테스트

```bash
curl http://localhost:8095/health
# 예상 응답: {"status":"ok","api_key_configured":true}

curl https://uni2road.com/api/health
# 예상 응답: {"status":"ok","api_key_configured":true}
```

### Frontend 접속 테스트

브라우저에서:
- https://uni2road.com/agent-test

## 12. 로그 확인

```bash
# Backend 로그
sudo journalctl -u agent-test-api -f

# Nginx 로그
sudo tail -f /var/log/nginx/uni2road_access.log
sudo tail -f /var/log/nginx/uni2road_error.log
```

## 13. 자동 갱신 설정 (SSL)

Certbot은 자동으로 cron/systemd timer로 설정됩니다. 확인:

```bash
sudo certbot renew --dry-run
```

## 14. 서비스 관리 명령어

### Backend 서비스

```bash
# 시작
sudo systemctl start agent-test-api

# 중지
sudo systemctl stop agent-test-api

# 재시작
sudo systemctl restart agent-test-api

# 상태 확인
sudo systemctl status agent-test-api

# 로그 확인
sudo journalctl -u agent-test-api -f
```

### Nginx

```bash
# 시작
sudo systemctl start nginx

# 중지
sudo systemctl stop nginx

# 재시작
sudo systemctl restart nginx

# 설정 테스트
sudo nginx -t

# 설정 리로드 (다운타임 없음)
sudo systemctl reload nginx
```

## 15. 업데이트 배포

코드 변경 후 배포:

```bash
# 방법 1: 로컬에서 deploy.sh 실행
./deploy.sh

# 방법 2: 서버에서 직접 pull
ssh ubuntu@your-server-ip
cd /home/ubuntu/uniroad
git pull origin main
sudo systemctl restart agent-test-api
```

## 16. 트러블슈팅

### Backend 실행 안 됨

```bash
# 로그 확인
sudo journalctl -u agent-test-api -n 100 --no-pager

# 수동 실행으로 에러 확인
cd /home/ubuntu/uniroad/agent-tests/unified-framework/backend
python3 -m uvicorn main:app --host 0.0.0.0 --port 8095
```

### 포트 확인

```bash
sudo netstat -tulpn | grep 8095
```

### 프로세스 확인

```bash
ps aux | grep uvicorn
```

## 완료! 🎉

이제 https://uni2road.com/agent-test 에서 Agent Testing Framework를 사용할 수 있습니다!
