import os
import threading
import Quartz
import pyperclip
import appdirs
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from functools import wraps

cache_name = "cachedIndex.json"
appdir_path = appdirs.user_cache_dir("ParagraphManager", False)
cache_path = os.path.join(appdir_path, cache_name)
print("Cache Path: ", cache_path)
if not os.path.exists(appdir_path):
    os.makedirs(appdir_path)

def throttle(seconds=0.1):
    def decorator(func):
        last_call = [0.0]

        @wraps(func)
        def wrapper(*args, **kwargs):
            now = datetime.now().timestamp()
            if now - last_call[0] >= seconds:
                last_call[0] = now
                return func(*args, **kwargs)
        return wrapper
    return decorator

class ClipboardManager:
    def __init__(self):
        self.blocked = False
        self.index = 0
        self.paragraphs = []
        self.cmd_pressed = False
        self.v_pressed = False
        self.alt_pressed = False

        event_tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionDefault,
            Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown) | Quartz.CGEventMaskBit(Quartz.kCGEventKeyUp),
            self.callback_proxy,
            None
        )

        if not event_tap:
            print("Failed to create event tap.")
            return

        run_loop_source = Quartz.CFMachPortCreateRunLoopSource(None, event_tap, 0)
        Quartz.CFRunLoopAddSource(
            Quartz.CFRunLoopGetCurrent(),
            run_loop_source,
            Quartz.kCFRunLoopCommonModes
        )
        Quartz.CGEventTapEnable(event_tap, True)

        threading.Thread(target=self.run_loop, daemon=True).start()

    def run_loop(self):
        Quartz.CFRunLoopRun()
        print("Event loop exited")

    def callback_proxy(self, proxy, event_type, event, refcon):
        key_code = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
        flags = Quartz.CGEventGetFlags(event)

        if event_type == Quartz.kCGEventKeyDown:
            if key_code == 8:  # 'v' key
                self.v_pressed = True
            if flags & Quartz.kCGEventFlagMaskCommand:
                self.cmd_pressed = True
            if flags & Quartz.kCGEventFlagMaskAlternate:
                self.alt_pressed = True

        elif event_type == Quartz.kCGEventKeyUp:
            if key_code == 8:  # 'v' key
                self.v_pressed = False
            if not (flags & Quartz.kCGEventFlagMaskCommand):
                self.cmd_pressed = False
            if not (flags & Quartz.kCGEventFlagMaskAlternate):
                self.alt_pressed = False

        if self.cmd_pressed and self.v_pressed:
            self.handle_paste()

        return event

    def blockKeyboard(self):
        self.blocked = True

    def unblockKeyboard(self):
        self.blocked = False

    @throttle(seconds=0.1)
    def handle_paste(self):
        self.copy_current_text()

    def load_file(self, file_path):
        try:
            with open(file_path, 'r') as file:
                self.paragraphs = file.read().split('\n\n')
                self.index = 0
                self.copy_current_text()
        except Exception as e:
            print(f"Error loading file: {e}")

    def add_index(self):
        if len(self.paragraphs) <= self.index + 1:
            return
        self.index += 1

    @throttle(seconds=0.1)
    def add_index_and_copy(self):
        self.add_index()
        self.copy_current_text()

    def sub_index(self):
        if self.index <= 0:
            return
        self.index -= 1

    @throttle(seconds=0.1)
    def sub_index_and_copy(self):
        self.sub_index()
        self.copy_current_text()

    def copy_current_text(self):
        current_text = self.get_current_text()
        print("문장 복사 <", current_text.split('\n')[0], len(self.paragraphs), self.index)
        if current_text == "파일을 불러오세요":
            return
        pyperclip.copy(current_text)

    def get_current_text(self):
        if self.index < len(self.paragraphs):
            return self.paragraphs[self.index]
        return "파일을 불러오세요"

    def get_prev_text(self):
        if self.index > 0:
            return self.paragraphs[self.index - 1]
        return ""

    def get_next_text(self):
        if self.index < len(self.paragraphs) - 1:
            return self.paragraphs[self.index + 1]
        return ""

clipboard_manager = ClipboardManager()

app = Flask(__name__)

@app.route('/')
def index():
    return "Paragraph Manager API"

@app.route('/load_file', methods=['POST'])
def load_file():
    data = request.get_json()
    file_path = data.get('file_path')
    clipboard_manager.load_file(file_path)
    return jsonify(success=True)

@app.route('/get_paragraphs', methods=['GET'])
def get_paragraphs():
    return jsonify(
        previous=clipboard_manager.get_prev_text(),
        current=clipboard_manager.get_current_text(),
        next=clipboard_manager.get_next_text()
    )

@app.route('/next_paragraph', methods=['POST'])
def next_paragraph():
    clipboard_manager.add_index_and_copy()
    return jsonify(success=True)

@app.route('/prev_paragraph', methods=['POST'])
def prev_paragraph():
    clipboard_manager.sub_index_and_copy()
    return jsonify(success=True)

if __name__ == '__main__':
    app.run(port=5001)