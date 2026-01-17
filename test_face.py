import requests
import time
import random
import os

# [关键修复] 强制禁用系统代理
# 防止 requests 库试图通过 VPN/加速器访问本地 localhost，导致 3213 端口报错
os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""
os.environ["ALL_PROXY"] = ""
os.environ["NO_PROXY"] = "*" 

# 指向 live2d_server.py 的控制接口
SERVER_URL = "http://127.0.0.1:8000/control"

def send_command(cmd_type, value):
    try:
        payload = {"type": cmd_type, "value": value}
        print(f"正在发送指令: {payload} ... ", end="")
        resp = requests.post(SERVER_URL, json=payload, timeout=1)
        if resp.status_code == 200:
            print("✅ 成功")
        else:
            print(f"❌ 失败 ({resp.status_code})")
    except Exception as e:
        print(f"❌ 连接错误: {e}")
        print("请检查 live2d_server.py 是否正在运行！")

print("="*40)
print("   Project Ethereal - Live2D 联动测试器")
print("="*40)
print("请确保 live2d_server.py 和 网页/桌面挂件 均已打开。\n")

# 1. 表情测试
emotions = ["happy", "angry", "neutral", "annoyed"]
print("\n--- 阶段一：表情测试 (每3秒换一个) ---")
for emo in emotions:
    send_command("expression", emo)
    print(f"   观察模型是否有动作变化? (当前: {emo})")
    time.sleep(3)

# 2. 口型测试
print("\n--- 阶段二：口型测试 (模拟说话 5秒) ---")
print("   观察模型嘴巴是否开合?")
start_time = time.time()
while time.time() - start_time < 5:
    # 随机生成 0.0 ~ 1.0 的张嘴幅度，模拟语音振幅
    volume = random.uniform(0.0, 1.0) 
    send_command("lipsync", volume)
    time.sleep(0.1) # 100ms 发送一次

# 归零
send_command("lipsync", 0.0)
print("\n--- 测试结束 ---")