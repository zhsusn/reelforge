# 织影项目候选模块清单（客观罗列）

| 模块ID | 模块名 | 功能描述 | 预估代码行 | 外部依赖 | 与业务耦合 |
|--------|--------|----------|------------|----------|------------|
| M01 | config | 配置管理（读取YAML/ENV） | 80-120 | python-dotenv | 无 |
| M02 | database | SQLite连接与连接池 | 150-200 | sqlite3 | 无 |
| M03 | models | SQLAlchemy模型定义 | 200-300 | sqlalchemy | 低 |
| M04 | excel_parser | Excel剧本解析 | 100-150 | pandas | 中 |
| M05 | character_manager | 角色库管理 | 200-250 | PIL, sqlite3 | 中 |
| M06 | shot_generator | 分镜生成（AI绘图+TTS） | 400-500 | aiohttp, edge-tts | 高 |
| M07 | video_renderer | 视频合成引擎 | 500-600 | moviepy | 高 |

## 风险评估矩阵（1-5分，5为最高风险）

| 模块 | 技术复杂度 | 依赖外部API | 状态管理难度 | 失败回滚成本 | **总分** | **建议等级** |
|------|------------|-------------|--------------|--------------|----------|--------------|
| M01 config | 1 | 1 | 1 | 1 | **4** | 🟢 试点候选 |
| M02 database | 2 | 1 | 3 | 2 | **8** | 🟢 试点候选 |
| M03 models | 2 | 1 | 2 | 3 | **8** | 🟢 试点候选 |
| M04 excel_parser | 2 | 1 | 1 | 2 | **6** | 🟡 次要候选 |
| M05 character_manager | 3 | 2 | 3 | 3 | **11** | 🟡 次要候选 |
| M06 shot_generator | 4 | 5 | 4 | 4 | **17** | 🔴 排除 |
| M07 video_renderer | 5 | 3 | 4 | 5 | **17** | 🔴 排除 |

**试点选择建议**：
- 首选：M02 database（能验证SQL生成+类型系统+错误处理，且与业务无耦合）
- 备选：M01 config（过于简单，验证价值低）或 M03 models（需先确定database）
