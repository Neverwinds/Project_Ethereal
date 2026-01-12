import requests
import pygame
import io
import os
import re
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

        # 初始检查
        self.check_service_status()

    def check_service_status(self):
        """探测 TTS 服务与素材状态"""
        try:
            requests.get(config.TTS_API_URL, timeout=1.0)
            
            if not os.path.exists(config.REF_AUDIO_PATH):
                config.console.print(Panel(f"TTS 在线，但参考音频缺失:\n{config.REF_AUDIO_PATH}", style="bold yellow"))
                self.enabled = False
            else:
                self.enabled = True
                config.console.print(Panel("● Mouth (GPT-SoVITS): Online [Local]", style="bold green"))

        except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout):
            self.enabled = False
            config.console.print(Panel("○ Mouth (GPT-SoVITS): Offline", style="bold yellow"))

    def _clean_text(self, text):
        """
        深度文本清洗：适配 TTS 发音习惯
        """
        if not text: return ""
        
        # 1. [未来扩展] 提取情感/动作标签 (目前先直接去除)
        # 例如: (笑) -> 提取 emotion='happy' (未来实现) -> 文本删除 '(笑)'
        text = re.sub(r'[\（\(\[].*?[\）\)\]]', '', text)
        
        # 2. 去除 Markdown
        text = text.replace('*', '')
        
        # 3. 符号转译 (优化停顿)
        # 破折号/波浪线 -> 逗号
        text = re.sub(r'[—~-]{1,}', '，', text)
        
        # 4. [新增] 去除引号 (防止 TTS 读出奇怪的重音或停顿)
        text = re.sub(r'["\'“”‘’]', '', text)
        
        # 5. 去除多余空白
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text if text else "..."

    def speak(self, text):
        """执行语音合成"""
        if not self.enabled or not text:
            return

        # 1. 数据清洗
        clean_text = self._clean_text(text)
        
        # 2. 调用 API
        with config.console.status(f"[bold blue]Synthesizing: '{clean_text}'...[/bold blue]", spinner="bouncingBar"):
            try:
                # 适配 GPT-SoVITS API v2
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