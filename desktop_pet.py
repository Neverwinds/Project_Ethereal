import sys
from PyQt5.QtCore import Qt, QEvent, QUrl
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView

# 配置：指向你的 Live2D 服务器地址
LIVE2D_URL = "http://127.0.0.1:8000/web/index.html"

class TransparentWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # 1. 窗口基础设置
        self.setWindowTitle("Project Ethereal Avatar")
        # [修改] 加大尺寸，让立绘显示更完整
        self.setGeometry(100, 100, 1000, 1600) 
        
        # 2. 关键：设置无边框 + 透明背景 + 顶层显示
        self.setWindowFlags(
            Qt.FramelessWindowHint |  # 无边框
            Qt.WindowStaysOnTopHint | # 总是置顶
            Qt.Tool                   # 不在任务栏显示图标
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 3. 创建浏览器视图
        self.webview = QWebEngineView()
        self.webview.page().setBackgroundColor(Qt.transparent)
        self.webview.load(QUrl(LIVE2D_URL))
        
        # [关键修复] 安装事件过滤器，拦截鼠标事件以支持拖拽
        self.webview.installEventFilter(self)
        # WebEngineView 内部还有一个子部件负责渲染，也需要拦截
        for child in self.webview.children():
            child.installEventFilter(self)
        
        self.setCentralWidget(self.webview)
        self.drag_pos = None

    # --- 核心修复：事件过滤器 ---
    def eventFilter(self, source, event):
        # 拦截鼠标按下
        if event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.LeftButton:
                # 记录按下时的相对位置
                self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()
                # 注意：这里我们不返回 True，而是让事件继续传递给网页
                # 这样网页里的点击交互（比如点身体触发动作）依然有效！
                return False

        # 拦截鼠标移动
        elif event.type() == QEvent.MouseMove:
            if event.buttons() == Qt.LeftButton and self.drag_pos:
                # 如果按住左键移动，则移动窗口
                self.move(event.globalPos() - self.drag_pos)
                return True # 消耗掉事件，避免网页选中文字

        # 拦截鼠标释放
        elif event.type() == QEvent.MouseButtonRelease:
            self.drag_pos = None
            return False

        return super().eventFilter(source, event)

if __name__ == "__main__":
    # 必须先启动 live2d_server.py
    app = QApplication(sys.argv)
    window = TransparentWindow()
    window.show()
    sys.exit(app.exec_())