import requests
import pygame
import io
import os
import time
import json
from rich.panel import Panel
import config 

class EtherealBot:
    """
    Project Ethereal 核心智能体 (Agent Core)
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

        # 3. 自动执行冷启动预热
        self.is_cold_start = True
        self._warmup_neural_engine()

    def _system_check(self):
        """系统环境检查"""
        print("--- 执行启动前安全审计 (Security Audit) ---")
        config.security_audit(config.OLLAMA_URL, "Brain (Ollama)")
        config.security_audit(config.TTS_API_URL, "Mouth (GPT-SoVITS)")
        print("[Security] 环境安全。")
        print("------------------------------------------")

        print("[DEBUG] 正在初始化音频驱动...") 
        try:
            pygame.mixer.init()
        except Exception as e:
            config.console.print(f"[yellow][System] Audio device not found: {e}. Sound disabled.[/yellow]")

        self.voice_enabled = False
        print("[DEBUG] 正在检测 GPT-SoVITS 服务状态...")
        self._check_voice_service()

    def _load_character_config(self):
        """加载 JSON 配置文件"""
        try:
            with open(config.CHARACTER_CONFIG_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                config.console.print(f"[green]✔ 人格数据已加载: {data.get('name', 'Unknown')}[/green]")
                return data
        except FileNotFoundError:
            config.console.print(f"[red]❌ 找不到配置文件: {config.CHARACTER_CONFIG_PATH}[/red]")
            # 返回默认值防止崩溃
            return {"system_prompt": "You are Ethereal."}

    def _check_voice_service(self):
        """探测 TTS 服务"""
        try:
            requests.get(config.TTS_API_URL, timeout=1.0)
            
            # 检查音频文件是否存在
            if not os.path.exists(config.REF_AUDIO_PATH):
                config.console.print(Panel(f"TTS 在线，但参考音频缺失:\n{config.REF_AUDIO_PATH}\n请将 wav 文件放入 assets 文件夹。", style="bold yellow"))
                self.voice_enabled = False
            else:
                self.voice_enabled = True
                config.console.print(Panel("● Brain: Linked\n● Mouth: Online", style="bold green", title="System Check"))

        except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout):
            self.voice_enabled = False
            config.console.print(Panel("● Brain: Linked\n○ Mouth: Offline (Text Mode)", style="bold yellow", title="System Check"))

    def _warmup_neural_engine(self):
        """
        主动预热：强制加载模型到显存
        """
        config.console.print("\n[bold magenta]>>> 系统正在执行冷启动 (Cold Start)...[/bold magenta]")
        config.console.print("[dim]正在将神经网络完整加载到 RTX 5080 显存中，请稍候...[/dim]")

        with config.console.status("[bold magenta]正在唤醒神经网络...[/bold magenta]", spinner="dots"):
            try:
                # 发送一个极简的 Dummy 请求来触发加载
                payload = {
                    "model": config.TARGET_MODEL,
                    "messages": [{"role": "system", "content": "init"}],
                    "stream": False 
                }
                # 发送请求 (设置较长超时)
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
        if not self.voice_enabled or not text:
            return
        
        # 从配置中读取 TTS 参数
        voice_cfg = self.character_config.get("voice_settings", {})

        with config.console.status("[bold blue]Synthesizing Voice...", spinner="bouncingBar"):
            try:
                # [关键修正] 适配 GPT-SoVITS API v2 的参数名称
                # v1: text_language, prompt_language, refer_wav_path
                # v2: text_lang, prompt_lang, ref_audio_path
                params = {
                    "text": text,
                    "text_lang": voice_cfg.get("target_lang", "zh"),    # 修正
                    "ref_audio_path": config.REF_AUDIO_PATH,            # 修正
                    "prompt_text": voice_cfg.get("prompt_text", ""),
                    "prompt_lang": voice_cfg.get("prompt_lang", "zh"),  # 修正
                }
                
                response = requests.get(config.TTS_API_URL, params=params, timeout=30)

                if response.status_code == 200:
                    audio_stream = io.BytesIO(response.content)
                    pygame.mixer.music.load(audio_stream)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy():
                        pygame.time.Clock().tick(10)
                else:
                    config.console.print(f"[red]TTS API Error ({response.status_code})[/red]")
                    # 如果报错 422，通常是参数验证失败
                    if response.status_code == 422:
                        config.console.print(f"[dim]{response.text}[/dim]")

            except Exception as e:
                config.console.print(f"[red]Audio Error:[/red] {e}")
                self.voice_enabled = False

    def terminate(self):
        config.console.print("\n[yellow]正在切断神经连接并释放 RTX 5080 资源...[/yellow]")
        try:
            payload = {
                "model": config.TARGET_MODEL,
                "keep_alive": 0 
            }
            requests.post(config.OLLAMA_URL, json=payload, timeout=2.0)
            config.console.print("[green]✔ 模型已从显存卸载。系统休眠。[/green]")
        except Exception:
            pass