"""
项目数据模型和CRUD操作
版本：v1.0
文件映射：docs/03-architecture/database-schema.sql (projects表)

职责：项目数据的创建、读取、更新、删除操作，状态管理
依赖：src/reelforge/models/database/ (Database, DatabaseError等)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

from reelforge.models.database import Database, DatabaseError, QueryResult


# =============================================================================
# 数据模型定义
# =============================================================================

class ProjectStatus(str, Enum):
    """项目状态枚举"""
    DRAFT = "draft"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Project:
    """项目数据模型

    对应数据库表：projects
    字段映射：
        id -> project_id
        name -> name
        description -> description
        status -> status (ProjectStatus)
        excel_path -> excel_path (Path)
        output_video_path -> output_video_path (Path)
        task_id -> task_id
        created_at -> created_at (datetime)
        updated_at -> updated_at (datetime)
        deleted_at -> deleted_at (datetime, 软删除)
    """

    project_id: int
    name: str
    description: Optional[str]
    status: ProjectStatus
    excel_path: Optional[Path]
    output_video_path: Optional[Path]
    task_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> Project:
        """从数据库行创建Project对象"""
        return cls(
            project_id=row["id"],
            name=row["name"],
            description=row["description"],
            status=ProjectStatus(row["status"]),
            excel_path=Path(row["excel_path"]) if row["excel_path"] else None,
            output_video_path=Path(row["output_video_path"]) if row["output_video_path"] else None,
            task_id=row["task_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            deleted_at=datetime.fromisoformat(row["deleted_at"]) if row["deleted_at"] else None,
        )


@dataclass
class ProjectCreate:
    """创建项目时的数据模型（输入）"""
    name: str
    description: Optional[str] = None
    excel_path: Optional[Path] = None


@dataclass
class ProjectUpdate:
    """更新项目时的数据模型（输入）"""
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ProjectStatus] = None
    excel_path: Optional[Path] = None
    output_video_path: Optional[Path] = None
    task_id: Optional[str] = None


# =============================================================================
# 异常定义
# =============================================================================

class ProjectError(DatabaseError):
    """项目操作基础异常"""
    pass


class ProjectNotFoundError(ProjectError):
    """项目未找到异常"""
    pass


class ProjectInvalidStatusError(ProjectError):
    """项目状态无效异常"""
    pass


class ProjectAlreadyDeletedError(ProjectError):
    """项目已软删除异常"""
    pass


# =============================================================================
# 主类接口实现
# =============================================================================

class ProjectManager:
    """项目管理器（CRUD操作）

    职责：
        1. 项目创建、读取、更新、删除（软删除）
        2. 项目状态管理
        3. 项目查询和过滤
        4. 项目关联操作（获取角色、剧本行等）
    """

    def __init__(self, database: Database) -> None:
        """
        初始化项目管理器

        Args:
            database: 数据库实例
        """
        self._db = database
        self._logger = logging.getLogger(__name__)

        # 确保数据库已连接
        try:
            self._db.connect()
        except Exception as e:
            raise ProjectError(f"Database connection failed: {e}") from e

    # =========================================================================
    # 基本CRUD操作
    # =========================================================================

    def create(self, project_data: ProjectCreate) -> Project:
        """
        创建新项目

        Args:
            project_data: 项目创建数据

        Returns:
            Project: 创建的项目对象

        Raises:
            ProjectError: 创建失败
        """
        self._logger.info(f"Creating project: {project_data.name}")

        # 验证数据
        if not project_data.name.strip():
            raise ProjectError("Project name cannot be empty")

        # 构建SQL
        sql = """
        INSERT INTO projects (
            name, description, excel_path, status,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """

        params = (
            project_data.name.strip(),
            project_data.description,
            str(project_data.excel_path) if project_data.excel_path else None,
            ProjectStatus.DRAFT.value,
        )

        try:
            # 执行插入
            affected = self._db.execute(sql, params)
            if affected != 1:
                raise ProjectError(f"Failed to create project: affected rows={affected}")

            # 获取新创建的项目
            new_id = self._get_last_insert_id()
            return self.get_by_id(new_id)

        except DatabaseError as e:
            raise ProjectError(f"Failed to create project: {e}") from e

    def get_by_id(self, project_id: int, include_deleted: bool = False) -> Project:
        """
        根据ID获取项目

        Args:
            project_id: 项目ID
            include_deleted: 是否包含已删除的项目

        Returns:
            Project: 项目对象

        Raises:
            ProjectNotFoundError: 项目不存在
            ProjectError: 查询失败
        """
        self._logger.debug(f"Getting project by ID: {project_id}")

        # 构建SQL
        where_clause = "id = ?"
        params: Tuple[Any, ...] = (project_id,)

        if not include_deleted:
            where_clause += " AND deleted_at IS NULL"

        sql = f"""
        SELECT id, name, description, status, excel_path, output_video_path, task_id,
               created_at, updated_at, deleted_at
        FROM projects
        WHERE {where_clause}
        """

        try:
            result = self._db.query(sql, params)
            rows = list(result)

            if not rows:
                raise ProjectNotFoundError(f"Project with ID {project_id} not found")

            if len(rows) > 1:
                self._logger.warning(f"Multiple projects found with ID {project_id}")

            return Project.from_row(dict(rows[0]))

        except DatabaseError as e:
            raise ProjectError(f"Failed to get project by ID: {e}") from e

    def update(self, project_id: int, update_data: ProjectUpdate) -> Project:
        """
        更新项目信息

        Args:
            project_id: 项目ID
            update_data: 更新数据

        Returns:
            Project: 更新后的项目对象

        Raises:
            ProjectNotFoundError: 项目不存在
            ProjectAlreadyDeletedError: 项目已软删除
            ProjectError: 更新失败
        """
        self._logger.info(f"Updating project {project_id}")

        # 检查项目是否存在且未删除
        project = self.get_by_id(project_id)
        if project.deleted_at:
            raise ProjectAlreadyDeletedError(f"Project {project_id} is already deleted")

        # 构建更新SQL
        updates = []
        params: List[Any] = []

        if update_data.name is not None:
            updates.append("name = ?")
            params.append(update_data.name.strip())

        if update_data.description is not None:
            updates.append("description = ?")
            params.append(update_data.description)

        if update_data.status is not None:
            updates.append("status = ?")
            params.append(update_data.status.value)

        if update_data.excel_path is not None:
            updates.append("excel_path = ?")
            params.append(str(update_data.excel_path))

        if update_data.output_video_path is not None:
            updates.append("output_video_path = ?")
            params.append(str(update_data.output_video_path))

        if update_data.task_id is not None:
            updates.append("task_id = ?")
            params.append(update_data.task_id)

        # 如果没有更新内容，直接返回原项目
        if not updates:
            return project

        # 添加updated_at自动更新
        updates.append("updated_at = CURRENT_TIMESTAMP")

        # 构建完整SQL
        sql = f"""
        UPDATE projects
        SET {', '.join(updates)}
        WHERE id = ? AND deleted_at IS NULL
        """

        params.append(project_id)

        try:
            affected = self._db.execute(sql, tuple(params))
            if affected != 1:
                raise ProjectError(f"Failed to update project: affected rows={affected}")

            return self.get_by_id(project_id)

        except DatabaseError as e:
            raise ProjectError(f"Failed to update project: {e}") from e

    def delete(self, project_id: int, hard_delete: bool = False) -> bool:
        """
        删除项目

        Args:
            project_id: 项目ID
            hard_delete: 是否物理删除（默认软删除）

        Returns:
            bool: 删除是否成功

        Raises:
            ProjectNotFoundError: 项目不存在
            ProjectError: 删除失败
        """
        self._logger.info(f"Deleting project {project_id} (hard={hard_delete})")

        # 检查项目是否存在
        try:
            project = self.get_by_id(project_id, include_deleted=True)

            # 如果项目已软删除且要求硬删除，或者直接要求硬删除
            if hard_delete:
                return self._hard_delete(project_id)
            elif project.deleted_at:
                raise ProjectAlreadyDeletedError(f"Project {project_id} is already deleted")
            else:
                return self._soft_delete(project_id)

        except ProjectNotFoundError:
            raise
        except DatabaseError as e:
            raise ProjectError(f"Failed to delete project: {e}") from e

    def _soft_delete(self, project_id: int) -> bool:
        """软删除项目"""
        sql = """
        UPDATE projects
        SET deleted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND deleted_at IS NULL
        """

        try:
            affected = self._db.execute(sql, (project_id,))
            success = affected == 1
            if success:
                self._logger.info(f"Soft deleted project {project_id}")
            else:
                self._logger.warning(f"Project {project_id} not found or already deleted")
            return success

        except DatabaseError as e:
            raise ProjectError(f"Failed to soft delete project: {e}") from e

    def _hard_delete(self, project_id: int) -> bool:
        """物理删除项目"""
        sql = "DELETE FROM projects WHERE id = ?"

        try:
            affected = self._db.execute(sql, (project_id,))
            success = affected == 1
            if success:
                self._logger.info(f"Hard deleted project {project_id}")
            else:
                self._logger.warning(f"Project {project_id} not found")
            return success

        except DatabaseError as e:
            raise ProjectError(f"Failed to hard delete project: {e}") from e

    # =========================================================================
    # 查询和列表操作
    # =========================================================================

    def list_all(
        self,
        include_deleted: bool = False,
        status: Optional[ProjectStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Project]:
        """
        列出所有项目

        Args:
            include_deleted: 是否包含已删除的项目
            status: 按状态过滤
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            List[Project]: 项目列表
        """
        self._logger.debug(f"Listing projects: deleted={include_deleted}, status={status}")

        # 构建WHERE条件
        conditions = []
        params: List[Any] = []

        if not include_deleted:
            conditions.append("deleted_at IS NULL")

        if status is not None:
            conditions.append("status = ?")
            params.append(status.value)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # 构建SQL
        sql = f"""
        SELECT id, name, description, status, excel_path, output_video_path, task_id,
               created_at, updated_at, deleted_at
        FROM projects
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """

        params.extend([limit, offset])

        try:
            result = self._db.query(sql, tuple(params))
            return [Project.from_row(dict(row)) for row in result]

        except DatabaseError as e:
            raise ProjectError(f"Failed to list projects: {e}") from e

    def count(
        self,
        include_deleted: bool = False,
        status: Optional[ProjectStatus] = None,
    ) -> int:
        """
        统计项目数量

        Args:
            include_deleted: 是否包含已删除的项目
            status: 按状态过滤

        Returns:
            int: 项目数量
        """
        self._logger.debug(f"Counting projects: deleted={include_deleted}, status={status}")

        # 构建WHERE条件
        conditions = []
        params: List[Any] = []

        if not include_deleted:
            conditions.append("deleted_at IS NULL")

        if status is not None:
            conditions.append("status = ?")
            params.append(status.value)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # 构建SQL
        sql = f"SELECT COUNT(*) as count FROM projects WHERE {where_clause}"

        try:
            result = self._db.query(sql, tuple(params))
            row = list(result)[0]
            return int(row["count"])

        except DatabaseError as e:
            raise ProjectError(f"Failed to count projects: {e}") from e

    def search_by_name(self, name_query: str, limit: int = 50) -> List[Project]:
        """
        按名称搜索项目

        Args:
            name_query: 名称查询（支持模糊匹配）
            limit: 返回数量限制

        Returns:
            List[Project]: 匹配的项目列表
        """
        self._logger.debug(f"Searching projects by name: '{name_query}'")

        sql = """
        SELECT id, name, description, status, excel_path, output_video_path, task_id,
               created_at, updated_at, deleted_at
        FROM projects
        WHERE name LIKE ? AND deleted_at IS NULL
        ORDER BY created_at DESC
        LIMIT ?
        """

        # 添加通配符进行模糊匹配
        search_term = f"%{name_query}%"

        try:
            result = self._db.query(sql, (search_term, limit))
            return [Project.from_row(dict(row)) for row in result]

        except DatabaseError as e:
            raise ProjectError(f"Failed to search projects: {e}") from e

    # =========================================================================
    # 状态管理操作
    # =========================================================================

    def update_status(self, project_id: int, new_status: ProjectStatus) -> Project:
        """
        更新项目状态

        Args:
            project_id: 项目ID
            new_status: 新状态

        Returns:
            Project: 更新后的项目对象

        Raises:
            ProjectNotFoundError: 项目不存在
            ProjectInvalidStatusError: 状态转换无效
            ProjectError: 更新失败
        """
        self._logger.info(f"Updating project {project_id} status to {new_status}")

        # 获取当前项目状态
        project = self.get_by_id(project_id)

        # 验证状态转换（可选，根据业务规则）
        if not self._is_valid_status_transition(project.status, new_status):
            raise ProjectInvalidStatusError(
                f"Invalid status transition: {project.status} -> {new_status}"
            )

        # 更新状态
        update_data = ProjectUpdate(status=new_status)
        return self.update(project_id, update_data)

    def get_by_status(self, status: ProjectStatus, limit: int = 100) -> List[Project]:
        """
        获取指定状态的所有项目

        Args:
            status: 项目状态
            limit: 返回数量限制

        Returns:
            List[Project]: 指定状态的项目列表
        """
        self._logger.debug(f"Getting projects with status: {status}")

        sql = """
        SELECT id, name, description, status, excel_path, output_video_path, task_id,
               created_at, updated_at, deleted_at
        FROM projects
        WHERE status = ? AND deleted_at IS NULL
        ORDER BY updated_at DESC
        LIMIT ?
        """

        try:
            result = self._db.query(sql, (status.value, limit))
            return [Project.from_row(dict(row)) for row in result]

        except DatabaseError as e:
            raise ProjectError(f"Failed to get projects by status: {e}") from e

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
            raise ProjectError(f"Failed to get last insert ID: {e}") from e

    def _is_valid_status_transition(
        self, current_status: ProjectStatus, new_status: ProjectStatus
    ) -> bool:
        """验证状态转换是否有效

        业务规则：
        1. draft -> processing, completed, failed
        2. processing -> completed, failed
        3. completed, failed -> 不可转换（需要重新创建）
        """
        transitions = {
            ProjectStatus.DRAFT: {
                ProjectStatus.PROCESSING,
                ProjectStatus.COMPLETED,
                ProjectStatus.FAILED,
            },
            ProjectStatus.PROCESSING: {
                ProjectStatus.COMPLETED,
                ProjectStatus.FAILED,
            },
            ProjectStatus.COMPLETED: set(),  # 不可转换
            ProjectStatus.FAILED: set(),  # 不可转换
        }

        return new_status in transitions.get(current_status, set())

    # =========================================================================
    # 统计和报表
    # =========================================================================

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取项目统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        self._logger.debug("Getting project statistics")

        sql = """
        SELECT
            COUNT(*) as total_count,
            COUNT(CASE WHEN deleted_at IS NULL THEN 1 END) as active_count,
            COUNT(CASE WHEN status = 'draft' AND deleted_at IS NULL THEN 1 END) as draft_count,
            COUNT(CASE WHEN status = 'processing' AND deleted_at IS NULL THEN 1 END) as processing_count,
            COUNT(CASE WHEN status = 'completed' AND deleted_at IS NULL THEN 1 END) as completed_count,
            COUNT(CASE WHEN status = 'failed' AND deleted_at IS NULL THEN 1 END) as failed_count,
            MIN(created_at) as earliest_project,
            MAX(created_at) as latest_project
        FROM projects
        """

        try:
            result = self._db.query(sql, ())
            row = dict(list(result)[0])

            return {
                "total_count": int(row["total_count"]),
                "active_count": int(row["active_count"]),
                "draft_count": int(row["draft_count"]),
                "processing_count": int(row["processing_count"]),
                "completed_count": int(row["completed_count"]),
                "failed_count": int(row["failed_count"]),
                "earliest_project": row["earliest_project"],
                "latest_project": row["latest_project"],
            }

        except DatabaseError as e:
            raise ProjectError(f"Failed to get project statistics: {e}") from e


# =============================================================================
# 导出列表
# =============================================================================

__all__ = [
    # 数据模型
    "Project",
    "ProjectCreate",
    "ProjectUpdate",
    "ProjectStatus",
    # 异常
    "ProjectError",
    "ProjectNotFoundError",
    "ProjectInvalidStatusError",
    "ProjectAlreadyDeletedError",
    # 主类
    "ProjectManager",
]