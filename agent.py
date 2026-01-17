import requests
import time
import json
import re
import os
from openai import OpenAI
from rich.panel import Panel
import config
from tts_engine import TTSEngine
from face_engine import FaceEngine

class EtherealBot:
    """
    Project Ethereal 核心智能体 (Agent Core) - V4.2 全感官版
    """
    def __init__(self):
        # 1. 配置加载
        self.character_config = self._load_json(config.CHARACTER_CONFIG_PATH)
        self.secrets_config = self._load_json(config.SECRETS_CONFIG_PATH)
        
        sys_cfg = self.character_config.get("system_settings", {})
        self.brain_type = sys_cfg.get("brain_type", config.DEFAULT_BRAIN)
        self.deepseek_key = self.secrets_config.get("deepseek_key", "")
        self.ollama_model = sys_cfg.get("ollama_model", config.OLLAMA_MODEL)

        self.system_prompt_text = self._construct_system_prompt()
        self.history = [] 
        self.ds_client = None

        # 2. 启动自检
        self._system_check_pre()
        
        # 3. 初始化器官
        self.face = FaceEngine() # 先初始化脸，因为嘴巴需要用到脸
        
        # [关键修改] 初始化 TTS 时传入口型回调函数
        # 这样 tts_engine 算出的音量就会直接变成 face.set_mouth_open 的参数
        self.tts = TTSEngine(
            self.character_config.get("voice_settings", {}),
            lip_sync_callback=self.face.set_mouth_open
        )
        
        # 4. 初始化大脑
        self._init_brain()

        self.last_stats = {"brain_time": 0.0, "mouth_time": 0.0}
        self.current_emotion = "neutral"

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
                self.ds_client = OpenAI(api_key=self.deepseek_key, base_url=config.DEEPSEEK_BASE_URL)
                self.history = [{"role": "system", "content": self.system_prompt_text}]
                self._unload_local_model()
                config.console.print(f"[green]✔ Brain: DeepSeek V3[/green]")
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
        text = re.sub(r'[\（\(\[].*?[\）\)\]]', '', text)
        return text.replace('*', '').strip()

    def think(self, user_input):
        if self.brain_type == "deepseek": return self._think_deepseek(user_input)
        return self._think_ollama(user_input)

    def _think_deepseek(self, user_input):
        if not self.ds_client: return None
        self.history.append({"role": "user", "content": user_input})
        st = time.time()
        try:
            resp = self.ds_client.chat.completions.create(model=config.DEEPSEEK_MODEL, messages=self.history)
            raw = resp.choices[0].message.content
            return self._process_response(raw, time.time()-st)
        except Exception as e:
            config.console.print(f"[red]DeepSeek Error: {e}[/red]")
            return None

    def _think_ollama(self, user_input):
        self.history.append({"role": "user", "content": user_input})
        st = time.time()
        try:
            resp = requests.post(config.OLLAMA_URL, json={"model": self.ollama_model, "messages": self.history, "stream": False})
            if resp.status_code == 200:
                raw = resp.json()["message"]["content"]
                return self._process_response(raw, time.time()-st)
        except: pass
        return None

    def _process_response(self, raw_text, duration):
        self.history.append({"role": "assistant", "content": raw_text})
        self.last_stats["brain_time"] = duration
        
        emotion, temp_text = self._extract_emotion(raw_text)
        clean_text = self._clean_text_for_display(temp_text)
        self.current_emotion = emotion
        
        # 驱动表情
        self.face.set_expression(emotion)
        
        config.console.print(f"\n[cyan]Ethereal ({emotion}):[/cyan] {clean_text}")
        return {"text": clean_text, "emotion": emotion, "duration": duration, "raw": raw_text, "payload": {}}

    def speak(self, text):
        st = time.time()
        # TTS 内部现在会自动调用 face.set_mouth_open
        self.tts.speak(text)
        self.last_stats["mouth_time"] = time.time() - st
        return self.last_stats["mouth_time"]

    def terminate(self):
        self._unload_local_model()