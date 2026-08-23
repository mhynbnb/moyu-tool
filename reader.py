# from asyncio.log import logger
import os
import re
from PyQt6.QtWidgets import (QApplication, QListWidget, QMainWindow, QMenu, QStackedWidget, QSystemTrayIcon, QVBoxLayout, QWidget, QHBoxLayout, QPushButton, QLabel, 
                             QFrame,QComboBox,QTextBrowser)
from PyQt6.QtCore import QEvent, QPoint, QSize, QThread, QTimer, QUrl, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QCursor, QIcon
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import json
import svg
import theme
from svg import svg_to_icon
import chardet  # 新增：用于检测 txt 编码
import mobi
import traceback
import feedparser
import logging

# 在类的 __init__ 之前配置
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class EpubReader(QMainWindow):
    def __init__(self, file_path):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)# 设置窗口背景透明
        
        self.setWindowFlags(
            self.windowFlags()  
            |Qt.WindowType.WindowStaysOnTopHint  # 窗口总在最前
            |Qt.WindowType.FramelessWindowHint  # 无边框
        )
        self.setMouseTracking(True)
        self.show_hide_window = True # 控制窗口显示隐藏的变量
        self.keep_visible = True # 控制窗口保持可见的变量
        self._drag_pos = QPoint()# 用于记录拖动时的鼠标位置偏移
        self.file_path = file_path# 电子书路径
        self.config_path = "configs/reader_config.json"# 记录进度文件的路径
        self.setting_path = "configs/setting.json"# 记录设置文件的路径
        self._padding = 5  # 鼠标距离边缘多少像素时触发缩放
        # 加载电子书
        # self.book = epub.read_epub(file_path)
        self.chapters = [] # 保存章节信息
        self.current_chapter_index = 0
        self.font_size = 18 # 默认初始字体
        self.font_color = "#000"
        self.resize(400, 500)
        
        self.parse_content()
        self.load_saved_progress() # 读取上次进度
        self.init_ui()# 初始化界面
        self.load_chapter(self.current_chapter_index,self.current_chapter_location)# 加载章节

        self.check_timer = QTimer(self)
        self.check_timer.timeout.connect(self.monitor_mouse)
        self.check_timer.start(100)  # 每 100 毫秒检测一次

        self._is_resizing = False
        self._is_dragging = False # 新增：拖动状态锁
        
    def parse_content(self):
        """统一解析逻辑，根据后缀名分发"""
        ext = os.path.splitext(self.file_path)[1].lower()
        
        # 1. 处理 EPUB
        if ext == '.epub':
            self.book = epub.read_epub(self.file_path)
            items = list(self.book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
            for item in items:
                soup = BeautifulSoup(item.get_content(), 'html.parser')
                title = soup.find(['h1', 'h2', 'title'])
                title_text = title.get_text() if title else soup.get_text()[:20].strip() + "..."
                if title_text.strip():
                    self.chapters.append({
                        "title": title_text,
                        "content": item.get_content().decode('utf-8')
                    })

        # 2. 处理 MOBI
        elif ext in ['.mobi', '.azw3']:
            try:
                tempdir, html_file = mobi.extract(self.file_path)# 提取临时文件

                with open(html_file, 'rb') as f: # 读取并检测编码
                    raw_data = f.read()
                    res = chardet.detect(raw_data)
                    encoding = res['encoding'] if res['encoding'] else 'utf-8'
                
                raw_content = raw_data.decode(encoding, errors='ignore')
                soup = BeautifulSoup(raw_content, 'html.parser')
                
                
                for img in soup.find_all(['img', 'image', 'svg', 'figure']):# 去除图片
                    img.decompose()

                # 自动分章节逻辑
                content_source = soup.find('body') if soup.find('body') else soup
                elements = content_source.find_all(['h1', 'h2', 'h3', 'p', 'div'])
                
                current_chapter_title = os.path.basename(self.file_path)
                current_chapter_html = ""
                
                # 章节匹配正则
                chapter_regex = r'^\s*第[一二三四五六七八九十百千万零\d]+[章节回卷集部].*'

                for el in elements:
                    text = el.get_text().strip()
                    if not text: continue

                    # --- 多维度判断是否为标题 ---
                    is_chapter_head = False
                    
                    # 维度A：标准的标题标签
                    if el.name in ['h1', 'h2']:
                        is_chapter_head = True
                    
                    # 维度B： (居中 + 加粗)
                    elif el.name == 'p' and (el.get('align') == 'center' or el.find('b') or el.find('strong')):
                        # 补充判断：标题通常不会太长
                        if len(text) < 40:
                            is_chapter_head = True
                    
                    # 维度C：文本正则匹配 (第x章...)
                    elif re.match(chapter_regex, text):
                        if len(text) < 50:
                            is_chapter_head = True

                    # --- 执行切分 ---
                    if is_chapter_head:
                        # 保存当前累积的内容作为上一章
                        if current_chapter_html.strip():
                            self.chapters.append({
                                "title": current_chapter_title,
                                "content": f"<html><body>{current_chapter_html}</body></html>"
                            })
                        
                        # 重置新章节信息
                        current_chapter_title = text
                        current_chapter_html = f"<h1>{text}</h1>" # 统一转为 h1 以便样式生效
                    else:
                        # 累加正文
                        # 如果有 h3 之类的子标题但没触发切分，也保留结构
                        if el.name in ['h1', 'h2', 'h3']:
                            current_chapter_html += f"<h1>{text}</h1>"
                        else:
                            current_chapter_html += f"<p>{text}</p>"

                # 保存最后一章
                if current_chapter_html.strip():
                    self.chapters.append({
                        "title": current_chapter_title,
                        "content": f"<html><body>{current_chapter_html}</body></html>"
                    })

                # 保底处理
                if not self.chapters:
                    self.chapters.append({
                        "title": os.path.basename(self.file_path),
                        "content": f"<html><body><p>{content_source.get_text()}</p></body></html>"
                    })

                print(f"Mobi解析完成，识别到 {len(self.chapters)} 个章节")

            except Exception as e:
                traceback.print_exc() # 打印完整错误堆栈
                self.chapters.append({"title": "解析失败", "content": f"Kindle文件读取错误: {e}"})
        
        # 处理 txt
        elif ext == '.txt':
            try:
                with open(self.file_path, 'rb') as f:
                    raw_data = f.read()
                    res = chardet.detect(raw_data)
                    encoding = res['encoding'] if res['encoding'] else 'utf-8'
                
                text_content = raw_data.decode(encoding, errors='ignore')
                
                # 1. 章节匹配正则
                chapter_pattern = r'(^\s*(第[一二三四五六七八九十百千万零\d]+[章节回卷集部]).*)|(^\s*(前言|序言|楔子|后记|番外).*)'
                matches = list(re.finditer(chapter_pattern, text_content, re.MULTILINE))
                
                # 2. 模拟生效 content 的构造函数
                def build_standard_html(title, body_text):
                    lines = body_text.split('\n')
                    p_tags = ""
                    for line in lines:
                        content = line.strip()
                        if content:
                            p_tags += f'<p class="bodycontent">{content}</p>\n'
                        else:
                            pass
                    
                    # 构建完整的 HTML 骨架
                    full_html = f"""
                    <html>
                    <head></head>
                    <body>
                        <h2 class="chaptercaption1">{title}</h2>
                        {p_tags}
                    </body>
                    </html>
                    """
                    return full_html

                # 3. 开始切分并填充 chapters
                if not matches:
                    self.chapters.append({
                        "title": os.path.basename(self.file_path),
                        "content": build_standard_html("正文", text_content)
                    })
                else:
                    for i in range(len(matches)):
                        title = matches[i].group().strip()
                        start_pos = matches[i].start()
                        end_pos = matches[i+1].start() if i + 1 < len(matches) else len(text_content)
                        chapter_body = text_content[start_pos:end_pos]
                        
                        self.chapters.append({
                            "title": title,
                            "content": build_standard_html(title, chapter_body)
                        })

                # 4. 处理卷首简介
                if matches and matches[0].start() > 0:
                    intro = text_content[:matches[0].start()].strip()
                    if intro:
                        self.chapters.insert(0, {
                            "title": "引言",
                            "content": build_standard_html("引言", intro)
                        })
            except Exception as e:
                self.chapters.append({"title": "解析失败", "content": f"TXT读取错误: {e}"})

    def init_ui(self):
        # 主容器
        self.container = QWidget()
        self.setCentralWidget(self.container)# 设置容器为主窗口的中央组件
        self.container.setStyleSheet("background: transparent;")# 确保容器背景透明
        
        # 正文显示层 (铺满全屏)
        self.viewer = QTextBrowser(self.container)
        self.viewer.setGeometry(0, 0, self.width(), self.height())# 确保正文初始大小
        self.viewer.setFrameShape(QFrame.Shape.NoFrame)# 去掉边框
        self.viewer.setAutoFillBackground(False)# 不自动填充背景，保持透明
        self.viewer.setStyleSheet(f"""QTextBrowser {{background:rgba(0, 0, 0, {self.background_opacity}); border:none;}}""")# 确保 QTextBrowser 背景透明
        self.viewer.viewport().setStyleSheet("background-color: transparent;")# 确保 viewport 也透明        
        self.viewer.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)# 隐藏滚动条
        self.viewer.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)# 隐藏滚动条
        self.viewer.viewport().installEventFilter(self)# 安装事件过滤器，监听对正文的点击
        self.viewer.setMouseTracking(True)# 开启鼠标追踪
        self.viewer.viewport().setMouseTracking(True)# 开启 viewport 的鼠标追踪

        # 浮动工具栏层 (平时隐藏) —— 深色玻璃拟态样式统一由 theme 提供
        self.toolbar = QFrame(self.container)
        self.toolbar.setObjectName("FloatingToolbar")
        self.toolbar.setStyleSheet(theme.toolbar_qss())
        self.toolbar.setFixedHeight(40)#固定尺寸
        self.toolbar.hide() # 初始隐藏
        tool_layout = QHBoxLayout(self.toolbar)# 工具栏内部布局
        tool_layout.setContentsMargins(8, 6, 8, 6)
        tool_layout.setSpacing(4)

        # 章节跳转下拉框
        self.chapter_selector = QComboBox()
        for ch in self.chapters:
            self.chapter_selector.addItem(ch["title"])
        self.chapter_selector.currentIndexChanged.connect(self.load_chapter)# 绑定章节切换事件
        self.chapter_selector.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)# 根据内容调整宽度
        tool_layout.addWidget(self.chapter_selector)
        tool_layout.addStretch()# 添加弹性空间，使后续按钮靠右
        
        self.btnFontColorWhite = QPushButton("")
        fontwhite_icon = svg_to_icon(svg.fontcolorBtn, size=QSize(20, 20), color="#fff")
        self.btnFontColorWhite.setIcon(fontwhite_icon)
        self.btnFontColorWhite.setIconSize(QSize(20, 20))

        self.btnFontColorBlack = QPushButton("")
        fontblack_icon = svg_to_icon(svg.fontcolorBtn, size=QSize(20, 20), color="#000")
        self.btnFontColorBlack.setIcon(fontblack_icon)
        self.btnFontColorBlack.setIconSize(QSize(20, 20))

        self.btnFontColorWhite.clicked.connect(lambda: self.set_color_font('#fff'))
        self.btnFontColorBlack.clicked.connect(lambda: self.set_color_font('#000'))

        # 字体调节按钮
        self.btn_font_toggle = QPushButton("")
        fontsize_icon = svg_to_icon(svg.fontsizeBtn, size=QSize(20, 20), color=theme.COLORS["glass_text"])
        self.btn_font_toggle.setIcon(fontsize_icon)
        self.btn_font_toggle.setIconSize(QSize(20, 20))
        self.btn_font_toggle.setToolTip("左键增大 A+ / 右键减小 A-")
        self.btn_font_toggle.installEventFilter(self)


        # 置顶按钮
        self.btnOnTop = QPushButton("")
        self.btnOnTop.setToolTip("点击置顶")
        top_icon = svg_to_icon(svg.topBtn, size=QSize(20, 20), color=theme.COLORS["glass_text"])
        self.btnOnTop.setIcon(top_icon)
        self.btnOnTop.setIconSize(QSize(20, 20))
        self.btnOnTop.clicked.connect(self.toggle_on_top)

        # 最小化按钮
        close_icon = svg_to_icon(svg.minBtn, size=QSize(20, 20), color=theme.COLORS["glass_text"]) # 将 SVG 转换为 QIcon，并设置颜色
        self.btnClose = QPushButton("")
        self.btnClose.setIcon(close_icon)
        self.btnClose.setIconSize(QSize(20, 20))
        self.btnClose.setToolTip("最小化阅读器")
        self.btnClose.clicked.connect(self.handle_min_btn)

        # 保持窗口可见按钮
        self.btnKeepVisible = QPushButton("")
        self.btnKeepVisible.setIcon(svg_to_icon(svg.showBtn, size=QSize(20, 20), color=theme.COLORS["glass_text"]))
        self.btnKeepVisible.setIconSize(QSize(20, 20))
        self.btnKeepVisible.setToolTip("保持窗口可见")
        self.btnKeepVisible.clicked.connect(self.toggle_keep_visible)

        self.btnToolbarList = [self.btnFontColorWhite,self.btnFontColorBlack, self.btn_font_toggle, self.btnOnTop, self.btnClose, self.btnKeepVisible]#工具栏按钮列表

        for btn in self.btnToolbarList:
            btn.setFixedSize(24, 24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            tool_layout.addWidget(btn)


        # 进度百分比
        self.progress_label = QLabel("0%")
        self.progress_label.setObjectName("ProgressPill")
        tool_layout.addWidget(self.progress_label)
        
        # 创建托盘图标和菜单（菜单样式由全局样式表统一提供）
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(svg_to_icon(svg.bookIcon, size=QSize(20, 20), color="#000000"))) # 请确保路径下有图标文件，否则托盘可能不显示
        self.tray_icon.setToolTip(f"正在阅读：{self.file_path.split('\\')[-1].split('.')[0]}")# 设置托盘提示文本为当前阅读的书籍名称
        self.tray_menu = QMenu()
        
        self.exit_action = QAction("退出阅读", self)# 添加退出动作
        self.exit_action.triggered.connect(self.close)
        self.tray_menu.addAction(self.exit_action)
        
        self.tray_icon.setContextMenu(self.tray_menu)# 将菜单设置给托盘图标
        
        self.tray_icon.show()
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
    def handle_min_btn(self):
        self.hide() # 隐藏主窗口
        self.show_hide_window=False
    def on_tray_icon_activated(self, reason):
        """处理托盘点击事件"""
        # 判断是否为双击 (或者是单击，根据喜好决定)
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()
            self.show_hide_window=True
    
    def toggle_keep_visible(self):
        """切换窗口保持可见状态，鼠标移出窗口范围时隐藏窗口"""
        if self.keep_visible:
            self.keep_visible = False
            self.btnKeepVisible.setIcon(svg_to_icon(svg.hideBtn, size=QSize(20, 20), color=theme.COLORS["glass_text"]))
        else:
            self.keep_visible = True
            self.btnKeepVisible.setIcon(svg_to_icon(svg.showBtn, size=QSize(20, 20), color=theme.COLORS["glass_text"]))
    
    def toggle_on_top(self):
        """切换窗口置顶状态"""
        
        if self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint:# 判断当前窗口是否已置顶
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint)# 取消置顶
            colorTmp="#94A3B8"
        else:
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)# 设置置顶
            colorTmp="#F1F5F9"
        top_icon = svg_to_icon(svg.topBtn, size=QSize(20, 20), color=colorTmp)# 更新按钮样式以反映当前状态
        self.btnOnTop.setIcon(top_icon)
    
    def eventFilter(self, source, event):
        padding = 40 
        if source == self.btn_font_toggle and event.type() == QEvent.Type.MouseButtonPress:
            # 调节字体大小的按钮被点击了，根据鼠标按键类型调整字体大小
            if event.button() == Qt.MouseButton.LeftButton:
                self.change_font(1)  # 左键增大
                return True
            elif event.button() == Qt.MouseButton.RightButton:
                self.change_font(-1) # 右键减小
                return True
        if source in (self.viewer, self.viewer.viewport()):
            # 处理鼠标滚轮事件 (实现翻页) 
            if event.type() == QEvent.Type.Wheel:
                # angleDelta().y() > 0 是向上滚， < 0 是向下滚
                delta = event.angleDelta().y()
                scrollbar = self.viewer.verticalScrollBar()    
                if delta < 0 and scrollbar.value() >= scrollbar.maximum():# 如果向下滚动，且滚动条已到最底部
                    if self.current_chapter_index < len(self.chapters) - 1:
                        self.load_chapter(self.current_chapter_index + 1,0)# 切换到下一章
                        self.viewer.verticalScrollBar().setValue(0)# 切换后将滚动条重置到顶部
                        return True # 消费掉事件，防止抖动
                
                # 如果向上滚动，且滚动条已到最顶部，自动回退上一章
                elif delta > 0 and scrollbar.value() <= 0:
                    if self.current_chapter_index > 0:
                        self.load_chapter(self.current_chapter_index - 1,0)
                        QTimer.singleShot(50, lambda: scrollbar.setValue(scrollbar.maximum()))# 切换到上一章后，通常将滚动条设到底部，方便连续阅读
                        return True
            if event.type() == QEvent.Type.MouseButtonPress:
                # 处理鼠标按下事件
                if event.button() == Qt.MouseButton.LeftButton:
                    self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                    return False

            elif event.type() == QEvent.Type.MouseMove:
                pos = self.mapFromGlobal(event.globalPosition().toPoint())
                self._is_resizing = (pos.x() > self.width() - padding and 
                                        pos.y() > self.height() - padding)
                
                self._is_dragging = not self._is_resizing# 如果不是缩放，那就是拖动

                global_pos = event.globalPosition().toPoint()
                local_pos = self.mapFromGlobal(global_pos)

                if event.buttons() == Qt.MouseButton.NoButton:
                    # print("Mouse is moving without buttons pressed.")
                    if local_pos.x() > self.width() - padding and local_pos.y() > self.height() - padding:
                        # self._is_resizing = True
                        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
                        source.setCursor(Qt.CursorShape.SizeFDiagCursor)
                    else:
                        # pass
                        self.setCursor(Qt.CursorShape.ArrowCursor)
                        source.setCursor(Qt.CursorShape.ArrowCursor)
                    return False

                if event.buttons() & Qt.MouseButton.LeftButton:
                    if getattr(self, '_is_resizing', False):
                        self.resize(max(200, local_pos.x()+padding//2), max(200, local_pos.y()+padding//2))
                        return True 
                    elif getattr(self, '_is_dragging', False):
                        self.move(global_pos - self._drag_pos)
                        return True

            # 新增：释放鼠标时重置所有状态
            elif event.type() == QEvent.Type.MouseButtonRelease:
                self._is_resizing = False
                self._is_dragging = False
                return False
            # 拦截右键点击事件
            elif event.type() == QEvent.Type.ContextMenu:
                self.show_custom_context_menu(event.globalPos())
                return True # 返回 True 表示该事件已被处理，不再传递给系统默认菜单

        return super().eventFilter(source, event)
    
    def monitor_mouse(self):
        
        global_pos = QCursor.pos()# 获取全局坐标和窗口当前的矩形区域
        window_rect = self.frameGeometry() # 使用 frameGeometry 包含边框范围（如有）    
        is_mouse_in_window = window_rect.contains(global_pos)# 判断鼠标是否在窗口范围内
        
        if is_mouse_in_window:
            # 如果窗口隐藏了，且鼠标移入，则显示
            if self.isHidden() and self.show_hide_window:
                self.show()
            
            # --- 原有的工具栏显隐逻辑 ---
            mouse_pos = self.mapFromGlobal(global_pos)
            if 0 <= mouse_pos.y() <= 40 and 0 <= mouse_pos.x() <= self.width():
                if self.toolbar.isHidden():
                    # 保持工具栏高度一致
                    self.toolbar.setGeometry(40, 20, self.width() - 80, 40)
                    theme.fade_in(self.toolbar)  # 平滑淡入显示
                    self.toolbar.raise_()
            else:
                if not self.toolbar.isHidden() and not self.toolbar.underMouse() and not self.chapter_selector.view().isVisible():
                    self.toolbar.hide()  
            # 实时更新内存中的滚动位置
            self.saved_scroll_pos = self.viewer.verticalScrollBar().value()

        else:
            # --- 鼠标移出窗口的逻辑 ---
            if not self.keep_visible or not self.show_hide_window:
                if not self.isHidden():
                    self.hide()
            else:
                if self.isHidden():
                    self.show()

    def show_custom_context_menu(self, global_pos):
        """自定义右键菜单：包含子菜单选择颜色"""
        menu = QMenu(self)  # 菜单样式由全局样式表统一提供
        # 创建“设置颜色”子菜单
        color_menu = QMenu("", menu)
        color_menu.setIcon(svg_to_icon(svg.fontcolorMenu, size=QSize(20, 20))) # 设置子菜单图标
        colors = [
            ("🤍", "#FFFFFF"),#白
            ("🖤", "#000000"),# 黑色
            ("🤍", "#E0E0E0"),#浅灰
            ("💙", "#2C3E50"),#深蓝
            ("🤎", "#333333"),#深灰
            ("💜", "#74E098"),#紫
            ("🩵", "#A6B9EF")#浅蓝
        ]
        for name, code in colors:
            color_action = QAction('', self)
            color_action.setIcon(svg_to_icon(svg.fontcolorBtn, size=QSize(20, 20), color=code))
            color_action.triggered.connect(lambda checked, c=code: self.set_color_font(c))
            color_menu.addAction(color_action)
        menu.addMenu(color_menu)# 将子菜单添加到主菜单中
        
        menu.addSeparator()
     
        # 添加退出按钮
        exic_action = QAction("", self)
        exic_action.setIcon(svg_to_icon(svg.closeBtn, size=QSize(20, 20), color="#64748B"))
        exic_action.triggered.connect(self.close)
        menu.addAction(exic_action)
       
        menu.exec(global_pos) # 弹出菜单
    def mouseReleaseEvent(self, event):
        """鼠标释放时，重置变量"""
        self._drag_pos = QPoint()
        event.accept()

    def change_font(self, delta):
        """修改字体大小并重新渲染"""
        self.font_size += delta
        self.font_size = max(12, min(self.font_size, 40)) # 限制范围
        self.update_style()

    def load_chapter(self, index, scroll_pos=0):
        """加载章节"""
        if 0 <= index < len(self.chapters):
            self.current_chapter_index = index
            
            self.update_style()
            
            # 更新UI状态
            progress = int(((index + 1) / len(self.chapters)) * 100)
            self.progress_label.setText(f" {progress}% ")

            # print(f"Loading chapter (索引: {scroll_pos})")
            QTimer.singleShot(10, lambda: self.viewer.verticalScrollBar().setValue(scroll_pos))
            # self.viewer.verticalScrollBar().setValue(scroll_pos)
            # 阻止信号循环
            self.chapter_selector.blockSignals(True)
            self.chapter_selector.setCurrentIndex(index)
            self.chapter_selector.blockSignals(False)
    def set_color_font(self, color):
        self.font_color = color
        scroll_pos = self.viewer.verticalScrollBar().value()
        """设置白色字体"""
        """通过 CSS 渲染正文内容"""
        current_html = self.chapters[self.current_chapter_index]["content"]
        style = theme.reader_document_css(self.font_size, self.font_family, self.font_color)
        self.viewer.setHtml(style + current_html)
        self.viewer.verticalScrollBar().setValue(scroll_pos)
    def update_style(self):
        """通过 CSS 渲染正文内容"""
        scroll_pos = self.viewer.verticalScrollBar().value()

        current_html = self.chapters[self.current_chapter_index]["content"]
        style = theme.reader_document_css(self.font_size, self.font_family, self.font_color)
        self.viewer.setHtml(style + current_html)
        self.viewer.verticalScrollBar().setValue(scroll_pos)

    def resizeEvent(self, event):
        """窗口缩放时自适应布局"""
        self.viewer.setGeometry(0, 0, self.width(), self.height())
        super().resizeEvent(event)

    # --- 进度保存逻辑 ---
    def load_saved_progress(self):
        """从 JSON 加载上次阅读到的位置"""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                aaa=data.get(self.file_path, [0, 0])
                # print(type(aaa))
                if isinstance(aaa, list) and len(aaa) == 2:
                    self.current_chapter_index = aaa[0]
                    self.current_chapter_location = aaa[1]
                else:
                    self.current_chapter_index = aaa
                    self.current_chapter_location = 0

        if os.path.exists(self.setting_path):
            with open(self.setting_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.background_opacity = data.get("opacity", 1.0)
                self.font_family = data.get("font", "Simhei")
    def closeEvent(self, event):
        """关闭时保存当前章节索引"""
        data = {}
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        
        data[self.file_path] = [self.current_chapter_index,self.viewer.verticalScrollBar().value()] # 保存章节索引和滚动位置
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f)

        super().closeEvent(event)


# 异步下载 RSS 的线程，防止主界面卡顿
class RSSLoaderThread(QThread):
    def __init__(self, rssname=None):
        super().__init__()
        self.rssname = rssname
    finished = pyqtSignal(object)
    def run(self):
        if self.rssname == "zhihu_daily":
            # 知乎日报 RSS 源
            feed = feedparser.parse("https://plink.anyfeeder.com/zhihu/daily")
        elif self.rssname == "ithome":
            # IT之家 RSS 源
            feed = feedparser.parse("https://www.ithome.com/rss/")
        elif self.rssname == "sspai":
            # 少数派 RSS 源
            feed = feedparser.parse("https://sspai.com/feed")
        elif self.rssname == "ifanr":
            # 爱范儿 RSS 源
            feed = feedparser.parse("https://www.ifanr.com/feed")
        self.finished.emit(feed)


def fetch_sspai_article_html(url):
    """抓取少数派文章页面，提取正文 HTML 片段。

    少数派官方 RSS(https://sspai.com/feed)只提供摘要 + "查看全文"链接，
    不含 content:encoded 全文字段，所以需要在用户点击时按文章链接抓原文页面。

    正文容器按文章类型分两种：
    - 普通长文：单个 <div class="article__main__content wangEditor-txt">
    - 派早报：多篇新闻条目，每条在 <div class="post__body__extend__item"> 内，
      含 <h2 class="post__body__extend__item__title"> 标题 +
      <div class="post__body__extend__item__content wangEditor-txt"> 正文。
      早报的 article__main__content 容器里只有站点推广位，不是新闻正文，
      必须改抓 post__body__extend__item 才能拿到完整内容。
    """
    import urllib.request
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read()
        if resp.headers.get("Content-Encoding", "").lower() == "gzip":
            import gzip
            raw = gzip.decompress(raw)
        charset = resp.headers.get_content_charset() or "utf-8"
        html = raw.decode(charset, errors="replace")

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")

    # 1) 派早报类：抓取每条新闻条目（标题 + 正文），拼接成完整正文
    extend_items = soup.find_all("div", class_="post__body__extend__item")
    if extend_items:
        parts = []
        for item in extend_items:
            title = item.find("h2", class_="post__body__extend__item__title")
            content = item.find("div", class_="post__body__extend__item__content")
            if content is None:
                continue
            # 清理脚本/样式/iframe
            for tag in content.find_all(["script", "style", "iframe"]):
                tag.decompose()
            if title:
                parts.append(f"<h2>{title.get_text(strip=True)}</h2>")
            parts.append(content.decode_contents())
        if parts:
            return "".join(parts)

    # 2) 普通长文类：抓 article__main__content
    content_div = soup.find("div", class_="article__main__content")
    if content_div is None:  # 兼容个别老模板
        content_div = soup.find("div", class_="article-body") or soup.find("div", class_="slab")
    if content_div is None:
        return None
    for tag in content_div.find_all(["script", "style", "iframe"]):
        tag.decompose()
    for a in content_div.find_all("a"):
        if a.get_text(strip=True) in ("查看全文", "View Full Article", "查看原文"):
            a.decompose()
    return content_div.decode_contents()


class ArticleLoaderThread(QThread):
    """按需抓取单篇文章全文的异步线程（当前用于少数派，避免主线程卡顿）"""
    loaded = pyqtSignal(str, object)  # (url, html_str_or_None)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        html = None
        try:
            html = fetch_sspai_article_html(self.url)
        except Exception:
            html = None  # 失败也回传 None，缓存后避免重复重试
        self.loaded.emit(self.url, html)


class RSSWindow(QWidget):
    def __init__(self, rssname=None):
        super().__init__()
        self.resize(400, 500)
        self.rssname = rssname
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)   # 设置窗口背景透明
        self.setWindowFlags(
            self.windowFlags()  
            |Qt.WindowType.WindowStaysOnTopHint     # 窗口总在最前
            |Qt.WindowType.FramelessWindowHint      # 无边框
        )
        self.setMouseTracking(True)     # 开启鼠标追踪
        self.setting_path = "configs/setting.json"  # 记录设置文件的路径
        self.load_settings()            # 加载设置数据
        self._padding = 5               # 鼠标距离边缘多少像素时触发缩放
        self.init_ui()                  # 初始化界面

        self.show_hide_window = True    # 控制窗口显示隐藏的变量
        self.keep_visible = True        # 控制窗口保持可见的变量
        self._drag_pos = QPoint()       # 用于记录拖动时的鼠标位置偏移

        self._is_resizing = False
        self._is_dragging = False       # 新增：拖动状态锁
        self._article_cache = {}        # 少数派全文缓存：{url: html_str_or_None}
        self._article_thread = None     # 文章抓取线程引用
        self._current_detail_entry = None  # 当前正在查看的条目
        self._expected_url = ""         # 当前条目对应的 url 字符串（用于异步回调比对，避免 feedparser 属性访问的边角问题）
        
        self.check_timer = QTimer(self)
        self.check_timer.timeout.connect(self.monitor_mouse)
        self.check_timer.start(100)     # 每 100 毫秒检测一次

        self.load_rss()
    def load_settings(self):
        """加载设置数据"""
        if os.path.exists(self.setting_path):
            with open(self.setting_path, 'r', encoding='utf-8') as f:
                self.setting_data = json.load(f)
                self.background_opacity = self.setting_data.get("opacity", 0.01)
                self.font_family = self.setting_data.get("font", "Simhei")
                self.font_size = self.setting_data.get("font_size", 18)
                self.font_color = self.setting_data.get("font_color", "#000000")
        else:
            self.background_opacity = 0.01
            self.font_family = "Simhei"
            self.font_size = 18
            self.font_color = "#000000"

    def init_ui(self):
        # 使用堆栈布局：0层为列表，1层为内容详情
        self.layout = QVBoxLayout(self)
        self.stack = QStackedWidget()
        
        self.stack.setStyleSheet(f"background-color: rgba(0, 0, 0, {self.background_opacity}); border: none;font-family: {self.font_family};font-size: {self.font_size}px;")# 设置堆栈窗口背景透明
        self.stack.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)# 确保它的视口或内部也不绘制背景
        
        
        # --- 页面 1: 标题列表 ---
        self.list_widget = QListWidget()
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)# 隐藏滚动条
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)# 隐藏滚动条
        self.list_widget.viewport().installEventFilter(self)# 安装事件过滤器，监听对正文的点击
        self.list_widget.setMouseTracking(True)# 开启鼠标追踪
        self.list_widget.viewport().setMouseTracking(True)# 开启 viewport 的鼠标追踪

        self.list_widget.itemClicked.connect(self.show_detail)
        
        # --- 页面 2: 内容展示 ---
        self.viewer = QTextBrowser()
        self.viewer.setStyleSheet(f"background-color: rgba(0, 0, 0, {self.background_opacity}); border: none;font-family: {self.font_family};font-size: {self.font_size}px;")
        # self.viewer.setOpenExternalLinks(True)# 允许外部链接
        # self.viewer.setSource(QUrl("")) # 初始化一个空源，有时能激活网络访问
        self.viewer.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)# 隐藏滚动条
        self.viewer.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)# 隐藏滚动条
        self.viewer.setFrameShape(QFrame.Shape.NoFrame)# 去掉边框
        self.viewer.setAutoFillBackground(False)# 不自动填充背景，保持透明
        self.viewer.viewport().setStyleSheet("background-color: transparent;")# 确保 viewport 也透明        
        self.viewer.viewport().installEventFilter(self)# 安装事件过滤器，监听对正文的点击
        self.viewer.setMouseTracking(True)# 开启鼠标追踪
        self.viewer.viewport().setMouseTracking(True)# 开启 viewport 的鼠标追踪

        
        # 浮动工具栏层 (平时隐藏) —— 深色玻璃拟态样式统一由 theme 提供
        self.toolbar = QFrame(self.stack)
        self.toolbar.setObjectName("FloatingToolbar")
        self.toolbar.setStyleSheet(theme.toolbar_qss())
        self.toolbar.setFixedHeight(40)                 # 固定尺寸
        self.toolbar.hide()                             # 初始隐藏
        tool_layout = QHBoxLayout(self.toolbar)         # 工具栏内部布局
        tool_layout.setContentsMargins(8, 6, 8, 6)
        tool_layout.setSpacing(4)

        self.btnBackToList = QPushButton("")                 # 返回列表按钮
        self.btnBackToList.setIcon(svg_to_icon(svg.backBtn, size=QSize(20, 20), color=theme.COLORS["glass_text"]))
        self.btnBackToList.setToolTip("返回列表")
        self.btnBackToList.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        self.btnBackToList.setIconSize(QSize(20, 20))
        
        self.btnFontColorWhite = QPushButton("")        #字体颜色按钮-白色
        self.btnFontColorWhite.setIcon(svg_to_icon(svg.fontcolorBtn, size=QSize(20, 20), color="#fff"))
        self.btnFontColorWhite.setIconSize(QSize(20, 20))

        self.btnFontColorBlack = QPushButton("")        #字体颜色按钮-黑色
        self.btnFontColorBlack.setIcon(svg_to_icon(svg.fontcolorBtn, size=QSize(20, 20), color="#000"))
        self.btnFontColorBlack.setIconSize(QSize(20, 20))

        self.btnFontColorWhite.clicked.connect(lambda: self.change_color('#fff'))
        self.btnFontColorBlack.clicked.connect(lambda: self.change_color('#000'))

        
        self.btn_font_toggle = QPushButton("")          # 字体大小调节按钮
        self.btn_font_toggle.setIcon(svg_to_icon(svg.fontsizeBtn, size=QSize(20, 20), color=theme.COLORS["glass_text"]))
        self.btn_font_toggle.setIconSize(QSize(20, 20))
        self.btn_font_toggle.setToolTip("左键增大 A+ / 右键减小 A-")
        self.btn_font_toggle.installEventFilter(self)

        
        self.btn_mouse_cross = QPushButton("")                 # 鼠标穿透按钮
        self.btn_mouse_cross.setToolTip("点击切换鼠标穿透")
        self.btn_mouse_cross.setIcon(svg_to_icon(svg.mouseCrossBtn, size=QSize(20, 20), color=theme.COLORS["glass_text"]))
        self.btn_mouse_cross.setIconSize(QSize(20, 20))
        self.btn_mouse_cross.clicked.connect(self.toggle_mouse_cross)


        self.btnOnTop = QPushButton("")                 # 置顶按钮
        self.btnOnTop.setToolTip("点击置顶")
        top_icon = svg_to_icon(svg.topBtn, size=QSize(20, 20), color=theme.COLORS["glass_text"])
        self.btnOnTop.setIcon(top_icon)
        self.btnOnTop.setIconSize(QSize(20, 20))
        self.btnOnTop.clicked.connect(self.toggle_on_top)

        # 最小化按钮
        close_icon = svg_to_icon(svg.minBtn, size=QSize(20, 20), color=theme.COLORS["glass_text"]) # 将 SVG 转换为 QIcon，并设置颜色
        self.btnClose = QPushButton("")
        self.btnClose.setIcon(close_icon)
        self.btnClose.setIconSize(QSize(20, 20))
        self.btnClose.setToolTip("最小化阅读器")
        self.btnClose.clicked.connect(self.handle_min_btn)

        # 保持窗口可见按钮
        self.btnKeepVisible = QPushButton("")
        self.btnKeepVisible.setIcon(svg_to_icon(svg.showBtn, size=QSize(20, 20), color=theme.COLORS["glass_text"]))
        self.btnKeepVisible.setIconSize(QSize(20, 20))
        self.btnKeepVisible.setToolTip("保持窗口可见")
        self.btnKeepVisible.clicked.connect(self.toggle_keep_visible)

        self.btnToolbarList = [self.btnBackToList,self.btnFontColorWhite,self.btnFontColorBlack, self.btn_font_toggle, self.btn_mouse_cross, self.btnOnTop, self.btnClose, self.btnKeepVisible]#工具栏按钮列表

        for btn in self.btnToolbarList:
            btn.setFixedSize(24, 24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            tool_layout.addWidget(btn)

        # 创建托盘图标和菜单（菜单样式由全局样式表统一提供）
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(svg_to_icon(svg.bookIcon, size=QSize(20, 20), color="#000000"))) # 请确保路径下有图标文件，否则托盘可能不显示
        self.tray_menu = QMenu()
        
        self.exit_action = QAction("退出阅读", self)# 添加退出动作
        self.exit_action.triggered.connect(self.close)
        self.tray_menu.addAction(self.exit_action)
        
        self.tray_icon.setContextMenu(self.tray_menu)# 将菜单设置给托盘图标
        
        self.tray_icon.show()
        self.tray_icon.activated.connect(self.on_tray_icon_activated)


        # 添加到堆栈
        self.stack.addWidget(self.list_widget)
        self.stack.addWidget(self.viewer)
        self.layout.addWidget(self.stack)
        self.update_style()


    def toggle_mouse_cross(self):  
        # self.setWindowFlags(
        #     self.windowFlags() | 
        #     Qt.WindowType.WindowTransparentForInput | # 核心：设置输入透明
        #     Qt.WindowType.WindowStaysOnTopHint        # 通常穿透窗口需要保持置顶
        #     ) 
        pass

    def load_rss(self):
        self.thread = RSSLoaderThread(self.rssname)
        self.thread.finished.connect(self.on_rss_loaded)
        self.thread.start()

    def on_rss_loaded(self, feed):
        self.entries = feed.entries
        self.list_widget.clear()
        for entry in self.entries:
            self.list_widget.addItem(entry.title)
    def clean_zhihu_html(self, raw_html, title):
        """将知乎日报的原始HTML清洗并标准化"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(raw_html, 'html.parser')
        content_div = soup.find('div', class_='content')
        if not content_div:
            content_div = soup.find('div', class_='main-wrap') or soup
        for unwanted in content_div.find_all(['a', 'span'], class_=['originUrl', 'view-more']):
            unwanted.decompose()
        for img in content_div.find_all('img'):
            if img.get('src'):
                img.attrs = {'src': img['src']} 
        inner_html = content_div.decode_contents()
        full_html = f"""
        <html>
        <body>
            <h3 class="chapter-title">{title}</h3>
            <div class="rss-content">
                {inner_html}
            </div>
        </body>
        </html>
        """
        return full_html
    
    def show_detail(self, item):
        """点击列表项，展示文章详情。少数派源走全文抓取分支。"""
        index = self.list_widget.row(item)      # 找到点击的文章
        entry = self.entries[index]

        if self.rssname == "sspai":
            self._show_sspai_detail(entry)
            return

        # 其他源：沿用原有解析逻辑（content/summary）
        raw_body = entry.content[0].value if hasattr(entry, 'content') else entry.summary
        standard_html = self.clean_zhihu_html(raw_body, entry.title)

        # 我们只保留正文标签，后续由 update_style 统一上色
        self.current_raw_html = standard_html

        self.stack.setCurrentIndex(1)               # 切换到详情页
        self.viewer.verticalScrollBar().setValue(0) # 滚动到顶部
        self.update_style()

    # ---------- 少数派全文获取 ----------
    # 少数派 RSS(https://sspai.com/feed)本身只提供摘要，不含全文。
    # 因此点击后用 ArticleLoaderThread 异步抓取原文页面，
    # 提取 <div class="article__main__content"> 中的完整正文。
    def _show_sspai_detail(self, entry):
        """少数派：RSS 只给摘要，需抓原文页面取全文。"""
        url = getattr(entry, 'link', '')
        self._current_detail_entry = entry
        self._expected_url = url  # 用纯字符串比对，避免 feedparser 对象属性访问的边角问题

        # 1) 命中缓存（含失败缓存，避免反复重试）→ 直接渲染
        if url in self._article_cache:
            cached = self._article_cache[url]
            if cached:
                self._render_sspai_article(entry, cached)               # 全文
            else:
                self._render_sspai_article(
                    entry, entry.summary, note="全文加载失败，以下为摘要")  # 失败兜底
            return

        # 2) 先用摘要即时展示，避免界面空白（标题由 _render_sspai_article 统一包装）
        self._render_sspai_article(entry, entry.summary, note="正在加载全文…")

        # 3) 启动异步抓取
        if not url:
            return
        # 复用线程引用，避免多个并发
        if self._article_thread is not None and self._article_thread.isRunning():
            self._article_thread.quit()
            self._article_thread.wait(2000)
        self._article_thread = ArticleLoaderThread(url)
        self._article_thread.loaded.connect(self._on_article_loaded)
        self._article_thread.start()

    def _on_article_loaded(self, url, html):
        """少数派文章全文抓取完成回调"""
        self._article_cache[url] = html  # 失败也缓存 None，避免重复请求
        # 用 _expected_url（纯字符串）做比对，比 feedparser 对象属性访问更可靠
        if self._expected_url != url:
            return  # 用户已切到其他文章，不覆盖
        entry = self._current_detail_entry
        if entry is None:
            return
        if html:
            self._render_sspai_article(entry, html)                       # 全文已到
        else:
            self._render_sspai_article(
                entry, entry.summary, note="全文加载失败，以下为摘要")    # 失败兜底

    def _wrap_sspai_html(self, body_html, title, note=""):
        """把正文片段包装为统一结构：标题 + 可选提示 + 正文（便于 update_style 复用）"""
        note_block = f'<p class="sspai-note" style="color:#888;">{note}</p>' if note else ""
        return f"""
        <html>
        <body>
            <h3 class="chapter-title">{title}</h3>
            {note_block}
            <div class="rss-content">
                {body_html}
            </div>
        </body>
        </html>
        """

    def _render_sspai_article(self, entry, body_html, note=""):
        """渲染少数派文章正文：统一包装标题+正文+提示，再交由 update_style 上色"""
        self.current_raw_html = self._wrap_sspai_html(body_html, entry.title, note)
        self.stack.setCurrentIndex(1)
        self.viewer.verticalScrollBar().setValue(0)
        self.update_style()

    
    def handle_min_btn(self):
        self.hide() # 隐藏主窗口
        self.show_hide_window=False
    def on_tray_icon_activated(self, reason):
        """处理托盘点击事件"""
        # 判断是否为双击 (或者是单击，根据喜好决定)
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()
            self.show_hide_window=True
    
    def toggle_keep_visible(self):
        """切换窗口保持可见状态，鼠标移出窗口范围时隐藏窗口"""
        if self.keep_visible:
            self.keep_visible = False
            self.btnKeepVisible.setIcon(svg_to_icon(svg.hideBtn, size=QSize(20, 20), color=theme.COLORS["glass_text"]))
        else:
            self.keep_visible = True
            self.btnKeepVisible.setIcon(svg_to_icon(svg.showBtn, size=QSize(20, 20), color=theme.COLORS["glass_text"]))
    
    def toggle_on_top(self):
        """切换窗口置顶状态"""
        
        if self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint:# 判断当前窗口是否已置顶
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint)# 取消置顶
            colorTmp="#94A3B8"
        else:
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)# 设置置顶
            colorTmp="#F1F5F9"
        top_icon = svg_to_icon(svg.topBtn, size=QSize(20, 20), color=colorTmp)# 更新按钮样式以反映当前状态
        self.btnOnTop.setIcon(top_icon)
    
    def eventFilter(self, source, event):
        # --- 新增安全检查：如果按钮还没创建，直接跳过 ---
        if not hasattr(self, 'btn_font_toggle'):
            return super().eventFilter(source, event)
        
        padding = 40 
        if source == self.btn_font_toggle and event.type() == QEvent.Type.MouseButtonPress:
            # 调节字体大小的按钮
            if event.button() == Qt.MouseButton.LeftButton:
                self.change_font(1)  # 左键增大
                # print('放大字体')
                return True
            elif event.button() == Qt.MouseButton.RightButton:
                self.change_font(-1) # 右键减小
                # print('缩小字体')
                return True
        if source in (self.viewer, self.viewer.viewport()):         # 处理阅读器事件
            
            if event.type() == QEvent.Type.MouseButtonPress:        # 鼠标按下事件
                # logging.debug('鼠标按下事件')
                if event.button() == Qt.MouseButton.LeftButton:     # 左键按下
                    self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()# 计算鼠标按下时窗口的相对位置
                    return False

            elif event.type() == QEvent.Type.MouseMove:             # 处理鼠标移动事件
                pos = self.mapFromGlobal(event.globalPosition().toPoint())
                self._is_resizing = (pos.x() > self.width() - padding and 
                                        pos.y() > self.height() - padding)
                
                self._is_dragging = not self._is_resizing           # 如果不是缩放，那就是拖动
                # logging.debug(f'鼠标移动事件 - 位置: {pos}, _is_resizing: {self._is_resizing}, _is_dragging: {self._is_dragging}')
                global_pos = event.globalPosition().toPoint()
                local_pos = self.mapFromGlobal(global_pos)

                if event.buttons() == Qt.MouseButton.NoButton:
                    # logging.debug('鼠标移动事件（无按键）')
                    if local_pos.x() > self.width() - padding and local_pos.y() > self.height() - padding:
                        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
                        source.setCursor(Qt.CursorShape.SizeFDiagCursor)
                    else:
                        self.setCursor(Qt.CursorShape.ArrowCursor)
                        source.setCursor(Qt.CursorShape.ArrowCursor)
                    return False

                if event.buttons() & Qt.MouseButton.LeftButton:
                    # logging.debug('鼠标移动事件（左键按下）')
                    # logging.debug(f'当前状态 - _is_resizing: {getattr(self, "_is_resizing", False)}, _is_dragging: {getattr(self, "_is_dragging", False)}')
                    if getattr(self, '_is_resizing', False):
                        self.resize(max(200, local_pos.x()+padding//2), max(200, local_pos.y()+padding//2))
                        return True 
                    elif getattr(self, '_is_dragging', False):
                        self.move(global_pos - self._drag_pos)
                        return True

            
            elif event.type() == QEvent.Type.MouseButtonRelease:    # 释放鼠标时重置所有状态
                self._is_resizing = False
                self._is_dragging = False
                return False
            
            elif event.type() == QEvent.Type.ContextMenu:           # 拦截右键点击事件
                self.show_custom_context_menu(event.globalPos())
                return True
        if source in (self.list_widget, self.list_widget.viewport()):
            if event.type() == QEvent.Type.ContextMenu:
                print("触发右键菜单")
                self.show_custom_context_menu(event.globalPos())
                return True 
        return super().eventFilter(source, event)
    
    def monitor_mouse(self):
        
        global_pos = QCursor.pos()          # 获取全局坐标和窗口当前的矩形区域
        window_rect = self.frameGeometry()  # 使用 frameGeometry 包含边框范围（如有）    
        is_mouse_in_window = window_rect.contains(global_pos)   # 判断鼠标是否在窗口范围内
        
        if is_mouse_in_window:
            if self.isHidden() and self.show_hide_window:   # 如果窗口隐藏了，且鼠标移入，则显示
                self.show()

            # 工具栏显隐逻辑
            mouse_pos = self.mapFromGlobal(global_pos)      # 获取鼠标在窗口中的位置
            if 0 <= mouse_pos.y() <= 40 and 0 <= mouse_pos.x() <= self.width():
                if self.toolbar.isHidden():         # 如果鼠标在工具栏区域，且工具栏当前是隐藏的，则显示工具栏
                    self.toolbar.setGeometry(40, 20, self.width() - 80, 40)
                    theme.fade_in(self.toolbar)  # 平滑淡入显示
                    self.toolbar.raise_()
            else:
                if not self.toolbar.isHidden() and not self.toolbar.underMouse():# 只有当工具栏没有被隐藏，且鼠标不在工具栏区域时，才隐藏
                    self.toolbar.hide()  
        else:
            if not self.keep_visible or not self.show_hide_window:# 只有当“始终显示”没有被勾选时，才执行隐藏操作
                if not self.isHidden():
                    self.hide()
            else:
                if self.isHidden():
                    self.show()

    def show_custom_context_menu(self, global_pos):
        """自定义右键菜单：包含子菜单选择颜色"""
        menu = QMenu(self)  # 菜单样式由全局样式表统一提供
        # 创建“设置颜色”子菜单
        color_menu = QMenu("", menu)
        color_menu.setIcon(svg_to_icon(svg.fontcolorMenu, size=QSize(20, 20))) # 设置子菜单图标
        colors = [
            ("🤍", "#FFFFFF"),#白
            ("🖤", "#000000"),# 黑色
            ("🤍", "#E0E0E0"),#浅灰
            ("💙", "#2C3E50"),#深蓝
            ("🤎", "#333333"),#深灰
            ("💜", "#74E098"),#紫
            ("🩵", "#A6B9EF")#浅蓝
        ]
        for name, code in colors:
            color_action = QAction('', self)
            color_action.setIcon(svg_to_icon(svg.fontcolorBtn, size=QSize(20, 20), color=code))
            color_action.triggered.connect(lambda checked, c=code: self.change_color(c))
            color_menu.addAction(color_action)
        menu.addMenu(color_menu)# 将子菜单添加到主菜单中
        
        menu.addSeparator()
     
        # 添加退出按钮
        exic_action = QAction("", self)
        exic_action.setIcon(svg_to_icon(svg.closeBtn, size=QSize(20, 20), color="#64748B"))
        exic_action.triggered.connect(self.close)
        menu.addAction(exic_action)
       
        menu.exec(global_pos) # 弹出菜单
    def mouseReleaseEvent(self, event):
        """鼠标释放时，重置变量"""
        self._drag_pos = QPoint()
        event.accept()

    def change_font(self, delta):
        """修改字体大小并重新渲染"""
        self.font_size += delta
        self.font_size = max(12, min(self.font_size, 40)) # 限制范围
        self.update_style()

    def change_color(self, color):
        self.font_color = color
        self.setting_data['font_color'] = color
        with open("configs/setting.json", 'w', encoding='utf-8') as f:
            json.dump(self.setting_data, f)
        self.update_style()
    def update_style(self):
        """通过 CSS 渲染正文内容"""
        if self.stack.currentIndex() == 0:
            # 列表样式（保留透明度隐身语义）统一由 theme 提供
            self.list_widget.setStyleSheet(
                theme.reader_list_qss(self.font_size, self.background_opacity, self.font_color)
            )
        else:
            scroll_pos = self.viewer.verticalScrollBar().value()
            content = getattr(self, 'current_raw_html', "")
            if not content:
                content = self.viewer.toPlainText()
            # 移除 <img> 标签
            content = re.sub(r'<img [^>]*>', '', content)
            # 移除 <figure> 及其内容（通常包裹着图片和图注）
            content = re.sub(r'<figure[^>]*>.*?</figure>', '', content, flags=re.DOTALL)
            # 移除可能残余的图注标签
            content = re.sub(r'<figcaption[^>]*>.*?</figcaption>', '', content, flags=re.DOTALL)
            content = re.sub(r'<a[^>]*>(.*?)</a>', r'\1', content, flags=re.DOTALL)
            style = theme.reader_document_css(self.font_size, self.font_family, self.font_color)
            self.viewer.setHtml(style + content)
            # 延迟恢复滚动位置，防止渲染未完成导致失效
            QTimer.singleShot(1, lambda: self.viewer.verticalScrollBar().setValue(scroll_pos))

    def resizeEvent(self, event):
        """窗口缩放时自适应布局"""
        self.viewer.setGeometry(0, 0, self.width(), self.height())
        super().resizeEvent(event)

    def closeEvent(self, event):
        """窗口关闭时彻底清理资源"""
        print("Closing...")
        
        # 1. 关键：立刻停止监控计时器，防止它再次触发 self.show()
        if hasattr(self, 'check_timer'):
            self.check_timer.stop()
        
        # 2. 停止 RSS 加载线程
        if hasattr(self, 'thread') and self.thread.isRunning():
            self.thread.terminate()
            self.thread.wait()

        # 2.1 停少数派全文抓取线程（如有）
        if getattr(self, '_article_thread', None) is not None and self._article_thread.isRunning():
            self._article_thread.quit()
            self._article_thread.wait(2000)
        
        # 3. 彻底销毁托盘（不仅仅是隐藏）
        self.tray_icon.setParent(None)
        self.tray_icon.deleteLater()
        
        event.accept()
        
