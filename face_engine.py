import requests
import threading
import config

class FaceEngine:
    """
    Project Ethereal 面部表情引擎 (The Face)
    负责将情感状态同步给 Live2D 服务器
    """
    def __init__(self):
        # 指向 live2d_server.py 的控制接口
        self.api_url = "http://127.0.0.1:8000/control"
        self.enabled = True
        
        # 简单的自检
        self._check_connection()

    def _check_connection(self):
        try:
            # 尝试访问 Live2D 服务主页看是否活着
            requests.get("http://127.0.0.1:8000/web/", timeout=0.5)
            config.console.print("[green]● Face (Live2D): Online[/green]")
            self.enabled = True
        except:
            config.console.print("[yellow]○ Face (Live2D): Offline (Server not running)[/yellow]")
            config.console.print("[dim]提示: 请先运行 python live2d_server.py[/dim]")
            self.enabled = False

    def set_expression(self, emotion):
        """
        发送表情指令
        emotion: neutral, happy, angry, etc.
        """
        if not self.enabled: return

        # 放到后台线程发请求，防止卡住主对话逻辑
        threading.Thread(target=self._send_request, args=("expression", emotion), daemon=True).start()

    def set_mouth_open(self, value):
        """
        设置嘴巴张合度 (0.0 - 1.0)
        用于口型同步
        """
        if not self.enabled: return
        threading.Thread(target=self._send_request, args=("lipsync", value), daemon=True).start()

    def _send_request(self, type_str, value):
        try:
            payload = {"type": type_str, "value": value}
            # 发送给 live2d_server.py
            requests.post(self.api_url, json=payload, timeout=0.2)
        except Exception:
            pass # 脸部通讯失败不应影响主流程，静默失败即可