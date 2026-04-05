# 影工厂阶段检查点 (Phase Checkpoints)
# 文件路径：prompts/phase-checkpoints.md
# 版本：v1.0 | 2026-03-19
# 说明：定义7个阶段的进入/退出条件及阻断条件，确保流程受控

# =============================================================================
# 阶段总览 (Pipeline Overview)
# =============================================================================

pipeline:
  name: "影工厂AI闭环开发流程"
  paradigm: "超级个体/单兵作战"
  total_stages: 7
  execution_mode: "sequential_with_gateways"  # 顺序执行，带人工阻断点
  
  # 全局阻断原则（适用于所有阶段）
  global_blockers:
    - "文档哈希校验失败（严格模式下）"
    - "上游阶段交付物缺失或损坏"
    - "用户显式暂停（输入'暂停'或'阻断'）"
    - "检测到不可恢复的技术债务累积（如架构冲突）"

# =============================================================================
# 阶段1：需求收敛 (Brainstorm & Convergence)
# =============================================================================

stage_1:
  id: "STEP1"
  name: "需求收敛"
  alias: "创意收敛"
  
  entry_conditions:
    required_inputs:
      - "原始创意描述（文字/草图/参考链接）"
      - "目标用户画像（网文工作室/知识博主/二创剪辑师）"
      - "成功标准（如：日产10条/零云成本）"
    optional_inputs:
      - "竞品分析报告"
      - "技术预研结论（如通义万相首帧锁定可行性）"
  
  exit_conditions:
    deliverables:
      - "@docs/01-convergence/feasibility-report.md"
        content: "技术可行性、商业可行性、替代方案"
      - "@docs/01-convergence/scope-locked.md"
        content: "P0功能清单（不超过5个）、验收标准量化指标"
      - "@docs/decisions.md#ADR-001"
        content: "首批架构决策记录（技术栈初选）"
  
  blockers:
    - condition: "P0功能超过5个"
      action: "阻断，要求删减至5个以内"
      auto_suggest: "将非核心功能标记为P1/P2，移至后续迭代"
    - condition: "未明确成功标准（无法量化验证）"
      action: "阻断，要求补充验收标准"
      example: "零云成本=除API按量计费外无固定支出；首帧锁定=相似度&gt;=90%"
    - condition: "技术可行性评估为'高风险'且无缓解方案"
      action: "阻断，要求重新评估或调整创意"
  
  checklists:
    entry: 
      - "[ ] 已提供创意描述"
      - "[ ] 已确认目标用户"
    exit:
      - "[ ] 可行性报告已生成并通过校验"
      - "[ ] P0功能范围已锁定（5个以内）"
      - "[ ] 首批ADR已记录到decisions.md"

# =============================================================================
# 阶段2：技术架构 (Architecture Design)
# =============================================================================

stage_2:
  id: "STEP2"
  name: "技术架构"
  alias: "架构设计"
  
  entry_conditions:
    required_inputs:
      - "@docs/01-convergence/scope-locked.md [STEP1交付]"
      - "@prompts/project-config.yaml [项目约束]"
    dependencies_resolved:
      - "STEP1已退出"
  
  exit_conditions:
    deliverables:
      - "@docs/02-architecture/tech-stack-decision.md"
        content: "技术选型对比表、决策理由、债务清单"
      - "@docs/02-architecture/system-architecture.md"
        content: "分层架构图、数据流图、模块边界"
      - "@docs/02-architecture/adr-index.md"
        content: "架构决策记录索引（ADR-001至ADR-00N）"
      - "@prompts/project-config.yaml [更新]"
        content: "技术栈版本锁定（如Streamlit 1.29.0）"
  
  blockers:
    - condition: "技术栈违反项目约束（如选用PostgreSQL而非SQLite）"
      action: "阻断，要求重新选择或书面豁免"
      escalation: "需用户输入'确认豁免：使用xxx替代SQLite，理由：'"
    - condition: "未识别关键技术风险或风险缓解方案不充分"
      action: "阻断，要求补充风险缓解策略"
      example: "通义万相API限流风险必须有降级方案（首帧锁定→风格描述+随机种子）"
    - condition: "架构复杂度与'super-individual'范式冲突（如引入K8s/微服务）"
      action: "阻断，要求简化至单兵可维护"
      guidance: "参考约束：single-developer, zero-cloud-cost"
  
  checklists:
    entry:
      - "[ ] STEP1已标记完成"
      - "[ ] 项目配置已加载"
    exit:
      - "[ ] 技术选型对比表已生成（含超级个体友好度评分⭐）"
      - "[ ] 数据流图已绘制（Mermaid或文字描述）"
      - "[ ] 技术债务清单已建立（含偿还优先级）"
      - "[ ] 技术栈版本已锁定到配置"

# =============================================================================
# 阶段3：详细设计 (Detailed Design)
# =============================================================================

stage_3:
  id: "STEP3"
  name: "详细设计"
  alias: "UI/UX设计"
  
  entry_conditions:
    required_inputs:
      - "@docs/02-architecture/system-architecture.md [STEP2交付]"
      - "@docs/01-convergence/scope-locked.md [功能范围]"
      - "@docs/UI-design.md [已有设计规范，如存在]"
    dependencies_resolved:
      - "STEP2已退出"
      - "架构已冻结（技术栈不可变更）"
  
  exit_conditions:
    deliverables:
      - "@docs/03-design/ui-spec.md"
        content: "页面清单（6+1结构）、组件规范、交互流程"
      - "@docs/03-design/api-contract-draft.yaml"
        content: "接口草案（HTTP路径、请求/响应结构）"
      - "@docs/03-design/state-management.md"
        content: "Streamlit状态管理方案（session_state结构）"
  
  blockers:
    - condition: "页面数量与6+1结构冲突（超过7页或关键页缺失）"
      action: "阻断，要求调整至6+1或书面说明例外"
      reference: "6+1=首页/剧本工坊/角色工厂/分镜工作室/渲染中心/成片库+设置"
    - condition: "未定义Streamlit技术限制下的妥协方案"
      action: "阻断，要求明确替代实现"
      example: "无真拖拽→使用st.sortable；无真并发→使用Threading轮询"
    - condition: "API接口草案与架构分层冲突（如业务逻辑泄露到UI层）"
      action: "阻断，要求重新划分边界"
  
  checklists:
    entry:
      - "[ ] STEP2已标记完成"
      - "[ ] UI设计规范已加载（或准备新建）"
    exit:
      - "[ ] 页面清单符合6+1结构"
      - "[ ] 所有交互元素有明确的技术实现方案（含妥协说明）"
      - "[ ] API草案与core/services模块边界一致"

# =============================================================================
# 阶段4：数据库设计 (Schema Design)
# =============================================================================

stage_4:
  id: "STEP4"
  name: "数据库设计"
  alias: "Schema设计"
  
  entry_conditions:
    required_inputs:
      - "@docs/03-design/ui-spec.md [STEP3交付，页面清单]"
      - "@docs/02-architecture/system-architecture.md [数据流]"
      - "@prompts/project-config.yaml [SQLite约束]"
    dependencies_resolved:
      - "STEP3已退出"
      - "UI流程已冻结（影响数据状态流转）"
  
  exit_conditions:
    deliverables:
      - "@docs/02-architecture/database-schema.sql"
        content: "SQLite建表语句（projects/characters/shots/tasks）"
      - "@docs/02-architecture/entity-relationship.md"
        content: "ER图或表关系说明（含外键约束）"
      - "@docs/02-architecture/migration-strategy.md"
        content: "Schema演进策略（SQLite单文件如何升级）"
  
  blockers:
    - condition: "数据库选型违反约束（非SQLite）"
      action: "阻断，强制要求SQLite"
      no_exception: true  # 此条件不接受豁免
    - condition: "未定义软删除字段（deleted_at）"
      action: "阻断，要求所有业务表添加软删除"
      reference: "business_rules.soft_delete_mandatory"
    - condition: "表结构未覆盖PRD中的核心实体（缺失projects/characters/shots/tasks任一）"
      action: "阻断，要求补充缺失实体表"
    - condition: "字段类型与业务规则冲突（如首帧特征向量存储方式不明确）"
      action: "阻断，要求明确BLOB或BASE64存储方案"
  
  checklists:
    entry:
      - "[ ] STEP3已标记完成"
      - "[ ] 页面清单已确认（影响数据表设计）"
    exit:
      - "[ ] 建表语句可通过SQLite语法检查"
      - "[ ] 包含软删除字段（deleted_at）"
      - "[ ] 包含时间戳字段（created_at, updated_at）"
      - "[ ] 首帧特征向量存储方案已明确"
      - "[ ] 外键关系与级联策略已定义"

# =============================================================================
# 阶段5：代码生成 (Code Generation) - 核心阶段，多重阻断
# =============================================================================

stage_5:
  id: "STEP5"
  name: "代码生成"
  alias: "编码实现"
  
  entry_conditions:
    required_inputs:
      - "@docs/02-architecture/database-schema.sql [STEP4交付，必须已冻结]"
      - "@docs/03-design/ui-spec.md [UI规范]"
      - "@docs/02-architecture/api-contract-draft.yaml [接口草案]"
      - "@prompts/coding-standards.md [代码规范]"
    dependencies_resolved:
      - "STEP4已退出"
      - "Schema已冻结（标记为@docs/02-architecture/database-schema.sql#FROZEN）"
  
  # 阶段5内部子流程（两轮阻断）
  sub_stages:
    step_5_1:
      name: "接口定义 (Interface Definition)"
      description: "仅生成接口/类签名，无实现"
      
      exit_conditions:
        deliverables:
          - "@docs/05-coding/interface-definitions/{module}-interface.py"
            content: "每个模块的抽象基类/Protocol、函数签名、类型注解"
      
      blockers:
        - condition: "接口定义违反代码规范（如函数长度&gt;50行声明，类型注解缺失）"
          action: "阻断，要求修正规范"
        - condition: "模块间接口循环依赖（如A依赖B且B依赖A）"
          action: "阻断，要求重构为单向依赖（DAG）"
    
    step_5_2:
      name: "代码实现 (Implementation)"
      description: "基于已冻结的接口定义生成实现"
      
      entry_conditions:
        required_inputs:
          - "@docs/05-coding/interface-definitions/*.py [所有接口已确认]"
        confirmation_required: "用户输入'确认接口定义'或'修改[具体建议]'"
      
      exit_conditions:
        deliverables:
          - "@src/reelforge/{module}/{file}.py"
            content: "Python实现代码"
          - "@tests/test_{module}.py"
            content: "对应单元测试"
      
      blockers:
        - condition: "代码未通过语法检查（python -m py_compile失败）"
          action: "阻断，AI自动修复并重试（最多3次），仍失败则人工介入"
        - condition: "类型检查失败（mypy报错）"
          action: "阻断，要求修正类型注解"
        - condition: "单函数超过50行（违反coding-standards）"
          action: "阻断，要求拆分函数"
        - condition: "发现Schema与代码不匹配（字段名/类型不一致）"
          action: "阻断，提示：'Schema已冻结，是否申请Schema变更？'（需退回Step 4）"
        - condition: "检测到阻塞式I/O未放入后台线程（Streamlit主线程&gt;2s）"
          action: "阻断，要求使用threading或ThreadPoolExecutor"
        - condition: "未包含tenacity重试装饰器（外部API调用）"
          action: "阻断，要求添加@retry"
  
  # 阶段5整体阻断（跨子阶段）
  global_blockers:
    - condition: "Schema冻结后发生变更（校验和不匹配）"
      action: "阻断，提示'文档锁定冲突'，要求选择：A.退回Step 4更新Schema  B.回滚代码重新生成"
      severity: "critical"
    - condition: "生成代码与上游架构决策冲突（如改用非SQLite数据库）"
      action: "阻断，要求检查ADR"
    - condition: "单模块代码量&gt;1000行（需拆分或重构）"
      action: "阻断，要求拆分为子模块"
  
  checklists:
    entry:
      - "[ ] STEP4已标记完成（Schema冻结）"
      - "[ ] 接口定义子阶段已完成（如适用）"
    exit:
      - "[ ] 所有模块通过语法检查"
      - "[ ] 所有模块通过类型检查（mypy）"
      - "[ ] 所有外部API调用含重试机制"
      - "[ ] 所有耗时操作已放入后台线程"
      - "[ ] 单元测试覆盖率&gt;60%（关键路径）"
      - "[ ] 代码符合Src-Layout目录结构"

# =============================================================================
# 阶段6：验证与债务 (Validation & Debt)
# =============================================================================

stage_6:
  id: "STEP6"
  name: "验证与债务"
  alias: "质量门禁"
  
  entry_conditions:
    required_inputs:
      - "@src/reelforge/ [全部代码生成完成]"
      - "@tests/ [单元测试]"
      - "@docs/02-architecture/tech-stack-decision.md [债务清单]"
    dependencies_resolved:
      - "STEP5已退出"
  
  exit_conditions:
    deliverables:
      - "@docs/06-validation/test-report.md"
        content: "测试覆盖率报告、集成测试结果"
      - "@docs/06-validation/tech-debt-register.md"
        content: "技术债务登记（位置、影响、偿还计划）"
      - "@docs/decisions.md [更新]"
        content: "新增ADR（如测试中发现需架构调整）"
  
  blockers:
    - condition: "集成测试失败（端到端流程不通）"
      action: "阻断，要求修复或标记为已知问题（需偿还计划）"
      example: "Excel上传→分镜生成→首帧锁定→视频渲染 任一环节失败"
    - condition: "技术债务未显性化（代码中有TODO/HACK但未记录）"
      action: "阻断，要求提取到tech-debt-register.md"
    - condition: "性能指标未达标（PRD验收标准）"
      action: "阻断，要求优化或调整验收标准（需人工确认）"
      metrics: "1分钟语音总处理&lt;3分钟；内存峰值&lt;4GB"
  
  checklists:
    entry:
      - "[ ] STEP5已标记完成"
      - "[ ] 单元测试全部通过"
    exit:
      - "[ ] 集成测试通过（至少一条完整流程）"
      - "[ ] 技术债务已登记并分类（高/中/低优先级）"
      - "[ ] 性能基准测试通过（或已标记为债务）"

# =============================================================================
# 阶段7：打包部署 (Deployment)
# =============================================================================

stage_7:
  id: "STEP7"
  name: "打包部署"
  alias: "发布准备"
  
  entry_conditions:
    required_inputs:
      - "@src/reelforge/ [全部代码]"
      - "@docs/06-validation/test-report.md [质量报告]"
      - "@assets/ [静态资源]"
      - "@prompts/project-config.yaml [部署配置]"
    dependencies_resolved:
      - "STEP6已退出"
      - "质量门禁已通过或债务已登记"
  
  exit_conditions:
    deliverables:
      - "@dist/reelforge-{version}-{platform}.{ext}"
        content: "PyInstaller打包产物（EXE/APP）"
      - "@docs/07-deployment/install-guide.md"
        content: "安装手册（含FFmpeg安装、API密钥配置）"
      - "@docs/07-deployment/packaging-report.md"
        content: "打包过程记录、依赖清单、体积优化说明"
      - "start.bat / start.sh"
        content: "生产环境启动脚本（双击即用）"
  
  blockers:
    - condition: "打包后文件&gt;500MB（未优化）"
      action: "阻断，要求检查冗余依赖（如是否包含PyTorch等无用库）"
      guidance: "使用PyInstaller的--exclude-module排除未使用的大型库"
    - condition: "启动脚本在目标平台测试失败"
      action: "阻断，要求修复路径处理（Windows vs Mac/Linux）"
    - condition: "FFmpeg未正确打包或路径检测失败"
      action: "阻断，要求确认运行时FFmpeg可用性"
    - condition: "API密钥未从代码中清除（安全扫描发现硬编码密钥）"
      action: "阻断，强制要求移至.env文件"
  
  checklists:
    entry:
      - "[ ] STEP6已标记完成"
      - "[ ] 已确认目标平台（Windows/Mac/两者）"
    exit:
      - "[ ] 打包产物体积&lt;500MB（或已标记为债务）"
      - "[ ] 启动脚本在干净环境测试通过"
      - "[ ] 无硬编码API密钥"
      - "[ ] 安装手册包含FFmpeg配置说明"
      - "[ ] Git标签已打（v1.0.0）"

# =============================================================================
# 跨阶段依赖矩阵 (Dependency Matrix)
# =============================================================================

dependency_matrix:
  # 格式：阶段X -&gt; 阶段Y（Y依赖X的交付物）
  STEP1 -&gt; STEP2: ["@docs/01-convergence/scope-locked.md"]
  STEP2 -&gt; STEP3: ["@docs/02-architecture/system-architecture.md"]
  STEP3 -&gt; STEP4: ["@docs/03-design/ui-spec.md"]
  STEP4 -&gt; STEP5: ["@docs/02-architecture/database-schema.sql [FROZEN]"]
  STEP5 -&gt; STEP6: ["@src/reelforge/", "@tests/"]
  STEP6 -&gt; STEP7: ["@docs/06-validation/test-report.md"]
  
  # 关键阻断点可视化
  critical_gateways:
    - location: "STEP4 -&gt; STEP5"
      name: "Schema冻结点"
      description: "数据库Schema一旦冻结，变更需退回Step 4或触发代码重生成"
      rollback_cost: "高（已生成代码可能全部作废）"
    
    - location: "STEP5.1 -&gt; STEP5.2"
      name: "接口确认点"
      description: "接口定义必须人工确认后才生成实现"
      rollback_cost: "低（仅接口签名，无实现代码）"
    
    - location: "STEP5 -&gt; STEP6"
      name: "代码冻结点"
      description: "代码通过质量门禁后进入验证，大规模变更需退回Step 5"
      rollback_cost: "中（已有测试覆盖，修改需同步更新测试）"

# =============================================================================
# 阻断升级路径 (Escalation Path)
# =============================================================================

escalation:
  # 当阻断条件被触发时的处理流程
  
  level_1_auto_fix:
    description: "AI自动修复（3次尝试）"
    applies_to:
      - "语法错误"
      - "类型检查错误（简单补全Any-&gt;具体类型）"
      - "导入路径错误（相对路径-&gt;绝对路径）"
  
  level_2_human_confirm:
    description: "暂停等待人工输入"
    prompt_template: |
      ## 🔴 阻断条件触发
      
      **阶段**: {stage_name}
      **条件**: {blocker_condition}
      **影响**: {impact_description}
      
      **请选择**:
      1. [修复建议] {auto_fix_suggestion} → 回复"确认修复"
      2. [豁免申请] 书面说明理由 → 回复"豁免：{理由}"
      3. [阶段回退] 退回至 {previous_stage} → 回复"退回"
      4. [强制继续] 标记为技术债务 → 回复"债务化：{偿还计划}"
  
  level_3_architecture_review:
    description: "架构级变更（需重新执行前置阶段）"
    applies_to:
      - "Step 5发现需要修改Schema（退回Step 4）"
      - "Step 4发现需要修改架构（退回Step 2）"
      - "Step 2发现需要修改需求（退回Step 1）"
    warning: "此级别触发时，当前阶段所有交付物可能被废弃"

# =============================================================================
# 协议元数据 (Protocol Metadata)
# =============================================================================

protocol_meta:
  version: "1.0"
  compatible_with:
    - "document-protocol.md v1.0"
    - "coding-standards.md v1.1"
    - "project-config.yaml v1.0"
  generated_by: "影工厂初始化流程"
  last_updated: "2026-03-19"