"""
Queue Manager 模块实现

文件：src/reelforge/core/queue_manager.py
接口定义：docs/05-coding/interface-definitions/queue_manager-interface.v1.locked.py

职责：任务队列管理、线程安全调度、状态跟踪
约束：Threading模型，禁用async/await

实现状态：遵循接口定义v1.0，但注意：接口中enqueue方法提到ValidationError，但异常定义中没有ValidationError。
          本实现使用QueueError作为验证错误的基类。
最后更新：2026-04-03
"""

from __future__ import annotations

import queue
import threading
import time
import uuid
from dataclasses import dataclass, field, replace
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

# =============================================================================
# 枚举定义
# =============================================================================

class TaskStatus(Enum):
    """任务状态枚举"""
    QUEUED = auto()      # 已入队，等待处理
    PROCESSING = auto()  # 处理中
    COMPLETED = auto()   # 已完成
    FAILED = auto()      # 失败
    PAUSED = auto()      # 已暂停
    CANCELLED = auto()   # 已取消

# =============================================================================
# 数据模型定义
# =============================================================================

@dataclass
class Task:
    """任务数据模型"""
    task_id: str                     # 任务唯一ID
    project_id: int                  # 关联的项目ID
    task_type: str                   # 任务类型
    status: TaskStatus               # 当前状态
    priority: int = 0                # 优先级（0=最高，数字越大优先级越低）

    # 进度信息
    progress_current: int = 0        # 当前进度
    progress_total: int = 1          # 总进度
    progress_message: str = ""       # 进度消息

    # 时间戳
    created_at: float = 0.0          # 创建时间戳
    started_at: Optional[float] = None  # 开始时间戳
    completed_at: Optional[float] = None  # 完成时间戳

    # 错误信息
    error_code: Optional[str] = None  # 错误代码（E-XXX-XX格式）
    error_message: Optional[str] = None  # 错误消息
    error_stack: Optional[str] = None  # 错误堆栈

    def update_progress(self, current: int, total: int, message: str = "") -> None:
        """更新任务进度"""
        self.progress_current = current
        self.progress_total = total
        if message:
            self.progress_message = message

    def start(self) -> None:
        """标记任务开始"""
        if self.status == TaskStatus.QUEUED:
            self.status = TaskStatus.PROCESSING
            self.started_at = time.time()

    def complete(self) -> None:
        """标记任务完成"""
        if self.status == TaskStatus.PROCESSING:
            self.status = TaskStatus.COMPLETED
            self.completed_at = time.time()
            self.progress_current = self.progress_total
            self.progress_message = "已完成"

    def fail(self, error_code: str, error_message: str, error_stack: Optional[str] = None) -> None:
        """标记任务失败"""
        if self.status in [TaskStatus.QUEUED, TaskStatus.PROCESSING]:
            self.status = TaskStatus.FAILED
            self.completed_at = time.time()
            self.error_code = error_code
            self.error_message = error_message
            self.error_stack = error_stack

    def pause(self) -> None:
        """暂停任务"""
        if self.status == TaskStatus.PROCESSING:
            self.status = TaskStatus.PAUSED

    def resume(self) -> None:
        """恢复任务"""
        if self.status == TaskStatus.PAUSED:
            self.status = TaskStatus.PROCESSING

    def cancel(self) -> None:
        """取消任务"""
        if self.status in [TaskStatus.QUEUED, TaskStatus.PROCESSING, TaskStatus.PAUSED]:
            self.status = TaskStatus.CANCELLED
            self.completed_at = time.time()

# =============================================================================
# 异常定义
# =============================================================================

class QueueError(Exception):
    """队列管理器基础异常"""
    def __init__(self, message: str, original_error: Optional[Exception] = None) -> None:
        super().__init__(message)
        self.message = message
        self.original_error = original_error


class QueueFullError(QueueError):
    """队列已满异常（最大容量：3个任务）"""
    pass


class QueueEmptyError(QueueError):
    """队列为空异常（阻塞超时）"""
    pass


class WorkerDeadError(QueueError):
    """工作线程异常退出"""
    pass


class TaskNotFoundError(QueueError):
    """任务ID不存在"""
    pass


class ValidationError(QueueError):
    """任务参数验证失败异常"""
    pass


# =============================================================================
# 主类实现
# =============================================================================

class QueueManager:
    """
    任务队列管理器

    职责：
        1. 任务入队/出队管理
        2. 线程安全的任务调度
        3. 任务状态跟踪和回调
        4. 工作线程管理

    约束：
        - 最大队列容量：3个任务
        - Threading模型（禁用async/await）
        - 支持暂停/恢复/停止控制
    """

    def __init__(self, max_size: int = 3) -> None:
        """
        初始化队列管理器

        Args:
            max_size: 最大队列容量（默认3个任务）
        """
        self._max_size = max_size
        self._queue: queue.Queue[Task] = queue.Queue(maxsize=max_size)
        self._tasks: Dict[str, Task] = {}  # 任务ID -> 任务对象
        self._callbacks: Dict[str, List[Callable[[Task], None]]] = {}
        self._lock = threading.RLock()  # 可重入锁，用于保护共享状态
        self._worker_thread: Optional[threading.Thread] = None
        self._worker_running = False
        self._worker_paused = False
        self._stop_requested = False

    def enqueue(self, task_dict: Dict[str, Any]) -> str:
        """
        任务入队

        Args:
            task_dict: 任务字典，必须包含 project_id 和 priority

        Returns:
            str: 生成的task_id

        Raises:
            QueueFullError: 队列已满（达到max_size）
            ValidationError: task_dict参数不完整
        """
        # 验证任务参数
        if "project_id" not in task_dict:
            raise ValidationError("task_dict必须包含project_id")
        if "priority" not in task_dict:
            raise ValidationError("task_dict必须包含priority")

        # 生成任务ID
        task_id = str(uuid.uuid4())

        # 创建任务对象
        task = Task(
            task_id=task_id,
            project_id=int(task_dict["project_id"]),
            task_type=str(task_dict.get("task_type", "unknown")),
            status=TaskStatus.QUEUED,
            priority=int(task_dict["priority"]),
            progress_message="等待处理",
            created_at=time.time()
        )

        # 可选字段处理
        if "progress_current" in task_dict:
            task.progress_current = int(task_dict["progress_current"])
        if "progress_total" in task_dict:
            task.progress_total = int(task_dict["progress_total"])
        if "progress_message" in task_dict:
            task.progress_message = str(task_dict["progress_message"])

        with self._lock:
            # 检查队列是否已满
            if self._queue.full():
                raise QueueFullError(f"队列已满，最大容量：{self.max_size}")

            # 存储任务
            self._tasks[task_id] = task

            try:
                # 非阻塞入队（因为已检查队列未满）
                self._queue.put(task, block=False)
            except queue.Full:
                # 理论上不会发生，因为已检查队列未满
                del self._tasks[task_id]
                raise QueueFullError(f"队列已满，最大容量：{self.max_size}")

        return task_id

    def dequeue(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        任务出队（阻塞直到有任务或超时）

        Args:
            timeout: 超时时间（秒），None表示无限等待

        Returns:
            Dict[str, Any]: 任务字典

        Raises:
            QueueEmptyError: 队列为空且超时
        """
        try:
            # 阻塞获取任务
            task = self._queue.get(timeout=timeout)

            with self._lock:
                # 更新任务状态为处理中
                task.start()
                self._tasks[task.task_id] = task

            # 转换为字典返回
            return self._task_to_dict(task)

        except queue.Empty:
            raise QueueEmptyError("队列为空且超时")

    def get_status(self, task_id: str) -> TaskStatus:
        """
        获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            TaskStatus: 任务状态枚举

        Raises:
            TaskNotFoundError: 任务ID不存在
        """
        with self._lock:
            if task_id not in self._tasks:
                raise TaskNotFoundError(f"任务不存在：{task_id}")

            return self._tasks[task_id].status

    def register_callback(self, task_id: str, callback: Callable[[Task], None]) -> None:
        """
        注册任务完成回调

        Args:
            task_id: 任务ID
            callback: 回调函数，接收Task对象作为参数

        Raises:
            TaskNotFoundError: 任务ID不存在
        """
        with self._lock:
            if task_id not in self._tasks:
                raise TaskNotFoundError(f"任务不存在：{task_id}")

            if task_id not in self._callbacks:
                self._callbacks[task_id] = []

            self._callbacks[task_id].append(callback)

    def start_worker(self) -> None:
        """
        启动工作线程

        工作线程职责：
            - 从队列中取出任务
            - 执行任务处理逻辑
            - 更新任务状态
            - 触发回调

        Raises:
            WorkerDeadError: 工作线程异常退出
        """
        with self._lock:
            if self._worker_thread and self._worker_thread.is_alive():
                raise WorkerDeadError("工作线程已在运行")

            if self._worker_running:
                raise WorkerDeadError("工作线程已在运行")

            self._worker_running = True
            self._worker_paused = False
            self._stop_requested = False

            self._worker_thread = threading.Thread(
                target=self._worker_loop,
                name="QueueManager-Worker",
                daemon=True  # 守护线程，主线程退出时自动结束
            )
            self._worker_thread.start()

    def pause(self) -> None:
        """暂停队列处理"""
        with self._lock:
            self._worker_paused = True

    def resume(self) -> None:
        """恢复队列处理"""
        with self._lock:
            self._worker_paused = False

    def stop(self) -> None:
        """停止队列处理（优雅关闭）"""
        with self._lock:
            self._stop_requested = True
            self._worker_running = False

        # 等待工作线程结束
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5.0)

    def list_tasks(self) -> List[Task]:
        """
        列出所有任务

        Returns:
            List[Task]: 任务列表
        """
        with self._lock:
            return list(self._tasks.values())

    def get_task(self, task_id: str) -> Task:
        """
        获取任务详情

        Args:
            task_id: 任务ID

        Returns:
            Task: 任务对象

        Raises:
            TaskNotFoundError: 任务ID不存在
        """
        with self._lock:
            if task_id not in self._tasks:
                raise TaskNotFoundError(f"任务不存在：{task_id}")

            return self._tasks[task_id]

    @property
    def is_running(self) -> bool:
        """检查工作线程是否正在运行"""
        with self._lock:
            return self._worker_running and not self._stop_requested

    @property
    def queue_size(self) -> int:
        """获取当前队列大小"""
        return self._queue.qsize()

    @property
    def max_size(self) -> int:
        """获取队列最大容量"""
        return self._max_size

    # =========================================================================
    # 内部方法
    # =========================================================================

    def _worker_loop(self) -> None:
        """工作线程主循环"""
        while not self._stop_requested:
            try:
                # 检查是否暂停
                if self._worker_paused:
                    time.sleep(0.1)
                    continue

                # 非阻塞获取任务
                try:
                    task = self._queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                # 更新任务状态为处理中
                with self._lock:
                    task.start()
                    self._tasks[task.task_id] = task

                # 处理任务
                self._process_task(task)

                # 标记任务完成
                self._queue.task_done()

            except Exception as e:
                # 捕获所有异常，防止工作线程崩溃
                print(f"工作线程异常：{e}")
                time.sleep(1.0)  # 避免异常循环

        # 清理
        with self._lock:
            self._worker_running = False

    def _process_task(self, task: Task) -> None:
        """处理单个任务（示例实现，应由子类重写）"""
        try:
            # 示例任务处理逻辑
            task.update_progress(0, 100, "开始处理")

            # 模拟处理过程
            for i in range(1, 11):
                if self._worker_paused:
                    # 如果暂停，等待恢复
                    while self._worker_paused and not self._stop_requested:
                        time.sleep(0.1)

                if self._stop_requested:
                    task.cancel()
                    break

                time.sleep(0.1)  # 模拟工作
                task.update_progress(i * 10, 100, f"处理中 {i}/10")

            if task.status != TaskStatus.CANCELLED:
                task.complete()

        except Exception as e:
            # 任务失败
            import traceback
            task.fail(
                error_code="E-999-99",
                error_message=str(e),
                error_stack=traceback.format_exc()
            )

        finally:
            # 触发回调
            self._trigger_callbacks(task)

    def _trigger_callbacks(self, task: Task) -> None:
        """触发任务回调"""
        with self._lock:
            callbacks = self._callbacks.get(task.task_id, [])

        for callback in callbacks:
            try:
                callback(task)
            except Exception as e:
                print(f"回调函数执行失败：{e}")

        # 清理回调列表
        with self._lock:
            if task.task_id in self._callbacks:
                del self._callbacks[task.task_id]

    def _task_to_dict(self, task: Task) -> Dict[str, Any]:
        """将Task对象转换为字典"""
        return {
            "task_id": task.task_id,
            "project_id": task.project_id,
            "task_type": task.task_type,
            "status": task.status,
            "priority": task.priority,
            "progress_current": task.progress_current,
            "progress_total": task.progress_total,
            "progress_message": task.progress_message,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "error_code": task.error_code,
            "error_message": task.error_message,
            "error_stack": task.error_stack,
        }

    def _validate_task_dict(self, task_dict: Dict[str, Any]) -> None:
        """验证任务字典（内部方法）"""
        required_fields = ["project_id", "priority"]
        missing = [field for field in required_fields if field not in task_dict]

        if missing:
            raise ValidationError(f"缺少必填字段：{missing}")


# =============================================================================
# 导出列表
# =============================================================================

__all__ = [
    # 枚举
    "TaskStatus",
    # 数据模型
    "Task",
    # 异常
    "QueueError",
    "QueueFullError",
    "QueueEmptyError",
    "WorkerDeadError",
    "TaskNotFoundError",
    "ValidationError",
    # 主类
    "QueueManager",
]