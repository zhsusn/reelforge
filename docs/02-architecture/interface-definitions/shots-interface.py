"""
Shots 模块接口定义 (Type Spec)
版本：v1.0（草案）
项目：ReelForge
文件映射：`models/shots.py`

职责：分镜数据的创建、读取、更新、删除操作，生成状态管理，相似度验证
依赖：src/reelforge/models/database/ (Database, DatabaseError等)
      src/reelforge/models/script_lines.py (关联剧本行)

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

class ShotStatus(str, Enum):
    """分镜状态枚举"""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Shot:
    """分镜数据模型

    对应数据库表：shots
    字段映射：
        id -> shot_id
        project_id -> project_id
        script_line_id -> script_line_id (可选)
        sequence -> sequence
        scene_description -> scene_description
        dialogue -> dialogue
        emotion -> emotion
        camera_movement -> camera_movement (可选)
        shot_type -> shot_type (可选)
        status -> status (ShotStatus)
        generated_image_path -> generated_image_path (可选)
        tts_audio_path -> tts_audio_path (可选)
        actual_duration -> actual_duration (可选)
        subtitle_start -> subtitle_start (可选)
        subtitle_end -> subtitle_end (可选)
        similarity_score -> similarity_score (可选)
        created_at -> created_at (datetime)
        updated_at -> updated_at (datetime)
    """

    shot_id: int
    project_id: int
    script_line_id: Optional[int]
    sequence: int
    scene_description: str
    dialogue: str
    emotion: str
    camera_movement: Optional[str]
    shot_type: Optional[str]
    status: ShotStatus
    generated_image_path: Optional[Path]
    tts_audio_path: Optional[Path]
    actual_duration: Optional[float]
    subtitle_start: Optional[float]
    subtitle_end: Optional[float]
    similarity_score: Optional[float]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> Shot:
        """从数据库行创建Shot对象"""
        return cls(
            shot_id=row["id"],
            project_id=row["project_id"],
            script_line_id=row["script_line_id"],
            sequence=row["sequence"],
            scene_description=row["scene_description"],
            dialogue=row["dialogue"],
            emotion=row["emotion"],
            camera_movement=row["camera_movement"],
            shot_type=row["shot_type"],
            status=ShotStatus(row["status"]),
            generated_image_path=Path(row["generated_image_path"]) if row["generated_image_path"] else None,
            tts_audio_path=Path(row["tts_audio_path"]) if row["tts_audio_path"] else None,
            actual_duration=float(row["actual_duration"]) if row["actual_duration"] else None,
            subtitle_start=float(row["subtitle_start"]) if row["subtitle_start"] else None,
            subtitle_end=float(row["subtitle_end"]) if row["subtitle_end"] else None,
            similarity_score=float(row["similarity_score"]) if row["similarity_score"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


@dataclass
class ShotCreate:
    """创建分镜时的数据模型（输入）"""
    project_id: int
    sequence: int
    scene_description: str
    dialogue: str
    emotion: str
    script_line_id: Optional[int] = None
    camera_movement: Optional[str] = None
    shot_type: Optional[str] = None


@dataclass
class ShotUpdate:
    """更新分镜时的数据模型（输入）"""
    sequence: Optional[int] = None
    scene_description: Optional[str] = None
    dialogue: Optional[str] = None
    emotion: Optional[str] = None
    camera_movement: Optional[str] = None
    shot_type: Optional[str] = None
    status: Optional[ShotStatus] = None
    generated_image_path: Optional[Path] = None
    tts_audio_path: Optional[Path] = None
    actual_duration: Optional[float] = None
    subtitle_start: Optional[float] = None
    subtitle_end: Optional[float] = None
    similarity_score: Optional[float] = None


@dataclass
class ShotWithStats(Shot):
    """包含统计信息的比分镜数据模型"""
    script_line_sequence: Optional[int] = None  # 关联剧本行序号
    character_name: Optional[str] = None  # 角色名（从剧本行获取）
    processing_time: Optional[float] = None  # 处理时间（秒）
    estimated_duration: Optional[float] = None  # 预估时长（从剧本行获取）


# =============================================================================
# 异常定义
# =============================================================================

class ShotError(DatabaseError):
    """分镜操作基础异常"""
    pass


class ShotNotFoundError(ShotError):
    """分镜未找到异常"""
    pass


class ShotAlreadyExistsError(ShotError):
    """分镜已存在异常（项目ID + 序号重复）"""
    pass


class InvalidShotStatusError(ShotError):
    """分镜状态无效异常"""
    pass


class ShotGenerationError(ShotError):
    """分镜生成失败异常（AI生图、TTS等失败）"""
    pass


class SimilarityScoreError(ShotError):
    """相似度分数验证失败异常"""
    pass


class ResourceNotFoundError(ShotError):
    """资源文件未找到异常（图片、音频文件）"""
    pass


# =============================================================================
# 主类接口实现
# =============================================================================

class ShotManager:
    """分镜管理器（CRUD操作）

    职责：
        1. 分镜创建、读取、更新、删除
        2. 生成状态管理（pending → generating → completed/failed）
        3. 相似度分数管理（用于首帧锁定验证）
        4. 资源文件路径管理（图片、音频）
        5. 剧本行关联管理
        6. 分镜查询和过滤
    """

    def __init__(self, database: Database) -> None:
        """
        初始化分镜管理器

        Args:
            database: 数据库实例
        """
        raise NotImplementedError

    # =========================================================================
    # 基本CRUD操作
    # =========================================================================

    def create(self, shot_data: ShotCreate) -> Shot:
        """
        创建新分镜

        Args:
            shot_data: 分镜创建数据

        Returns:
            Shot: 创建的分镜对象

        Raises:
            ShotError: 创建失败
            ShotAlreadyExistsError: 序号在项目中已存在
        """
        raise NotImplementedError

    def get_by_id(self, shot_id: int) -> Shot:
        """
        根据ID获取分镜

        Args:
            shot_id: 分镜ID

        Returns:
            Shot: 分镜对象

        Raises:
            ShotNotFoundError: 分镜不存在
            ShotError: 查询失败
        """
        raise NotImplementedError

    def get_by_project_and_sequence(
        self,
        project_id: int,
        sequence: int
    ) -> Shot:
        """
        根据项目ID和序号获取分镜

        Args:
            project_id: 项目ID
            sequence: 序号

        Returns:
            Shot: 分镜对象

        Raises:
            ShotNotFoundError: 分镜不存在
            ShotError: 查询失败
        """
        raise NotImplementedError

    def update(self, shot_id: int, update_data: ShotUpdate) -> Shot:
        """
        更新分镜信息

        Args:
            shot_id: 分镜ID
            update_data: 更新数据

        Returns:
            Shot: 更新后的分镜对象

        Raises:
            ShotNotFoundError: 分镜不存在
            ShotAlreadyExistsError: 新序号在项目中已存在
            ShotError: 更新失败
        """
        raise NotImplementedError

    def delete(self, shot_id: int) -> bool:
        """
        删除分镜

        Args:
            shot_id: 分镜ID

        Returns:
            bool: 删除是否成功

        Raises:
            ShotNotFoundError: 分镜不存在
            ShotError: 删除失败
        """
        raise NotImplementedError

    # =========================================================================
    # 状态管理操作
    # =========================================================================

    def update_status(self, shot_id: int, new_status: ShotStatus) -> Shot:
        """
        更新分镜状态

        Args:
            shot_id: 分镜ID
            new_status: 新状态

        Returns:
            Shot: 更新后的分镜对象

        Raises:
            ShotNotFoundError: 分镜不存在
            InvalidShotStatusError: 状态转换无效
            ShotError: 更新失败
        """
        raise NotImplementedError

    def mark_as_generating(self, shot_id: int) -> Shot:
        """
        标记分镜为生成中

        Args:
            shot_id: 分镜ID

        Returns:
            Shot: 更新后的分镜对象
        """
        raise NotImplementedError

    def mark_as_completed(
        self,
        shot_id: int,
        generated_image_path: Path,
        tts_audio_path: Path,
        actual_duration: float,
        subtitle_start: float,
        subtitle_end: float,
        similarity_score: Optional[float] = None,
    ) -> Shot:
        """
        标记分镜为已完成

        Args:
            shot_id: 分镜ID
            generated_image_path: 生成的图片路径
            tts_audio_path: TTS音频路径
            actual_duration: 实际时长（秒）
            subtitle_start: 字幕开始时间（秒）
            subtitle_end: 字幕结束时间（秒）
            similarity_score: 相似度分数（可选）

        Returns:
            Shot: 更新后的分镜对象

        Raises:
            ShotNotFoundError: 分镜不存在
            ResourceNotFoundError: 资源文件未找到
            ShotError: 更新失败
        """
        raise NotImplementedError

    def mark_as_failed(self, shot_id: int, error_message: Optional[str] = None) -> Shot:
        """
        标记分镜为失败

        Args:
            shot_id: 分镜ID
            error_message: 错误信息（可选）

        Returns:
            Shot: 更新后的分镜对象
        """
        raise NotImplementedError

    def reset_to_pending(self, shot_id: int) -> Shot:
        """
        重置分镜为待处理状态

        Args:
            shot_id: 分镜ID

        Returns:
            Shot: 更新后的分镜对象
        """
        raise NotImplementedError

    # =========================================================================
    # 查询和列表操作
    # =========================================================================

    def get_by_project(
        self,
        project_id: int,
        status: Optional[ShotStatus] = None,
        limit: int = 100,
        offset: int = 0,
        order_by_sequence: bool = True,
    ) -> List[Shot]:
        """
        获取指定项目的所有分镜

        Args:
            project_id: 项目ID
            status: 按状态过滤（可选）
            limit: 返回数量限制
            offset: 偏移量
            order_by_sequence: 是否按序号排序

        Returns:
            List[Shot]: 分镜列表
        """
        raise NotImplementedError

    def get_by_script_line(self, script_line_id: int) -> List[Shot]:
        """
        获取指定剧本行的所有分镜

        Args:
            script_line_id: 剧本行ID

        Returns:
            List[Shot]: 分镜列表
        """
        raise NotImplementedError

    def get_by_status(
        self,
        status: ShotStatus,
        project_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Shot]:
        """
        获取指定状态的所有分镜

        Args:
            status: 分镜状态
            project_id: 按项目ID过滤（可选）
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            List[Shot]: 分镜列表
        """
        raise NotImplementedError

    def list_all(
        self,
        project_id: Optional[int] = None,
        status: Optional[ShotStatus] = None,
        script_line_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Shot]:
        """
        列出所有分镜（带过滤条件）

        Args:
            project_id: 按项目ID过滤（可选）
            status: 按状态过滤（可选）
            script_line_id: 按剧本行ID过滤（可选）
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            List[Shot]: 分镜列表
        """
        raise NotImplementedError

    def count(
        self,
        project_id: Optional[int] = None,
        status: Optional[ShotStatus] = None,
    ) -> int:
        """
        统计分镜数量

        Args:
            project_id: 按项目ID过滤（可选）
            status: 按状态过滤（可选）

        Returns:
            int: 分镜数量
        """
        raise NotImplementedError

    def search_by_scene_description(
        self,
        project_id: Optional[int] = None,
        query: str = "",
        limit: int = 50,
    ) -> List[Shot]:
        """
        按画面描述搜索分镜

        Args:
            project_id: 按项目ID过滤（可选）
            query: 搜索关键词
            limit: 返回数量限制

        Returns:
            List[Shot]: 匹配的分镜列表
        """
        raise NotImplementedError

    # =========================================================================
    # 批量操作
    # =========================================================================

    def batch_create(self, shots_data: List[ShotCreate]) -> List[Shot]:
        """
        批量创建分镜

        Args:
            shots_data: 分镜创建数据列表

        Returns:
            List[Shot]: 创建的分镜列表

        Raises:
            ShotError: 批量创建失败
        """
        raise NotImplementedError

    def batch_update_status(
        self,
        shot_ids: List[int],
        new_status: ShotStatus,
    ) -> List[Shot]:
        """
        批量更新分镜状态

        Args:
            shot_ids: 分镜ID列表
            new_status: 新状态

        Returns:
            List[Shot]: 更新后的分镜列表

        Raises:
            ShotError: 批量更新失败
        """
        raise NotImplementedError

    def batch_delete(self, shot_ids: List[int]) -> Dict[str, Any]:
        """
        批量删除分镜

        Args:
            shot_ids: 分镜ID列表

        Returns:
            Dict[str, Any]: 删除结果统计
        """
        raise NotImplementedError

    # =========================================================================
    # 资源文件管理
    # =========================================================================

    def update_image_path(self, shot_id: int, image_path: Path) -> Shot:
        """
        更新分镜的图片路径

        Args:
            shot_id: 分镜ID
            image_path: 图片路径

        Returns:
            Shot: 更新后的分镜对象

        Raises:
            ShotNotFoundError: 分镜不存在
            ResourceNotFoundError: 图片文件未找到
            ShotError: 更新失败
        """
        raise NotImplementedError

    def update_audio_path(self, shot_id: int, audio_path: Path) -> Shot:
        """
        更新分镜的音频路径

        Args:
            shot_id: 分镜ID
            audio_path: 音频路径

        Returns:
            Shot: 更新后的分镜对象

        Raises:
            ShotNotFoundError: 分镜不存在
            ResourceNotFoundError: 音频文件未找到
            ShotError: 更新失败
        """
        raise NotImplementedError

    def validate_resources(self, shot_id: int) -> Dict[str, bool]:
        """
        验证分镜的资源文件是否存在

        Args:
            shot_id: 分镜ID

        Returns:
            Dict[str, bool]: 资源验证结果
        """
        raise NotImplementedError

    def get_resource_paths(self, shot_id: int) -> Dict[str, Optional[Path]]:
        """
        获取分镜的资源文件路径

        Args:
            shot_id: 分镜ID

        Returns:
            Dict[str, Optional[Path]]: 资源路径字典
        """
        raise NotImplementedError

    # =========================================================================
    # 相似度分数管理
    # =========================================================================

    def update_similarity_score(
        self,
        shot_id: int,
        similarity_score: float,
    ) -> Shot:
        """
        更新分镜的相似度分数

        Args:
            shot_id: 分镜ID
            similarity_score: 相似度分数（0-100）

        Returns:
            Shot: 更新后的分镜对象

        Raises:
            ShotNotFoundError: 分镜不存在
            SimilarityScoreError: 相似度分数无效（不在0-100范围内）
            ShotError: 更新失败
        """
        raise NotImplementedError

    def get_similarity_stats(self, project_id: int) -> Dict[str, Any]:
        """
        获取项目的相似度分数统计

        Args:
            project_id: 项目ID

        Returns:
            Dict[str, Any]: 相似度统计信息
        """
        raise NotImplementedError

    def get_low_similarity_shots(
        self,
        project_id: int,
        threshold: float = 80.0,
        limit: int = 100,
    ) -> List[Shot]:
        """
        获取低于相似度阈值的分镜

        Args:
            project_id: 项目ID
            threshold: 相似度阈值（默认80）
            limit: 返回数量限制

        Returns:
            List[Shot]: 低相似度分镜列表
        """
        raise NotImplementedError

    # =========================================================================
    # 时长和时间戳管理
    # =========================================================================

    def update_duration(
        self,
        shot_id: int,
        actual_duration: float,
        subtitle_start: float,
        subtitle_end: float,
    ) -> Shot:
        """
        更新分镜的时长和字幕时间戳

        Args:
            shot_id: 分镜ID
            actual_duration: 实际时长（秒）
            subtitle_start: 字幕开始时间（秒）
            subtitle_end: 字幕结束时间（秒）

        Returns:
            Shot: 更新后的分镜对象

        Raises:
            ShotNotFoundError: 分镜不存在
            ShotError: 更新失败
        """
        raise NotImplementedError

    def calculate_total_duration(self, project_id: int) -> float:
        """
        计算项目的分镜总时长

        Args:
            project_id: 项目ID

        Returns:
            float: 总时长（秒）
        """
        raise NotImplementedError

    def get_timeline(self, project_id: int) -> List[Dict[str, Any]]:
        """
        获取项目的时间线信息

        Args:
            project_id: 项目ID

        Returns:
            List[Dict[str, Any]]: 时间线信息列表
        """
        raise NotImplementedError

    # =========================================================================
    # 统计和报表
    # =========================================================================

    def get_statistics(self, project_id: Optional[int] = None) -> Dict[str, Any]:
        """
        获取分镜统计信息

        Args:
            project_id: 按项目ID过滤（可选）

        Returns:
            Dict[str, Any]: 统计信息
        """
        raise NotImplementedError

    def get_with_stats(self, shot_id: int) -> ShotWithStats:
        """
        获取分镜及其统计信息

        Args:
            shot_id: 分镜ID

        Returns:
            ShotWithStats: 包含统计信息的分镜对象
        """
        raise NotImplementedError

    def get_status_distribution(self, project_id: int) -> Dict[str, int]:
        """
        获取状态分布统计

        Args:
            project_id: 项目ID

        Returns:
            Dict[str, int]: 状态->数量映射
        """
        raise NotImplementedError

    def get_emotion_distribution(self, project_id: int) -> Dict[str, int]:
        """
        获取情绪分布统计

        Args:
            project_id: 项目ID

        Returns:
            Dict[str, int]: 情绪->数量映射
        """
        raise NotImplementedError

    # =========================================================================
    # 序列号管理
    # =========================================================================

    def get_next_sequence(self, project_id: int) -> int:
        """
        获取项目的下一个可用序号

        Args:
            project_id: 项目ID

        Returns:
            int: 下一个序号
        """
        raise NotImplementedError

    def reorder_sequences(self, project_id: int) -> bool:
        """
        重新排序项目的分镜序号（确保连续）

        Args:
            project_id: 项目ID

        Returns:
            bool: 是否成功重新排序

        Raises:
            ShotError: 重新排序失败
        """
        raise NotImplementedError

    # =========================================================================
    # 辅助方法
    # =========================================================================

    def _get_last_insert_id(self) -> int:
        """获取最后插入的ID"""
        raise NotImplementedError

    def _validate_sequence(self, project_id: int, sequence: int) -> bool:
        """验证序号在项目中是否可用"""
        raise NotImplementedError

    def _is_valid_status_transition(
        self,
        current_status: ShotStatus,
        new_status: ShotStatus,
    ) -> bool:
        """验证状态转换是否有效"""
        raise NotImplementedError


# =============================================================================
# 导出列表
# =============================================================================

__all__ = [
    # 数据模型
    "Shot",
    "ShotCreate",
    "ShotUpdate",
    "ShotWithStats",
    "ShotStatus",
    # 异常
    "ShotError",
    "ShotNotFoundError",
    "ShotAlreadyExistsError",
    "InvalidShotStatusError",
    "ShotGenerationError",
    "SimilarityScoreError",
    "ResourceNotFoundError",
    # 主类
    "ShotManager",
]