"""
角色数据模型和CRUD操作
版本：v1.0
文件映射：docs/03-architecture/database-schema.sql (characters表)

职责：角色数据的创建、读取、更新、删除操作，首帧锁定管理，相似度验证
依赖：src/reelforge/models/database/ (Database, DatabaseError等)
      src/reelforge/services/tongyi_client.py (角色一致性验证)
"""

from __future__ import annotations

import json
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

class VoiceProfile(str, Enum):
    """音色配置枚举（Edge TTS音色）"""
    XIAOXIAO = "zh-CN-XiaoxiaoNeural"  # 晓晓（年轻女声，默认）
    YUNXI = "zh-CN-YunxiNeural"  # 云希（年轻男声）
    YUNYANG = "zh-CN-YunyangNeural"  # 云扬（男声，播音风格）
    XIAOYI = "zh-CN-XiaoyiNeural"  # 晓伊（年轻女声，温柔）
    NARRATOR = "zh-CN-YunxiNeural"  # 旁白（默认使用云希）


@dataclass
class Character:
    """角色数据模型

    对应数据库表：characters
    字段映射：
        id -> character_id
        project_id -> project_id
        name -> name
        description -> description
        first_frame_path -> first_frame_path (Path)
        character_vector -> character_vector (bytes, 可选)
        similarity_score -> similarity_score (float, 0-100)
        voice_profile -> voice_profile (VoiceProfile)
        created_at -> created_at (datetime)
        updated_at -> updated_at (datetime)
        deleted_at -> deleted_at (datetime, 软删除)
    """

    character_id: int
    project_id: int
    name: str
    description: Optional[str]
    first_frame_path: Path
    character_vector: Optional[bytes]
    similarity_score: Optional[float]
    voice_profile: VoiceProfile
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> Character:
        """从数据库行创建Character对象"""
        voice_profile_value = row.get("voice_profile", "zh-CN-XiaoxiaoNeural")
        try:
            voice_profile = VoiceProfile(voice_profile_value)
        except ValueError:
            # 如果数据库中的值不是有效的枚举值，使用默认值
            voice_profile = VoiceProfile.XIAOXIAO

        return cls(
            character_id=row["id"],
            project_id=row["project_id"],
            name=row["name"],
            description=row["description"],
            first_frame_path=Path(row["first_frame_path"]),
            character_vector=row["character_vector"],
            similarity_score=float(row["similarity_score"]) if row["similarity_score"] else None,
            voice_profile=voice_profile,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            deleted_at=datetime.fromisoformat(row["deleted_at"]) if row["deleted_at"] else None,
        )


@dataclass
class CharacterCreate:
    """创建角色时的数据模型（输入）"""
    project_id: int
    name: str
    description: Optional[str] = None
    first_frame_path: Optional[Path] = None
    voice_profile: VoiceProfile = VoiceProfile.XIAOXIAO


@dataclass
class CharacterUpdate:
    """更新角色时的数据模型（输入）"""
    name: Optional[str] = None
    description: Optional[str] = None
    first_frame_path: Optional[Path] = None
    character_vector: Optional[bytes] = None
    similarity_score: Optional[float] = None
    voice_profile: Optional[VoiceProfile] = None


@dataclass
class CharacterWithStats(Character):
    """包含统计信息的角色数据模型"""
    dialogue_count: int = 0  # 关联的台词数量
    shot_count: int = 0  # 关联的分镜数量
    average_similarity: Optional[float] = None  # 平均相似度


# =============================================================================
# 异常定义
# =============================================================================

class CharacterError(DatabaseError):
    """角色操作基础异常"""
    pass


class CharacterNotFoundError(CharacterError):
    """角色未找到异常"""
    pass


class CharacterAlreadyDeletedError(CharacterError):
    """角色已软删除异常"""
    pass


class InvalidFirstFrameError(CharacterError):
    """无效的首帧图片异常"""
    pass


class ProjectMismatchError(CharacterError):
    """项目不匹配异常（角色不属于指定项目）"""
    pass


# =============================================================================
# 主类接口实现
# =============================================================================

class CharacterManager:
    """角色管理器（CRUD操作）

    职责：
        1. 角色创建、读取、更新、删除（软删除）
        2. 首帧锁定管理（图片路径、特征向量）
        3. 相似度分数管理
        4. 角色查询和过滤
        5. 项目关联操作
    """

    def __init__(self, database: Database) -> None:
        """
        初始化角色管理器

        Args:
            database: 数据库实例
        """
        self._db = database
        self._logger = logging.getLogger(__name__)

        # 确保数据库已连接
        try:
            self._db.connect()
        except Exception as e:
            raise CharacterError(f"Database connection failed: {e}") from e

    # =========================================================================
    # 基本CRUD操作
    # =========================================================================

    def create(self, character_data: CharacterCreate) -> Character:
        """
        创建新角色

        Args:
            character_data: 角色创建数据

        Returns:
            Character: 创建的角色对象

        Raises:
            CharacterError: 创建失败
            InvalidFirstFrameError: 首帧图片路径无效
        """
        self._logger.info(f"Creating character: {character_data.name} for project {character_data.project_id}")

        # 验证数据
        if not character_data.name.strip():
            raise CharacterError("Character name cannot be empty")

        if not character_data.first_frame_path:
            raise InvalidFirstFrameError("First frame path is required")

        if not character_data.first_frame_path.exists():
            raise InvalidFirstFrameError(f"First frame image not found: {character_data.first_frame_path}")

        # 验证项目存在（可选，依赖于外键约束）
        # self._validate_project_exists(character_data.project_id)

        # 构建SQL
        sql = """
        INSERT INTO characters (
            project_id, name, description, first_frame_path, voice_profile,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """

        params = (
            character_data.project_id,
            character_data.name.strip(),
            character_data.description,
            str(character_data.first_frame_path),
            character_data.voice_profile.value,
        )

        try:
            # 执行插入
            affected = self._db.execute(sql, params)
            if affected != 1:
                raise CharacterError(f"Failed to create character: affected rows={affected}")

            # 获取新创建的角色
            new_id = self._get_last_insert_id()
            return self.get_by_id(new_id)

        except DatabaseError as e:
            raise CharacterError(f"Failed to create character: {e}") from e

    def get_by_id(self, character_id: int, include_deleted: bool = False) -> Character:
        """
        根据ID获取角色

        Args:
            character_id: 角色ID
            include_deleted: 是否包含已删除的角色

        Returns:
            Character: 角色对象

        Raises:
            CharacterNotFoundError: 角色不存在
            CharacterError: 查询失败
        """
        self._logger.debug(f"Getting character by ID: {character_id}")

        # 构建SQL
        where_clause = "id = ?"
        params: Tuple[Any, ...] = (character_id,)

        if not include_deleted:
            where_clause += " AND deleted_at IS NULL"

        sql = f"""
        SELECT id, project_id, name, description, first_frame_path,
               character_vector, similarity_score, voice_profile,
               created_at, updated_at, deleted_at
        FROM characters
        WHERE {where_clause}
        """

        try:
            result = self._db.query(sql, params)
            rows = list(result)

            if not rows:
                raise CharacterNotFoundError(f"Character with ID {character_id} not found")

            return Character.from_row(dict(rows[0]))

        except DatabaseError as e:
            raise CharacterError(f"Failed to get character by ID: {e}") from e

    def get_by_project(
        self,
        project_id: int,
        include_deleted: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Character]:
        """
        获取指定项目的所有角色

        Args:
            project_id: 项目ID
            include_deleted: 是否包含已删除的角色
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            List[Character]: 角色列表
        """
        self._logger.debug(f"Getting characters for project {project_id}")

        # 构建WHERE条件
        conditions = ["project_id = ?"]
        params: List[Any] = [project_id]

        if not include_deleted:
            conditions.append("deleted_at IS NULL")

        where_clause = " AND ".join(conditions)

        # 构建SQL
        sql = f"""
        SELECT id, project_id, name, description, first_frame_path,
               character_vector, similarity_score, voice_profile,
               created_at, updated_at, deleted_at
        FROM characters
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """

        params.extend([limit, offset])

        try:
            result = self._db.query(sql, tuple(params))
            return [Character.from_row(dict(row)) for row in result]

        except DatabaseError as e:
            raise CharacterError(f"Failed to get characters by project: {e}") from e

    def update(self, character_id: int, update_data: CharacterUpdate) -> Character:
        """
        更新角色信息

        Args:
            character_id: 角色ID
            update_data: 更新数据

        Returns:
            Character: 更新后的角色对象

        Raises:
            CharacterNotFoundError: 角色不存在
            CharacterAlreadyDeletedError: 角色已软删除
            CharacterError: 更新失败
        """
        self._logger.info(f"Updating character {character_id}")

        # 检查角色是否存在且未删除
        character = self.get_by_id(character_id)
        if character.deleted_at:
            raise CharacterAlreadyDeletedError(f"Character {character_id} is already deleted")

        # 构建更新SQL
        updates = []
        params: List[Any] = []

        if update_data.name is not None:
            updates.append("name = ?")
            params.append(update_data.name.strip())

        if update_data.description is not None:
            updates.append("description = ?")
            params.append(update_data.description)

        if update_data.first_frame_path is not None:
            if not update_data.first_frame_path.exists():
                raise InvalidFirstFrameError(f"First frame image not found: {update_data.first_frame_path}")
            updates.append("first_frame_path = ?")
            params.append(str(update_data.first_frame_path))

        if update_data.character_vector is not None:
            updates.append("character_vector = ?")
            params.append(update_data.character_vector)

        if update_data.similarity_score is not None:
            updates.append("similarity_score = ?")
            params.append(update_data.similarity_score)

        if update_data.voice_profile is not None:
            updates.append("voice_profile = ?")
            params.append(update_data.voice_profile.value)

        # 如果没有更新内容，直接返回原角色
        if not updates:
            return character

        # 添加updated_at自动更新
        updates.append("updated_at = CURRENT_TIMESTAMP")

        # 构建完整SQL
        sql = f"""
        UPDATE characters
        SET {', '.join(updates)}
        WHERE id = ? AND deleted_at IS NULL
        """

        params.append(character_id)

        try:
            affected = self._db.execute(sql, tuple(params))
            if affected != 1:
                raise CharacterError(f"Failed to update character: affected rows={affected}")

            return self.get_by_id(character_id)

        except DatabaseError as e:
            raise CharacterError(f"Failed to update character: {e}") from e

    def delete(self, character_id: int, hard_delete: bool = False) -> bool:
        """
        删除角色

        Args:
            character_id: 角色ID
            hard_delete: 是否物理删除（默认软删除）

        Returns:
            bool: 删除是否成功

        Raises:
            CharacterNotFoundError: 角色不存在
            CharacterError: 删除失败
        """
        self._logger.info(f"Deleting character {character_id} (hard={hard_delete})")

        # 检查角色是否存在
        try:
            character = self.get_by_id(character_id, include_deleted=True)

            # 如果角色已软删除且要求硬删除，或者直接要求硬删除
            if hard_delete:
                return self._hard_delete(character_id)
            elif character.deleted_at:
                raise CharacterAlreadyDeletedError(f"Character {character_id} is already deleted")
            else:
                return self._soft_delete(character_id)

        except CharacterNotFoundError:
            raise
        except DatabaseError as e:
            raise CharacterError(f"Failed to delete character: {e}") from e

    def _soft_delete(self, character_id: int) -> bool:
        """软删除角色"""
        sql = """
        UPDATE characters
        SET deleted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND deleted_at IS NULL
        """

        try:
            affected = self._db.execute(sql, (character_id,))
            success = affected == 1
            if success:
                self._logger.info(f"Soft deleted character {character_id}")
            else:
                self._logger.warning(f"Character {character_id} not found or already deleted")
            return success

        except DatabaseError as e:
            raise CharacterError(f"Failed to soft delete character: {e}") from e

    def _hard_delete(self, character_id: int) -> bool:
        """物理删除角色"""
        sql = "DELETE FROM characters WHERE id = ?"

        try:
            affected = self._db.execute(sql, (character_id,))
            success = affected == 1
            if success:
                self._logger.info(f"Hard deleted character {character_id}")
            else:
                self._logger.warning(f"Character {character_id} not found")
            return success

        except DatabaseError as e:
            raise CharacterError(f"Failed to hard delete character: {e}") from e

    # =========================================================================
    # 首帧锁定和特征管理
    # =========================================================================

    def update_character_vector(
        self,
        character_id: int,
        character_vector: bytes,
        similarity_score: Optional[float] = None,
    ) -> Character:
        """
        更新角色特征向量和相似度分数

        Args:
            character_id: 角色ID
            character_vector: 特征向量（BLOB）
            similarity_score: 相似度分数（0-100，可选）

        Returns:
            Character: 更新后的角色对象
        """
        self._logger.info(f"Updating character vector for character {character_id}")

        update_data = CharacterUpdate(
            character_vector=character_vector,
            similarity_score=similarity_score,
        )

        return self.update(character_id, update_data)

    def get_by_first_frame_path(self, first_frame_path: Path) -> List[Character]:
        """
        根据首帧图片路径查找角色

        Args:
            first_frame_path: 首帧图片路径

        Returns:
            List[Character]: 匹配的角色列表
        """
        self._logger.debug(f"Getting characters by first frame path: {first_frame_path}")

        sql = """
        SELECT id, project_id, name, description, first_frame_path,
               character_vector, similarity_score, voice_profile,
               created_at, updated_at, deleted_at
        FROM characters
        WHERE first_frame_path = ? AND deleted_at IS NULL
        """

        try:
            result = self._db.query(sql, (str(first_frame_path),))
            return [Character.from_row(dict(row)) for row in result]

        except DatabaseError as e:
            raise CharacterError(f"Failed to get characters by first frame path: {e}") from e

    # =========================================================================
    # 查询和列表操作
    # =========================================================================

    def list_all(
        self,
        include_deleted: bool = False,
        project_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Character]:
        """
        列出所有角色

        Args:
            include_deleted: 是否包含已删除的角色
            project_id: 按项目ID过滤（可选）
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            List[Character]: 角色列表
        """
        self._logger.debug(f"Listing characters: deleted={include_deleted}, project={project_id}")

        # 构建WHERE条件
        conditions = []
        params: List[Any] = []

        if not include_deleted:
            conditions.append("deleted_at IS NULL")

        if project_id is not None:
            conditions.append("project_id = ?")
            params.append(project_id)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # 构建SQL
        sql = f"""
        SELECT id, project_id, name, description, first_frame_path,
               character_vector, similarity_score, voice_profile,
               created_at, updated_at, deleted_at
        FROM characters
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """

        params.extend([limit, offset])

        try:
            result = self._db.query(sql, tuple(params))
            return [Character.from_row(dict(row)) for row in result]

        except DatabaseError as e:
            raise CharacterError(f"Failed to list characters: {e}") from e

    def count(
        self,
        include_deleted: bool = False,
        project_id: Optional[int] = None,
    ) -> int:
        """
        统计角色数量

        Args:
            include_deleted: 是否包含已删除的角色
            project_id: 按项目ID过滤（可选）

        Returns:
            int: 角色数量
        """
        self._logger.debug(f"Counting characters: deleted={include_deleted}, project={project_id}")

        # 构建WHERE条件
        conditions = []
        params: List[Any] = []

        if not include_deleted:
            conditions.append("deleted_at IS NULL")

        if project_id is not None:
            conditions.append("project_id = ?")
            params.append(project_id)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # 构建SQL
        sql = f"SELECT COUNT(*) as count FROM characters WHERE {where_clause}"

        try:
            result = self._db.query(sql, tuple(params))
            row = list(result)[0]
            return int(row["count"])

        except DatabaseError as e:
            raise CharacterError(f"Failed to count characters: {e}") from e

    def search_by_name(
        self,
        name_query: str,
        project_id: Optional[int] = None,
        limit: int = 50,
    ) -> List[Character]:
        """
        按名称搜索角色

        Args:
            name_query: 名称查询（支持模糊匹配）
            project_id: 按项目ID过滤（可选）
            limit: 返回数量限制

        Returns:
            List[Character]: 匹配的角色列表
        """
        self._logger.debug(f"Searching characters by name: '{name_query}', project={project_id}")

        # 构建WHERE条件
        conditions = ["name LIKE ?", "deleted_at IS NULL"]
        params: List[Any] = [f"%{name_query}%"]

        if project_id is not None:
            conditions.append("project_id = ?")
            params.append(project_id)

        where_clause = " AND ".join(conditions)

        # 构建SQL
        sql = f"""
        SELECT id, project_id, name, description, first_frame_path,
               character_vector, similarity_score, voice_profile,
               created_at, updated_at, deleted_at
        FROM characters
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT ?
        """

        params.append(limit)

        try:
            result = self._db.query(sql, tuple(params))
            return [Character.from_row(dict(row)) for row in result]

        except DatabaseError as e:
            raise CharacterError(f"Failed to search characters: {e}") from e

    # =========================================================================
    # 统计和报表
    # =========================================================================

    def get_with_stats(self, character_id: int) -> CharacterWithStats:
        """
        获取角色及其统计信息

        Args:
            character_id: 角色ID

        Returns:
            CharacterWithStats: 包含统计信息的角色对象
        """
        self._logger.debug(f"Getting character with stats: {character_id}")

        # 先获取基础角色信息
        character = self.get_by_id(character_id)

        # 获取统计信息
        stats = self._get_character_stats(character_id)

        # 创建包含统计信息的角色对象
        return CharacterWithStats(
            character_id=character.character_id,
            project_id=character.project_id,
            name=character.name,
            description=character.description,
            first_frame_path=character.first_frame_path,
            character_vector=character.character_vector,
            similarity_score=character.similarity_score,
            voice_profile=character.voice_profile,
            created_at=character.created_at,
            updated_at=character.updated_at,
            deleted_at=character.deleted_at,
            dialogue_count=stats["dialogue_count"],
            shot_count=stats["shot_count"],
            average_similarity=stats["average_similarity"],
        )

    def get_project_characters_with_stats(self, project_id: int) -> List[CharacterWithStats]:
        """
        获取项目的所有角色及其统计信息

        Args:
            project_id: 项目ID

        Returns:
            List[CharacterWithStats]: 包含统计信息的角色列表
        """
        self._logger.debug(f"Getting project characters with stats: {project_id}")

        # 获取项目所有角色
        characters = self.get_by_project(project_id)

        # 为每个角色获取统计信息
        result = []
        for character in characters:
            stats = self._get_character_stats(character.character_id)
            result.append(
                CharacterWithStats(
                    character_id=character.character_id,
                    project_id=character.project_id,
                    name=character.name,
                    description=character.description,
                    first_frame_path=character.first_frame_path,
                    character_vector=character.character_vector,
                    similarity_score=character.similarity_score,
                    voice_profile=character.voice_profile,
                    created_at=character.created_at,
                    updated_at=character.updated_at,
                    deleted_at=character.deleted_at,
                    dialogue_count=stats["dialogue_count"],
                    shot_count=stats["shot_count"],
                    average_similarity=stats["average_similarity"],
                )
            )

        return result

    def _get_character_stats(self, character_id: int) -> Dict[str, Any]:
        """获取角色统计信息"""
        # 获取关联的台词数量
        dialogue_sql = """
        SELECT COUNT(*) as count
        FROM script_lines sl
        JOIN characters c ON sl.project_id = c.project_id AND sl.character_name = c.name
        WHERE c.id = ? AND c.deleted_at IS NULL
        """

        # 获取关联的分镜数量
        shot_sql = """
        SELECT COUNT(*) as count
        FROM shots s
        JOIN characters c ON s.project_id = c.project_id
        WHERE c.id = ? AND c.deleted_at IS NULL
        """

        # 获取平均相似度
        avg_similarity_sql = """
        SELECT AVG(similarity_score) as avg_similarity
        FROM shots s
        JOIN characters c ON s.project_id = c.project_id
        WHERE c.id = ? AND c.deleted_at IS NULL AND s.similarity_score IS NOT NULL
        """

        try:
            # 执行查询
            dialogue_result = list(self._db.query(dialogue_sql, (character_id,)))
            shot_result = list(self._db.query(shot_sql, (character_id,)))
            avg_similarity_result = list(self._db.query(avg_similarity_sql, (character_id,)))

            dialogue_count = dialogue_result[0]["count"] if dialogue_result else 0
            shot_count = shot_result[0]["count"] if shot_result else 0
            avg_similarity = float(avg_similarity_result[0]["avg_similarity"]) if avg_similarity_result and avg_similarity_result[0]["avg_similarity"] else None

            return {
                "dialogue_count": dialogue_count,
                "shot_count": shot_count,
                "average_similarity": avg_similarity,
            }

        except DatabaseError as e:
            self._logger.warning(f"Failed to get character stats: {e}")
            return {
                "dialogue_count": 0,
                "shot_count": 0,
                "average_similarity": None,
            }

    def get_voice_profile_usage(self, project_id: Optional[int] = None) -> Dict[str, int]:
        """
        获取音色配置使用统计

        Args:
            project_id: 按项目ID过滤（可选）

        Returns:
            Dict[str, int]: 音色配置->使用次数映射
        """
        self._logger.debug(f"Getting voice profile usage: project={project_id}")

        # 构建WHERE条件
        conditions = ["deleted_at IS NULL"]
        params: List[Any] = []

        if project_id is not None:
            conditions.append("project_id = ?")
            params.append(project_id)

        where_clause = " AND ".join(conditions)

        # 构建SQL
        sql = f"""
        SELECT voice_profile, COUNT(*) as count
        FROM characters
        WHERE {where_clause}
        GROUP BY voice_profile
        ORDER BY count DESC
        """

        try:
            result = self._db.query(sql, tuple(params))
            usage = {}
            for row in result:
                usage[row["voice_profile"]] = row["count"]
            return usage

        except DatabaseError as e:
            raise CharacterError(f"Failed to get voice profile usage: {e}") from e

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
            raise CharacterError(f"Failed to get last insert ID: {e}") from e

    def _validate_project_exists(self, project_id: int) -> None:
        """验证项目是否存在（可选验证）"""
        # 这里可以调用ProjectManager验证项目存在
        # 当前仅依赖数据库外键约束
        pass

    def validate_character_belongs_to_project(self, character_id: int, project_id: int) -> bool:
        """
        验证角色是否属于指定项目

        Args:
            character_id: 角色ID
            project_id: 项目ID

        Returns:
            bool: 是否属于该项目

        Raises:
            CharacterNotFoundError: 角色不存在
        """
        try:
            character = self.get_by_id(character_id)
            return character.project_id == project_id
        except CharacterNotFoundError:
            raise

    # =========================================================================
    # 批量操作
    # =========================================================================

    def batch_create(self, characters_data: List[CharacterCreate]) -> List[Character]:
        """
        批量创建角色

        Args:
            characters_data: 角色创建数据列表

        Returns:
            List[Character]: 创建的角色列表

        Raises:
            CharacterError: 批量创建失败
        """
        self._logger.info(f"Batch creating {len(characters_data)} characters")

        created_characters = []
        for char_data in characters_data:
            try:
                character = self.create(char_data)
                created_characters.append(character)
            except Exception as e:
                self._logger.error(f"Failed to create character {char_data.name}: {e}")
                # 继续创建其他角色
                continue

        return created_characters

    def batch_delete(
        self,
        character_ids: List[int],
        hard_delete: bool = False,
    ) -> Dict[str, Any]:
        """
        批量删除角色

        Args:
            character_ids: 角色ID列表
            hard_delete: 是否物理删除（默认软删除）

        Returns:
            Dict[str, Any]: 删除结果统计
        """
        self._logger.info(f"Batch deleting {len(character_ids)} characters (hard={hard_delete})")

        results = {
            "total": len(character_ids),
            "success": 0,
            "failed": 0,
            "already_deleted": 0,
            "not_found": 0,
            "errors": [],
        }

        for char_id in character_ids:
            try:
                success = self.delete(char_id, hard_delete)
                if success:
                    results["success"] += 1
                else:
                    results["not_found"] += 1
            except CharacterAlreadyDeletedError:
                results["already_deleted"] += 1
            except CharacterNotFoundError:
                results["not_found"] += 1
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(f"Character {char_id}: {str(e)}")

        return results


# =============================================================================
# 导出列表
# =============================================================================

__all__ = [
    # 数据模型
    "Character",
    "CharacterCreate",
    "CharacterUpdate",
    "CharacterWithStats",
    "VoiceProfile",
    # 异常
    "CharacterError",
    "CharacterNotFoundError",
    "CharacterAlreadyDeletedError",
    "InvalidFirstFrameError",
    "ProjectMismatchError",
    # 主类
    "CharacterManager",
]