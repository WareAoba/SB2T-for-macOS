import Quartz
import json
import os
import pyperclip
from pynput import keyboard
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from functools import wraps
import time
import appdirs
import threading

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
            now = time.time()
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

        self.listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        self.listener.start()

        event_tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionDefault,
            Quartz.CGEventMaskBit(Quartz.kCGEventKeyUp),
            self.callback_proxy,
            None
        )

        if not event_tap:
            print("Failed to create event tap!")
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
        if event_type == Quartz.kCGEventKeyUp:
            cmd_key_down = Quartz.CGEventGetFlags(event) & Quartz.kCGEventFlagMaskCommand
            v_keycode = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
            if cmd_key_down and v_keycode == 9:  # V 키의 키코드가 9입니다.
                print("Cmd + V 감지!")
                self.handle_paste()
        return event

    def blockKeyboard(self):
        self.blocked = True

    def unblockKeyboard(self):
        self.blocked = False

    def on_press(self, key):
        try:
            if key == keyboard.Key.cmd:
                self.cmd_pressed = True
            elif key == keyboard.Key.alt:
                self.alt_pressed = True
            elif hasattr(key, 'char') and key.char == 'v':
                self.v_pressed = True

            if self.alt_pressed:
                if key == keyboard.Key.left:
                    self.sub_index_and_copy()
                elif key == keyboard.Key.right:
                    self.add_index_and_copy()
                elif key == keyboard.Key.up:
                    self.unblockKeyboard()
                elif key == keyboard.Key.down:
                    self.blockKeyboard()

        except AttributeError:
            pass

    def on_release(self, key):
        try:
            if key == keyboard.Key.cmd:
                self.cmd_pressed = False
            elif key == keyboard.Key.alt:
                self.alt_pressed = False
            elif hasattr(key, 'char') and key.char == 'v':
                self.v_pressed = False
        except AttributeError:
            pass

    @throttle(seconds=0.1)
    def handle_paste(self):
        if self.blocked:
            return
        if not self.paragraphs:
            print("파일을 불러오세요")
            return
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
                        continue
                    self.paragraphs.append(p)

                self.paragraphs = ["[start]"] + self.paragraphs + ["[end]"]
                self.index = 1
                self.copy_current_text()
            return True
        except Exception as e:
            print(f"Failed to read file: {e}")
            return False

    def add_index(self):
        if len(self.paragraphs) <= self.index + 1:
            return
        self.index += 1

    @throttle(seconds=0.1)
    def add_index_and_copy(self):
        self.add_index()
        self.copy_current_text()

    def sub_index(self):
        if self.index <= 1:
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
            return False
        pyperclip.copy(current_text)

    def get_current_text(self):
        if not self.paragraphs:
            return "파일을 불러오세요"
        return self.paragraphs[self.index]

    def get_prev_text(self):
        if not self.paragraphs:
            return "파일을 불러오세요"
        return self.paragraphs[(self.index - 1) % len(self.paragraphs)]

    def get_next_text(self):
        if not self.paragraphs:
            return "파일을 불러오세요"
        return self.paragraphs[(self.index + 1) % len(self.paragraphs)]

clipboard_manager = ClipboardManager()

app = Flask(__name__)

@app.route('/load_file', methods=['POST'])
def load_file():
    data = request.get_json()
    file_path = data.get('file_path')
    success = clipboard_manager.load_file(file_path)
    return jsonify({'success': success})

@app.route('/get_paragraphs', methods=['GET'])
def get_paragraphs():
    current = clipboard_manager.get_current_text()
    prev = clipboard_manager.get_prev_text()
    next_p = clipboard_manager.get_next_text()
    return jsonify({
        'current': current,
        'previous': prev,
        'next': next_p
    })

@app.route('/next_paragraph', methods=['POST'])
def next_paragraph():
    clipboard_manager.add_index_and_copy()
    return jsonify({'status': 'success'})

@app.route('/prev_paragraph', methods=['POST'])
def prev_paragraph():
    clipboard_manager.sub_index_and_copy()
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(port=5001)  # 포트를 5001로 변경