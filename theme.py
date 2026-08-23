# -*- coding: utf-8 -*-
"""
theme.py —— 全局设计系统（Design Tokens + QSS 生成器）

集中管理配色、字体、间距、圆角等设计令牌，并统一生成各界面样式表。
需要调整视觉风格时，只修改本文件顶部的令牌定义即可全局生效，各页面保持一致。

配色体系：
  - 主色  primary      深青（Cyan-700），继承原 teal 视觉基因，用于主操作/选中态
  - 辅助色 accent      琥珀，仅用于轻量提示（如“敬请期待”徽标）
  - 中性色 slate 系    文本三级（主/次/弱）、边框、背景，构成视觉层次
"""

import os

from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, Qt
from PyQt6.QtGui import QColor, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QGraphicsDropShadowEffect, QGraphicsOpacityEffect


# ============================================================
# 1. 设计令牌（Design Tokens）
# ============================================================

COLORS = {
    # ---- 主色（深青 Cyan）----
    "primary":        "#0E7490",   # 主操作、选中态
    "primary_hover":  "#155E75",
    "primary_active": "#164E63",
    "primary_soft":   "#E0F2F7",   # 主色浅底：悬停背景 / 选中背景
    "primary_border": "#7CC6DB",   # 主色浅边框：悬停描边

    # ---- 辅助色（琥珀，轻量提示用）----
    "accent":         "#F59E0B",
    "accent_soft":    "#FEF3C7",
    "accent_text":    "#B45309",

    # ---- 中性色（Slate）----
    "text":           "#0F172A",   # 一级文本
    "text_secondary": "#475569",   # 二级文本
    "text_muted":     "#94A3B8",   # 弱化文本 / 占位
    "border":         "#E2E8F0",   # 常规边框
    "border_strong":  "#CBD5E1",   # 控件描边
    "bg_window":      "#F4F6F8",   # 窗口底色
    "bg_card":        "#FFFFFF",   # 卡片底色
    "bg_hover":       "#F1F5F9",   # 中性悬停底

    # ---- 深色浮层（阅读器浮动工具栏，玻璃拟态）----
    "glass_bg":       "rgba(15, 23, 42, 218)",
    "glass_border":   "rgba(255, 255, 255, 30)",
    "glass_text":     "#E2E8F0",
}

# UI 字体（Windows 自带，含回退链）
FONT_FAMILIES = ["Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI"]

# 字号阶梯（px）
FONT_SIZE = {"xs": 11, "sm": 12, "body": 13, "md": 14, "lg": 16, "xl": 18}

# 间距阶梯（px）：4 的倍数，保持节奏一致
SPACING = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24}

# 圆角阶梯（px）
RADIUS = {"sm": 6, "md": 8, "card": 10, "lg": 14}


# ============================================================
# 2. 运行期小图标（QSS 需要落盘文件，这里用 QPainter 现画并缓存）
# ============================================================

def _draw_check(path):
    """白色对勾（用于复选框选中态）"""
    pm = QPixmap(18, 18)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor("#FFFFFF"), 2.6)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.drawLine(4, 9, 7, 12)
    p.drawLine(7, 12, 13, 5)
    p.end()
    pm.save(path)


def _draw_chevron(path, color):
    """下拉箭头（V 形）"""
    pm = QPixmap(16, 16)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 2.0)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.drawLine(4, 6, 8, 10)
    p.drawLine(8, 10, 12, 6)
    p.end()
    pm.save(path)


_ICONS = {}


def _icon(name):
    """生成（并缓存）QSS 用小图标，返回可直接用于 url() 的路径"""
    if name in _ICONS:
        return _ICONS[name]
    d = os.path.join(tempdir(), "moyu_theme_icons")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, name + ".png")
    has_valid = os.path.exists(path) and os.path.getsize(path) > 0
    if not has_valid:
        # QPixmap 必须在 QApplication 之后创建；无实例时先落一个空文件占位
        # （正常启动流程中 build_stylesheet 总是在 QApplication 创建之后调用）
        if os.path.exists(path):
            os.remove(path)  # 清理空占位文件
        if _app_ready():
            if name == "check":
                _draw_check(path)
            elif name == "chevron_dark":
                _draw_chevron(path, "#64748B")
            elif name == "chevron_light":
                _draw_chevron(path, "#E2E8F0")
        else:
            open(path, "wb").close()
    url = path.replace("\\", "/")
    _ICONS[name] = url
    return url


def _app_ready():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() is not None


def tempdir():
    import tempfile
    return tempfile.gettempdir()


def _apply_tokens(qss, extra=None):
    """将 @token@ 占位符替换为设计令牌的值"""
    tokens = dict(COLORS)
    if extra:
        tokens.update(extra)
    # 长键先替换，避免前缀冲突
    for key in sorted(tokens, key=len, reverse=True):
        qss = qss.replace("@" + key + "@", tokens[key])
    return qss


# ============================================================
# 3. 全局样式表（主窗口 + 托盘菜单 + 右键菜单 + 各类控件）
# ============================================================

_MAIN_QSS = """
/* ---------------- 基础 ---------------- */
QWidget {
    font-size: 13px;
    color: @text@;
    selection-background-color: @primary_soft@;
    selection-color: @text@;
}
QMainWindow { background-color: @bg_window@; }
QToolTip {
    background-color: @text@; color: #F8FAFC;
    border: 1px solid @text@; border-radius: 6px;
    padding: 5px 10px; font-size: 12px;
}

/* ---------------- 标签页 ---------------- */
QTabWidget { background: transparent; }
QTabWidget > QWidget { background: transparent; }
QTabWidget::pane { border: none; border-top: 1px solid @border@; margin-top: 10px; background: transparent; }
QTabBar { alignment: center; background: transparent; }
QTabBar::tab {
    background: transparent; color: @text_secondary@;
    padding: 8px 26px; margin: 4px 6px 0 6px;
    border-radius: 8px; font-size: 14px; font-weight: 600; min-width: 72px;
}
QTabBar::tab:hover { color: @primary@; background: @bg_hover@; }
QTabBar::tab:selected { color: @primary@; background: @primary_soft@; }

/* ---------------- 按钮 ---------------- */
QPushButton {
    background-color: @bg_card@; color: @text_secondary@;
    border: 1px solid @border_strong@; border-radius: 8px;
    padding: 7px 16px; font-size: 13px; font-weight: 600;
}
QPushButton:hover { color: @primary@; border-color: @primary_border@; background-color: #F8FBFC; }
QPushButton:pressed { color: @primary@; border-color: @primary@; background-color: @primary_soft@; }
QPushButton:disabled { color: @text_muted@; border-color: @border@; background-color: @bg_hover@; }

/* 主操作按钮（实心主色） */
QPushButton[class="primary"] {
    background-color: @primary@; color: #FFFFFF; border: 1px solid @primary@;
}
QPushButton[class="primary"]:hover { background-color: @primary_hover@; border-color: @primary_hover@; color: #FFFFFF; }
QPushButton[class="primary"]:pressed { background-color: @primary_active@; border-color: @primary_active@; }

/* ---------------- 下拉框 ---------------- */
QComboBox {
    background-color: @bg_card@; color: @text@;
    border: 1px solid @border_strong@; border-radius: 8px;
    padding: 6px 30px 6px 12px; min-height: 22px; font-size: 13px;
}
QComboBox:hover { border-color: @primary_border@; }
QComboBox:focus { border-color: @primary@; }
QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: right center; width: 26px; border: none; }
QComboBox::down-arrow { image: url("@chevron_url@"); width: 12px; height: 12px; }
QComboBox QAbstractItemView {
    background-color: @bg_card@; border: 1px solid @border@; border-radius: 8px;
    padding: 4px; color: @text@;
    selection-background-color: @primary_soft@; selection-color: @primary@;
    outline: none;
}
QComboBox QAbstractItemView::item { min-height: 24px; padding: 4px 10px; border-radius: 6px; }

/* ---------------- 滑块 ---------------- */
QSlider { background: transparent; }
QSlider::groove:horizontal { height: 6px; border-radius: 3px; background-color: @border@; }
QSlider::sub-page:horizontal { background-color: @primary@; border-radius: 3px; }
QSlider::sub-page:horizontal:disabled { background-color: @border_strong@; }
QSlider::handle:horizontal {
    width: 16px; height: 16px; margin: -6px 0; border-radius: 8px;
    background-color: @bg_card@; border: 2px solid @primary@;
}
QSlider::handle:horizontal:hover { background-color: @primary_soft@; border-color: @primary_hover@; }
QSlider::handle:horizontal:pressed { background-color: @primary_soft@; }
QSlider::handle:horizontal:disabled { border-color: @border_strong@; }

/* ---------------- 复选框 ---------------- */
QCheckBox { spacing: 8px; color: @text_secondary@; }
QCheckBox::indicator {
    width: 18px; height: 18px; border-radius: 5px;
    border: 2px solid @border_strong@; background-color: @bg_card@;
}
QCheckBox::indicator:hover { border-color: @primary@; }
QCheckBox::indicator:checked { background-color: @primary@; border-color: @primary@; image: url("@check_url@"); }
QCheckBox::indicator:checked:hover { background-color: @primary_hover@; }
QCheckBox::indicator:disabled { border-color: @border@; }

/* ---------------- 滚动区域 / 滚动条 ---------------- */
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background-color: @border_strong@; border-radius: 3px; min-height: 32px; }
QScrollBar::handle:vertical:hover { background-color: @text_muted@; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; width: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background-color: @border_strong@; border-radius: 3px; min-width: 32px; }
QScrollBar::handle:horizontal:hover { background-color: @text_muted@; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { height: 0; width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }

/* ---------------- 菜单（托盘菜单 / 右键菜单）---------------- */
QMenu {
    background-color: @bg_card@; border: 1px solid @border@;
    border-radius: 10px; padding: 6px;
}
QMenu::item { padding: 7px 26px 7px 12px; border-radius: 6px; color: @text_secondary@; font-size: 13px; }
QMenu::item:selected { background-color: @primary_soft@; color: @primary@; }
QMenu::item:disabled { color: @text_muted@; }
QMenu::separator { height: 1px; background-color: @border@; margin: 6px 8px; }
QMenu::icon { padding-left: 8px; }

/* ---------------- 列表 ---------------- */
QListWidget { background: transparent; border: none; outline: none; }

/* ---------------- 语义化标签 ---------------- */
QLabel { background: transparent; }
QLabel#PageTitle { font-size: 18px; font-weight: 700; color: @text@; }
QLabel#CardTitle { font-size: 14px; font-weight: 600; color: @primary@; }
QLabel#BookName  { font-size: 14px; font-weight: 600; color: @text@; }
QLabel#Muted     { font-size: 12px; color: @text_muted@; }
QLabel#Badge {
    font-size: 11px; font-weight: 600; color: @accent_text@;
    background-color: @accent_soft@; border-radius: 6px; padding: 3px 10px;
}

/* ---------------- 卡片 ---------------- */
#Card {
    background-color: @bg_card@;
    border: 1px solid @border@;
    border-radius: 10px;
}

/* ---------------- 书架条目（悬停卡片）---------------- */
#BookItem {
    background-color: @bg_card@;
    border: 1px solid @border@;
    border-radius: 10px;
    padding: 10px 14px;
}
#BookItem:hover { background-color: #F8FBFC; border: 1px solid @primary_border@; }
"""


def build_stylesheet():
    """生成应用级全局样式表"""
    extra = {
        "check_url": _icon("check"),
        "chevron_url": _icon("chevron_dark"),
    }
    return _apply_tokens(_MAIN_QSS, extra)


# ============================================================
# 4. 阅读器浮动工具栏（深色玻璃拟态）
# ============================================================

_TOOLBAR_QSS = """
#FloatingToolbar {
    background-color: @glass_bg@;
    border: 1px solid @glass_border@;
    border-radius: 14px;
}
#FloatingToolbar QLabel { color: @glass_text@; background: transparent; font-size: 12px; }
#FloatingToolbar #ProgressPill {
    color: @glass_text@; font-size: 12px;
    background-color: rgba(255, 255, 255, 26);
    border-radius: 9px; padding: 2px 10px;
}
#FloatingToolbar QPushButton {
    background-color: transparent; border: none; border-radius: 8px;
}
#FloatingToolbar QPushButton:hover { background-color: rgba(255, 255, 255, 38); }
#FloatingToolbar QPushButton:pressed { background-color: rgba(255, 255, 255, 64); }
#FloatingToolbar QComboBox {
    background-color: rgba(255, 255, 255, 26);
    border: 1px solid rgba(255, 255, 255, 0);
    border-radius: 8px; color: @glass_text@;
    padding: 4px 26px 4px 12px; font-size: 12px; min-height: 18px;
}
#FloatingToolbar QComboBox:hover { background-color: rgba(255, 255, 255, 42); }
#FloatingToolbar QComboBox::drop-down { border: none; width: 20px; }
#FloatingToolbar QComboBox::down-arrow { image: url("@chevron_url@"); width: 12px; height: 12px; }
"""


def toolbar_qss():
    """生成阅读器浮动工具栏样式表（含悬停 / 按压反馈）"""
    extra = {"chevron_url": _icon("chevron_light")}
    return _apply_tokens(_TOOLBAR_QSS, extra)


# ============================================================
# 5. 阅读正文 / RSS 列表样式
# ============================================================

def reader_document_css(font_size, font_family, font_color):
    """生成阅读正文（QTextBrowser HTML）的排版样式"""
    return f"""
    <style>
        body {{
            font-size: {font_size}px;
            line-height: 1.9;
            padding: 40px 44px;
            background-color: transparent;
            font-family: '{font_family}', sans-serif;
            color: {font_color};
        }}
        p {{ margin: 0 0 0.75em 0; }}
        h1, h2, h3 {{ color: {font_color}; text-align: center; margin: 1.1em 0 0.8em 0; }}
        img {{ max-width: 100%; }}
    </style>
    """


def reader_list_qss(font_size, bg_opacity, font_color):
    """
    生成 RSS 文章列表样式。
    保留原有的透明度隐身语义：背景透明度随设置联动，
    选中 / 悬停高亮在原透明度基础上小幅增强。
    """
    def _clamp(v):
        return max(0.0, min(1.0, v))

    bg = _clamp(bg_opacity)
    hover_a = _clamp(bg_opacity + 0.07)
    sel_a = _clamp(bg_opacity + 0.15)
    return f"""
    QListWidget {{
        background-color: rgba(255, 255, 255, {bg});
        border: none; outline: none;
        color: {font_color}; font-size: {font_size}px;
    }}
    QListWidget::item {{
        background-color: transparent;
        color: {font_color}; font-size: {font_size}px;
        padding: 9px 14px; margin: 1px 5px; border-radius: 8px;
    }}
    QListWidget::item:hover {{
        background-color: rgba(14, 116, 144, {hover_a}); border-radius: 8px;
    }}
    QListWidget::item:selected {{
        background-color: rgba(14, 116, 144, {sel_a});
        color: #FFFFFF; border-radius: 8px;
    }}
    """


# ============================================================
# 6. 交互反馈辅助（动画 / 阴影）
# ============================================================

def fade_in(widget, duration=150):
    """
    平滑淡入显示控件（用于浮动工具栏等）。
    效果与动画对象缓存在控件属性上，避免重复创建造成泄漏。
    """
    widget.show()
    effect = getattr(widget, "_fade_effect", None)
    if effect is None:
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        widget._fade_effect = effect
    old_anim = getattr(widget, "_fade_anim", None)
    if old_anim is not None:
        old_anim.stop()
    anim = QPropertyAnimation(effect, b"opacity", widget)
    widget._fade_anim = anim
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.start()
    return anim


def apply_shadow(widget, blur=28, dy=6, alpha=38):
    """为卡片等组件添加柔和投影（Qt QSS 不支持 box-shadow，用图形效果实现）"""
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, dy)
    effect.setColor(QColor(15, 23, 42, alpha))
    widget.setGraphicsEffect(effect)
    return effect


def set_app_font(app):
    """为整个应用设置 UI 字体（含回退链）"""
    try:
        from PyQt6.QtGui import QFont
        font = QFont()
        font.setFamilies(FONT_FAMILIES)
        app.setFont(font)
    except Exception:
        pass
