import requests
import io
import os
import re
import time
import subprocess
import threading
import numpy as np
import sounddevice as sd
import soundfile as sf
import config
from rich.panel import Panel

class TTSEngine:
    """
    Project Ethereal 语音合成引擎 (The Mouth)
    [V2.4] 口型柔和版 - 降低增益，增加细腻度
    """
    def __init__(self, voice_config, lip_sync_callback=None):
        self.voice_cfg = voice_config
        self.enabled = False
        self.lip_sync_callback = lip_sync_callback
        self.audio_stream = None 
        
        self._ensure_service_running()

    def _ensure_service_running(self):
        """探测 TTS 服务状态"""
        if self._check_connection():
            self._validate_assets()
            return

        config.console.print("[yellow]⚠ 检测到 GPT-SoVITS 未运行，尝试自动唤醒...[/yellow]")
        
        script_path = os.path.join(config.GPT_SOVITS_DIR, config.TTS_LAUNCH_SCRIPT)
        if not os.path.exists(script_path):
            config.console.print(f"[red]❌ 找不到启动脚本: {script_path}[/red]")
            self.enabled = False
            return

        try:
            subprocess.Popen(
                ["cmd.exe", "/c", "start", config.TTS_LAUNCH_SCRIPT], 
                cwd=config.GPT_SOVITS_DIR,
                shell=True
            )
            
            with config.console.status("[bold magenta]正在启动 GPT-SoVITS 引擎...[/bold magenta]", spinner="dots"):
                for _ in range(20):
                    time.sleep(1)
                    if self._check_connection():
                        config.console.print("[bold green]✔ GPT-SoVITS 引擎启动成功！[/bold green]")
                        self._validate_assets()
                        return
            
            config.console.print("[red]❌ 启动超时。[/red]")
            self.enabled = False

        except Exception as e:
            config.console.print(f"[red]❌ 自动启动失败: {e}[/red]")
            self.enabled = False

    def _check_connection(self):
        try:
            test_url = config.TTS_API_URL.replace("/tts", "/") 
            requests.get(test_url, timeout=1.0)
            return True
        except:
            return False

    def _validate_assets(self):
        if not os.path.exists(config.REF_AUDIO_PATH):
            config.console.print(Panel(f"TTS 在线，但参考音频缺失:\n{config.REF_AUDIO_PATH}", style="bold yellow"))
            self.enabled = False
        else:
            self.enabled = True
            config.console.print(Panel("● Mouth (GPT-SoVITS): Online [Local]", style="bold green"))

    def _clean_text(self, text):
        if not text: return ""
        text = re.sub(r'[\（\(\[].*?[\）\)\]]', '', text)
        text = text.replace('*', '')
        text = re.sub(r'[—~-]{1,}', '，', text)
        text = re.sub(r'["\'“”‘’]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text if text else "..."

    def speak(self, text):
        """执行语音合成并播放"""
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
                    audio_data = io.BytesIO(response.content)
                    data, fs = sf.read(audio_data, dtype='float32')
                    self._play_with_lipsync(data, fs)
                else:
                    config.console.print(f"[red]TTS API Error ({response.status_code})[/red]")

            except Exception as e:
                config.console.print(f"[red]Audio Error:[/red] {e}")

    def _play_with_lipsync(self, data, fs):
        """
        [调优版] 播放音频并在回调中计算合理的口型值
        """
        if data.ndim > 1:
            amplitude_data = np.mean(data, axis=1)
        else:
            amplitude_data = data

        blocksize = 1024 
        current_frame = 0
        
        def callback(outdata, frames, time_info, status):
            nonlocal current_frame
            if status: print(status)
            
            chunk_size = len(outdata)
            end_frame = current_frame + chunk_size
            
            chunk = data[current_frame:end_frame]
            amp_chunk = amplitude_data[current_frame:end_frame]
            
            if len(chunk) < chunk_size:
                outdata[:len(chunk)] = chunk.reshape(-1, 1) if chunk.ndim == 1 else chunk
                outdata[len(chunk):] = 0
                raise sd.CallbackStop()
            else:
                outdata[:] = chunk.reshape(-1, 1) if chunk.ndim == 1 else chunk
            
            # --- [算法优化核心 V2.4] ---
            if len(amp_chunk) > 0:
                rms = np.sqrt(np.mean(amp_chunk**2))
            else:
                rms = 0.0
            
            # 1. 保持底噪过滤
            if rms < 0.002:
                lipsync_value = 0.0
            else:
                # 2. 降低增益：从 6.0 降至 4.0
                # 这样 0.2 的音量 (大声) * 4 = 0.8，不会封顶
                # 0.1 的音量 (正常) * 4 = 0.4
                lipsync_value = min(1.0, rms * 4.0)

            # 3. [关键] 强制转换为纯 Python float，防止 Numpy 类型干扰 JSON 序列化
            lipsync_value = float(lipsync_value)

            if self.lip_sync_callback:
                self.lip_sync_callback(lipsync_value)
            
            current_frame += chunk_size

        try:
            with sd.OutputStream(samplerate=fs, callback=callback, blocksize=blocksize):
                sd.sleep(int(len(data) / fs * 1000) + 100)
        except Exception as e:
            config.console.print(f"[red]Playback Error:[/red] {e}")
            
        if self.lip_sync_callback:
            self.lip_sync_callback(0.0)