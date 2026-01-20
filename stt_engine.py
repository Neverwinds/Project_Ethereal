import os
import time
import threading
import queue
import re
import numpy as np
import pyaudio
import torch
from funasr import AutoModel
from rich.console import Console

console = Console()

class STTEngine:
    """
    Speech-to-Text Engine using SenseVoiceSmall (via FunASR) for accurate text,
    emotion and event detection.
    """
    
    # SenseVoiceSmall Supported Tags
    # Emotions (Reference)
    EMOTION_TAGS = {
        "HAPPY": "Happy / 开心",
        "SAD": "Sad / 悲伤",
        "ANGRY": "Angry / 愤怒",
        "NEUTRAL": "Neutral / 中性",
    }
    
    # Audio Events (Reference)
    EVENT_TAGS = {
        "Laughter": "Laughter / 笑声",
        "Music": "Music / 音乐",
        "Speech": "Speech / 说话",
        "Applause": "Applause / 掌声",
        "Cry": "Cry / 哭声",
        "Sneeze": "Sneeze / 喷嚏",
        "Cough": "Cough / 咳嗽",
        "Breath": "Breath / 呼吸声"
    }

    def __init__(self, callback, device="cuda"):
        """
        Initialize the STT Engine.

        Args:
            callback (function): Function to call with transcribed text and metadata.
                                 Signature: callback(perception_data)
            device (str): Device to run models on ("cuda" or "cpu").
        """
        self.callback = callback
        self.is_running = False
        self.is_listening_active = True
        self.audio_queue = queue.Queue()
        
        # Audio configuration
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 16000
        self.CHUNK = 512
        
        # VAD configuration
        self.vad_threshold = 0.5
        self.silence_duration_threshold = 0.8
        self.min_speech_duration_ms = 250
        
        console.log(f"[bold green]Initializing STT Engine (SenseVoice)...[/bold green]")

        # Check CUDA availability
        if device == "cuda" and not torch.cuda.is_available():
            console.print("[bold yellow]Warning: CUDA requested but Torch not compiled with CUDA enabled or no GPU found.[/bold yellow]")
            console.print("[yellow]Falling back to CPU. This will be slower.[/yellow]")
            device = "cpu"
        
        self.device = device
        self.vad_device = "cpu" # Force VAD to CPU to avoid CUDA compatibility issues
        
        try:
            self._init_models(device)
            
        except Exception as e:
            console.print(f"[bold red]Error initializing models:[/bold red] {e}")
            raise e

        self.p = pyaudio.PyAudio()

    def _init_models(self, device):
        """Initialize all AI models."""
        
        # 1. Load Silero VAD
        console.log(f"Loading Silero VAD model on {self.vad_device}...")
        self.vad_model, utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            onnx=False
        )
        (self.get_speech_timestamps, self.save_audio, self.read_audio, self.VADIterator, self.collect_chunks) = utils
        self.vad_model.to(self.vad_device)
        console.log("[green]Silero VAD loaded.[/green]")

        # 2. Load SenseVoiceSmall (ASR & Events & Emotion)
        console.log(f"Loading SenseVoiceSmall on {device}...")
        # disable_update=True to avoid checking for updates at runtime
        self.asr_model = AutoModel(
            model="iic/SenseVoiceSmall",
            device=device,
            disable_update=True,
            hub="ms", # Use ModelScope
            log_level="ERROR"
        )
        console.log("[green]SenseVoiceSmall loaded.[/green]")

        console.log("[bold green]All systems initialized.[/bold green]")

    def start_listening(self):
        """Start the audio recording and processing thread."""
        self.is_running = True
        self.processing_thread = threading.Thread(target=self._process_audio, daemon=True)
        self.processing_thread.start()
        console.log("[bold cyan]STT Engine started listening...[/bold cyan]")

    def stop_listening(self):
        """Stop the listening thread."""
        self.is_running = False
        if hasattr(self, 'processing_thread'):
            self.processing_thread.join()
        self.p.terminate()

    def set_listening_active(self, active: bool):
        """Enable or disable VAD processing."""
        self.is_listening_active = active
        status = "active" if active else "inactive"
        console.log(f"[yellow]STT Listening is now {status}[/yellow]")

    def _process_audio(self):
        """Main loop for capturing and processing audio."""
        try:
            stream = self.p.open(format=self.FORMAT,
                                 channels=self.CHANNELS,
                                 rate=self.RATE,
                                 input=True,
                                 frames_per_buffer=self.CHUNK)
        except OSError as e:
            console.print(f"[bold red]Could not open microphone:[/bold red] {e}")
            return

        speech_buffer = []
        silence_start_time = None
        is_speaking = False
        
        console.log("Microphone stream opened. Waiting for voice...")

        while self.is_running:
            try:
                data = stream.read(self.CHUNK, exception_on_overflow=False)
                
                if not self.is_listening_active:
                    if speech_buffer:
                        speech_buffer = []
                        is_speaking = False
                        silence_start_time = None
                    continue

                audio_chunk = np.frombuffer(data, dtype=np.int16)
                audio_float32 = audio_chunk.astype(np.float32) / 32768.0
                
                with torch.no_grad():
                    speech_prob = self.vad_model(torch.from_numpy(audio_float32).to(self.vad_device), self.RATE).item()

                current_time = time.time()

                if speech_prob > self.vad_threshold:
                    if not is_speaking:
                        is_speaking = True
                        console.log("[dim]Voice start detected...[/dim]")
                    
                    speech_buffer.append(audio_chunk)
                    silence_start_time = None
                    
                else:
                    if is_speaking:
                        speech_buffer.append(audio_chunk)
                        
                        if silence_start_time is None:
                            silence_start_time = current_time
                        
                        if current_time - silence_start_time > self.silence_duration_threshold:
                            console.log("[dim]End of sentence detected. Processing...[/dim]")
                            self._process_speech(speech_buffer)
                            
                            speech_buffer = []
                            is_speaking = False
                            silence_start_time = None
            
            except Exception as e:
                console.print(f"[red]Error in audio processing loop:[/red] {e}")
                time.sleep(0.5)
                continue

        stream.stop_stream()
        stream.close()

    def _process_speech(self, buffer):
        """
        Process audio with SenseVoice for ASR, emotion and event detection.
        """
        if not buffer:
            return

        # Combine chunks
        full_audio_int16 = np.concatenate(buffer)

        # Convert to float32 normalized for SenseVoice
        full_audio_float32 = full_audio_int16.astype(np.float32) / 32768.0

        try:
            # SenseVoice expects input array directly
            asr_res = self.asr_model.generate(
                input=full_audio_float32,
                cache={},
                language="auto",
                use_itn=True,
                batch_size_s=60
            )

            # Debug: Print raw SenseVoice response
            console.print(f"[dim yellow]SenseVoice Raw Response: {asr_res}[/dim yellow]")

            # Extract SenseVoice Raw Text
            raw_sensevoice = ""
            if asr_res and isinstance(asr_res, list) and len(asr_res) > 0:
                raw_sensevoice = asr_res[0].get("text", "")

            # Debug: Print extracted raw text
            console.print(f"[dim yellow]Extracted Raw Text: '{raw_sensevoice}'[/dim yellow]")

            # Parse and callback
            self._parse_and_callback(raw_sensevoice)

        except Exception as e:
            console.print(f"[red]Speech Processing Error:[/red] {e}")

    def _parse_and_callback(self, raw_sensevoice):
        """
        Parse SenseVoice output and trigger callback.
        """
        # 1. Parse SenseVoice Tags
        sv_tags = re.findall(r'<\|([A-Za-z0-9]+)\|>', raw_sensevoice)
        clean_text = re.sub(r'<\|.*?\|>', '', raw_sensevoice).strip()

        emotion = "NEUTRAL"
        event = None
        detected_lang = "zh" # Default to zh

        # Known definitions
        known_events = {
            "Laughter", "Speech", "Music", "Applause",
            "Cry", "Sneeze", "Breath", "Cough"
        }
        known_langs = {"zh", "en"} # Restrict to zh and en
        ignored_tags = {"withitn", "woitn"}

        for tag in sv_tags:
            if tag in known_langs:
                detected_lang = tag
                continue

            # Check for ignored tags or other languages
            if tag in ignored_tags or tag in ["ja", "ko", "yue"]:
                continue

            if tag in known_events:
                event = tag
            elif tag != "NEUTRAL":
                emotion = tag # SenseVoice emotion

        # 2. Construct Result
        perception_data = {
            "text": clean_text,
            "emotion": emotion,
            "event": event,
            "raw": raw_sensevoice,
            "lang": detected_lang
        }

        # 3. Output & Callback
        has_text = bool(clean_text)
        has_event = event is not None

        if has_text or has_event:
            # Rich logging
            console.print(f"[bold blue]Heard:[/bold blue] '{clean_text}'")
            console.print(f"[dim]Emotion: {emotion} | Event: {event} | Lang: {detected_lang}[/dim]")

            if self.callback:
                self.callback(perception_data)
        else:
            console.log("[dim]No meaningful content detected.[/dim]")

    def _unload_local_model(self):
         pass
