#!/usr/bin/env python3
"""
대입정보포털(어디가) 환산점수 산출 상세 크롤링 스크립트 v2.

목표:
- 로그인 후 대학성적분석 > 정시 분석 페이지 접근
- 대학별 환산점수 산출 상세 정보 추출
- 계산 공식, 반영비율, 가산점 등 추출

사용법:
    python crawl_adiga_scoring_v2.py --username YOUR_ID --password YOUR_PW
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
from urllib.parse import urljoin

try:
    from playwright.async_api import async_playwright, Page, Browser, Response
except ImportError:
    print("Playwright가 설치되어 있지 않습니다.")
    print("설치: pip install playwright && playwright install chromium")
    sys.exit(1)

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE_DIR / "data" / "adiga_crawl"


class AdigaScoringCrawler:
    """대입정보포털 환산점수 상세 크롤러"""
    
    BASE_URL = "https://www.adiga.kr"
    LOGIN_URL = f"{BASE_URL}/mbs/log/mbsLogView.do?menuId=PCMBSLOG1000"
    
    # 정시 성적분석 관련 URL
    SCORE_ANALYSIS_URL = f"{BASE_URL}/sco/agu/univScoScaAnlsView.do?menuId=PCSCOAGU2000"
    SCORE_CATEGORY_URL = f"{BASE_URL}/sco/agu/univScoCatAnlsView.do?menuId=PCSCOAGU3000"
    
    # API 엔드포인트
    UNIV_GROUP_API = f"{BASE_URL}/sco/agu/univScoCatUnivGroupAjax.do"
    UNIV_LIST_API = f"{BASE_URL}/sco/agu/univScoCatUnivListAjax.do"
    SCORE_DETAIL_API = f"{BASE_URL}/sco/agu/univScoCatAnalsDetail.do"
    
    def __init__(self, username: str, password: str, headless: bool = True):
        self.username = username
        self.password = password
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.context = None
        self.api_responses: List[Dict[str, Any]] = []
        self.results: Dict[str, Any] = {
            "crawl_time": datetime.now().isoformat(),
            "universities": [],
            "scoring_details": [],
            "api_data": [],
            "errors": [],
        }
    
    async def start(self):
        """브라우저 시작"""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"]
        )
        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self.page = await self.context.new_page()
        
        # 모든 응답 캡처
        self.page.on("response", self._capture_response)
        
        print(f"[INFO] 브라우저 시작 (headless={self.headless})")
    
    async def _capture_response(self, response: Response):
        """API 응답 캡처"""
        url = response.url
        # 성적분석 관련 API만 캡처
        if any(x in url for x in ["/sco/", "/agu/", "Anls", "Score", "Univ"]):
            try:
                content_type = response.headers.get("content-type", "")
                if "json" in content_type or "html" in content_type:
                    try:
                        if "json" in content_type:
                            body = await response.json()
                        else:
                            body = await response.text()
                        self.api_responses.append({
                            "url": url,
                            "status": response.status,
                            "content_type": content_type,
                            "body": body if isinstance(body, dict) else body[:10000] if len(body) > 10000 else body,
                        })
                    except Exception:
                        pass
            except Exception:
                pass
    
    async def login(self) -> bool:
        """로그인 수행"""
        print(f"[INFO] 로그인 페이지 접속: {self.LOGIN_URL}")
        
        try:
            await self.page.goto(self.LOGIN_URL, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)
            
            # 아이디 입력
            await self.page.fill('input[type="text"]', self.username)
            print(f"[INFO] 아이디 입력 완료")
            
            # 비밀번호 입력
            await self.page.fill('input[type="password"]', self.password)
            print(f"[INFO] 비밀번호 입력 완료")
            
            # 로그인 버튼 클릭
            await self.page.click('button[type="submit"], a.btn_login, button:has-text("로그인")')
            await asyncio.sleep(3)
            
            # 로그인 확인
            page_content = await self.page.content()
            if "로그아웃" in page_content or "마이페이지" in page_content:
                print("[SUCCESS] 로그인 성공!")
                return True
            else:
                print("[WARNING] 로그인 상태 불확실, 계속 진행")
                return True
                
        except Exception as e:
            print(f"[ERROR] 로그인 실패: {e}")
            self.results["errors"].append({"step": "login", "error": str(e)})
            return False
    
    async def navigate_to_jungsi_analysis(self) -> bool:
        """정시 성적분석 페이지로 이동"""
        print(f"[INFO] 정시 성적분석 페이지 접속")
        
        try:
            # 대학성적분석 페이지로 이동
            await self.page.goto(self.SCORE_CATEGORY_URL, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)
            
            # 스크린샷 저장
            screenshot_path = OUTPUT_DIR / "jungsi_analysis_page.png"
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            print(f"[INFO] 스크린샷 저장: {screenshot_path}")
            
            return True
            
        except Exception as e:
            print(f"[ERROR] 페이지 이동 실패: {e}")
            self.results["errors"].append({"step": "navigate_jungsi", "error": str(e)})
            return False
    
    async def get_university_groups(self) -> List[Dict[str, Any]]:
        """대학 그룹(가나다군) 목록 가져오기"""
        print("[INFO] 대학 그룹 목록 조회...")
        
        groups = []
        try:
            # AJAX 요청으로 대학 그룹 가져오기
            response = await self.page.evaluate("""
                async () => {
                    const formData = new FormData();
                    formData.append('_csrf', document.querySelector("meta[name='_csrf']")?.getAttribute("content") || '');
                    
                    const response = await fetch('/sco/agu/univScoCatUnivGroupAjax.do', {
                        method: 'POST',
                        body: formData
                    });
                    return await response.text();
                }
            """)
            
            if response:
                groups.append({"type": "group_response", "data": response[:5000]})
                print(f"[INFO] 대학 그룹 응답 수신")
                
        except Exception as e:
            print(f"[WARNING] 대학 그룹 조회 실패: {e}")
        
        return groups
    
    async def extract_scoring_calculation_logic(self) -> List[Dict[str, Any]]:
        """환산점수 계산 로직 추출"""
        print("[INFO] 환산점수 계산 로직 추출...")
        
        formulas = []
        
        try:
            # 페이지 내 모든 스크립트에서 계산 관련 함수 추출
            scripts_data = await self.page.evaluate("""
                () => {
                    const results = {
                        functions: [],
                        variables: [],
                        formulas: []
                    };
                    
                    // 전역 함수 중 계산 관련 함수 찾기
                    const calcKeywords = ['calc', 'score', 'convert', 'formula', '환산', '계산', 'point', 'grade'];
                    
                    for (const key of Object.keys(window)) {
                        try {
                            const val = window[key];
                            if (typeof val === 'function') {
                                const funcStr = val.toString();
                                const lowerKey = key.toLowerCase();
                                const lowerFunc = funcStr.toLowerCase();
                                
                                if (calcKeywords.some(kw => lowerKey.includes(kw) || lowerFunc.includes(kw))) {
                                    results.functions.push({
                                        name: key,
                                        source: funcStr.substring(0, 3000)
                                    });
                                }
                            }
                        } catch (e) {}
                    }
                    
                    // 인라인 스크립트에서 계산 로직 추출
                    const scripts = document.querySelectorAll('script:not([src])');
                    for (const script of scripts) {
                        const content = script.textContent || '';
                        if (calcKeywords.some(kw => content.toLowerCase().includes(kw))) {
                            // 함수 정의 추출
                            const funcMatches = content.match(/function\s+\w+\s*\([^)]*\)\s*\{[^}]+\}/g) || [];
                            for (const match of funcMatches.slice(0, 20)) {
                                if (calcKeywords.some(kw => match.toLowerCase().includes(kw))) {
                                    results.formulas.push(match.substring(0, 2000));
                                }
                            }
                        }
                    }
                    
                    return results;
                }
            """)
            
            if scripts_data:
                formulas.append(scripts_data)
                print(f"[INFO] 함수 {len(scripts_data.get('functions', []))}개, 공식 {len(scripts_data.get('formulas', []))}개 추출")
                
        except Exception as e:
            print(f"[WARNING] 계산 로직 추출 실패: {e}")
        
        return formulas
    
    async def click_university_and_extract_detail(self, univ_name: str = None) -> Dict[str, Any]:
        """대학 클릭 후 산출내역 상세 추출"""
        print(f"[INFO] 대학 산출내역 상세 추출 시도...")
        
        detail_data = {}
        
        try:
            # 대학 목록에서 첫 번째 대학의 산출내역 버튼 찾기
            calc_buttons = await self.page.query_selector_all('button:has-text("산출내역"), a:has-text("산출내역")')
            
            if calc_buttons:
                print(f"[INFO] 산출내역 버튼 {len(calc_buttons)}개 발견")
                
                # 첫 번째 버튼 클릭
                for i, btn in enumerate(calc_buttons[:3]):  # 최대 3개만
                    try:
                        # 새 창/팝업 대기
                        async with self.context.expect_page() as new_page_info:
                            await btn.click()
                            await asyncio.sleep(2)
                        
                        new_page = await new_page_info.value
                        await new_page.wait_for_load_state("networkidle")
                        
                        # 새 페이지 내용 추출
                        content = await new_page.content()
                        
                        # 스크린샷
                        screenshot_path = OUTPUT_DIR / f"scoring_detail_{i}.png"
                        await new_page.screenshot(path=str(screenshot_path), full_page=True)
                        
                        # HTML 저장
                        html_path = OUTPUT_DIR / f"scoring_detail_{i}.html"
                        html_path.write_text(content, encoding="utf-8")
                        
                        detail_data[f"detail_{i}"] = {
                            "url": new_page.url,
                            "content_length": len(content),
                            "screenshot": str(screenshot_path),
                            "html": str(html_path),
                        }
                        
                        print(f"[INFO] 산출내역 {i+1} 추출 완료")
                        
                        await new_page.close()
                        
                    except Exception as e:
                        print(f"[WARNING] 산출내역 {i+1} 추출 실패: {e}")
                        
            else:
                print("[INFO] 산출내역 버튼을 찾지 못함, 테이블 데이터 직접 추출 시도")
                
                # 테이블에서 직접 데이터 추출
                table_data = await self.page.evaluate("""
                    () => {
                        const tables = document.querySelectorAll('table');
                        const results = [];
                        
                        for (const table of tables) {
                            const rows = table.querySelectorAll('tr');
                            const tableData = [];
                            
                            for (const row of rows) {
                                const cells = row.querySelectorAll('th, td');
                                const rowData = [];
                                for (const cell of cells) {
                                    rowData.push(cell.textContent.trim());
                                }
                                if (rowData.length > 0) {
                                    tableData.push(rowData);
                                }
                            }
                            
                            if (tableData.length > 0) {
                                results.push(tableData);
                            }
                        }
                        
                        return results;
                    }
                """)
                
                if table_data:
                    detail_data["tables"] = table_data
                    print(f"[INFO] 테이블 {len(table_data)}개 추출")
                    
        except Exception as e:
            print(f"[ERROR] 상세 추출 실패: {e}")
            self.results["errors"].append({"step": "extract_detail", "error": str(e)})
        
        return detail_data
    
    async def extract_all_js_files(self) -> List[Dict[str, Any]]:
        """모든 관련 JS 파일 추출"""
        print("[INFO] JavaScript 파일 추출...")
        
        js_files = []
        
        try:
            # 외부 스크립트 URL 수집
            script_urls = await self.page.evaluate("""
                () => {
                    const scripts = document.querySelectorAll('script[src]');
                    return Array.from(scripts).map(s => s.src).filter(src => 
                        src.includes('/sco/') || 
                        src.includes('/agu/') || 
                        src.includes('score') || 
                        src.includes('calc') ||
                        src.includes('common')
                    );
                }
            """)
            
            for url in script_urls[:10]:  # 최대 10개
                try:
                    response = await self.page.goto(url)
                    if response and response.ok:
                        content = await response.text()
                        js_files.append({
                            "url": url,
                            "content": content[:50000],  # 최대 50KB
                        })
                        print(f"[INFO] JS 파일 추출: {url}")
                except Exception as e:
                    print(f"[WARNING] JS 파일 추출 실패: {url} - {e}")
            
            # 원래 페이지로 돌아가기
            await self.page.goto(self.SCORE_CATEGORY_URL, wait_until="networkidle")
            
        except Exception as e:
            print(f"[WARNING] JS 파일 추출 중 오류: {e}")
        
        return js_files
    
    async def search_and_extract_universities(self, search_term: str = "") -> List[Dict[str, Any]]:
        """대학 검색 후 결과 추출"""
        print(f"[INFO] 대학 검색 및 추출...")
        
        universities = []
        
        try:
            # 검색 실행 (빈 검색어로 전체 목록)
            await self.page.evaluate("""
                () => {
                    if (typeof fnGroupSearch === 'function') {
                        fnGroupSearch();
                    }
                }
            """)
            await asyncio.sleep(3)
            
            # 결과 테이블에서 대학 정보 추출
            univ_data = await self.page.evaluate("""
                () => {
                    const results = [];
                    
                    // 대학 목록 테이블 찾기
                    const rows = document.querySelectorAll('table tbody tr, .univList tr, .resultList tr');
                    
                    for (const row of rows) {
                        const cells = row.querySelectorAll('td');
                        if (cells.length > 0) {
                            const univInfo = {
                                cells: Array.from(cells).map(c => c.textContent.trim()),
                                // 데이터 속성 추출
                                dataAttrs: {}
                            };
                            
                            // checkbox나 input에서 데이터 속성 추출
                            const inputs = row.querySelectorAll('input[type="checkbox"], input[type="hidden"]');
                            for (const input of inputs) {
                                for (const attr of input.attributes) {
                                    if (attr.name.startsWith('data-')) {
                                        univInfo.dataAttrs[attr.name] = attr.value;
                                    }
                                }
                            }
                            
                            if (Object.keys(univInfo.dataAttrs).length > 0 || univInfo.cells.length > 0) {
                                results.push(univInfo);
                            }
                        }
                    }
                    
                    return results;
                }
            """)
            
            if univ_data:
                universities = univ_data
                print(f"[INFO] 대학 정보 {len(universities)}개 추출")
                
        except Exception as e:
            print(f"[WARNING] 대학 검색 실패: {e}")
        
        return universities
    
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
            if not await self.login():
                print("[ERROR] 로그인 실패로 중단")
                return self.results
            
            # 2. 정시 성적분석 페이지 이동
            await self.navigate_to_jungsi_analysis()
            
            # 3. 대학 그룹 정보 가져오기
            groups = await self.get_university_groups()
            self.results["university_groups"] = groups
            
            # 4. 환산점수 계산 로직 추출
            formulas = await self.extract_scoring_calculation_logic()
            self.results["scoring_formulas"] = formulas
            
            # 5. 대학 검색 및 추출
            universities = await self.search_and_extract_universities()
            self.results["universities"] = universities
            
            # 6. 산출내역 상세 추출
            details = await self.click_university_and_extract_detail()
            self.results["scoring_details"] = details
            
            # 7. 캡처된 API 응답 저장
            self.results["api_data"] = self.api_responses
            
        except Exception as e:
            print(f"[ERROR] 크롤링 실패: {e}")
            self.results["errors"].append({"step": "run", "error": str(e)})
        finally:
            await self.close()
        
        # 결과 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = OUTPUT_DIR / f"adiga_scoring_v2_{timestamp}.json"
        output_path.write_text(
            json.dumps(self.results, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8"
        )
        print(f"[INFO] 결과 저장: {output_path}")
        
        return self.results


async def main():
    parser = argparse.ArgumentParser(description="대입정보포털 환산점수 상세 크롤러 v2")
    parser.add_argument("--username", "-u", required=True, help="로그인 아이디")
    parser.add_argument("--password", "-p", required=True, help="로그인 비밀번호")
    parser.add_argument("--headless", action="store_true", default=True, help="헤드리스 모드")
    parser.add_argument("--no-headless", dest="headless", action="store_false", help="브라우저 표시")
    args = parser.parse_args()
    
    crawler = AdigaScoringCrawler(
        username=args.username,
        password=args.password,
        headless=args.headless,
    )
    
    results = await crawler.run()
    
    # 요약 출력
    print("\n" + "=" * 60)
    print("크롤링 결과 요약 (v2)")
    print("=" * 60)
    print(f"대학 수: {len(results.get('universities', []))}")
    print(f"환산 공식 데이터: {len(results.get('scoring_formulas', []))}")
    print(f"산출내역 상세: {len(results.get('scoring_details', {}))}")
    print(f"API 응답 수: {len(results.get('api_data', []))}")
    print(f"오류 수: {len(results.get('errors', []))}")


if __name__ == "__main__":
    asyncio.run(main())
