# Agent Testing Framework - AWS 배포 가이드

## 배포 구조

```
https://uni2road.com/agent-test    → Frontend (index.html)
https://uni2road.com/api           → Backend API (FastAPI)
```

## 1. 환경 설정

### Backend 환경 변수
Backend 실행 시 `.env` 파일 필요:

```bash
GEMINI_API_KEY=your_gemini_api_key_here
```

## 2. Backend 배포

### 방법 1: systemd 서비스 (권장)

1. **서비스 파일 생성** (`/etc/systemd/system/agent-test-api.service`):

```ini
[Unit]
Description=Agent Testing Framework API
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/uniroad/agent-tests/unified-framework/backend
Environment="PATH=/usr/bin:/usr/local/bin"
ExecStart=/usr/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8095
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

2. **서비스 시작**:

```bash
sudo systemctl daemon-reload
sudo systemctl enable agent-test-api
sudo systemctl start agent-test-api
sudo systemctl status agent-test-api
```

### 방법 2: PM2 (Node.js 필요)

```bash
cd /path/to/unified-framework/backend
pm2 start "python3 -m uvicorn main:app --host 0.0.0.0 --port 8095" --name agent-test-api
pm2 save
pm2 startup
```

## 3. Nginx 설정

### Frontend + Backend 통합 설정

`/etc/nginx/sites-available/uni2road.com`:

```nginx
server {
    listen 80;
    server_name uni2road.com www.uni2road.com;
    
    # HTTPS 리디렉션
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name uni2road.com www.uni2road.com;
    
    # SSL 인증서 (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/uni2road.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/uni2road.com/privkey.pem;
    
    # Frontend (Agent Testing)
    location /agent-test {
        alias /home/ubuntu/uniroad/agent-tests/unified-framework;
        index index.html;
        try_files $uri $uri/ /agent-test/index.html;
    }
    
    # Backend API (FastAPI)
    location /api/ {
        proxy_pass http://localhost:8095/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # CORS (이미 FastAPI에서 처리하지만 보험)
        add_header 'Access-Control-Allow-Origin' '*' always;
        add_header 'Access-Control-Allow-Methods' 'GET, POST, DELETE, OPTIONS' always;
        add_header 'Access-Control-Allow-Headers' '*' always;
        
        # OPTIONS 요청 처리
        if ($request_method = OPTIONS) {
            return 204;
        }
    }
    
    # 기타 설정
    client_max_body_size 50M;
}
```

### Nginx 재시작

```bash
sudo nginx -t
sudo systemctl restart nginx
```

## 4. SSL 인증서 (Let's Encrypt)

```bash
sudo apt update
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d uni2road.com -d www.uni2road.com
```

자동 갱신 확인:
```bash
sudo certbot renew --dry-run
```

## 5. 파일 업로드

### rsync로 파일 업로드 (로컬에서 실행)

```bash
# Frontend
rsync -avz --exclude 'node_modules' \
  agent-tests/unified-framework/index.html \
  ubuntu@your-server-ip:/home/ubuntu/uniroad/agent-tests/unified-framework/

# Backend
rsync -avz --exclude '__pycache__' --exclude '*.pyc' \
  agent-tests/unified-framework/backend/ \
  ubuntu@your-server-ip:/home/ubuntu/uniroad/agent-tests/unified-framework/backend/
```

### 또는 Git Pull (서버에서 실행)

```bash
cd /home/ubuntu/uniroad
git pull origin main
```

## 6. 의존성 설치 (서버에서 실행)

```bash
cd /home/ubuntu/uniroad/agent-tests/unified-framework/backend
pip3 install -r requirements.txt
```

## 7. 배포 후 확인

1. **Backend API 테스트**:
   ```bash
   curl https://uni2road.com/api/health
   # 응답: {"status":"ok","api_key_configured":true}
   ```

2. **Frontend 접속**:
   - https://uni2road.com/agent-test

3. **브라우저 개발자 도구**에서 API 호출 확인:
   - Network 탭에서 `https://uni2road.com/api/...` 요청 확인

## 8. 트러블슈팅

### Backend가 시작되지 않는 경우

```bash
# 로그 확인
sudo journalctl -u agent-test-api -f

# 수동 실행으로 에러 확인
cd /home/ubuntu/uniroad/agent-tests/unified-framework/backend
python3 -m uvicorn main:app --host 0.0.0.0 --port 8095
```

### CORS 에러

- Backend CORS 설정은 이미 `allow_origins=["*"]`로 모든 origin 허용
- Nginx 설정에서 OPTIONS 요청 처리 확인

### API 호출 실패

1. Backend 서비스 상태 확인:
   ```bash
   sudo systemctl status agent-test-api
   ```

2. 포트 리스닝 확인:
   ```bash
   sudo netstat -tulpn | grep 8095
   ```

3. 방화벽 확인 (AWS Security Group):
   - 인바운드: 포트 80, 443 허용
   - 포트 8095는 localhost에서만 접근 (Nginx를 통해서만)

## 9. 자동 배포 스크립트 (옵션)

로컬에서 실행할 배포 스크립트 (`deploy.sh`):

```bash
#!/bin/bash
set -e

SERVER="ubuntu@your-server-ip"
REMOTE_PATH="/home/ubuntu/uniroad/agent-tests/unified-framework"

echo "📦 Deploying to production..."

# 1. Frontend 업로드
echo "📤 Uploading frontend..."
rsync -avz --exclude 'node_modules' \
  index.html \
  ${SERVER}:${REMOTE_PATH}/

# 2. Backend 업로드
echo "📤 Uploading backend..."
rsync -avz --exclude '__pycache__' --exclude '*.pyc' \
  backend/ \
  ${SERVER}:${REMOTE_PATH}/backend/

# 3. Backend 재시작
echo "🔄 Restarting backend service..."
ssh ${SERVER} "sudo systemctl restart agent-test-api"

# 4. 상태 확인
echo "✅ Deployment complete!"
echo "🔍 Checking service status..."
ssh ${SERVER} "sudo systemctl status agent-test-api --no-pager"

echo "
🎉 Deployment successful!
📍 Frontend: https://uni2road.com/agent-test
📍 API: https://uni2road.com/api/health
"
```

사용법:
```bash
chmod +x deploy.sh
./deploy.sh
```

## 10. 모니터링

### 로그 실시간 확인

```bash
# Backend 로그
sudo journalctl -u agent-test-api -f

# Nginx 로그
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### 성능 모니터링

```bash
# 프로세스 확인
ps aux | grep uvicorn

# 메모리/CPU 사용량
htop
```
