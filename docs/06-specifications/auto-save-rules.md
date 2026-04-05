# 影工厂自动保存规则 (Auto-Save Rules)
# 文件路径：prompts/auto-save-rules.md
# 版本：v1.0 | 2026-03-19
# 设计目标：低交互频率、三层触发、批量归档

# =============================================================================
# 1. 三层触发策略 (Three-Tier Trigger Strategy)
# =============================================================================

trigger_strategy:
  name: "低交互自动保存"
  paradigm: "关键决策捕获 + 批量归档 + 零干扰默认"
  
  # -------------------------------------------------------------------------
  # 层级1：自动缓冲 (Auto-Buffer) - 零干扰
  # -------------------------------------------------------------------------
  tier_1_auto:
    name: "自动缓冲层"
    interference_level: "zero"  # 对用户零打扰
    trigger_events:  # 触发条件（自然决策点）
      - "架构决策确定（如'确认使用SQLite'）"
      - "技术选型变更（如'改用Streamlit替代Gradio'）"
      - "范围冻结（如'P0功能锁定为5个'）"
      - "接口定义确认（如'确认parser.py的函数签名'）"
      - "异常处理方案确定（如'API限流时降级至Ken Burns'）"
      - "检测到代码规范违反（如函数长度&gt;50行）"
    
    buffer_mechanism:
      type: "memory_ring_buffer"  # 内存环形缓冲区
      capacity: 50  # 最多缓存50条决策记录
      deduplication: true  # 自动去重（相同决策只保留最后一条）
      
      # 🔧 可调参数：防抖缓冲时长（默认30秒，可调整为10-60秒）
      debounce_duration: 30  # 秒，决策输入停止后30秒才写入缓冲区
      # 调整说明：如觉得30秒太长可改为10秒（更敏感），或60秒（更宽松）
      
      persistence: "session_only"  # 仅当前会话有效，会话结束自动清空
      format: "structured_json"   # 结构化JSON，便于后续批量处理
    
    ai_behavior: |
      1. 实时监听对话中的决策信号（如"确定"、"改为"、"锁定"等关键词）
      2. 决策发生后等待{debounce_duration}秒（防抖期）
      3. 防抖期内无新决策 → 写入缓冲区
      4. 完全不提示用户，后台静默执行

  # -------------------------------------------------------------------------
  # 层级2：半自动批量 (Semi-Auto Batch) - 低干扰（核心机制）
  # -------------------------------------------------------------------------
  tier_2_semi_auto:
    name: "半自动批量层"
    interference_level: "low"  # 低打扰，批量确认
    trigger_conditions:  # 触发条件（满足任一即触发）
      temporal:
        - "功能模块完成（如'parser.py已生成并通过测试'）"
        - "阶段里程碑达成（如'Step 4 Schema设计完成'）"
        - "代码生成批次结束（如'已生成3个模块，共15个文件'）"
      
      interval_based:
        # 🔧 可调参数：定时触发间隔（默认30分钟，可调整为10-60分钟）
        max_interval: 30  # 分钟，距离上次保存超过30分钟强制触发
        # 调整说明：高频开发可调为10分钟，专注长考可调为60分钟
      
      buffer_based:
        max_buffered_items: 10  # 缓冲区积累10条决策立即触发
        max_buffered_size: "50KB"  # 或缓冲区达50KB触发
    
    interaction_mode:
      type: "batch_review"
      ui_template: |
        =========================================
        💾 检测到 [{module_name}] 已完成，积累 {n} 条决策
        
        【待归档内容】
        📄 decisions.md 追加：
           - ADR-{id}: 使用SQLite替代PostgreSQL（决策点）
           - 债务记录: 首帧降级策略待完善
        
        📄 progress.md 更新：
           - [x] Step 4 Schema设计 (100%)
           - [ ] Step 5.1 接口定义 (等待中)
           - 阻塞项: 无
        
        📄 sessions/2026-03-19.md 追加：
           - 详细对话片段（3条关键决策）
        
        【执行？】[确认] [修改] [跳过] [查看详情]
        =========================================
      
      timeout_behavior: "prompt_after_delay"  # 延迟后提示，非强制阻断
      default_action_on_timeout: "skip"  # 超时无响应默认跳过（保守策略）
      timeout_seconds: 60  # 给用户60秒确认时间
    
    human_options:
      - "确认": "立即执行批量保存，清空缓冲区"
      - "修改": "进入编辑模式，调整保存内容（如删减敏感决策）"
      - "跳过": "丢弃当前缓冲区，继续开发（风险：决策丢失）"
      - "保存": "立即强制保存（等效于Tier 3手动触发）"

  # -------------------------------------------------------------------------
  # 层级3：手动强制 (Manual Override) - 用户主导
  # -------------------------------------------------------------------------
  tier_3_manual:
    name: "手动强制层"
    interference_level: "user_driven"  # 完全由用户触发
    
    trigger_commands:  # 用户可随时输入
      - "保存"
      - "归档"
      - "persist"
      - "checkpoint"
      - "💾"  # emoji快捷指令
    
    scope_options:
      - "quick": "仅保存decisions.md（轻量级，1秒完成）"
      - "full": "完整归档（decisions + progress + sessions + 代码快照）"
      - "stage": "标记阶段完成（如'Step 4结束'），触发阶段总结归档"
    
    immediate_execution: true  # 立即执行，无缓冲
    bypass_buffer: true          # 无视当前缓冲区状态
    
    session_end_auto_trigger:  # 会话结束时自动建议
      enabled: true
      prompt: "会话即将结束，是否一键归档全部内容？[Y/n]"

# =============================================================================
# 2. 缓冲区管理 (Buffer Management)
# =============================================================================

buffer_management:
  # 内存缓冲区配置
  memory_buffer:
    max_entries: 50
    max_age: "2h"  # 条目超过2小时自动刷新到持久化（防丢失）
    compression: false  # 不压缩，便于实时查看
    
  # 持久化暂存区（半自动确认前）
  staging_area:
    path: ".auto-save-staging/"
    files:
      - "decisions.pending.json"  # 待确认的决策
      - "progress.pending.md"     # 待确认的进展
      - "session.pending.md"      # 待确认的会话片段
    
    cleanup: "on_confirm"  # 确认后自动清理，跳过则保留供下次批量

  # 紧急恢复机制
  crash_recovery:
    enabled: true
    interval: "5m"  # 每5分钟自动将缓冲区备份到.workspace/.auto-save-backup/
    max_backups: 3  # 保留最近3个备份点

# =============================================================================
# 3. 文件归档规范 (Archiving Standards)
# =============================================================================

archive_structure:
  # 与coding-standards.md的目录结构保持一致
  base_path: "docs/"
  
  files:
    decisions:
      path: "docs/decisions.md"
      format: "markdown_log"  # 追加模式
      trigger_tiers: [1, 2, 3]  # 所有层级都写入
      content_template: |
        ## [{timestamp}] {decision_type}: {title}
        **阶段**: {current_stage}
        **背景**: {context_summary}
        **决策**: {decision_content}
        **理由**: {rationale}
        **影响**: {impact_analysis}
        **状态**: 已确认/待验证/已撤销
    
    progress:
      path: "docs/progress.md"
      format: "kanban_board"  # 看板格式
      trigger_tiers: [2, 3]   # 半自动和手动触发
      sections:
        - "已完成"
        - "进行中 ({current_stage})"
        - "阻塞项"
        - "待办"
    
    sessions:
      path: "docs/sessions/{date}.md"
      format: "chronological_log"  # 时序日志
      trigger_tiers: [2, 3]
      rotation: "daily"  # 按日期分文件，避免单文件过大
      content_template: |
        # 会话记录 {date} ({session_id})
        ## 关键决策摘要（{n}条）
        {tier_1_buffer_summary}
        
        ## 详细对话片段
        {selected_transcripts}
        
        ## 产出物清单
        - {file_path} ({status})
        
        ## 技术债务新增
        - {debt_items}
    
    code_snapshots:  # 可选：重要里程碑的代码快照
      enabled: true
      path: ".snapshots/{timestamp}-{stage}/"
      trigger: "tier_3_manual_only"  # 仅手动触发，避免磁盘膨胀
      max_snapshots: 5  # 保留最近5个手动快照

# =============================================================================
# 4. 决策内容捕获规范 (Content Capture Rules)
# =============================================================================

capture_rules:
  # 自动捕获的信号词（Tier 1触发）
  decision_signals:
    strong_commitment:
      - "确定使用"
      - "确认选择"
      - "锁定"
      - "冻结"
      - "采纳方案"
    change_direction:
      - "改为"
      - "调整为"
      - "替代"
      - "回退到"
    rejection:
      - "排除"
      - "不采用"
      - "放弃"
    technical_debt:
      - "临时方案"
      - "TODO"
      - "先这样"
      - "后续优化"
    blocker_identified:
      - "阻塞"
      - "卡点"
      - "无法继续"
  
  # 捕获内容过滤（避免保存敏感信息）
  filters:
    exclude_patterns:
      - "api_key.*=.*sk-"      # API密钥（已脱敏的除外）
      - "password.*="          # 密码
      - ".*@.*\\.com"          # 邮箱（可选）
    max_line_length: 200        # 超长行截断（避免base64图片等）
    max_message_length: 1000    # 单条决策最大长度

  # 去重规则（相同决策不重复保存）
  deduplication:
    key_fields: ["decision_type", "title"]  # 基于类型+标题去重
    similarity_threshold: 0.9  # 文本相似度&gt;90%视为重复
    keep_strategy: "last"    # 保留最后一条（更新理由）

# =============================================================================
# 5. 交互频率控制 (Interaction Frequency Control)
# =============================================================================

frequency_control:
  # 全局冷却期（防止连续触发）
  global_cooldown: "5m"  # 无论何种触发，5分钟内不重复提示
  
  # 分层静默期（Tier 2特有）
  tier_2_quiet_hours:  # 专注时段不打扰（可选）
    enabled: false     # 默认关闭，开启后22:00-08:00不触发半自动保存
    hours: [22, 23, 0, 1, 2, 3, 4, 5, 6, 7, 8]
  
  # 批量大小自适应（根据开发强度调整）
  adaptive_batching:
    enabled: true
    high_velocity:  # 高强度开发（&gt;10条决策/小时）
      threshold: 10
      action: "缩短interval至10分钟，快速归档防溢出"
    low_velocity:   # 低强度（&lt;2条/小时）
      threshold: 2
      action: "延长interval至60分钟，减少打扰"

# =============================================================================
# 6. 可调参数总览 (Tunable Parameters)
# =============================================================================

tunable_parameters:
  # 🔧 关键可调参数（用户可在此修改）
  
  - name: "防抖缓冲时长 (debounce_duration)"
    location: "tier_1_auto.buffer_mechanism"
    current: 30  # 秒
    range: [10, 60]
    description: "决策发生后等待多久写入缓冲区（防抖）"
    adjust_guidance: "如觉得保存太敏感（频繁写缓冲区），增大至60秒；如担心丢失，减小至10秒"
  
  - name: "半自动触发间隔 (max_interval)"
    location: "tier_2_semi_auto.trigger_conditions.interval_based"
    current: 30  # 分钟
    range: [10, 60]
    description: "强制批量确认的最大间隔时间"
    adjust_guidance: "快速迭代期可调10分钟（高频确认）；深度设计期可调60分钟（减少打断）"
  
  - name: "缓冲区容量 (max_entries)"
    location: "memory_buffer"
    current: 50
    range: [20, 100]
    description: "内存中缓存的最大决策条目数"
    adjust_guidance: "长会话（&gt;3小时）可调大至100；短会话保持50"
  
  - name: "批量确认超时 (timeout_seconds)"
    location: "tier_2_semi_auto.interaction_mode"
    current: 60  # 秒
    range: [30, 300]
    description: "等待用户响应的时间，超时后默认跳过"
    adjust_guidance: "如常离开座位可调至300秒（5分钟），快速开发保持60秒"

# =============================================================================
# 7. 协议兼容性 (Protocol Compatibility)
# =============================================================================

compatibility:
  with_document_protocol: |
    - 所有归档路径遵循@docs/xxx.md语法
    - 版本锁定机制与auto-save独立，保存前检查文档状态
  
  with_phase_checkpoints: |
    - 阶段完成自动触发Tier 2批量确认
    - 阻断条件触发时，立即执行Tier 3强制保存（防丢失）
    - Step 5接口定义确认后，自动归档到decisions.md
  
  with_coding_standards: |
    - 保存内容遵循coding-standards.md（如代码片段长度限制）
    - Src-Layout路径规范（@src/语法）

# =============================================================================
# 使用说明 (Usage Notes)
# =============================================================================

usage:
  - "默认配置已针对影工厂7步流程优化，一般无需调整"
  - "如需调整，修改上方'tunable_parameters'后告知AI：'已更新auto-save-rules.md，请按新参数执行'"
  - "临时覆盖：单次对话中可说'这次用10秒缓冲'或'跳过下次批量确认'"
  - "紧急保存：随时说'保存'触发Tier 3手动归档"