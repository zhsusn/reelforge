# 影工厂文档引用协议 (Document Protocol)
# 文件路径：prompts/document-protocol.md
# 版本：v1.0 | 2026-03-19

# =============================================================================
# 1. 引用语法规范 (Reference Syntax)
# =============================================================================

syntax:
  # 标准引用格式
  format: "@&lt;scope&gt;/&lt;path&gt;"
  
  # 作用域定义 (Scope)
  scopes:
    docs: 
      path: "docs/"
      description: "项目文档（需求、设计、架构）"
      examples: ["@docs/PRD-v2.0.md", "@docs/UI-design.md"]
    
    prompts: 
      path: "prompts/"
      description: "AI提示词资产（配置、规范、阶段模板）"
      examples: ["@prompts/project-config.yaml", "@prompts/coding-standards.md"]
    
    src: 
      path: "src/reelforge/"
      description: "源代码引用（用于代码生成时参考已有模块）"
      examples: ["@src/core/parser.py", "@src/models/database.py"]
    
    tests: 
      path: "tests/"
      description: "测试用例引用"
      examples: ["@tests/test_parser.py"]
    
    assets: 
      path: "assets/"
      description: "静态资源引用（模板、示例数据）"
      examples: ["@assets/templates/script_template.xlsx"]

  # 路径解析规则
  path_resolution:
    base_dir: "${PROJECT_ROOT}"  # 项目根目录（含.git或pyproject.toml的目录）
    case_sensitive: false       # Windows兼容：路径不区分大小写，但警告大小写不一致
    extension_optional: false   # 必须包含扩展名（明确文件类型）
    encoding: "UTF-8"
    
    # 相对路径解析示例：
    # @docs/PRD-v2.0.md → ${PROJECT_ROOT}/docs/PRD-v2.0.md
    # @src/core/parser.py → ${PROJECT_ROOT}/src/reelforge/core/parser.py

# =============================================================================
# 2. 版本锁定机制 (Version Locking)
# =============================================================================

version_lock:
  # 锁定文件位置
  lock_file: ".document-lock.json"
  
  # 锁定模式
  modes:
    strict: 
      description: "严格模式（推荐用于生产阶段）"
      behavior: "引用文件哈希值必须匹配，否则报错阻断"
      use_case: "代码生成前确保文档未变更"
    
    warning: 
      description: "警告模式（推荐用于开发阶段）"
      behavior: "哈希不匹配时警告并继续，但记录差异"
      use_case: "文档频繁迭代时保持灵活性"
    
    frozen: 
      description: "冻结模式（里程碑存档）"
      behavior: "锁定全部文档版本，任何变更必须显式解锁"
      use_case: "发布候选(RC)阶段，确保生成代码一致性"

  # 校验算法
  checksum:
    algorithm: "SHA-256"
    truncate_to: 16  # 存储前16位（如：a1b2c3d4e5f67890）
    
  # 锁定内容结构
  lock_entry_schema:
    file: "原始引用路径（如 @docs/PRD-v2.0.md）"
    resolved_path: "绝对路径（用于校验）"
    checksum: "SHA-256前16位"
    size_bytes: "文件大小"
    modified_time: "ISO 8601时间戳（最后修改）"
    version_tag: "可选：文档内部版本号（如V2.0）"
    locked_by: "锁定操作者（AI会话ID或人工标记）"
    locked_at: "锁定时间"

  # 锁定文件示例片段：
  example_lock: |
    {
      "protocol_version": "1.0",
      "mode": "strict",
      "entries": {
        "@docs/PRD-v2.0.md": {
          "resolved_path": "/home/user/reelforge/docs/PRD-v2.0.md",
          "checksum": "a1b2c3d4e5f67890",
          "size_bytes": 15234,
          "modified_time": "2026-03-19T14:30:00Z",
          "version_tag": "V2.0",
          "locked_by": "session-20260319-001",
          "locked_at": "2026-03-19T15:00:00Z"
        },
        "@prompts/coding-standards.md": {
          "checksum": "f9e8d7c6b5a43210",
          "version_tag": "v1.1"
        }
      }
    }

# =============================================================================
# 3. 引用解析与验证流程 (Resolution & Validation)
# =============================================================================

resolution_pipeline:
  step_1_parse:
    action: "提取引用字符串"
    input: "原始文本（如：请基于 @docs/PRD-v2.0.md 生成代码）"
    regex: "@(docs|prompts|src|tests|assets)/([\\w\\-./]+\\.[\\w]+)"
    output: "scope, relative_path"
    
  step_2_resolve:
    action: "解析为绝对路径"
    rule: "基于 ${PROJECT_ROOT} + scope映射表 + relative_path"
    validation: 
      - "检查文件存在性（FileNotFoundError时阻断）"
      - "检查文件可读性（权限不足时警告）"
      - "检查文件大小（&gt;10MB时警告可能影响上下文窗口）"
    
  step_3_version_check:
    action: "版本一致性检查"
    logic: |
      if lock_file.exists():
          entry = lock_file.get(reference)
          if entry:
              current_checksum = calculate_sha256(resolved_path)
              if current_checksum != entry.checksum:
                  if mode == "strict":
                      raise VersionMismatchError(
                          f"文档已变更：{reference}\n"
                          f"锁定版本：{entry.checksum}\n"
                          f"当前版本：{current_checksum}\n"
                          f"操作：请确认文档变更后更新锁定文件（python scripts/update-lock.py）"
                      )
                  elif mode == "warning":
                      log_warning(f"文档变更检测：{reference}")
                      append_to_diff_log(reference, entry, current_checksum)
    
  step_4_load:
    action: "加载文档内容"
    encoding: "UTF-8"
    max_size: "50MB"  # 超过则分块加载或报错
    content_type_detection: 
      by_extension:
        ".md": "Markdown"
        ".yaml/.yml": "YAML"
        ".json": "JSON"
        ".py": "Python"
        ".sql": "SQL"
        ".html": "HTML"
        ".xlsx": "Binary（仅读取元数据或跳过内容）"
    
  step_5_cache:
    action: "上下文缓存（当前会话）"
    mechanism: "当前会话内，同一引用只读取一次，后续从内存获取"
    ttl: "当前会话有效（重启后重新加载）"

# =============================================================================
# 4. 错误处理与恢复 (Error Handling)
# =============================================================================

error_catalog:
  E-DOC-01:
    code: "E-DOC-01"
    name: "ReferenceSyntaxError"
    description: "引用语法错误（如缺少@符号、非法字符）"
    resolution: "检查格式是否为 @scope/path/to/file.ext"
    
  E-DOC-02:
    code: "E-DOC-02"
    name: "DocumentNotFoundError"
    description: "文件不存在"
    resolution: |
      1. 检查路径拼写（大小写不敏感但建议一致）
      2. 确认文件是否已上传或生成
      3. 如需创建新文件，使用显式创建命令而非引用
      
  E-DOC-03:
    code: "E-DOC-03"
    name: "VersionMismatchError"
    description: "版本锁定冲突（严格模式下）"
    resolution: |
      选择以下操作之一：
      A. 人工确认文档变更合理性，然后更新锁定：
         python scripts/update-lock.py @docs/PRD-v2.0.md
      B. 临时切换为警告模式（开发阶段）：
         修改 .document-lock.json 中 "mode": "warning"
      C. 回滚文档到锁定版本（谨慎）：
         git checkout &lt;锁定时的commit&gt; -- docs/PRD-v2.0.md
        
  E-DOC-04:
    code: "E-DOC-04"
    name: "CircularReferenceError"
    description: "循环引用（文档A引用文档B，B又引用A）"
    resolution: "检查文档间的include/link关系，打破循环"
    
  E-DOC-05:
    code: "E-DOC-05"
    name: "ScopeViolationError"
    description: "作用域越界（如 @src/../../../etc/passwd）"
    resolution: "禁止 .. 和绝对路径，只能引用项目内文件"

recovery_procedures:
  missing_file:
    immediate_action: "暂停生成，列出缺失文件清单"
    fallback: |
      如果文件非关键（如示例数据）：
      1. 使用PRD中的描述作为假设基础
      2. 在生成代码中添加 TODO: 需补充xxx文件后调整
      3. 继续生成但标记为"需验证"
    
  checksum_mismatch:
    immediate_action: "计算差异摘要（行数变化、关键段落变更）"
    decision_tree: |
      如果是标题/格式微调（&lt;5%内容变化）？
        → 警告并继续
      如果是功能范围变更（新增/删除P0功能）？
        → 阻断，要求人工确认是否重置技术架构
      如果是技术方案调整（如更换数据库）？
        → 阻断，要求重新执行Step 2架构设计

# =============================================================================
# 5. 特殊引用模式 (Special Patterns)
# =============================================================================

special_patterns:
  # 版本化引用（显式指定版本）
  versioned_reference:
    syntax: "@docs/PRD-v2.0.md#V2.0"  # URL片段标识版本
    resolution: "校验文件内元数据（如 front matter 的 version: V2.0）"
    mismatch_action: "警告：引用指定V2.0但文件实际为V2.1"
    
  # 行级引用（精确到段落）
  line_reference:
    syntax: "@docs/PRD-v2.0.md#L120-L150"
    use_case: "引用特定验收标准或接口定义"
    warning: "行号随文档编辑漂移，建议改用锚点引用"
    
  # 章节引用（推荐）
  section_reference:
    syntax: "@docs/PRD-v2.0.md##业务规则"  # Markdown标题锚点
    resolution: "查找 ## 业务规则 所在段落"
    stability: "优于行级引用，但需确保标题不修改"
    
  # 多文件批量引用
  batch_reference:
    syntax: "@docs/*.md"  # 通配符（仅用于列表，不加载内容）
    use_case: "检查docs目录下所有文档的存在性和锁定状态"

# =============================================================================
# 6. 与代码生成工作流的集成 (Integration)
# =============================================================================

workflow_integration:
  # 阶段1-2：需求收敛时
  stage_1_2:
    action: "初始化锁定文件，记录PRD和架构文档的基线版本"
    lock_scope: ["@docs/PRD-v*.md", "@docs/UI-design.md", "@docs/tech-architecture.md"]
  
  # 阶段3-4：设计阶段时
  stage_3_4:
    action: "锁定数据库Schema和API契约"
    lock_scope: ["@docs/database-schema.sql", "@docs/api-contract.yaml"]
    pre_condition: "确认上游PRD未变更（校验和匹配）"
  
  # 阶段5：代码生成时（最关键）
  stage_5:
    action: "严格模式锁定，确保代码与文档一致"
    lock_scope: ["所有已生成的设计文档"]
    validation: |
      每次生成模块前：
      1. 校验所有依赖文档（如生成parser.py前检查@docs/database-schema.sql）
      2. 如检测到变更，阻断并提示："检测到Schema变更，是否重新生成接口定义？"
  
  # 阶段6：验证时
  stage_6:
    action: "比对生成代码与锁定文档的差异"
    report: "生成 document-compliance-report.md（文档遵循度报告）"

# =============================================================================
# 7. 工具命令参考 (CLI Commands)
# =============================================================================

cli_commands: |
  # 初始化锁定文件（项目首次使用）
  python scripts/init-lock.py
  
  # 更新特定文档锁定（确认变更后）
  python scripts/update-lock.py @docs/PRD-v2.0.md
  
  # 批量更新所有变更文档（谨慎）
  python scripts/update-lock.py --all
  
  # 验证当前项目状态
  python scripts/verify-docs.py --mode=strict
  
  # 导出文档依赖图（用于可视化）
  python scripts/export-deps.py --format=mermaid --output=docs/doc-deps.mmd
  
  # 生成文档快照（用于存档）
  python scripts/snapshot.py --tag=milestone-v1.0

# =============================================================================
# 8. 协议元数据 (Protocol Metadata)
# =============================================================================

protocol_meta:
  version: "1.0"
  compatible_with: 
    - "coding-standards.md v1.1"
    - "project-config.yaml v1.0"
  src_layout_compliance: |
    本协议完全兼容 Src-Layout：
    - @src/ 引用自动映射到 src/reelforge/
    - 与Python导入规范一致（from reelforge.xxx 对应 @src/xxx）
  changelog:
    "1.0": "初始版本，支持docs/prompts/src/tests/assets五作用域"