"""
任务数据模型和CRUD操作
版本：v1.0
文件映射：docs/02-architecture/database-schema.sql (tasks表)

职责：任务数据的创建、读取、更新、删除操作，状态跟踪，进度管理
依赖：src/reelforge/models/database/ (Database, DatabaseError等)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

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
        self._db = database
        self._logger = logging.getLogger(__name__)

        # 确保数据库已连接
        try:
            self._db.connect()
        except Exception as e:
            raise TaskError(f"Database connection failed: {e}") from e

    # =========================================================================
    # 私有方法
    # =========================================================================

    def _get_last_insert_id(self) -> int:
        """获取最后插入的ID（可能不可靠，尽量使用外部任务ID代替）"""
        try:
            result = self._db.query("SELECT last_insert_rowid() as id", ())
            rows = list(result)
            if not rows:
                raise TaskError("No last insert ID found")
            return int(rows[0]["id"])
        except DatabaseError as e:
            raise TaskError(f"Failed to get last insert ID: {e}") from e

    def _is_valid_status_transition(self, current: TaskStatus, new: TaskStatus) -> bool:
        """验证状态转换是否有效"""
        # 定义允许的状态转换
        valid_transitions = {
            TaskStatus.QUEUED: [TaskStatus.PROCESSING, TaskStatus.CANCELLED],
            TaskStatus.PROCESSING: [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.PAUSED],
            TaskStatus.PAUSED: [TaskStatus.PROCESSING, TaskStatus.CANCELLED],
            TaskStatus.CANCELLED: [],  # 取消后不能再转换
            TaskStatus.COMPLETED: [],  # 完成后不能再转换
            TaskStatus.FAILED: [],  # 失败后不能再转换
        }

        # 如果状态未定义或相同状态，允许转换（自身转换用于更新其他字段）
        if current == new:
            return True

        # 检查是否允许转换
        return new in valid_transitions.get(current, [])

    def _safe_parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """安全解析日期时间字符串"""
        if not dt_str:
            return None
        try:
            return datetime.fromisoformat(dt_str)
        except ValueError:
            self._logger.warning(f"Failed to parse datetime: {dt_str}")
            return None

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
        self._logger.info(f"Creating task: {task_data.external_task_id}")

        # 验证数据
        if not task_data.external_task_id.strip():
            raise TaskError("External task ID cannot be empty")

        if task_data.project_id <= 0:
            raise TaskError("Project ID must be positive")

        if task_data.priority < 0:
            raise InvalidPriorityError("Priority must be non-negative")

        if task_data.progress_total <= 0:
            raise ProgressError("Progress total must be positive")

        # 检查外部任务ID是否已存在
        try:
            self.get_by_external_id(task_data.external_task_id)
            raise TaskAlreadyExistsError(
                f"Task with external ID '{task_data.external_task_id}' already exists"
            )
        except TaskNotFoundError:
            # 外部任务ID不存在，可以继续创建
            pass

        # 构建SQL
        sql = """
        INSERT INTO tasks (
            task_id, project_id, status, task_type, priority,
            progress_current, progress_total,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """

        params = (
            task_data.external_task_id.strip(),
            task_data.project_id,
            TaskStatus.QUEUED.value,
            task_data.task_type.value,
            task_data.priority,
            0,  # progress_current 初始为0
            task_data.progress_total,
        )

        try:
            # 执行插入
            affected = self._db.execute(sql, params)
            if affected != 1:
                raise TaskError(f"Failed to create task: affected rows={affected}")

            # 通过外部任务ID获取新创建的任务（更可靠，因为last_insert_rowid可能在不同连接中失效）
            return self.get_by_external_id(task_data.external_task_id)

        except DatabaseError as e:
            raise TaskError(f"Failed to create task: {e}") from e

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
        self._logger.debug(f"Getting task by ID: {task_id}")

        sql = """
        SELECT id, task_id, project_id, status, task_type, priority,
               progress_current, progress_total, progress_message,
               error_code, error_message, error_stack,
               created_at, updated_at, started_at, completed_at
        FROM tasks
        WHERE id = ?
        """

        try:
            result = self._db.query(sql, (task_id,))
            rows = list(result)

            if not rows:
                raise TaskNotFoundError(f"Task with ID {task_id} not found")

            if len(rows) > 1:
                self._logger.warning(f"Multiple tasks found with ID {task_id}")

            return Task.from_row(dict(rows[0]))

        except DatabaseError as e:
            raise TaskError(f"Failed to get task by ID: {e}") from e

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
        self._logger.debug(f"Getting task by external ID: {external_task_id}")

        sql = """
        SELECT id, task_id, project_id, status, task_type, priority,
               progress_current, progress_total, progress_message,
               error_code, error_message, error_stack,
               created_at, updated_at, started_at, completed_at
        FROM tasks
        WHERE task_id = ?
        """

        try:
            result = self._db.query(sql, (external_task_id,))
            rows = list(result)

            if not rows:
                raise TaskNotFoundError(f"Task with external ID '{external_task_id}' not found")

            if len(rows) > 1:
                self._logger.warning(f"Multiple tasks found with external ID '{external_task_id}'")

            return Task.from_row(dict(rows[0]))

        except TaskNotFoundError:
            # 直接传递任务未找到异常
            raise
        except DatabaseError as e:
            raise TaskError(f"Failed to get task by external ID: {e}") from e

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
        self._logger.info(f"Updating task {task_id}")

        # 检查任务是否存在
        task = self.get_by_id(task_id)

        # 构建更新SQL
        updates = []
        params: List[Any] = []

        # 验证并构建更新字段
        if update_data.status is not None:
            # 验证状态转换
            if not self._is_valid_status_transition(task.status, update_data.status):
                raise InvalidTaskStatusError(
                    f"Invalid status transition: {task.status} -> {update_data.status}"
                )
            updates.append("status = ?")
            params.append(update_data.status.value)

            # 如果是开始处理，设置started_at
            if update_data.status == TaskStatus.PROCESSING and update_data.started_at is None:
                updates.append("started_at = CURRENT_TIMESTAMP")

            # 如果是完成或失败，设置completed_at
            if update_data.status in [TaskStatus.COMPLETED, TaskStatus.FAILED] and update_data.completed_at is None:
                updates.append("completed_at = CURRENT_TIMESTAMP")

        if update_data.priority is not None:
            if update_data.priority < 0:
                raise InvalidPriorityError("Priority must be non-negative")
            updates.append("priority = ?")
            params.append(update_data.priority)

        if update_data.progress_current is not None:
            progress_total = update_data.progress_total or task.progress_total
            if update_data.progress_current < 0:
                raise ProgressError("Progress current cannot be negative")
            if update_data.progress_current > progress_total:
                raise ProgressError(f"Progress current ({update_data.progress_current}) cannot exceed total ({progress_total})")
            updates.append("progress_current = ?")
            params.append(update_data.progress_current)

        if update_data.progress_total is not None:
            if update_data.progress_total <= 0:
                raise ProgressError("Progress total must be positive")
            updates.append("progress_total = ?")
            params.append(update_data.progress_total)

        if update_data.progress_message is not None:
            updates.append("progress_message = ?")
            params.append(update_data.progress_message)

        if update_data.error_code is not None:
            updates.append("error_code = ?")
            params.append(update_data.error_code)

        if update_data.error_message is not None:
            updates.append("error_message = ?")
            params.append(update_data.error_message)

        if update_data.error_stack is not None:
            updates.append("error_stack = ?")
            params.append(update_data.error_stack)

        if update_data.started_at is not None:
            updates.append("started_at = ?")
            params.append(update_data.started_at.isoformat() if isinstance(update_data.started_at, datetime) else None)

        if update_data.completed_at is not None:
            updates.append("completed_at = ?")
            params.append(update_data.completed_at.isoformat() if isinstance(update_data.completed_at, datetime) else None)

        # 如果没有更新内容，直接返回原任务
        if not updates:
            return task

        # 添加updated_at自动更新
        updates.append("updated_at = CURRENT_TIMESTAMP")

        # 构建完整SQL
        sql = f"""
        UPDATE tasks
        SET {', '.join(updates)}
        WHERE id = ?
        """

        params.append(task_id)

        try:
            affected = self._db.execute(sql, tuple(params))
            if affected != 1:
                raise TaskError(f"Failed to update task: affected rows={affected}")

            return self.get_by_id(task_id)

        except DatabaseError as e:
            raise TaskError(f"Failed to update task: {e}") from e

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
        self._logger.info(f"Deleting task {task_id}")

        # 检查任务是否存在
        self.get_by_id(task_id)

        sql = "DELETE FROM tasks WHERE id = ?"

        try:
            affected = self._db.execute(sql, (task_id,))
            success = affected == 1
            if success:
                self._logger.info(f"Deleted task {task_id}")
            else:
                self._logger.warning(f"Task {task_id} not found")
            return success

        except DatabaseError as e:
            raise TaskError(f"Failed to delete task: {e}") from e

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
        self._logger.info(f"Updating task {task_id} status to {new_status}")

        update_data = TaskUpdate(status=new_status)
        return self.update(task_id, update_data)

    def mark_as_processing(self, task_id: int) -> Task:
        """
        标记任务为处理中（设置started_at）

        Args:
            task_id: 任务ID

        Returns:
            Task: 更新后的任务对象
        """
        self._logger.info(f"Marking task {task_id} as processing")

        update_data = TaskUpdate(
            status=TaskStatus.PROCESSING,
            started_at=datetime.now()
        )
        return self.update(task_id, update_data)

    def mark_as_completed(self, task_id: int) -> Task:
        """
        标记任务为已完成（设置completed_at）

        Args:
            task_id: 任务ID

        Returns:
            Task: 更新后的任务对象
        """
        self._logger.info(f"Marking task {task_id} as completed")

        # 获取当前任务以检查进度
        task = self.get_by_id(task_id)

        # 确保进度为100%
        if task.progress_current != task.progress_total:
            self._logger.warning(f"Task {task_id} progress is {task.progress_current}/{task.progress_total}, setting to 100%")
            update_data = TaskUpdate(
                status=TaskStatus.COMPLETED,
                progress_current=task.progress_total,
                completed_at=datetime.now()
            )
        else:
            update_data = TaskUpdate(
                status=TaskStatus.COMPLETED,
                completed_at=datetime.now()
            )

        return self.update(task_id, update_data)

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
        self._logger.error(f"Marking task {task_id} as failed: {error_code} - {error_message}")

        update_data = TaskUpdate(
            status=TaskStatus.FAILED,
            error_code=error_code,
            error_message=error_message,
            error_stack=error_stack,
            completed_at=datetime.now()
        )
        return self.update(task_id, update_data)

    def pause_task(self, task_id: int) -> Task:
        """
        暂停任务

        Args:
            task_id: 任务ID

        Returns:
            Task: 更新后的任务对象
        """
        self._logger.info(f"Pausing task {task_id}")

        # 只能暂停处理中的任务
        task = self.get_by_id(task_id)
        if task.status != TaskStatus.PROCESSING:
            raise InvalidTaskStatusError(f"Cannot pause task in {task.status} state")

        return self.update_status(task_id, TaskStatus.PAUSED)

    def cancel_task(self, task_id: int) -> Task:
        """
        取消任务

        Args:
            task_id: 任务ID

        Returns:
            Task: 更新后的任务对象
        """
        self._logger.info(f"Cancelling task {task_id}")

        # 只能取消排队中或暂停的任务
        task = self.get_by_id(task_id)
        if task.status not in [TaskStatus.QUEUED, TaskStatus.PAUSED]:
            raise InvalidTaskStatusError(f"Cannot cancel task in {task.status} state")

        return self.update_status(task_id, TaskStatus.CANCELLED)

    def resume_task(self, task_id: int) -> Task:
        """
        恢复任务（从paused状态）

        Args:
            task_id: 任务ID

        Returns:
            Task: 更新后的任务对象
        """
        self._logger.info(f"Resuming task {task_id}")

        # 只能恢复暂停的任务
        task = self.get_by_id(task_id)
        if task.status != TaskStatus.PAUSED:
            raise InvalidTaskStatusError(f"Cannot resume task in {task.status} state")

        return self.update_status(task_id, TaskStatus.PROCESSING)

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
        self._logger.info(f"Updating task {task_id} progress to {progress_current}")

        # 验证进度
        if progress_current < 0:
            raise ProgressError("Progress current cannot be negative")

        # 如果未提供progress_total，使用现有值
        task = self.get_by_id(task_id)
        if progress_total is None:
            progress_total = task.progress_total

        if progress_current > progress_total:
            raise ProgressError(f"Progress current ({progress_current}) cannot exceed total ({progress_total})")

        if progress_total <= 0:
            raise ProgressError("Progress total must be positive")

        update_data = TaskUpdate(
            progress_current=progress_current,
            progress_total=progress_total,
            progress_message=progress_message
        )
        return self.update(task_id, update_data)

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
        self._logger.debug(f"Incrementing task {task_id} progress by {increment}")

        if increment <= 0:
            raise ProgressError("Increment must be positive")

        task = self.get_by_id(task_id)
        new_progress = task.progress_current + increment

        # 如果超过总进度，设置为总进度
        if new_progress > task.progress_total:
            new_progress = task.progress_total
            self._logger.info(f"Task {task_id} progress capped at total: {new_progress}")

        return self.update_progress(task_id, new_progress, None, progress_message)

    def get_progress_percentage(self, task_id: int) -> float:
        """
        获取任务进度百分比

        Args:
            task_id: 任务ID

        Returns:
            float: 进度百分比（0-100）
        """
        task = self.get_by_id(task_id)

        if task.progress_total == 0:
            return 0.0

        percentage = (task.progress_current / task.progress_total) * 100.0
        return round(percentage, 2)

    def reset_progress(self, task_id: int) -> Task:
        """
        重置任务进度（恢复为初始状态）

        Args:
            task_id: 任务ID

        Returns:
            Task: 更新后的任务对象
        """
        self._logger.info(f"Resetting task {task_id} progress")

        # 获取任务以获取原始progress_total
        task = self.get_by_id(task_id)

        # 只能重置排队中或暂停的任务
        if task.status not in [TaskStatus.QUEUED, TaskStatus.PAUSED]:
            raise InvalidTaskStatusError(f"Cannot reset progress for task in {task.status} state")

        update_data = TaskUpdate(
            progress_current=0,
            progress_total=task.progress_total
        )
        return self.update(task_id, update_data)

    # =========================================================================
    # 查询操作
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
        self._logger.debug(f"Getting tasks for project {project_id}")

        # 验证参数
        if project_id <= 0:
            raise TaskError("Project ID must be positive")

        if limit < 0:
            raise TaskError("Limit must be non-negative")

        if offset < 0:
            raise TaskError("Offset must be non-negative")

        # 构建SQL
        where_clauses = ["project_id = ?"]
        params: List[Any] = [project_id]

        if status is not None:
            where_clauses.append("status = ?")
            params.append(status.value)

        if task_type is not None:
            where_clauses.append("task_type = ?")
            params.append(task_type.value)

        where_sql = " AND ".join(where_clauses)

        # 排序
        order_by = "created_at DESC" if order_by_created else "priority DESC, created_at DESC"

        sql = f"""
        SELECT id, task_id, project_id, status, task_type, priority,
               progress_current, progress_total, progress_message,
               error_code, error_message, error_stack,
               created_at, updated_at, started_at, completed_at
        FROM tasks
        WHERE {where_sql}
        ORDER BY {order_by}
        LIMIT ? OFFSET ?
        """

        params.append(limit)
        params.append(offset)

        try:
            result = self._db.query(sql, tuple(params))
            return [Task.from_row(dict(row)) for row in result]

        except DatabaseError as e:
            raise TaskError(f"Failed to get tasks by project: {e}") from e

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
        self._logger.debug(f"Getting tasks with status {status}")

        # 验证参数
        if limit < 0:
            raise TaskError("Limit must be non-negative")

        if offset < 0:
            raise TaskError("Offset must be non-negative")

        # 构建SQL
        where_clauses = ["status = ?"]
        params: List[Any] = [status.value]

        if project_id is not None:
            if project_id <= 0:
                raise TaskError("Project ID must be positive")
            where_clauses.append("project_id = ?")
            params.append(project_id)

        if task_type is not None:
            where_clauses.append("task_type = ?")
            params.append(task_type.value)

        where_sql = " AND ".join(where_clauses)

        sql = f"""
        SELECT id, task_id, project_id, status, task_type, priority,
               progress_current, progress_total, progress_message,
               error_code, error_message, error_stack,
               created_at, updated_at, started_at, completed_at
        FROM tasks
        WHERE {where_sql}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """

        params.append(limit)
        params.append(offset)

        try:
            result = self._db.query(sql, tuple(params))
            return [Task.from_row(dict(row)) for row in result]

        except DatabaseError as e:
            raise TaskError(f"Failed to get tasks by status: {e}") from e

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
        self._logger.debug(f"Getting tasks of type {task_type}")

        # 验证参数
        if limit < 0:
            raise TaskError("Limit must be non-negative")

        if offset < 0:
            raise TaskError("Offset must be non-negative")

        # 构建SQL
        where_clauses = ["task_type = ?"]
        params: List[Any] = [task_type.value]

        if project_id is not None:
            if project_id <= 0:
                raise TaskError("Project ID must be positive")
            where_clauses.append("project_id = ?")
            params.append(project_id)

        if status is not None:
            where_clauses.append("status = ?")
            params.append(status.value)

        where_sql = " AND ".join(where_clauses)

        sql = f"""
        SELECT id, task_id, project_id, status, task_type, priority,
               progress_current, progress_total, progress_message,
               error_code, error_message, error_stack,
               created_at, updated_at, started_at, completed_at
        FROM tasks
        WHERE {where_sql}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """

        params.append(limit)
        params.append(offset)

        try:
            result = self._db.query(sql, tuple(params))
            return [Task.from_row(dict(row)) for row in result]

        except DatabaseError as e:
            raise TaskError(f"Failed to get tasks by type: {e}") from e

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
        self._logger.debug("Listing all tasks")

        # 验证参数
        if limit < 0:
            raise TaskError("Limit must be non-negative")

        if offset < 0:
            raise TaskError("Offset must be non-negative")

        # 构建SQL
        where_clauses = []
        params: List[Any] = []

        if project_id is not None:
            if project_id <= 0:
                raise TaskError("Project ID must be positive")
            where_clauses.append("project_id = ?")
            params.append(project_id)

        if status is not None:
            where_clauses.append("status = ?")
            params.append(status.value)

        if task_type is not None:
            where_clauses.append("task_type = ?")
            params.append(task_type.value)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # 排序
        order_by = "priority DESC, created_at DESC" if order_by_priority else "created_at DESC"

        sql = f"""
        SELECT id, task_id, project_id, status, task_type, priority,
               progress_current, progress_total, progress_message,
               error_code, error_message, error_stack,
               created_at, updated_at, started_at, completed_at
        FROM tasks
        WHERE {where_sql}
        ORDER BY {order_by}
        LIMIT ? OFFSET ?
        """

        params.append(limit)
        params.append(offset)

        try:
            result = self._db.query(sql, tuple(params))
            return [Task.from_row(dict(row)) for row in result]

        except DatabaseError as e:
            raise TaskError(f"Failed to list tasks: {e}") from e

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
        self._logger.debug("Getting pending tasks")

        # 验证参数
        if limit < 0:
            raise TaskError("Limit must be non-negative")

        if offset < 0:
            raise TaskError("Offset must be non-negative")

        # 构建SQL
        where_clauses = ["status IN (?, ?)"]
        params: List[Any] = [TaskStatus.QUEUED.value, TaskStatus.PAUSED.value]

        if project_id is not None:
            if project_id <= 0:
                raise TaskError("Project ID must be positive")
            where_clauses.append("project_id = ?")
            params.append(project_id)

        if task_type is not None:
            where_clauses.append("task_type = ?")
            params.append(task_type.value)

        where_sql = " AND ".join(where_clauses)

        sql = f"""
        SELECT id, task_id, project_id, status, task_type, priority,
               progress_current, progress_total, progress_message,
               error_code, error_message, error_stack,
               created_at, updated_at, started_at, completed_at
        FROM tasks
        WHERE {where_sql}
        ORDER BY priority DESC, created_at ASC
        LIMIT ? OFFSET ?
        """

        params.append(limit)
        params.append(offset)

        try:
            result = self._db.query(sql, tuple(params))
            return [Task.from_row(dict(row)) for row in result]

        except DatabaseError as e:
            raise TaskError(f"Failed to get pending tasks: {e}") from e

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
        self._logger.debug("Getting active tasks")

        # 验证参数
        if limit < 0:
            raise TaskError("Limit must be non-negative")

        if offset < 0:
            raise TaskError("Offset must be non-negative")

        # 构建SQL
        where_clauses = ["status = ?"]
        params: List[Any] = [TaskStatus.PROCESSING.value]

        if project_id is not None:
            if project_id <= 0:
                raise TaskError("Project ID must be positive")
            where_clauses.append("project_id = ?")
            params.append(project_id)

        if task_type is not None:
            where_clauses.append("task_type = ?")
            params.append(task_type.value)

        where_sql = " AND ".join(where_clauses)

        sql = f"""
        SELECT id, task_id, project_id, status, task_type, priority,
               progress_current, progress_total, progress_message,
               error_code, error_message, error_stack,
               created_at, updated_at, started_at, completed_at
        FROM tasks
        WHERE {where_sql}
        ORDER BY started_at ASC
        LIMIT ? OFFSET ?
        """

        params.append(limit)
        params.append(offset)

        try:
            result = self._db.query(sql, tuple(params))
            return [Task.from_row(dict(row)) for row in result]

        except DatabaseError as e:
            raise TaskError(f"Failed to get active tasks: {e}") from e

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
        self._logger.debug("Counting tasks")

        # 构建SQL
        where_clauses = []
        params: List[Any] = []

        if project_id is not None:
            if project_id <= 0:
                raise TaskError("Project ID must be positive")
            where_clauses.append("project_id = ?")
            params.append(project_id)

        if status is not None:
            where_clauses.append("status = ?")
            params.append(status.value)

        if task_type is not None:
            where_clauses.append("task_type = ?")
            params.append(task_type.value)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        sql = f"""
        SELECT COUNT(*) as count
        FROM tasks
        WHERE {where_sql}
        """

        try:
            result = self._db.query(sql, tuple(params))
            row = list(result)[0]
            return int(row["count"])

        except DatabaseError as e:
            raise TaskError(f"Failed to count tasks: {e}") from e

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
        self._logger.debug(f"Searching tasks by progress message: '{query}'")

        # 验证参数
        if limit < 0:
            raise TaskError("Limit must be non-negative")

        # 构建SQL
        where_clauses = ["progress_message LIKE ?"]
        params: List[Any] = [f"%{query}%"]

        if project_id is not None:
            if project_id <= 0:
                raise TaskError("Project ID must be positive")
            where_clauses.append("project_id = ?")
            params.append(project_id)

        where_sql = " AND ".join(where_clauses)

        sql = f"""
        SELECT id, task_id, project_id, status, task_type, priority,
               progress_current, progress_total, progress_message,
               error_code, error_message, error_stack,
               created_at, updated_at, started_at, completed_at
        FROM tasks
        WHERE {where_sql}
        ORDER BY updated_at DESC
        LIMIT ?
        """

        params.append(limit)

        try:
            result = self._db.query(sql, tuple(params))
            return [Task.from_row(dict(row)) for row in result]

        except DatabaseError as e:
            raise TaskError(f"Failed to search tasks by progress message: {e}") from e

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
        self._logger.info(f"Batch creating {len(tasks_data)} tasks")

        if not tasks_data:
            return []

        # 验证所有任务数据
        for task_data in tasks_data:
            if not task_data.external_task_id.strip():
                raise TaskError("External task ID cannot be empty")

            if task_data.project_id <= 0:
                raise TaskError("Project ID must be positive")

            if task_data.priority < 0:
                raise InvalidPriorityError("Priority must be non-negative")

            if task_data.progress_total <= 0:
                raise ProgressError("Progress total must be positive")

        # 检查外部任务ID是否已存在
        existing_ids = set()
        for task_data in tasks_data:
            try:
                self.get_by_external_id(task_data.external_task_id)
                existing_ids.add(task_data.external_task_id)
            except TaskNotFoundError:
                pass

        if existing_ids:
            raise TaskAlreadyExistsError(
                f"Tasks with external IDs already exist: {', '.join(existing_ids)}"
            )

        # 构建批量插入SQL
        sql = """
        INSERT INTO tasks (
            task_id, project_id, status, task_type, priority,
            progress_current, progress_total,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """

        # 准备批量参数和外部任务ID映射
        params_list = []
        external_id_map = {}  # external_task_id -> index

        for idx, task_data in enumerate(tasks_data):
            external_id = task_data.external_task_id.strip()
            params = (
                external_id,
                task_data.project_id,
                TaskStatus.QUEUED.value,
                task_data.task_type.value,
                task_data.priority,
                0,  # progress_current 初始为0
                task_data.progress_total,
            )
            params_list.append(params)
            external_id_map[external_id] = idx

        try:
            # 在事务中执行批量插入
            with self._db.transaction() as tx:
                # 逐个插入
                for params in params_list:
                    cursor = tx.execute(sql, params)
                    if cursor is None:
                        raise TaskError("Failed to create task in batch: cursor is None")

                # 批量查询所有插入的任务（通过外部任务ID）
                created_tasks = []
                for external_id in external_id_map.keys():
                    cursor = tx.execute("""
                        SELECT id, task_id, project_id, status, task_type, priority,
                               progress_current, progress_total, progress_message,
                               error_code, error_message, error_stack,
                               created_at, updated_at, started_at, completed_at
                        FROM tasks WHERE task_id = ?
                    """, (external_id,))

                    row = cursor.fetchone()
                    if not row:
                        raise TaskError(f"Failed to retrieve created task with external ID '{external_id}'")

                    created_tasks.append(Task.from_row(dict(row)))

            # 按照原始顺序排序
            created_tasks.sort(key=lambda t: external_id_map.get(t.external_task_id, 999))

            self._logger.info(f"Successfully created {len(created_tasks)} tasks")
            return created_tasks

        except DatabaseError as e:
            raise TaskError(f"Batch create failed: {e}") from e

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
        self._logger.info(f"Batch updating {len(task_ids)} tasks to status {new_status}")

        if not task_ids:
            return []

        # 验证任务ID
        for task_id in task_ids:
            if task_id <= 0:
                raise TaskError(f"Invalid task ID: {task_id}")

        try:
            # 在事务中执行批量更新
            with self._db.transaction() as tx:
                # 批量更新状态
                sql = "UPDATE tasks SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?"

                for task_id in task_ids:
                    cursor = tx.execute(sql, (new_status.value, task_id))
                    if cursor is None:
                        self._logger.warning(f"Task {task_id} not found during batch update")

            # 获取更新后的任务对象
            updated_tasks = []
            for task_id in task_ids:
                try:
                    task = self.get_by_id(task_id)
                    updated_tasks.append(task)
                except TaskNotFoundError:
                    self._logger.warning(f"Task {task_id} not found after batch update")

            self._logger.info(f"Successfully updated {len(updated_tasks)} tasks")
            return updated_tasks

        except DatabaseError as e:
            raise TaskError(f"Batch update status failed: {e}") from e

    def batch_delete(self, task_ids: List[int]) -> Dict[str, Any]:
        """
        批量删除任务

        Args:
            task_ids: 任务ID列表

        Returns:
            Dict[str, Any]: 删除结果统计
        """
        self._logger.info(f"Batch deleting {len(task_ids)} tasks")

        if not task_ids:
            return {"deleted": 0, "not_found": 0, "total": 0}

        # 验证任务ID
        for task_id in task_ids:
            if task_id <= 0:
                raise TaskError(f"Invalid task ID: {task_id}")

        try:
            # 在事务中执行批量删除
            with self._db.transaction() as tx:
                deleted_count = 0
                not_found = []

                for task_id in task_ids:
                    # 检查任务是否存在
                    cursor = tx.execute("SELECT id FROM tasks WHERE id = ?", (task_id,))
                    row = cursor.fetchone()
                    if not row:
                        not_found.append(task_id)
                        continue

                    # 删除任务
                    cursor = tx.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
                    if cursor is not None:
                        deleted_count += 1

            result_stats = {
                "deleted": deleted_count,
                "not_found": len(not_found),
                "total": len(task_ids),
                "not_found_ids": not_found if not_found else []
            }

            self._logger.info(f"Batch delete completed: {deleted_count} deleted, {len(not_found)} not found")
            return result_stats

        except DatabaseError as e:
            raise TaskError(f"Batch delete failed: {e}") from e

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
        self._logger.debug("Getting task statistics")

        # 构建where条件
        where_clauses = []
        params: List[Any] = []

        if project_id is not None:
            if project_id <= 0:
                raise TaskError("Project ID must be positive")
            where_clauses.append("project_id = ?")
            params.append(project_id)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        try:
            # 获取基本统计
            sql_basic = f"""
            SELECT
                COUNT(*) as total_count,
                SUM(CASE WHEN status = 'queued' THEN 1 ELSE 0 END) as queued_count,
                SUM(CASE WHEN status = 'processing' THEN 1 ELSE 0 END) as processing_count,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_count,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_count,
                SUM(CASE WHEN status = 'paused' THEN 1 ELSE 0 END) as paused_count,
                SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled_count,
                AVG(priority) as avg_priority
            FROM tasks
            WHERE {where_sql}
            """

            result = self._db.query(sql_basic, tuple(params))
            row = dict(list(result)[0])

            # 获取平均处理时间
            avg_processing_time = self.get_average_processing_time(project_id)
            failure_rate = self.get_failure_rate(project_id)

            # 获取状态分布
            status_dist = self.get_status_distribution(project_id)
            type_dist = self.get_type_distribution(project_id)

            stats = {
                "total_count": int(row["total_count"]) if row["total_count"] else 0,
                "queued_count": int(row["queued_count"]) if row["queued_count"] else 0,
                "processing_count": int(row["processing_count"]) if row["processing_count"] else 0,
                "completed_count": int(row["completed_count"]) if row["completed_count"] else 0,
                "failed_count": int(row["failed_count"]) if row["failed_count"] else 0,
                "paused_count": int(row["paused_count"]) if row["paused_count"] else 0,
                "cancelled_count": int(row["cancelled_count"]) if row["cancelled_count"] else 0,
                "avg_priority": float(row["avg_priority"]) if row["avg_priority"] else 0.0,
                "avg_processing_time": avg_processing_time,
                "failure_rate": failure_rate,
                "status_distribution": status_dist,
                "type_distribution": type_dist,
            }

            return stats

        except DatabaseError as e:
            raise TaskError(f"Failed to get statistics: {e}") from e

    def get_with_stats(self, task_id: int) -> TaskWithStats:
        """
        获取任务及其统计信息

        Args:
            task_id: 任务ID

        Returns:
            TaskWithStats: 包含统计信息的任务对象
        """
        self._logger.debug(f"Getting task {task_id} with stats")

        # 获取基础任务信息
        task = self.get_by_id(task_id)

        try:
            # 获取项目名称
            sql_project = "SELECT name FROM projects WHERE id = ?"
            result = self._db.query(sql_project, (task.project_id,))
            rows = list(result)
            project_name = rows[0]["name"] if rows else None

            # 计算时长
            processing_duration = self.get_processing_time(task_id)
            waiting_duration = self.get_waiting_time(task_id)

            # 创建TaskWithStats对象
            return TaskWithStats(
                task_id=task.task_id,
                external_task_id=task.external_task_id,
                project_id=task.project_id,
                status=task.status,
                task_type=task.task_type,
                priority=task.priority,
                progress_current=task.progress_current,
                progress_total=task.progress_total,
                progress_message=task.progress_message,
                error_code=task.error_code,
                error_message=task.error_message,
                error_stack=task.error_stack,
                created_at=task.created_at,
                updated_at=task.updated_at,
                started_at=task.started_at,
                completed_at=task.completed_at,
                project_name=project_name,
                processing_duration=processing_duration,
                waiting_duration=waiting_duration,
            )

        except DatabaseError as e:
            raise TaskError(f"Failed to get task with stats: {e}") from e

    def get_status_distribution(self, project_id: Optional[int] = None) -> Dict[str, int]:
        """
        获取状态分布统计

        Args:
            project_id: 按项目ID过滤（可选）

        Returns:
            Dict[str, int]: 状态->数量映射
        """
        self._logger.debug("Getting status distribution")

        # 构建where条件
        where_clauses = []
        params: List[Any] = []

        if project_id is not None:
            if project_id <= 0:
                raise TaskError("Project ID must be positive")
            where_clauses.append("project_id = ?")
            params.append(project_id)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        sql = f"""
        SELECT status, COUNT(*) as count
        FROM tasks
        WHERE {where_sql}
        GROUP BY status
        ORDER BY count DESC
        """

        try:
            result = self._db.query(sql, tuple(params))
            distribution = {}
            for row in result:
                distribution[row["status"]] = int(row["count"])
            return distribution

        except DatabaseError as e:
            raise TaskError(f"Failed to get status distribution: {e}") from e

    def get_type_distribution(self, project_id: Optional[int] = None) -> Dict[str, int]:
        """
        获取类型分布统计

        Args:
            project_id: 按项目ID过滤（可选）

        Returns:
            Dict[str, int]: 类型->数量映射
        """
        self._logger.debug("Getting type distribution")

        # 构建where条件
        where_clauses = []
        params: List[Any] = []

        if project_id is not None:
            if project_id <= 0:
                raise TaskError("Project ID must be positive")
            where_clauses.append("project_id = ?")
            params.append(project_id)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        sql = f"""
        SELECT task_type, COUNT(*) as count
        FROM tasks
        WHERE {where_sql}
        GROUP BY task_type
        ORDER BY count DESC
        """

        try:
            result = self._db.query(sql, tuple(params))
            distribution = {}
            for row in result:
                distribution[row["task_type"]] = int(row["count"])
            return distribution

        except DatabaseError as e:
            raise TaskError(f"Failed to get type distribution: {e}") from e

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
        self._logger.debug("Getting average processing time")

        # 构建where条件
        where_clauses = ["status = ?", "started_at IS NOT NULL", "completed_at IS NOT NULL"]
        params: List[Any] = [TaskStatus.COMPLETED.value]

        if project_id is not None:
            if project_id <= 0:
                raise TaskError("Project ID must be positive")
            where_clauses.append("project_id = ?")
            params.append(project_id)

        if task_type is not None:
            where_clauses.append("task_type = ?")
            params.append(task_type.value)

        where_sql = " AND ".join(where_clauses)

        sql = f"""
        SELECT AVG(
            (julianday(completed_at) - julianday(started_at)) * 86400.0
        ) as avg_seconds
        FROM tasks
        WHERE {where_sql}
        """

        try:
            result = self._db.query(sql, tuple(params))
            row = list(result)[0]
            avg_seconds = row["avg_seconds"]

            if avg_seconds is None:
                return None

            return float(avg_seconds)

        except DatabaseError as e:
            raise TaskError(f"Failed to get average processing time: {e}") from e

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
        self._logger.debug("Getting failure rate")

        # 构建where条件
        where_clauses = []
        params: List[Any] = []

        if project_id is not None:
            if project_id <= 0:
                raise TaskError("Project ID must be positive")
            where_clauses.append("project_id = ?")
            params.append(project_id)

        if task_type is not None:
            where_clauses.append("task_type = ?")
            params.append(task_type.value)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        sql = f"""
        SELECT
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_count,
            COUNT(*) as total_count
        FROM tasks
        WHERE {where_sql} AND status IN ('completed', 'failed')
        """

        try:
            result = self._db.query(sql, tuple(params))
            row = list(result)[0]

            failed_count = int(row["failed_count"]) if row["failed_count"] else 0
            total_count = int(row["total_count"]) if row["total_count"] else 0

            if total_count == 0:
                return 0.0

            failure_rate = (failed_count / total_count) * 100.0
            return round(failure_rate, 2)

        except DatabaseError as e:
            raise TaskError(f"Failed to get failure rate: {e}") from e

    def get_waiting_time(self, task_id: int) -> Optional[float]:
        """
        获取任务等待时间

        Args:
            task_id: 任务ID

        Returns:
            Optional[float]: 等待时间（秒），未开始返回None
        """
        self._logger.debug(f"Getting waiting time for task {task_id}")

        task = self.get_by_id(task_id)

        if task.started_at is None:
            # 如果任务未开始，计算从创建到现在的等待时间
            if task.status not in [TaskStatus.QUEUED, TaskStatus.PAUSED]:
                return None

            return self._calculate_duration(task.created_at, datetime.now())

        # 如果已开始，等待时间是从创建到开始的时间
        return self._calculate_duration(task.created_at, task.started_at)

    def get_processing_time(self, task_id: int) -> Optional[float]:
        """
        获取任务处理时间

        Args:
            task_id: 任务ID

        Returns:
            Optional[float]: 处理时间（秒），未完成返回None
        """
        self._logger.debug(f"Getting processing time for task {task_id}")

        task = self.get_by_id(task_id)

        if task.started_at is None or task.completed_at is None:
            # 如果任务未开始或未完成
            if task.status == TaskStatus.PROCESSING:
                # 处理中的任务，计算从开始到现在的时间
                return self._calculate_duration(task.started_at, datetime.now())
            return None

        # 已完成的任务，计算从开始到完成的时间
        return self._calculate_duration(task.started_at, task.completed_at)

    def get_total_time(self, task_id: int) -> Optional[float]:
        """
        获取任务总时间（创建到完成）

        Args:
            task_id: 任务ID

        Returns:
            Optional[float]: 总时间（秒），未完成返回None
        """
        self._logger.debug(f"Getting total time for task {task_id}")

        task = self.get_by_id(task_id)

        if task.completed_at is None:
            # 如果任务未完成，计算从创建到现在的时间
            if task.status in [TaskStatus.QUEUED, TaskStatus.PROCESSING, TaskStatus.PAUSED]:
                return self._calculate_duration(task.created_at, datetime.now())
            return None

        # 已完成的任务，计算从创建到完成的时间
        return self._calculate_duration(task.created_at, task.completed_at)

    def get_oldest_pending_task(self, project_id: Optional[int] = None) -> Optional[Task]:
        """
        获取最老的待处理任务

        Args:
            project_id: 按项目ID过滤（可选）

        Returns:
            Optional[Task]: 最老的待处理任务，无返回None
        """
        self._logger.debug("Getting oldest pending task")

        # 构建where条件
        where_clauses = ["status IN (?, ?)"]
        params: List[Any] = [TaskStatus.QUEUED.value, TaskStatus.PAUSED.value]

        if project_id is not None:
            if project_id <= 0:
                raise TaskError("Project ID must be positive")
            where_clauses.append("project_id = ?")
            params.append(project_id)

        where_sql = " AND ".join(where_clauses)

        sql = f"""
        SELECT id, task_id, project_id, status, task_type, priority,
               progress_current, progress_total, progress_message,
               error_code, error_message, error_stack,
               created_at, updated_at, started_at, completed_at
        FROM tasks
        WHERE {where_sql}
        ORDER BY created_at ASC
        LIMIT 1
        """

        try:
            result = self._db.query(sql, tuple(params))
            rows = list(result)

            if not rows:
                return None

            return Task.from_row(dict(rows[0]))

        except DatabaseError as e:
            raise TaskError(f"Failed to get oldest pending task: {e}") from e

    # =========================================================================
    # 辅助方法（已部分实现）
    # =========================================================================

    def _validate_progress(
        self,
        progress_current: int,
        progress_total: int,
    ) -> bool:
        """验证进度值是否有效"""
        if progress_current < 0:
            return False

        if progress_total <= 0:
            return False

        if progress_current > progress_total:
            return False

        return True

    def _calculate_duration(
        self,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
    ) -> Optional[float]:
        """计算时间差（秒）"""
        if start_time is None or end_time is None:
            return None

        try:
            # 转换为时间戳计算差值
            start_timestamp = start_time.timestamp()
            end_timestamp = end_time.timestamp()
            duration = end_timestamp - start_timestamp

            return max(0.0, duration)  # 确保非负

        except (AttributeError, ValueError) as e:
            self._logger.warning(f"Failed to calculate duration: {e}")
            return None