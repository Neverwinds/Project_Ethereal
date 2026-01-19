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
    [V2.6] 修复音画同步延迟 - 将表情触发延迟到播放时刻
    """
    def __init__(self, voice_config, lip_sync_callback=None, expression_callback=None):
        self.voice_cfg = voice_config
        self.enabled = False
        self.lip_sync_callback = lip_sync_callback
        self.expression_callback = expression_callback # [新增] 表情回调
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
        # 移除 [] () 中的内容
        text = re.sub(r'[\（\(\[].*?[\）\)\]]', '', text)
        # 移除 *...* 中的动作描述
        text = re.sub(r'\*.*?\*', '', text)
        
        text = re.sub(r'[—~-]{1,}', '，', text)
        text = re.sub(r'["\'“”‘’]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text if text else "..."

    def speak(self, text, emotion="neutral"):
        """
        执行语音合成并播放
        [修改] 接收 emotion 参数
        """
        if not self.enabled or not text:
            # [新增] 即使不说话，也要负责重置表情，防止卡在 Thinking
            if self.expression_callback:
                self.expression_callback("neutral")
            return

        clean_text = self._clean_text(text)
        
        # [新增] 清洗后如果没字了，也要重置
        if not clean_text or clean_text == "...":
            if self.expression_callback:
                self.expression_callback("neutral")
            return
        
        with config.console.status(f"[bold blue]Synthesizing: '{clean_text}'...[/bold blue]", spinner="bouncingBar"):
            try:
                params = {
                    "text": clean_text,
                    "text_lang": self.voice_cfg.get("target_lang", "zh"),    
                    "ref_audio_path": config.REF_AUDIO_PATH,            
                    "prompt_text": self.voice_cfg.get("prompt_text", ""),
                    "prompt_lang": self.voice_cfg.get("prompt_lang", "zh"),  
                }
                
                # 这里是耗时操作 (约1-2秒)
                response = requests.get(config.TTS_API_URL, params=params, timeout=30)

                if response.status_code == 200:
                    audio_data = io.BytesIO(response.content)
                    data, fs = sf.read(audio_data, dtype='float32')
                    
                    # --- [核心修复] ---
                    # 音频下载完毕，准备播放了，这时候再触发表情
                    # 这样表情和声音就是同步的
                    if self.expression_callback:
                        self.expression_callback(emotion)
                    
                    self._play_with_lipsync(data, fs)
                else:
                    config.console.print(f"[red]TTS API Error ({response.status_code})[/red]")
                    # [新增] API 错误也要重置
                    if self.expression_callback:
                        self.expression_callback("neutral")

            except Exception as e:
                config.console.print(f"[red]Audio Error:[/red] {e}")
                # [新增] 异常也要重置
                if self.expression_callback:
                    self.expression_callback("neutral")

    def _play_with_lipsync(self, data, fs):
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
            
            # 保持之前的参数：门限 0.002, 增益 4.0
            if len(amp_chunk) > 0:
                rms = np.sqrt(np.mean(amp_chunk**2))
            else:
                rms = 0.0
            
            if rms < 0.002:
                lipsync_value = 0.0
            else:
                lipsync_value = min(1.0, rms * 4.0)

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
            
        # [新增] 播放结束后，恢复 Neutral 表情 (Decay)
        if self.expression_callback:
            self.expression_callback("neutral")