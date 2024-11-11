import os
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import darkdetect
import Quartz
import json
import pyperclip
from pynput import keyboard
import time
from datetime import datetime, timedelta
from functools import wraps
import appdirs
import subprocess
from pathlib import Path
import threading
import stat

class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SB2T")
        self.geometry("500x300")
        print("GUI 초기화 시작")

        # GUI 요소 생성
        self.create_widgets()
        print("GUI 위젯 생성 완료")

        # 오버레이 초기화
        self.overlay = StatusOverlay(self)
        print("오버레이 초기화 완료")

        # Progress Bar
        self.progress = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self, variable=self.progress, maximum=100)
        self.progress_bar.pack(pady=10)
        print("Progress Bar 생성 완료")

        # 기본 상태
        self.clipboard_manager = ClipboardManager(self.update_overlay)
        print("ClipboardManager 초기화 완료")

        # GUI 로드 후에 ClipboardManager 시작
        # self.after(100, self.start_clipboard_manager)  # 제거됨
        print("ClipboardManager 시작 예약됨")

    def create_widgets(self):
        """GUI 위젯 생성"""
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

    # def start_clipboard_manager(self):
    #     print("ClipboardManager 시작")
    #     self.clipboard_manager.start()
    #     print("ClipboardManager 비동기적으로 시작됨")
    #     # `start_swift_process` 호출 제거

    # # `start_swift_process` 메서드 제거

    def update_overlay(self, _=None):
        prev_text = self.clipboard_manager.get_prev_text()
        current_text = self.clipboard_manager.get_current_text()
        next_text = self.clipboard_manager.get_next_text()
        self.overlay.update_paragraph_text(prev_text, current_text, next_text)

    def load_file(self):
        try:
            filepath = filedialog.askopenfilename(
                filetypes=[("텍스트 파일", "*.txt")]
            )
            if filepath:
                if self.clipboard_manager.load_file(filepath):
                    self.status_label.config(text=f"파일 로드됨: {Path(filepath).name}")
                    self.update_overlay()
        except Exception as e:
            self.status_label.config(text=f"파일 로드 실패: {e}")
            messagebox.showerror("오류", str(e))

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
            text = "\n".join(map(lambda x: x if len(x) < maxCharPerline else x[:maxCharPerline] + "...", text.split("\n")))
            display[key] = text
            
        self.prev_label.config(text=f"이전: {display['prev']}")
        self.current_label.config(text=f"현재: {display['current']}")
        self.next_label.config(text=f"다음: {display['next']}")

cache_name = "cachedIndex.json"
appdir_path = appdirs.user_cache_dir("ParagraphManager", False)
cache_path = os.path.join(appdir_path, cache_name)
print("Cache Path: ", cache_path)
if not os.path.exists(appdir_path):
    os.makedirs(appdir_path)

class throttle(object):
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
        self.blocked = False
        self.index = 0
        self.paragraphs = []
        self.cmd_pressed = False
        self.v_pressed = False
        self.alt_pressed = False

        # 키보드 리스너 설정
        self.listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        self.listener.start()
        print("Keyboard Listener 시작됨")

        # 이벤트 탭을 별도의 스레드에서 시작 (중복 제거)
        threading.Thread(target=self.start_event_tap, daemon=True).start()
        print("Cmd + V 입력 감지를 시작합니다...")

    def start_event_tap(self):
        # 파이프 파일 대기 및 생성
        self.waitForPipes()
        print("파이프 파일 대기 완료")
        
        # Quartz 이벤트 탭 설정
        event_tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionDefault,
            Quartz.CGEventMaskBit(Quartz.kCGEventKeyUp),
            self.callback_proxy,
            None
        )  # 여분의 ')' 제거됨

        if not event_tap:
            print("Failed to create event tap!")
            return

        run_loop_source = Quartz.CFMachPortCreateRunLoopSource(None, event_tap, 0)
        run_loop = Quartz.CFRunLoopGetCurrent()
        Quartz.CFRunLoopAddSource(
            run_loop,
            run_loop_source,
            Quartz.kCFRunLoopCommonModes
        )
        Quartz.CGEventTapEnable(event_tap, True)

        # RunLoop 실행
        Quartz.CFRunLoopRun()

    def callback_proxy(self, proxy, event_type, event, refcon):
        if event_type == Quartz.kCGEventKeyUp:
            cmd_key_down = Quartz.CGEventGetFlags(event) & Quartz.kCGEventFlagMaskCommand
            # V 키가 눌렸는지 확인 (V key code = 9)
            v_key_down = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode) == 9

            if cmd_key_down and v_key_down:
                print("Cmd + V 감지!")
                self.handle_paste()

        return event

    def on_press(self, key):
        pass

    def on_release(self, key):
        pass

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
        time.sleep(0.1)
        self.add_index_and_copy()

    def load_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                self.paragraphs = []
                for p in content.split('\n\n'):
                    temp = p.strip()
                    removeChars = ["=", "-", "ㅡ", "페이지"]

                    for c in removeChars:
                        temp = temp.replace(c, "")
                    if temp == "" or temp.strip().isdigit():
                        print("스킵: ", p)
                        continue
                    self.paragraphs.append(p)
                    
                self.paragraphs = ["[start]"] + self.paragraphs + ["[end]"]
                self.index = 1
                self.copy_current_text()
                self.update_gui_callback()
            return True
        except Exception as e:
            print(f"Failed to read file: {e}")
            return False
        
    def update_index(self, new_index):
        self.index = new_index
        
    def add_index(self):
        if len(self.paragraphs) <= self.index + 2:
            return
        self.index += 1
    
    @throttle(seconds=0.1)
    def add_index_and_copy(self):
        self.add_index()
        self.copy_current_text()
        self.update_gui_callback()
        
    def sub_index(self):
        if self.index <= 1:
            return
        self.index -= 1
    
    @throttle(seconds=0.1)
    def sub_index_and_copy(self):
        self.sub_index()
        self.copy_current_text()
        self.update_gui_callback()
        
    def copy_current_text(self):
        current_text = self.get_current_text()
        print("문장 복사 < ", current_text.split('\n')[0], len(self.paragraphs), self.index)
        if current_text == "파일을 불러오세요":
            return False
        pyperclip.copy(current_text)
        return True
    
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
        return self.paragraphs[(self.index + 1) % len(self.paragraphs)]
    
    def handle_swift_message(self, message):
        try:
            msg_type, content = message.split(':', 1)
            
            if msg_type == "ERROR":
                self.show_error(content)
            elif msg_type == "INFO":
                self.show_info(content)  # show_info 메서드 추가
            elif msg_type == "SUCCESS":
                self.add_index_and_copy()
            elif msg_type == "FAIL":
                self.update_gui_callback("프로그램 중지")
            elif msg_type == "COPY_NEXT_PARAGRAPH":
                self.add_index_and_copy()
            elif msg_type == "COPY_PREV_PARAGRAPH":
                self.sub_index_and_copy()
            elif msg_type == "COPY_STOP_PARAGRAPH":
                self.blocked = True
            elif msg_type == "COPY_RESUME_PARAGRAPH":
                self.blocked = False
                
        except Exception as e:
            print(f"메시지 처리 실패: {e}")
    
    def show_info(self, message):
        if self.update_gui_callback:
            self.update_gui_callback({
                'type': 'info',
                'message': message
            })
            
    def show_error(self, message):
        if self.update_gui_callback:
            self.update_gui_callback({
                'type': 'error',
                'message': message
            })
        
    def waitForPipes(self):
        inputPipePath = "/tmp/python_to_swift"
        outputPipePath = "/tmp/swift_to_python"

        # 파이프가 없으면 생성
        if not os.path.exists(inputPipePath):
            os.mkfifo(inputPipePath)
            print(f"파이프 생성됨: {inputPipePath}")
        if not os.path.exists(outputPipePath):
            os.mkfifo(outputPipePath)
            print(f"파이프 생성됨: {outputPipePath}")

        while not (os.path.exists(inputPipePath) and os.path.exists(outputPipePath)):
            print("파이프 파일이 생성될 때까지 대기 중...")
            time.sleep(0.1)

if __name__ == "__main__":
    print("프로그램 시작")
    app = Application()
    print("메인 루프 진입")
    app.mainloop()