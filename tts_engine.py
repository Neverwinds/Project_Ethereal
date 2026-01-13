import requests
import pygame
import io
import os
import re
import time
import subprocess
import config
from rich.panel import Panel

class TTSEngine:
    """
    Project Ethereal 语音合成引擎 (The Mouth)
    负责文本清洗、情感预处理、语音合成与播放
    """
    def __init__(self, voice_config):
        self.voice_cfg = voice_config
        self.enabled = False
        
        # 初始化音频驱动
        try:
            pygame.mixer.init()
        except Exception as e:
            config.console.print(f"[yellow][Audio] Driver init failed: {e}[/yellow]")

        # 初始检查与自动启动
        self._ensure_service_running()

    def _ensure_service_running(self):
        """探测 TTS 服务状态，如果未运行则尝试自动启动"""
        if self._check_connection():
            self._validate_assets()
            return

        # 如果连接失败，尝试自动启动
        config.console.print("[yellow]⚠ 检测到 GPT-SoVITS 未运行，尝试自动唤醒...[/yellow]")
        
        script_path = os.path.join(config.GPT_SOVITS_DIR, config.TTS_LAUNCH_SCRIPT)
        if not os.path.exists(script_path):
            config.console.print(f"[red]❌ 找不到启动脚本: {script_path}[/red]")
            config.console.print("[dim]请检查 config.py 中的 GPT_SOVITS_DIR 配置[/dim]")
            self.enabled = False
            return

        try:
            # 使用 subprocess 启动 .bat 文件
            # cwd=config.GPT_SOVITS_DIR 极其重要，确保脚本在它的目录下运行
            subprocess.Popen(
                ["cmd.exe", "/c", "start", config.TTS_LAUNCH_SCRIPT], 
                cwd=config.GPT_SOVITS_DIR,
                shell=True
            )
            
            # 等待服务启动 (轮询检测)
            with config.console.status("[bold magenta]正在启动 GPT-SoVITS 引擎... (这可能需要几秒)[/bold magenta]", spinner="dots"):
                for _ in range(20): # 最多等待 20秒
                    time.sleep(1)
                    if self._check_connection():
                        config.console.print("[bold green]✔ GPT-SoVITS 引擎启动成功！[/bold green]")
                        self._validate_assets()
                        return
            
            config.console.print("[red]❌ 启动超时。请检查弹出的黑框框是否有报错。[/red]")
            self.enabled = False

        except Exception as e:
            config.console.print(f"[red]❌ 自动启动失败: {e}[/red]")
            self.enabled = False

    def _check_connection(self):
        """仅检测 HTTP 连接"""
        try:
            # 访问 API 根路径或 docs 来测试存活，不请求 /tts 以免参数报错
            # 这里我们假设根目录 http://127.0.0.1:9880/ 是通的
            test_url = config.TTS_API_URL.replace("/tts", "/") 
            requests.get(test_url, timeout=1.0)
            return True
        except:
            return False

    def _validate_assets(self):
        """连接成功后，校验素材"""
        if not os.path.exists(config.REF_AUDIO_PATH):
            config.console.print(Panel(f"TTS 在线，但参考音频缺失:\n{config.REF_AUDIO_PATH}", style="bold yellow"))
            self.enabled = False
        else:
            self.enabled = True
            config.console.print(Panel("● Mouth (GPT-SoVITS): Online [Local]", style="bold green"))

    def _clean_text(self, text):
        """深度文本清洗"""
        if not text: return ""
        text = re.sub(r'[\（\(\[].*?[\）\)\]]', '', text)
        text = text.replace('*', '')
        text = re.sub(r'[—~-]{1,}', '，', text)
        text = re.sub(r'["\'“”‘’]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text if text else "..."

    def speak(self, text):
        if not self.enabled or not text:
            return

        clean_text = self._clean_text(text)
        
        with config.console.status(f"[bold blue]Synthesizing: '{clean_text}'...[/bold blue]", spinner="bouncingBar"):
            try:
                params = {
                    "text": clean_text,
                    "text_lang": self.voice_cfg.get("target_lang", "zh"),    
                    "ref_audio_path": config.REF_AUDIO_PATH,            
                    "prompt_text": self.voice_cfg.get("prompt_text", ""),
                    "prompt_lang": self.voice_cfg.get("prompt_lang", "zh"),  
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

            except Exception as e:
                config.console.print(f"[red]Audio Error:[/red] {e}")
                self.enabled = False