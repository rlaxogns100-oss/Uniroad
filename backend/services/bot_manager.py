"""
자동 댓글 봇 관리 서비스

봇 프로세스의 시작/중지, 상태 확인, 설정 관리, 댓글 기록 조회를 담당합니다.
"""
import os
import json
import subprocess
import signal
import requests
import asyncio
from datetime import datetime
from typing import Optional, Dict, List, Any
from pathlib import Path
import google.generativeai as genai


class BotManager:
    """자동 댓글 봇 관리 클래스"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # auto_reply 디렉토리 경로 설정
        # 서버에서의 경로를 환경변수로 설정 가능
        self.bot_dir = os.environ.get(
            "AUTO_REPLY_DIR",
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "auto_reply")
        )
        
        self.config_file = os.path.join(self.bot_dir, "bot_config.json")
        self.history_file = os.path.join(self.bot_dir, "comment_history.json")
        self.dry_run_history_file = os.path.join(self.bot_dir, "dry_run_history.json")
        self.prompts_file = os.path.join(self.bot_dir, "bot_prompts.json")
        self.skip_links_file = os.path.join(self.bot_dir, "skip_links.json")
        self.stop_flag_file = os.path.join(self.bot_dir, ".stop_bot")
        self.pid_file = os.path.join(self.bot_dir, ".bot_pid")
        
        self._process: Optional[subprocess.Popen] = None
        self._initialized = True
        
        print(f"[BotManager] 봇 디렉토리: {self.bot_dir}")
    
    @classmethod
    def get_instance(cls) -> "BotManager":
        """싱글톤 인스턴스 반환"""
        return cls()
    
    def _read_pid_file(self) -> Optional[int]:
        """PID 파일에서 프로세스 ID 읽기"""
        if os.path.exists(self.pid_file):
            try:
                with open(self.pid_file, "r") as f:
                    return int(f.read().strip())
            except:
                pass
        return None
    
    def _write_pid_file(self, pid: int):
        """PID 파일에 프로세스 ID 저장"""
        with open(self.pid_file, "w") as f:
            f.write(str(pid))
    
    def _remove_pid_file(self):
        """PID 파일 삭제"""
        if os.path.exists(self.pid_file):
            os.remove(self.pid_file)
    
    def _is_process_running(self, pid: int) -> bool:
        """프로세스가 실행 중인지 확인"""
        try:
            os.kill(pid, 0)  # 시그널 0은 프로세스 존재 확인용
            return True
        except (OSError, ProcessLookupError):
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """봇 상태 조회"""
        pid = self._read_pid_file()
        is_running = False
        
        if pid:
            is_running = self._is_process_running(pid)
            if not is_running:
                self._remove_pid_file()
        
        # 내부 프로세스 확인
        if self._process and self._process.poll() is None:
            is_running = True
            pid = self._process.pid
        
        # 쿠키 파일 존재 확인
        cookie_file = os.path.join(self.bot_dir, "naver_cookies.pkl")
        cookie_exists = os.path.exists(cookie_file)
        
        # 설정 로드
        config = self.get_config()
        
        return {
            "running": is_running,
            "pid": pid if is_running else None,
            "cookie_exists": cookie_exists,
            "config": config,
            "bot_dir": self.bot_dir,
            "timestamp": datetime.now().isoformat()
        }
    
    def _cleanup_chrome_processes(self):
        """기존 Chrome 프로세스 및 데이터 정리 (crash 방지)"""
        try:
            import shutil
            import glob
            
            # 1. 모든 Chrome/ChromeDriver 프로세스 강제 종료 (절대 경로 사용)
            try:
                subprocess.run(["/usr/bin/pkill", "-9", "chrome"], capture_output=True)
                subprocess.run(["/usr/bin/pkill", "-9", "chromedriver"], capture_output=True)
                print("[BotManager] Chrome 프로세스 정리 완료")
            except Exception as e:
                print(f"[BotManager] Chrome 프로세스 종료 중 오류 (무시): {e}")
            
            # 2. bot_dir 내부의 모든 chrome_data_* 디렉토리 삭제
            chrome_data_dirs = glob.glob(os.path.join(self.bot_dir, "chrome_data_*"))
            for dir_path in chrome_data_dirs:
                try:
                    shutil.rmtree(dir_path)
                    print(f"[BotManager] Chrome 데이터 정리: {dir_path}")
                except Exception as e:
                    print(f"[BotManager] Chrome 데이터 정리 실패: {e}")
            
            # 3. /tmp 내 Chrome 임시 파일 정리
            tmp_patterns = [
                "/tmp/com.google.Chrome.*",
                "/tmp/.org.chromium.*",
                "/tmp/org.chromium.*"
            ]
            for pattern in tmp_patterns:
                for tmp_path in glob.glob(pattern):
                    try:
                        if os.path.isdir(tmp_path):
                            shutil.rmtree(tmp_path)
                        else:
                            os.remove(tmp_path)
                    except:
                        pass
            
            # 4. 정리 후 잠시 대기 (프로세스 완전 종료 대기)
            import time
            time.sleep(2)
            
            print("[BotManager] Chrome 정리 완료")
            
        except Exception as e:
            print(f"[BotManager] Chrome 프로세스 정리 중 오류: {e}")
    
    def start(self, dry_run: bool = False) -> Dict[str, Any]:
        """봇 시작
        
        Args:
            dry_run: True면 댓글을 실제로 달지 않고 생성만 함 (가실행 모드)
        """
        status = self.get_status()
        
        if status["running"]:
            return {
                "success": False,
                "message": "봇이 이미 실행 중입니다.",
                "pid": status["pid"]
            }
        
        if not status["cookie_exists"]:
            return {
                "success": False,
                "message": "쿠키 파일이 없습니다. 로컬에서 get_cookies.py를 실행하세요."
            }
        
        # Chrome 프로세스 정리 (crash 방지)
        self._cleanup_chrome_processes()
        
        # 정지 플래그 제거
        if os.path.exists(self.stop_flag_file):
            os.remove(self.stop_flag_file)
        
        try:
            # 봇 프로세스 시작
            main_py = os.path.join(self.bot_dir, "main.py")
            
            if not os.path.exists(main_py):
                return {
                    "success": False,
                    "message": f"봇 스크립트를 찾을 수 없습니다: {main_py}"
                }
            
            # 환경 변수 설정
            env = os.environ.copy()
            env["HEADLESS"] = "true"
            env["PYTHONUNBUFFERED"] = "1"  # 로그 실시간 출력 (버퍼링 해제)
            if dry_run:
                env["DRY_RUN"] = "true"
            
            # 시스템 PATH 추가 (venv 환경에서 실행 시 Chrome 등 시스템 바이너리 접근 필요)
            system_paths = "/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin"
            if "PATH" in env:
                env["PATH"] = f"{system_paths}:{env['PATH']}"
            else:
                env["PATH"] = system_paths
            
            # DISPLAY 환경변수 제거 (headless 모드에서 불필요)
            env.pop("DISPLAY", None)
            
            # 백그라운드 프로세스로 시작 (봇 로그는 bot_dir/bot.log에 기록)
            # 시스템 python3 명시적 사용 (selenium 등 시스템 패키지 사용)
            python_cmd = "/usr/bin/python3" if os.path.exists("/usr/bin/python3") else "python3"
            bot_log = os.path.join(self.bot_dir, "bot.log")
            logf = open(bot_log, "a", encoding="utf-8")
            logf.write(f"\n===== 봇 시작 {datetime.now().isoformat()} =====\n")
            logf.flush()
            
            # DRY_RUN 모드 설정
            if env.get("DRY_RUN") == "true":
                logf.write("[DRY RUN MODE] 댓글을 실제로 달지 않고 생성만 합니다.\n")
            
            self._process = subprocess.Popen(
                [python_cmd, main_py],
                cwd=self.bot_dir,
                env=env,
                stdout=logf,
                stderr=subprocess.STDOUT,
                start_new_session=True  # 부모 프로세스와 분리
            )
            logf.close()  # 자식이 fd 상속했으므로 부모만 닫음
            
            # PID 저장
            self._write_pid_file(self._process.pid)
            
            mode_msg = " (가실행 모드)" if dry_run else ""
            return {
                "success": True,
                "message": f"봇이 시작되었습니다.{mode_msg}",
                "pid": self._process.pid,
                "dry_run": dry_run
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"봇 시작 실패: {str(e)}"
            }
    
    def stop(self) -> Dict[str, Any]:
        """봇 중지"""
        status = self.get_status()
        
        if not status["running"]:
            # 실행 중이 아니어도 Chrome 정리는 수행
            self._cleanup_chrome_processes()
            return {
                "success": False,
                "message": "봇이 실행 중이 아닙니다."
            }
        
        try:
            # 정지 플래그 파일 생성 (graceful shutdown)
            Path(self.stop_flag_file).touch()
            
            pid = status["pid"]
            
            # SIGTERM 시그널 전송
            if pid:
                try:
                    os.kill(pid, signal.SIGTERM)
                except (OSError, ProcessLookupError):
                    pass
            
            # 내부 프로세스 종료
            if self._process and self._process.poll() is None:
                self._process.terminate()
                try:
                    self._process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self._process.kill()
            
            self._process = None
            self._remove_pid_file()
            
            # Chrome 프로세스 정리
            self._cleanup_chrome_processes()
            
            return {
                "success": True,
                "message": "봇 종료 신호를 보냈습니다."
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"봇 중지 실패: {str(e)}"
            }
    
    def get_config(self) -> Dict[str, Any]:
        """봇 설정 조회"""
        default_config = {
            "min_delay_seconds": 50,
            "comments_per_hour_min": 5,
            "comments_per_hour_max": 10,
            "rest_minutes": 3,
            "keywords": []  # 검색 키워드 목록
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    default_config.update(loaded)
            except:
                pass
        
        return default_config
    
    def update_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """봇 설정 업데이트"""
        current_config = self.get_config()
        current_config.update(config)
        
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(current_config, f, ensure_ascii=False, indent=2)
            
            return {
                "success": True,
                "message": "설정이 업데이트되었습니다.",
                "config": current_config
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"설정 저장 실패: {str(e)}"
            }
    
    def get_comments(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """댓글 기록 조회 (실제 댓글 + 가실행 댓글 통합)"""
        all_comments = []
        
        # 1. 실제 댓글 기록 로드
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    comments = json.load(f)
                    all_comments.extend(comments)
            except Exception as e:
                print(f"[BotManager] 실제 댓글 기록 로드 실패: {e}")
        
        # 2. 가실행 댓글 기록 로드
        if os.path.exists(self.dry_run_history_file):
            try:
                with open(self.dry_run_history_file, "r", encoding="utf-8") as f:
                    dry_run_comments = json.load(f)
                    all_comments.extend(dry_run_comments)
            except Exception as e:
                print(f"[BotManager] 가실행 댓글 기록 로드 실패: {e}")
        
        # 3. 시간순 정렬 (최신순)
        if all_comments:
            all_comments.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        total = len(all_comments)
        comments = all_comments[offset:offset + limit]
        
        return {
            "success": True,
            "comments": comments,
            "total": total,
            "limit": limit,
            "offset": offset
        }

    def get_prompts(self) -> Dict[str, Any]:
        """봇 프롬프트 조회 (Query/Answer Agent용). 파일 없으면 빈 dict."""
        if not os.path.exists(self.prompts_file):
            return {"query_prompt": "", "answer_prompt": ""}
        try:
            with open(self.prompts_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {
                    "query_prompt": data.get("query_prompt", ""),
                    "answer_prompt": data.get("answer_prompt", "")
                }
        except Exception:
            return {"query_prompt": "", "answer_prompt": ""}

    def update_prompts(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """봇 프롬프트 저장. query_prompt와 answer_prompt 둘 다 저장."""
        query_prompt = data.get("query_prompt")
        answer_prompt = data.get("answer_prompt")
        
        if query_prompt is None and answer_prompt is None:
            return {"success": False, "message": "query_prompt 또는 answer_prompt 필드가 필요합니다."}
        
        # 기존 파일 읽어서 업데이트
        current = {"query_prompt": "", "answer_prompt": ""}
        if os.path.exists(self.prompts_file):
            try:
                with open(self.prompts_file, "r", encoding="utf-8") as f:
                    current = json.load(f)
            except:
                pass
        
        if query_prompt is not None:
            current["query_prompt"] = query_prompt
        if answer_prompt is not None:
            current["answer_prompt"] = answer_prompt
        
        try:
            with open(self.prompts_file, "w", encoding="utf-8") as f:
                json.dump(current, f, ensure_ascii=False, indent=2)
            return {"success": True, "message": "프롬프트가 저장되었습니다."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def test_generate_reply(self, post_content: str) -> Dict[str, Any]:
        """
        테스트용 댓글 생성 (Query Agent -> RAG -> Answer Agent 파이프라인)
        
        Args:
            post_content: 테스트할 게시글 내용 (제목 + 본문)
            
        Returns:
            dict: query, function_result, answer 포함
        """
        try:
            # config.py에서 API 키 로드
            config_py = os.path.join(self.bot_dir, "config.py")
            if not os.path.exists(config_py):
                return {"success": False, "message": "config.py 파일이 없습니다."}
            
            # config.py 동적 로드
            import importlib.util
            spec = importlib.util.spec_from_file_location("bot_config", config_py)
            bot_config = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(bot_config)
            
            # Gemini API 설정
            genai.configure(api_key=bot_config.GEMINI_API_KEY)
            
            # 프롬프트 로드
            prompts = self.get_prompts()
            query_prompt = prompts.get("query_prompt", "").strip()
            answer_prompt = prompts.get("answer_prompt", "").strip()
            
            # 기본 Query Agent 프롬프트 (프롬프트가 비어있으면 사용)
            if not query_prompt:
                query_prompt = self._get_default_query_prompt()
            
            if not answer_prompt:
                answer_prompt = self._get_default_answer_prompt()
            
            # Query Agent 모델 초기화 (system_instruction 사용)
            try:
                query_agent = genai.GenerativeModel(
                    'gemini-2.5-flash-lite',
                    system_instruction=query_prompt
                )
            except:
                query_agent = genai.GenerativeModel(
                    'gemini-2.0-flash',
                    system_instruction=query_prompt
                )
            
            # Answer Agent 모델 초기화
            try:
                answer_agent = genai.GenerativeModel('gemini-3-flash-preview')
            except:
                answer_agent = genai.GenerativeModel('gemini-2.5-flash')
            
            # 제목과 본문 분리 (첫 줄을 제목으로)
            lines = post_content.strip().split('\n', 1)
            title = lines[0] if lines else ""
            content = lines[1] if len(lines) > 1 else ""
            
            # 1. Query Agent 실행
            query_message = f"""[게시글]
제목: {title}
본문: {content[:1000]}

위 게시글을 분석하여 function_calls를 JSON 형식으로 생성하세요.
"""
            
            generation_config = {
                "temperature": 0.0,
                "max_output_tokens": 2048,
                "response_mime_type": "application/json"
            }
            
            response = query_agent.generate_content(query_message, generation_config=generation_config)
            result_text = response.text.strip()
            
            # JSON 파싱
            try:
                result = json.loads(result_text)
                function_calls = result.get("function_calls", [])
            except json.JSONDecodeError:
                function_calls = []
            
            query_result = json.dumps(function_calls, ensure_ascii=False, indent=2)
            
            if not function_calls:
                return {
                    "success": True,
                    "query": query_result,
                    "function_result": "",
                    "answer": "[PASS] 도움이 필요하지 않은 게시글입니다."
                }
            
            # 2. RAG API 호출 (직접 함수 호출)
            rag_context = ""
            
            try:
                from services.multi_agent.functions import execute_function_calls
                # async 함수를 await로 호출
                rag_results = await execute_function_calls(function_calls)
                print(f"🔍 [DEBUG] RAG 결과 키: {list(rag_results.keys()) if rag_results else 'None'}")
                if rag_results:
                    for key, val in rag_results.items():
                        chunks = val.get("chunks", [])
                        print(f"🔍 [DEBUG] {key}: {len(chunks)}개 청크")
                    rag_context = self._format_rag_context(rag_results)
                    print(f"🔍 [DEBUG] rag_context 길이: {len(rag_context)}")
            except Exception as e:
                import traceback
                print(f"❌ [DEBUG] RAG 오류: {e}")
                traceback.print_exc()
                rag_context = f"[RAG 오류: {str(e)}]"
            
            # 3. Answer Agent 실행
            rag_section = ""
            if rag_context:
                rag_section = f"""
[📚 관련 입시 정보 (RAG)]
아래는 게시글과 관련된 공식 입시 정보입니다. 답변 시 참고하세요.
{rag_context}
"""
            
            answer_full_prompt = f"""
당신은 수만휘 입시 커뮤니티의 입시 멘토입니다.
게시글을 읽고 도움이 되는 댓글을 작성하세요.

[게시글 정보]
제목: {title}
본문: {content[:1000]}
{rag_section}
{answer_prompt}
"""
            
            answer_response = answer_agent.generate_content(answer_full_prompt)
            answer_text = (answer_response.text or "").strip()
            answer_text = answer_text.replace('"', '').replace("'", "").strip()
            
            if not answer_text or len(answer_text) <= 20:
                final_answer = "[PASS] 할 말이 없거나 너무 짧습니다."
            else:
                final_answer = f"""수험생 전문 ai에 물어보니까 이러네요

{answer_text}

구글에 uni2road 검색해서 써 보세요"""
            
            return {
                "success": True,
                "query": query_result,
                "function_result": rag_context,
                "answer": final_answer
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"테스트 실행 실패: {str(e)}",
                "query": "",
                "function_result": "",
                "answer": ""
            }
    
    def _format_rag_context(self, rag_results: Dict) -> str:
        """RAG 결과를 문자열로 포맷팅"""
        if not rag_results:
            return ""
        
        context_parts = []
        
        for key, result in rag_results.items():
            chunks = result.get("chunks", [])
            if not chunks:
                continue
            
            context_parts.append(f"\n=== 관련 입시 정보 ({result.get('university', '전체')}) ===")
            
            for i, chunk in enumerate(chunks[:10], 1):
                content = chunk.get("content", "")
                context_parts.append(f"[{i}] {content}")
        
        return "\n".join(context_parts) if context_parts else ""
    
    def _get_default_query_prompt(self) -> str:
        """기본 Query Agent 프롬프트 반환"""
        return """당신은 대학 입시 커뮤니티 게시글을 분석하는 **Query Agent**입니다.

## 정체성
당신의 역할은 정보 검색을 위한 json 형식의 함수 호출입니다.

## 사용 가능한 함수

### univ(university, query)
특정 대학의 입시 정보를 검색합니다.
- university: 대학 정식명칭 (서울대학교, 경희대학교), 빈 문자열이면 전체 검색
- query: 검색 쿼리 (연도 + 전형 + 학과 명시)

예시:
- "서울대 가는 법" -> univ("서울대학교", "서울대학교 2026학년도 모집요강")
- "서울대 기계과 정시" → univ("서울대학교", "2026학년도 기계공학부 정시")

### consult(scores, target_univ, target_major, target_range)
대학 입결 조회, 학생 성적 대학별 환산점수 변환, 합격 가능성 평가
학생 성적을 분석하여 합격 가능성을 평가합니다. 환산점수 계산 포함.
#### 주의: 성적 정보가 질문에 있으면 scores 로 사용, 질문에 없고 history에 있으면 그 정보를 scores 로 사용, 둘 다 없으면 consult 호출 안 함
- scores: 성적 딕셔너리 {"국어": {"type": "등급", "value": 1}, ...}
- target_univ: 분석 대상 대학 리스트 (없으면 [])
- target_major: 관심 학과 리스트 (없으면 [])
- target_range: 분석 범위 리스트 (없으면 [] = 전체 범위)

#### 성적 입력 형식
1. 축약형 (5자리): "11232" → 국어/수학/영어/탐구1/탐구2 등급
2. 축약형 (6자리): "211332" → 한국사/국어/수학/영어/탐구1/탐구2 등급
3. 등급: "국어 1등급", "수학 2등급"
4. 표준점수: "수학 140점", "수학 표준점수 140"
5. 백분위: "국어 백분위 98"

#### 성적 출력 형식
```json
{
  "scores": {
    "국어": {"type": "등급", "value": 1},
    "수학": {"type": "표준점수", "value": 140},
    "영어": {"type": "등급", "value": 2},
    "한국사": {"type": "등급", "value": 1},
    "탐구1": {"type": "등급", "value": 1, "과목명": "생활과윤리"},
    "탐구2": {"type": "등급", "value": 2, "과목명": "사회문화"}
  }
}
```
- type: "등급", "표준점수", "백분위"
- 탐구 과목은 키를 "탐구1", "탐구2"로 고정하고, 과목명이 언급된 경우 "과목명" 필드 추가
- 한국사는 항상 포함 (미언급 시 1등급으로 기본 추정)

성적 예시:
- "11232" → {"국어": {"type": "등급", "value": 1}, "수학": {"type": "등급", "value": 1}, "영어": {"type": "등급", "value": 2}, "한국사": {"type": "등급", "value": 1}, "탐구1": {"type": "등급", "value": 3}, "탐구2": {"type": "등급", "value": 2}}
- "국어 화작 1등급, 수학 미적 140점" → {"국어": {"type": "등급", "value": 1, "선택과목": "화법과작문"}, "수학": {"type": "표준점수", "value": 140, "선택과목": "미적분"}}

target_range 옵션 (새로운 판정 기준):
- ["안정"]: 내 점수 >= 안정컷 (safeScore), 합격 확률 매우 높음
- ["적정"]: 내 점수 >= 적정컷 (appropriateScore), 합격 가능성 높음
- ["소신"]: 내 점수 >= 소신컷 (expectedScore), 합격 가능성 있음
- ["도전"]: 내 점수 >= 도전컷 (challengeScore), 도전적인 지원
- ["어려움"]: 내 점수 < 도전컷, 합격 어려움
- []: 빈 배열 = 모든 범위 (기본값)

예시:
- "나 11232인데 경희대 갈 수 있어?" → consult(scores, ["경희대학교"], [], [])
- "11112로 기계공학 어디 갈까?" → consult(scores, [], ["기계공학"], ["안정", "적정", "소신"])

## 출력 형식
반드시 JSON만 출력하세요. 다른 텍스트 절대 금지.

### 단일 함수 호출 예시 (서울대 정시 정보 알려줘)
```json
{
  "function_calls": [
    {
      "function": "univ",
      "params": {
        "university": "서울대학교",
        "query": "2026학년도 서울대학교 정시 모집요강"
      }
    }
  ]
}
```

### 성적 분석 예시 (나 11232인데 경희대 갈 수 있어?)
```json
{
  "function_calls": [
    {
      "function": "consult",
      "params": {
        "scores": {
          "국어": {"type": "등급", "value": 1},
          "수학": {"type": "등급", "value": 1},
          "영어": {"type": "등급", "value": 2},
          "탐구1": {"type": "등급", "value": 3},
          "탐구2": {"type": "등급", "value": 2}
        },
        "target_univ": ["경희대학교"],
        "target_major": [],
        "target_range": []
      }
    }
  ]
}
```

도움이 필요 없는 게시글이면 빈 배열을 반환하세요:
{"function_calls": []}
"""
    
    def _get_default_answer_prompt(self) -> str:
        """기본 Answer Agent 프롬프트 반환"""
        return """## 답변 작성 가이드라인

1. **말투:** "~해요"체 사용하되, 자신감 있고 확신에 찬 어조.
2. **길이:** 3~4문장. (서론 빼고 본론만 딱.)
3. **출력 형식:** 댓글 내용만 출력하세요.
   - 마크다운 형식 사용 금지. 평문만 사용.
"""

    def _extract_article_id(self, url: str) -> Optional[str]:
        """URL에서 article ID 추출 (다양한 형식 지원)"""
        import re
        # f-e 형식: /articles/29429119
        match = re.search(r'/articles/(\d+)', url)
        if match:
            return match.group(1)
        
        # 일반 형식: /카페명/29429119 또는 /카페명/29429119?...
        match = re.search(r'/([a-zA-Z0-9_]+)/(\d+)(?:\?|$)', url)
        if match:
            return match.group(2)
        
        return None

    def get_skip_links(self) -> Dict[str, Any]:
        """수동 스킵 링크 목록 조회"""
        skip_links = []
        
        if os.path.exists(self.skip_links_file):
            try:
                with open(self.skip_links_file, "r", encoding="utf-8") as f:
                    skip_links = json.load(f)
            except:
                pass
        
        return {
            "success": True,
            "links": skip_links,
            "total": len(skip_links)
        }

    def add_skip_link(self, url: str) -> Dict[str, Any]:
        """수동 스킵 링크 추가"""
        # article ID 추출
        article_id = self._extract_article_id(url)
        if not article_id:
            return {"success": False, "message": "유효한 네이버 카페 URL이 아닙니다."}
        
        # 기존 목록 로드
        skip_links = []
        if os.path.exists(self.skip_links_file):
            try:
                with open(self.skip_links_file, "r", encoding="utf-8") as f:
                    skip_links = json.load(f)
            except:
                pass
        
        # 중복 체크
        for link in skip_links:
            if link.get("article_id") == article_id:
                return {"success": False, "message": "이미 등록된 링크입니다."}
        
        # 추가
        skip_links.append({
            "url": url,
            "article_id": article_id,
            "added_at": datetime.now().isoformat()
        })
        
        try:
            with open(self.skip_links_file, "w", encoding="utf-8") as f:
                json.dump(skip_links, f, ensure_ascii=False, indent=2)
            return {"success": True, "message": f"링크가 추가되었습니다. (Article ID: {article_id})"}
        except Exception as e:
            return {"success": False, "message": f"저장 실패: {str(e)}"}

    def remove_skip_link(self, url: str) -> Dict[str, Any]:
        """수동 스킵 링크 삭제"""
        article_id = self._extract_article_id(url)
        if not article_id:
            return {"success": False, "message": "유효한 네이버 카페 URL이 아닙니다."}
        
        if not os.path.exists(self.skip_links_file):
            return {"success": False, "message": "등록된 링크가 없습니다."}
        
        try:
            with open(self.skip_links_file, "r", encoding="utf-8") as f:
                skip_links = json.load(f)
        except:
            return {"success": False, "message": "파일 읽기 실패"}
        
        # 삭제
        original_len = len(skip_links)
        skip_links = [link for link in skip_links if link.get("article_id") != article_id]
        
        if len(skip_links) == original_len:
            return {"success": False, "message": "해당 링크를 찾을 수 없습니다."}
        
        try:
            with open(self.skip_links_file, "w", encoding="utf-8") as f:
                json.dump(skip_links, f, ensure_ascii=False, indent=2)
            return {"success": True, "message": "링크가 삭제되었습니다."}
        except Exception as e:
            return {"success": False, "message": f"저장 실패: {str(e)}"}

    # ==========================================
    # 반자동 시스템 메서드들
    # ==========================================
    
    def _load_comment_history(self) -> List[Dict]:
        """댓글 히스토리 로드"""
        if not os.path.exists(self.history_file):
            return []
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    
    def _save_comment_history(self, history: List[Dict]) -> bool:
        """댓글 히스토리 저장"""
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
            return True
        except:
            return False
    
    def _find_comment_by_id(self, comment_id: str) -> Optional[Dict]:
        """ID로 댓글 찾기"""
        history = self._load_comment_history()
        for comment in history:
            if comment.get("id") == comment_id:
                return comment
        return None
    
    def _update_comment(self, comment_id: str, updates: Dict) -> bool:
        """댓글 업데이트"""
        history = self._load_comment_history()
        for comment in history:
            if comment.get("id") == comment_id:
                comment.update(updates)
                # action_history에 추가
                if "action_history" not in comment:
                    comment["action_history"] = []
                return self._save_comment_history(history)
        return False
    
    def approve_comment(self, comment_id: str) -> Dict[str, Any]:
        """댓글 승인 - 게시 대기열에 추가"""
        history = self._load_comment_history()
        
        for comment in history:
            if comment.get("id") == comment_id:
                if comment.get("status") != "pending":
                    return {"success": False, "message": f"현재 상태({comment.get('status')})에서는 승인할 수 없습니다."}
                
                comment["status"] = "approved"
                if "action_history" not in comment:
                    comment["action_history"] = []
                comment["action_history"].append({
                    "action": "approved",
                    "timestamp": datetime.now().isoformat()
                })
                
                if self._save_comment_history(history):
                    return {"success": True, "message": "댓글이 승인되었습니다. 게시 대기열에 추가됨."}
                return {"success": False, "message": "저장 실패"}
        
        return {"success": False, "message": "댓글을 찾을 수 없습니다."}
    
    def cancel_comment(self, comment_id: str) -> Dict[str, Any]:
        """댓글 취소 - 게시하지 않음"""
        history = self._load_comment_history()
        
        for comment in history:
            if comment.get("id") == comment_id:
                if comment.get("status") not in ["pending", "approved"]:
                    return {"success": False, "message": f"현재 상태({comment.get('status')})에서는 취소할 수 없습니다."}
                
                comment["status"] = "cancelled"
                if "action_history" not in comment:
                    comment["action_history"] = []
                comment["action_history"].append({
                    "action": "cancelled",
                    "timestamp": datetime.now().isoformat()
                })
                
                if self._save_comment_history(history):
                    return {"success": True, "message": "댓글이 취소되었습니다."}
                return {"success": False, "message": "저장 실패"}
        
        return {"success": False, "message": "댓글을 찾을 수 없습니다."}
    
    def revert_to_pending(self, comment_id: str) -> Dict[str, Any]:
        """댓글을 pending 상태로 되돌리기"""
        history = self._load_comment_history()
        
        for comment in history:
            if comment.get("id") == comment_id:
                old_status = comment.get("status")
                if old_status == "posted":
                    return {"success": False, "message": "이미 게시된 댓글은 되돌릴 수 없습니다."}
                
                comment["status"] = "pending"
                if "action_history" not in comment:
                    comment["action_history"] = []
                comment["action_history"].append({
                    "action": "reverted_to_pending",
                    "timestamp": datetime.now().isoformat(),
                    "from_status": old_status
                })
                
                if self._save_comment_history(history):
                    return {"success": True, "message": f"댓글이 대기 상태로 되돌려졌습니다. ({old_status} → pending)"}
                return {"success": False, "message": "저장 실패"}
        
        return {"success": False, "message": "댓글을 찾을 수 없습니다."}
    
    def edit_comment(self, comment_id: str, new_comment: str) -> Dict[str, Any]:
        """댓글 수정"""
        history = self._load_comment_history()
        
        for comment in history:
            if comment.get("id") == comment_id:
                if comment.get("status") not in ["pending", "approved"]:
                    return {"success": False, "message": f"현재 상태({comment.get('status')})에서는 수정할 수 없습니다."}
                
                old_comment = comment.get("comment", "")
                comment["comment"] = new_comment
                if "action_history" not in comment:
                    comment["action_history"] = []
                comment["action_history"].append({
                    "action": "edited",
                    "timestamp": datetime.now().isoformat(),
                    "old_comment": old_comment
                })
                
                if self._save_comment_history(history):
                    return {"success": True, "message": "댓글이 수정되었습니다."}
                return {"success": False, "message": "저장 실패"}
        
        return {"success": False, "message": "댓글을 찾을 수 없습니다."}
    
    async def regenerate_comment(self, comment_id: str) -> Dict[str, Any]:
        """댓글 재생성 - AI 에이전트를 다시 실행"""
        history = self._load_comment_history()
        
        target_comment = None
        for comment in history:
            if comment.get("id") == comment_id:
                target_comment = comment
                break
        
        if not target_comment:
            return {"success": False, "message": "댓글을 찾을 수 없습니다."}
        
        if target_comment.get("status") not in ["pending", "approved"]:
            return {"success": False, "message": f"현재 상태({target_comment.get('status')})에서는 재생성할 수 없습니다."}
        
        # 원본 게시글 내용으로 다시 생성
        post_content = target_comment.get("post_content", "")
        post_title = target_comment.get("post_title", "")
        
        if not post_content:
            return {"success": False, "message": "원본 게시글 내용이 없어 재생성할 수 없습니다."}
        
        # test_generate_reply 호출하여 새 댓글 생성
        try:
            result = await self.test_generate_reply(f"제목: {post_title}\n\n{post_content}")
            
            if result.get("success") and result.get("answer"):
                old_comment = target_comment.get("comment", "")
                target_comment["comment"] = result["answer"]
                target_comment["query"] = result.get("query", "")
                target_comment["function_result"] = result.get("function_result", "")
                
                if "action_history" not in target_comment:
                    target_comment["action_history"] = []
                target_comment["action_history"].append({
                    "action": "regenerated",
                    "timestamp": datetime.now().isoformat(),
                    "old_comment": old_comment
                })
                
                if self._save_comment_history(history):
                    return {
                        "success": True,
                        "message": "댓글이 재생성되었습니다.",
                        "new_comment": result["answer"],
                        "query": result.get("query", ""),
                        "function_result": result.get("function_result", "")
                    }
                return {"success": False, "message": "저장 실패"}
            else:
                return {"success": False, "message": result.get("error", "댓글 생성 실패")}
        except Exception as e:
            return {"success": False, "message": f"재생성 실패: {str(e)}"}
    
    # ==========================================
    # 게시 워커 관리
    # ==========================================
    
    def __init_poster_attrs(self):
        """게시 워커 관련 속성 초기화"""
        if not hasattr(self, '_poster_process'):
            self._poster_process = None
        if not hasattr(self, 'poster_stop_flag_file'):
            self.poster_stop_flag_file = os.path.join(self.bot_dir, ".stop_poster")
        if not hasattr(self, 'poster_pid_file'):
            self.poster_pid_file = os.path.join(self.bot_dir, ".poster_pid")
    
    def start_poster(self) -> Dict[str, Any]:
        """게시 워커 시작 - 승인된 댓글을 딜레이 적용하여 게시"""
        self.__init_poster_attrs()
        
        # 이미 실행 중인지 확인
        poster_status = self.get_poster_status()
        if poster_status.get("running"):
            return {
                "success": False,
                "message": "게시 워커가 이미 실행 중입니다.",
                "pid": poster_status.get("pid")
            }
        
        # 쿠키 파일 확인
        cookie_file = os.path.join(self.bot_dir, "naver_cookies.pkl")
        if not os.path.exists(cookie_file):
            return {
                "success": False,
                "message": "쿠키 파일이 없습니다."
            }
        
        # 정지 플래그 제거
        if os.path.exists(self.poster_stop_flag_file):
            os.remove(self.poster_stop_flag_file)
        
        try:
            # 게시 워커용 스크립트 실행
            main_py = os.path.join(self.bot_dir, "main.py")
            
            env = os.environ.copy()
            env["HEADLESS"] = "true"
            env["PYTHONUNBUFFERED"] = "1"
            env["RUN_POSTER"] = "true"  # 게시 워커 모드
            
            system_paths = "/usr/local/bin:/usr/bin:/bin"
            env["PATH"] = f"{system_paths}:{env.get('PATH', '')}"
            env.pop("DISPLAY", None)
            
            python_cmd = "/usr/bin/python3" if os.path.exists("/usr/bin/python3") else "python3"
            poster_log = os.path.join(self.bot_dir, "poster.log")
            logf = open(poster_log, "a", encoding="utf-8")
            logf.write(f"\n===== 게시 워커 시작 {datetime.now().isoformat()} =====\n")
            logf.flush()
            
            # poster 모드로 실행하는 래퍼 명령
            self._poster_process = subprocess.Popen(
                [python_cmd, "-c", f"import sys; sys.path.insert(0, '{self.bot_dir}'); from main import run_poster_bot; run_poster_bot()"],
                cwd=self.bot_dir,
                env=env,
                stdout=logf,
                stderr=subprocess.STDOUT,
                start_new_session=True
            )
            logf.close()
            
            # PID 저장
            with open(self.poster_pid_file, "w") as f:
                f.write(str(self._poster_process.pid))
            
            return {
                "success": True,
                "message": "게시 워커가 시작되었습니다.",
                "pid": self._poster_process.pid
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"게시 워커 시작 실패: {str(e)}"
            }
    
    def stop_poster(self) -> Dict[str, Any]:
        """게시 워커 중지"""
        self.__init_poster_attrs()
        
        poster_status = self.get_poster_status()
        if not poster_status.get("running"):
            return {
                "success": False,
                "message": "게시 워커가 실행 중이 아닙니다."
            }
        
        try:
            # 정지 플래그 파일 생성
            Path(self.poster_stop_flag_file).touch()
            
            pid = poster_status.get("pid")
            if pid:
                try:
                    os.kill(pid, signal.SIGTERM)
                except (OSError, ProcessLookupError):
                    pass
            
            if self._poster_process and self._poster_process.poll() is None:
                self._poster_process.terminate()
                try:
                    self._poster_process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self._poster_process.kill()
            
            self._poster_process = None
            
            if os.path.exists(self.poster_pid_file):
                os.remove(self.poster_pid_file)
            
            return {
                "success": True,
                "message": "게시 워커 종료 신호를 보냈습니다."
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"게시 워커 중지 실패: {str(e)}"
            }
    
    def get_poster_status(self) -> Dict[str, Any]:
        """게시 워커 상태 조회"""
        self.__init_poster_attrs()
        
        pid = None
        is_running = False
        
        # PID 파일에서 확인
        if os.path.exists(self.poster_pid_file):
            try:
                with open(self.poster_pid_file, "r") as f:
                    pid = int(f.read().strip())
                is_running = self._is_process_running(pid)
                if not is_running:
                    os.remove(self.poster_pid_file)
                    pid = None
            except:
                pass
        
        # 내부 프로세스 확인
        if self._poster_process and self._poster_process.poll() is None:
            is_running = True
            pid = self._poster_process.pid
        
        # 승인된 댓글 수 확인
        approved_count = 0
        history = self._load_comment_history()
        for comment in history:
            if comment.get("status") == "approved":
                approved_count += 1
        
        return {
            "running": is_running,
            "pid": pid if is_running else None,
            "approved_count": approved_count,
            "timestamp": datetime.now().isoformat()
        }

    def get_poster_logs(self, lines: int = 50) -> Dict[str, Any]:
        """게시 워커 로그 조회"""
        self.__init_poster_attrs()
        
        poster_log_file = os.path.join(self.bot_dir, "poster.log")
        logs = []
        
        if os.path.exists(poster_log_file):
            try:
                with open(poster_log_file, "r", encoding="utf-8") as f:
                    all_lines = f.readlines()
                    logs = [line.rstrip() for line in all_lines[-lines:]]
            except Exception as e:
                logs = [f"로그 읽기 오류: {str(e)}"]
        else:
            logs = ["게시 로그 파일이 없습니다."]
        
        return {"logs": logs}


# 모듈 로드 시 인스턴스 생성하지 않음 (경로 문제 방지)
def get_bot_manager() -> BotManager:
    """BotManager 인스턴스 반환"""
    return BotManager.get_instance()
