import asyncio
import threading
import json
import pyvts
import config

class VTSAdapter:
    """
    Project Ethereal -> VTube Studio 桥接器
    """
    def __init__(self):
        self.plugin_info = {
            "plugin_name": "Ethereal Core",
            "developer": "Master",
            "authentication_token_path": "./vts_token.txt"
        }

        self.vts = pyvts.vts(plugin_info=self.plugin_info)
        self.connected = False
        self.event_loop = None

        # WebSocket 请求锁，防止并发调用 recv() 导致冲突
        self._request_lock = None

        # 存储表情列表: { "ExpressionName": "ExpressionFile" }
        self.expression_cache = {}
        # 当前激活的表情文件名
        self.current_expression = None
        # 表情切换的淡入淡出时间 (秒)
        self.expression_fade_time = 0.5

        threading.Thread(target=self._run_loop, daemon=True).start()

    def _run_loop(self):
        self.event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.event_loop)
        self.event_loop.run_until_complete(self._connect_and_auth())
        self.event_loop.run_forever()

    async def _connect_and_auth(self):
        try:
            # 在 event loop 中初始化请求锁
            self._request_lock = asyncio.Lock()

            await self.vts.connect()
            await self.vts.request_authenticate_token()
            await self.vts.request_authenticate()

            self.connected = True
            config.console.print("[green]✔ VTube Studio Link Established![/green]")

            # 连接成功后，立即请求表情列表
            await self._fetch_expressions()

        except Exception as e:
            config.console.print(f"[red]❌ VTS Connection Failed: {e}[/red]")

    async def _safe_request(self, payload):
        """
        线程安全的 VTS 请求，使用锁防止 WebSocket 并发调用冲突
        """
        async with self._request_lock:
            return await self.vts.request(payload)

    async def _fetch_expressions(self):
        """获取当前模型的所有表情文件"""
        try:
            response = await self._safe_request({
                "apiName": "VTubeStudioPublicAPI",
                "apiVersion": "1.0",
                "requestID": "GetExpressions",
                "messageType": "ExpressionStateRequest",
                "data": {
                    "details": False
                }
            })

            if "data" in response and "expressions" in response["data"]:
                expressions = response["data"]["expressions"]
                config.console.print("\n[cyan]--- VTS Available Expressions ---[/cyan]")
                self.expression_cache.clear()
                for expr in expressions:
                    name = expr.get("name", "Unknown")
                    file = expr.get("file", "")
                    active = expr.get("active", False)
                    self.expression_cache[name] = file
                    status = "[green]✓[/green]" if active else " "
                    config.console.print(f"{status} Name: {name: <20} | File: {file}")
                config.console.print("----------------------------------\n")
        except Exception as e:
            config.console.print(f"[red]Failed to fetch expressions: {e}[/red]")

    def find_expression(self, name_query):
        """
        根据名称查找表情文件名 (模糊匹配)
        """
        # 1. 精确匹配
        if name_query in self.expression_cache:
            return self.expression_cache[name_query]

        # 2. 不区分大小写匹配
        name_lower = name_query.lower()
        for name, file in self.expression_cache.items():
            if name.lower() == name_lower:
                return file

        # 3. 包含匹配 (比如 query="happy", actual="Happy Expression")
        for name, file in self.expression_cache.items():
            if name_lower in name.lower():
                return file

        return None

    def set_expression_by_name(self, name_query, fade_time=None):
        """
        根据名称切换表情 (互斥切换 - 先关闭当前表情，再开启新表情)
        
        Args:
            name_query: 表情名称 (支持模糊匹配)。如果是 "Neutral" 或 "neutral"，则关闭当前表情。
            fade_time: 淡入淡出时间 (秒)，None 则使用默认值
        """
        # 特殊处理 Neutral: 直接关闭当前表情
        if name_query.lower() == "neutral":
            if self.current_expression:
                config.console.print("[VTS] Resetting to Neutral (Deactivating current)")
                if fade_time is None: fade_time = self.expression_fade_time
                async def _reset():
                    await self._deactivate_expression(self.current_expression, fade_time)
                    self.current_expression = None
                asyncio.run_coroutine_threadsafe(_reset(), self.event_loop)
            return

        expr_file = self.find_expression(name_query)
        if expr_file:
            config.console.print(f"[VTS] Found expression '{name_query}' -> File: {expr_file}")
            self.set_expression(expr_file, fade_time)
        else:
            config.console.print(f"[VTS] Expression not found for query: {name_query}")

    def set_expression(self, expression_file, fade_time=None):
        """
        切换到指定表情文件 (互斥切换)

        Args:
            expression_file: 表情文件名 (如 "Happy.exp3.json")
            fade_time: 淡入淡出时间 (秒)，None 则使用默认值
        """
        if not self.connected or self.event_loop is None:
            return

        if fade_time is None:
            fade_time = self.expression_fade_time

        # 如果要切换到同一个表情，跳过
        if self.current_expression == expression_file:
            config.console.print(f"[VTS] Expression already active: {expression_file}")
            return

        async def _switch():
            try:
                # 1. 先关闭当前激活的表情 (如果有)
                if self.current_expression:
                    await self._deactivate_expression(self.current_expression, fade_time)

                # 2. 激活新表情
                await self._activate_expression(expression_file, fade_time)
                self.current_expression = expression_file

            except Exception as e:
                config.console.print(f"[red]Failed to switch expression: {e}[/red]")

        asyncio.run_coroutine_threadsafe(_switch(), self.event_loop)

    async def _activate_expression(self, expression_file, fade_time):
        """激活表情"""
        payload = {
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": "ActivateExpression",
            "messageType": "ExpressionActivationRequest",
            "data": {
                "expressionFile": expression_file,
                "active": True,
                "fadeTime": fade_time
            }
        }
        await self._safe_request(payload)
        config.console.print(f"[VTS] Activated expression: {expression_file} (fade: {fade_time}s)")

    async def _deactivate_expression(self, expression_file, fade_time):
        """关闭表情"""
        payload = {
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": "DeactivateExpression",
            "messageType": "ExpressionActivationRequest",
            "data": {
                "expressionFile": expression_file,
                "active": False,
                "fadeTime": fade_time
            }
        }
        await self._safe_request(payload)
        config.console.print(f"[VTS] Deactivated expression: {expression_file}")

    async def _deactivate_all_expressions(self, fade_time=None):
        """关闭所有激活的表情"""
        if fade_time is None:
            fade_time = self.expression_fade_time

        try:
            # 获取当前表情状态
            response = await self._safe_request({
                "apiName": "VTubeStudioPublicAPI",
                "apiVersion": "1.0",
                "requestID": "GetExpressions",
                "messageType": "ExpressionStateRequest",
                "data": {"details": False}
            })

            if "data" in response and "expressions" in response["data"]:
                for expr in response["data"]["expressions"]:
                    if expr.get("active", False):
                        await self._deactivate_expression(expr["file"], fade_time)

            self.current_expression = None
        except Exception as e:
            config.console.print(f"[red]Failed to deactivate expressions: {e}[/red]")

    def set_mouth_open(self, value):
        if not self.connected or self.event_loop is None: return
        
        async def _send():
            try:
                payload = {
                    "apiName": "VTubeStudioPublicAPI",
                    "apiVersion": "1.0",
                    "requestID": "LipSync",
                    "messageType": "InjectParameterDataRequest",
                    "data": {
                        "faceFound": False,
                        "mode": "set",
                        "parameterValues": [{"id": "MouthOpen", "value": value, "weight": 1.0}]
                    }
                }
                await self._safe_request(payload)
            except Exception:
                pass

        asyncio.run_coroutine_threadsafe(_send(), self.event_loop)