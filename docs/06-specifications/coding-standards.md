# 影工厂 (ReelForge) 代码规范
# 文件路径：prompts/coding-standards.md
# 版本：v1.1 | 2026-03-19
# 布局：Src-Layout (src/reelforge/) - 业界标准，避免导入歧义

# =============================================================================
# 🔴 关键架构决策：异步策略
# =============================================================================
async_strategy: "THREADING"

# =============================================================================
# 1. Python 类型注解规范（TYPE HINTING）
# =============================================================================
typing_rules:
  mandatory: true
  python_version: "3.9+"
  strict_any: true
  
  patterns:
    function:
      example: |
        def parse_excel(file_path: Path, required_cols: list[str]) -&gt; pd.DataFrame:
            ...
    
    attributes: |
        class ProjectManager:
            db: Database
            def __init__(self, db_path: Path) -&gt; None:
                self.db: Database = Database(db_path)
    
    optional: "使用 | None（3.10+）或 Optional[Type]（兼容3.9）"
    union: "使用 | 语法（str | int）而非 Union[str, int]"
    
    complex_types:
      - "Callable[[ArgType], ReturnType]"
      - "Generator[YieldType, SendType, ReturnType]"
      - "Protocol"
    
    generics: "使用TypeVar定义泛型约束，容器必须参数化：list[dict[str, Any]]"
  
  exceptions:
    - "第三方库无stub：TYPE_CHECKING块中导入，运行时Any并加# type: ignore"
    - "SQL结果：使用TypedDict定义行结构或sqlite3.Row"
    - "Streamlit session_state：使用类型断言cast(dict, st.session_state)"

  checker: "mypy"
  mypy_config: |
    [mypy]
    python_version = 3.9
    strict = True
    warn_return_any = True
    disallow_untyped_defs = True
    disallow_incomplete_defs = True
    disallow_untyped_decorators = True

# =============================================================================
# 2. 错误码体系（ERROR CODE SYSTEM）
# =============================================================================
error_codes:
  categories:
    SYSTEM: "0"
    BUSINESS: "1"
    EXTERNAL: "2"
    VALIDATION: "3"
  
  modules:
    "00": "通用/全局"
    "01": "剧本工坊（Script）"
    "02": "角色工厂（Character）"
    "03": "分镜工作室（Storyboard）"
    "04": "渲染中心（Render）"
    "05": "成片库（Library）"
    "06": "系统设置（Settings）"
    "07": "任务队列（Queue）"
  
  codes:
    E-000-01: {level: "CRITICAL", message: "配置文件缺失或损坏", action: "检查config.yaml"}
    E-000-02: {level: "ERROR", message: "数据库连接失败", action: "检查workspace目录权限"}
    E-000-03: {level: "WARNING", message: "FFmpeg未安装或不在PATH中", action: "安装FFmpeg并添加到环境变量"}
    
    E-101-01: {level: "ERROR", message: "Excel文件格式错误", action: "确保包含'角色'、'台词'、'情绪'三列"}
    E-101-02: {level: "ERROR", message: "Excel列缺失", detail_template: "缺失列：{missing_columns}", action: "补充缺失列"}
    E-101-03: {level: "WARNING", message: "Excel行数超过限制", detail_template: "当前{actual}行，最大允许{limit}行", action: "拆分剧本"}
    
    E-102-01: {level: "ERROR", message: "首帧图格式不支持", detail_template: "仅支持：{supported_formats}", action: "转换格式为PNG或JPG"}
    E-102-02: {level: "WARNING", message: "首帧图尺寸非标准", detail_template: "当前{current_size}，建议{recommended_size}", action: "系统将自动裁剪"}
    E-102-03: {level: "ERROR", message: "角色一致性检测失败", detail_template: "相似度{similarity}%低于阈值{threshold}%", action: "重新上传首帧图"}
    
    E-104-01: {level: "ERROR", message: "视频合成失败", action: "检查FFmpeg日志"}
    E-104-02: {level: "WARNING", message: "磁盘空间不足", detail_template: "剩余{free_space}GB，需要{required_space}GB", action: "清理temp目录"}
    
    E-201-01: {level: "ERROR", message: "DeepSeek API调用失败", detail_template: "HTTP {status_code}: {error_msg}", action: "检查API密钥和网络", retryable: true}
    E-201-02: {level: "WARNING", message: "DeepSeek Token额度不足", detail_template: "剩余{remaining_tokens}", action: "等待月度重置"}
    E-202-01: {level: "ERROR", message: "通义万相 API限流", action: "等待60秒后重试", retryable: true}
    E-202-02: {level: "ERROR", message: "通义万相积分不足", detail_template: "剩余{credits}/50积分", action: "今日额度已用完"}
    E-203-01: {level: "ERROR", message: "Edge TTS语音合成失败", action: "检查网络连接", retryable: true}
    
    E-301-01: {level: "ERROR", message: "参数类型错误", detail_template: "参数'{param}'期望{type}，实际得到{actual_type}"}
    E-301-02: {level: "ERROR", message: "文件路径不安全", detail_template: "路径'{path}'包含非法字符", action: "禁止../等相对路径"}

error_handling_pattern: |
  from typing import TypeVar, Generic, Optional, Any
  from enum import Enum
  
  T = TypeVar('T')
  
  class ErrorCode(Enum):
      EXCEL_FORMAT_ERROR = "E-101-01"
  
  class BusinessException(Exception):
      def __init__(self, code: ErrorCode, detail: Optional[dict] = None):
          self.code = code
          self.detail = detail or {}
          super().__init__(code.value)
  
  class Result(Generic[T]):
      def __init__(self, ok: bool, value: Optional[T] = None, error: Optional[BusinessException] = None):
          self.ok = ok
          self.value = value
          self.error = error
      
      @staticmethod
      def success(value: T) -&gt; "Result[T]":
          return Result(True, value, None)
      
      @staticmethod
      def failure(error: BusinessException) -&gt; "Result[Any]":
          return Result(False, None, error)

# =============================================================================
# 3. 目录结构（DIRECTORY STRUCTURE）- Src-Layout 标准
# =============================================================================
# 说明：外层 reelforge/ 是仓库名，内层 src/reelforge/ 是Python包名
# 这种设计符合 PyPA (Python Packaging Authority) 官方推荐的 Src-Layout
# 优点：避免导入歧义、测试更真实、代码与配置分离

directory_structure: |
  reelforge/                          # 项目根目录（仓库名）
  │
  ├── 📁 prompts/                     # AI提示词资产（本项目配置）
  │   ├── project-config.yaml
  │   ├── coding-standards.md         # 本文件
  │   └── stages/                     # 阶段模板
  │       ├── STEP4-schema.md
  │       └── STEP5-coding.md
  │
  ├── 📁 docs/                        # 项目文档
  │   ├── PRD-v2.0.md
  │   ├── UI-design.md
  │   ├── tech-architecture.md
  │   ├── database-schema.sql         # 待生成
  │   ├── decisions.md                # 运行时追加
  │   └── progress.md                 # 运行时追加
  │
  ├── 📁 src/                         # ⭐ 源代码根（Src-Layout 标准）
  │   └── 📁 reelforge/               # ⭐ Python包目录（import reelforge）
  │       ├── __init__.py             # 包初始化，版本号：__version__ = "1.0.0"
  │       │
  │       ├── 📁 app/                 # Streamlit多页面（原app/移入包内）
  │       │   ├── 🏠_首页.py          # 使用emoji前缀便于识别
  │       │   ├── 2_🎬_剧本工坊.py
  │       │   ├── 3_🎭_角色工厂.py
  │       │   ├── 4_✂️_分镜工作室.py
  │       │   ├── 5_⚡_渲染中心.py
  │       │   ├── 6_📚_成片库.py
  │       │   └── ⚙️_系统设置.py
  │       │
  │       ├── 📁 core/                # 核心业务逻辑（无UI）
  │       │   ├── __init__.py
  │       │   ├── parser.py           # Excel解析器
  │       │   ├── storyboard.py     # 分镜生成器
  │       │   ├── character.py      # 角色管理
  │       │   ├── video_renderer.py # 视频渲染器
  │       │   ├── tts_engine.py     # TTS引擎
  │       │   └── queue_manager.py  # 任务队列
  │       │
  │       ├── 📁 services/          # 外部服务客户端
  │       │   ├── __init__.py
  │       │   ├── deepseek_client.py
  │       │   ├── tongyi_client.py
  │       │   └── tts_client.py
  │       │
  │       ├── 📁 models/              # 数据模型（可选，如不用ORM可合并到core）
  │       │   ├── __init__.py
  │       │   ├── database.py         # SQLite连接
  │       │   ├── project.py
  │       │   ├── character.py
  │       │   ├── shot.py
  │       │   └── task.py
  │       │
  │       ├── 📁 utils/               # 通用工具
  │       │   ├── __init__.py
  │       │   ├── validators.py
  │       │   ├── exceptions.py       # 错误码定义
  │       │   ├── logging_config.py
  │       │   └── type_defs.py        # TypedDict等类型定义
  │       │
  │       └── config.py               # 应用配置（原根目录config.py移入包内）
  │
  ├── 📁 tests/                       # 测试目录（pytest标准，与src平级）
  │   ├── __init__.py
  │   ├── conftest.py                 # pytest共享固件
  │   ├── test_parser.py
  │   ├── test_character.py
  │   └── test_integration.py
  │
  ├── 📁 assets/                      # 静态资源（运行时只读）
  │   ├── bgm/
  │   ├── default_bg/
  │   └── fonts/
  │
  ├── 📁 workspace/                   # 运行时数据（.gitignore）
  │   ├── uploads/
  │   ├── temp/
  │   ├── output/
  │   ├── queue/
  │   ├── zhiying.db                  # SQLite数据库
  │   └── logs/
  │
  ├── 📄 pyproject.toml               # 现代Python项目配置（PEP 518）
  ├── 📄 setup.py                     # 向后兼容（可选）
  ├── 📄 requirements.txt             # 生产依赖（根目录，pip标准）
  ├── 📄 requirements-dev.txt         # 开发依赖
  ├── 📄 .env.example                 # 环境变量模板
  ├── 📄 .gitignore
  ├── 📄 README.md
  ├── 📄 start.bat                    # Windows启动脚本
  └── 📄 start.sh                     # Mac/Linux启动脚本

# 命名约定
naming_conventions:
  folders: "snake_case，无空格，尽量小写"
  python_files: "snake_case.py"
  streamlit_pages: "emoji前缀 + snake_case，如'🏠_首页.py'"
  classes: "PascalCase"
  functions: "snake_case"
  constants: "SCREAMING_SNAKE_CASE"
  private: "单下划线前缀（_internal_func）"
  import_style: "绝对导入（from reelforge.core import parser）"

# 导入规范（Src-Layout 特有）
import_rules:
  # 禁止相对导入（. / ..），必须使用绝对导入
  forbidden: "from .core import parser  # 错误"
  required: "from reelforge.core import parser  # 正确"
  
  # 开发时安装后使用
  development: "pip install -e .  # 可编辑安装，修改代码无需重装"
  
  # 禁止在包内使用根目录相对路径
  path_handling: "使用importlib.resources或pathlib.Path(__file__)定位资源"

# =============================================================================
# 4. Streamlit 特殊处理规则
# =============================================================================
streamlit_specific:
  state_management:
    - "使用st.session_state存储跨页面状态（当前项目ID等）"
    - "使用st.query_params处理URL参数（页面跳转）"
    - "使用st.rerun()代替手动刷新（但避免高频调用）"
  
  performance:
    - "使用@st.cache_data缓存数据加载（TTL=3600）"
    - "使用@st.cache_resource缓存数据库连接等资源"
    - "大文件（&gt;10MB）分片处理"
  
  threading:
    - "Streamlit是线程安全的，但session_state操作需加锁"
    - "后台任务使用threading.Thread，禁止阻塞主线程&gt;2s"
    - "进度更新使用st.progress + st.empty()轮询"
  
  page_organization:
    - "每个.py文件就是一个页面，文件名即URL路径"
    - "公用组件提取到utils/ui_components.py"

# =============================================================================
# 5. 附录：pyproject.toml 模板（必须创建）
# =============================================================================
pyproject_template: |
  [build-system]
  requires = ["setuptools&gt;=61.0", "wheel"]
  build-backend = "setuptools.build_meta"

  [project]
  name = "reelforge"
  version = "1.0.0"
  description = "AI短剧生成平台 - 零云成本本地渲染"
  requires-python = "&gt;=3.9"
  dependencies = [
      "streamlit&gt;=1.29.0",
      "pandas&gt;=2.0.0",
      "pillow&gt;=10.1.0",
      "moviepy==1.0.3",
      "librosa&gt;=0.10.1",
      "pydub&gt;=0.25.1",
      "httpx&gt;=0.25.0",
      "tenacity&gt;=8.2.0",
      "persist-queue&gt;=0.8.1",
      "rembg&gt;=2.0.50",
      "face-recognition&gt;=1.3.0",
      "numpy&gt;=1.24.0",
  ]

  [project.optional-dependencies]
  dev = [
      "pytest&gt;=7.0.0",
      "mypy&gt;=1.0.0",
      "ruff&gt;=0.1.0",
      "black&gt;=23.0.0",
  ]

  [project.scripts]
  reelforge = "reelforge.app.🏠_首页:main"

  [tool.setuptools.packages.find]
  where = ["src"]

  [tool.mypy]
  python_version = "3.9"
  strict = true

  [tool.ruff]
  line-length = 100
  select = ["E", "F", "I"]
  ignore = ["E501"]  # 行长度由ruff控制

  [tool.black]
  line-length = 100
  target-version = ['py39']