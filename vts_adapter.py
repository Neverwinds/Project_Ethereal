import asyncio
import threading
import json
import pyvts
import config

class VTSAdapter:
    """
    Project Ethereal -> VTube Studio 桥接器
    负责处理鉴权、连接以及高频参数注入
    """
    def __init__(self):
        # 定义插件信息
        self.plugin_info = {
            "plugin_name": "Ethereal Core",
            "developer": "Master",
            "authentication_token_path": "./vts_token.txt"
        }
        
        # 初始化 pyvts
        self.vts = pyvts.vts(plugin_info=self.plugin_info)
        self.connected = False
        self.event_loop = None
        
        # 启动后台连接线程 (VTS 通讯必须在 Asyncio 循环中运行)
        threading.Thread(target=self._run_loop, daemon=True).start()

    def _run_loop(self):
        """在后台线程运行 Asyncio Loop"""
        self.event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.event_loop)
        self.event_loop.run_until_complete(self._connect_and_auth())
        self.event_loop.run_forever()

    async def _connect_and_auth(self):
        """连接并鉴权"""
        try:
            # 1. 尝试连接
            await self.vts.connect()
            
            # 2. 尝试鉴权
            # pyvts 会自动读取 token 文件，如果没有则请求新 token
            await self.vts.request_authenticate_token() 
            await self.vts.request_authenticate()
            
            self.connected = True
            config.console.print("[green]✔ VTube Studio Link Established![/green]")
            config.console.print("[dim]提示: 如果 VTube Studio 弹出请求，请点击 'Allow'[/dim]")
            
        except Exception as e:
            config.console.print(f"[red]❌ VTS Connection Failed: {e}[/red]")
            config.console.print("[yellow]请确保 VTube Studio 已打开并在设置中开启了 API (端口8001)[/yellow]")

    def set_mouth_open(self, value):
        """
        [口型同步接口]
        直接注入参数控制嘴巴
        VTS 标准参数名: MouthOpen (0.0 - 1.0)
        """
        if not self.connected or self.event_loop is None: 
            return
        
        async def _send():
            try:
                # [关键修复] 手动构造请求字典，绕过 pyvts 版本兼容问题
                payload = {
                    "apiName": "VTubeStudioPublicAPI",
                    "apiVersion": "1.0",
                    "requestID": "LipSync",
                    "messageType": "InjectParameterDataRequest",
                    "data": {
                        "faceFound": False, # 强制覆盖摄像头捕捉
                        "mode": "set",
                        "parameterValues": [
                            {
                                "id": "MouthOpen",
                                "value": value,
                                "weight": 1.0
                            }
                        ]
                    }
                }
                await self.vts.request(payload)
            except Exception:
                pass # 高频数据允许偶尔丢包，不打印错误以免刷屏
        
        # 将发送任务扔进后台循环，非阻塞执行
        asyncio.run_coroutine_threadsafe(_send(), self.event_loop)

    def set_expression(self, emotion):
        """
        [表情触发接口]
        触发 VTS 里的 Hotkey (需要你在 VTS 里提前配好按键)
        这里作为预留接口，因为 VTS 的表情调用比较复杂，通常建议映射到参数
        """
        # 简单打印一下，证明信号通了
        # config.console.print(f"[VTS] Trigger Emotion: {emotion}")
        pass