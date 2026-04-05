"""
Queue Manager 模块接口定义 (Type Spec)
版本：v1.0（已冻结）
项目：ReelForge
文件映射：`core/queue_manager.py`

职责：任务队列管理、线程安全调度、状态跟踪
约束：Threading模型，禁用async/await

状态：🔒 LOCKED (冻结)
锁定日期：2026-04-03
锁定原因：接口定义完整，通过mypy严格检查
验证状态：✅ 类型检查通过 (mypy --strict)

重要：此文件为冻结接口定义，不可修改。如需变更请创建RFC文档。
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
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

# =============================================================================
# 主类接口
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
        raise NotImplementedError

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
        raise NotImplementedError

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
        raise NotImplementedError

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
        raise NotImplementedError

    def register_callback(self, task_id: str, callback: Callable[[Task], None]) -> None:
        """
        注册任务完成回调

        Args:
            task_id: 任务ID
            callback: 回调函数，接收Task对象作为参数

        Raises:
            TaskNotFoundError: 任务ID不存在
        """
        raise NotImplementedError

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
        raise NotImplementedError

    def pause(self) -> None:
        """暂停队列处理"""
        raise NotImplementedError

    def resume(self) -> None:
        """恢复队列处理"""
        raise NotImplementedError

    def stop(self) -> None:
        """停止队列处理（优雅关闭）"""
        raise NotImplementedError

    def list_tasks(self) -> List[Task]:
        """
        列出所有任务

        Returns:
            List[Task]: 任务列表
        """
        raise NotImplementedError

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
        raise NotImplementedError

    @property
    def is_running(self) -> bool:
        """检查工作线程是否正在运行"""
        raise NotImplementedError

    @property
    def queue_size(self) -> int:
        """获取当前队列大小"""
        raise NotImplementedError

    @property
    def max_size(self) -> int:
        """获取队列最大容量"""
        raise NotImplementedError

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
    # 主类
    "QueueManager",
]