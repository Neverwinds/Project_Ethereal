import requests
import time
import json
import re
import os
from openai import OpenAI
from rich.panel import Panel
import config
from tts_engine import TTSEngine

class EtherealBot:
    """
    Project Ethereal 核心智能体 (Agent Core) - V3.4 安全与调试增强版
    """
    def __init__(self):
        # 1. 加载普通配置
        self.character_config = self._load_json(config.CHARACTER_CONFIG_PATH)
        # 2. 加载敏感配置 (API Key)
        self.secrets_config = self._load_json(config.SECRETS_CONFIG_PATH)
        
        sys_cfg = self.character_config.get("system_settings", {})
        self.brain_type = sys_cfg.get("brain_type", config.DEFAULT_BRAIN)
        # [安全] 从 secrets.json 读取 Key
        self.deepseek_key = self.secrets_config.get("deepseek_key", "")
        self.ollama_model = sys_cfg.get("ollama_model", config.OLLAMA_MODEL)

        self._system_check()
        
        self.system_prompt_text = self._construct_system_prompt()
        self.history = [] 
        self.ds_client = None

        # 初始化大脑
        if self.brain_type == "deepseek":
            self._init_deepseek()
            self._unload_local_model()
        elif self.brain_type == "ollama":
            self.history.append({"role": "system", "content": self.system_prompt_text})
            self.is_cold_start = True
            self._warmup_neural_engine()
        else:
            self.brain_type = "ollama"
            self.history.append({"role": "system", "content": self.system_prompt_text})
            self.is_cold_start = True
            self._warmup_neural_engine()

        self.tts = TTSEngine(self.character_config.get("voice_settings", {}))
        self.last_stats = {"brain_time": 0.0, "mouth_time": 0.0}
        self.current_emotion = "neutral"

    @property
    def voice_enabled(self):
        return self.tts.enabled
    
    @voice_enabled.setter
    def voice_enabled(self, value):
        self.tts.enabled = value

    def _system_check(self):
        print("--- 启动自检 ---")
        config.security_audit(config.TTS_API_URL, "Mouth (GPT-SoVITS)")
        if self.brain_type == "ollama":
            config.security_audit(config.OLLAMA_URL, "Brain (Ollama)")
            print(f"[System] 当前大脑: Local Ollama ({self.ollama_model})")
        else:
            print(f"[System] 当前大脑: Cloud {self.brain_type.title()}")
        print("----------------")

    def _load_json(self, path):
        """通用 JSON 读取"""
        try:
            if not os.path.exists(path): return {}
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def _construct_system_prompt(self):
        cfg = self.character_config
        persona = cfg.get("persona", {})
        kb = cfg.get("knowledge_base", {})
        instr = cfg.get("instructions", {})
        
        prompt = f"{persona.get('identity', '')}\n"
        prompt += f"\n[PERSONALITY]\n{persona.get('personality', '')}\n"
        
        if kb:
            prompt += "\n[KNOWLEDGE]\n"
            prompt += f"- Origin: {kb.get('origin', '')}\n"
            prompt += f"- Likes: {kb.get('likes', '')}\n"
            prompt += f"- Dislikes: {kb.get('dislikes', '')}\n"
            
        prompt += f"\n[INSTRUCTIONS]\n{instr.get('format_rules', '')}\n"
        prompt += f"\n[EXAMPLES]\n{instr.get('examples', '')}\n"
        
        return prompt

    def _unload_local_model(self):
        config.console.print("[yellow]检测到云端模式，正在清理本地显存占用...[/yellow]")
        try:
            payload = {"model": self.ollama_model, "keep_alive": 0}
            requests.post(config.OLLAMA_URL, json=payload, timeout=2.0)
            config.console.print("[green]✔ 本地显存已释放。[/green]")
        except Exception:
            pass

    def _init_deepseek(self):
        if not self.deepseek_key:
            config.console.print("[red]❌ DeepSeek API Key 未配置！请在设置中填写。[/red]")
            return
        
        try:
            self.ds_client = OpenAI(
                api_key=self.deepseek_key, 
                base_url=config.DEEPSEEK_BASE_URL
            )
            # DeepSeek 使用 messages 传递 system prompt
            self.history = [{"role": "system", "content": self.system_prompt_text}]
            config.console.print(f"[green]✔ DeepSeek V3 API 已连接[/green]")
        except Exception as e:
            config.console.print(f"[red]❌ DeepSeek 初始化失败: {e}[/red]")

    def _warmup_neural_engine(self):
        config.console.print("[dim]正在预热本地神经网络...[/dim]")
        try:
            payload = {
                "model": self.ollama_model,
                "messages": [{"role": "system", "content": "init"}],
                "stream": False 
            }
            requests.post(config.OLLAMA_URL, json=payload, timeout=60)
            self.is_cold_start = False
            config.console.print("[bold green]✔ 本地大脑已就绪。[/bold green]")
        except Exception as e:
            config.console.print(f"[red]⚠ 本地预热失败: {e}[/red]")

    def _extract_emotion(self, text):
        match = re.match(r'^\[(\w+)\]\s*(.*)', text, re.DOTALL)
        if match:
            return match.group(1).lower(), match.group(2)
        return "neutral", text

    def _clean_text_for_display(self, text):
        """
        [新增] 显示层文本清洗
        强力去除所有括号内容，避免 AI 的内心戏 (sigh) 出现在气泡里
        """
        if not text: return ""
        # 去除中文括号、英文括号、中括号及其内容
        text = re.sub(r'[\（\(\[].*?[\）\)\]]', '', text)
        # 去除 Markdown
        text = text.replace('*', '')
        return text.strip()

    def think(self, user_input):
        if self.brain_type == "deepseek":
            return self._think_with_deepseek(user_input)
        else:
            return self._think_with_ollama(user_input)

    def _think_with_deepseek(self, user_input):
        if not self.ds_client:
            return {"text": "[Error] DeepSeek Key missing.", "raw": "", "emotion": "neutral", "duration": 0, "payload": {}}

        self.history.append({"role": "user", "content": user_input})
        start_time = time.time()
        
        with config.console.status("[bold purple]DeepSeek Thinking...[/bold purple]", spinner="dots"):
            try:
                # 捕获请求负载用于 Debug
                debug_payload = {
                    "model": config.DEEPSEEK_MODEL,
                    "messages": self.history[-10:] # 只显示最近10条，防止debug刷屏
                }

                response = self.ds_client.chat.completions.create(
                    model=config.DEEPSEEK_MODEL,
                    messages=self.history,
                    stream=False
                )
                
                raw_text = response.choices[0].message.content
                duration = time.time() - start_time
                self.last_stats["brain_time"] = duration
                
                self.history.append({"role": "assistant", "content": raw_text})
                
                emotion, temp_text = self._extract_emotion(raw_text)
                clean_text = self._clean_text_for_display(temp_text) # 二次清洗
                
                self.current_emotion = emotion
                
                return {
                    "text": clean_text,
                    "emotion": emotion,
                    "duration": duration,
                    "raw": raw_text,
                    "payload": debug_payload # 返回给 GUI
                }
            except Exception as e:
                config.console.print(f"[red]DeepSeek API Error: {e}[/red]")
                return None

    def _think_with_ollama(self, user_input):
        self.history.append({"role": "user", "content": user_input})
        
        with config.console.status("[bold cyan]Ollama Thinking...[/bold cyan]", spinner="dots"):
            try:
                # 捕获请求负载
                payload = {"model": self.ollama_model, "messages": self.history, "stream": False}
                
                start_time = time.time()
                response = requests.post(config.OLLAMA_URL, json=payload)
                end_time = time.time()
                
                if response.status_code == 200:
                    raw_text = response.json()["message"]["content"]
                    duration = end_time - start_time
                    self.last_stats["brain_time"] = duration
                    
                    self.history.append({"role": "assistant", "content": raw_text})
                    emotion, temp_text = self._extract_emotion(raw_text)
                    clean_text = self._clean_text_for_display(temp_text)
                    self.current_emotion = emotion
                    
                    # 简化 payload 显示，截取部分历史
                    debug_payload = payload.copy()
                    debug_payload["messages"] = payload["messages"][-5:] 

                    return {
                        "text": clean_text,
                        "emotion": emotion,
                        "duration": duration,
                        "raw": raw_text,
                        "payload": debug_payload
                    }
                else:
                    return None
            except Exception as e:
                return None

    def speak(self, text):
        start_time = time.time()
        # TTS 引擎有自己的清洗逻辑，这里传入 text 或 clean_text 都可以，建议传 clean_text
        self.tts.speak(text)
        duration = time.time() - start_time
        self.last_stats["mouth_time"] = duration
        return duration

    def terminate(self):
        self._unload_local_model()