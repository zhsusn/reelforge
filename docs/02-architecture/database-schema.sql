-- ReelForge 数据库模式定义
-- 版本：v1.0
-- 日期：2026-04-02
-- 状态：Step 4 产出 - 数据建模
-- 依赖：@docs/02-architecture/module-design.md, @docs/01-requirements/PRD-v1.0.locked.md

-- 启用 SQLite 外键约束和 WAL 模式（建议）
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

-- =============================================================================
-- 1. 项目表 (projects)
-- =============================================================================
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    -- 项目状态: draft(草稿), processing(处理中), completed(已完成), failed(失败)
    status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft', 'processing', 'completed', 'failed')),
    -- Excel 文件路径（原始输入）
    excel_path TEXT,
    -- 输出视频路径（渲染结果）
    output_video_path TEXT,
    -- 任务队列状态
    task_id TEXT,  -- 关联到 tasks 表

    -- 时间戳
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- 软删除标志
    deleted_at DATETIME,

    -- 索引在表创建后单独定义
);

-- =============================================================================
-- 2. 角色表 (characters)
-- =============================================================================
CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    -- 角色信息
    name TEXT NOT NULL,
    description TEXT,
    -- 首帧锁定信息
    first_frame_path TEXT NOT NULL,  -- 参考图片路径
    character_vector BLOB,  -- 角色特征向量（用于相似度计算）
    similarity_score REAL CHECK(similarity_score >= 0 AND similarity_score <= 100),  -- 相似度分数(0-100)
    -- 音色映射
    voice_profile TEXT DEFAULT 'zh-CN-XiaoxiaoNeural',  -- Edge TTS 音色ID

    -- 时间戳
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at DATETIME,

    -- 外键约束
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- =============================================================================
-- 3. 剧本行表 (script_lines)
-- =============================================================================
CREATE TABLE IF NOT EXISTS script_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    -- 剧本行信息（对应 Excel 模板列）
    sequence INTEGER NOT NULL,  -- 序号
    character_name TEXT NOT NULL,  -- 角色名
    dialogue TEXT NOT NULL,  -- 台词
    emotion TEXT NOT NULL,  -- 情绪
    knowledge_point TEXT,  -- 知识点（可选）
    camera_suggestion TEXT,  -- 运镜建议（可选）
    bgm_suggestion TEXT,  -- BGM建议（可选）
    estimated_duration REAL,  -- 预估时长（秒，可选）

    -- 外键约束（角色通过名称关联）
    -- 注意：character_name 需要与 characters.name 匹配

    -- 时间戳
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- 外键
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    UNIQUE(project_id, sequence)
);

-- =============================================================================
-- 4. 分镜表 (shots)
-- =============================================================================
CREATE TABLE IF NOT EXISTS shots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    script_line_id INTEGER,  -- 关联的剧本行（可为空，如果分镜由 AI 生成）

    -- 分镜信息（对应 module-design.md ShotDescription 模型）
    sequence INTEGER NOT NULL,  -- 分镜序号
    scene_description TEXT NOT NULL,  -- 画面描述（用于 AI 生图）
    dialogue TEXT NOT NULL,  -- 台词
    emotion TEXT NOT NULL,  -- 情绪
    camera_movement TEXT,  -- 运镜建议
    shot_type TEXT,  -- 景别：特写/中景/全景

    -- 生成状态
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'generating', 'completed', 'failed')),
    generated_image_path TEXT,  -- AI生成的图片路径
    tts_audio_path TEXT,  -- TTS生成的音频路径
    actual_duration REAL,  -- 实际时长（秒，librosa计算）
    subtitle_start REAL,  -- 字幕开始时间（秒）
    subtitle_end REAL,  -- 字幕结束时间（秒）

    -- 相似度分数（用于首帧锁定验证）
    similarity_score REAL CHECK(similarity_score >= 0 AND similarity_score <= 100),

    -- 时间戳
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- 外键约束
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (script_line_id) REFERENCES script_lines(id) ON DELETE SET NULL,
    UNIQUE(project_id, sequence)
);

-- =============================================================================
-- 5. 任务队列表 (tasks)
-- =============================================================================
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- 任务信息
    task_id TEXT NOT NULL,  -- 外部任务ID（由 queue_manager 生成）
    project_id INTEGER NOT NULL,

    -- 任务状态（对应 module-design.md TaskStatus 枚举）
    status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ('queued', 'processing', 'completed', 'failed', 'paused', 'cancelled')),

    -- 任务类型
    task_type TEXT NOT NULL CHECK(task_type IN ('excel_parse', 'character_gen', 'storyboard_gen', 'tts_gen', 'video_render')),

    -- 任务优先级（0=最高，数字越大优先级越低）
    priority INTEGER NOT NULL DEFAULT 0 CHECK(priority >= 0),

    -- 进度信息
    progress_current INTEGER DEFAULT 0,  -- 当前进度
    progress_total INTEGER DEFAULT 1,  -- 总进度
    progress_message TEXT,  -- 进度消息

    -- 错误信息（任务失败时记录）
    error_code TEXT,  -- 错误代码（E-XXX-XX格式）
    error_message TEXT,  -- 错误消息
    error_stack TEXT,  -- 错误堆栈

    -- 时间戳
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME,
    completed_at DATETIME,

    -- 外键约束
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    UNIQUE(task_id)
);

-- =============================================================================
-- 6. 系统配置表 (system_config)
-- =============================================================================
CREATE TABLE IF NOT EXISTS system_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- 配置项
    config_key TEXT NOT NULL UNIQUE,
    config_value TEXT,
    config_type TEXT NOT NULL DEFAULT 'string' CHECK(config_type IN ('string', 'int', 'float', 'bool', 'json')),
    description TEXT,
    -- 更新时间
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- 7. API 配额表 (api_quotas)
-- =============================================================================
CREATE TABLE IF NOT EXISTS api_quotas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- 服务标识
    service_name TEXT NOT NULL CHECK(service_name IN ('deepseek', 'tongyi', 'edge_tts')),
    -- 配额信息
    quota_total INTEGER NOT NULL DEFAULT 0,  -- 总配额
    quota_used INTEGER NOT NULL DEFAULT 0,  -- 已使用配额
    quota_reset_date DATE NOT NULL,  -- 配额重置日期
    -- 配置信息
    api_key TEXT,  -- API密钥（加密存储）
    endpoint_url TEXT,  -- 端点URL
    -- 状态
    is_enabled BOOLEAN NOT NULL DEFAULT 1,
    -- 时间戳
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- 索引在表创建后单独定义
);

-- =============================================================================
-- 8. 渲染配置表 (render_configs)
-- =============================================================================
CREATE TABLE IF NOT EXISTS render_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    -- 视频参数（对应 module-design.md RenderConfig 模型）
    resolution_width INTEGER NOT NULL DEFAULT 1080,
    resolution_height INTEGER NOT NULL DEFAULT 1920,
    fps INTEGER NOT NULL DEFAULT 30,
    video_codec TEXT NOT NULL DEFAULT 'libx264',
    video_bitrate TEXT NOT NULL DEFAULT '8000k',
    audio_codec TEXT NOT NULL DEFAULT 'aac',
    audio_bitrate TEXT NOT NULL DEFAULT '192k',
    -- 字幕参数
    subtitle_font_path TEXT,
    subtitle_color TEXT NOT NULL DEFAULT '#FFFFFF',
    subtitle_font_size INTEGER NOT NULL DEFAULT 36,
    -- BGM参数
    bgm_path TEXT,
    bgm_volume REAL NOT NULL DEFAULT 0.2 CHECK(bgm_volume >= 0 AND bgm_volume <= 1),
    -- 时间戳
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- 外键约束
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- =============================================================================
-- 9. 数据库迁移表 (migrations)
-- =============================================================================
CREATE TABLE IF NOT EXISTS migrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- 迁移信息
    version INTEGER NOT NULL,
    name TEXT NOT NULL,
    checksum TEXT NOT NULL,
    -- 状态
    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- 约束
    UNIQUE(version, name)
);

-- =============================================================================
-- 10. 触发器（更新时间戳）
-- =============================================================================

-- 项目表更新时间戳触发器
CREATE TRIGGER IF NOT EXISTS update_projects_timestamp
AFTER UPDATE ON projects
BEGIN
    UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- 角色表更新时间戳触发器
CREATE TRIGGER IF NOT EXISTS update_characters_timestamp
AFTER UPDATE ON characters
BEGIN
    UPDATE characters SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- 分镜表更新时间戳触发器
CREATE TRIGGER IF NOT EXISTS update_shots_timestamp
AFTER UPDATE ON shots
BEGIN
    UPDATE shots SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- 任务表更新时间戳触发器
CREATE TRIGGER IF NOT EXISTS update_tasks_timestamp
AFTER UPDATE ON tasks
BEGIN
    UPDATE tasks SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- 渲染配置表更新时间戳触发器
CREATE TRIGGER IF NOT EXISTS update_render_configs_timestamp
AFTER UPDATE ON render_configs
BEGIN
    UPDATE render_configs SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- =============================================================================
-- 11. 索引创建（表创建后单独定义）
-- =============================================================================

-- 项目表索引
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_created ON projects(created_at);
CREATE INDEX IF NOT EXISTS idx_projects_task ON projects(task_id);
CREATE INDEX IF NOT EXISTS idx_projects_name_deleted ON projects(name, deleted_at);

-- 角色表索引
CREATE INDEX IF NOT EXISTS idx_characters_project ON characters(project_id);
CREATE INDEX IF NOT EXISTS idx_characters_name ON characters(name);
CREATE INDEX IF NOT EXISTS idx_characters_voice ON characters(voice_profile);

-- 剧本行表索引
CREATE INDEX IF NOT EXISTS idx_script_lines_project_seq ON script_lines(project_id, sequence);
CREATE INDEX IF NOT EXISTS idx_script_lines_character ON script_lines(project_id, character_name);

-- 分镜表索引
CREATE INDEX IF NOT EXISTS idx_shots_project_seq ON shots(project_id, sequence);
CREATE INDEX IF NOT EXISTS idx_shots_status ON shots(status);
CREATE INDEX IF NOT EXISTS idx_shots_script_line ON shots(script_line_id);

-- 任务表索引
CREATE INDEX IF NOT EXISTS idx_tasks_project_status ON tasks(project_id, status);
CREATE INDEX IF NOT EXISTS idx_tasks_status_priority ON tasks(status, priority);
CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at);
CREATE INDEX IF NOT EXISTS idx_tasks_type ON tasks(task_type);

-- API配额表索引
CREATE INDEX IF NOT EXISTS idx_api_quotas_service ON api_quotas(service_name, is_enabled);

-- =============================================================================
-- 12. 初始数据插入
-- =============================================================================

-- 插入默认系统配置
INSERT OR IGNORE INTO system_config (config_key, config_value, config_type, description) VALUES
    ('app_name', 'ReelForge (影工厂)', 'string', '应用名称'),
    ('app_version', '0.1.0', 'string', '应用版本'),
    ('max_concurrent_tasks', '3', 'int', '最大并发任务数（对应 queue_manager 最大队列大小）'),
    ('default_voice_profile', 'zh-CN-XiaoxiaoNeural', 'string', '默认TTS音色'),
    ('similarity_threshold', '90', 'int', '角色相似度阈值（0-100）'),
    ('enable_auto_retry', 'true', 'bool', '是否启用自动重试'),
    ('max_retry_attempts', '3', 'int', '最大重试次数'),
    ('workspace_path', './workspace', 'string', '工作空间路径');

-- 插入 API 配额初始记录（每月重置）
INSERT OR IGNORE INTO api_quotas (service_name, quota_total, quota_used, quota_reset_date, is_enabled) VALUES
    ('deepseek', 5000000, 0, date('now', 'start of month', '+1 month'), 1),  -- DeepSeek 免费额度 5M tokens/月
    ('tongyi', 1000, 0, date('now', '+1 day'), 1),  -- 通义万相假设每日1000积分
    ('edge_tts', 0, 0, date('now', '+1 month'), 1);  -- Edge TTS 免费使用

-- =============================================================================
-- 13. 视图（常用查询）
-- =============================================================================

-- 项目概览视图
CREATE VIEW IF NOT EXISTS project_overview AS
SELECT
    p.id,
    p.name,
    p.status,
    p.created_at,
    p.updated_at,
    (SELECT COUNT(*) FROM characters c WHERE c.project_id = p.id AND c.deleted_at IS NULL) as character_count,
    (SELECT COUNT(*) FROM script_lines sl WHERE sl.project_id = p.id) as script_line_count,
    (SELECT COUNT(*) FROM shots s WHERE s.project_id = p.id AND s.status = 'completed') as completed_shots,
    (SELECT COUNT(*) FROM shots s WHERE s.project_id = p.id) as total_shots,
    (SELECT status FROM tasks t WHERE t.project_id = p.id ORDER BY t.created_at DESC LIMIT 1) as latest_task_status
FROM projects p
WHERE p.deleted_at IS NULL;

-- 角色统计视图
CREATE VIEW IF NOT EXISTS character_stats AS
SELECT
    c.project_id,
    c.name,
    c.voice_profile,
    c.similarity_score,
    (SELECT COUNT(*) FROM script_lines sl WHERE sl.project_id = c.project_id AND sl.character_name = c.name) as dialogue_count,
    (SELECT COUNT(*) FROM shots s WHERE s.project_id = c.project_id AND s.dialogue LIKE '%' || c.name || '%') as shot_count
FROM characters c
WHERE c.deleted_at IS NULL;

-- 任务队列视图
CREATE VIEW IF NOT EXISTS task_queue AS
SELECT
    t.task_id,
    t.project_id,
    p.name as project_name,
    t.status,
    t.task_type,
    t.priority,
    t.progress_current,
    t.progress_total,
    ROUND((t.progress_current * 100.0 / NULLIF(t.progress_total, 0)), 1) as progress_percent,
    t.progress_message,
    t.created_at,
    t.started_at,
    t.completed_at
FROM tasks t
LEFT JOIN projects p ON t.project_id = p.id
WHERE p.deleted_at IS NULL
ORDER BY
    CASE t.status
        WHEN 'processing' THEN 1
        WHEN 'queued' THEN 2
        WHEN 'paused' THEN 3
        ELSE 4
    END,
    t.priority ASC,
    t.created_at ASC;

-- =============================================================================
-- 14. 数据完整性检查约束
-- =============================================================================

-- 检查任务状态与时间戳的一致性
-- SQLite 触发器语法不同，暂时注释掉复杂的触发器
-- 检查任务状态与时间戳的一致性
-- CREATE TRIGGER IF NOT EXISTS check_task_timestamps
-- BEFORE UPDATE ON tasks
-- FOR EACH ROW
-- BEGIN
--     -- 状态变为 processing 时设置 started_at
--     SELECT CASE
--         WHEN NEW.status = 'processing' AND (OLD.status IS NULL OR OLD.status != 'processing') AND NEW.started_at IS NULL THEN
--             RAISE(ABORT, '触发器逻辑需要应用程序层实现');
--     END;
-- END;

-- 检查分镜状态与生成路径的一致性
CREATE TRIGGER IF NOT EXISTS check_shot_completion
BEFORE UPDATE ON shots
FOR EACH ROW
WHEN NEW.status = 'completed' AND OLD.status != 'completed'
BEGIN
    SELECT
        CASE
            WHEN NEW.generated_image_path IS NULL THEN
                RAISE(ABORT, 'Completed shot must have generated_image_path')
            WHEN NEW.tts_audio_path IS NULL THEN
                RAISE(ABORT, 'Completed shot must have tts_audio_path')
            WHEN NEW.actual_duration IS NULL OR NEW.actual_duration <= 0 THEN
                RAISE(ABORT, 'Completed shot must have valid actual_duration')
        END;
END;

-- =============================================================================
-- 表结构说明
-- =============================================================================

/*
数据流关系图：

projects (1) ← (many) characters
    ↓
script_lines (many) ← (1) projects
    ↓
shots (many) ← (1) projects
    ↑
script_lines (optional FK)

projects (1) ← (many) tasks
projects (1) → (1) render_configs

核心业务流：
1. 用户创建项目 (projects) → 上传Excel
2. 解析Excel → script_lines 表
3. 创建角色 (characters) → 上传首帧图片
4. AI生成分镜 (shots) → 关联 characters 和 script_lines
5. TTS生成音频 → shots.tts_audio_path
6. 视频渲染 → projects.output_video_path
7. 任务队列管理 (tasks) 跟踪整个过程

索引策略：
- 所有外键都有索引
- 常用查询字段有索引（status, created_at等）
- 复合索引用于多字段查询

性能考虑：
- 软删除使用 deleted_at 字段而非物理删除
- WAL模式提高并发性能
- 适当使用触发器维护数据一致性
*/