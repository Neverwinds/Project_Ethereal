import requests
import time
import json
import re
import os
import threading
# from openai import OpenAI (Removed to fix DLL issue)
from rich.panel import Panel
import config
from tts_engine import TTSEngine
from face_engine import FaceEngine
from stt_engine import STTEngine

class EtherealBot:
    """
    Project Ethereal 核心智能体 (Agent Core) - V4.3 音画同步版
    """
    def __init__(self, ui_callback=None, response_callback=None):
        self.character_config = self._load_json(config.CHARACTER_CONFIG_PATH)
        self.secrets_config = self._load_json(config.SECRETS_CONFIG_PATH)
        
        # UI Callback for chat display
        self.ui_callback = ui_callback
        self.response_callback = response_callback
        
        sys_cfg = self.character_config.get("system_settings", {})
        self.brain_type = sys_cfg.get("brain_type", config.DEFAULT_BRAIN)
        self.deepseek_key = self.secrets_config.get("deepseek_key", "")
        self.ollama_model = sys_cfg.get("ollama_model", config.OLLAMA_MODEL)
        self.temperature = sys_cfg.get("temperature", 0.7)
        self.top_p = sys_cfg.get("top_p", 0.9)

        self.system_prompt_text = self._construct_system_prompt()
        self.history = [] 
        # self.ds_client = None (Removed)

        self._system_check_pre()
        
        # 初始化脸
        self.face = FaceEngine()
        
        # [关键修改] 绑定 expression_callback 给 TTS
        self.tts = TTSEngine(
            self.character_config.get("voice_settings", {}),
            lip_sync_callback=self.face.set_mouth_open,
            expression_callback=self.face.set_expression 
        )
        
        # [新增] 初始化耳朵 (STT)
        self.ears = STTEngine(callback=self.on_hearing_input)
        
        self._init_brain()
        
        # Start listening
        self.ears.start_listening()

        self.last_stats = {"brain_time": 0.0, "mouth_time": 0.0}
        self.current_emotion = "neutral"

    def set_audio_input_enabled(self, enabled):
        """Enable or disable STT listening."""
        if hasattr(self, 'ears'):
            self.ears.set_listening_active(enabled)

    def on_hearing_input(self, perception_data):
        """
        Callback triggered when STT Engine hears something.
        Runs in a separate thread.
        """
        text = perception_data.get("text", "").strip()
        event = perception_data.get("event")
        emotion = perception_data.get("emotion", "NEUTRAL").upper()
        
        # 1. Noise Filter: Exit if no text and no special event (or just Speech)
        if not text and (not event or event == "Speech"):
            return

        # 2. Process in a new thread to prevent blocking the STT loop
        threading.Thread(target=self._process_hearing_thread, args=(text, emotion, event, perception_data)).start()

    def _process_hearing_thread(self, text, emotion, event, full_data):
        """
        Threaded processing of hearing input:
        1. Format prompt (Chinese Stage Direction Style)
        2. UI Display
        3. Think & Speak (Half-Duplex)
        """
        # [Locking] Prevent concurrent processing (Fix duplicate TTS issue)
        if not hasattr(self, '_processing_lock'):
            self._processing_lock = threading.Lock()
            
        if not self._processing_lock.acquire(blocking=False):
            config.console.print("[dim]Ignored concurrent input while processing...[/dim]")
            return

        try:
            # --- 1. Format Prompt (Chinese Stage Directions) ---
            prefix = ""
            
            # Event Map (English Tag -> Chinese Description)
            event_map = {
                "Laughter": "（用户发出了笑声）",
                "Sneeze": "（用户打了个喷嚏）",
                "Cough": "（用户咳嗽了几声）",
                "Cry": "（用户在哭泣）",
                "Breath": "（用户深吸了一口气）",
                "Applause": "（用户在鼓掌）"
            }
            
            # Emotion Map (English Tag -> Chinese Adjective)
            emotion_map = {
                "HAPPY": "开心",
                "SAD": "悲伤",
                "ANGRY": "愤怒",
                "ANNOYED": "烦躁",
                "FEARFUL": "害怕",
                "SURPRISED": "惊讶"
            }
            
            # Priority 1: Events (They imply context/emotion strongly)
            if event and event != "Speech":
                prefix = event_map.get(event, f"（用户发生了 {event} 事件）")
            
            # Priority 2: Emotion (Only if no event, to avoid redundancy)
            elif emotion not in ["NEUTRAL", "SPEECH"]:
                cn_emotion = emotion_map.get(emotion, emotion)
                prefix = f"（用户语气{cn_emotion}地说道）"
            
            # Final Assembly
            prompt_text = f"{prefix} {text}".strip()
            
            # Display text for UI (Clean, but indicates event)
            display_text = text
            if event and event != "Speech":
                display_text += f" *{event}*"
            elif not text:
                display_text = prefix # If only event, show the description
                 
            config.console.print(f"[bold magenta]Hearing Input:[/bold magenta] {prompt_text}")

            # --- 2. GUI Callback ---
            if self.ui_callback:
                # Update UI Display
                self.ui_callback(display_text, full_data, None) # None prompt = don't trigger AI in GUI
                
                # --- 3. Think & Speak (Here, under lock) ---
                if self.response_callback:
                    self.response_callback(None, "thinking_started")

                response = self.think(prompt_text)
                
                if response and response.get("text"):
                    if self.response_callback:
                        self.response_callback(response, "thinking_done")

                    m_time = self.speak(response["text"])
                    
                    if self.response_callback:
                        self.response_callback(response, "speaking_done", m_time)
                else:
                    if self.response_callback:
                        self.response_callback(None, "error")
                
            else:
                # Fallback for CLI mode
                response = self.think(prompt_text)
                
                if response and response.get("text"):
                    self.speak(response["text"])
                    
        finally:
            self._processing_lock.release()

    @property
    def voice_enabled(self): return self.tts.enabled
    @voice_enabled.setter
    def voice_enabled(self, value): self.tts.enabled = value

    def _system_check_pre(self):
        print("--- 执行启动前自检 ---")
        config.security_audit(config.TTS_API_URL, "Mouth (GPT-SoVITS)")
        if self.brain_type == "ollama":
            config.security_audit(config.OLLAMA_URL, "Brain (Ollama)")

    def _load_json(self, path):
        try:
            if not os.path.exists(path): return {}
            with open(path, 'r', encoding='utf-8') as f: return json.load(f)
        except: return {}

    def _construct_system_prompt(self):
        cfg = self.character_config
        persona = cfg.get("persona", {})
        kb = cfg.get("knowledge_base", {})
        instr = cfg.get("instructions", {})
        
        prompt = f"{persona.get('identity', '')}\n"
        prompt += f"\n[PERSONALITY]\n{persona.get('personality', '')}\n"
        if kb:
            prompt += "\n[KNOWLEDGE]\n" + "\n".join([f"- {k.title()}: {v}" for k,v in kb.items() if isinstance(v, str)])
        prompt += f"\n[INSTRUCTIONS]\n{instr.get('format_rules', '')}\n[EXAMPLES]\n{instr.get('examples', '')}\n"
        return prompt

    def _init_brain(self):
        if self.brain_type == "deepseek":
            if not self.deepseek_key: config.console.print("[red]❌ DeepSeek Key Missing[/red]")
            else:
                # Removed OpenAI client initialization to avoid DLL errors
                self.history = [{"role": "system", "content": self.system_prompt_text}]
                self._unload_local_model()
                config.console.print(f"[green]✔ Brain: DeepSeek V3 (Requests Mode)[/green]")
        else:
            self.history.append({"role": "system", "content": self.system_prompt_text})
            self.is_cold_start = True
            self._warmup_neural_engine()
            config.console.print(f"[green]✔ Brain: Local Ollama[/green]")

    def _warmup_neural_engine(self):
        config.console.print("[dim]预热本地神经网络...[/dim]")
        try:
            requests.post(config.OLLAMA_URL, json={"model": self.ollama_model, "messages": [{"role": "user", "content": "hi"}], "stream": False}, timeout=60)
            self.is_cold_start = False
        except: pass

    def _unload_local_model(self):
        try: requests.post(config.OLLAMA_URL, json={"model": self.ollama_model, "keep_alive": 0}, timeout=2)
        except: pass

    def _extract_emotion(self, text):
        match = re.match(r'^\[(\w+)\]\s*(.*)', text, re.DOTALL)
        if match: return match.group(1).lower(), match.group(2)
        return "neutral", text

    def _clean_text_for_display(self, text):
        # 移除 [] () 中的内容
        text = re.sub(r'[\（\(\[].*?[\）\)\]]', '', text)
        # 移除 *...* 中的动作描述
        text = re.sub(r'\*.*?\*', '', text)
        return text.strip()

    def think(self, user_input):
        # [新增] 在开始思考前，立即切换到 Thinking 表情
        self.face.set_expression("thinking")
        
        try:
            if self.brain_type == "deepseek": return self._think_deepseek(user_input)
            return self._think_ollama(user_input)
        except Exception as e:
            # 兜底：如果思考过程崩溃，重置表情
            self.face.set_expression("neutral")
            return None

    def _think_deepseek(self, user_input):
        if not self.deepseek_key: return None
        self.history.append({"role": "user", "content": user_input})
        st = time.time()
        try:
            # Use standard requests instead of OpenAI SDK
            headers = {
                "Authorization": f"Bearer {self.deepseek_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": config.DEEPSEEK_MODEL,
                "messages": self.history,
                "stream": False,
                "temperature": self.temperature,
                "top_p": self.top_p
            }
            resp = requests.post(
                f"{config.DEEPSEEK_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if resp.status_code == 200:
                data = resp.json()
                raw = data["choices"][0]["message"]["content"]
                return self._process_response(raw, time.time()-st, payload)
            else:
                config.console.print(f"[red]DeepSeek API Error: {resp.status_code} - {resp.text}[/red]")
                return None

        except Exception as e:
            config.console.print(f"[red]DeepSeek Error: {e}[/red]")
            return None

    def _think_ollama(self, user_input):
        self.history.append({"role": "user", "content": user_input})
        st = time.time()
        try:
            payload = {
                "model": self.ollama_model, 
                "messages": self.history, 
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "top_p": self.top_p
                }
            }
            resp = requests.post(config.OLLAMA_URL, json=payload)
            if resp.status_code == 200:
                raw = resp.json()["message"]["content"]
                return self._process_response(raw, time.time()-st, payload)
        except: pass
        return None

    def _process_response(self, raw_text, duration, payload=None):
        self.history.append({"role": "assistant", "content": raw_text})
        self.last_stats["brain_time"] = duration
        
        emotion, temp_text = self._extract_emotion(raw_text)
        clean_text = self._clean_text_for_display(temp_text)
        
        # [修改] 记录情感，但不在这里触发，而是交给 TTS
        self.current_emotion = emotion 
        
        config.console.print(f"\n[cyan]Ethereal ({emotion}):[/cyan] {clean_text}")
        return {"text": clean_text, "emotion": emotion, "duration": duration, "raw": raw_text, "payload": payload or {}}

    def speak(self, text):
        st = time.time()
        
        # [修改] 移除重复的 Thinking 表情设置 (已移动到 think)
        
        # [Half-Duplex] Disable listening while speaking to avoid echo loop
        if hasattr(self, 'ears'):
            self.ears.set_listening_active(False)
            
        try:
            # [修改] 传入当前情感
            self.tts.speak(text, self.current_emotion)
        finally:
            # [Half-Duplex] Re-enable listening after speaking
            # Add a small delay to avoid picking up the tail of the audio
            if hasattr(self, 'ears'):
                # Ideally, this should be done after the audio actually finishes playing.
                # Since tts.speak is blocking (due to sd.sleep), this is safe.
                # Adding a small buffer time just in case.
                time.sleep(0.5)
                self.ears.set_listening_active(True)

        self.last_stats["mouth_time"] = time.time() - st
        return self.last_stats["mouth_time"]

    def terminate(self):
        self._unload_local_model()