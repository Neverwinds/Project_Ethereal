import os
import sys
from urllib.parse import urlparse
from rich.console import Console

console = Console()

# ==========================================
#        🛡️ 安全协议区域
# ==========================================
os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""
os.environ["ALL_PROXY"] = ""
os.environ["NO_PROXY"] = "*" 

# ==========================================
#              全局配置区域
# ==========================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- 大脑配置 ---
DEFAULT_BRAIN = "ollama"

# 1. Ollama (Local)
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
OLLAMA_MODEL = "qwen3-vl:8b"

# 2. DeepSeek (Cloud)
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

# 3. 嘴巴配置 (GPT-SoVITS)
TTS_API_URL = "http://127.0.0.1:9880/tts" 
GPT_SOVITS_DIR = r"F:\00_Software\GPT-SoVITS-1007-cu128" 
TTS_LAUNCH_SCRIPT = "go-api.bat"

# 4. 文件路径
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
if not os.path.exists(ASSETS_DIR):
    os.makedirs(ASSETS_DIR, exist_ok=True)

REF_AUDIO_PATH = os.path.join(ASSETS_DIR, "ref.wav")
CHARACTER_CONFIG_PATH = os.path.join(BASE_DIR, "character.json")

# [新增] 敏感信息配置文件 (用于存储 API Key)
SECRETS_CONFIG_PATH = os.path.join(BASE_DIR, "secrets.json")

def security_audit(url, service_name):
    """安全审计"""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if hostname and hostname not in ["127.0.0.1", "localhost"]:
            console.print(f"[bold red][SECURITY ALERT] 发现高危配置！[/bold red]")
            console.print(f"本地服务 '{service_name}' 指向了非本地网络: [yellow]{hostname}[/yellow]")
            sys.exit(1) 
    except Exception as e:
        console.print(f"[red]配置解析失败: {e}[/red]")
        sys.exit(1)