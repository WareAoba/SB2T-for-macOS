import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import darkdetect
import pyperclip
import time
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
import threading
import json

class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SB2T")
        self.geometry("500x300")
        self.configure_gui()
        print("GUI 설정 완료")  # 추가
        self.create_widgets()
        print("위젯 생성 완료")  # 추가
        self.overlay = StatusOverlay(self)
        print("Overlay 초기화 완료")  # 추가
        self.clipboard_manager = ClipboardManager(self)
        print("ClipboardManager 초기화 완료")  # 추가
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        print("Application 초기화 완료")  # 추가

    def configure_gui(self):
        """OS 테마에 따라 GUI 설정"""
        if darkdetect.isDark():
            self.style = ttk.Style(self)
            self.style.theme_use('clam')
            self.style.configure('.', background='#333333', foreground='white')
            self.configure(bg='#333333')
        else:
            self.style = ttk.Style(self)
            self.style.theme_use('clam')
            self.style.configure('.', background='#EEEEEE', foreground='black')
            self.configure(bg='#EEEEEE')

    def create_widgets(self):
        """GUI 위젯 생성"""
        self.status_label = tk.Label(self, text="시작 중...", wraplength=400)
        self.status_label.pack(pady=10)

        self.file_button = tk.Button(
            self, 
            text="파일 열기",
            command=self.load_file,
        )
        self.file_button.pack(pady=5)
    
    def load_file(self):
        """텍스트 파일 불러오기 및 전처리"""
        filepath = filedialog.askopenfilename(
            filetypes=[("텍스트 파일", "*.txt")]
        )
        if filepath:
            success = self.clipboard_manager.load_file(filepath)
            if success:
                self.status_label.config(text=f"파일 로드됨: {Path(filepath).name}")
                self.overlay.update_overlay()
                self.clipboard_manager.copy_current_paragraph()
            else:
                self.status_label.config(text="파일 로드 실패")
                messagebox.showerror("오류", "파일을 불러오는 데 실패했습니다.")
    
    def on_close(self):
        """프로그램 종료 시 클립보드 매니저 종료"""
        self.clipboard_manager.stop()
        self.destroy()

class StatusOverlay(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.overrideredirect(True)
        self.attributes('-topmost', True, '-alpha', 0.8)
        self.geometry("400x150+50+50")
        self.configure_overlay()
        print("Overlay 색상 설정 완료")  # 추가
        self.create_labels()
        print("Overlay 레이블 생성 완료")  # 추가
    
    def configure_overlay(self):
        """OS 테마에 따라 Overlay 색상 설정"""
        if darkdetect.isDark():
            bg_color = '#333333'
            fg_color = 'white'
        else:
            bg_color = '#EEEEEE'
            fg_color = 'black'
        self.configure(bg=bg_color)
    
    def create_labels(self):
        """이전, 현재, 다음 문단을 표시할 레이블 생성"""
        self.prev_label = tk.Label(self, wraplength=380, bg=self['bg'], fg='white' if darkdetect.isDark() else 'black')
        self.current_label = tk.Label(self, wraplength=380, bg=self['bg'], fg='white' if darkdetect.isDark() else 'black')
        self.next_label = tk.Label(self, wraplength=380, bg=self['bg'], fg='white' if darkdetect.isDark() else 'black')
        
        self.prev_label.pack(pady=5)
        self.current_label.pack(pady=5)
        self.next_label.pack(pady=5)
    
    def update_overlay(self, prev_text="", current_text="", next_text=""):
        """Overlay 창에 문단 정보 업데이트"""
        self.prev_label.config(text=f"이전: {prev_text}")
        self.current_label.config(text=f"현재: {current_text}")
        self.next_label.config(text=f"다음: {next_text}")

def throttle(seconds=0.1):
    """함수 호출을 제한하는 데코레이터"""
    def decorator(fn):
        last_call = [datetime.min]
        
        @wraps(fn)
        def wrapper(*args, **kwargs):
            now = datetime.now()
            if now - last_call[0] > timedelta(seconds=seconds):
                last_call[0] = now
                return fn(*args, **kwargs)
        return wrapper
    return decorator

class ClipboardManager:
    def __init__(self, app):
        self.app = app
        self.paragraphs = []
        self.current_index = 0
        self.blocked = False
        self.input_pipe = None
        self.output_pipe = None
        self.running = True
        self.init_pipes()
        print("파이프 초기화 완료")  # 추가
        self.start_clipboard_listener()
        print("클립보드 리스너 시작")  # 추가
        self.start_communication_thread()
        print("Swift와의 통신 스레드 시작")  # 추가
        print("ClipboardManager 초기화 완료")
    
    def init_pipes(self):
        """파이프 파일 초기화"""
        input_pipe_path = "/tmp/python_to_swift"
        output_pipe_path = "/tmp/swift_to_python"
        if not os.path.exists(input_pipe_path):
            os.mkfifo(input_pipe_path)
            print(f"파이프 생성됨: {input_pipe_path}")
        if not os.path.exists(output_pipe_path):
            os.mkfifo(output_pipe_path)
            print(f"파이프 생성됨: {output_pipe_path}")
        
        self.input_pipe = open(input_pipe_path, 'r')
        self.output_pipe = open(output_pipe_path, 'w')
        print("파이프 초기화 완료")
    
    def load_file(self, file_path):
        """텍스트 파일 로드 및 문단 분리"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            print(f"파일 읽기 완료: {file_path}")  # 추가
            self.paragraphs = []
            for p in content.split('\n\n'):
                temp = p.strip()
                remove_chars = ["=", "-", "ㅡ", "페이지"]
                for c in remove_chars:
                    temp = temp.replace(c, "")
                if temp == "" or temp.isdigit():
                    print(f"스킵된 문단: {p}")  # 추가
                    continue
                self.paragraphs.append(p.strip())
            self.paragraphs = ["[start]"] + self.paragraphs + ["[end]"]
            self.current_index = 1
            print(f"문단 분리 완료. 총 문단 수: {len(self.paragraphs)}")  # 추가
            return True
        except Exception as e:
            print(f"파일 로드 실패: {e}")
            return False
    
    def copy_current_paragraph(self):
        """현재 문단을 클립보드에 복사하고 Overlay 업데이트"""
        if not self.paragraphs:
            self.app.status_label.config(text="파일을 불러오세요")
            print("클립보드 복사 실패: 문단 없음")  # 추가
            return
        current_text = self.paragraphs[self.current_index]
        pyperclip.copy(current_text)
        print(f"클립보드에 복사됨: {current_text[:30]}...")  # 추가
        prev_text = self.paragraphs[self.current_index - 1] if self.current_index > 0 else ""
        next_text = self.paragraphs[self.current_index + 1] if self.current_index < len(self.paragraphs) -1 else ""
        self.app.overlay.update_overlay(prev_text, current_text, next_text)
        print(f"Overlay 업데이트 완료: 이전={prev_text[:30]}..., 현재={current_text[:30]}..., 다음={next_text[:30]}...")  # 추가
    
    @throttle(seconds=0.1)
    def handle_paste(self):
        """Swift로부터의 메시지에 따른 동작 처리"""
        recent_clipboard = pyperclip.paste()
        print(f"클립보드 내용 확인: {recent_clipboard[:30]}...")  # 추가
        if not self.paragraphs:
            self.app.status_label.config(text="파일을 불러오세요")
            print("프로그램 중지: 문단 없음")  # 추가
            return
        if recent_clipboard not in self.paragraphs:
            self.app.status_label.config(text="프로그램 중지")
            print("프로그램 중지: 클립보드 불일치")  # 추가
            return
        print("클립보드 일치 확인")  # 추가
        self.add_index_and_copy()
    
    def start_clipboard_listener(self):
        """키보드 리스너 시작 (필요 시 구현)"""
        # 현재 ClipboardManager는 Swift와 통신을 통해 클립보드를 관리합니다.
        pass
    
    def start_communication_thread(self):
        """Swift와의 통신을 위한 스레드 시작"""
        threading.Thread(target=self.listen_to_swift, daemon=True).start()
    
    def listen_to_swift(self):
        """Swift로부터 메시지를 수신하고 처리"""
        while self.running:
            try:
                data = self.input_pipe.read()
                if data:
                    print(f"받은 데이터: {data.strip()}")  # 추가
                    commands = data.strip().split('\n')
                    for command in commands:
                        self.process_command(command)
                else:
                    time.sleep(0.1)
            except Exception as e:
                print(f"Swift 통신 오류: {e}")
                time.sleep(0.1)
    
    def process_command(self, command):
        """수신된 명령을 처리"""
        components = command.split(':', 1)
        if len(components) != 2:
            print(f"잘못된 명령 형식: {command}")
            return
        cmd_type, content = components
        print(f"명령 처리 시작 - 타입: {cmd_type}, 내용: {content}")  # 추가
        if cmd_type == "COPY_NEXT_PARAGRAPH":
            self.copy_next_paragraph()
        elif cmd_type == "COPY_PREV_PARAGRAPH":
            self.copy_prev_paragraph()
        elif cmd_type == "COPY_STOP_PARAGRAPH":
            self.blocked = True
            self.app.status_label.config(text="프로그램 일시정지")
            print("프로그램 일시정지")  # 추가
        elif cmd_type == "COPY_RESUME_PARAGRAPH":
            self.blocked = False
            self.app.status_label.config(text="프로그램 재개")
            self.copy_current_paragraph()
            print("프로그램 재개")  # 추가
        elif cmd_type == "SUCCESS":
            self.app.status_label.config(text="클립보드 일치")
            print("클립보드 일치")  # 추가
        elif cmd_type == "FAIL":
            self.app.status_label.config(text="클립보드 불일치")
            print("클립보드 불일치")  # 추가
        elif cmd_type == "INFO":
            self.app.status_label.config(text=content)
            print(f"정보 메시지 수신: {content}")  # 추가
        elif cmd_type == "ERROR":
            self.app.status_label.config(text=content)
            messagebox.showerror("오류", content)
            print(f"오류 메시지 수신: {content}")  # 추가
        else:
            print(f"알 수 없는 명령 타입: {cmd_type}")  # 추가
    
    def copy_next_paragraph(self):
        """다음 문단으로 이동 및 복사"""
        if self.current_index < len(self.paragraphs) - 1:
            self.current_index += 1
            self.copy_current_paragraph()
            self.send_message("SUCCESS", "다음 문단 복사")
        else:
            self.send_message("INFO", "마지막 문단입니다.")
    
    def copy_prev_paragraph(self):
        """이전 문단으로 이동 및 복사"""
        if self.current_index > 0:
            self.current_index -= 1
            self.copy_current_paragraph()
            self.send_message("SUCCESS", "이전 문단 복사")
        else:
            self.send_message("INFO", "첫 번째 문단입니다.")
    
    def add_index_and_copy(self):
        """인덱스 증가 및 현재 문단 복사"""
        if self.current_index < len(self.paragraphs) - 1:
            self.current_index += 1
            self.copy_current_paragraph()
            self.send_message("SUCCESS", "다음 문단 복사")
        else:
            self.send_message("INFO", "마지막 문단입니다.")
    
    def sub_index_and_copy(self):
        """인덱스 감소 및 현재 문단 복사"""
        if self.current_index > 0:
            self.current_index -= 1
            self.copy_current_paragraph()
            self.send_message("SUCCESS", "이전 문단 복사")
        else:
            self.send_message("INFO", "첫 번째 문단입니다.")
    
    def send_message(self, msg_type, content):
        """Swift로 메시지 전송"""
        message = f"{msg_type}:{content}\n"
        try:
            self.output_pipe.write(message)
            self.output_pipe.flush()
            print(f"Swift로 메시지 전송: {message.strip()}")  # 추가
        except Exception as e:
            print(f"메시지 전송 실패: {e}")  # 추가
    
    def stop(self):
        """프로그램 정지"""
        self.running = False
        if self.input_pipe:
            self.input_pipe.close()
        if self.output_pipe:
            self.output_pipe.close()
        print("ClipboardManager 종료됨")

if __name__ == "__main__":
    app = Application()
    app.mainloop()
