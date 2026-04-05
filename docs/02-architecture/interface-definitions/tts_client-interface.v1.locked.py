"""
TTS Client 模块接口定义 (Type Spec)
版本：v1.0（已锁定）
项目：ReelForge
文件映射：`services/tts_client.py`

职责：Edge TTS 客户端、音色映射、音频缓存
依赖：edge-tts

状态：✅ 已冻结 (LOCKED)
锁定日期：2026-04-02
锁定原因：进入 Step 5.2 代码实现阶段
验证状态：mypy --strict 检查通过 (0 错误)

变更约束：
1. 此文件为冻结接口，不可直接修改
2. 如需修改必须创建 RFC 文档
3. RFC 批准后创建 v2.0 版本
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# =============================================================================
# 数据模型定义
# =============================================================================

@dataclass
class VoiceProfile:
    """音色配置数据模型"""
    voice_id: str                   # Edge TTS 音色ID（如：zh-CN-XiaoxiaoNeural）
    name: str                       # 音色名称（如：晓晓）
    gender: str                     # 性别（male/female）
    language: str                   # 语言（zh-CN）
    description: str                # 音色描述

# =============================================================================
# 异常定义
# =============================================================================

class TTSError(Exception):
    """TTS合成失败异常"""
    def __init__(self, message: str, original_error: Optional[Exception] = None) -> None:
        super().__init__(message)
        self.message = message
        self.original_error = original_error

class TimeoutError(TTSError):
    """网络超时异常（Edge TTS需访问微软服务器）"""
    pass

class VoiceNotFoundError(TTSError):
    """音色ID不存在异常"""
    pass

# =============================================================================
# 主类接口
# =============================================================================

class TTSClient:
    """
    Edge TTS 客户端

    职责：
        1. 文本转语音合成（TTS）
        2. 音色映射管理
        3. 音频文件缓存
        4. 时长预估

    音色映射表（来自 @prompts/project-config.yaml）：
        | 角色类型 | Voice ID | 描述 |
        |:---------|:---------|:-----|
        | 旁白 | zh-CN-XiaoxiaoNeural | 晓晓（女声通用） |
        | 男性角色 | zh-CN-YunxiNeural | 云希（男声青年） |
        | 女性角色 | zh-CN-XiaoyiNeural | 晓伊（女声温柔） |
        | 老年角色 | zh-CN-YunjianNeural | 云健（男声老年） |
    """

    def __init__(self, cache_dir: Optional[Path] = None) -> None:
        """
        初始化TTS客户端

        Args:
            cache_dir: 音频缓存目录，None则使用默认目录
        """
        raise NotImplementedError

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((TTSError, TimeoutError))
    )
    def synthesize(self, text: str, voice_profile: str) -> Path:
        """
        文本转语音合成

        Args:
            text: 要合成的文本
            voice_profile: 音色ID（如：zh-CN-XiaoxiaoNeural）

        Returns:
            Path: 生成的MP3文件路径

        Raises:
            TTSError: TTS合成失败
            TimeoutError: 网络超时
            VoiceNotFoundError: 音色ID不存在
        """
        raise NotImplementedError

    def estimate_duration(self, text: str, voice_profile: Optional[str] = None) -> float:
        """
        预估语音时长

        Args:
            text: 要预估的文本
            voice_profile: 可选音色ID，None则使用默认音色

        Returns:
            float: 预估时长（秒）
        """
        raise NotImplementedError

    def get_voices(self) -> List[VoiceProfile]:
        """
        获取可用音色列表

        Returns:
            List[VoiceProfile]: 音色配置列表
        """
        raise NotImplementedError

    def get_voice_mapping(self) -> Dict[str, str]:
        """
        获取角色类型到音色ID的映射表

        Returns:
            Dict[str, str]: 映射表，键为角色类型，值为音色ID
        """
        raise NotImplementedError

    def clear_cache(self, older_than_days: int = 7) -> int:
        """
        清理过期缓存文件

        Args:
            older_than_days: 清理超过指定天数的文件

        Returns:
            int: 清理的文件数量
        """
        raise NotImplementedError

    @property
    def default_voice(self) -> str:
        """获取默认音色ID"""
        raise NotImplementedError

    @property
    def cache_dir(self) -> Path:
        """获取缓存目录"""
        raise NotImplementedError

# =============================================================================
# 导出列表
# =============================================================================

__all__ = [
    # 数据模型
    "VoiceProfile",
    # 异常
    "TTSError",
    "TimeoutError",
    "VoiceNotFoundError",
    # 主类
    "TTSClient",
]