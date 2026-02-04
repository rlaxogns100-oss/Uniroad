#!/bin/bash

echo "🚀 유니로드 서버 시작"
echo "="
echo ""

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 터미널 창으로 실행
if command -v osascript &> /dev/null; then
    # macOS
    echo "📱 macOS 감지 - 터미널 3개 자동 실행"
    
    # 백엔드 터미널
    osascript -e 'tell application "Terminal"
        do script "cd \"'$PROJECT_DIR'/backend\" && python3 main.py"
    end tell'
    
    # 프론트엔드 터미널 (본 프로젝트)
    osascript -e 'tell application "Terminal"
        do script "cd \"'$PROJECT_DIR'/frontend\" && npm run dev"
    end tell'
    
    echo "✅ 서버 시작 완료!"
    echo ""
    echo "📍 접속 주소:"
    echo "   프론트엔드: http://localhost:5173"
    echo "   백엔드 API: http://localhost:8000"
    echo "   API 문서: http://localhost:8000/docs"
else
    # Linux/기타
    echo "⚠️  수동으로 2개 터미널에서 실행하세요:"
    echo ""
    echo "터미널 1 (백엔드):"
    echo "  cd $PROJECT_DIR/backend"
    echo "  python3 main.py"
    echo ""
    echo "터미널 2 (수능 계산기):"
    echo "  cd $PROJECT_DIR/suneung-calculator"
    echo "  python3 -m http.server 8080"
fi

echo ""
