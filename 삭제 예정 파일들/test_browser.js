const puppeteer = require('puppeteer');

(async () => {
  console.log('🚀 브라우저 테스트 시작...');
  
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  
  try {
    const page = await browser.newPage();
    
    // 콘솔 로그 캡처 (오류, 경고, 중요 메시지만)
    page.on('console', msg => {
      const text = msg.text();
      const type = msg.type();
      
      // error, warning, 또는 중요 키워드가 있는 경우만 출력
      if (type === 'error' || type === 'warning' || 
          text.includes('오류') || text.includes('에러') || text.includes('Error') ||
          text.includes('📤') || text.includes('✅') || text.includes('🚫') ||
          text.includes('API') || text.includes('스트리밍') || text.includes('답변')) {
        console.log(`  [${type}]`, text);
      }
    });
    
    // 에러 캡처
    page.on('pageerror', error => {
      console.error('  [브라우저 에러]', error.message);
    });
    
    // 네트워크 요청 모니터링
    page.on('request', request => {
      const url = request.url();
      if (url.includes('/api/chat/stream')) {
        console.log(`  [요청] POST ${url}`);
      }
    });
    
    page.on('response', async response => {
      const url = response.url();
      if (url.includes('/api/chat/stream')) {
        console.log(`  [응답] ${response.status()} ${url}`);
        if (response.status() !== 200) {
          try {
            const text = await response.text();
            console.error(`  [응답 내용] ${text.substring(0, 200)}`);
          } catch (e) {}
        }
      }
    });
    
    page.on('requestfailed', request => {
      const url = request.url();
      if (url.includes('/api/')) {
        console.error(`  [요청 실패] ${url} - ${request.failure()?.errorText}`);
      }
    });
    
    console.log('📱 페이지 로딩 중...');
    await page.goto('http://localhost:5173', { 
      waitUntil: 'networkidle2',
      timeout: 10000 
    });
    
    console.log('✅ 페이지 로드 완료');
    
    // 입력창 찾기 (placeholder로 정확하게 찾기)
    console.log('🔍 입력창 찾는 중...');
    await page.waitForSelector('input[placeholder*="유니로드"]', { timeout: 5000 });
    
    // 메시지 입력
    console.log('⌨️  메시지 입력 중: "서울대 물리학과"');
    await page.type('input[placeholder*="유니로드"]', '서울대 물리학과');
    
    // 전송 버튼 찾기 (입력창 다음에 있는 bg-blue-600 버튼)
    console.log('🔍 전송 버튼 찾는 중...');
    const sendButton = await page.evaluateHandle(() => {
      const input = document.querySelector('input[placeholder*="유니로드"]');
      const container = input?.closest('.flex');
      const button = container?.querySelector('button.bg-blue-600');
      return button;
    });
    
    if (!sendButton) {
      throw new Error('전송 버튼을 찾을 수 없습니다');
    }
    
    // 버튼 상태 확인
    const buttonInfo = await page.evaluate((btn) => {
      return {
        disabled: btn.disabled,
        className: btn.className.substring(0, 100),
        innerHTML: btn.innerHTML.substring(0, 50)
      };
    }, sendButton);
    console.log('  버튼 정보:', buttonInfo);
    
    console.log('📤 메시지 전송...');
    await sendButton.click();
    
    // 클릭 후 약간 대기
    await new Promise(resolve => setTimeout(resolve, 1000));
    console.log('  클릭 완료, 1초 대기...');
    
    // 답변 대기 (최대 60초, Sub Agent 실행 포함)
    console.log('⏳ 답변 대기 중 (Sub Agent 쿼리는 최대 60초 소요)...');
    
    let lastMessageCount = 0;
    const startTime = Date.now();
    
    await page.waitForFunction(
      () => {
        // ChatMessage 컴포넌트로 렌더링된 메시지를 찾기
        const messageDivs = Array.from(document.querySelectorAll('.rounded-2xl'));
        if (messageDivs.length < 2) return false;
        
        // 두 번째 메시지(봇 답변)의 내용 확인
        const botMessage = messageDivs[1];
        const text = botMessage.textContent || '';
        
        // 에러 메시지가 나온 경우 즉시 반환
        if (text.includes('오류가 발생') || text.includes('다시 시도')) {
          return true; // 에러 발생
        }
        
        // "생각하는 과정" 또는 "처리 중"이 아닌 실제 답변인지 확인
        return !text.includes('생각 중') && 
               !text.includes('처리 중') && 
               !text.includes('질문을 분석') &&
               text.length > 50; // 최소 50자 이상의 답변
      },
      { timeout: 60000 }
    );
    
    const elapsedTime = ((Date.now() - startTime) / 1000).toFixed(1);
    console.log(`  답변 수신 완료 (소요 시간: ${elapsedTime}초)`);
    
    // 메시지 내용 확인
    const messages = await page.evaluate(() => {
      const msgDivs = Array.from(document.querySelectorAll('.rounded-2xl'));
      return msgDivs.map(msg => ({
        text: msg.textContent?.substring(0, 100),
        isError: msg.textContent?.includes('오류') || msg.textContent?.includes('에러'),
        isUser: msg.classList.contains('bg-blue-600')
      }));
    });
    
    console.log('\n📝 화면에 표시된 메시지:');
    messages.forEach((msg, i) => {
      console.log(`  ${i + 1}. ${msg.text}`);
      if (msg.isError) {
        console.error('  ❌ 에러 메시지 발견!');
      }
    });
    
    // 스크린샷 저장
    await page.screenshot({ 
      path: '/tmp/browser_test_result.png',
      fullPage: true 
    });
    console.log('\n📸 스크린샷 저장: /tmp/browser_test_result.png');
    
    // 에러 메시지가 있는지 확인
    const hasError = messages.some(msg => msg.isError);
    if (hasError) {
      console.error('\n❌ 테스트 실패: 에러 메시지가 표시됨');
      process.exit(1);
    } else {
      console.log('\n✅ 테스트 성공: 정상 답변 표시됨');
    }
    
  } catch (error) {
    console.error('\n❌ 테스트 실패:', error.message);
    
    // 에러 발생 시에도 스크린샷 저장
    try {
      const page = (await browser.pages())[0];
      if (page) {
        await page.screenshot({ 
          path: '/tmp/browser_test_error.png',
          fullPage: true 
        });
        console.log('📸 에러 스크린샷 저장: /tmp/browser_test_error.png');
      }
    } catch (e) {}
    
    process.exit(1);
  } finally {
    await browser.close();
  }
})();
