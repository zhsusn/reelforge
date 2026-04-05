# 决策记录 (Decisions Log)

**项目**: ReelForge (影工厂)  
**维护**: 自动同步机制  
**目的**: 记录技术决策、接口锁定、变更记录  

---

## 接口锁定记录

### tts_client 模块接口锁定
- **日期**: 2026-04-02
- **版本**: v1.0
- **文件**: `docs/05-coding/interface-definitions/tts_client-interface.v1.locked.py`
- **状态**: ✅ 已冻结
- **验证**: mypy --strict 检查通过 (0 错误)
- **冻结原因**: 进入 Step 5.2 代码实现阶段
- **变更约束**: 如需修改必须创建 RFC 文档
- **依赖**: Edge TTS API (edge-tts 6.1.9)
- **实现路径**: `src/reelforge/services/tts_client.py`

**锁定确认**: 接口定义完整，包含：
1. 数据模型: `VoiceProfile`
2. 异常体系: `TTSError`, `TimeoutError`, `VoiceNotFoundError`
3. 主类接口: `TTSClient` 及其所有方法
4. 音色映射表: 符合 project-config.yaml 配置

---

## 技术决策

### 2026-04-02: 开发顺序决策
**决策**: 选择 `tts_client` 作为首个实现模块  
**理由**:
1. **无依赖**: services 层模块，不依赖其他内部模块
2. **复杂度适中**: 适合验证完整开发流程
3. **技术债务**: 解决 TD-003 (第三方 API 依赖)
4. **实用性**: TTS 是视频生成的基础功能

**实施顺序**:
1. `tts_client` (Edge TTS) - 最简单，无依赖
2. `tongyi_client` (通义万相) - 解决关键债务 TD-006
3. `deepseek_client` (DeepSeek) - 流式响应较复杂

---

## RFC 记录

*(暂无 RFC 文档)*
