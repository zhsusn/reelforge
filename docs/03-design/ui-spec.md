# ReelForge UI 设计规范（UI Specification）

**项目**：影工厂 (ReelForge)  
**版本**：v1.0  
**日期**：2026-03-20  
**阶段**：Step 3 - 详细设计  
**上游依赖**：@docs/01-requirements/PRD-v1.0.locked.md, @docs/02-architecture/tech-stack-decision.md  

---

## 1. 设计系统（Design Tokens）

从 HTML 原型中提取并标准化的设计 Token：

### 1.1 颜色系统

```yaml
colors:
  # 主色调
  primary: "#00d4ff"           # 科技青 - 主按钮、高亮、激活状态
  primary_dark: "#008fb3"      # 科技青深色 - 渐变终点
  secondary: "#b829dd"         # 荧光紫 - 次要按钮、强调
  secondary_dark: "#7a1ba3"    # 荧光紫深色 - 渐变终点
  
  # 背景色
  background: "#0a0a0f"        # 深空黑 - 页面主背景
  surface: "#1a1a24"           # 卡片背景 - glass效果基础色
  surface_hover: "rgba(255,255,255,0.05)"  # 悬停背景
  
  # 文字色
  text_primary: "#ffffff"              # 主文字
  text_secondary: "#a0a0b0"            # 次要文字（ slate-400 ）
  text_muted: "#64748b"                # 辅助文字（ slate-500 ）
  
  # 状态色
  success: "#00c853"           # 成功/完成
  success_light: "#00ffab"     # 成功亮色
  warning: "#ffd600"           # 警告
  error: "#ff5252"             # 错误
  info: "#00d4ff"              # 信息（同主色）
  
  # 特殊效果
  glass_border: "rgba(255,255,255,0.08)"   # 玻璃态边框
  glass_bg: "rgba(26,26,35,0.6)"           # 玻璃态背景
  glow_cyan: "rgba(0,212,255,0.3)"         # 青色光晕
  glow_purple: "rgba(184,41,221,0.3)"      # 紫色光晕
  
  # 渐变色
  gradient_primary: "linear-gradient(135deg, #00d4ff, #008fb3)"
  gradient_secondary: "linear-gradient(135deg, #b829dd, #7a1ba3)"
  gradient_brand: "linear-gradient(90deg, #00d4ff, #b829dd)"  # 品牌渐变色
```

### 1.2 字体系统

```yaml
typography:
  font_family: "Inter, 'PingFang SC', system-ui, sans-serif"
  font_family_mono: "'JetBrains Mono', 'Fira Code', monospace"
  
  # 字号层级
  heading_1: "2rem (32px)"      # 页面大标题
  heading_2: "1.5rem (24px)"    # 模块标题
  heading_3: "1.25rem (20px)"   # 卡片标题
  body: "1rem (16px)"           # 正文
  body_sm: "0.875rem (14px)"    # 小正文
  caption: "0.75rem (12px)"     # 注释
  caption_xs: "0.625rem (10px)" # 极小字（标签）
  
  # 字重
  font_light: 300
  font_normal: 400
  font_medium: 500
  font_semibold: 600
  font_bold: 700
  
  # 行高
  leading_tight: 1.25
  leading_normal: 1.5
  leading_relaxed: 1.75
```

### 1.3 间距系统

```yaml
spacing:
  unit: "8px"
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  xxl: "48px"
  
  # 页面布局
  sidebar_width: "256px"        # 侧边栏宽度（w-64）
  main_margin: "256px"          # 主内容区左边距
  page_padding: "32px"          # 页面内边距（p-8）
  section_gap: "32px"           # 区块间距
  card_padding: "24px"          # 卡片内边距（p-6）
  card_gap: "24px"              # 卡片间距
```

### 1.4 圆角与边框

```yaml
borders:
  radius_sm: "4px"              # 小按钮、标签
  radius_md: "8px"              # 输入框、小卡片
  radius_lg: "16px"             # 卡片（rounded-2xl）
  radius_xl: "24px"             # 大卡片（rounded-3xl）
  radius_xxl: "32px"            # 超大卡片（rounded-[2rem]）
  
  # 边框样式
  border_thin: "1px solid rgba(255,255,255,0.08)"
  border_hover: "1px solid rgba(0,212,255,0.4)"
  border_active: "4px solid #00d4ff"  # 侧边栏激活状态
```

### 1.5 阴影与光效

```yaml
effects:
  # 阴影
  shadow_card: "0 4px 15px rgba(0,0,0,0.3)"
  shadow_glow_cyan: "0 0 15px rgba(0,212,255,0.3)"
  shadow_glow_cyan_hover: "0 0 25px rgba(0,212,255,0.5)"
  shadow_glow_purple: "0 0 15px rgba(184,41,221,0.3)"
  
  # 玻璃态
  glass_bg: "rgba(26,26,35,0.6)"
  glass_blur: "blur(12px)"
  glass_backdrop: "backdrop-filter: blur(12px)"
  
  # 文字效果
  text_gradient: "linear-gradient(90deg, #00d4ff, #b829dd)"
```

---

## 2. 页面清单与布局规范（对应 PRD 6+1 模块）

### 2.1 首页 (Dashboard)

**视觉参考**：`@docs/03-design/dashboard/index.html`

| 区域 | 布局 | Streamlit 组件 | 交互说明 |
|:-----|:-----|:---------------|:---------|
| 顶部栏 | 通栏 | `st.header` + `st.metric` 横向排列 | 显示 API 额度、项目数、渲染数 |
| 快速开始 | 4 列卡片 | `st.columns(4)` + `st.container` | 今日成片/节省时长/Tokens/GPU利用率 |
| API趋势图表 | 2/3 宽度 | `st.line_chart` 或 ECharts | DeepSeek Token 与渲染任务趋势 |
| 最近项目 | 1/3 宽度 | `st.container` + `st.columns` | 显示最近 3 个项目，点击跳转编辑 |
| 系统状态 | 底部 | `st.sidebar` | 存储空间、版本号 |

**Streamlit 限制处理**：
- 卡片点击：使用 `st.button` 嵌套在 `st.columns` 中，而非真卡片点击
- 实时数据：使用 `st.empty()` 占位符 + 5 秒轮询更新
- 图表：使用原生 `st.line_chart` 替代 ECharts，简化实现

---

### 2.2 剧本工坊 (Script Workshop)

**视觉参考**：`@docs/03-design/dashboard/scripts.html`

| 区域 | 布局 | Streamlit 组件 | 交互说明 |
|:-----|:-----|:---------------|:---------|
| 页面标题 | 顶部 | `st.title` + `st.caption` | "剧本工坊" + 副标题说明 |
| 上传区 | 居中 | `st.file_uploader` | 拖拽上传（原生支持），限制 `.xlsx` |
| 剧本卡片网格 | 2 列网格 | `st.columns(2)` + 循环渲染 | 显示封面、角色数、分镜数、状态 |
| 智能导入按钮 | 右上角 | `st.button` (primary) | 跳转 AI 导入流程 |

**卡片内容结构**：
```
[封面图] [类型标签]          [更新时间]
[剧本标题]
角色: X个 | 分镜: Y个 | 时长: Z
[状态]                    [编辑] [生成]
```

**Streamlit 限制处理**：
- 无 Excel 实时预览：上传后显示 `st.dataframe` 静态预览，非真电子表格编辑
- 卡片hover效果：使用 `st.container` + CSS 模拟，悬停效果受限
- 标签样式：使用 `st.badge` 或自定义 Markdown 标签

---

### 2.3 角色工厂 (Character Lab)

**视觉参考**：`@docs/03-design/dashboard/characters.html`

| 区域 | 布局 | Streamlit 组件 | 交互说明 |
|:-----|:-----|:---------------|:---------|
| 页面标题 | 顶部 | `st.title` + `st.caption` | "角色工厂" + AI 风格说明 |
| 操作按钮 | 右上角 | `st.button` 组 | "音色测试" + "创建新角色" |
| 角色网格 | 4 列网格 | `st.columns(4)` + 循环 | 角色卡片（封面/名称/风格/一致性） |
| 创建占位 | 最后一格 | `st.container` + 虚线边框 | "训练新角色模型"入口 |

**角色卡片结构**：
```
[角色图片]
[一致性 98%]  [指示器]
[角色名]
[风格描述]
[首帧图锁定] [编辑]
```

**Streamlit 限制处理**：
- 无真拖拽排序：明确使用"↑↓"按钮实现排序，而非 HTML5 拖拽（TD-005 技术债务）
- 首帧预览：上传后立即 `st.image` 显示，添加 `st.spinner` 处理裁剪
- 一致性分数：使用 `st.progress` 或文本显示百分比

---

### 2.4 分镜工作室 (Storyboard Studio)

**视觉参考**：`@docs/03-design/dashboard/editor.html`

| 区域 | 布局 | Streamlit 组件 | 交互说明 |
|:-----|:-----|:---------------|:---------|
| 左侧分镜列表 | 30% 宽度 | `st.container` + `st.button` 列表 | 垂直卡片列表，点击选择 |
| 中央预览区 | 40% 宽度 | `st.image` + 播放控制 | 当前分镜大图预览 |
| 右侧参数面板 | 30% 宽度 | `st.tabs` + `st.form` | Prompt/运镜/时长设置 |
| 底部控制栏 | 固定底部 | `st.columns` + `st.button` | 上一个/暂停/下一个/渲染 |

**分镜列表项结构**：
```
[缩略图] [SCENE 01]
[画面描述摘要]
```

**Streamlit 限制处理**：
- 无水平时间轴：改用垂直卡片列表，选中高亮显示（边框变色）
- 无多轨道编辑：单分镜编辑模式，分步处理画面/台词/运镜
- 实时预览：使用 `st.rerun()` 切换分镜，而非真 SPA 路由
- 播放器皮肤：使用原生 `st.audio` + 自定义按钮组，无自定义播放器

---

### 2.5 渲染中心 (Render Queue)

**视觉参考**：`@docs/03-design/dashboard/render.html`

| 区域 | 布局 | Streamlit 组件 | 交互说明 |
|:-----|:-----|:---------------|:---------|
| 页面标题 | 顶部 | `st.title` + `st.caption` | "渲染调度管理" + 副标题 |
| 三列看板 | 横向 3 列 | `st.columns(3)` | 待处理/渲染中/已完成（Kanban 风格） |
| 任务卡片 | 列内 | `st.container` + `st.progress` | 显示进度条、项目名、预计时间 |
| 实时日志 | 底部折叠 | `st.expander` + `st.code` | 显示 FFmpeg 输出日志 |

**任务卡片结构（渲染中）**：
```
[项目名]              [76%]
[=========>    ]
[节点名]        [剩余时间]
```

**Streamlit 限制处理**：
- 无真实时推送：使用 `st.empty()` + `time.sleep(1)` 轮询更新进度（TD-001 技术债务）
- 跨列拖拽：不支持，使用"移动到下阶段"按钮替代
- 日志流：`st.expander` 包裹 `st.code`，手动展开查看

---

### 2.6 成片库 (Library)

**视觉参考**：`@docs/03-design/dashboard/library.html`

| 区域 | 布局 | Streamlit 组件 | 交互说明 |
|:-----|:-----|:---------------|:---------|
| 页面标题 | 顶部 | `st.title` + 统计信息 | "数字化视频资产管理" + 文件数/存储 |
| 搜索排序 | 右上角 | `st.text_input` + `st.selectbox` | 搜索文件名/标签 + 排序方式 |
| 视频网格 | 4 列响应式 | `st.columns(4)` 循环 | 视频缩略图（第一帧）+ 标题 + 标签 |
| 操作覆盖层 | 悬停显示 | `st.popover` 或页面跳转 | 播放/下载/删除 |

**视频卡片结构**：
```
[视频缩略图] [时长]
[播放/下载按钮] (hover显示)

[文件名] [收藏]
[4K] [Sci-Fi] (标签)
[生成日期]
```

**Streamlit 限制处理**：
- 无真瀑布流：固定 4 列网格，响应式通过 `st.columns` 实现
- 视频播放：使用 `st.video` 原生播放器，非自定义播放器皮肤
- hover效果受限：使用 `st.popover` 或点击进入详情页

---

### 2.7 系统设置 (Settings)

**视觉参考**：`@docs/03-design/dashboard/settings.html`

| 区域 | 布局 | Streamlit 组件 | 交互说明 |
|:-----|:-----|:---------------|:---------|
| 页面标题 | 顶部 | `st.title` | "偏好设置与集成" |
| API 密钥管理 | 卡片 | `st.form` + `st.text_input` | DeepSeek/通义万相密钥输入 |
| 存储管理 | 卡片 | `st.metric` + `st.button` | 显示磁盘使用，清理临时文件 |
| 界面偏好 | 卡片 | `st.toggle` + `st.checkbox` | 渲染特效/预解析/性能模式 |
| 保存按钮 | 底部 | `st.form_submit_button` | 保存并应用所有更改 |

**Streamlit 限制处理**：
- 密码显示切换：`st.text_input(type="password")` + 显示按钮（通过 session_state 切换）
- 开关样式：使用 `st.toggle` (1.29+) 替代自定义开关
- 表单分组：使用 `st.form` 包裹相关设置项

---

## 3. 组件映射表（视觉 → Streamlit）

| 视觉设计元素 | HTML 实现 | Streamlit 替代方案 | 妥协说明 |
|:-------------|:----------|:-------------------|:---------|
| 玻璃态卡片 | `backdrop-filter: blur` | `st.container` + 自定义 CSS | 效果简化，避免复杂 CSS |
| 渐变文字 | `background-clip: text` | `st.markdown` + HTML/CSS | 使用 `unsafe_allow_html=True` |
| 悬浮按钮 | `position: fixed` | `st.button` 放在侧边栏或顶部 | 无真悬浮，固定位置 |
| 下拉菜单 | `<select>` | `st.selectbox` / `st.multiselect` | 原生样式，不可深度定制 |
| 开关 | `<input type="checkbox">` | `st.toggle` (1.29+) | 使用新版组件 |
| 滑块 | `<input type="range">` | `st.slider` | 功能等价 |
| 日期选择 | `<input type="date">` | `st.date_input` | 功能等价 |
| 文件拖拽 | `dragover` 事件 | `st.file_uploader` | 原生支持，无需妥协 |
| 图片裁剪 | canvas 操作 | 后端 Pillow 裁剪 | 上传后处理，非实时裁剪 |
| 真拖拽排序 | HTML5 Drag API | `st.sortable` 或上下箭头 | **技术债务 TD-005**：使用按钮替代 |
| 实时进度条 | WebSocket 推送 | `st.progress` + 轮询 | **技术债务 TD-001**：轮询更新 |
| 多栏布局 | CSS Grid | `st.columns` / `st.tabs` | 网格系统不如 CSS Grid 灵活 |
| 弹窗/模态框 | Modal dialog | `st.dialog` (1.29+) 或页面跳转 | 无自定义层级 z-index |
| 富文本编辑 | WYSIWYG Editor | `st.text_area` + Markdown | 无所见即所得编辑器 |
| 图片预览网格 | Masonry Layout | `st.columns` + `st.image` | 无瀑布流布局 |
| 视频播放器 | Custom skin | `st.video` | 使用原生播放器 |
| 日志终端 | Monospace console | `st.code` + `st.expander` | 样式简化 |
| 实时图表 | ECharts | `st.line_chart` / `st.area_chart` | 功能简化 |

---

## 4. 响应式策略

基于 Streamlit 的限制，明确以下断点：

```yaml
breakpoints:
  mobile: "< 768px"       # 单列布局，侧边栏收起为汉堡菜单
  tablet: "768-1024px"    # 2 列布局
  desktop: "> 1024px"     # 4 列布局（默认开发目标）

adaptive_rules:
  - "首页统计卡片：移动端垂直堆叠 (st.columns(1))，桌面端 4 列 (st.columns(4))"
  - "剧本工坊上传区：移动端全宽，桌面端居中 80%"
  - "角色工厂网格：移动端 2 列，平板 3 列，桌面 4 列"
  - "分镜工作室：移动端隐藏左侧列表，仅用下拉选择分镜"
  - "渲染中心看板：移动端单列堆叠，桌面 3 列"
  - "成片库网格：移动端 1 列，平板 2 列，桌面 4 列"
  - "系统设置：移动端单列，桌面 2 列网格"
```

---

## 5. 交互状态定义

### 5.1 加载状态

```python
# 全局加载（阻塞操作）
with st.spinner("AI生成中..."):
    result = generate_image(prompt)

# 局部加载（非阻塞）
progress_placeholder = st.empty()
for i in range(100):
    progress_placeholder.progress(i + 1, text=f"渲染中... {i+1}%")
    time.sleep(0.1)

# 骨架屏（不支持原生）
st.info("⏳ 加载中...")  # 使用 info 替代
```

### 5.2 空状态

| 场景 | 组件 | 文案 |
|:-----|:-----|:-----|
| 无项目 | `st.info` | "暂无项目，点击上方按钮创建" |
| 无角色 | `st.warning` | "请先创建角色，再生成视频" |
| 渲染队列为空 | `st.success` | "🎉 所有任务已完成！" |
| 无成片 | `st.info` | "暂无成品，前往渲染中心开始制作" |
| 搜索无结果 | `st.info` | "未找到匹配的文件，尝试其他关键词" |

### 5.3 错误状态

| 错误类型 | 组件 | 样式 |
|:---------|:-----|:-----|
| 校验错误 | `st.error` | 红色边框 + 图标 "❌ Excel格式错误：缺少'台词'列" |
| API 限流 | `st.toast` | 临时提示 "DeepSeek API限流，自动重试中..." (1.29+) |
| 系统错误 | `st.exception` | 仅在调试模式显示详细堆栈 |
| 网络错误 | `st.error` | "网络连接失败，请检查网络后重试" |
| 磁盘空间不足 | `st.error` | "❌ 磁盘空间不足，请清理 output 目录" |

---

## 6. 自定义 CSS 规范

Streamlit 允许通过 `st.markdown` 注入自定义 CSS：

```python
import streamlit as st

# 自定义样式注入
custom_css = """
<style>
    /* 主色调变量 */
    :root {
        --primary: #00d4ff;
        --secondary: #b829dd;
        --background: #0a0a0f;
        --surface: #1a1a24;
    }
    
    /* 页面背景 */
    .stApp {
        background-color: var(--background);
    }
    
    /* 玻璃态卡片 */
    .glass-card {
        background: rgba(26, 26, 35, 0.6);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 24px;
    }
    
    /* 主按钮样式 */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #00d4ff, #008fb3);
        border: none;
        box-shadow: 0 0 15px rgba(0, 212, 255, 0.3);
    }
    
    /* 渐变文字 */
    .text-gradient {
        background: linear-gradient(90deg, #00d4ff, #b829dd);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    /* 隐藏默认侧边栏 */
    [data-testid="stSidebar"] {
        display: none;
    }
</style>
"""

st.markdown(custom_css, unsafe_allow_html=True)
```

---

## 7. 与上游文档对齐检查

### 7.1 与 PRD-v2.0 对齐

| PRD 模块 | PRD 验收标准 | 本规范对应 | 状态 |
|:---------|:-------------|:-----------|:----:|
| P0-首帧角色锁定 | AC5: 进度实时反馈 | 角色工厂页面 + `st.progress` | ✅ |
| P0-Excel批量剧本 | AC1: 列名校验 | 剧本工坊 + `st.dataframe` 预览 | ✅ |
| P0-智能分镜 | AC5: 可视化时间轴 | 分镜工作室 + 垂直卡片列表 | ✅ |
| P0-本地渲染 | AC5: 渲染进度 | 渲染中心 + `st.progress` 轮询 | ✅ |
| P1-零成本配置 | AC1: API向导 | 系统设置 + `st.form` | ✅ |
| P1-成本预警 | AC2: 额度提示 | 首页 + `st.metric` | ✅ |

### 7.2 与 tech-stack-decision.md 对齐

| 技术债务 | 限制说明 | 本规范妥协方案 | 状态 |
|:---------|:---------|:---------------|:----:|
| TD-001 无真并发 | Streamlit 架构限制 | 使用 `st.empty()` + 轮询更新 | ✅ |
| TD-005 无真拖拽 | 无原生拖拽组件 | 上下箭头按钮实现排序 | ✅ |
| ADR-001 Streamlit | 无 WebSocket 真推送 | `st.rerun()` + 进度条轮询 | ✅ |

### 7.3 页面覆盖检查

- [x] 首页 (Dashboard) - 有 HTML 参考
- [x] 剧本工坊 (Script Workshop) - 有 HTML 参考
- [x] 角色工厂 (Character Lab) - 有 HTML 参考
- [x] 分镜工作室 (Storyboard Studio) - 有 HTML 参考
- [x] 渲染中心 (Render Queue) - 有 HTML 参考
- [x] 成片库 (Library) - 有 HTML 参考
- [x] 系统设置 (Settings) - 有 HTML 参考

---

## 8. 阻断条件（P3.1 → P3.2/P4）

进入下一步（Schema设计或接口定义）前必须确认：

- [ ] **颜色系统提取完成**：主色/辅色/背景色有明确 HEX 值（已提取：#00d4ff / #b829dd / #0a0a0f）
- [ ] **Streamlit 限制处理明确**：每个页面的"限制处理"章节已填写（无空白）
- [ ] **妥协方案可接受**：
  - [ ] 上下箭头排序替代拖拽（TD-005）
  - [ ] 垂直时间轴替代水平时间轴
  - [ ] 轮询进度替代 WebSocket 推送（TD-001）
- [ ] **图片输入处理**：所有 6+1 页面有对应的 HTML 视觉参考

---

## 附录：文档引用

### 上游输入

| 文档 | 路径 | 用途 |
|:-----|:-----|:-----|
| PRD V2.0 | `@docs/01-requirements/PRD-v1.0.locked.md` | 功能需求、验收标准 |
| 技术栈决策 | `@docs/02-architecture/tech-stack-decision.md` | Streamlit 限制、技术债务 |
| HTML 原型 | `@docs/03-design/dashboard/*.html` | 视觉设计参考 |

### 下游依赖

| 文档 | 路径 | 依赖关系 |
|:-----|:-----|:---------|
| 模块详细设计 | `@docs/02-architecture/module-design.md` | 基于 UI 规范定义模块接口 |
| Streamlit 页面代码 | `src/reelforge/app/*.py` | 基于本规范实现 |

---

**文档元数据**

| 属性 | 值 |
|:-----|:---|
| **文档编号** | UI-2026-001 |
| **版本** | v1.0 |
| **创建日期** | 2026-03-20 |
| **作者** | UI 设计规范工程师 + Streamlit 组件专家 |
| **审核状态** | 待确认 |
| **下游阶段** | Step 3.2 - Schema 设计 / Step 4 - 接口定义 |

---

*本文档遵循《通用行动列表》Step 3 规范生成，与影工厂 (ReelForge) 项目技术架构保持一致。*
