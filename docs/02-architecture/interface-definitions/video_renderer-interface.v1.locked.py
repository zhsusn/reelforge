"""
Video Renderer 模块接口定义 (Type Spec)
版本：v1.0（已冻结）
项目：ReelForge
文件映射：`core/video_renderer.py`

职责：视频渲染、音画合成、字幕生成
依赖：moviepy, ffmpeg-python, librosa

状态：🔒 LOCKED (冻结)
锁定日期：2026-04-03
锁定原因：接口定义完整，通过mypy严格检查
验证状态：✅ 类型检查通过 (mypy --strict)

重要：此文件为冻结接口定义，不可修改。如需变更请创建RFC文档。
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
    """渲染失败基类"""
    def __init__(self, message: str, original_error: Optional[Exception] = None) -> None:
        super().__init__(message)
        self.message = message
        self.original_error = original_error

class FFmpegNotFoundError(RenderError):
    """FFmpeg未安装或未在PATH中找到"""
    pass

class SubtitleError(RenderError):
    """字幕生成失败"""
    pass

class ResourceError(RenderError):
    """素材资源错误（文件不存在、无法读取等）"""
    pass

# =============================================================================
# 主类接口
# =============================================================================

class VideoRenderer:
    """
    视频渲染引擎

    职责：
        1. MoviePy 音画合成
        2. FFmpeg 编码输出
        3. 字幕生成与叠加
        4. BGM混音

    约束：
        - 峰值内存限制：4GB
        - FFmpeg必须安装并在PATH中
        - 函数长度 < 50行
        - 类型注解 100%
        - 禁用 async/await
    """

    def __init__(self, ffmpeg_path: Optional[str] = None) -> None:
        """
        初始化视频渲染器

        Args:
            ffmpeg_path: FFmpeg可执行文件路径（None则使用系统PATH）
        """
        raise NotImplementedError

    def validate_ffmpeg(self) -> bool:
        """
        检查 FFmpeg 是否可用

        Returns:
            bool: 是否可用

        Raises:
            FFmpegNotFoundError: FFmpeg未安装或路径错误
        """
        raise NotImplementedError

    def render(
        self,
        shots: List[Shot],
        config: RenderConfig,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Path:
        """
        渲染视频

        Args:
            shots: 分镜片段列表
            config: 渲染配置
            progress_callback: 进度回调函数(progress_pct, step_name)

        Returns:
            Path: 输出视频文件路径

        Raises:
            RenderError: 渲染过程失败
            ResourceError: 素材文件不存在
            FFmpegNotFoundError: FFmpeg不可用
        """
        raise NotImplementedError

    def estimate_duration(self, shots: List[Shot]) -> float:
        """
        预估总时长

        Args:
            shots: 分镜片段列表

        Returns:
            float: 预估秒数
        """
        raise NotImplementedError

    def generate_subtitles(
        self,
        shots: List[Shot],
        output_path: Path,
        config: RenderConfig
    ) -> Path:
        """
        生成 SRT 字幕文件

        Args:
            shots: 分镜片段列表
            output_path: 输出路径
            config: 渲染配置（字体、颜色等）

        Returns:
            Path: SRT文件路径

        Raises:
            SubtitleError: 字幕生成失败
        """
        raise NotImplementedError

    def preview_frame(
        self,
        shot: Shot,
        config: RenderConfig,
        time_offset: float = 0.0
    ) -> Any:
        """
        生成预览帧（用于界面缩略图）

        Args:
            shot: 分镜片段
            config: 渲染配置
            time_offset: 时间偏移（秒）

        Returns:
            Any: 图像帧数据（通常为numpy数组）
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