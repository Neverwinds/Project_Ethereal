import customtkinter as ctk
import threading
import time
from PIL import Image
import config
# 注意：这里我们只导入类，但不立即实例化
from agent import EtherealBot

# 设置外观模式
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

class ChatBubble(ctk.CTkFrame):
    """自定义聊天气泡组件"""
    def __init__(self, master, text, is_user=True, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0) if is_user else self.columnconfigure(1, weight=1)
        
        bubble_color = "#2b2b2b" if is_user else "#1f2937"
        text_color = "#ffffff" if is_user else "#e0e7ff"
        
        self.bubble = ctk.CTkLabel(
            self, 
            text=text, 
            fg_color=bubble_color, 
            text_color=text_color,
            corner_radius=15,
            wraplength=400,
            justify="left",
            font=("Microsoft YaHei UI", 14),
            padx=15, pady=10
        )
        if is_user:
            self.bubble.grid(row=0, column=1, sticky="e", padx=(50, 10), pady=5)
        else:
            self.bubble.grid(row=0, column=0, sticky="w", padx=(10, 50), pady=5)

class EtherealApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- 窗口基础设置 ---
        self.title("Project Ethereal - Terminal V2.0")
        self.geometry("1000x700")
        
        # 核心变量
        self.bot = None 
        self.is_ready = False

        # --- 布局配置 ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # === 左侧边栏 ===
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.sidebar.grid_rowconfigure(4, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar, text="ETHEREAL", font=("Segoe UI", 24, "bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        self.status_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.status_frame.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        
        self.brain_status = ctk.CTkLabel(self.status_frame, text="● Brain: Init...", text_color="gray", anchor="w")
        self.brain_status.pack(fill="x", pady=2)
        
        self.mouth_status = ctk.CTkLabel(self.status_frame, text="● Mouth: Init...", text_color="gray", anchor="w")
        self.mouth_status.pack(fill="x", pady=2)
        
        self.activity_label = ctk.CTkLabel(self.sidebar, text="[BOOTING]", font=("Consolas", 14, "bold"), text_color="#facc15")
        self.activity_label.grid(row=3, column=0, padx=20, pady=30)

        self.quit_btn = ctk.CTkButton(self.sidebar, text="Terminate", fg_color="#ef4444", hover_color="#dc2626", command=self.on_close)
        self.quit_btn.grid(row=5, column=0, padx=20, pady=20)

        # === 右侧聊天区 ===
        self.chat_area = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.chat_area.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.chat_area.grid_columnconfigure(0, weight=1)

        self.input_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.input_frame.grid(row=1, column=1, sticky="ew", padx=20, pady=(0, 20))
        self.input_frame.grid_columnconfigure(0, weight=1)

        self.entry = ctk.CTkEntry(self.input_frame, placeholder_text="System initializing...", height=50, font=("Microsoft YaHei UI", 14))
        self.entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.entry.bind("<Return>", self.send_message_event)
        self.entry.configure(state="disabled") # 初始化完成前禁止输入

        self.send_btn = ctk.CTkButton(self.input_frame, text="SEND", width=100, height=50, command=self.send_message_event)
        self.send_btn.grid(row=0, column=1)
        self.send_btn.configure(state="disabled")

        # --- 🚀 关键修改：异步启动核心 ---
        # 窗口先弹出来，然后再去加载 AI
        self.after(100, self.start_async_loading)

    def start_async_loading(self):
        """在后台线程加载 EtherealBot，防止卡住界面"""
        threading.Thread(target=self._load_bot_core, daemon=True).start()

    def _load_bot_core(self):
        self.add_message("System", "正在加载神经网络内核 (RTX 5080)...", False)
        
        # 这里会执行耗时的冷启动
        self.bot = EtherealBot()
        self.is_ready = True
        
        # 加载完成后更新 UI
        self.brain_status.configure(text="● Brain: Online", text_color="#4ade80")
        self.update_mouth_status()
        self.activity_label.configure(text="[IDLE]", text_color="#60a5fa")
        self.entry.configure(state="normal", placeholder_text="Send a message...")
        self.send_btn.configure(state="normal")
        
        self.add_message("Ethereal", "神经链路已连接。等待指令。", False)

    def update_mouth_status(self):
        if self.bot and self.bot.voice_enabled:
            self.mouth_status.configure(text="● Mouth: Online", text_color="#4ade80")
        else:
            self.mouth_status.configure(text="○ Mouth: Offline", text_color="#facc15")

    def add_message(self, sender, text, is_user=True):
        bubble = ChatBubble(self.chat_area, text=text, is_user=is_user)
        bubble.pack(fill="x", pady=5)
        self.chat_area._parent_canvas.yview_moveto(1.0)

    def send_message_event(self, event=None):
        if not self.is_ready: return
        text = self.entry.get().strip()
        if not text: return
        
        self.entry.delete(0, "end")
        self.add_message("You", text, is_user=True)
        self.entry.configure(state="disabled")
        
        threading.Thread(target=self.process_ai_response, args=(text,), daemon=True).start()

    def process_ai_response(self, user_text):
        self.update_activity("[THINKING...]", "#c084fc")
        reply = self.bot.think(user_text)
        
        if reply:
            self.after(0, self.add_message, "Ethereal", reply, False)
            self.update_activity("[SPEAKING...]", "#4ade80")
            self.bot.speak(reply)
        else:
            self.after(0, self.add_message, "System", "[Error] Link lost.", False)

        self.update_activity("[IDLE]", "#60a5fa")
        self.after(0, lambda: self.entry.configure(state="normal"))
        self.after(0, lambda: self.entry.focus_set())

    def update_activity(self, text, color):
        self.after(0, lambda: self.activity_label.configure(text=text, text_color=color))

    def on_close(self):
        if self.bot:
            self.bot.terminate()
        self.destroy()
        # 强制结束所有残留线程
        import os
        os._exit(0)

if __name__ == "__main__":
    app = EtherealApp()
    app.mainloop()