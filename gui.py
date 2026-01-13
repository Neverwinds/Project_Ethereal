import customtkinter as ctk
import threading
import time
import json
import os
from PIL import Image
import config
from agent import EtherealBot

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
            self, text=text, fg_color=bubble_color, text_color=text_color,
            corner_radius=15, wraplength=400, justify="left",
            font=("Microsoft YaHei UI", 14), padx=15, pady=10
        )
        if is_user:
            self.bubble.grid(row=0, column=1, sticky="e", padx=(20, 10), pady=5)
        else:
            self.bubble.grid(row=0, column=0, sticky="w", padx=(10, 20), pady=5)

class EtherealApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Project Ethereal - Terminal V4.0 (Dashboard)")
        self.geometry("1400x900") # 加宽以容纳三栏
        self.bot = None 
        self.is_ready = False

        # --- 主布局：左侧边栏 + 右侧内容区 ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_content_area()

        # 默认显示 Chat 界面
        self.show_chat_view()

        # 启动异步加载
        self.after(100, self.start_async_loading)

    def _build_sidebar(self):
        """构建左侧常驻栏：Logo + Metadata + 导航"""
        self.sidebar = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(4, weight=1) # 撑开中间空间

        # 1. Logo
        ctk.CTkLabel(self.sidebar, text="ETHEREAL", font=("Segoe UI", 24, "bold")).grid(row=0, column=0, padx=20, pady=(30, 20))
        
        # 2. 状态卡片 (Status Card)
        self.status_card = ctk.CTkFrame(self.sidebar, fg_color="#18181b", corner_radius=10)
        self.status_card.grid(row=1, column=0, padx=15, pady=10, sticky="ew")
        
        self.brain_status = ctk.CTkLabel(self.status_card, text="● Brain: Init...", text_color="gray", font=("Consolas", 12), anchor="w")
        self.brain_status.pack(fill="x", padx=15, pady=(10, 5))
        self.mouth_status = ctk.CTkLabel(self.status_card, text="● Mouth: Init...", text_color="gray", font=("Consolas", 12), anchor="w")
        self.mouth_status.pack(fill="x", padx=15, pady=(0, 10))

        # 3. 实时元数据 (Live Metadata) - 常驻显示
        self.meta_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.meta_frame.grid(row=2, column=0, padx=15, pady=10, sticky="ew")
        
        ctk.CTkLabel(self.meta_frame, text="LIVE METRICS", font=("Consolas", 10, "bold"), text_color="#52525b", anchor="w").pack(fill="x")
        
        # Emotion
        self.emotion_label = ctk.CTkLabel(self.meta_frame, text="[NEUTRAL]", font=("Segoe UI", 20, "bold"), text_color="#a1a1aa")
        self.emotion_label.pack(pady=(10, 5))
        ctk.CTkLabel(self.meta_frame, text="CURRENT EMOTION", font=("Consolas", 10), text_color="gray").pack()
        
        ctk.CTkFrame(self.meta_frame, height=1, fg_color="#27272a").pack(fill="x", pady=15)
        
        # Latency Grid
        l_grid = ctk.CTkFrame(self.meta_frame, fg_color="transparent")
        l_grid.pack(fill="x")
        l_grid.columnconfigure(0, weight=1); l_grid.columnconfigure(1, weight=1)
        
        self.perf_brain_label = ctk.CTkLabel(l_grid, text="0.00s", font=("Consolas", 18, "bold"), text_color="#a1a1aa")
        self.perf_brain_label.grid(row=0, column=0)
        ctk.CTkLabel(l_grid, text="BRAIN (s)", font=("Consolas", 10), text_color="gray").grid(row=1, column=0)
        
        self.perf_mouth_label = ctk.CTkLabel(l_grid, text="0.00s", font=("Consolas", 18, "bold"), text_color="#a1a1aa")
        self.perf_mouth_label.grid(row=0, column=1)
        ctk.CTkLabel(l_grid, text="TTS (s)", font=("Consolas", 10), text_color="gray").grid(row=1, column=1)

        # 4. 底部导航与控制 (Navigation)
        self.nav_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.nav_frame.grid(row=5, column=0, padx=15, pady=20, sticky="ew")
        
        self.activity_label = ctk.CTkLabel(self.nav_frame, text="[BOOTING]", font=("Consolas", 14, "bold"), text_color="#facc15")
        self.activity_label.pack(pady=(0, 20))
        
        # 页面切换按钮
        self.btn_chat = ctk.CTkButton(self.nav_frame, text="CHAT TERMINAL", fg_color="#2563eb", hover_color="#1d4ed8", height=45, font=("Segoe UI", 12, "bold"), command=self.show_chat_view)
        self.btn_chat.pack(fill="x", pady=5)
        
        self.btn_conf = ctk.CTkButton(self.nav_frame, text="SETTINGS / CONFIG", fg_color="#3f3f46", hover_color="#27272a", height=45, font=("Segoe UI", 12, "bold"), command=self.show_settings_view)
        self.btn_conf.pack(fill="x", pady=5)
        
        ctk.CTkFrame(self.nav_frame, height=1, fg_color="#27272a").pack(fill="x", pady=15)
        
        self.quit_btn = ctk.CTkButton(self.nav_frame, text="TERMINATE", fg_color="#ef4444", hover_color="#dc2626", command=self.on_close)
        self.quit_btn.pack(fill="x")

    def _build_content_area(self):
        """构建右侧内容容器"""
        self.content_container = ctk.CTkFrame(self, fg_color="transparent")
        self.content_container.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.content_container.grid_rowconfigure(0, weight=1)
        self.content_container.grid_columnconfigure(0, weight=1) # Chat Area
        # Settings View 将会覆盖这里，或者 Chat View 将会分割这里

        # --- View 1: Chat View (Split Layout) ---
        self.view_chat = ctk.CTkFrame(self.content_container, fg_color="transparent")
        self.view_chat.grid_rowconfigure(0, weight=1)
        self.view_chat.grid_columnconfigure(0, weight=2) # Chat 占 2/3
        self.view_chat.grid_columnconfigure(1, weight=1) # Debug 占 1/3
        
        # Left: Chat Window
        self.chat_frame = ctk.CTkFrame(self.view_chat, fg_color="transparent")
        self.chat_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 20))
        self.chat_frame.grid_rowconfigure(0, weight=1)
        self.chat_frame.grid_columnconfigure(0, weight=1)
        
        self.chat_area = ctk.CTkScrollableFrame(self.chat_frame, fg_color="#101012") # 更深一点的背景
        self.chat_area.grid(row=0, column=0, sticky="nsew")
        self.chat_area.grid_columnconfigure(0, weight=1)
        
        self.input_frame = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        self.input_frame.grid(row=1, column=0, sticky="ew", pady=(15, 0))
        self.input_frame.grid_columnconfigure(0, weight=1)
        
        self.entry = ctk.CTkEntry(self.input_frame, placeholder_text="System initializing...", height=50, font=("Microsoft YaHei UI", 14))
        self.entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.entry.bind("<Return>", self.send_message_event)
        self.entry.configure(state="disabled") 
        
        self.send_btn = ctk.CTkButton(self.input_frame, text="SEND", width=100, height=50, command=self.send_message_event)
        self.send_btn.grid(row=0, column=1)
        self.send_btn.configure(state="disabled")

        # Right: Debug Panel (Permanent)
        self.debug_frame = ctk.CTkFrame(self.view_chat, fg_color="#18181b", corner_radius=10)
        self.debug_frame.grid(row=0, column=1, sticky="nsew")
        self.debug_frame.grid_rowconfigure(1, weight=1)
        self.debug_frame.grid_rowconfigure(3, weight=1)
        self.debug_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(self.debug_frame, text="REQUEST PAYLOAD", font=("Consolas", 11, "bold"), text_color="#52525b", anchor="w").grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 5))
        self.payload_box = ctk.CTkTextbox(self.debug_frame, font=("Consolas", 11), text_color="#a1a1aa", fg_color="#27272a", wrap="none")
        self.payload_box.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        self.payload_box.configure(state="disabled")
        
        ctk.CTkLabel(self.debug_frame, text="RAW RESPONSE STREAM", font=("Consolas", 11, "bold"), text_color="#52525b", anchor="w").grid(row=2, column=0, sticky="ew", padx=15, pady=(5, 5))
        self.log_box = ctk.CTkTextbox(self.debug_frame, font=("Consolas", 11), text_color="#a1a1aa", fg_color="#27272a", wrap="word")
        self.log_box.grid(row=3, column=0, sticky="nsew", padx=15, pady=(0, 15))
        self.log_box.configure(state="disabled")

        # --- View 2: Settings View (Full Width) ---
        self.view_settings = ctk.CTkFrame(self.content_container, fg_color="transparent")
        self.view_settings.grid_rowconfigure(0, weight=1)
        self.view_settings.grid_columnconfigure(0, weight=1)
        
        # 复用之前的 Tabview 逻辑，但现在它是全屏的
        self.settings_tabs = ctk.CTkTabview(self.view_settings, fg_color="transparent")
        self.settings_tabs.grid(row=0, column=0, sticky="nsew")
        
        self.tab_persona = self.settings_tabs.add("PERSONA")
        self.tab_voice = self.settings_tabs.add("VOICE")
        self.tab_system = self.settings_tabs.add("SYSTEM")
        
        self._build_persona_ui(self.tab_persona)
        self._build_voice_ui(self.tab_voice)
        self._build_system_ui(self.tab_system)
        
        self.save_btn = ctk.CTkButton(self.view_settings, text="SAVE & RELOAD CORE", fg_color="#10b981", hover_color="#059669", height=50, font=("Segoe UI", 13, "bold"), command=self.save_settings)
        self.save_btn.grid(row=1, column=0, sticky="ew", pady=(15, 0))

    # --- 视图切换逻辑 ---
    def show_chat_view(self):
        self.view_settings.grid_forget()
        self.view_chat.grid(row=0, column=0, sticky="nsew")
        self.btn_chat.configure(fg_color="#2563eb") # Active Blue
        self.btn_conf.configure(fg_color="#3f3f46") # Inactive Gray

    def show_settings_view(self):
        self.view_chat.grid_forget()
        self.view_settings.grid(row=0, column=0, sticky="nsew")
        self.btn_chat.configure(fg_color="#3f3f46")
        self.btn_conf.configure(fg_color="#2563eb")

    # --- UI 构建辅助函数 (保持之前的逻辑) ---
    def _add_section_header(self, parent, text, row):
        label = ctk.CTkLabel(parent, text=text, font=("Consolas", 14, "bold"), text_color="#60a5fa")
        label.grid(row=row, column=0, sticky="w", padx=10, pady=(20, 5))

    def _add_description(self, parent, text, row):
        label = ctk.CTkLabel(parent, text=text, font=("Microsoft YaHei UI", 11), text_color="gray", wraplength=600, justify="left")
        label.grid(row=row, column=0, sticky="w", padx=20, pady=(0, 10))

    def _add_input_field(self, parent, label_text, row, height=30):
        ctk.CTkLabel(parent, text=label_text, font=("Consolas", 11), text_color="gray").grid(row=row, column=0, sticky="w", padx=20, pady=(5, 0))
        if height > 30:
            entry = ctk.CTkTextbox(parent, height=height, font=("Consolas", 12), fg_color="#18181b")
        else:
            entry = ctk.CTkEntry(parent, font=("Consolas", 12), fg_color="#18181b")
        entry.grid(row=row+1, column=0, sticky="ew", padx=20, pady=(0, 10))
        return entry

    # --- Settings Pages UI ---
    def _build_persona_ui(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)
        
        r = 0
        self._add_section_header(scroll, "CORE PERSONA", r); r+=1
        self._add_description(scroll, "定义 AI 的核心身份、性格特征和说话语调。", r); r+=1
        self.entry_identity = self._add_input_field(scroll, "Identity", r, 60); r+=2
        self.entry_personality = self._add_input_field(scroll, "Personality", r, 60); r+=2
        self.entry_tone = self._add_input_field(scroll, "Tone & Style", r); r+=2
        
        self._add_section_header(scroll, "KNOWLEDGE BASE", r); r+=1
        self.entry_origin = self._add_input_field(scroll, "Origin", r); r+=2
        self.entry_worldview = self._add_input_field(scroll, "World View", r, 60); r+=2
        
        lf = ctk.CTkFrame(scroll, fg_color="transparent")
        lf.grid(row=r, column=0, sticky="ew", padx=20, pady=5); r+=1
        lf.grid_columnconfigure(0, weight=1); lf.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(lf, text="Likes", font=("Consolas", 11), text_color="gray").grid(row=0, column=0, sticky="w")
        self.entry_likes = ctk.CTkEntry(lf, fg_color="#18181b"); self.entry_likes.grid(row=1, column=0, sticky="ew", padx=(0,10))
        ctk.CTkLabel(lf, text="Dislikes", font=("Consolas", 11), text_color="gray").grid(row=0, column=1, sticky="w")
        self.entry_dislikes = ctk.CTkEntry(lf, fg_color="#18181b"); self.entry_dislikes.grid(row=1, column=1, sticky="ew")
        
        self._add_section_header(scroll, "INSTRUCTIONS", r); r+=1
        self.entry_format = self._add_input_field(scroll, "Format Rules", r, 60); r+=2
        self.entry_examples = self._add_input_field(scroll, "Examples", r, 150); r+=2

    def _build_voice_ui(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        r = 0
        self._add_section_header(parent, "GPT-SoVITS", r); r+=1
        self.entry_ref_audio = self._add_input_field(parent, "Ref Audio", r); r+=2
        self.entry_ref_text = self._add_input_field(parent, "Ref Content", r); r+=2

    def _build_system_ui(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        r = 0
        self._add_section_header(parent, "BRAIN SELECTION", r); r+=1
        ctk.CTkLabel(parent, text="Brain Source:", font=("Consolas", 11), text_color="gray").grid(row=r, column=0, sticky="w", padx=20, pady=(5,0))
        self.combo_brain = ctk.CTkComboBox(parent, values=["ollama", "deepseek"])
        self.combo_brain.grid(row=r+1, column=0, sticky="ew", padx=20, pady=(0,15)); r+=2
        
        self._add_section_header(parent, "LOCAL CONFIG", r); r+=1
        self.entry_ollama_model = self._add_input_field(parent, "Model Name", r); r+=2
        
        self._add_section_header(parent, "CLOUD CONFIG", r); r+=1
        self.entry_deepseek_key = self._add_input_field(parent, "DeepSeek API Key", r); r+=2

    # --- Loading & Saving ---
    def load_settings_to_ui(self):
        try:
            with open(config.CHARACTER_CONFIG_PATH, 'r', encoding='utf-8') as f: data = json.load(f)
            p = data.get("persona", {})
            self._set_text(self.entry_identity, p.get("identity", ""))
            self._set_text(self.entry_personality, p.get("personality", ""))
            self._set_text(self.entry_tone, p.get("tone_style", ""))
            
            k = data.get("knowledge_base", {})
            self._set_text(self.entry_origin, k.get("origin", ""))
            self._set_text(self.entry_likes, k.get("likes", ""))
            self._set_text(self.entry_dislikes, k.get("dislikes", ""))
            self._set_text(self.entry_worldview, k.get("world_view", ""))
            
            i = data.get("instructions", {})
            self._set_text(self.entry_format, i.get("format_rules", ""))
            self._set_text(self.entry_examples, i.get("examples", ""))
            
            v = data.get("voice_settings", {})
            self._set_text(self.entry_ref_audio, v.get("ref_audio", ""))
            self._set_text(self.entry_ref_text, v.get("prompt_text", ""))
            
            s = data.get("system_settings", {})
            self.combo_brain.set(s.get("brain_type", "ollama"))
            self._set_text(self.entry_ollama_model, s.get("ollama_model", config.OLLAMA_MODEL))
            
            if os.path.exists(config.SECRETS_CONFIG_PATH):
                with open(config.SECRETS_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    sec = json.load(f)
                    self._set_text(self.entry_deepseek_key, sec.get("deepseek_key", ""))
        except Exception as e: print(f"Load error: {e}")

    def save_settings(self):
        try:
            with open(config.CHARACTER_CONFIG_PATH, 'r', encoding='utf-8') as f: data = json.load(f)
            
            data["persona"]["identity"] = self._get_text(self.entry_identity)
            data["persona"]["personality"] = self._get_text(self.entry_personality)
            data["persona"]["tone_style"] = self._get_text(self.entry_tone)
            
            data["knowledge_base"]["origin"] = self._get_text(self.entry_origin)
            data["knowledge_base"]["likes"] = self._get_text(self.entry_likes)
            data["knowledge_base"]["dislikes"] = self._get_text(self.entry_dislikes)
            data["knowledge_base"]["world_view"] = self._get_text(self.entry_worldview)
            
            data["instructions"]["format_rules"] = self._get_text(self.entry_format)
            data["instructions"]["examples"] = self._get_text(self.entry_examples)
            
            data["voice_settings"]["ref_audio"] = self._get_text(self.entry_ref_audio)
            data["voice_settings"]["prompt_text"] = self._get_text(self.entry_ref_text)
            
            if "system_settings" not in data: data["system_settings"] = {}
            data["system_settings"]["brain_type"] = self.combo_brain.get()
            data["system_settings"]["ollama_model"] = self._get_text(self.entry_ollama_model)
            
            with open(config.CHARACTER_CONFIG_PATH, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)
            
            secrets = {"deepseek_key": self._get_text(self.entry_deepseek_key)}
            with open(config.SECRETS_CONFIG_PATH, 'w', encoding='utf-8') as f: json.dump(secrets, f, indent=4, ensure_ascii=False)
            
            if self.bot:
                self.bot = EtherealBot()
                bn = self.bot.brain_type.title()
                self.brain_status.configure(text=f"● Brain: {bn}", text_color="#4ade80")
                self.append_log(f"[System] Reloaded. Engine: {bn}")
        except Exception as e: print(f"Save error: {e}")

    # --- Helpers ---
    def _set_text(self, w, t):
        if isinstance(w, ctk.CTkEntry): w.delete(0, "end"); w.insert(0, t)
        else: w.delete("1.0", "end"); w.insert("1.0", t)
    def _get_text(self, w): return w.get() if isinstance(w, ctk.CTkEntry) else w.get("1.0", "end-1c")

    # --- Core Logic ---
    def start_async_loading(self): threading.Thread(target=self._load_bot_core, daemon=True).start()
    def _load_bot_core(self):
        self.bot = EtherealBot()
        self.is_ready = True
        self.after(0, self.load_settings_to_ui)
        bn = self.bot.brain_type.title()
        self.brain_status.configure(text=f"● Brain: {bn}", text_color="#4ade80")
        self.update_mouth_status()
        self.activity_label.configure(text="[IDLE]", text_color="#60a5fa")
        self.emotion_label.configure(text="[NEUTRAL]")
        self.entry.configure(state="normal", placeholder_text="Send a message...")
        self.send_btn.configure(state="normal")
        self.add_message("Ethereal", "Link Established.", False)

    def update_mouth_status(self):
        if self.bot and self.bot.voice_enabled: self.mouth_status.configure(text="● Mouth: Online", text_color="#4ade80")
        else: self.mouth_status.configure(text="○ Mouth: Offline", text_color="#facc15")

    def update_debug_panels(self, payload, b_time, m_time):
        self.payload_box.configure(state="normal")
        self.payload_box.delete("1.0", "end")
        self.payload_box.insert("1.0", json.dumps(payload, indent=2, ensure_ascii=False))
        self.payload_box.configure(state="disabled")
        
        # [修改] 移除这里的 log_box 更新逻辑，避免重复
        
        self.perf_brain_label.configure(text=f"{b_time:.2f}s", text_color="#ef4444" if b_time>3 else "#a1a1aa")
        self.perf_mouth_label.configure(text=f"{m_time:.2f}s")

    def update_emotion_display(self):
        emo = self.bot.current_emotion.upper()
        self.emotion_label.configure(text=f"[{emo}]")
        colors = {"NEUTRAL": "#a1a1aa", "HAPPY": "#4ade80", "ANNOYED": "#facc15", "ANGRY": "#ef4444"}
        self.emotion_label.configure(text_color=colors.get(emo, "#ffffff"))

    def add_message(self, sender, text, is_user=True):
        bubble = ChatBubble(self.chat_area, text=text, is_user=is_user)
        bubble.pack(fill="x", pady=5)
        self.update_idletasks()
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
        self.after(0, lambda: self.activity_label.configure(text="[THINKING]", text_color="#c084fc"))
        data = self.bot.think(user_text)
        if data:
            self.after(0, self.add_message, "Ethereal", data["text"], False)
            self.after(0, self.update_emotion_display)
            
            # [新增] 显式调用一次 append_raw_log
            self.after(0, self.append_raw_log, data["raw"])
            
            # 更新面板，不再传入 raw log
            self.after(0, self.update_debug_panels, data.get("payload"), data["duration"], 0)
            
            self.after(0, lambda: self.activity_label.configure(text="[SPEAKING]", text_color="#4ade80"))
            m_time = self.bot.speak(data["text"])
            
            # 再次更新面板 (仅更新时间)
            self.after(0, self.update_debug_panels, data.get("payload"), data["duration"], m_time)
        else:
            self.after(0, self.add_message, "System", "Link Lost.", False)
        
        self.after(0, lambda: self.activity_label.configure(text="[IDLE]", text_color="#60a5fa"))
        self.after(0, lambda: self.entry.configure(state="normal"))
        self.after(0, lambda: self.entry.focus_set())

    def on_close(self):
        if self.bot: self.bot.terminate()
        self.destroy()
        import os; os._exit(0)

    def append_log(self, text): 
        # Helper for system logs
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[SYS] {text}\n")
        self.log_box.configure(state="disabled")

    def append_raw_log(self, text):
        # Helper for raw LLM response logs
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"> {text}\n\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

if __name__ == "__main__":
    app = EtherealApp()
    app.mainloop()