import time
import sys
import os

# Add parent directory to path to import stt_engine
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from rich.console import Console
from stt_engine import STTEngine

console = Console()

def on_speech_recognized(perception_data):
    console.print(f"[bold magenta]Callback received:[/bold magenta] {perception_data['text']}")
    console.print(f"[dim cyan]Metadata: Emotion={perception_data['emotion']}, Event={perception_data['event']}, Lang={perception_data['lang']}[/dim cyan]")
    console.print(f"[dim]Debug: Raw='{perception_data['raw']}'[/dim]")

def main():
    console.print("[bold]Testing STTEngine (SenseVoiceSmall)...[/bold]")
    console.print("Please speak into your microphone.")
    console.print("Press Ctrl+C to stop.")

    # Initialize Engine
    try:
        # model_size is removed, device defaults to cuda
        engine = STTEngine(callback=on_speech_recognized, device="cuda")
    except Exception as e:
        console.print(f"[red]Failed to initialize engine.[/red]")
        console.print(f"Error: {e}")
        return

    # Start listening
    engine.start_listening()

    try:
        # Simulate a main loop
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping...[/yellow]")
        engine.stop_listening()
        console.print("[green]Test finished.[/green]")
        sys.exit(0)

if __name__ == "__main__":
    main()
