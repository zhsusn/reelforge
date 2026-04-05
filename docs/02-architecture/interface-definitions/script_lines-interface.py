"""
Script Lines 模块接口定义 (Type Spec)
版本：v1.0（草案）
项目：ReelForge
文件映射：`models/script_lines.py`

职责：剧本行数据的创建、读取、更新、删除操作，项目关联管理
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
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

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
        raise NotImplementedError

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
        raise NotImplementedError

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
        raise NotImplementedError

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
        raise NotImplementedError

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
        raise NotImplementedError

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
        raise NotImplementedError

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
        raise NotImplementedError

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
        raise NotImplementedError

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
        raise NotImplementedError

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
        raise NotImplementedError

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
        raise NotImplementedError

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
        raise NotImplementedError

    def batch_delete(self, script_line_ids: List[int]) -> Dict[str, Any]:
        """
        批量删除剧本行

        Args:
            script_line_ids: 剧本行ID列表

        Returns:
            Dict[str, Any]: 删除结果统计
        """
        raise NotImplementedError

    def import_from_excel_data(
        self,
        project_id: int,
        excel_rows: List[Dict[str, Any]],
        overwrite: bool = False,
    ) -> List[ScriptLine]:
        """
        从Excel数据导入剧本行

        Args:
            project_id: 项目ID
            excel_rows: Excel行数据列表
            overwrite: 是否覆盖现有剧本行

        Returns:
            List[ScriptLine]: 导入的剧本行列表

        Raises:
            ScriptLineError: 导入失败
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
        重新排序项目的剧本行序号（确保连续）

        Args:
            project_id: 项目ID

        Returns:
            bool: 是否成功重新排序

        Raises:
            ScriptLineError: 重新排序失败
        """
        raise NotImplementedError

    def validate_sequences(self, project_id: int) -> Dict[str, Any]:
        """
        验证项目内剧本行序号的有效性

        Args:
            project_id: 项目ID

        Returns:
            Dict[str, Any]: 验证结果
        """
        raise NotImplementedError

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
        raise NotImplementedError

    def get_unique_characters(self, project_id: int) -> List[str]:
        """
        获取项目中唯一的角色名列表

        Args:
            project_id: 项目ID

        Returns:
            List[str]: 角色名列表
        """
        raise NotImplementedError

    def get_character_dialogue_count(self, project_id: int, character_name: str) -> int:
        """
        获取角色的台词数量

        Args:
            project_id: 项目ID
            character_name: 角色名

        Returns:
            int: 台词数量
        """
        raise NotImplementedError

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
        raise NotImplementedError

    def get_with_stats(self, script_line_id: int) -> ScriptLineWithStats:
        """
        获取剧本行及其统计信息

        Args:
            script_line_id: 剧本行ID

        Returns:
            ScriptLineWithStats: 包含统计信息的剧本行对象
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

    def get_character_distribution(self, project_id: int) -> Dict[str, int]:
        """
        获取角色分布统计

        Args:
            project_id: 项目ID

        Returns:
            Dict[str, int]: 角色名->数量映射
        """
        raise NotImplementedError

    # =========================================================================
    # 分镜关联操作
    # =========================================================================

    def get_associated_shots(self, script_line_id: int) -> List[Dict[str, Any]]:
        """
        获取关联的分镜信息

        Args:
            script_line_id: 剧本行ID

        Returns:
            List[Dict[str, Any]]: 分镜信息列表
        """
        raise NotImplementedError

    def has_completed_shots(self, script_line_id: int) -> bool:
        """
        检查是否有已完成的分镜

        Args:
            script_line_id: 剧本行ID

        Returns:
            bool: 是否有已完成的分镜
        """
        raise NotImplementedError

    def get_shot_count(self, script_line_id: int) -> int:
        """
        获取关联的分镜数量

        Args:
            script_line_id: 剧本行ID

        Returns:
            int: 分镜数量
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

    def _generate_batch_sequence(
        self,
        project_id: int,
        count: int,
        start_sequence: Optional[int] = None,
    ) -> List[int]:
        """为批量创建生成连续序号"""
        raise NotImplementedError


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