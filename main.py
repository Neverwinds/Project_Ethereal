from gui import EtherealApp
import config

# 原来的命令行导入方式已废弃
# from agent import EtherealBot

def main():
    print("--- 正在启动 Project Ethereal GUI ---") 
    
    # 实例化并运行图形界面
    # 所有的逻辑现在由 gui.py 接管
    app = EtherealApp()
    
    # 这一步会阻塞，直到窗口关闭
    app.mainloop()

if __name__ == "__main__":
    main()