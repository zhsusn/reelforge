-- ReelForge 简化数据库模式定义
-- 只包含核心表结构用于测试

-- 启用 SQLite 外键约束和 WAL 模式
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
    status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft', 'processing', 'completed', 'failed')),
    excel_path TEXT,
    output_video_path TEXT,
    task_id TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at DATETIME
);

-- =============================================================================
-- 2. 角色表 (characters)
-- =============================================================================
CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    first_frame_path TEXT NOT NULL,
    character_vector BLOB,
    similarity_score REAL CHECK(similarity_score >= 0 AND similarity_score <= 100),
    voice_profile TEXT DEFAULT 'zh-CN-XiaoxiaoNeural',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at DATETIME,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- =============================================================================
-- 3. 剧本行表 (script_lines)
-- =============================================================================
CREATE TABLE IF NOT EXISTS script_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    sequence INTEGER NOT NULL,
    character_name TEXT NOT NULL,
    dialogue TEXT NOT NULL,
    emotion TEXT NOT NULL,
    knowledge_point TEXT,
    camera_suggestion TEXT,
    bgm_suggestion TEXT,
    estimated_duration REAL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    UNIQUE(project_id, sequence)
);

-- =============================================================================
-- 4. 分镜表 (shots)
-- =============================================================================
CREATE TABLE IF NOT EXISTS shots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    script_line_id INTEGER,
    sequence INTEGER NOT NULL,
    scene_description TEXT NOT NULL,
    dialogue TEXT NOT NULL,
    emotion TEXT NOT NULL,
    camera_movement TEXT,
    shot_type TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'generating', 'completed', 'failed')),
    generated_image_path TEXT,
    tts_audio_path TEXT,
    actual_duration REAL,
    subtitle_start REAL,
    subtitle_end REAL,
    similarity_score REAL CHECK(similarity_score >= 0 AND similarity_score <= 100),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (script_line_id) REFERENCES script_lines(id) ON DELETE SET NULL,
    UNIQUE(project_id, sequence)
);

-- =============================================================================
-- 5. 任务队列表 (tasks)
-- =============================================================================
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    project_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ('queued', 'processing', 'completed', 'failed', 'paused', 'cancelled')),
    task_type TEXT NOT NULL CHECK(task_type IN ('excel_parse', 'character_gen', 'storyboard_gen', 'tts_gen', 'video_render')),
    priority INTEGER NOT NULL DEFAULT 0 CHECK(priority >= 0),
    progress_current INTEGER DEFAULT 0,
    progress_total INTEGER DEFAULT 1,
    progress_message TEXT,
    error_code TEXT,
    error_message TEXT,
    error_stack TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME,
    completed_at DATETIME,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    UNIQUE(task_id)
);

-- =============================================================================
-- 6. 系统配置表 (system_config)
-- =============================================================================
CREATE TABLE IF NOT EXISTS system_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_key TEXT NOT NULL UNIQUE,
    config_value TEXT,
    config_type TEXT NOT NULL DEFAULT 'string' CHECK(config_type IN ('string', 'int', 'float', 'bool', 'json')),
    description TEXT,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- 7. API 配额表 (api_quotas)
-- =============================================================================
CREATE TABLE IF NOT EXISTS api_quotas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_name TEXT NOT NULL CHECK(service_name IN ('deepseek', 'tongyi', 'edge_tts')),
    quota_total INTEGER NOT NULL DEFAULT 0,
    quota_used INTEGER NOT NULL DEFAULT 0,
    quota_reset_date DATE NOT NULL,
    api_key TEXT,
    endpoint_url TEXT,
    is_enabled BOOLEAN NOT NULL DEFAULT 1,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(service_name, quota_reset_date)
);

-- =============================================================================
-- 8. 渲染配置表 (render_configs)
-- =============================================================================
CREATE TABLE IF NOT EXISTS render_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    resolution_width INTEGER NOT NULL DEFAULT 1080,
    resolution_height INTEGER NOT NULL DEFAULT 1920,
    fps INTEGER NOT NULL DEFAULT 30,
    video_codec TEXT NOT NULL DEFAULT 'libx264',
    video_bitrate TEXT NOT NULL DEFAULT '8000k',
    audio_codec TEXT NOT NULL DEFAULT 'aac',
    audio_bitrate TEXT NOT NULL DEFAULT '192k',
    subtitle_font_path TEXT,
    subtitle_color TEXT NOT NULL DEFAULT '#FFFFFF',
    subtitle_font_size INTEGER NOT NULL DEFAULT 36,
    bgm_path TEXT,
    bgm_volume REAL NOT NULL DEFAULT 0.2 CHECK(bgm_volume >= 0 AND bgm_volume <= 1),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
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