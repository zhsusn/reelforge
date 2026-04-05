"""
剧本行数据模型和CRUD操作
版本：v1.0
文件映射：docs/03-architecture/database-schema.sql (script_lines表)

职责：剧本行数据的创建、读取、更新、删除操作，项目关联管理
依赖：src/reelforge/models/database/ (Database, DatabaseError等)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

from reelforge.models.database import Database, DatabaseError, QueryResult


# =============================================================================
# 数据模型定义
# =============================================================================

@dataclass
class ScriptLine:
    """剧本行数据模型

    对应数据库表：script_lines
    字段映射：
        id -> script_line_id
        project_id -> project_id
        sequence -> sequence
        character_name -> character_name
        dialogue -> dialogue
        emotion -> emotion
        knowledge_point -> knowledge_point (可选)
        camera_suggestion -> camera_suggestion (可选)
        bgm_suggestion -> bgm_suggestion (可选)
        estimated_duration -> estimated_duration (可选)
        created_at -> created_at (datetime)
    """

    script_line_id: int
    project_id: int
    sequence: int
    character_name: str
    dialogue: str
    emotion: str
    knowledge_point: Optional[str]
    camera_suggestion: Optional[str]
    bgm_suggestion: Optional[str]
    estimated_duration: Optional[float]
    created_at: datetime

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> ScriptLine:
        """从数据库行创建ScriptLine对象"""
        return cls(
            script_line_id=row["id"],
            project_id=row["project_id"],
            sequence=row["sequence"],
            character_name=row["character_name"],
            dialogue=row["dialogue"],
            emotion=row["emotion"],
            knowledge_point=row["knowledge_point"],
            camera_suggestion=row["camera_suggestion"],
            bgm_suggestion=row["bgm_suggestion"],
            estimated_duration=float(row["estimated_duration"]) if row["estimated_duration"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
        )


@dataclass
class ScriptLineCreate:
    """创建剧本行时的数据模型（输入）"""
    project_id: int
    sequence: int
    character_name: str
    dialogue: str
    emotion: str
    knowledge_point: Optional[str] = None
    camera_suggestion: Optional[str] = None
    bgm_suggestion: Optional[str] = None
    estimated_duration: Optional[float] = None


@dataclass
class ScriptLineUpdate:
    """更新剧本行时的数据模型（输入）"""
    sequence: Optional[int] = None
    character_name: Optional[str] = None
    dialogue: Optional[str] = None
    emotion: Optional[str] = None
    knowledge_point: Optional[str] = None
    camera_suggestion: Optional[str] = None
    bgm_suggestion: Optional[str] = None
    estimated_duration: Optional[float] = None


@dataclass
class ScriptLineWithStats(ScriptLine):
    """包含统计信息的剧本行数据模型"""
    shot_count: int = 0  # 关联的分镜数量
    has_completed_shot: bool = False  # 是否有已完成的分镜


# =============================================================================
# 异常定义
# =============================================================================

class ScriptLineError(DatabaseError):
    """剧本行操作基础异常"""
    pass


class ScriptLineNotFoundError(ScriptLineError):
    """剧本行未找到异常"""
    pass


class ScriptLineAlreadyExistsError(ScriptLineError):
    """剧本行已存在异常（项目ID + 序号重复）"""
    pass


class InvalidSequenceError(ScriptLineError):
    """无效的序号异常"""
    pass


class CharacterMismatchError(ScriptLineError):
    """角色名不匹配异常"""
    pass


# =============================================================================
# 主类接口实现
# =============================================================================

class ScriptLineManager:
    """剧本行管理器（CRUD操作）

    职责：
        1. 剧本行创建、读取、更新、删除
        2. 序列号管理（保证在项目内唯一且连续）
        3. 角色关联验证
        4. 剧本行查询和过滤
        5. 项目关联操作
    """

    def __init__(self, database: Database) -> None:
        """
        初始化剧本行管理器

        Args:
            database: 数据库实例
        """
        self._db = database
        self._logger = logging.getLogger(__name__)

        # 确保数据库已连接
        try:
            self._db.connect()
        except Exception as e:
            raise ScriptLineError(f"Database connection failed: {e}") from e

    # =========================================================================
    # 基本CRUD操作
    # =========================================================================

    def create(self, script_line_data: ScriptLineCreate) -> ScriptLine:
        """
        创建新剧本行

        Args:
            script_line_data: 剧本行创建数据

        Returns:
            ScriptLine: 创建的剧本行对象

        Raises:
            ScriptLineError: 创建失败
            ScriptLineAlreadyExistsError: 序号在项目中已存在
            InvalidSequenceError: 序号无效
        """
        self._logger.info(f"Creating script line for project {script_line_data.project_id}: sequence={script_line_data.sequence}")

        # 验证数据
        if script_line_data.sequence <= 0:
            raise InvalidSequenceError("Sequence must be positive integer")

        if not script_line_data.character_name.strip():
            raise ScriptLineError("Character name cannot be empty")

        if not script_line_data.dialogue.strip():
            raise ScriptLineError("Dialogue cannot be empty")

        # 检查序号是否在项目中已存在
        if not self._validate_sequence(script_line_data.project_id, script_line_data.sequence):
            raise ScriptLineAlreadyExistsError(
                f"Sequence {script_line_data.sequence} already exists in project {script_line_data.project_id}"
            )

        # 构建SQL
        sql = """
        INSERT INTO script_lines (
            project_id, sequence, character_name, dialogue, emotion,
            knowledge_point, camera_suggestion, bgm_suggestion, estimated_duration,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """

        params = (
            script_line_data.project_id,
            script_line_data.sequence,
            script_line_data.character_name.strip(),
            script_line_data.dialogue.strip(),
            script_line_data.emotion.strip(),
            script_line_data.knowledge_point,
            script_line_data.camera_suggestion,
            script_line_data.bgm_suggestion,
            script_line_data.estimated_duration,
        )

        try:
            # 执行插入
            affected = self._db.execute(sql, params)
            if affected != 1:
                raise ScriptLineError(f"Failed to create script line: affected rows={affected}")

            # 获取新创建的剧本行
            new_id = self._get_last_insert_id()
            return self.get_by_id(new_id)

        except DatabaseError as e:
            raise ScriptLineError(f"Failed to create script line: {e}") from e

    def get_by_id(self, script_line_id: int) -> ScriptLine:
        """
        根据ID获取剧本行

        Args:
            script_line_id: 剧本行ID

        Returns:
            ScriptLine: 剧本行对象

        Raises:
            ScriptLineNotFoundError: 剧本行不存在
            ScriptLineError: 查询失败
        """
        self._logger.debug(f"Getting script line by ID: {script_line_id}")

        sql = """
        SELECT id, project_id, sequence, character_name, dialogue, emotion,
               knowledge_point, camera_suggestion, bgm_suggestion, estimated_duration,
               created_at
        FROM script_lines
        WHERE id = ?
        """

        try:
            result = self._db.query(sql, (script_line_id,))
            rows = list(result)

            if not rows:
                raise ScriptLineNotFoundError(f"Script line with ID {script_line_id} not found")

            if len(rows) > 1:
                self._logger.warning(f"Multiple script lines found with ID {script_line_id}")

            return ScriptLine.from_row(dict(rows[0]))

        except DatabaseError as e:
            raise ScriptLineError(f"Failed to get script line by ID: {e}") from e

    def get_by_project_and_sequence(
        self,
        project_id: int,
        sequence: int
    ) -> ScriptLine:
        """
        根据项目ID和序号获取剧本行

        Args:
            project_id: 项目ID
            sequence: 序号

        Returns:
            ScriptLine: 剧本行对象

        Raises:
            ScriptLineNotFoundError: 剧本行不存在
            ScriptLineError: 查询失败
        """
        self._logger.debug(f"Getting script line: project={project_id}, sequence={sequence}")

        sql = """
        SELECT id, project_id, sequence, character_name, dialogue, emotion,
               knowledge_point, camera_suggestion, bgm_suggestion, estimated_duration,
               created_at
        FROM script_lines
        WHERE project_id = ? AND sequence = ?
        """

        try:
            result = self._db.query(sql, (project_id, sequence))
            rows = list(result)

            if not rows:
                raise ScriptLineNotFoundError(f"Script line not found for project {project_id}, sequence {sequence}")

            if len(rows) > 1:
                self._logger.warning(f"Multiple script lines found for project {project_id}, sequence {sequence}")

            return ScriptLine.from_row(dict(rows[0]))

        except DatabaseError as e:
            raise ScriptLineError(f"Failed to get script line: {e}") from e

    def update(self, script_line_id: int, update_data: ScriptLineUpdate) -> ScriptLine:
        """
        更新剧本行信息

        Args:
            script_line_id: 剧本行ID
            update_data: 更新数据

        Returns:
            ScriptLine: 更新后的剧本行对象

        Raises:
            ScriptLineNotFoundError: 剧本行不存在
            ScriptLineAlreadyExistsError: 新序号在项目中已存在
            ScriptLineError: 更新失败
        """
        self._logger.info(f"Updating script line {script_line_id}")

        # 获取当前剧本行
        script_line = self.get_by_id(script_line_id)

        # 如果需要更新序号，检查新序号是否可用
        if update_data.sequence is not None and update_data.sequence != script_line.sequence:
            if not self._validate_sequence(script_line.project_id, update_data.sequence, exclude_id=script_line_id):
                raise ScriptLineAlreadyExistsError(
                    f"Sequence {update_data.sequence} already exists in project {script_line.project_id}"
                )

        # 构建更新SQL
        updates = []
        params: List[Any] = []

        if update_data.sequence is not None:
            updates.append("sequence = ?")
            params.append(update_data.sequence)

        if update_data.character_name is not None:
            updates.append("character_name = ?")
            params.append(update_data.character_name.strip())

        if update_data.dialogue is not None:
            updates.append("dialogue = ?")
            params.append(update_data.dialogue.strip())

        if update_data.emotion is not None:
            updates.append("emotion = ?")
            params.append(update_data.emotion.strip())

        if update_data.knowledge_point is not None:
            updates.append("knowledge_point = ?")
            params.append(update_data.knowledge_point)

        if update_data.camera_suggestion is not None:
            updates.append("camera_suggestion = ?")
            params.append(update_data.camera_suggestion)

        if update_data.bgm_suggestion is not None:
            updates.append("bgm_suggestion = ?")
            params.append(update_data.bgm_suggestion)

        if update_data.estimated_duration is not None:
            updates.append("estimated_duration = ?")
            params.append(update_data.estimated_duration)

        # 如果没有更新内容，直接返回原剧本行
        if not updates:
            return script_line

        # 构建完整SQL
        sql = f"""
        UPDATE script_lines
        SET {', '.join(updates)}
        WHERE id = ?
        """

        params.append(script_line_id)

        try:
            affected = self._db.execute(sql, tuple(params))
            if affected != 1:
                raise ScriptLineError(f"Failed to update script line: affected rows={affected}")

            return self.get_by_id(script_line_id)

        except DatabaseError as e:
            raise ScriptLineError(f"Failed to update script line: {e}") from e

    def delete(self, script_line_id: int) -> bool:
        """
        删除剧本行

        Args:
            script_line_id: 剧本行ID

        Returns:
            bool: 删除是否成功

        Raises:
            ScriptLineNotFoundError: 剧本行不存在
            ScriptLineError: 删除失败
        """
        self._logger.info(f"Deleting script line {script_line_id}")

        # 检查剧本行是否存在
        try:
            self.get_by_id(script_line_id)
        except ScriptLineNotFoundError:
            raise

        sql = "DELETE FROM script_lines WHERE id = ?"

        try:
            affected = self._db.execute(sql, (script_line_id,))
            success = affected == 1
            if success:
                self._logger.info(f"Deleted script line {script_line_id}")
            else:
                self._logger.warning(f"Script line {script_line_id} not found")
            return success

        except DatabaseError as e:
            raise ScriptLineError(f"Failed to delete script line: {e}") from e

    # =========================================================================
    # 查询和列表操作
    # =========================================================================

    def get_by_project(
        self,
        project_id: int,
        limit: int = 100,
        offset: int = 0,
        order_by_sequence: bool = True,
    ) -> List[ScriptLine]:
        """
        获取指定项目的所有剧本行

        Args:
            project_id: 项目ID
            limit: 返回数量限制
            offset: 偏移量
            order_by_sequence: 是否按序号排序

        Returns:
            List[ScriptLine]: 剧本行列表
        """
        self._logger.debug(f"Getting script lines for project {project_id}")

        order_clause = "ORDER BY sequence ASC" if order_by_sequence else "ORDER BY created_at DESC"

        sql = f"""
        SELECT id, project_id, sequence, character_name, dialogue, emotion,
               knowledge_point, camera_suggestion, bgm_suggestion, estimated_duration,
               created_at
        FROM script_lines
        WHERE project_id = ?
        {order_clause}
        LIMIT ? OFFSET ?
        """

        try:
            result = self._db.query(sql, (project_id, limit, offset))
            return [ScriptLine.from_row(dict(row)) for row in result]

        except DatabaseError as e:
            raise ScriptLineError(f"Failed to get script lines for project: {e}") from e

    def get_by_character(
        self,
        project_id: int,
        character_name: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ScriptLine]:
        """
        获取指定项目的指定角色的所有剧本行

        Args:
            project_id: 项目ID
            character_name: 角色名
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            List[ScriptLine]: 剧本行列表
        """
        self._logger.debug(f"Getting script lines for character '{character_name}' in project {project_id}")

        sql = """
        SELECT id, project_id, sequence, character_name, dialogue, emotion,
               knowledge_point, camera_suggestion, bgm_suggestion, estimated_duration,
               created_at
        FROM script_lines
        WHERE project_id = ? AND character_name = ?
        ORDER BY sequence ASC
        LIMIT ? OFFSET ?
        """

        try:
            result = self._db.query(sql, (project_id, character_name, limit, offset))
            return [ScriptLine.from_row(dict(row)) for row in result]

        except DatabaseError as e:
            raise ScriptLineError(f"Failed to get script lines for character: {e}") from e

    def list_all(
        self,
        project_id: Optional[int] = None,
        character_name: Optional[str] = None,
        emotion: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ScriptLine]:
        """
        列出所有剧本行（带过滤条件）

        Args:
            project_id: 按项目ID过滤（可选）
            character_name: 按角色名过滤（可选）
            emotion: 按情绪过滤（可选）
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            List[ScriptLine]: 剧本行列表
        """
        self._logger.debug(f"Listing script lines: project={project_id}, character={character_name}, emotion={emotion}")

        # 构建WHERE条件
        conditions = []
        params: List[Any] = []

        if project_id is not None:
            conditions.append("project_id = ?")
            params.append(project_id)

        if character_name is not None:
            conditions.append("character_name = ?")
            params.append(character_name)

        if emotion is not None:
            conditions.append("emotion = ?")
            params.append(emotion)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        sql = f"""
        SELECT id, project_id, sequence, character_name, dialogue, emotion,
               knowledge_point, camera_suggestion, bgm_suggestion, estimated_duration,
               created_at
        FROM script_lines
        WHERE {where_clause}
        ORDER BY project_id, sequence
        LIMIT ? OFFSET ?
        """

        params.extend([limit, offset])

        try:
            result = self._db.query(sql, tuple(params))
            return [ScriptLine.from_row(dict(row)) for row in result]

        except DatabaseError as e:
            raise ScriptLineError(f"Failed to list script lines: {e}") from e

    def count(
        self,
        project_id: Optional[int] = None,
        character_name: Optional[str] = None,
        emotion: Optional[str] = None,
    ) -> int:
        """
        统计剧本行数量

        Args:
            project_id: 按项目ID过滤（可选）
            character_name: 按角色名过滤（可选）
            emotion: 按情绪过滤（可选）

        Returns:
            int: 剧本行数量
        """
        self._logger.debug(f"Counting script lines: project={project_id}, character={character_name}, emotion={emotion}")

        # 构建WHERE条件
        conditions = []
        params: List[Any] = []

        if project_id is not None:
            conditions.append("project_id = ?")
            params.append(project_id)

        if character_name is not None:
            conditions.append("character_name = ?")
            params.append(character_name)

        if emotion is not None:
            conditions.append("emotion = ?")
            params.append(emotion)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        sql = f"SELECT COUNT(*) as count FROM script_lines WHERE {where_clause}"

        try:
            result = self._db.query(sql, tuple(params))
            row = list(result)[0]
            return int(row["count"])

        except DatabaseError as e:
            raise ScriptLineError(f"Failed to count script lines: {e}") from e

    def search_by_dialogue(
        self,
        project_id: Optional[int] = None,
        query: str = "",
        limit: int = 50,
    ) -> List[ScriptLine]:
        """
        按台词内容搜索剧本行

        Args:
            project_id: 按项目ID过滤（可选）
            query: 搜索关键词
            limit: 返回数量限制

        Returns:
            List[ScriptLine]: 匹配的剧本行列表
        """
        self._logger.debug(f"Searching script lines by dialogue: project={project_id}, query='{query}'")

        # 构建WHERE条件
        conditions = ["dialogue LIKE ?"]
        params: List[Any] = [f"%{query}%"]

        if project_id is not None:
            conditions.append("project_id = ?")
            params.append(project_id)

        where_clause = " AND ".join(conditions)

        sql = f"""
        SELECT id, project_id, sequence, character_name, dialogue, emotion,
               knowledge_point, camera_suggestion, bgm_suggestion, estimated_duration,
               created_at
        FROM script_lines
        WHERE {where_clause}
        ORDER BY sequence
        LIMIT ?
        """

        params.append(limit)

        try:
            result = self._db.query(sql, tuple(params))
            return [ScriptLine.from_row(dict(row)) for row in result]

        except DatabaseError as e:
            raise ScriptLineError(f"Failed to search script lines: {e}") from e

    # =========================================================================
    # 批量操作
    # =========================================================================

    def batch_create(self, script_lines_data: List[ScriptLineCreate]) -> List[ScriptLine]:
        """
        批量创建剧本行

        Args:
            script_lines_data: 剧本行创建数据列表

        Returns:
            List[ScriptLine]: 创建的剧本行列表

        Raises:
            ScriptLineError: 批量创建失败
        """
        self._logger.info(f"Batch creating {len(script_lines_data)} script lines")

        # 按项目ID分组
        project_groups: Dict[int, List[ScriptLineCreate]] = {}
        for data in script_lines_data:
            if data.project_id not in project_groups:
                project_groups[data.project_id] = []
            project_groups[data.project_id].append(data)

        created_lines: List[ScriptLine] = []

        # 为每个项目生成连续序号
        for project_id, project_data in project_groups.items():
            # 获取当前项目的下一个可用序号
            next_seq = self.get_next_sequence(project_id)

            # 为批量创建分配序号
            for i, data in enumerate(project_data):
                # 如果数据中没有指定序号，使用连续序号
                if data.sequence == 0:
                    data = ScriptLineCreate(
                        project_id=data.project_id,
                        sequence=next_seq + i,
                        character_name=data.character_name,
                        dialogue=data.dialogue,
                        emotion=data.emotion,
                        knowledge_point=data.knowledge_point,
                        camera_suggestion=data.camera_suggestion,
                        bgm_suggestion=data.bgm_suggestion,
                        estimated_duration=data.estimated_duration,
                    )

                try:
                    script_line = self.create(data)
                    created_lines.append(script_line)
                except ScriptLineError as e:
                    self._logger.error(f"Failed to create script line in batch: {e}")
                    # 可以选择继续或终止批量创建
                    continue

        return created_lines

    def batch_delete(self, script_line_ids: List[int]) -> Dict[str, Any]:
        """
        批量删除剧本行

        Args:
            script_line_ids: 剧本行ID列表

        Returns:
            Dict[str, Any]: 删除结果统计
        """
        self._logger.info(f"Batch deleting {len(script_line_ids)} script lines")

        success_count = 0
        failure_count = 0
        failed_ids: List[int] = []

        for script_line_id in script_line_ids:
            try:
                if self.delete(script_line_id):
                    success_count += 1
                else:
                    failure_count += 1
                    failed_ids.append(script_line_id)
            except ScriptLineError as e:
                self._logger.error(f"Failed to delete script line {script_line_id}: {e}")
                failure_count += 1
                failed_ids.append(script_line_id)

        return {
            "total": len(script_line_ids),
            "success": success_count,
            "failure": failure_count,
            "failed_ids": failed_ids,
        }

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

        sql = """
        SELECT MAX(sequence) as max_sequence
        FROM script_lines
        WHERE project_id = ?
        """

        try:
            result = self._db.query(sql, (project_id,))
            row = list(result)[0]
            max_seq = row["max_sequence"]

            return int(max_seq) + 1 if max_seq is not None else 1

        except DatabaseError as e:
            raise ScriptLineError(f"Failed to get next sequence: {e}") from e

    def reorder_sequences(self, project_id: int) -> bool:
        """
        重新排序项目的剧本行序号（确保连续）

        Args:
            project_id: 项目ID

        Returns:
            bool: 是否成功重新排序

        Raises:
            ScriptLineError: 重新排序失败
        """
        self._logger.info(f"Reordering sequences for project {project_id}")

        try:
            # 获取项目的所有剧本行（按当前序号排序）
            script_lines = self.get_by_project(project_id, order_by_sequence=True)

            # 使用事务确保原子性
            with self._db.transaction() as conn:
                # 更新每个剧本行的序号
                for index, script_line in enumerate(script_lines, start=1):
                    if script_line.sequence != index:
                        sql = "UPDATE script_lines SET sequence = ? WHERE id = ?"
                        conn.execute(sql, (index, script_line.script_line_id))

            self._logger.info(f"Reordered {len(script_lines)} script lines for project {project_id}")
            return True

        except DatabaseError as e:
            raise ScriptLineError(f"Failed to reorder sequences: {e}") from e

    def validate_sequences(self, project_id: int) -> Dict[str, Any]:
        """
        验证项目内剧本行序号的有效性

        Args:
            project_id: 项目ID

        Returns:
            Dict[str, Any]: 验证结果
        """
        self._logger.debug(f"Validating sequences for project {project_id}")

        sql = """
        SELECT sequence, COUNT(*) as count
        FROM script_lines
        WHERE project_id = ?
        GROUP BY sequence
        HAVING COUNT(*) > 1
        ORDER BY sequence
        """

        try:
            result = self._db.query(sql, (project_id,))
            duplicate_rows = list(result)

            # 检查序号是否连续
            script_lines = self.get_by_project(project_id, order_by_sequence=True)
            sequences = [sl.sequence for sl in script_lines]

            # 检查是否存在重复序号
            duplicate_sequences = [row["sequence"] for row in duplicate_rows]

            # 检查序号是否连续
            missing_sequences = []
            if sequences:
                max_seq = max(sequences)
                expected_sequences = set(range(1, max_seq + 1))
                actual_sequences = set(sequences)
                missing_sequences = sorted(list(expected_sequences - actual_sequences))

            return {
                "is_valid": len(duplicate_sequences) == 0 and len(missing_sequences) == 0,
                "total_lines": len(script_lines),
                "duplicate_sequences": duplicate_sequences,
                "missing_sequences": missing_sequences,
                "max_sequence": max(sequences) if sequences else 0,
                "min_sequence": min(sequences) if sequences else 0,
            }

        except DatabaseError as e:
            raise ScriptLineError(f"Failed to validate sequences: {e}") from e

    # =========================================================================
    # 角色关联操作
    # =========================================================================

    def validate_character_exists(
        self,
        project_id: int,
        character_name: str,
    ) -> bool:
        """
        验证角色是否在项目中存在

        Args:
            project_id: 项目ID
            character_name: 角色名

        Returns:
            bool: 角色是否存在

        Raises:
            CharacterMismatchError: 角色不存在
        """
        self._logger.debug(f"Validating character '{character_name}' in project {project_id}")

        # 查询项目中是否有该角色的剧本行
        count = self.count(project_id=project_id, character_name=character_name)

        if count == 0:
            raise CharacterMismatchError(
                f"Character '{character_name}' does not exist in project {project_id}"
            )

        return True

    def get_unique_characters(self, project_id: int) -> List[str]:
        """
        获取项目中唯一的角色名列表

        Args:
            project_id: 项目ID

        Returns:
            List[str]: 角色名列表
        """
        self._logger.debug(f"Getting unique characters for project {project_id}")

        sql = """
        SELECT DISTINCT character_name
        FROM script_lines
        WHERE project_id = ?
        ORDER BY character_name
        """

        try:
            result = self._db.query(sql, (project_id,))
            return [row["character_name"] for row in result]

        except DatabaseError as e:
            raise ScriptLineError(f"Failed to get unique characters: {e}") from e

    def get_character_dialogue_count(self, project_id: int, character_name: str) -> int:
        """
        获取角色的台词数量

        Args:
            project_id: 项目ID
            character_name: 角色名

        Returns:
            int: 台词数量
        """
        self._logger.debug(f"Getting dialogue count for character '{character_name}' in project {project_id}")

        sql = """
        SELECT COUNT(*) as count
        FROM script_lines
        WHERE project_id = ? AND character_name = ?
        """

        try:
            result = self._db.query(sql, (project_id, character_name))
            row = list(result)[0]
            return int(row["count"])

        except DatabaseError as e:
            raise ScriptLineError(f"Failed to get character dialogue count: {e}") from e

    # =========================================================================
    # 统计和报表
    # =========================================================================

    def get_statistics(self, project_id: Optional[int] = None) -> Dict[str, Any]:
        """
        获取剧本行统计信息

        Args:
            project_id: 按项目ID过滤（可选）

        Returns:
            Dict[str, Any]: 统计信息
        """
        self._logger.debug(f"Getting script line statistics: project={project_id}")

        # 构建WHERE条件
        conditions = []
        params: List[Any] = []

        if project_id is not None:
            conditions.append("project_id = ?")
            params.append(project_id)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        sql = f"""
        SELECT
            COUNT(*) as total_count,
            COUNT(DISTINCT project_id) as project_count,
            COUNT(DISTINCT character_name) as character_count,
            COUNT(DISTINCT emotion) as emotion_count,
            AVG(LENGTH(dialogue)) as avg_dialogue_length,
            SUM(estimated_duration) as total_estimated_duration
        FROM script_lines
        WHERE {where_clause}
        """

        try:
            result = self._db.query(sql, tuple(params))
            row = dict(list(result)[0])

            return {
                "total_count": int(row["total_count"]),
                "project_count": int(row["project_count"]),
                "character_count": int(row["character_count"]),
                "emotion_count": int(row["emotion_count"]),
                "avg_dialogue_length": float(row["avg_dialogue_length"]) if row["avg_dialogue_length"] else 0.0,
                "total_estimated_duration": float(row["total_estimated_duration"]) if row["total_estimated_duration"] else 0.0,
            }

        except DatabaseError as e:
            raise ScriptLineError(f"Failed to get statistics: {e}") from e

    # =========================================================================
    # 辅助方法
    # =========================================================================

    def _get_last_insert_id(self) -> int:
        """获取最后插入的ID"""
        try:
            result = self._db.query("SELECT last_insert_rowid() as id", ())
            row = list(result)[0]
            return int(row["id"])
        except DatabaseError as e:
            raise ScriptLineError(f"Failed to get last insert ID: {e}") from e

    def _validate_sequence(self, project_id: int, sequence: int, exclude_id: Optional[int] = None) -> bool:
        """验证序号在项目中是否可用"""
        self._logger.debug(f"Validating sequence {sequence} for project {project_id}")

        if sequence <= 0:
            return False

        conditions = ["project_id = ?", "sequence = ?"]
        params: List[Any] = [project_id, sequence]

        if exclude_id is not None:
            conditions.append("id != ?")
            params.append(exclude_id)

        where_clause = " AND ".join(conditions)

        sql = f"SELECT COUNT(*) as count FROM script_lines WHERE {where_clause}"

        try:
            result = self._db.query(sql, tuple(params))
            row = list(result)[0]
            return int(row["count"]) == 0

        except DatabaseError as e:
            raise ScriptLineError(f"Failed to validate sequence: {e}") from e


# =============================================================================
# 导出列表
# =============================================================================

__all__ = [
    # 数据模型
    "ScriptLine",
    "ScriptLineCreate",
    "ScriptLineUpdate",
    "ScriptLineWithStats",
    # 异常
    "ScriptLineError",
    "ScriptLineNotFoundError",
    "ScriptLineAlreadyExistsError",
    "InvalidSequenceError",
    "CharacterMismatchError",
    # 主类
    "ScriptLineManager",
]