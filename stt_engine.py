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
    Speech-to-Text Engine using SenseVoiceSmall (via FunASR) and Silero VAD.
    """
    def __init__(self, callback, device="cuda"):
        """
        Initialize the STT Engine.

        Args:
            callback (function): Function to call with transcribed text and metadata.
                                 Signature: callback(text, metadata_dict)
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
        
        console.log(f"[bold green]Initializing STT Engine (SenseVoiceSmall)...[/bold green]")

        # Check CUDA availability
        if device == "cuda" and not torch.cuda.is_available():
            console.print("[bold yellow]Warning: CUDA requested but Torch not compiled with CUDA enabled or no GPU found.[/bold yellow]")
            console.print("[yellow]Falling back to CPU. This will be slower.[/yellow]")
            device = "cpu"
        
        self.device = device
        self.vad_device = "cpu" # Force VAD to CPU to avoid CUDA compatibility issues
        
        try:
            # Load Silero VAD
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

            # Load SenseVoiceSmall
            console.log(f"Loading SenseVoiceSmall model on {device}...")
            # disable_update=True to avoid checking for updates at runtime
            self.model = AutoModel(
                model="iic/SenseVoiceSmall",
                device=device,
                disable_update=True,
                hub="ms" # Use ModelScope
            )
            console.log("[green]SenseVoiceSmall loaded.[/green]")
            
        except Exception as e:
            console.print(f"[bold red]Error initializing models:[/bold red] {e}")
            raise e

        self.p = pyaudio.PyAudio()

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
                            console.log("[dim]End of sentence detected. Transcribing...[/dim]")
                            self._transcribe_buffer(speech_buffer)
                            
                            speech_buffer = []
                            is_speaking = False
                            silence_start_time = None
            
            except Exception as e:
                console.print(f"[red]Error in audio processing loop:[/red] {e}")
                time.sleep(0.5)
                continue

        stream.stop_stream()
        stream.close()

    def _transcribe_buffer(self, buffer):
        """Transcribe the accumulated audio buffer using SenseVoice."""
        if not buffer:
            return

        # Combine all chunks
        full_audio_int16 = np.concatenate(buffer)
        
        # Convert int16 to float32 and normalize to [-1, 1]
        # SenseVoice/FunASR requires float32 input to avoid 'normal_kernel_cpu' not implemented for 'Short' error
        full_audio_float32 = full_audio_int16.astype(np.float32) / 32768.0
        
        try:
            # Inference
            res = self.model.generate(
                input=full_audio_float32,
                cache={},
                language="auto", 
                use_itn=True,
                batch_size_s=60
            )
            
            # Result format is typically a list of dicts: [{'text': '...'}]
            if res and isinstance(res, list) and len(res) > 0:
                raw_text = res[0].get("text", "")
                
                # Parse output
                perception_data = self._parse_sensevoice_output(raw_text)
                
                # Logic: Trigger callback if there is text OR if there is a significant event (not None)
                has_text = bool(perception_data["text"])
                has_event = perception_data["event"] is not None
                
                if has_text or has_event:
                    console.log(f"[bold blue]Heard:[/bold blue] '{perception_data['text']}'")
                    console.log(f"[dim]Emotion: {perception_data['emotion']} | Event: {perception_data['event']} | Lang: {perception_data['lang']}[/dim]")
                    
                    if self.callback:
                        self.callback(perception_data)
                else:
                    console.log("[dim]No meaningful content detected.[/dim]")
            else:
                console.log("[dim]No text recognized.[/dim]")

        except Exception as e:
            console.print(f"[red]Transcription error:[/red] {e}")

    def _parse_sensevoice_output(self, raw_text):
        """
        Parse SenseVoice output to extract text, emotion, and events.
        Dynamic parsing: Treat unknown tags as emotions unless they are known events.
        """
        if not raw_text:
            return {
                "text": "",
                "emotion": "NEUTRAL",
                "event": None,
                "lang": "zh"
            }

        # 1. Extract tags using generalized regex
        # Captures content inside <|...|>
        tags = re.findall(r'<\|([A-Za-z0-9]+)\|>', raw_text)
        
        # 2. Extract clean text (remove all tags)
        clean_text = re.sub(r'<\|.*?\|>', '', raw_text).strip()
        
        # 3. Initialize perception data
        perception_data = {
            "text": clean_text,
            "emotion": "NEUTRAL",
            "event": None,
            "lang": "zh"
        }
        
        # 4. Analyze tags
        # Define known events set
        known_events = {
            "Laughter", "Speech", "Music", "Applause", 
            "Cry", "Sneeze", "Breath", "Cough"
        }
        
        # Define known language codes (to avoid treating them as emotions)
        known_langs = {"zh", "en", "ja", "ko", "yue"}

        # Define tags to ignore (technical tags)
        ignored_tags = {"withitn", "woitn"}
        
        for tag in tags:
            # Check for language first
            if tag in known_langs:
                perception_data["lang"] = tag
                continue

            # Check for ignored tags
            if tag in ignored_tags:
                continue
                
            # Check if it is a known event
            # SenseVoice event tags are typically CamelCase or specific strings
            if tag in known_events:
                perception_data["event"] = tag
            else:
                # If not an event and not a language, treat as Emotion
                # This allows dynamic open-ended emotions (e.g., SURPRISE, EXCITED)
                # Avoid overwriting with lower-priority tags if multiple present? 
                # For now, last tag wins or we can prioritize non-NEUTRAL
                if tag != "NEUTRAL": 
                     perception_data["emotion"] = tag
                elif perception_data["emotion"] == "NEUTRAL":
                     # Only set NEUTRAL if we haven't found a stronger emotion yet
                     perception_data["emotion"] = tag
                
        return perception_data

    def _unload_local_model(self):
         pass
