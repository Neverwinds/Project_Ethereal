import config
from agent import EtherealBot  # [修正] 导入源改为 agent.py

def main():
    print("--- 正在启动 Project Ethereal ---") 
    
    # 实例化机器人 (核心逻辑在 agent.py 中运行)
    # 这会自动触发 agent.py 里的 __init__，进行安全审计和设备检测
    bot = EtherealBot()
    
    config.console.print("\n[dim]Type 'exit', 'quit' or 'bye' to leave.[/dim]")

    while True:
        try:
            # 获取用户输入
            user_input = config.console.input("\n[bold white]You > [/bold white]")
            
            if user_input.lower() in ["exit", "quit", "bye"]:
                # 退出前调用 terminate 清理显存
                bot.terminate()
                config.console.print("[yellow]Link severed.[/yellow]")
                break
            
            if not user_input.strip():
                continue

            # 1. 思考 (Think)
            reply = bot.think(user_input)
            
            # 2. 说话 (Speak)
            if reply:
                bot.speak(reply)

        except KeyboardInterrupt:
            # 即使强制中断，也尝试清理资源
            try:
                bot.terminate()
            except:
                pass
            config.console.print("\n[yellow]Shutting down link.[/yellow]")
            break

if __name__ == "__main__":
    main()