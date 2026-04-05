# ReelForge 第三步：同步机制建立报告

**生成日期**: 2026-04-02  
**报告版本**: v1.0  
**操作**: CLAUDE.md 追加同步规则章节

---

## ✅ 第三步完成状态

### 已执行操作

| 操作项 | 状态 | 详情 |
|--------|------|------|
| CLAUDE.md 打开 | ✅ | 读取 368 行完整文件 |
| 同步机制章节追加 | ✅ | 新增 ~600 行规则说明 |
| 规则编号与格式 | ✅ | 7 个主规则 + 子规则 + 命令参考 |
| 文件保存 | ✅ | 成功提交到项目根目录 |

---

## 📋 新增规则摘要（7 个主规则）

### 1️⃣ **接口先行原则** (Interface-First)
- 所有实现前必须先生成冻结接口定义 (`.locked.py`)
- 接口包含：类型提示、文档字符串、异常定义（无实现）
- mypy 检查必须通过（0 错误）
- 需人工审核后重命名为 `.v1.locked.py` 来冻结

**工作流**:
```
接口定义 → mypy 检查 → 人工审核 → 版本冻结(.locked.py)
   ↓                                        ↓
   └─→ 实现代码（必须匹配接口签名）
```

---

### 2️⃣ **冻结契约锁定机制** (Contract Lock)
- 所有 `.locked.py` 文件禁止直接修改
- 修改需通过 RFC 流程：创建 RFC 文档 → 影响分析 → 人工审核 → 版本升级

**保护机制**:
- ✅ 可读取和实现
- ❌ 不可修改
- ❌ 不可删除
- 变更流程：RFC-2026-NNN → 版本升级 v1→v2 → 重新冻结

**RFC 文档位置**: `docs/RFC-{YYYY}-{NNN}-{topic}.md`

---

### 3️⃣ **强制质量门禁** (Quality Gates)

三重检查机制（缺一不可）：

#### Gate 1: 类型检查（mypy strict）
```bash
mypy src/reelforge --strict
# 必须：0 错误
```
- ✅ 所有参数有类型
- ✅ 所有返回值有类型
- ✅ 无 `Any` 类型（除非有 `# type: ignore` 注释）
- ✅ 所有类属性有类型

#### Gate 2: 单元测试覆盖率（≥ 80%）
```bash
pytest --cov=src/reelforge --cov-report=term-missing
# 覆盖要求：≥ 80%
```
- ✅ 正常路径（happy path）
- ✅ 错误路径（异常、边界条件）
- ✅ 边界值（空输入、最大值）
- ✅ 模块集成（含 mock）

#### Gate 3: 代码复杂度
```bash
# 自动检查
- 函数长度 ≤ 50 行
- 圈复杂度 < 10
- 类长度 ≤ 300 行
- 文件长度 ≤ 800 行
```

**门禁规则**: 如果任何门禁失败，代码禁止输出（需重新编写）

---

### 4️⃣ **文档同步策略** (Doc Sync)

代码变更自动触发文档更新（提交前完成）：

| 代码变更类型 | 同步文档 | 验证方式 |
|:---|:---|:---|
| 新增 API 方法 | `docs/02-architecture/api-contract.yaml` | 有效 YAML |
| 新增表/列 | `docs/02-architecture/database-schema.sql` | SQL 语法有效 |
| 新/修改模块 | `docs/02-architecture/module-design.md` | DAG 无环 |
| 依赖关系变化 | `docs/02-architecture/dependency-graph.md` | 无循环引用 |
| 新错误码 | `prompts/coding-standards.md` 第 2 节 | 码格式匹配 |
| P0/P1 功能完成 | `docs/01-requirements/PRD-v1.0.locked.md` | 标记为 DONE |
| 技术债务完清 | `docs/02-architecture/tech-stack-decision.md` | 移除 TD 项 |

**例**: 添加角色 CRUD 模块
```
代码: models/character.py
  ↓ 触发
数据库: database-schema.sql
  ├─ ALTER TABLE characters...
  └─ Run: sqlite3 syntax-check
  ↓ 触发
模块设计: module-design.md
  ├─ 添加 character 方法签名
  ├─ 添加异常定义
  └─ Run: mypy interface-definitions/character-interface.py
  ↓ 触发
依赖图: dependency-graph.md
  └─ 添加节点、边，验证无环
  ↓
代码可提交
```

---

### 5️⃣ **版本与发布锁定管理** (Version Locking)

模块生命周期：

```
草稿阶段：
  docs/05-coding/interface-definitions/parser-interface.py
  (可改动，未冻结)
   ↓
审核批准：
  重命名 → parser-interface.v1.locked.py
  (冻结，不可修改)
   ↓
生产使用：
  src/reelforge/core/parser.py 实现
  接口签名锁定，只允许内部实现改进
   ↓
功能增强：
  若需修改签名：
    创建 RFC-2026-NNN
    批准后创建 v2.locked.py
    更新实现代码
    标记 v1 为弃用（提供迁移路径）
```

---

### 6️⃣ **集成检查点** (Integration Checkpoints)

代码合并前的验证清单：

```bash
# 1. 无导入错误
python -c "from reelforge.app import *; from reelforge.core import *; from reelforge.models import *; from reelforge.services import *"

# 2. 数据库 schema 与接口匹配
# (database 模块审查时自动检查)

# 3. API 客户端都有 @retry
grep -r "@retry" src/reelforge/services/
# 应包含：deepseek_client.py, tongyi_client.py, tts_client.py

# 4. 无 async/await（禁止模式）
grep -r "async def\|await\|asyncio" src/reelforge/
# 应返回空（无匹配）

# 5. 无通配符导入
grep -r "^from .* import \*" src/reelforge/
# 应返回空

# 6. 错误码定义完整
grep -ro "E-[0-9]{3}-[0-9]{2}" src/reelforge/ | sort | uniq
# 交叉检查 prompts/coding-standards.md 第 2 节

# 7. 类型覆盖 100%
mypy src/reelforge --strict
# 应输出：0 errors
```

---

### 7️⃣ **冲突解决协议** (Conflict Resolution)

当代码与文档不一致时的优先级顺序：

**优先级排序**（从高到低）：
1. ⭐⭐⭐ `.locked.py` 接口定义 (不可变，真实来源)
2. ⭐⭐ `database-schema.sql` (Step 4 产出)
3. ⭐ `module-design.md` (Step 3 产出)
4. `PRD-v1.0.locked.md` (Step 1 产出)
5. 运行时代码（可能滞后）

**解决步骤**:
```
1️⃣ 识别冲突
   (如：代码实现的签名与 .locked.py 不符)

2️⃣ 确定根因
   接口过时？还是代码错误？

3️⃣ 升级为 RFC（如需修改接口）
   或修正代码（如接口正确）

4️⃣ 更新依赖文档
   module-design.md、database-schema.sql、dependency-graph.md
```

---

## 🎯 工作流整合示例

**任务**: "实现 parser.py（Excel 解析）"

```
1️⃣ 检查接口
   └─ docs/05-coding/interface-definitions/parser-interface.v1.locked.py 是否存在
   └─ 若无：生成 → mypy 检查 → 人工审核 → 冻结

2️⃣ 生成实现
   └─ src/reelforge/core/parser.py
   └─ 完全匹配接口签名
   └─ 100% 类型注解
   └─ 若调用外部服务，添加 @retry

3️⃣ 编写测试
   └─ __tests__/test_parser.py
   └─ 目标：≥ 80% 覆盖率
   └─ 测试：正常路径 + 错误情况 + 边界值

4️⃣ 通过质量门禁
   └─ mypy src/reelforge (0 errors)
   └─ pytest --cov (≥ 80%)
   └─ 圈复杂度 < 10
   └─ 函数长度 ≤ 50 行

5️⃣ 同步文档
   └─ 若修改了接口：更新 module-design.md
   └─ 若调用数据库：更新 database-schema.sql
   └─ 若改变导入：更新 dependency-graph.md
   └─ 若添加错误码：更新 coding-standards.md

6️⃣ 集成验证
   └─ 无圆形导入
   └─ 无 async/await
   └─ 所有 @retry 到位
   └─ 类型检查通过

7️⃣ 交付
   └─ 代码 + 测试 + 更新文档
   └─ 准备审查
```

---

## 📚 快速命令参考

### 完整质量检查（提交前必做）

```bash
# 一键检查所有质量门禁
mypy src/reelforge --strict && \
pytest --cov=src/reelforge --cov-report=term-missing && \
python -c "from reelforge.app import *; from reelforge.core import *; from reelforge.models import *" && \
grep -r "async def\|await" src/reelforge/ && echo "❌ 发现 async!" || echo "✅ 无 async"
```

### 导入错误检查

```bash
python -m py_compile src/reelforge/**/*.py
```

### 错误码检查

```bash
# 列出代码中使用的所有错误码
grep -ro "E-[0-9]{3}-[0-9]{2}" src/reelforge/ | sort | uniq
# 与 prompts/coding-standards.md 第 2 节对照
```

### 依赖性检查（无循环导入）

```bash
# 使用 dependency-graph.md 视觉化检查
# 或运行 networkx 分析（需安装 networkx）
python -c "
import networkx as nx
# 加载依赖图，检查有无环
"
```

---

## 📊 同步机制架构图

```
代码实现
   ↓
[接口-先行原则] ← 必须有 .locked.py 接口
   ↓
[质量门禁检查]
   ├─ mypy (0 errors)
   ├─ pytest (≥ 80% coverage)
   └─ 复杂度 (< 10)
   ↓
[文档同步]
   ├─ API contract
   ├─ Database schema
   ├─ Module design
   ├─ Dependency graph
   └─ Error codes
   ↓
[集成验证]
   ├─ 无导入错误
   ├─ 无 async/await
   ├─ 有 @retry
   └─ 100% 类型
   ↓
[冲突解决]
   └─ 优先级：.locked.py > schema > design > PRD > code
   ↓
✅ 交付（可安全合并）
```

---

## ✅ 第三步检查清单

- [✅] CLAUDE.md 打开并读取
- [✅] 同步机制章节追加（~600 行）
- [✅] 7 个主规则完整记录
- [✅] 工作流示例说明
- [✅] 命令参考提供
- [✅] 文件保存提交

---

## 📄 更新的文件

**文件**: `CLAUDE.md`  
**新增章节**: "🔄 Automated Synchronization Mechanisms"  
**行数**: 增加 ~600 行（包含子规则、示例、命令）  
**位置**: 文件末尾（Future Enhancements 之后）

---

## 🎯 规则应用范围

这些同步规则自动适用于：
- ✅ 所有新模块实现
- ✅ 所有接口定义
- ✅ 所有测试编写
- ✅ 所有文档更新
- ✅ 所有代码重构
- ✅ 所有依赖变更

**执行方**: Claude（自动遵守，无需用户干预）  
**审核方**: 用户（人工审核接口、RFC、设计决策）

---

## 📋 新增规则概览

| 规则 | 目的 | 执行者 | 触发时机 |
|:---|:---|:---|:---|
| 接口先行 | 设计优于实现 | Claude | 每个新模块 |
| 契约锁定 | 防止意外变更 | Claude | 接口冻结后 |
| 质量门禁 | 代码质量保障 | Claude | 每次生成 |
| 文档同步 | 保持一致性 | Claude | 代码变更后 |
| 版本管理 | 版本控制 | Claude + User | 接口变更时 |
| 集成检查 | 模块兼容性 | Claude | 提交前 |
| 冲突解决 | 优先级明确 | Claude + User | 发现矛盾时 |

---

## 🚀 下一步指引

有了同步机制后：

1. **立即可做**:
   - ✅ Step 4: 生成 database-schema.sql
   - ✅ Step 5.1: 生成 7 个模块接口定义
   - ✅ Step 5.2: 按接口实现代码

2. **自动检查**:
   - 每次代码生成前：检查接口是否冻结
   - 每次代码完成后：运行 mypy + pytest + 集成检查
   - 每次文档变更：同步依赖文档

3. **手动审核** (需用户):
   - 接口定义：审核签名、异常、类型
   - RFC 变更：评估影响、批准版本升级
   - 设计决策：确认模块职责、依赖关系

---

**报告元数据**

| 属性 | 值 |
|:---|:---|
| 报告时间 | 2026-04-02 18:30:00 |
| 规则版本 | v1.0 |
| 应用范围 | 所有后续实现 |
| 审核周期 | 每个模块 |
| RFC 流程 | 接口版本变更时 |

---

✅ **第三步完成。同步机制已写入 CLAUDE.md，自动生效。** 

Ready for Step 4: 数据建模 → Step 5.1: 接口定义 → Step 5.2: 代码实现

