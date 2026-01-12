import requests
import time
import json
from rich.panel import Panel
import config
# [新增] 引入独立的语音引擎
from tts_engine import TTSEngine

class EtherealBot:
    """
    Project Ethereal 核心智能体 (Agent Core)
    负责认知推理，并调度 TTS 引擎进行表达。
    """
    def __init__(self):
        # 0. 启动自检
        self._system_check()

        # 1. 加载人格配置 (从 JSON)
        self.character_config = self._load_character_config()
        
        # 2. 初始化记忆
        self.history = [
            {
                "role": "system",
                "content": self.character_config.get("system_prompt", "You are a helpful AI.")
            }
        ]

        # 3. [重构] 初始化语音引擎 (Mouth)
        # 将配置中的 voice_settings 传给引擎
        self.tts = TTSEngine(self.character_config.get("voice_settings", {}))

        # 4. 自动执行冷启动预热 (Brain)
        self.is_cold_start = True
        self._warmup_neural_engine()

    # --- 兼容性属性 ---
    # 为了让 GUI (gui.py) 依然能通过 bot.voice_enabled 读取状态
    @property
    def voice_enabled(self):
        return self.tts.enabled
    
    @voice_enabled.setter
    def voice_enabled(self, value):
        self.tts.enabled = value
    # ------------------

    def _system_check(self):
        """系统环境检查"""
        print("--- 执行启动前安全审计 (Security Audit) ---")
        config.security_audit(config.OLLAMA_URL, "Brain (Ollama)")
        config.security_audit(config.TTS_API_URL, "Mouth (GPT-SoVITS)")
        print("[Security] 环境安全。")
        print("------------------------------------------")

    def _load_character_config(self):
        """加载 JSON 配置文件"""
        try:
            with open(config.CHARACTER_CONFIG_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                config.console.print(f"[green]✔ 人格数据已加载: {data.get('name', 'Unknown')}[/green]")
                return data
        except FileNotFoundError:
            config.console.print(f"[red]❌ 找不到配置文件: {config.CHARACTER_CONFIG_PATH}[/red]")
            return {"system_prompt": "You are Ethereal."}

    def _warmup_neural_engine(self):
        """
        主动预热：强制加载模型到显存
        """
        config.console.print("\n[bold magenta]>>> 系统正在执行冷启动 (Cold Start)...[/bold magenta]")
        config.console.print("[dim]正在将神经网络完整加载到本地计算核心显存中，请稍候...[/dim]")

        with config.console.status("[bold magenta]正在唤醒神经网络...[/bold magenta]", spinner="dots"):
            try:
                payload = {
                    "model": config.TARGET_MODEL,
                    "messages": [{"role": "system", "content": "init"}],
                    "stream": False 
                }
                requests.post(config.OLLAMA_URL, json=payload, timeout=60)
                
                self.is_cold_start = False
                config.console.print("[bold green]✔ 神经网络已激活。系统就绪。[/bold green]")
                
            except Exception as e:
                config.console.print(f"[red]⚠ 冷启动预热请求失败: {e}[/red]")
                config.console.print("[dim]系统仍将尝试运行，但第一次对话可能会变慢。[/dim]")

    def think(self, user_input):
        """执行认知推理"""
        self.history.append({"role": "user", "content": user_input})
        
        with config.console.status("[bold cyan]Thinking...[/bold cyan]", spinner="dots"):
            try:
                payload = {
                    "model": config.TARGET_MODEL,
                    "messages": self.history,
                    "stream": False 
                }
                
                start_time = time.time()
                response = requests.post(config.OLLAMA_URL, json=payload)
                end_time = time.time()
                
                if response.status_code == 200:
                    response_json = response.json()
                    ai_text = response_json["message"]["content"]
                    self.history.append({"role": "assistant", "content": ai_text})
                    
                    duration = end_time - start_time
                    config.console.print(f"\n[bold cyan]Ethereal ({duration:.2f}s):[/bold cyan] {ai_text}")
                    return ai_text
                else:
                    config.console.print(f"[red]Ollama Error: {response.text}[/red]")
                    return None
                
            except Exception as e:
                config.console.print(f"[red]Brain Connection Failed:[/red] {e}")
                return None

    def speak(self, text):
        """委托给 TTS 引擎表达"""
        self.tts.speak(text)

    def terminate(self):
        config.console.print("\n[yellow]正在切断神经连接并释放本地计算资源...[/yellow]")
        try:
            payload = {
                "model": config.TARGET_MODEL,
                "keep_alive": 0 
            }
            requests.post(config.OLLAMA_URL, json=payload, timeout=2.0)
            config.console.print("[green]✔ 模型已从显存卸载。系统休眠。[/green]")
        except Exception:
            pass