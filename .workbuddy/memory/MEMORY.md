# 摸鱼工具 — 项目长期约定

## UI 样式系统
- **设计令牌统一在 `theme.py`**：`COLORS`（主色 `#0E7490` 深青 / 辅助色 `#F59E0B` 琥珀 / Slate 系中性色 / `glass_*` 深色浮层）、`FONT_FAMILIES`、`SPACING`、`RADIUS`
- 修改视觉风格只需调令牌；各页面通过 `theme.build_stylesheet()` / `theme.toolbar_qss()` / `theme.reader_document_css()` / `theme.reader_list_qss()` 消费
- 控件样式优先用 `objectName`（`#Card` / `#BookItem` / `#BookName` / `#Muted` / `#Badge` / `#ProgressPill`） + `setProperty('class', 'primary')`，不写组件级 setStyleSheet
- 主操作按钮：`setProperty('class', 'primary')` + 全局 QSS `[class="primary"]` 选主色填充
- Qt QSS 不支持 `box-shadow` / `transition`，用 `theme.apply_shadow(widget)`（QGraphicsDropShadowEffect）和 `theme.fade_in(widget)`（QPropertyAnimation on opacity）实现
- 卡片背景色用 `#FFFFFF`，窗口背景 `@bg_window = #F4F6F8`，留视觉层次
- 间距基准 4 的倍数：4/8/12/16/24；圆角 6/8/10/14
- 字体：UI 用 `Microsoft YaHei UI` → `Microsoft YaHei` → `Segoe UI` 链；阅读正文用设置中的 `SimHei` / `SimSun` / `KaiTi`（用户自选）

## 依赖注意
- PyQt6 的 `QColorDialog` 位于 `QtWidgets`，不在 `QtGui`
- `QPixmap` / `QPainter` 必须在 `QApplication` 创建之后才能用；`theme._icon()` 已用 `_app_ready()` 守卫
- 已移除 `qt_material` 依赖，打包（`打包命令.txt`）时也无需再装

## 阅读器窗口特殊点
- 阅读器（EpubReader / RSSWindow）是无边框 + 半透明背景的悬浮窗
- 工具栏平时隐藏，鼠标进入顶部 40px 才显示
- 工具栏浮动按钮图标必须在浅灰白色（`theme.COLORS["glass_text"]`）才能在深色工具栏上有对比度
- 透明度设置联动 RSS 列表背景透明度（隐身语义），不要覆盖为固定值

## RSS 源处理
- 知乎日报 / IT之家 / 爱范儿：RSS 自带全文，`show_detail` 直接取 `entry.content[0].value` / `entry.summary`
- **少数派**：RSS `https://sspai.com/feed` 只给摘要，需点击时异步抓原文页（`fetch_sspai_article_html` 提取 `div.article__main__content`）→ `ArticleLoaderThread` → 缓存到 `RSSWindow._article_cache`
- 新增"只给摘要"的源时，参照少数派分支模式：在 `show_detail` 加 `if self.rssname == "xxx"` 分支 + 抓取线程 + 缓存
