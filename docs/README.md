# ReelForge 项目文档索引

## 文档结构

```
docs/
├── 01-requirements/          # 需求文档
├── 02-architecture/          # 架构文档
├── 03-design/                # 设计文档
├── 04-development/           # 开发文档
├── 06-validation/           # 验证文档
├── 06-specifications/       # 规范文档
├── 07-references/           # 参考文档
└── _archive/                # 归档文档
```

## 核心文档

### 1. 需求文档 (`01-requirements/`)
- `PRD-v1.0.locked.md` - 产品需求文档（锁定版本）

### 2. 架构文档 (`02-architecture/`)
- `tech-stack-decision.md` - 技术栈决策（ADR文档）
- `module-design.md` - 模块设计与接口定义
- `dependency-graph.md` - 模块依赖关系图
- `api-contract.yaml` - API接口定义
- `database-schema.sql` - 数据库模式定义
- `database-schema-simple.sql` - 简化数据库模式（测试用）
- `interface-definitions/` - 模块接口定义（.locked.py文件）

### 3. 设计文档 (`03-design/`)
- `ui-spec.md` - UI设计规范

### 4. 开发文档 (`04-development/`)
- `CLAUDE.md` - Claude Code开发指南
- `session-log.md` - 开发会话记录
- `decisions.md` - 开发决策记录
- `project-status/` - 项目状态报告
  - `2026-04-02-init-report.md` - 项目初始化报告
  - `2026-04-03-status-summary.md` - 项目状态总结
  - `sync-mechanism-report.md` - 同步机制验证报告

### 5. 验证文档 (`06-validation/`)
- `code-exploration-report.md` - 代码探索报告
- `sync-mechanism-test.md` - 同步机制测试报告

### 6. 规范文档 (`06-specifications/`)
- `coding-standards.md` - 编码规范（类型注解、错误码等）
- `document-protocol.md` - 文档协议
- `phase-checkpoints.md` - 开发阶段检查点
- `auto-save-rules.md` - 自动保存规则

### 7. 参考文档 (`07-references/`)
- `project-config.yaml` - 项目配置（API配额、技术约束等）

### 8. 归档文档 (`_archive/`)
- `pilot/` - 试点模块开发过程文档
- `tech-specs/` - 技术规格文档（历史）

## 开发流程

### 接口先行开发
1. 定义模块接口（`interface-definitions/{module}-interface.py`）
2. 锁定接口（重命名为`{module}-interface.v1.locked.py`）
3. 实现模块代码（必须匹配接口签名）
4. 编写测试（覆盖率≥80%）

### 质量门禁
- 类型检查：`mypy src/reelforge --strict`（必须0错误）
- 测试覆盖率：`pytest --cov=src/reelforge`（必须≥80%）
- 复杂度限制：函数≤50行，复杂度<10
- 代码规范：Black格式化，Ruff检查

### 禁止项
- ❌ 禁止使用 `async/await`
- ❌ 禁止使用外部数据库（仅限SQLite）
- ❌ 禁止循环依赖
- ❌ 禁止通配符导入

## 重要文档引用

| 文件 | 用途 | 路径 |
|------|------|------|
| `CLAUDE.md` | Claude开发指南 | `CLAUDE.md` |
| `project-config.yaml` | 项目配置 | `docs/07-references/project-config.yaml` |
| `coding-standards.md` | 编码规范 | `docs/06-specifications/coding-standards.md` |
| `module-design.md` | 模块设计 | `docs/02-architecture/module-design.md` |

## 快速开始

1. **安装**：`pip install -e ".[dev]"`
2. **配置**：参考 `docs/07-references/project-config.yaml`
3. **开发**：遵循 `docs/04-development/CLAUDE.md` 指南
4. **测试**：`pytest --cov=src/reelforge`

## 文档更新规则

1. **代码变更时同步更新文档**（参见 `CLAUDE.md` 同步机制）
2. **接口锁定后不能修改**（需要RFC流程）
3. **决策记录在 `decisions.md`**
4. **进度报告存入 `project-status/`**

---
*最后更新：2026-04-03*
*文档整理状态：已完成*