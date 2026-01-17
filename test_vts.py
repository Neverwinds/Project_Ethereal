import asyncio
import pyvts
import time
import json

async def main():
    print("=== VTube Studio 嘴型控制测试 ===")
    
    # 1. 配置插件信息 (必须与 vts_adapter.py 一致)
    plugin_info = {
        "plugin_name": "Ethereal Core",
        "developer": "Master",
        "authentication_token_path": "./vts_token.txt"
    }
    
    vts = pyvts.vts(plugin_info=plugin_info)

    try:
        # 2. 连接与鉴权
        print("正在连接 VTS (端口 8001)...")
        await vts.connect()
        print("正在鉴权...")
        await vts.request_authenticate_token()
        await vts.request_authenticate()
        print("✅ 连接成功！")

        # 3. 暴力测试张嘴
        print("\n开始测试张嘴 (0 -> 1 -> 0)...")
        print("请盯着你的 VTube Studio 模型看！")
        
        for i in range(20):
            # 模拟一个波形：0 -> 1 -> 0
            if i < 10:
                val = i / 10.0
            else:
                val = (20 - i) / 10.0
            
            print(f"发送指令: MouthOpen = {val:.1f}")
            
            # [关键修复] 手动构造请求字典，绕过可能存在的 pyvts 版本兼容问题
            # 这是 VTube Studio API 的标准 JSON 格式
            payload = {
                "apiName": "VTubeStudioPublicAPI",
                "apiVersion": "1.0",
                "requestID": "MouthTest",
                "messageType": "InjectParameterDataRequest",
                "data": {
                    "faceFound": False, # 强制覆盖摄像头捕捉
                    "mode": "set",
                    "parameterValues": [
                        {
                            "id": "MouthOpen",
                            "value": val
                        }
                    ]
                }
            }
            
            await vts.request(payload)
            await asyncio.sleep(0.1) # 10FPS

        print("\n测试结束。")
        await vts.close()

    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        print("建议排查：")
        print("1. VTube Studio 是否开启？")
        print("2. 插件 API 是否开启 (端口 8001)？")
        print("3. 是否在 VTS 中点击了 'Allow'？")

if __name__ == "__main__":
    asyncio.run(main())