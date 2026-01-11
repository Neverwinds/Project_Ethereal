import os
import sys
from urllib.parse import urlparse
from rich.console import Console

# 初始化全局共用的控制台
console = Console()

# ==========================================
#        🛡️ 安全协议区域 (SECURITY PROTOCOL)
# ==========================================

# [Level 1] 强制禁用系统代理
os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""
os.environ["ALL_PROXY"] = ""
os.environ["NO_PROXY"] = "*" 

# ==========================================
#              全局配置区域 (CONFIG)
# ==========================================

# 获取项目根目录 (即 config.py 所在的文件夹)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 1. 大脑配置 (Ollama)
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
# [已恢复] 保持 qwen3-vl:8b (如果你还没换的话)
TARGET_MODEL = "qwen3-vl:8b" 

# 2. 嘴巴配置 (GPT-SoVITS)
# [关键修复] 添加 /tts 后缀
# API v2 的标准接口路径是 /tts，而不是根目录
TTS_API_URL = "http://127.0.0.1:9880/tts" 

# 3. 文件路径配置
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

# 确保 assets 目录存在
if not os.path.exists(ASSETS_DIR):
    os.makedirs(ASSETS_DIR, exist_ok=True)

# 参考音频路径
REF_AUDIO_PATH = os.path.join(ASSETS_DIR, "ref.wav")

# 人格配置文件路径
CHARACTER_CONFIG_PATH = os.path.join(BASE_DIR, "character.json")

def security_audit(url, service_name):
    """
    [Level 2] 运行时地址审计
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        # 注意：localhost 解析出来可能是 None 或者 'localhost'
        if hostname and hostname not in ["127.0.0.1", "localhost"]:
            console.print(f"[bold red][SECURITY ALERT] 发现高危配置！[/bold red]")
            console.print(f"服务 '{service_name}' 的目标地址指向了非本地网络: [yellow]{hostname}[/yellow]")
            sys.exit(1) 
    except Exception as e:
        console.print(f"[red]配置解析失败: {e}[/red]")
        sys.exit(1)