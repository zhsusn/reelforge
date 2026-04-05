"""
分镜数据模型和CRUD操作
版本：v1.0
文件映射：docs/02-architecture/database-schema.sql (shots表)

职责：分镜数据的创建、读取、更新、删除操作，生成状态管理，相似度验证
依赖：src/reelforge/models/database/ (Database, DatabaseError等)
     src/reelforge/models/script_lines.py (关联剧本行)
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
        self._db = database
        self._logger = logging.getLogger(__name__)

        # 确保数据库已连接
        try:
            self._db.connect()
        except Exception as e:
            raise ShotError(f"Database connection failed: {e}") from e

    # =========================================================================
    # 私有方法
    # =========================================================================

    def _get_last_insert_id(self) -> int:
        """获取最后插入的ID"""
        try:
            result = self._db.query("SELECT last_insert_rowid() as id", ())
            rows = list(result)
            if not rows:
                raise ShotError("No last insert ID found")
            return int(rows[0]["id"])
        except DatabaseError as e:
            raise ShotError(f"Failed to get last insert ID: {e}") from e

    def _validate_sequence(self, project_id: int, sequence: int) -> bool:
        """验证序号在项目中是否可用"""
        try:
            sql = "SELECT COUNT(*) as count FROM shots WHERE project_id = ? AND sequence = ?"
            result = self._db.query(sql, (project_id, sequence))
            row = list(result)[0]
            return int(row["count"]) == 0
        except DatabaseError as e:
            self._logger.error(f"Failed to validate sequence: {e}")
            return False

    def _is_valid_status_transition(
        self,
        current_status: ShotStatus,
        new_status: ShotStatus,
    ) -> bool:
        """验证状态转换是否有效"""
        # 定义允许的状态转换
        valid_transitions = {
            ShotStatus.PENDING: [ShotStatus.GENERATING, ShotStatus.FAILED],
            ShotStatus.GENERATING: [ShotStatus.COMPLETED, ShotStatus.FAILED],
            ShotStatus.COMPLETED: [],  # 完成后不能再转换
            ShotStatus.FAILED: [ShotStatus.PENDING, ShotStatus.GENERATING],  # 可以重试
        }

        # 如果状态未定义或相同状态，允许转换（自身转换用于更新其他字段）
        if current_status == new_status:
            return True

        # 检查是否允许转换
        return new_status in valid_transitions.get(current_status, [])

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
        self._logger.info(f"Creating shot for project {shot_data.project_id}, sequence {shot_data.sequence}")

        # 验证数据
        if shot_data.project_id <= 0:
            raise ShotError("Project ID must be positive")

        if shot_data.sequence <= 0:
            raise ShotError("Sequence must be positive")

        if not shot_data.scene_description.strip():
            raise ShotError("Scene description cannot be empty")

        if not shot_data.dialogue.strip():
            raise ShotError("Dialogue cannot be empty")

        if not shot_data.emotion.strip():
            raise ShotError("Emotion cannot be empty")

        # 检查序号是否可用
        if not self._validate_sequence(shot_data.project_id, shot_data.sequence):
            raise ShotAlreadyExistsError(
                f"Shot with sequence {shot_data.sequence} already exists in project {shot_data.project_id}"
            )

        # 构建SQL
        sql = """
        INSERT INTO shots (
            project_id, script_line_id, sequence, scene_description, dialogue, emotion,
            camera_movement, shot_type, status,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """

        params = (
            shot_data.project_id,
            shot_data.script_line_id,
            shot_data.sequence,
            shot_data.scene_description.strip(),
            shot_data.dialogue.strip(),
            shot_data.emotion.strip(),
            shot_data.camera_movement,
            shot_data.shot_type,
            ShotStatus.PENDING.value,
        )

        try:
            # 执行插入
            affected = self._db.execute(sql, params)
            if affected != 1:
                raise ShotError(f"Failed to create shot: affected rows={affected}")

            # 通过项目ID和序号获取新创建的分镜
            return self.get_by_project_and_sequence(shot_data.project_id, shot_data.sequence)

        except DatabaseError as e:
            raise ShotError(f"Failed to create shot: {e}") from e

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
        self._logger.debug(f"Getting shot by ID: {shot_id}")

        sql = """
        SELECT id, project_id, script_line_id, sequence, scene_description, dialogue, emotion,
               camera_movement, shot_type, status,
               generated_image_path, tts_audio_path, actual_duration,
               subtitle_start, subtitle_end, similarity_score,
               created_at, updated_at
        FROM shots
        WHERE id = ?
        """

        try:
            result = self._db.query(sql, (shot_id,))
            rows = list(result)

            if not rows:
                raise ShotNotFoundError(f"Shot with ID {shot_id} not found")

            if len(rows) > 1:
                self._logger.warning(f"Multiple shots found with ID {shot_id}")

            return Shot.from_row(dict(rows[0]))

        except DatabaseError as e:
            raise ShotError(f"Failed to get shot by ID: {e}") from e

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
        self._logger.debug(f"Getting shot for project {project_id}, sequence {sequence}")

        sql = """
        SELECT id, project_id, script_line_id, sequence, scene_description, dialogue, emotion,
               camera_movement, shot_type, status,
               generated_image_path, tts_audio_path, actual_duration,
               subtitle_start, subtitle_end, similarity_score,
               created_at, updated_at
        FROM shots
        WHERE project_id = ? AND sequence = ?
        """

        try:
            result = self._db.query(sql, (project_id, sequence))
            rows = list(result)

            if not rows:
                raise ShotNotFoundError(f"Shot with project {project_id} and sequence {sequence} not found")

            if len(rows) > 1:
                self._logger.warning(f"Multiple shots found with project {project_id} and sequence {sequence}")

            return Shot.from_row(dict(rows[0]))

        except DatabaseError as e:
            raise ShotError(f"Failed to get shot by project and sequence: {e}") from e

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
        self._logger.info(f"Updating shot {shot_id}")

        # 检查分镜是否存在
        shot = self.get_by_id(shot_id)

        # 构建更新SQL
        updates = []
        params: List[Any] = []

        # 验证并构建更新字段
        if update_data.sequence is not None:
            if update_data.sequence <= 0:
                raise ShotError("Sequence must be positive")

            # 检查新序号是否可用（如果更改了序号）
            if update_data.sequence != shot.sequence:
                if not self._validate_sequence(shot.project_id, update_data.sequence):
                    raise ShotAlreadyExistsError(
                        f"Shot with sequence {update_data.sequence} already exists in project {shot.project_id}"
                    )
            updates.append("sequence = ?")
            params.append(update_data.sequence)

        if update_data.scene_description is not None:
            if not update_data.scene_description.strip():
                raise ShotError("Scene description cannot be empty")
            updates.append("scene_description = ?")
            params.append(update_data.scene_description.strip())

        if update_data.dialogue is not None:
            if not update_data.dialogue.strip():
                raise ShotError("Dialogue cannot be empty")
            updates.append("dialogue = ?")
            params.append(update_data.dialogue.strip())

        if update_data.emotion is not None:
            if not update_data.emotion.strip():
                raise ShotError("Emotion cannot be empty")
            updates.append("emotion = ?")
            params.append(update_data.emotion.strip())

        if update_data.camera_movement is not None:
            updates.append("camera_movement = ?")
            params.append(update_data.camera_movement)

        if update_data.shot_type is not None:
            updates.append("shot_type = ?")
            params.append(update_data.shot_type)

        if update_data.status is not None:
            # 验证状态转换
            if not self._is_valid_status_transition(shot.status, update_data.status):
                raise InvalidShotStatusError(
                    f"Invalid status transition: {shot.status} -> {update_data.status}"
                )
            updates.append("status = ?")
            params.append(update_data.status.value)

        if update_data.generated_image_path is not None:
            updates.append("generated_image_path = ?")
            params.append(str(update_data.generated_image_path))

        if update_data.tts_audio_path is not None:
            updates.append("tts_audio_path = ?")
            params.append(str(update_data.tts_audio_path))

        if update_data.actual_duration is not None:
            if update_data.actual_duration < 0:
                raise ShotError("Actual duration cannot be negative")
            updates.append("actual_duration = ?")
            params.append(update_data.actual_duration)

        if update_data.subtitle_start is not None:
            if update_data.subtitle_start < 0:
                raise ShotError("Subtitle start time cannot be negative")
            updates.append("subtitle_start = ?")
            params.append(update_data.subtitle_start)

        if update_data.subtitle_end is not None:
            if update_data.subtitle_end < 0:
                raise ShotError("Subtitle end time cannot be negative")
            if (update_data.subtitle_start is not None and
                update_data.subtitle_end <= update_data.subtitle_start):
                raise ShotError("Subtitle end time must be after start time")
            updates.append("subtitle_end = ?")
            params.append(update_data.subtitle_end)

        if update_data.similarity_score is not None:
            if update_data.similarity_score < 0 or update_data.similarity_score > 100:
                raise SimilarityScoreError("Similarity score must be between 0 and 100")
            updates.append("similarity_score = ?")
            params.append(update_data.similarity_score)

        # 如果没有更新内容，直接返回原分镜
        if not updates:
            return shot

        # 添加updated_at自动更新
        updates.append("updated_at = CURRENT_TIMESTAMP")

        # 构建完整SQL
        sql = f"""
        UPDATE shots
        SET {', '.join(updates)}
        WHERE id = ?
        """

        params.append(shot_id)

        try:
            affected = self._db.execute(sql, tuple(params))
            if affected != 1:
                raise ShotError(f"Failed to update shot: affected rows={affected}")

            return self.get_by_id(shot_id)

        except DatabaseError as e:
            raise ShotError(f"Failed to update shot: {e}") from e

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
        self._logger.info(f"Deleting shot {shot_id}")

        # 检查分镜是否存在
        self.get_by_id(shot_id)

        sql = "DELETE FROM shots WHERE id = ?"

        try:
            affected = self._db.execute(sql, (shot_id,))
            success = affected == 1
            if success:
                self._logger.info(f"Deleted shot {shot_id}")
            else:
                self._logger.warning(f"Shot {shot_id} not found")
            return success

        except DatabaseError as e:
            raise ShotError(f"Failed to delete shot: {e}") from e

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
        self._logger.info(f"Updating shot {shot_id} status to {new_status}")

        update_data = ShotUpdate(status=new_status)
        return self.update(shot_id, update_data)

    def mark_as_generating(self, shot_id: int) -> Shot:
        """
        标记分镜为生成中

        Args:
            shot_id: 分镜ID

        Returns:
            Shot: 更新后的分镜对象
        """
        self._logger.info(f"Marking shot {shot_id} as generating")
        return self.update_status(shot_id, ShotStatus.GENERATING)

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
        self._logger.info(f"Marking shot {shot_id} as completed")

        # 验证资源文件是否存在
        if not generated_image_path.exists():
            raise ResourceNotFoundError(f"Generated image not found: {generated_image_path}")

        if not tts_audio_path.exists():
            raise ResourceNotFoundError(f"TTS audio not found: {tts_audio_path}")

        # 验证时长
        if actual_duration <= 0:
            raise ShotError("Actual duration must be positive")

        if subtitle_start < 0:
            raise ShotError("Subtitle start time cannot be negative")

        if subtitle_end < 0:
            raise ShotError("Subtitle end time cannot be negative")

        if subtitle_end <= subtitle_start:
            raise ShotError("Subtitle end time must be after start time")

        # 验证相似度分数
        if similarity_score is not None:
            if similarity_score < 0 or similarity_score > 100:
                raise SimilarityScoreError("Similarity score must be between 0 and 100")

        update_data = ShotUpdate(
            status=ShotStatus.COMPLETED,
            generated_image_path=generated_image_path,
            tts_audio_path=tts_audio_path,
            actual_duration=actual_duration,
            subtitle_start=subtitle_start,
            subtitle_end=subtitle_end,
            similarity_score=similarity_score,
        )
        return self.update(shot_id, update_data)

    def mark_as_failed(self, shot_id: int, error_message: Optional[str] = None) -> Shot:
        """
        标记分镜为失败

        Args:
            shot_id: 分镜ID
            error_message: 错误信息（可选）

        Returns:
            Shot: 更新后的分镜对象
        """
        self._logger.error(f"Marking shot {shot_id} as failed: {error_message or 'Unknown error'}")
        return self.update_status(shot_id, ShotStatus.FAILED)

    def reset_to_pending(self, shot_id: int) -> Shot:
        """
        重置分镜为待处理状态

        Args:
            shot_id: 分镜ID

        Returns:
            Shot: 更新后的分镜对象
        """
        self._logger.info(f"Resetting shot {shot_id} to pending")
        return self.update_status(shot_id, ShotStatus.PENDING)

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
        self._logger.debug(f"Getting shots for project {project_id}")

        # 验证参数
        if project_id <= 0:
            raise ShotError("Project ID must be positive")

        if limit < 0:
            raise ShotError("Limit must be non-negative")

        if offset < 0:
            raise ShotError("Offset must be non-negative")

        # 构建SQL
        where_clauses = ["project_id = ?"]
        params: List[Any] = [project_id]

        if status is not None:
            where_clauses.append("status = ?")
            params.append(status.value)

        where_sql = " AND ".join(where_clauses)

        # 排序
        order_by = "sequence ASC" if order_by_sequence else "created_at DESC"

        sql = f"""
        SELECT id, project_id, script_line_id, sequence, scene_description, dialogue, emotion,
               camera_movement, shot_type, status,
               generated_image_path, tts_audio_path, actual_duration,
               subtitle_start, subtitle_end, similarity_score,
               created_at, updated_at
        FROM shots
        WHERE {where_sql}
        ORDER BY {order_by}
        LIMIT ? OFFSET ?
        """

        params.append(limit)
        params.append(offset)

        try:
            result = self._db.query(sql, tuple(params))
            return [Shot.from_row(dict(row)) for row in result]

        except DatabaseError as e:
            raise ShotError(f"Failed to get shots by project: {e}") from e

    def get_by_script_line(self, script_line_id: int) -> List[Shot]:
        """
        获取指定剧本行的所有分镜

        Args:
            script_line_id: 剧本行ID

        Returns:
            List[Shot]: 分镜列表
        """
        self._logger.debug(f"Getting shots for script line {script_line_id}")

        # 验证参数
        if script_line_id <= 0:
            raise ShotError("Script line ID must be positive")

        sql = """
        SELECT id, project_id, script_line_id, sequence, scene_description, dialogue, emotion,
               camera_movement, shot_type, status,
               generated_image_path, tts_audio_path, actual_duration,
               subtitle_start, subtitle_end, similarity_score,
               created_at, updated_at
        FROM shots
        WHERE script_line_id = ?
        ORDER BY sequence ASC
        """

        try:
            result = self._db.query(sql, (script_line_id,))
            return [Shot.from_row(dict(row)) for row in result]

        except DatabaseError as e:
            raise ShotError(f"Failed to get shots by script line: {e}") from e

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
        self._logger.debug(f"Getting shots by status {status}")

        # 验证参数
        if limit < 0:
            raise ShotError("Limit must be non-negative")

        if offset < 0:
            raise ShotError("Offset must be non-negative")

        # 构建SQL
        where_clauses = ["status = ?"]
        params: List[Any] = [status.value]

        if project_id is not None:
            if project_id <= 0:
                raise ShotError("Project ID must be positive if provided")
            where_clauses.append("project_id = ?")
            params.append(project_id)

        where_sql = " AND ".join(where_clauses)

        sql = f"""
        SELECT id, project_id, script_line_id, sequence, scene_description, dialogue, emotion,
               camera_movement, shot_type, status,
               generated_image_path, tts_audio_path, actual_duration,
               subtitle_start, subtitle_end, similarity_score,
               created_at, updated_at
        FROM shots
        WHERE {where_sql}
        ORDER BY updated_at DESC
        LIMIT ? OFFSET ?
        """

        params.append(limit)
        params.append(offset)

        try:
            result = self._db.query(sql, tuple(params))
            return [Shot.from_row(dict(row)) for row in result]

        except DatabaseError as e:
            raise ShotError(f"Failed to get shots by status: {e}") from e

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
        self._logger.debug("Listing all shots with filters")

        # 验证参数
        if limit < 0:
            raise ShotError("Limit must be non-negative")

        if offset < 0:
            raise ShotError("Offset must be non-negative")

        # 构建SQL
        where_clauses: List[str] = []
        params: List[Any] = []

        if project_id is not None:
            if project_id <= 0:
                raise ShotError("Project ID must be positive if provided")
            where_clauses.append("project_id = ?")
            params.append(project_id)

        if status is not None:
            where_clauses.append("status = ?")
            params.append(status.value)

        if script_line_id is not None:
            if script_line_id <= 0:
                raise ShotError("Script line ID must be positive if provided")
            where_clauses.append("script_line_id = ?")
            params.append(script_line_id)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        sql = f"""
        SELECT id, project_id, script_line_id, sequence, scene_description, dialogue, emotion,
               camera_movement, shot_type, status,
               generated_image_path, tts_audio_path, actual_duration,
               subtitle_start, subtitle_end, similarity_score,
               created_at, updated_at
        FROM shots
        WHERE {where_sql}
        ORDER BY project_id ASC, sequence ASC
        LIMIT ? OFFSET ?
        """

        params.append(limit)
        params.append(offset)

        try:
            result = self._db.query(sql, tuple(params))
            return [Shot.from_row(dict(row)) for row in result]

        except DatabaseError as e:
            raise ShotError(f"Failed to list shots: {e}") from e

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
        self._logger.debug("Counting shots")

        # 构建SQL
        where_clauses: List[str] = []
        params: List[Any] = []

        if project_id is not None:
            if project_id <= 0:
                raise ShotError("Project ID must be positive if provided")
            where_clauses.append("project_id = ?")
            params.append(project_id)

        if status is not None:
            where_clauses.append("status = ?")
            params.append(status.value)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        sql = f"SELECT COUNT(*) as count FROM shots WHERE {where_sql}"

        try:
            result = self._db.query(sql, tuple(params))
            rows = list(result)
            return int(rows[0]["count"]) if rows else 0

        except DatabaseError as e:
            raise ShotError(f"Failed to count shots: {e}") from e

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
        self._logger.debug(f"Searching shots by scene description: '{query}'")

        # 验证参数
        if limit <= 0:
            raise ShotError("Limit must be positive")

        # 构建SQL
        where_clauses: List[str] = []
        params: List[Any] = []

        if project_id is not None:
            if project_id <= 0:
                raise ShotError("Project ID must be positive if provided")
            where_clauses.append("project_id = ?")
            params.append(project_id)

        if query:
            where_clauses.append("scene_description LIKE ?")
            params.append(f"%{query}%")

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        sql = f"""
        SELECT id, project_id, script_line_id, sequence, scene_description, dialogue, emotion,
               camera_movement, shot_type, status,
               generated_image_path, tts_audio_path, actual_duration,
               subtitle_start, subtitle_end, similarity_score,
               created_at, updated_at
        FROM shots
        WHERE {where_sql}
        ORDER BY sequence ASC
        LIMIT ?
        """

        params.append(limit)

        try:
            result = self._db.query(sql, tuple(params))
            return [Shot.from_row(dict(row)) for row in result]

        except DatabaseError as e:
            raise ShotError(f"Failed to search shots by scene description: {e}") from e

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
        self._logger.info(f"Batch creating {len(shots_data)} shots")

        if not shots_data:
            return []

        # 验证输入数据
        for i, shot_data in enumerate(shots_data):
            if shot_data.project_id <= 0:
                raise ShotError(f"Shot {i}: Project ID must be positive")

            if shot_data.sequence <= 0:
                raise ShotError(f"Shot {i}: Sequence must be positive")

            if not shot_data.scene_description.strip():
                raise ShotError(f"Shot {i}: Scene description cannot be empty")

            if not shot_data.dialogue.strip():
                raise ShotError(f"Shot {i}: Dialogue cannot be empty")

            if not shot_data.emotion.strip():
                raise ShotError(f"Shot {i}: Emotion cannot be empty")

        created_shots: List[Shot] = []

        try:
            # 在事务中批量创建
            with self._db.transaction() as tx:
                for shot_data in shots_data:
                    sql = """
                    INSERT INTO shots (
                        project_id, script_line_id, sequence, scene_description, dialogue, emotion,
                        camera_movement, shot_type, status,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """

                    params = (
                        shot_data.project_id,
                        shot_data.script_line_id,
                        shot_data.sequence,
                        shot_data.scene_description.strip(),
                        shot_data.dialogue.strip(),
                        shot_data.emotion.strip(),
                        shot_data.camera_movement,
                        shot_data.shot_type,
                        ShotStatus.PENDING.value,
                    )

                    cursor = tx.execute(sql, params)
                    affected = cursor.rowcount
                    if affected != 1:
                        raise ShotError(f"Failed to create shot for project {shot_data.project_id}, sequence {shot_data.sequence}")

                    # 获取最后插入的ID
                    cursor = tx.execute("SELECT last_insert_rowid() as id", ())
                    last_row = cursor.fetchone()
                    last_id = last_row["id"] if last_row else None

                    if last_id is None:
                        raise ShotError("Failed to get last insert ID")

                    # 查询创建的分镜
                    select_sql = """
                    SELECT id, project_id, script_line_id, sequence, scene_description, dialogue, emotion,
                           camera_movement, shot_type, status,
                           generated_image_path, tts_audio_path, actual_duration,
                           subtitle_start, subtitle_end, similarity_score,
                           created_at, updated_at
                    FROM shots
                    WHERE id = ?
                    """
                    cursor = tx.execute(select_sql, (last_id,))
                    shot_row = cursor.fetchone()

                    if shot_row:
                        created_shots.append(Shot.from_row(dict(shot_row)))

            self._logger.info(f"Batch created {len(created_shots)} shots successfully")
            return created_shots

        except DatabaseError as e:
            raise ShotError(f"Failed to batch create shots: {e}") from e

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
        self._logger.info(f"Batch updating status for {len(shot_ids)} shots to {new_status}")

        if not shot_ids:
            return []

        # 验证输入数据
        invalid_ids = [shot_id for shot_id in shot_ids if shot_id <= 0]
        if invalid_ids:
            raise ShotError(f"Invalid shot IDs: {invalid_ids}")

        updated_shots: List[Shot] = []

        try:
            # 在事务中批量更新
            with self._db.transaction() as tx:
                # 先检查所有分镜是否存在，并获取当前状态用于验证
                placeholders = ", ".join(["?"] * len(shot_ids))
                check_sql = f"""
                SELECT id, project_id, sequence, status
                FROM shots
                WHERE id IN ({placeholders})
                """

                cursor = tx.execute(check_sql, shot_ids)
                existing_rows = cursor.fetchall()

                if len(existing_rows) != len(shot_ids):
                    found_ids = {row["id"] for row in existing_rows}
                    missing_ids = set(shot_ids) - found_ids
                    raise ShotNotFoundError(f"Shots not found: {sorted(missing_ids)}")

                # 验证状态转换
                for row in existing_rows:
                    current_status = ShotStatus(row["status"])
                    if not self._is_valid_status_transition(current_status, new_status):
                        raise InvalidShotStatusError(
                            f"Invalid status transition for shot {row['id']}: "
                            f"{current_status} -> {new_status}"
                        )

                # 执行批量更新
                update_sql = f"""
                UPDATE shots
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id IN ({placeholders})
                """

                params = [new_status.value] + shot_ids
                cursor = tx.execute(update_sql, tuple(params))
                affected = cursor.rowcount

                if affected != len(shot_ids):
                    self._logger.warning(f"Expected to update {len(shot_ids)} shots, but affected {affected} rows")

                # 查询更新后的分镜
                select_sql = f"""
                SELECT id, project_id, script_line_id, sequence, scene_description, dialogue, emotion,
                       camera_movement, shot_type, status,
                       generated_image_path, tts_audio_path, actual_duration,
                       subtitle_start, subtitle_end, similarity_score,
                       created_at, updated_at
                FROM shots
                WHERE id IN ({placeholders})
                ORDER BY sequence ASC
                """

                cursor = tx.execute(select_sql, shot_ids)
                for row in cursor.fetchall():
                    updated_shots.append(Shot.from_row(dict(row)))

            self._logger.info(f"Batch updated status for {len(updated_shots)} shots successfully")
            return updated_shots

        except DatabaseError as e:
            raise ShotError(f"Failed to batch update status: {e}") from e

    def batch_delete(self, shot_ids: List[int]) -> Dict[str, Any]:
        """
        批量删除分镜

        Args:
            shot_ids: 分镜ID列表

        Returns:
            Dict[str, Any]: 删除结果统计
        """
        self._logger.info(f"Batch deleting {len(shot_ids)} shots")

        if not shot_ids:
            return {
                "total": 0,
                "deleted": 0,
                "failed": 0,
                "missing": [],
            }

        # 验证输入数据
        invalid_ids = [shot_id for shot_id in shot_ids if shot_id <= 0]
        if invalid_ids:
            raise ShotError(f"Invalid shot IDs: {invalid_ids}")

        try:
            # 在事务中批量删除
            with self._db.transaction() as tx:
                # 检查存在的分镜
                placeholders = ", ".join(["?"] * len(shot_ids))
                check_sql = f"""
                SELECT id, project_id, sequence
                FROM shots
                WHERE id IN ({placeholders})
                """

                cursor = tx.execute(check_sql, shot_ids)
                existing_rows = cursor.fetchall()
                existing_shots = {row["id"] for row in existing_rows}
                missing_ids = set(shot_ids) - existing_shots

                # 执行批量删除
                delete_sql = f"""
                DELETE FROM shots
                WHERE id IN ({placeholders})
                """

                cursor = tx.execute(delete_sql, shot_ids)
                affected = cursor.rowcount

                result = {
                    "total": len(shot_ids),
                    "deleted": affected,
                    "failed": len(missing_ids),
                    "missing": sorted(missing_ids),
                }

            self._logger.info(f"Batch deleted {affected} shots (missing: {len(missing_ids)})")
            return result

        except DatabaseError as e:
            raise ShotError(f"Failed to batch delete shots: {e}") from e

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
        self._logger.info(f"Updating image path for shot {shot_id}: {image_path}")

        # 验证图片文件是否存在
        if not image_path.exists():
            raise ResourceNotFoundError(f"Image file not found: {image_path}")

        # 验证分镜是否存在
        shot = self.get_by_id(shot_id)

        # 验证文件路径格式
        if not str(image_path).strip():
            raise ShotError("Image path cannot be empty")

        update_data = ShotUpdate(generated_image_path=image_path)
        return self.update(shot_id, update_data)

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
        self._logger.info(f"Updating audio path for shot {shot_id}: {audio_path}")

        # 验证音频文件是否存在
        if not audio_path.exists():
            raise ResourceNotFoundError(f"Audio file not found: {audio_path}")

        # 验证分镜是否存在
        shot = self.get_by_id(shot_id)

        # 验证文件路径格式
        if not str(audio_path).strip():
            raise ShotError("Audio path cannot be empty")

        update_data = ShotUpdate(tts_audio_path=audio_path)
        return self.update(shot_id, update_data)

    def validate_resources(self, shot_id: int) -> Dict[str, bool]:
        """
        验证分镜的资源文件是否存在

        Args:
            shot_id: 分镜ID

        Returns:
            Dict[str, bool]: 资源验证结果
        """
        self._logger.debug(f"Validating resources for shot {shot_id}")

        # 获取分镜
        shot = self.get_by_id(shot_id)

        result: Dict[str, bool] = {}

        # 验证图片文件
        if shot.generated_image_path:
            result["image_exists"] = shot.generated_image_path.exists()
            result["image_path"] = str(shot.generated_image_path)
        else:
            result["image_exists"] = False
            result["image_path"] = None

        # 验证音频文件
        if shot.tts_audio_path:
            result["audio_exists"] = shot.tts_audio_path.exists()
            result["audio_path"] = str(shot.tts_audio_path)
        else:
            result["audio_exists"] = False
            result["audio_path"] = None

        # 计算总体验证结果
        result["all_resources_exist"] = (
            (shot.generated_image_path is None or result["image_exists"]) and
            (shot.tts_audio_path is None or result["audio_exists"])
        )

        return result

    def get_resource_paths(self, shot_id: int) -> Dict[str, Optional[Path]]:
        """
        获取分镜的资源文件路径

        Args:
            shot_id: 分镜ID

        Returns:
            Dict[str, Optional[Path]]: 资源路径字典
        """
        self._logger.debug(f"Getting resource paths for shot {shot_id}")

        # 获取分镜
        shot = self.get_by_id(shot_id)

        return {
            "generated_image_path": shot.generated_image_path,
            "tts_audio_path": shot.tts_audio_path,
        }

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
        self._logger.info(f"Updating similarity score for shot {shot_id} to {similarity_score}")

        # 验证相似度分数
        if similarity_score < 0 or similarity_score > 100:
            raise SimilarityScoreError("Similarity score must be between 0 and 100")

        # 验证分镜是否存在
        self.get_by_id(shot_id)

        update_data = ShotUpdate(similarity_score=similarity_score)
        return self.update(shot_id, update_data)

    def get_similarity_stats(self, project_id: int) -> Dict[str, Any]:
        """
        获取项目的相似度分数统计

        Args:
            project_id: 项目ID

        Returns:
            Dict[str, Any]: 相似度统计信息
        """
        self._logger.debug(f"Getting similarity stats for project {project_id}")

        # 验证项目ID
        if project_id <= 0:
            raise ShotError("Project ID must be positive")

        sql = """
        SELECT
            COUNT(*) as total_shots,
            COUNT(similarity_score) as scored_shots,
            AVG(similarity_score) as average_score,
            MIN(similarity_score) as min_score,
            MAX(similarity_score) as max_score,
            SUM(CASE WHEN similarity_score >= 90 THEN 1 ELSE 0 END) as high_similarity,
            SUM(CASE WHEN similarity_score >= 80 AND similarity_score < 90 THEN 1 ELSE 0 END) as medium_similarity,
            SUM(CASE WHEN similarity_score < 80 THEN 1 ELSE 0 END) as low_similarity
        FROM shots
        WHERE project_id = ? AND status = ? AND similarity_score IS NOT NULL
        """

        try:
            result = self._db.query(sql, (project_id, ShotStatus.COMPLETED.value))
            rows = list(result)

            if not rows or rows[0]["total_shots"] == 0:
                return {
                    "total_shots": 0,
                    "scored_shots": 0,
                    "average_score": None,
                    "min_score": None,
                    "max_score": None,
                    "high_similarity": 0,
                    "medium_similarity": 0,
                    "low_similarity": 0,
                }

            row = dict(rows[0])
            return {
                "total_shots": int(row["total_shots"]),
                "scored_shots": int(row["scored_shots"]),
                "average_score": float(row["average_score"]) if row["average_score"] else None,
                "min_score": float(row["min_score"]) if row["min_score"] else None,
                "max_score": float(row["max_score"]) if row["max_score"] else None,
                "high_similarity": int(row["high_similarity"]),
                "medium_similarity": int(row["medium_similarity"]),
                "low_similarity": int(row["low_similarity"]),
            }

        except DatabaseError as e:
            raise ShotError(f"Failed to get similarity stats: {e}") from e

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
        self._logger.debug(f"Getting low similarity shots for project {project_id} (threshold: {threshold})")

        # 验证参数
        if project_id <= 0:
            raise ShotError("Project ID must be positive")

        if threshold < 0 or threshold > 100:
            raise SimilarityScoreError("Threshold must be between 0 and 100")

        if limit <= 0:
            raise ShotError("Limit must be positive")

        sql = """
        SELECT id, project_id, script_line_id, sequence, scene_description, dialogue, emotion,
               camera_movement, shot_type, status,
               generated_image_path, tts_audio_path, actual_duration,
               subtitle_start, subtitle_end, similarity_score,
               created_at, updated_at
        FROM shots
        WHERE project_id = ?
          AND status = ?
          AND similarity_score IS NOT NULL
          AND similarity_score < ?
        ORDER BY similarity_score ASC, sequence ASC
        LIMIT ?
        """

        try:
            result = self._db.query(sql, (
                project_id,
                ShotStatus.COMPLETED.value,
                threshold,
                limit
            ))
            return [Shot.from_row(dict(row)) for row in result]

        except DatabaseError as e:
            raise ShotError(f"Failed to get low similarity shots: {e}") from e

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
        self._logger.info(f"Updating duration for shot {shot_id}")

        # 验证参数
        if actual_duration <= 0:
            raise ShotError("Actual duration must be positive")

        if subtitle_start < 0:
            raise ShotError("Subtitle start time cannot be negative")

        if subtitle_end < 0:
            raise ShotError("Subtitle end time cannot be negative")

        if subtitle_end <= subtitle_start:
            raise ShotError("Subtitle end time must be after start time")

        # 验证分镜是否存在
        self.get_by_id(shot_id)

        update_data = ShotUpdate(
            actual_duration=actual_duration,
            subtitle_start=subtitle_start,
            subtitle_end=subtitle_end,
        )
        return self.update(shot_id, update_data)

    def calculate_total_duration(self, project_id: int) -> float:
        """
        计算项目的分镜总时长

        Args:
            project_id: 项目ID

        Returns:
            float: 总时长（秒）
        """
        self._logger.debug(f"Calculating total duration for project {project_id}")

        # 验证项目ID
        if project_id <= 0:
            raise ShotError("Project ID must be positive")

        sql = """
        SELECT COALESCE(SUM(actual_duration), 0.0) as total_duration
        FROM shots
        WHERE project_id = ? AND status = ? AND actual_duration IS NOT NULL
        """

        try:
            result = self._db.query(sql, (project_id, ShotStatus.COMPLETED.value))
            rows = list(result)

            if not rows:
                return 0.0

            total_duration = float(rows[0]["total_duration"])
            return total_duration

        except DatabaseError as e:
            raise ShotError(f"Failed to calculate total duration: {e}") from e

    def get_timeline(self, project_id: int) -> List[Dict[str, Any]]:
        """
        获取项目的时间线信息

        Args:
            project_id: 项目ID

        Returns:
            List[Dict[str, Any]]: 时间线信息列表
        """
        self._logger.debug(f"Getting timeline for project {project_id}")

        # 验证项目ID
        if project_id <= 0:
            raise ShotError("Project ID must be positive")

        sql = """
        SELECT
            id,
            sequence,
            scene_description,
            dialogue,
            emotion,
            status,
            actual_duration,
            subtitle_start,
            subtitle_end,
            similarity_score,
            generated_image_path,
            tts_audio_path
        FROM shots
        WHERE project_id = ? AND status = ?
        ORDER BY sequence ASC
        """

        try:
            result = self._db.query(sql, (project_id, ShotStatus.COMPLETED.value))
            timeline = []

            for row in result:
                row_dict = dict(row)
                timeline.append({
                    "shot_id": row_dict["id"],
                    "sequence": row_dict["sequence"],
                    "scene_description": row_dict["scene_description"],
                    "dialogue": row_dict["dialogue"],
                    "emotion": row_dict["emotion"],
                    "duration": float(row_dict["actual_duration"]) if row_dict["actual_duration"] else None,
                    "subtitle_start": float(row_dict["subtitle_start"]) if row_dict["subtitle_start"] else None,
                    "subtitle_end": float(row_dict["subtitle_end"]) if row_dict["subtitle_end"] else None,
                    "similarity_score": float(row_dict["similarity_score"]) if row_dict["similarity_score"] else None,
                    "generated_image_path": row_dict["generated_image_path"],
                    "tts_audio_path": row_dict["tts_audio_path"],
                })

            return timeline

        except DatabaseError as e:
            raise ShotError(f"Failed to get timeline: {e}") from e

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
        self._logger.debug(f"Getting shot statistics for project {project_id}")

        # 构建SQL
        where_clauses: List[str] = []
        params: List[Any] = []

        if project_id is not None:
            if project_id <= 0:
                raise ShotError("Project ID must be positive if provided")
            where_clauses.append("project_id = ?")
            params.append(project_id)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        sql = f"""
        SELECT
            COUNT(*) as total_shots,
            SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as generating,
            SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as failed,
            COUNT(DISTINCT emotion) as distinct_emotions,
            COUNT(DISTINCT camera_movement) as distinct_camera_movements,
            COUNT(DISTINCT shot_type) as distinct_shot_types,
            COUNT(script_line_id) as shots_with_script_line,
            COALESCE(AVG(similarity_score), 0.0) as avg_similarity,
            COALESCE(AVG(actual_duration), 0.0) as avg_duration,
            COUNT(generated_image_path) as shots_with_image,
            COUNT(tts_audio_path) as shots_with_audio,
            MIN(created_at) as first_created,
            MAX(updated_at) as last_updated
        FROM shots
        WHERE {where_sql}
        """

        full_params = [
            ShotStatus.PENDING.value,
            ShotStatus.GENERATING.value,
            ShotStatus.COMPLETED.value,
            ShotStatus.FAILED.value,
        ] + params

        try:
            result = self._db.query(sql, tuple(full_params))
            rows = list(result)

            if not rows:
                return {
                    "total_shots": 0,
                    "status_distribution": {
                        "pending": 0,
                        "generating": 0,
                        "completed": 0,
                        "failed": 0,
                    },
                    "distinct_emotions": 0,
                    "distinct_camera_movements": 0,
                    "distinct_shot_types": 0,
                    "shots_with_script_line": 0,
                    "avg_similarity": 0.0,
                    "avg_duration": 0.0,
                    "shots_with_image": 0,
                    "shots_with_audio": 0,
                    "first_created": None,
                    "last_updated": None,
                }

            row = dict(rows[0])
            return {
                "total_shots": int(row["total_shots"]),
                "status_distribution": {
                    "pending": int(row["pending"]),
                    "generating": int(row["generating"]),
                    "completed": int(row["completed"]),
                    "failed": int(row["failed"]),
                },
                "distinct_emotions": int(row["distinct_emotions"]),
                "distinct_camera_movements": int(row["distinct_camera_movements"]),
                "distinct_shot_types": int(row["distinct_shot_types"]),
                "shots_with_script_line": int(row["shots_with_script_line"]),
                "avg_similarity": float(row["avg_similarity"]) if row["avg_similarity"] else 0.0,
                "avg_duration": float(row["avg_duration"]) if row["avg_duration"] else 0.0,
                "shots_with_image": int(row["shots_with_image"]),
                "shots_with_audio": int(row["shots_with_audio"]),
                "first_created": row["first_created"],
                "last_updated": row["last_updated"],
            }

        except DatabaseError as e:
            raise ShotError(f"Failed to get statistics: {e}") from e

    def get_with_stats(self, shot_id: int) -> ShotWithStats:
        """
        获取分镜及其统计信息

        Args:
            shot_id: 分镜ID

        Returns:
            ShotWithStats: 包含统计信息的分镜对象
        """
        self._logger.debug(f"Getting shot with stats for ID {shot_id}")

        # 获取基本分镜信息
        shot = self.get_by_id(shot_id)

        # 构建统计信息
        stats: Dict[str, Any] = {}

        # 如果有关联的剧本行，尝试获取额外信息
        if shot.script_line_id:
            try:
                # 尝试导入script_lines模块来获取剧本行信息
                from reelforge.models.script_lines import ScriptLineManager

                # 这里需要创建ScriptLineManager实例，但缺少database参数
                # 这是一个设计问题，应该通过依赖注入或其他方式解决
                # 目前先跳过这部分
                pass
            except ImportError:
                self._logger.debug("Script lines module not available")
            except Exception as e:
                self._logger.warning(f"Failed to get script line info: {e}")

        # 计算处理时间（如果已更新）
        if shot.status == ShotStatus.COMPLETED and shot.created_at and shot.updated_at:
            try:
                # 将ISO格式字符串转换为datetime对象
                if isinstance(shot.created_at, str):
                    from datetime import datetime
                    created_at = datetime.fromisoformat(shot.created_at)
                    updated_at = datetime.fromisoformat(shot.updated_at)
                else:
                    created_at = shot.created_at
                    updated_at = shot.updated_at

                processing_time = (updated_at - created_at).total_seconds()
                stats["processing_time"] = max(0.0, processing_time)
            except Exception as e:
                self._logger.warning(f"Failed to calculate processing time: {e}")
                stats["processing_time"] = None

        return ShotWithStats(
            shot_id=shot.shot_id,
            project_id=shot.project_id,
            script_line_id=shot.script_line_id,
            sequence=shot.sequence,
            scene_description=shot.scene_description,
            dialogue=shot.dialogue,
            emotion=shot.emotion,
            camera_movement=shot.camera_movement,
            shot_type=shot.shot_type,
            status=shot.status,
            generated_image_path=shot.generated_image_path,
            tts_audio_path=shot.tts_audio_path,
            actual_duration=shot.actual_duration,
            subtitle_start=shot.subtitle_start,
            subtitle_end=shot.subtitle_end,
            similarity_score=shot.similarity_score,
            created_at=shot.created_at,
            updated_at=shot.updated_at,
            script_line_sequence=None,  # TODO: 从script_lines获取
            character_name=None,  # TODO: 从script_lines获取
            processing_time=stats.get("processing_time"),
            estimated_duration=None,  # TODO: 从script_lines获取
        )

    def get_status_distribution(self, project_id: int) -> Dict[str, int]:
        """
        获取状态分布统计

        Args:
            project_id: 项目ID

        Returns:
            Dict[str, int]: 状态->数量映射
        """
        self._logger.debug(f"Getting status distribution for project {project_id}")

        # 验证项目ID
        if project_id <= 0:
            raise ShotError("Project ID must be positive")

        sql = """
        SELECT status, COUNT(*) as count
        FROM shots
        WHERE project_id = ?
        GROUP BY status
        ORDER BY status
        """

        try:
            result = self._db.query(sql, (project_id,))
            distribution = {}

            for row in result:
                status = str(row["status"])
                count = int(row["count"])
                distribution[status] = count

            # 确保所有状态都有值
            for status in ShotStatus:
                if status.value not in distribution:
                    distribution[status.value] = 0

            return distribution

        except DatabaseError as e:
            raise ShotError(f"Failed to get status distribution: {e}") from e

    def get_emotion_distribution(self, project_id: int) -> Dict[str, int]:
        """
        获取情绪分布统计

        Args:
            project_id: 项目ID

        Returns:
            Dict[str, int]: 情绪->数量映射
        """
        self._logger.debug(f"Getting emotion distribution for project {project_id}")

        # 验证项目ID
        if project_id <= 0:
            raise ShotError("Project ID must be positive")

        sql = """
        SELECT emotion, COUNT(*) as count
        FROM shots
        WHERE project_id = ?
        GROUP BY emotion
        ORDER BY count DESC
        """

        try:
            result = self._db.query(sql, (project_id,))
            distribution = {}

            for row in result:
                emotion = str(row["emotion"])
                count = int(row["count"])
                distribution[emotion] = count

            return distribution

        except DatabaseError as e:
            raise ShotError(f"Failed to get emotion distribution: {e}") from e

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
        self._logger.debug(f"Getting next sequence for project {project_id}")

        # 验证项目ID
        if project_id <= 0:
            raise ShotError("Project ID must be positive")

        sql = """
        SELECT COALESCE(MAX(sequence), 0) as max_sequence
        FROM shots
        WHERE project_id = ?
        """

        try:
            result = self._db.query(sql, (project_id,))
            rows = list(result)

            if not rows:
                return 1

            max_sequence = int(rows[0]["max_sequence"])
            return max_sequence + 1

        except DatabaseError as e:
            raise ShotError(f"Failed to get next sequence: {e}") from e

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
        self._logger.info(f"Reordering sequences for project {project_id}")

        # 验证项目ID
        if project_id <= 0:
            raise ShotError("Project ID must be positive")

        try:
            # 在事务中执行重新排序
            with self._db.transaction() as tx:
                # 获取项目的所有分镜，按当前序号排序
                select_sql = """
                SELECT id, sequence
                FROM shots
                WHERE project_id = ?
                ORDER BY sequence ASC, created_at ASC
                """

                cursor = tx.execute(select_sql, (project_id,))
                rows = cursor.fetchall()

                if not rows:
                    self._logger.info(f"No shots found for project {project_id}")
                    return True

                # 重新分配序号
                for new_sequence, row in enumerate(rows, start=1):
                    shot_id = row["id"]
                    old_sequence = row["sequence"]

                    # 如果序号已正确，跳过
                    if old_sequence == new_sequence:
                        continue

                    # 更新序号
                    update_sql = """
                    UPDATE shots
                    SET sequence = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """

                    cursor = tx.execute(update_sql, (new_sequence, shot_id))
                    if cursor.rowcount != 1:
                        raise ShotError(f"Failed to update sequence for shot {shot_id}")

                    self._logger.debug(f"Updated shot {shot_id}: {old_sequence} -> {new_sequence}")

                self._logger.info(f"Reordered {len(rows)} shots for project {project_id}")
                return True

        except DatabaseError as e:
            raise ShotError(f"Failed to reorder sequences: {e}") from e