import config
from vts_adapter import VTSAdapter

class FaceEngine:
    """
    Project Ethereal 面部表情引擎 (VTS 版)
    使用 ExpressionActivationRequest API 实现表情的互斥切换和衰减效果
    """
    def __init__(self):
        config.console.print("[System] Initializing VTube Studio Adapter...")
        self.adapter = VTSAdapter()
        self.enabled = True

        # [配置] 情感 -> VTS 表情名称
        # 系统会自动在 VTS 的表情列表中查找名称包含目标名称的表情
        # 注意: 这里的名称需要匹配 VTS 中的表情文件名 (不含 .exp3.json)
        self.EMOTION_MAP = {
            "happy": "Happy",
            "angry": "Angry",
            "annoyed": "Annoyed",
            "neutral": "Neutral",
            "thinking": "Thinking"
        }

        # 表情切换的淡入淡出时间 (秒), 范围 0-2
        self.fade_time = 0.5

    def set_expression(self, emotion, fade_time=None):
        """
        根据情感标签切换 VTS 表情 (互斥切换 - 自动关闭旧表情)

        Args:
            emotion: 情感标签 (如 "[Happy]", "sad" 等)
            fade_time: 表情切换的淡入淡出时间 (秒)，None 则使用默认值
        """
        if not self.adapter.connected:
            return

        # 1. 清洗情感标签
        clean_emo = emotion.replace("[", "").replace("]", "").lower()

        # 2. 查找映射的目标名称
        # 如果 map 中没有定义，就直接尝试用 clean_emo 去查找 (比如 "surprised")
        target_name = self.EMOTION_MAP.get(clean_emo, clean_emo)

        # 3. 使用 fade_time 参数或默认值
        if fade_time is None:
            fade_time = self.fade_time

        config.console.print(f"[Face] Requesting expression: {clean_emo} -> VTS Name: {target_name}")
        self.adapter.set_expression_by_name(target_name, fade_time)

    def set_mouth_open(self, value):
        if self.adapter.connected:
            self.adapter.set_mouth_open(value)