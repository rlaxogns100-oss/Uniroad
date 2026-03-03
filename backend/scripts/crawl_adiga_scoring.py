#!/usr/bin/env python3
"""
대입정보포털(어디가) 환산점수 산출 기능 크롤링 스크립트.

목표:
- adiga.kr 로그인 후 대학성적분석 메뉴 접근
- 대학별 환산점수 계산 공식/데이터 추출
- JSON 형태로 저장

사용법:
    python crawl_adiga_scoring.py --username YOUR_ID --password YOUR_PW
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from playwright.async_api import async_playwright, Page, Browser
except ImportError:
    print("Playwright가 설치되어 있지 않습니다.")
    print("설치: pip install playwright && playwright install chromium")
    sys.exit(1)

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE_DIR / "data" / "adiga_crawl"


class AdigaCrawler:
    """대입정보포털 크롤러"""
    
    BASE_URL = "https://www.adiga.kr"
    LOGIN_URL = f"{BASE_URL}/mbs/log/mbsLogView.do?menuId=PCMBSLOG1000"
    SCORE_ANALYSIS_URL = f"{BASE_URL}/sco/agu/univScoScaAnlsView.do?menuId=PCSCOAGU2000"
    SCORE_CATEGORY_URL = f"{BASE_URL}/sco/agu/univScoCatAnlsView.do?menuId=PCSCOAGU3000"
    
    def __init__(self, username: str, password: str, headless: bool = True):
        self.username = username
        self.password = password
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.results: Dict[str, Any] = {
            "crawl_time": datetime.now().isoformat(),
            "universities": [],
            "scoring_formulas": [],
            "api_endpoints": [],
            "errors": [],
        }
    
    async def start(self):
        """브라우저 시작"""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self.page = await context.new_page()
        
        # 네트워크 요청 모니터링 (API 엔드포인트 수집)
        self.page.on("request", self._on_request)
        self.page.on("response", self._on_response)
        
        print(f"[INFO] 브라우저 시작 (headless={self.headless})")
    
    async def _on_request(self, request):
        """API 요청 모니터링"""
        url = request.url
        if "/sco/" in url or "/agu/" in url:
            self.results["api_endpoints"].append({
                "url": url,
                "method": request.method,
                "type": "request",
            })
    
    async def _on_response(self, response):
        """API 응답 모니터링"""
        url = response.url
        if "/sco/" in url or "/agu/" in url:
            try:
                content_type = response.headers.get("content-type", "")
                if "json" in content_type:
                    body = await response.json()
                    self.results["api_endpoints"].append({
                        "url": url,
                        "status": response.status,
                        "type": "response",
                        "data_sample": str(body)[:500] if body else None,
                    })
            except Exception:
                pass
    
    async def login(self) -> bool:
        """로그인 수행"""
        print(f"[INFO] 로그인 페이지 접속: {self.LOGIN_URL}")
        
        try:
            await self.page.goto(self.LOGIN_URL, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)
            
            # 로그인 폼 찾기
            # 아이디 입력
            id_input = await self.page.query_selector('input[name="userId"]')
            if not id_input:
                id_input = await self.page.query_selector('input[id="userId"]')
            if not id_input:
                id_input = await self.page.query_selector('input[type="text"]')
            
            if id_input:
                await id_input.fill(self.username)
                print(f"[INFO] 아이디 입력 완료")
            else:
                print("[ERROR] 아이디 입력 필드를 찾을 수 없습니다.")
                # 페이지 HTML 저장
                html = await self.page.content()
                self.results["errors"].append({
                    "step": "login",
                    "error": "id_input_not_found",
                    "html_sample": html[:2000],
                })
                return False
            
            # 비밀번호 입력
            pw_input = await self.page.query_selector('input[name="userPw"]')
            if not pw_input:
                pw_input = await self.page.query_selector('input[id="userPw"]')
            if not pw_input:
                pw_input = await self.page.query_selector('input[type="password"]')
            
            if pw_input:
                await pw_input.fill(self.password)
                print(f"[INFO] 비밀번호 입력 완료")
            else:
                print("[ERROR] 비밀번호 입력 필드를 찾을 수 없습니다.")
                return False
            
            # 로그인 버튼 클릭
            login_btn = await self.page.query_selector('button[type="submit"]')
            if not login_btn:
                login_btn = await self.page.query_selector('a.btn_login')
            if not login_btn:
                login_btn = await self.page.query_selector('button:has-text("로그인")')
            if not login_btn:
                # JavaScript로 로그인 함수 직접 호출 시도
                await self.page.evaluate("fnLogin && fnLogin()")
            else:
                await login_btn.click()
            
            await asyncio.sleep(3)
            
            # 로그인 성공 확인
            current_url = self.page.url
            page_content = await self.page.content()
            
            if "로그아웃" in page_content or "마이페이지" in page_content:
                print("[SUCCESS] 로그인 성공!")
                return True
            else:
                print("[WARNING] 로그인 상태 확인 필요")
                # 스크린샷 저장
                screenshot_path = OUTPUT_DIR / "login_result.png"
                await self.page.screenshot(path=str(screenshot_path))
                print(f"[INFO] 스크린샷 저장: {screenshot_path}")
                return True  # 일단 진행
                
        except Exception as e:
            print(f"[ERROR] 로그인 실패: {e}")
            self.results["errors"].append({
                "step": "login",
                "error": str(e),
            })
            return False
    
    async def navigate_to_score_analysis(self) -> bool:
        """대학성적분석 페이지로 이동"""
        print(f"[INFO] 대학성적분석 페이지 접속: {self.SCORE_ANALYSIS_URL}")
        
        try:
            await self.page.goto(self.SCORE_ANALYSIS_URL, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)
            
            # 스크린샷 저장
            screenshot_path = OUTPUT_DIR / "score_analysis_page.png"
            await self.page.screenshot(path=str(screenshot_path))
            print(f"[INFO] 스크린샷 저장: {screenshot_path}")
            
            # 페이지 HTML 저장
            html = await self.page.content()
            html_path = OUTPUT_DIR / "score_analysis_page.html"
            html_path.write_text(html, encoding="utf-8")
            print(f"[INFO] HTML 저장: {html_path}")
            
            return True
            
        except Exception as e:
            print(f"[ERROR] 페이지 이동 실패: {e}")
            self.results["errors"].append({
                "step": "navigate_score_analysis",
                "error": str(e),
            })
            return False
    
    async def extract_university_list(self) -> List[Dict[str, Any]]:
        """대학 목록 추출"""
        print("[INFO] 대학 목록 추출 시도...")
        
        universities = []
        
        try:
            # 대학 선택 드롭다운 또는 목록 찾기
            selectors = [
                'select[name*="univ"]',
                'select[id*="univ"]',
                'select[name*="school"]',
                '.univ-list',
                '#univList',
                'select.univ-select',
            ]
            
            for selector in selectors:
                elements = await self.page.query_selector_all(selector)
                if elements:
                    print(f"[INFO] 대학 목록 요소 발견: {selector}")
                    for el in elements:
                        options = await el.query_selector_all("option")
                        for opt in options:
                            value = await opt.get_attribute("value")
                            text = await opt.inner_text()
                            if value and text and text.strip():
                                universities.append({
                                    "code": value,
                                    "name": text.strip(),
                                })
                    break
            
            # JavaScript로 대학 데이터 추출 시도
            if not universities:
                js_data = await self.page.evaluate("""
                    () => {
                        // 전역 변수에서 대학 데이터 찾기
                        const results = [];
                        
                        // 일반적인 변수명 패턴
                        const varNames = ['univList', 'schoolList', 'univData', 'universities'];
                        for (const name of varNames) {
                            if (window[name] && Array.isArray(window[name])) {
                                return window[name];
                            }
                        }
                        
                        // select 요소에서 추출
                        const selects = document.querySelectorAll('select');
                        for (const sel of selects) {
                            if (sel.options.length > 10) {
                                for (const opt of sel.options) {
                                    if (opt.value && opt.text) {
                                        results.push({code: opt.value, name: opt.text});
                                    }
                                }
                                if (results.length > 0) return results;
                            }
                        }
                        
                        return results;
                    }
                """)
                if js_data:
                    universities = js_data
            
            print(f"[INFO] 추출된 대학 수: {len(universities)}")
            self.results["universities"] = universities
            
        except Exception as e:
            print(f"[ERROR] 대학 목록 추출 실패: {e}")
            self.results["errors"].append({
                "step": "extract_university_list",
                "error": str(e),
            })
        
        return universities
    
    async def extract_scoring_formulas(self) -> List[Dict[str, Any]]:
        """환산점수 계산 공식 추출"""
        print("[INFO] 환산점수 공식 추출 시도...")
        
        formulas = []
        
        try:
            # JavaScript 파일에서 계산 로직 추출
            scripts = await self.page.query_selector_all("script")
            for script in scripts:
                src = await script.get_attribute("src")
                content = await script.inner_text()
                
                # 환산 관련 키워드가 포함된 스크립트 찾기
                keywords = ["환산", "계산", "score", "calc", "formula", "convert"]
                
                if src:
                    for kw in keywords:
                        if kw in src.lower():
                            print(f"[INFO] 관련 스크립트 발견: {src}")
                            # 스크립트 파일 다운로드
                            try:
                                script_url = src if src.startswith("http") else f"{self.BASE_URL}{src}"
                                await self.page.goto(script_url)
                                script_content = await self.page.content()
                                formulas.append({
                                    "type": "script_file",
                                    "url": script_url,
                                    "content_sample": script_content[:5000],
                                })
                            except Exception:
                                pass
                            break
                
                if content:
                    for kw in keywords:
                        if kw in content.lower():
                            formulas.append({
                                "type": "inline_script",
                                "content_sample": content[:5000],
                            })
                            break
            
            # 페이지 내 계산 함수 추출
            js_functions = await self.page.evaluate("""
                () => {
                    const results = [];
                    const funcNames = Object.keys(window).filter(k => {
                        const v = window[k];
                        return typeof v === 'function' && 
                               (k.includes('calc') || k.includes('score') || 
                                k.includes('convert') || k.includes('환산'));
                    });
                    
                    for (const name of funcNames) {
                        try {
                            results.push({
                                name: name,
                                source: window[name].toString().substring(0, 2000)
                            });
                        } catch (e) {}
                    }
                    
                    return results;
                }
            """)
            
            if js_functions:
                for func in js_functions:
                    formulas.append({
                        "type": "js_function",
                        "name": func.get("name"),
                        "source": func.get("source"),
                    })
            
            print(f"[INFO] 추출된 공식/함수 수: {len(formulas)}")
            self.results["scoring_formulas"] = formulas
            
        except Exception as e:
            print(f"[ERROR] 공식 추출 실패: {e}")
            self.results["errors"].append({
                "step": "extract_scoring_formulas",
                "error": str(e),
            })
        
        return formulas
    
    async def analyze_network_apis(self) -> List[Dict[str, Any]]:
        """네트워크 API 분석"""
        print("[INFO] API 엔드포인트 분석...")
        
        # 페이지에서 다양한 액션 수행하여 API 호출 유도
        try:
            # 탭/버튼 클릭
            tabs = await self.page.query_selector_all(".tab, .menu-item, button")
            for tab in tabs[:5]:
                try:
                    await tab.click()
                    await asyncio.sleep(1)
                except Exception:
                    pass
            
            # 드롭다운 변경
            selects = await self.page.query_selector_all("select")
            for sel in selects[:3]:
                try:
                    options = await sel.query_selector_all("option")
                    if len(options) > 1:
                        await options[1].click()
                        await asyncio.sleep(1)
                except Exception:
                    pass
                    
        except Exception as e:
            print(f"[WARNING] API 분석 중 오류: {e}")
        
        # 수집된 API 엔드포인트 정리
        unique_apis = {}
        for api in self.results["api_endpoints"]:
            url = api.get("url", "")
            if url not in unique_apis:
                unique_apis[url] = api
        
        self.results["api_endpoints"] = list(unique_apis.values())
        print(f"[INFO] 수집된 고유 API 엔드포인트: {len(unique_apis)}")
        
        return self.results["api_endpoints"]
    
    async def close(self):
        """브라우저 종료"""
        if self.browser:
            await self.browser.close()
            print("[INFO] 브라우저 종료")
    
    async def run(self) -> Dict[str, Any]:
        """전체 크롤링 실행"""
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        try:
            await self.start()
            
            # 1. 로그인
            login_success = await self.login()
            if not login_success:
                print("[WARNING] 로그인 실패, 비로그인 상태로 진행")
            
            # 2. 대학성적분석 페이지 이동
            await self.navigate_to_score_analysis()
            
            # 3. 대학 목록 추출
            await self.extract_university_list()
            
            # 4. 환산점수 공식 추출
            await self.extract_scoring_formulas()
            
            # 5. API 분석
            await self.analyze_network_apis()
            
        except Exception as e:
            print(f"[ERROR] 크롤링 실패: {e}")
            self.results["errors"].append({
                "step": "run",
                "error": str(e),
            })
        finally:
            await self.close()
        
        # 결과 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = OUTPUT_DIR / f"adiga_crawl_{timestamp}.json"
        output_path.write_text(
            json.dumps(self.results, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"[INFO] 결과 저장: {output_path}")
        
        return self.results


async def main():
    parser = argparse.ArgumentParser(description="대입정보포털 환산점수 크롤러")
    parser.add_argument("--username", "-u", required=True, help="로그인 아이디")
    parser.add_argument("--password", "-p", required=True, help="로그인 비밀번호")
    parser.add_argument("--headless", action="store_true", default=True, help="헤드리스 모드")
    parser.add_argument("--no-headless", dest="headless", action="store_false", help="브라우저 표시")
    args = parser.parse_args()
    
    crawler = AdigaCrawler(
        username=args.username,
        password=args.password,
        headless=args.headless,
    )
    
    results = await crawler.run()
    
    # 요약 출력
    print("\n" + "=" * 50)
    print("크롤링 결과 요약")
    print("=" * 50)
    print(f"대학 수: {len(results.get('universities', []))}")
    print(f"환산 공식/함수 수: {len(results.get('scoring_formulas', []))}")
    print(f"API 엔드포인트 수: {len(results.get('api_endpoints', []))}")
    print(f"오류 수: {len(results.get('errors', []))}")
    
    if results.get("errors"):
        print("\n오류 목록:")
        for err in results["errors"]:
            print(f"  - {err.get('step')}: {err.get('error')}")


if __name__ == "__main__":
    asyncio.run(main())
