"""
Tasks 模块接口定义 (Type Spec)
版本：v1.0（草案）
项目：ReelForge
文件映射：`models/tasks.py`

职责：任务数据的创建、读取、更新、删除操作，状态跟踪，进度管理
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
from typing import Any, Dict, List, Optional, Tuple, Union

from reelforge.models.database import Database, DatabaseError, QueryResult


# =============================================================================
# 数据模型定义
# =============================================================================

class TaskStatus(str, Enum):
    """任务状态枚举"""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    """任务类型枚举"""
    EXCEL_PARSE = "excel_parse"
    CHARACTER_GEN = "character_gen"
    STORYBOARD_GEN = "storyboard_gen"
    TTS_GEN = "tts_gen"
    VIDEO_RENDER = "video_render"


@dataclass
class Task:
    """任务数据模型

    对应数据库表：tasks
    字段映射：
        id -> task_id
        task_id -> external_task_id (外部任务ID，由queue_manager生成)
        project_id -> project_id
        status -> status (TaskStatus)
        task_type -> task_type (TaskType)
        priority -> priority
        progress_current -> progress_current
        progress_total -> progress_total
        progress_message -> progress_message
        error_code -> error_code (可选)
        error_message -> error_message (可选)
        error_stack -> error_stack (可选)
        created_at -> created_at (datetime)
        updated_at -> updated_at (datetime)
        started_at -> started_at (datetime, 可选)
        completed_at -> completed_at (datetime, 可选)
    """

    task_id: int
    external_task_id: str
    project_id: int
    status: TaskStatus
    task_type: TaskType
    priority: int
    progress_current: int
    progress_total: int
    progress_message: Optional[str]
    error_code: Optional[str]
    error_message: Optional[str]
    error_stack: Optional[str]
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> Task:
        """从数据库行创建Task对象"""
        return cls(
            task_id=row["id"],
            external_task_id=row["task_id"],
            project_id=row["project_id"],
            status=TaskStatus(row["status"]),
            task_type=TaskType(row["task_type"]),
            priority=row["priority"],
            progress_current=row["progress_current"],
            progress_total=row["progress_total"],
            progress_message=row["progress_message"],
            error_code=row["error_code"],
            error_message=row["error_message"],
            error_stack=row["error_stack"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
        )


@dataclass
class TaskCreate:
    """创建任务时的数据模型（输入）"""
    external_task_id: str
    project_id: int
    task_type: TaskType
    priority: int = 0
    progress_total: int = 1


@dataclass
class TaskUpdate:
    """更新任务时的数据模型（输入）"""
    status: Optional[TaskStatus] = None
    priority: Optional[int] = None
    progress_current: Optional[int] = None
    progress_total: Optional[int] = None
    progress_message: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    error_stack: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class TaskWithStats(Task):
    """包含统计信息的任务数据模型"""
    project_name: Optional[str] = None  # 项目名称
    processing_duration: Optional[float] = None  # 处理时长（秒）
    waiting_duration: Optional[float] = None  # 等待时长（秒）


# =============================================================================
# 异常定义
# =============================================================================

class TaskError(DatabaseError):
    """任务操作基础异常"""
    pass


class TaskNotFoundError(TaskError):
    """任务未找到异常"""
    pass


class TaskAlreadyExistsError(TaskError):
    """任务已存在异常（外部任务ID重复）"""
    pass


class InvalidTaskStatusError(TaskError):
    """任务状态无效异常"""
    pass


class InvalidPriorityError(TaskError):
    """优先级无效异常（非负整数）"""
    pass


class ProgressError(TaskError):
    """进度更新异常（进度大于总数或负数）"""
    pass


# =============================================================================
# 主类接口实现
# =============================================================================

class TaskManager:
    """任务管理器（CRUD操作）

    职责：
        1. 任务创建、读取、更新、删除
        2. 任务状态管理
        3. 进度信息更新
        4. 错误信息记录
        5. 时间戳管理
        6. 任务查询和过滤
    """

    def __init__(self, database: Database) -> None:
        """
        初始化任务管理器

        Args:
            database: 数据库实例
        """
        raise NotImplementedError

    # =========================================================================
    # 基本CRUD操作
    # =========================================================================

    def create(self, task_data: TaskCreate) -> Task:
        """
        创建新任务

        Args:
            task_data: 任务创建数据

        Returns:
            Task: 创建的任务对象

        Raises:
            TaskError: 创建失败
            TaskAlreadyExistsError: 外部任务ID已存在
            InvalidPriorityError: 优先级无效
        """
        raise NotImplementedError

    def get_by_id(self, task_id: int) -> Task:
        """
        根据ID获取任务

        Args:
            task_id: 任务ID

        Returns:
            Task: 任务对象

        Raises:
            TaskNotFoundError: 任务不存在
            TaskError: 查询失败
        """
        raise NotImplementedError

    def get_by_external_id(self, external_task_id: str) -> Task:
        """
        根据外部任务ID获取任务

        Args:
            external_task_id: 外部任务ID（由queue_manager生成）

        Returns:
            Task: 任务对象

        Raises:
            TaskNotFoundError: 任务不存在
            TaskError: 查询失败
        """
        raise NotImplementedError

    def update(self, task_id: int, update_data: TaskUpdate) -> Task:
        """
        更新任务信息

        Args:
            task_id: 任务ID
            update_data: 更新数据

        Returns:
            Task: 更新后的任务对象

        Raises:
            TaskNotFoundError: 任务不存在
            InvalidTaskStatusError: 状态转换无效
            ProgressError: 进度更新无效
            TaskError: 更新失败
        """
        raise NotImplementedError

    def delete(self, task_id: int) -> bool:
        """
        删除任务

        Args:
            task_id: 任务ID

        Returns:
            bool: 删除是否成功

        Raises:
            TaskNotFoundError: 任务不存在
            TaskError: 删除失败
        """
        raise NotImplementedError

    # =========================================================================
    # 状态管理操作
    # =========================================================================

    def update_status(self, task_id: int, new_status: TaskStatus) -> Task:
        """
        更新任务状态

        Args:
            task_id: 任务ID
            new_status: 新状态

        Returns:
            Task: 更新后的任务对象

        Raises:
            TaskNotFoundError: 任务不存在
            InvalidTaskStatusError: 状态转换无效
            TaskError: 更新失败
        """
        raise NotImplementedError

    def mark_as_processing(self, task_id: int) -> Task:
        """
        标记任务为处理中（设置started_at）

        Args:
            task_id: 任务ID

        Returns:
            Task: 更新后的任务对象
        """
        raise NotImplementedError

    def mark_as_completed(self, task_id: int) -> Task:
        """
        标记任务为已完成（设置completed_at）

        Args:
            task_id: 任务ID

        Returns:
            Task: 更新后的任务对象
        """
        raise NotImplementedError

    def mark_as_failed(
        self,
        task_id: int,
        error_code: str,
        error_message: str,
        error_stack: Optional[str] = None,
    ) -> Task:
        """
        标记任务为失败（设置错误信息）

        Args:
            task_id: 任务ID
            error_code: 错误代码
            error_message: 错误消息
            error_stack: 错误堆栈（可选）

        Returns:
            Task: 更新后的任务对象
        """
        raise NotImplementedError

    def pause_task(self, task_id: int) -> Task:
        """
        暂停任务

        Args:
            task_id: 任务ID

        Returns:
            Task: 更新后的任务对象
        """
        raise NotImplementedError

    def cancel_task(self, task_id: int) -> Task:
        """
        取消任务

        Args:
            task_id: 任务ID

        Returns:
            Task: 更新后的任务对象
        """
        raise NotImplementedError

    def resume_task(self, task_id: int) -> Task:
        """
        恢复任务（从paused状态）

        Args:
            task_id: 任务ID

        Returns:
            Task: 更新后的任务对象
        """
        raise NotImplementedError

    # =========================================================================
    # 进度管理操作
    # =========================================================================

    def update_progress(
        self,
        task_id: int,
        progress_current: int,
        progress_total: Optional[int] = None,
        progress_message: Optional[str] = None,
    ) -> Task:
        """
        更新任务进度

        Args:
            task_id: 任务ID
            progress_current: 当前进度
            progress_total: 总进度（可选，如果更新）
            progress_message: 进度消息（可选）

        Returns:
            Task: 更新后的任务对象

        Raises:
            TaskNotFoundError: 任务不存在
            ProgressError: 进度无效
            TaskError: 更新失败
        """
        raise NotImplementedError

    def increment_progress(
        self,
        task_id: int,
        increment: int = 1,
        progress_message: Optional[str] = None,
    ) -> Task:
        """
        增加任务进度

        Args:
            task_id: 任务ID
            increment: 增加量（默认1）
            progress_message: 进度消息（可选）

        Returns:
            Task: 更新后的任务对象
        """
        raise NotImplementedError

    def get_progress_percentage(self, task_id: int) -> float:
        """
        获取任务进度百分比

        Args:
            task_id: 任务ID

        Returns:
            float: 进度百分比（0-100）
        """
        raise NotImplementedError

    def reset_progress(self, task_id: int) -> Task:
        """
        重置任务进度（恢复为初始状态）

        Args:
            task_id: 任务ID

        Returns:
            Task: 更新后的任务对象
        """
        raise NotImplementedError

    # =========================================================================
    # 查询和列表操作
    # =========================================================================

    def get_by_project(
        self,
        project_id: int,
        status: Optional[TaskStatus] = None,
        task_type: Optional[TaskType] = None,
        limit: int = 100,
        offset: int = 0,
        order_by_created: bool = True,
    ) -> List[Task]:
        """
        获取指定项目的所有任务

        Args:
            project_id: 项目ID
            status: 按状态过滤（可选）
            task_type: 按任务类型过滤（可选）
            limit: 返回数量限制
            offset: 偏移量
            order_by_created: 是否按创建时间排序

        Returns:
            List[Task]: 任务列表
        """
        raise NotImplementedError

    def get_by_status(
        self,
        status: TaskStatus,
        project_id: Optional[int] = None,
        task_type: Optional[TaskType] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Task]:
        """
        获取指定状态的所有任务

        Args:
            status: 任务状态
            project_id: 按项目ID过滤（可选）
            task_type: 按任务类型过滤（可选）
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            List[Task]: 任务列表
        """
        raise NotImplementedError

    def get_by_type(
        self,
        task_type: TaskType,
        project_id: Optional[int] = None,
        status: Optional[TaskStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Task]:
        """
        获取指定类型的所有任务

        Args:
            task_type: 任务类型
            project_id: 按项目ID过滤（可选）
            status: 按状态过滤（可选）
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            List[Task]: 任务列表
        """
        raise NotImplementedError

    def list_all(
        self,
        project_id: Optional[int] = None,
        status: Optional[TaskStatus] = None,
        task_type: Optional[TaskType] = None,
        limit: int = 100,
        offset: int = 0,
        order_by_priority: bool = False,
    ) -> List[Task]:
        """
        列出所有任务（带过滤条件）

        Args:
            project_id: 按项目ID过滤（可选）
            status: 按状态过滤（可选）
            task_type: 按任务类型过滤（可选）
            limit: 返回数量限制
            offset: 偏移量
            order_by_priority: 是否按优先级排序

        Returns:
            List[Task]: 任务列表
        """
        raise NotImplementedError

    def get_pending_tasks(
        self,
        project_id: Optional[int] = None,
        task_type: Optional[TaskType] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Task]:
        """
        获取待处理的任务（queued或paused状态）

        Args:
            project_id: 按项目ID过滤（可选）
            task_type: 按任务类型过滤（可选）
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            List[Task]: 任务列表
        """
        raise NotImplementedError

    def get_active_tasks(
        self,
        project_id: Optional[int] = None,
        task_type: Optional[TaskType] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Task]:
        """
        获取活动中的任务（processing状态）

        Args:
            project_id: 按项目ID过滤（可选）
            task_type: 按任务类型过滤（可选）
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            List[Task]: 任务列表
        """
        raise NotImplementedError

    def count(
        self,
        project_id: Optional[int] = None,
        status: Optional[TaskStatus] = None,
        task_type: Optional[TaskType] = None,
    ) -> int:
        """
        统计任务数量

        Args:
            project_id: 按项目ID过滤（可选）
            status: 按状态过滤（可选）
            task_type: 按任务类型过滤（可选）

        Returns:
            int: 任务数量
        """
        raise NotImplementedError

    def search_by_progress_message(
        self,
        project_id: Optional[int] = None,
        query: str = "",
        limit: int = 50,
    ) -> List[Task]:
        """
        按进度消息搜索任务

        Args:
            project_id: 按项目ID过滤（可选）
            query: 搜索关键词
            limit: 返回数量限制

        Returns:
            List[Task]: 匹配的任务列表
        """
        raise NotImplementedError

    # =========================================================================
    # 批量操作
    # =========================================================================

    def batch_create(self, tasks_data: List[TaskCreate]) -> List[Task]:
        """
        批量创建任务

        Args:
            tasks_data: 任务创建数据列表

        Returns:
            List[Task]: 创建的任务列表

        Raises:
            TaskError: 批量创建失败
        """
        raise NotImplementedError

    def batch_update_status(
        self,
        task_ids: List[int],
        new_status: TaskStatus,
    ) -> List[Task]:
        """
        批量更新任务状态

        Args:
            task_ids: 任务ID列表
            new_status: 新状态

        Returns:
            List[Task]: 更新后的任务列表

        Raises:
            TaskError: 批量更新失败
        """
        raise NotImplementedError

    def batch_delete(self, task_ids: List[int]) -> Dict[str, Any]:
        """
        批量删除任务

        Args:
            task_ids: 任务ID列表

        Returns:
            Dict[str, Any]: 删除结果统计
        """
        raise NotImplementedError

    # =========================================================================
    # 统计和报表
    # =========================================================================

    def get_statistics(self, project_id: Optional[int] = None) -> Dict[str, Any]:
        """
        获取任务统计信息

        Args:
            project_id: 按项目ID过滤（可选）

        Returns:
            Dict[str, Any]: 统计信息
        """
        raise NotImplementedError

    def get_with_stats(self, task_id: int) -> TaskWithStats:
        """
        获取任务及其统计信息

        Args:
            task_id: 任务ID

        Returns:
            TaskWithStats: 包含统计信息的任务对象
        """
        raise NotImplementedError

    def get_status_distribution(self, project_id: Optional[int] = None) -> Dict[str, int]:
        """
        获取状态分布统计

        Args:
            project_id: 按项目ID过滤（可选）

        Returns:
            Dict[str, int]: 状态->数量映射
        """
        raise NotImplementedError

    def get_type_distribution(self, project_id: Optional[int] = None) -> Dict[str, int]:
        """
        获取类型分布统计

        Args:
            project_id: 按项目ID过滤（可选）

        Returns:
            Dict[str, int]: 类型->数量映射
        """
        raise NotImplementedError

    def get_average_processing_time(
        self,
        project_id: Optional[int] = None,
        task_type: Optional[TaskType] = None,
    ) -> Optional[float]:
        """
        获取平均处理时间

        Args:
            project_id: 按项目ID过滤（可选）
            task_type: 按任务类型过滤（可选）

        Returns:
            Optional[float]: 平均处理时间（秒），无数据返回None
        """
        raise NotImplementedError

    def get_failure_rate(
        self,
        project_id: Optional[int] = None,
        task_type: Optional[TaskType] = None,
    ) -> float:
        """
        获取任务失败率

        Args:
            project_id: 按项目ID过滤（可选）
            task_type: 按任务类型过滤（可选）

        Returns:
            float: 失败率（0-100）
        """
        raise NotImplementedError

    # =========================================================================
    # 时间管理和性能分析
    # =========================================================================

    def get_waiting_time(self, task_id: int) -> Optional[float]:
        """
        获取任务等待时间

        Args:
            task_id: 任务ID

        Returns:
            Optional[float]: 等待时间（秒），未开始返回None
        """
        raise NotImplementedError

    def get_processing_time(self, task_id: int) -> Optional[float]:
        """
        获取任务处理时间

        Args:
            task_id: 任务ID

        Returns:
            Optional[float]: 处理时间（秒），未完成返回None
        """
        raise NotImplementedError

    def get_total_time(self, task_id: int) -> Optional[float]:
        """
        获取任务总时间（创建到完成）

        Args:
            task_id: 任务ID

        Returns:
            Optional[float]: 总时间（秒），未完成返回None
        """
        raise NotImplementedError

    def get_oldest_pending_task(self, project_id: Optional[int] = None) -> Optional[Task]:
        """
        获取最老的待处理任务

        Args:
            project_id: 按项目ID过滤（可选）

        Returns:
            Optional[Task]: 最老的待处理任务，无返回None
        """
        raise NotImplementedError

    # =========================================================================
    # 辅助方法
    # =========================================================================

    def _get_last_insert_id(self) -> int:
        """获取最后插入的ID"""
        raise NotImplementedError

    def _is_valid_status_transition(
        self,
        current_status: TaskStatus,
        new_status: TaskStatus,
    ) -> bool:
        """验证状态转换是否有效"""
        raise NotImplementedError

    def _validate_progress(
        self,
        progress_current: int,
        progress_total: int,
    ) -> bool:
        """验证进度值是否有效"""
        raise NotImplementedError

    def _calculate_duration(
        self,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
    ) -> Optional[float]:
        """计算时间差（秒）"""
        raise NotImplementedError


# =============================================================================
# 导出列表
# =============================================================================

__all__ = [
    # 数据模型
    "Task",
    "TaskCreate",
    "TaskUpdate",
    "TaskWithStats",
    # 枚举
    "TaskStatus",
    "TaskType",
    # 异常
    "TaskError",
    "TaskNotFoundError",
    "TaskAlreadyExistsError",
    "InvalidTaskStatusError",
    "InvalidPriorityError",
    "ProgressError",
    # 主类
    "TaskManager",
]