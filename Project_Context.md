Project Ethereal - Context & Architecture

Read Me First: This document outlines the architecture, state, and roadmap of Project Ethereal to assist AI agents in continuing development.

1. 项目简介

Project Ethereal 是一个本地优先、全感官具身智能 (Embodied AI) 的桌面数字生命系统（类 Neuro-sama 的 AI Vtuber）。核心运行环境为 RTX 5080，追求极致的低延迟与高情感密度。

2. 模块架构 (System Architecture)

当前系统采用 Python 微服务架构，各器官解耦，通过 HTTP/WebSocket 通讯。

模块 (Organ)

实现技术 (Tech Stack)

职责 (Responsibility)

通讯方式 (Protocol)

Soul (Main)

Python (main.py)

中枢神经。负责调度 GUI、LLM、TTS，维护记忆与情感状态。

内部函数调用 / Threading

Brain (LLM)

Ollama / DeepSeek

大脑。负责认知推理、生成文本。支持本地/云端双切。

HTTP POST (OpenAI SDK)

Mouth (TTS)

GPT-SoVITS

嘴巴。负责将文本转为高保真语音。

HTTP GET (API v2)

Face (Visual)

Live2D (Web)

脸。负责展示形象、表情动作、口型同步。

WebSocket (Port 8000)

GUI (Control)

CustomTkinter

控制台。提供聊天界面、Debug 面板、配置编辑器。

主进程运行

3. 关键文件映射 (File Map)

核心后端 (Backend)

main.py: 启动入口。负责拉起 GUI 和后台线程。

agent.py: 智能体核心类。封装了 think() (调用 LLM) 和 speak() (调用 TTS)，处理情感提取正则逻辑。

config.py: 全局配置中心。包含 API Key 读取、路径管理、安全审计 (Proxy Block)。

tts_engine.py: TTS 抽象层。负责清洗文本、自动唤醒 GPT-SoVITS 服务 (.bat)、播放音频。

face_engine.py: 面部控制器。负责向 WebSocket 发送 {"type": "expression", ...} 指令。

视觉前端 (Frontend/Visuals)

live2d_server.py: 视觉后端。基于 FastAPI，提供静态网页服务 + WebSocket 信令通道。

desktop_pet.py: 视觉容器。基于 PyQtWebEngine，创建一个背景透明、无边框、顶层显示的浏览器窗口，加载 Live2D 网页。

web/index.html: 视觉前端。使用 PixiJS v6 + Live2D Plugin v0.4.0 渲染 Hiyori 模型，接收 WebSocket 指令驱动口型和动作。

数据与配置 (Data)

character.json: 核心人设、世界观 (Lore)、Prompt 示例。

secrets.json: (Git Ignored) 存储敏感 API Key。

4. 避坑指南 (Caveats & Pitfalls)

网络代理 (Proxy): 代码中已硬编码 os.environ["NO_PROXY"] = "*"。这是为了防止 VPN 导致 requests 无法连接 127.0.0.1 报错。不要删除。

Live2D 版本依赖: web/index.html 必须严格使用 PixiJS v6.5.2 配合 pixi-live2d-display v0.4.0。升级到 v7 会导致 undefined 错误。

GPT-SoVITS 路径: config.py 中的 GPT_SOVITS_DIR 必须指向真实的解压路径，且路径中尽量不要包含中文。

Hiyori 动作: 免费版 Hiyori 模型的动作组映射比较混乱，目前通过 web/index.html 中的自动扫描逻辑 (allMotions) 进行调试。

线程阻塞: TTS 生成和 LLM 推理都是阻塞操作，必须在 gui.py 的子线程 (threading) 中运行，否则界面会卡死。

5. 当前进度 (Progress & Roadmap)

✅ 已完成 (Done)

[x] GUI: V4.0 三栏式仪表盘 (Chat/Settings/Debug)。

[x] Brain: 双脑切换 (Local Ollama / Cloud DeepSeek)，支持热重载 System Prompt。

[x] Mouth: 接入 GPT-SoVITS，支持自动服务唤醒。

[x] Face: 实现了 Python 到 Web Live2D 的 WebSocket 控制链路，支持透明桌宠显示。

[x] Debug: 实现了 Request Payload 和 Raw Response 的可视化监控。

🚧 下一步计划 (Next Steps)

Ears (听觉): 接入 Faster-Whisper，实现麦克风语音输入。

Autonomy (自主性): 在 agent.py 中实现心跳线程，让 AI 在空闲时主动发起对话。

Emotion Sidecar (情感旁路): 引入小模型 (DistilBERT) 并行判断情感，替代目前的正则提取方案，降低延迟。