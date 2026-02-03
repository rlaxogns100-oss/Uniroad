"""
자동 댓글 봇 관리 서비스

봇 프로세스의 시작/중지, 상태 확인, 설정 관리, 댓글 기록 조회를 담당합니다.
"""
import os
import json
import subprocess
import signal
from datetime import datetime
from typing import Optional, Dict, List, Any
from pathlib import Path


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
            if dry_run:
                env["DRY_RUN"] = "true"
            
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
            "rest_minutes": 3
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
        """댓글 기록 조회"""
        comments = []
        
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    all_comments = json.load(f)
                    # 최신순 정렬
                    all_comments.reverse()
                    total = len(all_comments)
                    comments = all_comments[offset:offset + limit]
            except Exception as e:
                return {
                    "success": False,
                    "message": f"기록 조회 실패: {str(e)}",
                    "comments": [],
                    "total": 0
                }
        else:
            total = 0
        
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


# 모듈 로드 시 인스턴스 생성하지 않음 (경로 문제 방지)
def get_bot_manager() -> BotManager:
    """BotManager 인스턴스 반환"""
    return BotManager.get_instance()
