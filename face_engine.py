import config
from vts_adapter import VTSAdapter

class FaceEngine:
    """
    Project Ethereal 面部表情引擎 (VTS 版)
    负责将大脑的指令中转给 VTube Studio
    """
    def __init__(self):
        config.console.print("[System] Initializing VTube Studio Adapter...")
        self.adapter = VTSAdapter()
        # 默认启用，具体连没连上由 adapter 内部状态决定
        self.enabled = True 

    def set_expression(self, emotion):
        """
        设置表情
        """
        if self.adapter.connected:
            self.adapter.set_expression(emotion)

    def set_mouth_open(self, value):
        """
        设置嘴巴张合度 (0.0 - 1.0)
        接收来自 TTSEngine 的实时振幅数据
        """
        if self.adapter.connected:
            self.adapter.set_mouth_open(value)