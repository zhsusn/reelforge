"""
文件：__tests__/test_queue_manager.py
职责：Queue Manager 模块单元测试（覆盖率 > 80%）
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

import pytest

import sys
sys.path.insert(0, "src")

from reelforge.core.queue_manager import (
    QueueManager,
    Task,
    TaskStatus,
    QueueError,
    QueueFullError,
    QueueEmptyError,
    WorkerDeadError,
    TaskNotFoundError,
    ValidationError,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def queue_manager() -> QueueManager:
    """提供 QueueManager 实例（默认容量3）"""
    return QueueManager(max_size=3)


@pytest.fixture
def small_queue() -> QueueManager:
    """提供小容量队列（容量1）"""
    return QueueManager(max_size=1)


@pytest.fixture
def valid_task_dict() -> Dict[str, Any]:
    """提供有效的任务字典"""
    return {
        "project_id": 123,
        "priority": 0,
        "task_type": "render",
        "progress_current": 0,
        "progress_total": 100,
        "progress_message": "准备开始"
    }


# =============================================================================
# Test Task Model
# =============================================================================

class TestTaskModel:
    """测试 Task 数据模型"""

    def test_task_creation(self) -> None:
        """测试创建 Task 对象"""
        task = Task(
            task_id="test-123",
            project_id=123,
            task_type="render",
            status=TaskStatus.QUEUED,
            priority=0,
            progress_current=0,
            progress_total=100,
            progress_message="准备开始",
            created_at=time.time(),
            started_at=None,
            completed_at=None
        )

        assert task.task_id == "test-123"
        assert task.project_id == 123
        assert task.task_type == "render"
        assert task.status == TaskStatus.QUEUED
        assert task.priority == 0
        assert task.progress_current == 0
        assert task.progress_total == 100
        assert task.progress_message == "准备开始"

    def test_task_update_progress(self) -> None:
        """测试更新进度"""
        task = Task(
            task_id="test-123",
            project_id=123,
            task_type="render",
            status=TaskStatus.PROCESSING
        )

        task.update_progress(50, 100, "处理中")
        assert task.progress_current == 50
        assert task.progress_total == 100
        assert task.progress_message == "处理中"

    def test_task_start(self) -> None:
        """测试任务开始"""
        task = Task(
            task_id="test-123",
            project_id=123,
            task_type="render",
            status=TaskStatus.QUEUED
        )

        original_time = time.time()
        task.start()

        assert task.status == TaskStatus.PROCESSING
        assert task.started_at is not None
        assert task.started_at >= original_time

    def test_task_complete(self) -> None:
        """测试任务完成"""
        task = Task(
            task_id="test-123",
            project_id=123,
            task_type="render",
            status=TaskStatus.PROCESSING,
            progress_current=50,
            progress_total=100,
            progress_message="处理中"
        )

        original_time = time.time()
        task.complete()

        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None
        assert task.completed_at >= original_time
        assert task.progress_current == task.progress_total
        assert task.progress_message == "已完成"

    def test_task_fail(self) -> None:
        """测试任务失败"""
        task = Task(
            task_id="test-123",
            project_id=123,
            task_type="render",
            status=TaskStatus.PROCESSING
        )

        original_time = time.time()
        error_code = "E-999-99"
        error_message = "渲染失败"
        error_stack = "Traceback..."

        task.fail(error_code, error_message, error_stack)

        assert task.status == TaskStatus.FAILED
        assert task.completed_at is not None
        assert task.completed_at >= original_time
        assert task.error_code == error_code
        assert task.error_message == error_message
        assert task.error_stack == error_stack

    def test_task_pause_resume(self) -> None:
        """测试任务暂停和恢复"""
        task = Task(
            task_id="test-123",
            project_id=123,
            task_type="render",
            status=TaskStatus.PROCESSING
        )

        task.pause()
        assert task.status == TaskStatus.PAUSED

        task.resume()
        assert task.status == TaskStatus.PROCESSING

    def test_task_cancel(self) -> None:
        """测试任务取消"""
        task = Task(
            task_id="test-123",
            project_id=123,
            task_type="render",
            status=TaskStatus.QUEUED
        )

        original_time = time.time()
        task.cancel()

        assert task.status == TaskStatus.CANCELLED
        assert task.completed_at is not None
        assert task.completed_at >= original_time


# =============================================================================
# Test TaskStatus Enum
# =============================================================================

class TestTaskStatusEnum:
    """测试 TaskStatus 枚举"""

    def test_enum_values(self) -> None:
        """测试枚举值"""
        assert TaskStatus.QUEUED.value == 1
        assert TaskStatus.PROCESSING.value == 2
        assert TaskStatus.COMPLETED.value == 3
        assert TaskStatus.FAILED.value == 4
        assert TaskStatus.PAUSED.value == 5
        assert TaskStatus.CANCELLED.value == 6

    def test_enum_names(self) -> None:
        """测试枚举名称"""
        assert TaskStatus.QUEUED.name == "QUEUED"
        assert TaskStatus.PROCESSING.name == "PROCESSING"
        assert TaskStatus.COMPLETED.name == "COMPLETED"
        assert TaskStatus.FAILED.name == "FAILED"
        assert TaskStatus.PAUSED.name == "PAUSED"
        assert TaskStatus.CANCELLED.name == "CANCELLED"


# =============================================================================
# Test Exceptions
# =============================================================================

class TestExceptions:
    """测试异常体系"""

    def test_queue_error_with_original(self) -> None:
        """测试 QueueError 包装原始异常"""
        original = ValueError("original error")
        err = QueueError("queue error", original)

        assert err.message == "queue error"
        assert err.original_error is original

    def test_exception_inheritance(self) -> None:
        """测试异常继承关系"""
        assert issubclass(QueueFullError, QueueError)
        assert issubclass(QueueEmptyError, QueueError)
        assert issubclass(WorkerDeadError, QueueError)
        assert issubclass(TaskNotFoundError, QueueError)
        assert issubclass(ValidationError, QueueError)


# =============================================================================
# Test QueueManager Initialization
# =============================================================================

class TestQueueManagerInitialization:
    """测试 QueueManager 初始化"""

    def test_init_default_size(self) -> None:
        """测试默认容量初始化"""
        qm = QueueManager()
        assert qm.max_size == 3
        assert qm.queue_size == 0
        assert not qm.is_running

    def test_init_custom_size(self) -> None:
        """测试自定义容量初始化"""
        qm = QueueManager(max_size=5)
        assert qm.max_size == 5
        assert qm.queue_size == 0

    def test_init_properties(self) -> None:
        """测试属性访问"""
        qm = QueueManager(max_size=3)
        assert qm.max_size == 3
        assert qm.queue_size == 0
        assert not qm.is_running


# =============================================================================
# Test Task Enqueue
# =============================================================================

class TestTaskEnqueue:
    """测试任务入队"""

    def test_enqueue_valid(self, queue_manager: QueueManager, valid_task_dict: Dict[str, Any]) -> None:
        """测试有效任务入队"""
        task_id = queue_manager.enqueue(valid_task_dict)

        assert isinstance(task_id, str)
        assert len(task_id) > 0  # UUID应该非空

        # 验证任务已存储
        task = queue_manager.get_task(task_id)
        assert task.task_id == task_id
        assert task.project_id == 123
        assert task.task_type == "render"
        assert task.status == TaskStatus.QUEUED
        assert task.priority == 0
        assert task.progress_message == "准备开始"

    def test_enqueue_missing_project_id(self, queue_manager: QueueManager) -> None:
        """测试缺少project_id"""
        invalid_dict = {"priority": 0}

        with pytest.raises(ValidationError) as exc_info:
            queue_manager.enqueue(invalid_dict)

        assert "project_id" in str(exc_info.value)

    def test_enqueue_missing_priority(self, queue_manager: QueueManager) -> None:
        """测试缺少priority"""
        invalid_dict = {"project_id": 123}

        with pytest.raises(ValidationError) as exc_info:
            queue_manager.enqueue(invalid_dict)

        assert "priority" in str(exc_info.value)

    def test_enqueue_queue_full(self, small_queue: QueueManager) -> None:
        """测试队列已满"""
        valid_dict = {"project_id": 123, "priority": 0}

        # 第一个任务应该成功
        task_id1 = small_queue.enqueue(valid_dict)
        assert isinstance(task_id1, str)

        # 第二个任务应该失败（容量为1）
        with pytest.raises(QueueFullError):
            small_queue.enqueue(valid_dict)

    def test_enqueue_multiple_tasks(self, queue_manager: QueueManager) -> None:
        """测试多个任务入队"""
        tasks = []
        for i in range(3):  # 队列容量为3
            task_dict = {"project_id": i, "priority": i}
            task_id = queue_manager.enqueue(task_dict)
            tasks.append(task_id)

        # 所有任务都应该成功
        assert len(tasks) == 3
        assert len(set(tasks)) == 3  # 所有task_id应该不同

        # 第四个任务应该失败
        with pytest.raises(QueueFullError):
            queue_manager.enqueue({"project_id": 4, "priority": 0})

    def test_enqueue_with_optional_fields(self, queue_manager: QueueManager) -> None:
        """测试带可选字段的任务入队"""
        task_dict = {
            "project_id": 123,
            "priority": 1,
            "task_type": "special",
            "progress_current": 10,
            "progress_total": 200,
            "progress_message": "已部分完成"
        }

        task_id = queue_manager.enqueue(task_dict)
        task = queue_manager.get_task(task_id)

        assert task.task_type == "special"
        assert task.priority == 1
        assert task.progress_current == 10
        assert task.progress_total == 200
        assert task.progress_message == "已部分完成"


# =============================================================================
# Test Task Management
# =============================================================================

class TestTaskManagement:
    """测试任务管理"""

    def test_get_task_exists(self, queue_manager: QueueManager, valid_task_dict: Dict[str, Any]) -> None:
        """测试获取存在的任务"""
        task_id = queue_manager.enqueue(valid_task_dict)
        task = queue_manager.get_task(task_id)

        assert task.task_id == task_id
        assert task.project_id == 123

    def test_get_task_not_exists(self, queue_manager: QueueManager) -> None:
        """测试获取不存在的任务"""
        with pytest.raises(TaskNotFoundError):
            queue_manager.get_task("non-existent-id")

    def test_get_status(self, queue_manager: QueueManager, valid_task_dict: Dict[str, Any]) -> None:
        """测试获取任务状态"""
        task_id = queue_manager.enqueue(valid_task_dict)
        status = queue_manager.get_status(task_id)

        assert status == TaskStatus.QUEUED

    def test_get_status_not_exists(self, queue_manager: QueueManager) -> None:
        """测试获取不存在任务的状态"""
        with pytest.raises(TaskNotFoundError):
            queue_manager.get_status("non-existent-id")

    def test_list_tasks_empty(self, queue_manager: QueueManager) -> None:
        """测试空队列的任务列表"""
        tasks = queue_manager.list_tasks()
        assert tasks == []

    def test_list_tasks_multiple(self, queue_manager: QueueManager) -> None:
        """测试多任务列表"""
        task_ids = []
        for i in range(3):
            task_dict = {"project_id": i, "priority": i}
            task_id = queue_manager.enqueue(task_dict)
            task_ids.append(task_id)

        tasks = queue_manager.list_tasks()
        assert len(tasks) == 3

        # 验证任务ID匹配
        listed_ids = {task.task_id for task in tasks}
        assert listed_ids == set(task_ids)


# =============================================================================
# Test Task Dequeue
# =============================================================================

class TestTaskDequeue:
    """测试任务出队"""

    def test_dequeue_with_timeout_empty(self, queue_manager: QueueManager) -> None:
        """测试空队列出队（带超时）"""
        with pytest.raises(QueueEmptyError):
            queue_manager.dequeue(timeout=0.1)

    def test_dequeue_no_timeout_empty(self, queue_manager: QueueManager) -> None:
        """测试空队列出队（无超时）"""
        # 启动一个线程来入队任务
        def enqueue_later() -> None:
            time.sleep(0.2)
            queue_manager.enqueue({"project_id": 123, "priority": 0})

        threading.Thread(target=enqueue_later, daemon=True).start()

        # 应该阻塞直到任务入队
        task_dict = queue_manager.dequeue(timeout=1.0)
        assert task_dict["project_id"] == 123
        assert task_dict["status"] == TaskStatus.PROCESSING

    def test_dequeue_updates_status(self, queue_manager: QueueManager) -> None:
        """测试出队更新任务状态"""
        task_id = queue_manager.enqueue({"project_id": 123, "priority": 0})

        # 验证初始状态
        assert queue_manager.get_status(task_id) == TaskStatus.QUEUED

        # 出队
        task_dict = queue_manager.dequeue(timeout=0.1)

        # 验证状态已更新
        assert task_dict["task_id"] == task_id
        assert task_dict["status"] == TaskStatus.PROCESSING
        assert queue_manager.get_status(task_id) == TaskStatus.PROCESSING

    def test_dequeue_order(self, queue_manager: QueueManager) -> None:
        """测试出队顺序（FIFO）"""
        # 按顺序入队3个任务
        for i in range(3):
            queue_manager.enqueue({"project_id": i, "priority": i})

        # 按顺序出队
        for i in range(3):
            task_dict = queue_manager.dequeue(timeout=0.1)
            assert task_dict["project_id"] == i


# =============================================================================
# Test Callbacks
# =============================================================================

class TestCallbacks:
    """测试回调函数"""

    def test_register_callback(self, queue_manager: QueueManager, valid_task_dict: Dict[str, Any]) -> None:
        """测试注册回调函数"""
        task_id = queue_manager.enqueue(valid_task_dict)

        callback_called = []

        def test_callback(task: Task) -> None:
            callback_called.append(task)

        queue_manager.register_callback(task_id, test_callback)

        # 验证回调已注册（无法直接测试，依赖后续触发）

    def test_register_callback_not_exists(self, queue_manager: QueueManager) -> None:
        """测试为不存在任务注册回调"""
        def test_callback(task: Task) -> None:
            pass

        with pytest.raises(TaskNotFoundError):
            queue_manager.register_callback("non-existent-id", test_callback)


# =============================================================================
# Test Worker Thread
# =============================================================================

class TestWorkerThread:
    """测试工作线程"""

    def test_start_worker(self, queue_manager: QueueManager) -> None:
        """测试启动工作线程"""
        assert not queue_manager.is_running

        queue_manager.start_worker()
        time.sleep(0.1)  # 给线程启动时间

        assert queue_manager.is_running

        queue_manager.stop()

    def test_start_worker_twice(self, queue_manager: QueueManager) -> None:
        """测试重复启动工作线程"""
        queue_manager.start_worker()
        time.sleep(0.1)

        with pytest.raises(WorkerDeadError):
            queue_manager.start_worker()

        queue_manager.stop()

    def test_stop_worker(self, queue_manager: QueueManager) -> None:
        """测试停止工作线程"""
        queue_manager.start_worker()
        time.sleep(0.1)
        assert queue_manager.is_running

        queue_manager.stop()
        time.sleep(0.1)
        assert not queue_manager.is_running

    def test_pause_resume_worker(self, queue_manager: QueueManager) -> None:
        """测试暂停和恢复工作线程"""
        # 入队一个任务
        queue_manager.enqueue({"project_id": 123, "priority": 0})

        # 启动工作线程
        queue_manager.start_worker()
        time.sleep(0.1)  # 让工作线程开始运行

        # 暂停（工作线程已经在运行）
        queue_manager.pause()
        time.sleep(0.3)  # 确保工作线程检测到暂停状态

        # 恢复
        queue_manager.resume()
        time.sleep(1.0)  # 给处理时间（任务处理需要1秒）

        # 队列应该为空（任务已处理）
        assert queue_manager.queue_size == 0

        queue_manager.stop()

    def test_worker_processes_tasks(self, queue_manager: QueueManager) -> None:
        """测试工作线程处理任务"""
        # 入队一个任务
        task_id = queue_manager.enqueue({"project_id": 123, "priority": 0})

        # 注册回调来验证任务完成
        callback_called = []

        def completion_callback(task: Task) -> None:
            callback_called.append(task)

        queue_manager.register_callback(task_id, completion_callback)

        # 启动工作线程
        queue_manager.start_worker()

        # 等待任务完成（任务处理需要1秒，加上启动时间）
        time.sleep(2.0)

        # 验证回调被调用
        assert len(callback_called) == 1
        callback_task = callback_called[0]
        assert callback_task.task_id == task_id
        assert callback_task.status == TaskStatus.COMPLETED

        queue_manager.stop()


# =============================================================================
# Test Concurrency
# =============================================================================

class TestConcurrency:
    """测试并发操作"""

    def test_concurrent_enqueue(self, queue_manager: QueueManager) -> None:
        """测试并发入队"""
        errors = []
        results = []

        def worker(worker_id: int) -> None:
            try:
                task_id = queue_manager.enqueue({
                    "project_id": worker_id,
                    "priority": worker_id
                })
                results.append((worker_id, task_id))
            except Exception as e:
                errors.append((worker_id, e))

        # 启动多个线程并发入队
        threads = []
        for i in range(10):  # 超过队列容量
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=2.0)

        # 验证：应该有成功和失败的
        assert len(results) <= 3  # 最多成功3个（队列容量）
        assert len(errors) >= 7   # 至少失败7个

        # 验证失败的异常类型
        for _, error in errors:
            assert isinstance(error, QueueFullError)

    def test_thread_safe_get_status(self, queue_manager: QueueManager) -> None:
        """测试线程安全的状态获取"""
        task_id = queue_manager.enqueue({"project_id": 123, "priority": 0})

        errors = []
        results = []

        def worker() -> None:
            try:
                status = queue_manager.get_status(task_id)
                results.append(status)
            except Exception as e:
                errors.append(e)

        # 启动多个线程并发获取状态
        threads = []
        for _ in range(10):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=1.0)

        # 应该没有错误
        assert len(errors) == 0
        assert len(results) == 10
        assert all(status == TaskStatus.QUEUED for status in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])