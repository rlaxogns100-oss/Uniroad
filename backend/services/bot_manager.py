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

    def test_generate_reply(self, post_content: str) -> Dict[str, Any]:
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
            
            # Query Agent 모델 초기화
            try:
                query_agent = genai.GenerativeModel('gemini-2.5-flash-lite')
            except:
                query_agent = genai.GenerativeModel('gemini-2.0-flash')
            
            # Answer Agent 모델 초기화
            try:
                answer_agent = genai.GenerativeModel('gemini-3-flash-preview')
            except:
                answer_agent = genai.GenerativeModel('gemini-2.5-flash')
            
            # 프롬프트 로드
            prompts = self.get_prompts()
            query_prompt = prompts.get("query_prompt", "").strip()
            answer_prompt = prompts.get("answer_prompt", "").strip()
            
            # 기본 Query Agent 프롬프트 (프롬프트가 비어있으면 사용)
            if not query_prompt:
                query_prompt = self._get_default_query_prompt()
            
            if not answer_prompt:
                answer_prompt = self._get_default_answer_prompt()
            
            # 제목과 본문 분리 (첫 줄을 제목으로)
            lines = post_content.strip().split('\n', 1)
            title = lines[0] if lines else ""
            content = lines[1] if len(lines) > 1 else ""
            
            # 1. Query Agent 실행
            query_full_prompt = f"""{query_prompt}

[게시글]
제목: {title}
본문: {content[:1000]}

위 게시글을 분석하여 function_calls를 JSON 형식으로 생성하세요.
"""
            
            generation_config = {
                "temperature": 0.0,
                "max_output_tokens": 2048,
                "response_mime_type": "application/json"
            }
            
            response = query_agent.generate_content(query_full_prompt, generation_config=generation_config)
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
                # async 함수를 동기적으로 실행
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    rag_results = loop.run_until_complete(execute_function_calls(function_calls))
                    if rag_results:
                        rag_context = self._format_rag_context(rag_results)
                finally:
                    loop.close()
            except Exception as e:
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

## 출력 형식
반드시 아래 JSON 형식으로만 응답하세요:
{
  "function_calls": [
    {
      "function": "univ" 또는 "consult",
      "params": { ... }
    }
  ]
}

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


# 모듈 로드 시 인스턴스 생성하지 않음 (경로 문제 방지)
def get_bot_manager() -> BotManager:
    """BotManager 인스턴스 반환"""
    return BotManager.get_instance()
