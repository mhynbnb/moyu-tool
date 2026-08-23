import sys
import os
from PyQt6.QtWidgets import (QApplication, QCheckBox, QColorDialog, QMainWindow, QMenu, QSlider, QSystemTrayIcon, 
                              QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
                             QScrollArea, QFrame, QComboBox)
from PyQt6.QtCore import  QSize,  Qt
from PyQt6.QtGui import QAction, QColor, QIcon, QPixmap
import json
import svg
import theme
from svg import svg_to_icon
from reader import EpubReader, RSSWindow


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Modern Library")

        # 加载设置
        if os.path.exists("configs/setting.json"):
            with open("configs/setting.json", 'r', encoding='utf-8') as f:
                self.setting_data = json.load(f)
        else:
            self.setting_data = {}
        self.resize(560, 720)
        self.setMinimumSize(430, 560)  # 响应式：保证小窗口 / 小屏下布局不破碎
        self.setWindowIcon(QIcon(svg_to_icon(svg.fishIcon, size=QSize(20, 20), color=theme.COLORS["primary"])))
        self.init_ui()
        self.refresh_books()
        
    def init_ui(self):
        self.tabs = QTabWidget()  # 标签页样式（居中、圆角胶囊选中态）由全局样式表统一提供
        
        # --- 书架标签页 ---
        self.bookshelf_tab = QWidget()
        self.bookshelf_layout = QVBoxLayout()
        self.bookshelf_layout.setContentsMargins(16, 16, 16, 16)  # 统一页边距
        self.bookshelf_layout.setSpacing(12)
        
        top_bar = QHBoxLayout()
        top_bar.setSpacing(12)
        title_label = QLabel("📚 我的藏书")
        title_label.setObjectName("PageTitle")
        
        self.refresh_btn = QPushButton("🔄 刷新列表")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.refresh_books)
        
        top_bar.addWidget(title_label)
        top_bar.addStretch()
        top_bar.addWidget(self.refresh_btn)
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.list_layout.setSpacing(8)                      # 卡片间距统一 8px
        self.list_layout.setContentsMargins(4, 4, 4, 8)
        self.scroll.setWidget(self.list_container)

        self.bookshelf_layout.addLayout(top_bar)
        self.bookshelf_layout.addWidget(self.scroll)
        self.bookshelf_tab.setLayout(self.bookshelf_layout)

        # --- 设置标签页 ---
        self.settings_tab = QWidget()
        self.settings_main_layout = QVBoxLayout(self.settings_tab)
        self.settings_main_layout.setContentsMargins(16, 16, 16, 16)
        self.settings_main_layout.setSpacing(12)
        self.settings_main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # 界面外观组（卡片）
        self.appearance_group = QFrame()
        self.appearance_group.setObjectName("Card")
        self.appearance_layout = QVBoxLayout(self.appearance_group)
        self.appearance_layout.setContentsMargins(16, 14, 16, 16)
        self.appearance_layout.setSpacing(14)
        theme.apply_shadow(self.appearance_group)
        
        appearance_title = QLabel("🎨 界面外观")
        appearance_title.setObjectName("CardTitle")
        self.appearance_layout.addWidget(appearance_title)

        # 透明度设置
        opacity_layout = QHBoxLayout()
        opacity_layout.setSpacing(12)
        opacity_label = QLabel("背景透明度")

        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(1, 100)
        self.opacity_slider.setValue(int(self.setting_data.get("opacity", 1.0) * 100))
        self.opacity_slider.valueChanged.connect(self.update_opacity_setting) 

        opacity_layout.addWidget(opacity_label)
        opacity_layout.addWidget(self.opacity_slider)
        self.appearance_layout.addLayout(opacity_layout)

        # 开关设置 关闭阅读窗口后打开主界面
        self.topmost_layout = QHBoxLayout()
        self.topmost_layout.setSpacing(12)
        self.topmost_label = QLabel("关闭阅读窗口后打开主界面")
        
        self.topmost_check = QCheckBox()
        is_topmost = self.setting_data.get("topmost", True)# 设置初始状态（从配置中读取，默认为 True）
        self.topmost_check.setChecked(is_topmost)
        self.topmost_check.stateChanged.connect(self.update_topmost_setting)
        
        self.topmost_layout.addWidget(self.topmost_label)
        self.topmost_layout.addStretch() 
        self.topmost_layout.addWidget(self.topmost_check)
        self.appearance_layout.addLayout(self.topmost_layout)


        # 文本阅读组（卡片）
        text_group = QFrame()
        text_group.setObjectName("Card")
        text_layout = QVBoxLayout(text_group)
        text_layout.setContentsMargins(16, 14, 16, 16)
        text_layout.setSpacing(14)
        theme.apply_shadow(text_group)
        
        text_title = QLabel("📖 阅读偏好")
        text_title.setObjectName("CardTitle")
        text_layout.addWidget(text_title)

        # 字体选择
        font_layout = QHBoxLayout()
        font_layout.setSpacing(12)
        font_label = QLabel("字体")
        self.font_combo = QComboBox()
        self.font_combo.addItems(["SimHei", "SimSun", "KaiTi"])
        self.font_combo.setCurrentText(self.setting_data.get("font", "SimHei"))
        self.font_combo.currentTextChanged.connect(self.update_font_setting)
        font_layout.addWidget(font_label)
        font_layout.addWidget(self.font_combo)
        text_layout.addLayout(font_layout)

        # 字号设置
        fontsize_layout = QHBoxLayout()
        fontsize_layout.setSpacing(12)
        fontsize_label = QLabel("字号")
        # --- 用于显示具体数值的标签 ---
        self.fontsize_value_label = QLabel(str(self.setting_data.get("font_size", 16)))
        self.fontsize_value_label.setObjectName("Muted")
        self.fontsize_value_label.setFixedWidth(24) # 固定宽度防止数值变动时布局抖动
        self.fontsize_slider = QSlider(Qt.Orientation.Horizontal)
        self.fontsize_slider.setRange(10, 30)
        self.fontsize_slider.setValue(self.setting_data.get("font_size", 16))
        # 绑定信号
        self.fontsize_slider.valueChanged.connect(self.update_font_size_setting)
        # 按顺序添加控件
        fontsize_layout.addWidget(fontsize_label)
        fontsize_layout.addWidget(self.fontsize_slider)
        fontsize_layout.addWidget(self.fontsize_value_label) # 数值显示在滑动条右侧
        text_layout.addLayout(fontsize_layout)

        # --- 字体颜色设置布局 ---
        fontcolor_layout = QHBoxLayout()
        fontcolor_layout.setSpacing(12)
        fontcolor_label = QLabel("颜色")
        # 创建一个显示当前颜色的方块按钮
        self.color_button = QPushButton()
        self.color_button.setFixedSize(44, 26)
        self.color_button.setCursor(Qt.CursorShape.PointingHandCursor)
        # 初始化按钮背景色为当前字体颜色
        self.color_button.setStyleSheet(
            f"background-color: {self.setting_data.get('font_color', '#000')};"
            f"border: 1px solid {theme.COLORS['border_strong']}; border-radius: 6px;"
        )
        self.color_button.clicked.connect(self.open_color_dialog)

        fontcolor_layout.addWidget(fontcolor_label)
        fontcolor_layout.addStretch() # 让标签和按钮分开
        fontcolor_layout.addWidget(self.color_button)
        text_layout.addLayout(fontcolor_layout)


        # 3. 快捷键组（占位，卡片 + 辅助色徽标）
        hotkey_group = QFrame()
        hotkey_group.setObjectName("Card")
        theme.apply_shadow(hotkey_group)
        hotkey_layout = QVBoxLayout(hotkey_group)
        hotkey_layout.setContentsMargins(16, 14, 16, 14)
        hotkey_layout.setSpacing(8)

        hotkey_header = QHBoxLayout()
        hotkey_title = QLabel("⌨️ 快捷键设置")
        hotkey_title.setObjectName("CardTitle")
        hotkey_badge = QLabel("敬请期待")
        hotkey_badge.setObjectName("Badge")
        hotkey_header.addWidget(hotkey_title)
        hotkey_header.addSpacing(8)
        hotkey_header.addWidget(hotkey_badge)
        hotkey_header.addStretch()
        hotkey_layout.addLayout(hotkey_header)

        # 将所有组添加到主布局
        self.settings_main_layout.addWidget(self.appearance_group)
        self.settings_main_layout.addWidget(text_group)
        self.settings_main_layout.addWidget(hotkey_group)
        self.settings_main_layout.addStretch()

        # 将标签页添加到主控件
        self.tabs.addTab(self.bookshelf_tab, "书架")
        self.tabs.addTab(self.settings_tab, "设置")
        self.setCentralWidget(self.tabs)

        # 创建托盘图标和菜单（菜单样式由全局样式表统一提供）
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(svg_to_icon(svg.fishIcon, size=QSize(20, 20), color=theme.COLORS["primary"]))) # 请确保路径下有图标文件，否则托盘可能不显示
        self.tray_menu = QMenu()
        
        self.show_action = QAction("显示主界面", self)# 添加“显示”动作
        self.show_action.triggered.connect(self.show)   
        self.tray_menu.addAction(self.show_action)

        
        self.exit_action = QAction("退出程序", self)# 添加退出动作
        self.exit_action.triggered.connect(QApplication.instance().quit)
        self.tray_menu.addAction(self.exit_action)

        self.tray_icon.setContextMenu(self.tray_menu)# 将菜单设置给托盘图标
        self.tray_icon.show()

        self.tray_icon.activated.connect(self.on_tray_icon_activated)# 连接激活信号以支持双击
     

    def open_color_dialog(self):
        """弹出颜色选择器"""
        # 初始颜色设为当前颜色
        initial_color = QColor('#000000')  # 默认黑色
        color = QColorDialog.getColor(initial_color, self, "选择字体颜色")
        if color.isValid():
            # 将 QColor 对象转换为十六进制字符串 (例如 #ffffff)
            self.font_color = color.name()
            # 1. 更新按钮本身的颜色预览
            self.color_button.setStyleSheet(
                f"background-color: {self.font_color};"
                f"border: 1px solid {theme.COLORS['border_strong']}; border-radius: 6px;"
            )
            self.setting_data["font_color"] = self.font_color
            with open("configs/setting.json", 'w', encoding='utf-8') as f:
                json.dump(self.setting_data, f)
    
    def update_font_size_setting(self, value):
        """滑动条数值改变时的回调"""
        # 1. 更新标签显示
        self.fontsize_value_label.setText(str(value))
        self.setting_data["font_size"] = value
        with open("configs/setting.json", 'w', encoding='utf-8') as f:
            json.dump(self.setting_data, f)
    def update_topmost_setting(self, state):
        """关闭阅读窗口后是否打开主界面设置更新"""
        self.setting_data["topmost"] = self.topmost_check.isChecked()
        with open("configs/setting.json", 'w', encoding='utf-8') as f:
            json.dump(self.setting_data, f)
    
    def on_tray_icon_activated(self, reason):
        """处理托盘双击事件"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()
    def update_opacity_setting(self, value):
        """透明度设置更新"""
        self.setting_data["opacity"] = value / 100.0
        with open("configs/setting.json", 'w', encoding='utf-8') as f:
            json.dump(self.setting_data, f)

    def update_font_setting(self, font_name):
        """字体设置更新"""
        self.setting_data["font"] = font_name
        with open("configs/setting.json", 'w', encoding='utf-8') as f:
            json.dump(self.setting_data, f)
    
    def refresh_books(self):
        """刷新书架中的书籍列表"""
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        book_dir = "books"
        if not os.path.exists(book_dir): os.makedirs(book_dir)
        extensions = ('.txt', '.epub', '.mobi', '.azw3')
        files = [f for f in os.listdir(book_dir) if f.lower().endswith(extensions)]
        
        for file_name in files:
            self.add_book_item(file_name)
        self.add_book_item("知乎日报", rss=True)
        self.add_book_item("IT之家", rss=True)
        self.add_book_item("少数派", rss=True)
        self.add_book_item("爱范儿", rss=True)
    def add_book_item(self, file_name,rss=False):
        if not rss:
            item_frame = QFrame()
            item_frame.setObjectName("BookItem")  # 卡片样式（含悬停态）由全局样式表提供
            item_frame.setCursor(Qt.CursorShape.PointingHandCursor)
            
            item_layout = QHBoxLayout(item_frame)
            item_layout.setSpacing(12)
            
            icon = "📄"
            if file_name.endswith('.txt'): icon = "📝"
            elif file_name.endswith(('.epub', '.mobi', '.azw3')): icon = "📖"
            else: icon = "📄"
                
            name_label = QLabel(f"{icon} {file_name}")
            name_label.setObjectName("BookName")
            
            # 获取该书的进度
            progress_text = "未开始"
            full_path = os.path.join("books", file_name)
            
            if os.path.exists("configs/reader_config.json"):
                try:
                    with open("configs/reader_config.json", 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                        chapter_index = config_data.get(full_path)# 检查 JSON 中是否存在该文件的进度记录
                        if isinstance(chapter_index, int): # 确保索引是整数
                            pass
                        else:
                            chapter_index = chapter_index[0]
                        if chapter_index is not None:
                            progress_text = f"上次读至：第 {chapter_index + 1} 章"
                except:
                    pass

            progress_label = QLabel(progress_text)
            progress_label.setObjectName("Muted")

            read_btn = QPushButton("阅读")# 创建阅读按钮
            read_btn.setProperty('class', 'primary') # 主操作按钮（实心主色）
            read_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            read_btn.setFixedWidth(76)
            full_path = os.path.join("books", file_name)
            read_btn.clicked.connect(lambda ch, p=full_path: self.open_reader(p))
            
            item_layout.addWidget(name_label)
            item_layout.addStretch()
            item_layout.addWidget(progress_label) # 在按钮左侧插入进度
            item_layout.addWidget(read_btn)
            
            self.list_layout.addWidget(item_frame)
        else:
            item_frame = QFrame()
            item_frame.setObjectName("BookItem")
            item_frame.setCursor(Qt.CursorShape.PointingHandCursor)
            item_layout = QHBoxLayout(item_frame)
            item_layout.setSpacing(12)

            # 创建一个容器，用于放置图标和文字
            icon_text_container = QWidget()
            layout = QHBoxLayout(icon_text_container)
            layout.setContentsMargins(5, 0, 5, 0) # 设置容器的内边距
            layout.setSpacing(8) # 设置图标和文字之间的间距

            
            icon_label = QLabel()# 创建图标 Label
            if file_name == "知乎日报":
                icon_label.setPixmap(svg_to_icon(svg.zhihuIcon, size=QSize(18, 18)).pixmap(QSize(24, 24)))
                text_label = QLabel(" 知乎日报")
            elif file_name == "IT之家":
                icon_label.setPixmap(svg_to_icon(svg.ithomeIcon, size=QSize(18, 18)).pixmap(QSize(24, 24)))
                text_label = QLabel(" IT之家")
            elif file_name == "少数派":
                icon_label.setPixmap(svg_to_icon(svg.sspaiIcon, size=QSize(18, 18)).pixmap(QSize(24, 24)))
                text_label = QLabel(" 少数派")
            elif file_name == "爱范儿":
                icon_label.setPixmap(svg_to_icon(svg.ifanrIcon, size=QSize(18, 18)).pixmap(QSize(24, 24)))
                text_label = QLabel(" 爱范儿")
            text_label.setObjectName("BookName")
            layout.addWidget(icon_label)
            layout.addWidget(text_label)
            layout.addStretch()
                
            read_btn = QPushButton("阅读")              # 创建阅读按钮
            read_btn.setProperty('class', 'primary')    # 主操作按钮（实心主色）
            read_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            read_btn.setFixedWidth(76)
            if file_name == "知乎日报":
                read_btn.clicked.connect(lambda: self.open_rss_window("zhihu_daily"))
            elif file_name == "IT之家":
                read_btn.clicked.connect(lambda: self.open_rss_window("ithome"))
            elif file_name == "少数派":
                read_btn.clicked.connect(lambda: self.open_rss_window("sspai"))
            elif file_name == "爱范儿":
                read_btn.clicked.connect(lambda: self.open_rss_window("ifanr"))

            item_layout.addWidget(icon_text_container)
            item_layout.addStretch()
            item_layout.addWidget(read_btn)
            
            self.list_layout.addWidget(item_frame)
    def open_reader(self, path):
        self.reader = EpubReader(path) 
        self.reader.setParent(self, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.reader.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)# 设置关闭时自动销毁对象，这样 destroyed 信号才有效
        self.hide()
        if self.setting_data["topmost"]:
            self.reader.destroyed.connect(self.show)# 连接 destroyed 信号，当阅读器窗口关闭时显示主界面
        else:
            self.reader.destroyed.disconnect()
        self.reader.show()
    def open_rss_window(self, rssname):
        self.rss_win = RSSWindow(rssname) 
        self.rss_win.setParent(self, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.rss_win.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)# 设置关闭时自动销毁对象，这样 destroyed 信号才有效
        self.hide()
        if self.setting_data["topmost"]:
            self.rss_win.destroyed.connect(self.show)# 连接 destroyed 信号，当阅读器窗口关闭时显示主界面
        else:
            pass
        self.rss_win.show()

        
if __name__ == "__main__":
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("my_unique_reading_tool_v1")
    app = QApplication(sys.argv)
    theme.set_app_font(app)                 # 统一 UI 字体（含回退链）
    app.setStyleSheet(theme.build_stylesheet())  # 应用现代化全局样式（替代 qt_material）
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
