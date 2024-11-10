import Quartz

import json
import os
import pyperclip
from pynput import keyboard
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import time
import darkdetect
from datetime import datetime, timedelta
from functools import wraps
import appdirs


cache_name="cachedIndex.json"
appdir_path=appdirs.user_cache_dir("ParagraphManager", False)
cache_path=os.path.join(appdir_path,cache_name)
print("Cache Path: ",cache_path)
if not os.path.exists(appdir_path):
    os.makedirs(appdir_path)
    
class throttle(object):
    """
    Decorator that prevents a function from being called more than once every
    time period.
    To create a function that cannot be called more than once a minute:
        @throttle(minutes=1)
        def my_fun():
            pass
    """
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
    def __init__(self,update_gui_callback=None):
        self.update_gui_callback = update_gui_callback
        self.blocked=False
        self.index=0
        self.paragraphs=[]
        self.cmd_pressed = False
        self.v_pressed = False
        self.alt_pressed = False
        
        # hotkeys = keyboard.GlobalHotKeys({
        #     '<ctrl>+v': self.handle_paste,
        #     # '<alt>+<left>': self.sub_index_and_copy,
        #     # '<alt>+<right>': self.add_index_and_copy,
        #     # '<alt>+<up>': self.unblockKeyboard,
        #     # '<alt>+<down>': self.blockKeyboard
        # })
        # self.listener = hotkeys
        # self.listener.start()
        
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

        print("Listening for Cmd + V events...")

    def callback_proxy(self,proxy, event_type, event, refcon):
        global paste_triggered

        if event_type == Quartz.kCGEventKeyUp:
            # Command 키가 눌려 있는지 확인
            cmd_key_down = Quartz.CGEventGetFlags(event) & Quartz.kCGEventFlagMaskCommand
            # V 키가 눌렸는지 확인 (V key code = 9)
            v_key_down = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode) == 9

            if cmd_key_down and v_key_down:
                print("Cmd + V 감지!")
                self.handle_paste()

        return event

    def blockKeyboard(self):
        self.blocked=True
        
    def unblockKeyboard(self):
        self.blocked=False
        
    def on_press(self, key):
        char=getattr(key, 'char', None)
        original_key=self.listener.canonical(key)
        try:
            if original_key == keyboard.Key.cmd:
                self.cmd_pressed = True
            elif char == 'v':
                self.v_pressed = True
                # if self.cmd_pressed:
                #     self.handle_paste()
            elif original_key == keyboard.Key.alt:
                self.alt_pressed = True
                
            # if self.cmd_pressed and self.v_pressed:
            #     self.handle_paste()
            
            if self.alt_pressed:
                print("Alt Pressed",key,original_key)
                if key == keyboard.Key.left:
                    self.sub_index_and_copy()
                elif key == keyboard.Key.right:
                    self.add_index_and_copy()
                elif key == keyboard.Key.up:
                    self.unblockKeyboard()
                elif key == keyboard.Key.down:
                    self.blockKeyboard()
        except AttributeError as e:
            print(e)

    def on_release(self, key):
        char=getattr(key, 'char', None)
        original_key=self.listener.canonical(key)
        try:
            if original_key == keyboard.Key.cmd:
                self.cmd_pressed = False
            elif original_key == keyboard.Key.alt:
                self.alt_pressed = False
            elif char == 'v':
                self.v_pressed = False
        except AttributeError as e:
            print(e)
        
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
            return True
        except Exception as e:
            print(f"Failed to read file: {e}")
            return False
        
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
        if not self.paragraphs:
            return "파일을 불러오세요"
        return self.paragraphs[(self.index-1)%len(self.paragraphs)]
    
    def get_next_text(self):
        if not self.paragraphs:
            return "파일을 불러오세요"
        return self.paragraphs[(self.index+1)%len(self.paragraphs)]
    
        
class StatusOverlay:
    def __init__(self, root):
        self.root = root
        self.window = tk.Toplevel(root)
        self.window.overrideredirect(True)
        # self.window.title("Paragraph Overlay")


        self.window.geometry("400x250+0+0")
        self.window.attributes("-topmost", True)

        #오버레이 반투명
        self.window.attributes("-alpha", 0.8)

        # self.window.overrideredirect(False)
        
        # Configure grid layout with three rows and one column
        self.window.rowconfigure(0, weight=1)
        self.window.rowconfigure(1, weight=1)
        self.window.rowconfigure(2, weight=1)
        self.window.columnconfigure(0, weight=1)

        self.prev_label = tk.Label(self.window, text="", font=("Helvetica", 14), wraplength=480, anchor="w")
        self.prev_label.grid(row=0, column=0, sticky="nsew", padx=10, pady=5)

        self.current_label = tk.Label(self.window, text="", font=("Helvetica", 14, "bold"), wraplength=480, anchor="w")
        self.current_label.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)

        self.next_label = tk.Label(self.window, text="", font=("Helvetica", 14), wraplength=480, anchor="w")
        self.next_label.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)

        #오버레이 이동
        self.window.bind("<Button-1>", self.start_move)
        self.window.bind("<B1-Motion>", self.do_move)

    def start_move(self, event):
        self._x = event.x
        self._y = event.y

    def do_move(self, event):
        x = self.window.winfo_x() + (event.x - self._x)
        y = self.window.winfo_y() + (event.y - self._y)
        self.window.geometry(f"+{x}+{y}")

    def update_paragraph_text(self, prev_text, current_text, next_text):
        maxCharPerline=50
        maxLines=2
        display={"prev":prev_text, "current":current_text, "next":next_text}
        # handle prev_text, current_text, next_text
        for key in display:
            # if key == "current":
            #     maxCharPerline=30
            text=display[key]
            # if text.count("\n")>maxLines:
            #     text="\n".join(text.split("\n")[:maxLines])+"\n..."
            text=text.replace("\n", " ")
            text="\n".join(map(lambda x: x if len(x)<maxCharPerline else x[:maxCharPerline]+"...", text.split("\n")))
            display[key]=text
        self.prev_label.config(text=f"이전: {display['prev']}")
        self.current_label.config(text=f"현재: {display['current']}")
        self.next_label.config(text=f"다음: {display['next']}")

class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Paragraph Manager")
        self.geometry("500x300+500+500")
        # self.set_theme()
        self.clipboard_manager = ClipboardManager(self.update_gui)
        self.create_widgets()

        
        self.overlay = StatusOverlay(self)
        self.update_gui()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        # AttributeError: '_tkinter.tkapp' object has no attribute 'loaded_file_path'
        if hasattr(self,"loaded_file_path"):
            with open(cache_path,"w+", encoding='utf-8') as f:
                json.dump({self.loaded_file_path:self.clipboard_manager.index},f)
        self.destroy()

    def set_theme(self):
        if darkdetect.isDark():
            self.style = {
                "bg": '#1e1e1e',
                "fg": '#ffffff',
                "button_bg": '#2d2d2d',
                "button_fg": '#ffffff'
            }
        else:
            self.style = {
                "bg": '#f0f0f0',
                "fg": '#000000',
                "button_bg": '#e0e0e0',
                "button_fg": '#000000'
            }
        self.configure(bg=self.style['bg'])


    def create_widgets(self):

        # In create_widgets()


        self.file_button = tk.Button(self, text="Load File", command=self.load_file)
        self.file_button.pack(pady=10)

        self.paragraph_label = tk.Label(self, text="", font=("Helvetica", 16),  wraplength=480)
        self.paragraph_label.pack(pady=10)

        # Create a frame to hold the bottom buttons
        bottom_frame = tk.Frame(self)
        bottom_frame.pack(side=tk.BOTTOM, pady=10)

        self.prev_button = tk.Button(bottom_frame, text="<", command=self.previous_paragraph)
        self.prev_button.pack(side=tk.LEFT, padx=5)


        self.next_button = tk.Button(bottom_frame, text=">", command=self.next_paragraph)
        self.next_button.pack(side=tk.LEFT, padx=5)
        
        self.copy_current_button = tk.Button(bottom_frame, text="Copy Current Paragraph", command=self.copy_current_text)
        self.copy_current_button.pack(side=tk.LEFT, padx=5)

    
    def copy_current_text(self):
        self.clipboard_manager.copy_current_text()
        self.update_gui()
    def load_file(self):
        target_path = filedialog.askopenfilename()
        
        
        if self.clipboard_manager.load_file(target_path):
            self.loaded_file_path = target_path
            
            try:
                with open(cache_path,"r") as f:
                    cacheMap=json.load(f)
                if target_path in cacheMap:                    
                    loadLastIndex=messagebox.askyesno("진행상황 불러오기","이전에 봤던 대사부터 시작하시겠습니까?")
                    if loadLastIndex:
                        self.clipboard_manager.index=cacheMap[target_path]
            except Exception as e:
                print(e)
            self.update_gui()
            
    def update_gui(self, mainGuiText=None):
        current_text = self.clipboard_manager.get_current_text().replace("\n", " ")
        self.paragraph_label.config(text=mainGuiText if mainGuiText else current_text)
        self.overlay.update_paragraph_text(self.clipboard_manager.get_prev_text(), self.clipboard_manager.get_current_text(), self.clipboard_manager.get_next_text())
        
    def previous_paragraph(self):
        self.clipboard_manager.sub_index_and_copy()
        self.update_gui()
        
    def next_paragraph(self):
        self.clipboard_manager.add_index_and_copy()
        self.update_gui()   
        
        
if __name__ == "__main__":
    app = Application()
    app.mainloop()
