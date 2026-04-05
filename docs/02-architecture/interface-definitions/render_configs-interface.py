"""
Render Configs 模块接口定义 (Type Spec)
版本：v1.0（草案）
项目：ReelForge
文件映射：`models/render_configs.py`

职责：渲染配置数据的创建、读取、更新、删除操作，视频参数管理
依赖：src/reelforge/models/database/ (Database, DatabaseError等)

状态：📝 DRAFT (草案)
创建日期：2026-04-03
锁定状态：待审核确认

重要：此文件为接口定义草案，需通过mypy严格检查后锁定。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from reelforge.models.database import Database, DatabaseError, QueryResult


# =============================================================================
# 数据模型定义
# =============================================================================

class VideoCodec(str, Enum):
    """视频编码器枚举"""
    LIBX264 = "libx264"
    LIBX265 = "libx265"
    VP9 = "vp9"
    AV1 = "av1"


class AudioCodec(str, Enum):
    """音频编码器枚举"""
    AAC = "aac"
    MP3 = "mp3"
    OPUS = "opus"
    FLAC = "flac"


@dataclass
class RenderConfig:
    """渲染配置数据模型

    对应数据库表：render_configs
    字段映射：
        id -> config_id
        project_id -> project_id
        resolution_width -> width
        resolution_height -> height
        fps -> fps
        video_codec -> video_codec (VideoCodec)
        video_bitrate -> video_bitrate (字符串，如"8000k")
        audio_codec -> audio_codec (AudioCodec)
        audio_bitrate -> audio_bitrate (字符串，如"192k")
        subtitle_font_path -> subtitle_font_path (可选)
        subtitle_color -> subtitle_color (字符串，如"#FFFFFF")
        subtitle_font_size -> subtitle_font_size
        bgm_path -> bgm_path (可选)
        bgm_volume -> bgm_volume (0-1范围)
        created_at -> created_at (datetime)
        updated_at -> updated_at (datetime)
    """

    config_id: int
    project_id: int
    width: int
    height: int
    fps: int
    video_codec: VideoCodec
    video_bitrate: str
    audio_codec: AudioCodec
    audio_bitrate: str
    subtitle_font_path: Optional[Path]
    subtitle_color: str
    subtitle_font_size: int
    bgm_path: Optional[Path]
    bgm_volume: float
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> RenderConfig:
        """从数据库行创建RenderConfig对象"""
        return cls(
            config_id=row["id"],
            project_id=row["project_id"],
            width=row["resolution_width"],
            height=row["resolution_height"],
            fps=row["fps"],
            video_codec=VideoCodec(row["video_codec"]),
            video_bitrate=row["video_bitrate"],
            audio_codec=AudioCodec(row["audio_codec"]),
            audio_bitrate=row["audio_bitrate"],
            subtitle_font_path=Path(row["subtitle_font_path"]) if row["subtitle_font_path"] else None,
            subtitle_color=row["subtitle_color"],
            subtitle_font_size=row["subtitle_font_size"],
            bgm_path=Path(row["bgm_path"]) if row["bgm_path"] else None,
            bgm_volume=float(row["bgm_volume"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @property
    def resolution(self) -> str:
        """获取分辨率字符串（如"1080x1920"）"""
        return f"{self.width}x{self.height}"

    @property
    def has_bgm(self) -> bool:
        """检查是否有BGM配置"""
        return self.bgm_path is not None

    @property
    def has_custom_subtitle_font(self) -> bool:
        """检查是否有自定义字幕字体"""
        return self.subtitle_font_path is not None


@dataclass
class RenderConfigCreate:
    """创建渲染配置时的数据模型（输入）"""
    project_id: int
    width: Optional[int] = 1080
    height: Optional[int] = 1920
    fps: Optional[int] = 30
    video_codec: Optional[VideoCodec] = VideoCodec.LIBX264
    video_bitrate: Optional[str] = "8000k"
    audio_codec: Optional[AudioCodec] = AudioCodec.AAC
    audio_bitrate: Optional[str] = "192k"
    subtitle_font_path: Optional[Path] = None
    subtitle_color: Optional[str] = "#FFFFFF"
    subtitle_font_size: Optional[int] = 36
    bgm_path: Optional[Path] = None
    bgm_volume: Optional[float] = 0.2


@dataclass
class RenderConfigUpdate:
    """更新渲染配置时的数据模型（输入）"""
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[int] = None
    video_codec: Optional[VideoCodec] = None
    video_bitrate: Optional[str] = None
    audio_codec: Optional[AudioCodec] = None
    audio_bitrate: Optional[str] = None
    subtitle_font_path: Optional[Path] = None
    subtitle_color: Optional[str] = None
    subtitle_font_size: Optional[int] = None
    bgm_path: Optional[Path] = None
    bgm_volume: Optional[float] = None


@dataclass
class RenderPreset:
    """渲染预设配置"""
    name: str
    width: int
    height: int
    fps: int
    video_codec: VideoCodec
    video_bitrate: str
    audio_codec: AudioCodec
    audio_bitrate: str
    subtitle_color: str
    subtitle_font_size: int


# =============================================================================
# 异常定义
# =============================================================================

class RenderConfigError(DatabaseError):
    """渲染配置操作基础异常"""
    pass


class RenderConfigNotFoundError(RenderConfigError):
    """渲染配置未找到异常"""
    pass


class RenderConfigAlreadyExistsError(RenderConfigError):
    """渲染配置已存在异常（项目ID重复）"""
    pass


class InvalidResolutionError(RenderConfigError):
    """无效的分辨率异常"""
    pass


class InvalidVideoParameterError(RenderConfigError):
    """无效的视频参数异常（FPS、码率等）"""
    pass


class ResourceNotFoundError(RenderConfigError):
    """资源文件未找到异常（字体、BGM文件）"""
    pass


class BGMVolumeOutOfRangeError(RenderConfigError):
    """BGM音量超出范围异常（0-1）"""
    pass


# =============================================================================
# 主类接口实现
# =============================================================================

class RenderConfigManager:
    """渲染配置管理器（CRUD操作）

    职责：
        1. 渲染配置创建、读取、更新、删除
        2. 视频参数验证（分辨率、FPS、码率等）
        3. 资源文件管理（字体、BGM）
        4. 预设配置管理
        5. 批量操作和导入导出
    """

    def __init__(self, database: Database) -> None:
        """
        初始化渲染配置管理器

        Args:
            database: 数据库实例
        """
        raise NotImplementedError

    # =========================================================================
    # 基本CRUD操作
    # =========================================================================

    def create(self, config_data: RenderConfigCreate) -> RenderConfig:
        """
        创建新渲染配置

        Args:
            config_data: 渲染配置创建数据

        Returns:
            RenderConfig: 创建的渲染配置对象

        Raises:
            RenderConfigError: 创建失败
            RenderConfigAlreadyExistsError: 项目的渲染配置已存在
            InvalidResolutionError: 分辨率无效
            InvalidVideoParameterError: 视频参数无效
        """
        raise NotImplementedError

    def get_by_project(self, project_id: int) -> RenderConfig:
        """
        根据项目ID获取渲染配置

        Args:
            project_id: 项目ID

        Returns:
            RenderConfig: 渲染配置对象

        Raises:
            RenderConfigNotFoundError: 渲染配置不存在
            RenderConfigError: 查询失败
        """
        raise NotImplementedError

    def get_by_id(self, config_id: int) -> RenderConfig:
        """
        根据ID获取渲染配置

        Args:
            config_id: 配置ID

        Returns:
            RenderConfig: 渲染配置对象

        Raises:
            RenderConfigNotFoundError: 渲染配置不存在
            RenderConfigError: 查询失败
        """
        raise NotImplementedError

    def update(self, project_id: int, update_data: RenderConfigUpdate) -> RenderConfig:
        """
        更新渲染配置信息

        Args:
            project_id: 项目ID
            update_data: 更新数据

        Returns:
            RenderConfig: 更新后的渲染配置对象

        Raises:
            RenderConfigNotFoundError: 渲染配置不存在
            InvalidResolutionError: 分辨率无效
            InvalidVideoParameterError: 视频参数无效
            RenderConfigError: 更新失败
        """
        raise NotImplementedError

    def delete(self, project_id: int) -> bool:
        """
        删除渲染配置

        Args:
            project_id: 项目ID

        Returns:
            bool: 删除是否成功

        Raises:
            RenderConfigNotFoundError: 渲染配置不存在
            RenderConfigError: 删除失败
        """
        raise NotImplementedError

    # =========================================================================
    # 视频参数管理
    # =========================================================================

    def update_resolution(self, project_id: int, width: int, height: int) -> RenderConfig:
        """
        更新分辨率

        Args:
            project_id: 项目ID
            width: 宽度
            height: 高度

        Returns:
            RenderConfig: 更新后的渲染配置对象

        Raises:
            RenderConfigNotFoundError: 渲染配置不存在
            InvalidResolutionError: 分辨率无效
        """
        raise NotImplementedError

    def update_fps(self, project_id: int, fps: int) -> RenderConfig:
        """
        更新帧率

        Args:
            project_id: 项目ID
            fps: 帧率

        Returns:
            RenderConfig: 更新后的渲染配置对象

        Raises:
            RenderConfigNotFoundError: 渲染配置不存在
            InvalidVideoParameterError: FPS无效
        """
        raise NotImplementedError

    def update_video_codec(self, project_id: int, video_codec: VideoCodec) -> RenderConfig:
        """
        更新视频编码器

        Args:
            project_id: 项目ID
            video_codec: 视频编码器

        Returns:
            RenderConfig: 更新后的渲染配置对象

        Raises:
            RenderConfigNotFoundError: 渲染配置不存在
        """
        raise NotImplementedError

    def update_audio_codec(self, project_id: int, audio_codec: AudioCodec) -> RenderConfig:
        """
        更新音频编码器

        Args:
            project_id: 项目ID
            audio_codec: 音频编码器

        Returns:
            RenderConfig: 更新后的渲染配置对象

        Raises:
            RenderConfigNotFoundError: 渲染配置不存在
        """
        raise NotImplementedError

    def update_video_bitrate(self, project_id: int, bitrate: str) -> RenderConfig:
        """
        更新视频码率

        Args:
            project_id: 项目ID
            bitrate: 视频码率（如"8000k"）

        Returns:
            RenderConfig: 更新后的渲染配置对象

        Raises:
            RenderConfigNotFoundError: 渲染配置不存在
            InvalidVideoParameterError: 码率格式无效
        """
        raise NotImplementedError

    def update_audio_bitrate(self, project_id: int, bitrate: str) -> RenderConfig:
        """
        更新音频码率

        Args:
            project_id: 项目ID
            bitrate: 音频码率（如"192k"）

        Returns:
            RenderConfig: 更新后的渲染配置对象

        Raises:
            RenderConfigNotFoundError: 渲染配置不存在
            InvalidVideoParameterError: 码率格式无效
        """
        raise NotImplementedError

    # =========================================================================
    # 字幕参数管理
    # =========================================================================

    def update_subtitle_font(self, project_id: int, font_path: Path) -> RenderConfig:
        """
        更新字幕字体

        Args:
            project_id: 项目ID
            font_path: 字体文件路径

        Returns:
            RenderConfig: 更新后的渲染配置对象

        Raises:
            RenderConfigNotFoundError: 渲染配置不存在
            ResourceNotFoundError: 字体文件未找到
        """
        raise NotImplementedError

    def update_subtitle_color(self, project_id: int, color: str) -> RenderConfig:
        """
        更新字幕颜色

        Args:
            project_id: 项目ID
            color: 颜色代码（如"#FFFFFF"）

        Returns:
            RenderConfig: 更新后的渲染配置对象

        Raises:
            RenderConfigNotFoundError: 渲染配置不存在
            InvalidVideoParameterError: 颜色格式无效
        """
        raise NotImplementedError

    def update_subtitle_font_size(self, project_id: int, size: int) -> RenderConfig:
        """
        更新字幕字体大小

        Args:
            project_id: 项目ID
            size: 字体大小

        Returns:
            RenderConfig: 更新后的渲染配置对象

        Raises:
            RenderConfigNotFoundError: 渲染配置不存在
            InvalidVideoParameterError: 字体大小无效
        """
        raise NotImplementedError

    def remove_subtitle_font(self, project_id: int) -> RenderConfig:
        """
        移除自定义字幕字体（使用默认字体）

        Args:
            project_id: 项目ID

        Returns:
            RenderConfig: 更新后的渲染配置对象

        Raises:
            RenderConfigNotFoundError: 渲染配置不存在
        """
        raise NotImplementedError

    # =========================================================================
    # BGM参数管理
    # =========================================================================

    def add_bgm(self, project_id: int, bgm_path: Path, volume: float = 0.2) -> RenderConfig:
        """
        添加BGM

        Args:
            project_id: 项目ID
            bgm_path: BGM文件路径
            volume: 音量（0-1，默认0.2）

        Returns:
            RenderConfig: 更新后的渲染配置对象

        Raises:
            RenderConfigNotFoundError: 渲染配置不存在
            ResourceNotFoundError: BGM文件未找到
            BGMVolumeOutOfRangeError: 音量超出范围
        """
        raise NotImplementedError

    def update_bgm_volume(self, project_id: int, volume: float) -> RenderConfig:
        """
        更新BGM音量

        Args:
            project_id: 项目ID
            volume: 音量（0-1）

        Returns:
            RenderConfig: 更新后的渲染配置对象

        Raises:
            RenderConfigNotFoundError: 渲染配置不存在
            BGMVolumeOutOfRangeError: 音量超出范围
        """
        raise NotImplementedError

    def remove_bgm(self, project_id: int) -> RenderConfig:
        """
        移除BGM

        Args:
            project_id: 项目ID

        Returns:
            RenderConfig: 更新后的渲染配置对象

        Raises:
            RenderConfigNotFoundError: 渲染配置不存在
        """
        raise NotImplementedError

    # =========================================================================
    # 查询和列表操作
    # =========================================================================

    def list_all(
        self,
        resolution: Optional[str] = None,
        fps: Optional[int] = None,
        video_codec: Optional[VideoCodec] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[RenderConfig]:
        """
        列出所有渲染配置

        Args:
            resolution: 按分辨率过滤（可选，如"1080x1920"）
            fps: 按帧率过滤（可选）
            video_codec: 按视频编码器过滤（可选）
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            List[RenderConfig]: 渲染配置列表
        """
        raise NotImplementedError

    def count(self, resolution: Optional[str] = None, fps: Optional[int] = None) -> int:
        """
        统计渲染配置数量

        Args:
            resolution: 按分辨率过滤（可选）
            fps: 按帧率过滤（可选）

        Returns:
            int: 渲染配置数量
        """
        raise NotImplementedError

    # =========================================================================
    # 批量操作
    # =========================================================================

    def batch_create(self, configs_data: List[RenderConfigCreate]) -> List[RenderConfig]:
        """
        批量创建渲染配置

        Args:
            configs_data: 渲染配置创建数据列表

        Returns:
            List[RenderConfig]: 创建的渲染配置列表

        Raises:
            RenderConfigError: 批量创建失败
        """
        raise NotImplementedError

    def batch_delete(self, project_ids: List[int]) -> Dict[str, Any]:
        """
        批量删除渲染配置

        Args:
            project_ids: 项目ID列表

        Returns:
            Dict[str, Any]: 删除结果统计
        """
        raise NotImplementedError

    # =========================================================================
    # 预设配置管理
    # =========================================================================

    def apply_preset(self, project_id: int, preset_name: str) -> RenderConfig:
        """
        应用预设配置

        Args:
            project_id: 项目ID
            preset_name: 预设名称（如"mobile_vertical", "web_horizontal"）

        Returns:
            RenderConfig: 更新后的渲染配置对象

        Raises:
            RenderConfigNotFoundError: 渲染配置不存在
            InvalidVideoParameterError: 预设不存在
        """
        raise NotImplementedError

    def get_preset(self, preset_name: str) -> RenderPreset:
        """
        获取预设配置

        Args:
            preset_name: 预设名称

        Returns:
            RenderPreset: 预设配置对象

        Raises:
            InvalidVideoParameterError: 预设不存在
        """
        raise NotImplementedError

    def list_presets(self) -> List[str]:
        """
        列出所有可用的预设名称

        Returns:
            List[str]: 预设名称列表
        """
        raise NotImplementedError

    def create_preset(self, preset: RenderPreset) -> bool:
        """
        创建新预设

        Args:
            preset: 预设配置对象

        Returns:
            bool: 创建是否成功

        Raises:
            InvalidVideoParameterError: 预设参数无效
        """
        raise NotImplementedError

    # =========================================================================
    # 验证和辅助方法
    # =========================================================================

    def validate_resources(self, project_id: int) -> Dict[str, bool]:
        """
        验证资源文件是否存在（字体、BGM）

        Args:
            project_id: 项目ID

        Returns:
            Dict[str, bool]: 资源验证结果
        """
        raise NotImplementedError

    def get_resource_paths(self, project_id: int) -> Dict[str, Optional[Path]]:
        """
        获取资源文件路径

        Args:
            project_id: 项目ID

        Returns:
            Dict[str, Optional[Path]]: 资源路径字典
        """
        raise NotImplementedError

    def validate_resolution(self, width: int, height: int) -> bool:
        """
        验证分辨率是否有效

        Args:
            width: 宽度
            height: 高度

        Returns:
            bool: 分辨率是否有效

        规则：
        - 宽度和高度必须为正整数
        - 支持常见分辨率比例
        - 最小分辨率：320x240
        - 最大分辨率：4096x2160（4K）
        """
        raise NotImplementedError

    def validate_video_bitrate(self, bitrate: str) -> bool:
        """
        验证视频码率格式

        Args:
            bitrate: 码率字符串（如"8000k"）

        Returns:
            bool: 码率格式是否有效
        """
        raise NotImplementedError

    def validate_audio_bitrate(self, bitrate: str) -> bool:
        """
        验证音频码率格式

        Args:
            bitrate: 码率字符串（如"192k"）

        Returns:
            bool: 码率格式是否有效
        """
        raise NotImplementedError

    def validate_color_code(self, color: str) -> bool:
        """
        验证颜色代码格式

        Args:
            color: 颜色代码字符串（如"#FFFFFF"）

        Returns:
            bool: 颜色格式是否有效
        """
        raise NotImplementedError

    # =========================================================================
    # 统计和报表
    # =========================================================================

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取渲染配置统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        raise NotImplementedError

    def get_resolution_distribution(self) -> Dict[str, int]:
        """
        获取分辨率分布统计

        Returns:
            Dict[str, int]: 分辨率->数量映射
        """
        raise NotImplementedError

    def get_codec_distribution(self) -> Dict[str, Dict[str, int]]:
        """
        获取编码器分布统计

        Returns:
            Dict[str, Dict[str, int]]: 编码器分布统计
        """
        raise NotImplementedError

    # =========================================================================
    # 辅助方法
    # =========================================================================

    def _get_last_insert_id(self) -> int:
        """获取最后插入的ID"""
        raise NotImplementedError

    def _parse_resolution_string(self, resolution_str: str) -> Tuple[int, int]:
        """解析分辨率字符串"""
        raise NotImplementedError

    def _validate_bgm_volume(self, volume: float) -> bool:
        """验证BGM音量是否在0-1范围内"""
        raise NotImplementedError


# =============================================================================
# 导出列表
# =============================================================================

__all__ = [
    # 数据模型
    "RenderConfig",
    "RenderConfigCreate",
    "RenderConfigUpdate",
    "RenderPreset",
    # 枚举
    "VideoCodec",
    "AudioCodec",
    # 异常
    "RenderConfigError",
    "RenderConfigNotFoundError",
    "RenderConfigAlreadyExistsError",
    "InvalidResolutionError",
    "InvalidVideoParameterError",
    "ResourceNotFoundError",
    "BGMVolumeOutOfRangeError",
    # 主类
    "RenderConfigManager",
]