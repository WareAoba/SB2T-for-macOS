import os
import Quartz
import json
import pyperclip
from pynput import keyboard
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import time
import darkdetect
from datetime import datetime, timedelta
from functools import wraps
import appdirs
import subprocess
from pathlib import Path
import threading

# 코딩 할줄 전혀 몰라서 코파일럿 딸깍질만 반복했습니다
# 실행도 잘 안됨... 손좀 봐주셈...


cache_name="cachedIndex.json"
appdir_path=appdirs.user_cache_dir("ParagraphManager", False)
cache_path=os.path.join(appdir_path,cache_name)
print("Cache Path: ",cache_path)
if not os.path.exists(appdir_path):
    os.makedirs(appdir_path)
    
class throttle(object):
    
    # 함수 호출 주기 제한 데코레이터
    # 지정된 시간 간격 내에서 한 번만 호출되도록 함
    # 사용 예시:
    # @throttle(minutes=1)
    # def my_fun():
    #     pass

    def __init__(self, seconds=0, minutes=0, hours=0):
        self.throttle_period = timedelta(
            seconds=seconds, minutes=minutes, hours=hours
        )
        self.time_of_last_call = datetime.min

    def __call__(self, fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            now = datetime.now()
            time_since_last_call = now - self.time_of_last_call

            if time_since_last_call > self.throttle_period:
                self.time_of_last_call = now
                return fn(*args, **kwargs)

        return wrapper

class ClipboardManager:
    def __init__(self, update_gui_callback=None):
        self.update_gui_callback = update_gui_callback
        self.paragraphs = []
        self.index = 0
        self.swift_process = None
        self.to_swift = None
        self.from_swift = None
        
        # 파이프 설정 및 Swift 프로세스 시작
        self.setup_pipes()
        self.start_swift_monitor()
        
    def setup_pipes(self):
        """파이프 초기화"""
        try:
            # 기존 파이프 정리
            for pipe_path in ["/tmp/python_to_swift", "/tmp/swift_to_python"]:
                if os.path.exists(pipe_path):
                    os.unlink(pipe_path)
                os.mkfifo(pipe_path)
            
            # 파이프 열기
            self.to_swift = open("/tmp/python_to_swift", "w", buffering=1)
            self.from_swift = open("/tmp/swift_to_python", "r", buffering=1)
            
        except Exception as e:
            print(f"파이프 설정 실패: {e}")
            raise
            
    def send_to_swift(self, message):
        """Swift 프로세스로 메시지 전송"""
        try:
            if self.to_swift is None:
                raise RuntimeError("파이프가 초기화되지 않았습니다")
            self.to_swift.write(f"{message}\n")
            self.to_swift.flush()
        except Exception as e:
            print(f"메시지 전송 실패: {e}")
            raise
            
    def initialize(self):
        """비동기 초기화"""
        try:
            # 파이프 설정
            self.setup_pipes()
            self.initialized = True
            return True
        except Exception as e:
            print(f"초기화 실패: {e}")
            return False

    def init_pipes(self):
        try:
            self.setup_pipes()
            self.start_swift_monitor()
        except Exception as e:
            print(f"파이프 초기화 중 오류: {e}")
            if self.update_gui_callback:
                self.update_gui_callback({"error": str(e)})
    
    def start_swift_monitor(self):
        """Swift 모니터 시작"""
        try:
            # 1. Swift 프로그램 경로 확인
            current_dir = os.path.dirname(os.path.abspath(__file__))
            swift_path = os.path.join(current_dir, "ParagraphManager")
            
            if not os.path.exists(swift_path):
                raise FileNotFoundError(
                    f"Swift 실행 파일을 찾을 수 없습니다: {swift_path}\n"
                    f"다음 명령어로 컴파일하세요:\n"
                    f"cd {current_dir} && swiftc ParagraphManager.swift -o ParagraphManager"
                )
                
            # 2. 실행 권한 확인 및 설정
            if not os.access(swift_path, os.X_OK):
                os.chmod(swift_path, 0o755)
                
            # 3. Swift 프로세스 시작
            self.swift_process = subprocess.Popen(
                [swift_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # 4. 프로세스 상태 확인
            time.sleep(0.5)  # 프로세스 시작 대기
            if self.swift_process.poll() is not None:
                _, stderr = self.swift_process.communicate()
                raise RuntimeError(f"Swift 프로세스 실행 실패: {stderr.decode()}")
                
            print(f"Swift 모니터 시작됨 (PID: {self.swift_process.pid})")
            
        except Exception as e:
            print(f"Swift 모니터 시작 실패: {e}")
            raise
            
    def __del__(self):
        self.should_run = False
        if self.swift_process:
            self.swift_process.terminate()
        if hasattr(self, 'to_swift'):
            self.to_swift.close()
        if hasattr(self, 'from_swift'):
            self.from_swift.close()
        
        # 파이프 파일 정리
        for pipe_path in ["/tmp/python_to_swift", "/tmp/swift_to_python"]:
            try:
                if os.path.exists(pipe_path):
                    os.unlink(pipe_path)
            except OSError:
                pass
        try:
            if hasattr(self, 'swift_process') and self.swift_process:
                self.swift_process.terminate()
        except Exception as e:
            print(f"프로세스 종료 중 오류: {e}")
        
    @throttle(seconds=0.1)
    def handle_paste(self):
        if self.blocked:
            return
        recent_clipboard_content = pyperclip.paste()
        if not self.paragraphs:
            self.update_gui_callback("파일을 불러오세요")
            return
        if not recent_clipboard_content in self.paragraphs:
            self.update_gui_callback("프로그램 중지")
            return
        # time.sleep(0.05)
        time.sleep(0.1)
        self.add_index_and_copy()
    def load_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                self.paragraphs = []
                for p in content.split('\n\n'):
                    temp=p.strip()
                    removeChars=["=","-","ㅡ","페이지"]

                    for c in removeChars:
                        temp=temp.replace(c,"")
                    if temp == "" or temp.strip().isdigit():
                        print("스킵: ",p)
                        continue
                    self.paragraphs.append(p)
                    
                    
                # self.paragraphs = [p for p in content.split('\n\n') if p and p not in ["2", "----"]]
                self.paragraphs = ["[start]"] + self.paragraphs + ["[end]"]
                self.index=1
                self.copy_current_text()
                # Swift로 단락 데이터 전송
                self.send_to_swift(f"SET_PARAGRAPHS:{('|').join(self.paragraphs)}")
            return True
        except Exception as e:
            print(f"Failed to read file: {e}")
            return False
        
    def update_index(self, new_index):
        self.index = new_index
        self.send_to_swift(f"SET_INDEX:{new_index}")
        
    def add_index(self):
        if len(self.paragraphs)<=self.index+2:
            return
        self.index+=1
    
    @throttle(seconds=0.1)
    def add_index_and_copy(self):
        self.add_index()
        self.copy_current_text()
        self.update_gui_callback()
        
    def sub_index(self):
        if self.index<=1:
            return
        self.index-=1
    
    @throttle(seconds=0.1)
    def sub_index_and_copy(self):
        self.sub_index()
        self.copy_current_text()
        self.update_gui_callback()
        
    
    def copy_current_text(self):
        current_text=self.get_current_text()
        print("문장 복사 < ",current_text.split('\n')[0],len(self.paragraphs),self.index)
        if current_text == "파일을 불러오세요":
            return False
        pyperclip.copy(self.get_current_text())
    
    def get_current_text(self):
        if not self.paragraphs:
            return "파일을 불러오세요"
        return self.paragraphs[self.index]
    
    def get_prev_text(self):
        try:
            if not self.paragraphs:
                return "파일을 불러오세요"
            if self.index <= 0:
                return "이전 문단이 없습니다"
            return self.paragraphs[self.index - 1]
        except IndexError:
            return "문단 인덱스 오류"
    
    def get_next_text(self):
        if not self.paragraphs:
            return "파일을 불러오세요"
        return self.paragraphs[(self.index+1)%len(self.paragraphs)]
    
    def handle_swift_message(self, message):
        try:
            msg_type, content = message.split(':', 1)
            
            if msg_type == "ERROR":
                self.show_error(content)
            elif msg_type == "INFO":
                self.show_info(content)
            elif msg_type in ["SUCCESS", "FAIL"]:
                self.handle_validation_result(msg_type == "SUCCESS")
                
        except Exception as e:
            print(f"메시지 처리 실패: {e}")
            
    def show_error(self, message):
        if self.update_gui_callback:
            self.update_gui_callback({
                'type': 'error',
                'message': message
            })
        
class StatusOverlay:
    def __init__(self, master):
        self.window = tk.Toplevel(master)
        self.window.overrideredirect(True)
        self.window.attributes(
            '-topmost', True,
            '-alpha', 0.9  # 투명도 설정 (0.0 ~ 1.0)
        )
        self.window.geometry("400x150+50+50")
        
        # 다크모드 감지 및 색상 설정
        if darkdetect.isDark():
            bg_color = '#333333'
            fg_color = 'white'
        else:
            bg_color = '#EEEEEE'
            fg_color = 'black'
            
        self.window.configure(bg=bg_color)
        
        # 레이블 생성
        self.prev_label = tk.Label(self.window, wraplength=380, bg=bg_color, fg=fg_color)
        self.current_label = tk.Label(self.window, wraplength=380, bg=bg_color, fg=fg_color)
        self.next_label = tk.Label(self.window, wraplength=380, bg=bg_color, fg=fg_color)
        
        self.prev_label.pack(pady=5)
        self.current_label.pack(pady=5)
        self.next_label.pack(pady=5)
        
    def update_paragraph_text(self, prev_text, current_text, next_text, maxCharPerline=50):
        display = {"prev": prev_text, "current": current_text, "next": next_text}
        
        for key in display:
            text = display[key]
            text = text.replace("\n", " ")
            text = "\n".join(map(lambda x: x if len(x)<maxCharPerline else x[:maxCharPerline]+"...", text.split("\n")))
            display[key] = text
            
        self.prev_label.config(text=f"이전: {display['prev']}")
        self.current_label.config(text=f"현재: {display['current']}")
        self.next_label.config(text=f"다음: {display['next']}")

class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SB2T")
        self.geometry("500x300")
        
        # 기본 상태
        self.paragraphs = []
        self.current_index = 0
        
        # GUI 요소 생성
        self.create_widgets()
        
        # 오버레이 초기화
        self.overlay = StatusOverlay(self)
        
        # Swift 프로세스 시작
        self.start_swift_process()
        
    def create_widgets(self):
        # 상태 표시 레이블
        self.status_label = tk.Label(self, text="시작 중...", wraplength=400)
        self.status_label.pack(pady=10)
        
        # 파일 열기 버튼
        self.file_button = tk.Button(
            self, 
            text="파일 열기",
            command=self.load_file,
        )
        self.file_button.pack(pady=5)
        
    def start_swift_process(self):
        try:
            # Swift 경로 확인
            swift_path = Path(__file__).parent / "ParagraphManager"
            print(f"Swift 경로: {swift_path}")
            
            # 컴파일 상태 확인
            if not swift_path.exists():
                print("Swift 파일 컴파일 시작...")
                compile_result = subprocess.run([
                    "swiftc",
                    str(Path(__file__).parent / "ParagraphManager.swift"),
                    "-o",
                    str(swift_path)
                ], capture_output=True, text=True)
                
                if compile_result.returncode != 0:
                    raise RuntimeError(f"컴파일 실패:\n{compile_result.stderr}")
                print("컴파일 완료")
            
            # 실행 권한 확인 및 설정
            if not os.access(swift_path, os.X_OK):
                print("실행 권한 설정...")
                os.chmod(swift_path, 0o755)
            
            # 프로세스 시작
            print("Swift 프로세스 시작 중...")
            self.swift_process = subprocess.Popen(
                [str(swift_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # 프로세스 상태 확인
            time.sleep(0.5)
            if self.swift_process.poll() is not None:
                stdout, stderr = self.swift_process.communicate()
                raise RuntimeError(f"프로세스 즉시 종료됨:\nstdout: {stdout}\nstderr: {stderr}")
                
            print(f"Swift 프로세스 시작됨 (PID: {self.swift_process.pid})")
            self.status_label.config(text="준비 완료")
            
        except Exception as e:
            error_msg = f"Swift 초기화 실패: {str(e)}"
            print(error_msg)
            self.status_label.config(text=error_msg)
            messagebox.showerror("오류", error_msg)
            
    def load_file(self):
        try:
            filepath = filedialog.askopenfilename(
                filetypes=[("텍스트 파일", "*.txt")]
            )
            if filepath:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.paragraphs = ["[시작]"] + [p.strip() for p in content.split('\n\n') if p.strip()] + ["[끝]"]
                    self.current_index = 1
                    self.status_label.config(text=f"파일 로드됨: {Path(filepath).name}")
        except Exception as e:
            self.status_label.config(text=f"파일 로드 실패: {e}")
            messagebox.showerror("오류", str(e))

if __name__ == "__main__":
    app = Application()
    app.mainloop()
