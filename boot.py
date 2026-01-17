import subprocess
import time
import sys
import os
import signal

def run_script(script_name):
    """使用当前环境的 Python 解释器启动子进程"""
    # sys.executable 确保我们使用的是当前 Conda 环境的 python.exe
    return subprocess.Popen([sys.executable, script_name], cwd=os.getcwd())

def main():
    print("==================================================")
    print("   PROJECT ETHEREAL - SYSTEM BOOT SEQUENCE")
    print("==================================================")

    processes = []

    try:
        # 1. 启动 Live2D 后端服务 (必须最先启动)
        print(">> [1/3] Starting Live2D Server...")
        p_server = run_script("live2d_server.py")
        processes.append(p_server)
        # 等待2秒，确保服务端口已就绪
        time.sleep(2) 

        # 2. 启动桌面立绘 (透明窗口)
        print(">> [2/3] Starting Desktop Avatar...")
        p_pet = run_script("desktop_pet.py")
        processes.append(p_pet)
        time.sleep(1)

        # 3. 启动主控制台 (GUI Dashboard)
        print(">> [3/3] Starting Main Terminal...")
        p_main = run_script("main.py")
        processes.append(p_main)

        print("\n>> SYSTEM ONLINE. 所有模块运行中...")
        print(">> 关闭主窗口 (Terminal) 即可自动退出所有程序。")

        # 4. 守护进程：监控主程序状态
        # 如果 main.py 关闭了，我们就要把其他两个杀掉
        while True:
            # 检查主程序是否还活着
            if p_main.poll() is not None:
                print("\n>> 主程序已退出。正在终止子系统...")
                break
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n>> 接收到中断信号...")

    finally:
        # 5. 优雅退出：清理所有子进程
        print(">> Cleaning up processes...")
        for p in processes:
            if p.poll() is None: # 如果进程还在运行
                p.terminate() # 尝试温和终止
                try:
                    p.wait(timeout=2) # 等待2秒
                except subprocess.TimeoutExpired:
                    p.kill() # 强行杀掉
        print(">> SHUTDOWN COMPLETE.")

if __name__ == "__main__":
    main()