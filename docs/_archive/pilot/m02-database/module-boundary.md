# 试点模块：M02 database（边界冻结文档）

## 模块定位
- **类型**：基础设施层（非业务逻辑）
- **输入**：数据库文件路径（Path）、配置参数（WAL模式/超时时间）
- **输出**：连接对象、查询结果、事务上下文

## 路径规范（ReelForge项目）
- 根包：`src/reelforge/`
- 模块目录：`src/reelforge/modules/{module_name}/`
- 测试目录：`src/reelforge/modules/{module_name}/__tests__/`
- 配置目录：`src/reelforge/config/`

## 明确包含（Must Have）
1. SQLite连接初始化（支持WAL模式）
2. 基础查询接口（execute/query）
3. 连接池管理（单例模式，最大5连接）
4. 事务上下文管理器（with语句支持）
5. 连接健康检查（is_alive）

## 明确排除（Must Not Have）
- ❌ 不定义业务表结构（这是models模块职责）
- ❌ 不处理数据库迁移（独立migration模块）
- ❌ 不拼接业务SQL（防注入在Repository层处理）
- ❌ 不支持异步IO（第一版仅同步，简化复杂度）

## 技术约束（硬性红线）
- 必须使用SQLite（零部署约束）
- 函数长度 < 50行（强制）
- 圈复杂度 < 10（强制）
- 类型注解覆盖率 100%（强制）
- 单元测试覆盖率 > 80%（强制）

## 验收标准（可量化）
- [ ] 能成功连接SQLite文件（不存在时自动创建）
- [ ] 支持并发查询（10线程无死锁）
- [ ] 事务回滚正常工作（异常时数据不脏）
- [ ] 连接池耗尽时优雅等待（非崩溃）
- [ ] 所有异常可识别（自定义异常类，非裸抛sqlite3.Error）