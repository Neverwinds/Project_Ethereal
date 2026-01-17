import subprocess
import time
import sys
import os
import signal

def run_script(script_name):
    """使用当前环境的 Python 解释器启动子进程"""
    return subprocess.Popen([sys.executable, script_name], cwd=os.getcwd())

def main():
    print("==================================================")
    print("   PROJECT ETHEREAL - SYSTEM BOOT SEQUENCE")
    print("   (VTube Studio Edition)")
    print("==================================================")

    processes = []

    try:
        # [已移除] live2d_server.py (由 VTube Studio 接管)
        # [已移除] desktop_pet.py (由 VTube Studio 接管)

        # 1. 启动主控制台 (GUI Dashboard)
        # 注意：GPT-SoVITS 会由 main.py 内部的 tts_engine 自动唤醒，无需在此启动
        print(">> [1/1] Starting Main Terminal...")
        p_main = run_script("main.py")
        processes.append(p_main)

        print("\n>> SYSTEM ONLINE. 等待连接 VTube Studio...")
        print(">> 请确保 VTube Studio 已打开并开启了 API (端口 8001)。")
        print(">> 关闭主窗口即可退出。")

        # 2. 守护进程：监控主程序状态
        while True:
            # 检查主程序是否还活着
            if p_main.poll() is not None:
                print("\n>> 主程序已退出。系统关闭。")
                break
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n>> 接收到中断信号...")

    finally:
        # 3. 优雅退出：清理所有子进程
        print(">> Cleaning up processes...")
        for p in processes:
            if p.poll() is None: # 如果进程还在运行
                p.terminate() 
                try:
                    p.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    p.kill()
        print(">> SHUTDOWN COMPLETE.")

if __name__ == "__main__":
    main()