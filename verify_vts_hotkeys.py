import asyncio
import pyvts
import config

# 模拟 VTSAdapter 的查找逻辑
class SimpleAdapter:
    def __init__(self):
        self.hotkey_cache = {}
        self.plugin_info = {
            "plugin_name": "Ethereal Core",
            "developer": "Master",
            "authentication_token_path": "./vts_token.txt"
        }
        self.vts = pyvts.vts(plugin_info=self.plugin_info)

    async def connect_and_fetch(self):
        try:
            print("正在连接 VTube Studio...")
            await self.vts.connect()
            await self.vts.request_authenticate_token()
            await self.vts.request_authenticate()
            print("✅ 连接成功")
            
            print("正在获取热键列表...")
            response = await self.vts.request({
                "apiName": "VTubeStudioPublicAPI",
                "apiVersion": "1.0",
                "requestID": "GetHotkeys",
                "messageType": "HotkeysInCurrentModelRequest"
            })
            
            if "data" in response and "availableHotkeys" in response["data"]:
                hotkeys = response["data"]["availableHotkeys"]
                print("\n--- VTS 当前模型热键列表 ---")
                print(f"{'Name':<30} | {'ID'}")
                print("-" * 60)
                for hk in hotkeys:
                    name = hk.get("name", "Unknown")
                    hk_id = hk.get("hotkeyID")
                    self.hotkey_cache[name] = hk_id
                    print(f"{name:<30} | {hk_id}")
                print("-" * 60)
            else:
                print("❌ 未找到热键，请检查模型是否配置了热键。")
                
        except Exception as e:
            print(f"❌ 连接或获取失败: {e}")

    def find_hotkey(self, name_query):
        print(f"\n测试查找: '{name_query}'")
        
        # 1. 精确匹配
        if name_query in self.hotkey_cache:
            return self.hotkey_cache[name_query]
        
        # 2. 不区分大小写匹配
        name_lower = name_query.lower()
        for name, hk_id in self.hotkey_cache.items():
            if name.lower() == name_lower:
                return hk_id
                
        # 3. 包含匹配
        for name, hk_id in self.hotkey_cache.items():
            if name_lower in name.lower():
                return hk_id
                
        return None

async def main():
    adapter = SimpleAdapter()
    await adapter.connect_and_fetch()
    
    if not adapter.hotkey_cache:
        return

    # 测试几个标准表情
    test_emotions = ["Happy", "Angry", "Sad", "Neutral"]
    
    print("\n--- 模拟 FaceEngine 查找测试 ---")
    for emo in test_emotions:
        hk_id = adapter.find_hotkey(emo)
        if hk_id:
            print(f"✔ 找到 '{emo}' -> ID: {hk_id}")
            # Uncomment to actually trigger
            # await adapter.vts.request({...}) 
        else:
            print(f"❌ 未找到 '{emo}' (请在 VTS 中将热键命名为包含 '{emo}' 的名称)")

    await adapter.vts.close()

if __name__ == "__main__":
    asyncio.run(main())
