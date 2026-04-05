# Tech Spec：{{module_name}} 模块

## 1. 模块定位
- **模块名**：{{module_name}}
- **路径**：`src/reelforge/modules/{{module_name}}/`
- **类型**：基础设施层（无业务逻辑）
- **约束**：函数&lt;50行，圈复杂度&lt;10，类型注解100%，无async/await

## 2. 文件清单
src/reelforge/modules/{{module_name}}/
├── init.py          # 导出公共接口
├── exceptions.py        # 异常体系定义
├── core.py              # 主类实现
├── pool.py              # 连接池（如需要）
├── transaction.py       # 事务管理器（如需要）
└── tests/
├── test_core.py
├── test_pool.py
└── test_transaction.py

## 3. 阻断条件（P2.3 → P2.4）
进入实现阶段前必须确认：
- [ ] 接口定义通过 `mypy --strict` 检查（无类型错误）
- [ ] 函数签名冻结（P2.4后不可变更，除非回退到P2.3）
- [ ] 文件清单无循环依赖（DAG确认）
- [ ] 人工确认每个public方法的输入/输出/异常

## 4. 验收标准
| 检查项 | 标准 | 验证命令 |
|:-------|:-----|:---------|
| 语法检查 | 通过 | `python -m py_compile src/reelforge/modules/{{module_name}}/core.py` |
| 类型检查 | 通过 | `mypy src/reelforge/modules/{{module_name}}/ --strict` |
| 单元测试 | 100%通过 | `pytest __tests__/ -v` |
| 覆盖率 | >80% | `pytest --cov=core --cov-report=term-missing` |
| 并发测试 | 10线程无死锁 | `pytest test_pool.py::test_concurrent -s`（如适用） |
