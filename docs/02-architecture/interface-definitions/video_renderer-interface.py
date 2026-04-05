"""
Video Renderer 模块接口定义 (Type Spec)
版本：v1.0（草案）
项目：ReelForge
文件映射：`core/video_renderer.py`

职责：视频渲染、音画合成、字幕生成
依赖：moviepy, ffmpeg-python, librosa

状态：Generated（未冻结）
确认方式：运行 mypy 检查，然后可冻结为 video_renderer-interface.v1.locked.py
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple

# =============================================================================
# 数据模型定义
# =============================================================================

@dataclass
class Shot:
    """分镜数据模型"""
    sequence: int                   # 序号
    dialogue: str                   # 台词
    audio_path: Path                # TTS生成的语音文件路径
    image_path: Path                # AI生成的图片路径
    duration: float                 # 精确时长（秒，librosa计算）
    subtitle_start: float           # 字幕开始时间（秒）
    subtitle_end: float             # 字幕结束时间（秒）

@dataclass
class RenderConfig:
    """渲染配置模型"""
    resolution: Tuple[int, int] = (1080, 1920)  # 分辨率（宽×高），默认竖屏9:16
    fps: int = 30                               # 帧率
    codec: str = "libx264"                      # 视频编码器
    bitrate: str = "8000k"                      # 视频码率
    audio_codec: str = "aac"                    # 音频编码器
    audio_bitrate: str = "192k"                 # 音频码率
    subtitle_font: Optional[Path] = None        # 字幕字体文件路径
    subtitle_color: str = "#FFFFFF"             # 字幕颜色
    bgm_path: Optional[Path] = None             # BGM文件路径
    bgm_volume: float = 0.2                     # BGM音量（相对于语音，0-1）

# =============================================================================
# 异常定义
# =============================================================================

class RenderError(Exception):
    """渲染过程失败异常"""
    def __init__(self, message: str, original_error: Optional[Exception] = None) -> None:
        super().__init__(message)
        self.message = message
        self.original_error = original_error

class FFmpegNotFoundError(RenderError):
    """系统未安装FFmpeg或不在PATH"""
    pass

class SubtitleError(RenderError):
    """字幕生成失败异常"""
    pass

class ResourceError(RenderError):
    """素材文件不存在或无法读取"""
    pass

# =============================================================================
# 主类接口
# =============================================================================

class VideoRenderer:
    """
    视频渲染器主类

    职责：
        1. 视频合成（图像序列+音频）
        2. 字幕叠加（SRT格式）
        3. BGM混音
        4. FFmpeg调用封装

    约束：
        - 必须验证FFmpeg安装
        - 支持断点续传（通过中间文件）
        - 提供进度回调
    """

    def __init__(self) -> None:
        """初始化视频渲染器"""
        raise NotImplementedError

    def render(self, shots: List[Shot], config: RenderConfig,
               progress_callback: Optional[Callable[[int, int], None]] = None) -> Path:
        """
        渲染视频

        Args:
            shots: 分镜列表
            config: 渲染配置
            progress_callback: 进度回调函数，参数：(当前进度, 总进度)

        Returns:
            Path: 输出视频文件路径

        Raises:
            FFmpegNotFoundError: 系统未安装FFmpeg
            ResourceError: 素材文件不存在
            RenderError: 渲染过程失败
        """
        raise NotImplementedError

    def validate_ffmpeg(self) -> bool:
        """
        验证FFmpeg是否可用

        Returns:
            bool: True如果FFmpeg可用

        Raises:
            FFmpegNotFoundError: FFmpeg未安装或不在PATH
        """
        raise NotImplementedError

    def estimate_duration(self, shots: List[Shot]) -> float:
        """
        预估视频总时长

        Args:
            shots: 分镜列表

        Returns:
            float: 预估时长（秒）
        """
        raise NotImplementedError

    def generate_subtitles(self, shots: List[Shot], output_path: Optional[Path] = None) -> Path:
        """
        生成字幕文件（SRT格式）

        Args:
            shots: 分镜列表
            output_path: 可选输出路径，None则自动生成

        Returns:
            Path: 生成的SRT文件路径

        Raises:
            SubtitleError: 字幕生成失败
        """
        raise NotImplementedError

    @staticmethod
    def get_supported_codecs() -> List[str]:
        """
        获取支持的视频编码器列表

        Returns:
            List[str]: 编码器列表
        """
        raise NotImplementedError

    @staticmethod
    def get_supported_resolutions() -> List[Tuple[int, int]]:
        """
        获取支持的分辨率列表

        Returns:
            List[Tuple[int, int]]: 分辨率列表（宽×高）
        """
        raise NotImplementedError

# =============================================================================
# 导出列表
# =============================================================================

__all__ = [
    # 数据模型
    "Shot",
    "RenderConfig",
    # 异常
    "RenderError",
    "FFmpegNotFoundError",
    "SubtitleError",
    "ResourceError",
    # 主类
    "VideoRenderer",
]