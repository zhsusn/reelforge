# 文档整理计划

## 1. 当前文档问题分析

### 1.1 重复文档
1. **根目录报告文档**：
   - `PROJECT_INIT_REPORT.md` (与 `docs/01-convergence/project-ready-for-development.md` 重叠)
   - `PROJECT_STATUS_SUMMARY.md` (阶段性进度报告)
   - `STEP3_SYNC_MECHANISM_REPORT.md` (与 CLAUDE.md 中的同步机制内容重叠)
   - `docs/session-log.md` (开发会话记录)

2. **临时/过程文档**：
   - `docs/pilot/` 目录下的所有文档（试点模块开发过程文档）
   - `docs/tech-specs/m02-database-spec.md` (数据库技术规格，已完成)

### 1.2 过时/不适用文档
1. 中文命名文档：`docs/02-architecture/织影技术架构设计文档_V1.0.md`
2. 临时文件：`docs/05-coding/新建 文本文档.txt`, `docs/start.txt`
3. 空/无效文件：`docs/01-convergence/feasibility-report.md` (只有1行)

### 1.3 需要保持的文档
1. **架构文档**：
   - `docs/02-architecture/tech-stack-decision.md` (技术栈决策)
   - `docs/02-architecture/module-design.md` (模块设计)
   - `docs/02-architecture/dependency-graph.md` (依赖关系图)

2. **需求文档**：
   - `docs/01-requirements/PRD-v1.0.locked.md` (产品需求文档)

3. **设计文档**：
   - `docs/03-design/ui-spec.md` (UI设计规范)

4. **规范文档**：
   - `prompts/` 目录下的所有文档 (项目规范)

5. **实现文档**：
   - `CLAUDE.md` (Claude开发指南)
   - `README.md` (项目简介)

## 2. 目标目录结构

```
docs/
├── 01-convergence/           # 项目收敛文档
├── 01-requirements/          # 需求文档（合并了02-requirements）
├── 02-architecture/          # 架构文档 + 接口定义
├── 03-design/                # 设计文档
├── 04-development/           # 开发文档
├── 06-validation/            # 验证文档
├── 06-specifications/        # 规范文档
├── 07-references/            # 参考文档
├── _archive/                 # 归档文档
├── README.md                # 文档索引
└── document-consolidation-plan.md  # 整理计划
```

prompts/目录可以删除，内容移动到docs/06-specifications/

## 3. 移动计划

### 3.1 移动到del目录（无用文档）
1. `docs/02-architecture/织影技术架构设计文档_V1.0.md`
2. `docs/05-coding/新建 文本文档.txt`
3. `docs/start.txt`
4. `docs/01-convergence/feasibility-report.md` (只有1行)

### 3.2 移动到docs/_archive（归档文档）
1. `docs/pilot/` 整个目录
2. `docs/tech-specs/` 整个目录

### 3.3 移动到新目录结构
1. 从根目录移动：
   - `CLAUDE.md` → `docs/04-development/CLAUDE.md`
   - `PROJECT_INIT_REPORT.md` → `docs/04-development/project-status/2026-04-02-init-report.md`
   - `PROJECT_STATUS_SUMMARY.md` → `docs/04-development/project-status/2026-04-03-status-summary.md`
   - `STEP3_SYNC_MECHANISM_REPORT.md` → `docs/04-development/project-status/sync-mechanism-report.md`

2. 从prompts移动：
   - `prompts/coding-standards.md` → `docs/06-specifications/coding-standards.md`
   - `prompts/document-protocol.md` → `docs/06-specifications/document-protocol.md`
   - `prompts/phase-checkpoints.md` → `docs/06-specifications/phase-checkpoints.md`
   - `prompts/promptsauto-save-rules.md` → `docs/06-specifications/auto-save-rules.md`
   - `prompts/project-config.yaml` → `docs/07-references/project-config.yaml`

3. 其他移动：
   - `docs/session-log.md` → `docs/04-development/session-log.md`
   - `docs/decisions.md` → `docs/04-development/decisions.md`

## 4. 创建必要的索引文件

### 4.1 创建docs/README.md
项目文档索引

### 4.2 更新CLAUDE.md中的文档引用路径

## 5. 验证步骤
1. 所有移动后的文件路径有效
2. 引用关系正确
3. 删除无用文件前备份
4. 更新相关文档中的引用路径