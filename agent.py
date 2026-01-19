import requests
import time
import json
import re
import os
# from openai import OpenAI (Removed to fix DLL issue)
from rich.panel import Panel
import config
from tts_engine import TTSEngine
from face_engine import FaceEngine

class EtherealBot:
    """
    Project Ethereal 核心智能体 (Agent Core) - V4.3 音画同步版
    """
    def __init__(self):
        self.character_config = self._load_json(config.CHARACTER_CONFIG_PATH)
        self.secrets_config = self._load_json(config.SECRETS_CONFIG_PATH)
        
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
        
        # [修改] 传入当前情感
        self.tts.speak(text, self.current_emotion)
        self.last_stats["mouth_time"] = time.time() - st
        return self.last_stats["mouth_time"]

    def terminate(self):
        self._unload_local_model()