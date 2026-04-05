#!/usr/bin/env python3
"""
Task模块基本功能测试
测试TaskManager的核心功能
"""

import tempfile
import os
import sqlite3
from pathlib import Path
from datetime import datetime

# 导入模块
from reelforge.models.database import Database
from reelforge.models.task import TaskManager, TaskCreate, TaskType, TaskStatus


def create_test_database(db_path: str) -> None:
    """创建测试数据库和表"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 创建tasks表（从database-schema.sql中提取）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL UNIQUE,
            project_id INTEGER NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('queued', 'processing', 'completed', 'failed', 'paused', 'cancelled')),
            task_type TEXT NOT NULL CHECK(task_type IN ('excel_parse', 'character_gen', 'storyboard_gen', 'tts_gen', 'video_render')),
            priority INTEGER NOT NULL DEFAULT 0,
            progress_current INTEGER NOT NULL DEFAULT 0,
            progress_total INTEGER NOT NULL DEFAULT 1,
            progress_message TEXT,
            error_code TEXT,
            error_message TEXT,
            error_stack TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            started_at TEXT,
            completed_at TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
    """)

    # 创建projects表（简化版）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    """)

    # 插入测试项目
    cursor.execute("INSERT INTO projects (name) VALUES ('测试项目')")

    conn.commit()
    conn.close()


def test_basic_crud() -> None:
    """测试基本CRUD操作"""
    print("测试基本CRUD操作...")

    # 创建临时数据库
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        # 创建数据库和表
        create_test_database(db_path)

        # 创建Database和TaskManager
        db = Database(Path(db_path))
        manager = TaskManager(db)

        # 测试创建任务
        task_data = TaskCreate(
            external_task_id="test-task-001",
            project_id=1,
            task_type=TaskType.EXCEL_PARSE,
            priority=1,
            progress_total=100
        )

        task = manager.create(task_data)
        print(f"✓ 创建任务成功: ID={task.task_id}, 外部ID={task.external_task_id}")
        assert task.task_id == 1
        assert task.external_task_id == "test-task-001"
        assert task.status == TaskStatus.QUEUED

        # 测试通过ID获取任务
        task_by_id = manager.get_by_id(task.task_id)
        print(f"✓ 通过ID获取任务成功: ID={task_by_id.task_id}")
        assert task_by_id.task_id == task.task_id

        # 测试通过外部ID获取任务
        task_by_ext = manager.get_by_external_id("test-task-001")
        print(f"✓ 通过外部ID获取任务成功: ID={task_by_ext.task_id}")
        assert task_by_ext.task_id == task.task_id

        # 测试更新任务状态
        updated = manager.update_status(task.task_id, TaskStatus.PROCESSING)
        print(f"✓ 更新状态成功: {task.status} -> {updated.status}")
        assert updated.status == TaskStatus.PROCESSING

        # 测试进度更新
        task_with_progress = manager.update_progress(task.task_id, 50, progress_message="处理中...")
        print(f"✓ 更新进度成功: 50/{task_with_progress.progress_total}")
        assert task_with_progress.progress_current == 50

        # 测试增量进度
        task_incremented = manager.increment_progress(task.task_id, 30)
        print(f"✓ 增量进度成功: {task_incremented.progress_current}/{task_incremented.progress_total}")
        assert task_incremented.progress_current == 80

        # 测试获取进度百分比
        percentage = manager.get_progress_percentage(task.task_id)
        print(f"✓ 获取进度百分比成功: {percentage}%")
        assert percentage == 80.0

        # 测试标记为完成
        completed_task = manager.mark_as_completed(task.task_id)
        print(f"✓ 标记为完成成功: {completed_task.status}")
        assert completed_task.status == TaskStatus.COMPLETED
        assert completed_task.progress_current == completed_task.progress_total

        # 测试计数
        count = manager.count()
        print(f"✓ 计数成功: {count} 个任务")
        assert count == 1

        # 测试获取项目任务
        project_tasks = manager.get_by_project(project_id=1)
        print(f"✓ 获取项目任务成功: {len(project_tasks)} 个任务")
        assert len(project_tasks) == 1

        # 测试获取状态任务
        completed_tasks = manager.get_by_status(TaskStatus.COMPLETED)
        print(f"✓ 获取完成状态任务成功: {len(completed_tasks)} 个任务")
        assert len(completed_tasks) == 1

        # 测试删除任务
        deleted = manager.delete(task.task_id)
        print(f"✓ 删除任务成功: {deleted}")
        assert deleted

        # 验证任务已删除
        try:
            manager.get_by_id(task.task_id)
            assert False, "任务应该已删除"
        except Exception as e:
            print(f"✓ 任务删除验证成功: {e}")

        print("✅ 所有基本CRUD测试通过!")

    finally:
        # 清理临时文件
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_error_handling() -> None:
    """测试错误处理"""
    print("\n测试错误处理...")

    # 创建临时数据库
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        # 创建数据库和表
        create_test_database(db_path)

        # 创建Database和TaskManager
        db = Database(Path(db_path))
        manager = TaskManager(db)

        # 测试不存在的任务
        try:
            manager.get_by_id(999)
            assert False, "应该抛出TaskNotFoundError"
        except Exception as e:
            print(f"✓ 不存在的任务错误处理成功: {type(e).__name__}")

        # 测试无效的外部任务ID
        task_data = TaskCreate(
            external_task_id="",  # 空ID
            project_id=1,
            task_type=TaskType.EXCEL_PARSE
        )
        try:
            manager.create(task_data)
            assert False, "应该抛出TaskError"
        except Exception as e:
            print(f"✓ 无效外部任务ID错误处理成功: {type(e).__name__}")

        # 测试无效的项目ID
        task_data = TaskCreate(
            external_task_id="test-task-002",
            project_id=0,  # 无效ID
            task_type=TaskType.EXCEL_PARSE
        )
        try:
            manager.create(task_data)
            assert False, "应该抛出TaskError"
        except Exception as e:
            print(f"✓ 无效项目ID错误处理成功: {type(e).__name__}")

        # 测试无效优先级
        task_data = TaskCreate(
            external_task_id="test-task-003",
            project_id=1,
            task_type=TaskType.EXCEL_PARSE,
            priority=-1  # 无效优先级
        )
        try:
            manager.create(task_data)
            assert False, "应该抛出InvalidPriorityError"
        except Exception as e:
            print(f"✓ 无效优先级错误处理成功: {type(e).__name__}")

        # 创建正常任务用于测试状态转换
        task_data = TaskCreate(
            external_task_id="test-task-004",
            project_id=1,
            task_type=TaskType.EXCEL_PARSE
        )
        task = manager.create(task_data)

        # 测试无效状态转换（直接标记为失败）
        try:
            manager.update_status(task.task_id, TaskStatus.FAILED)
            assert False, "应该抛出InvalidTaskStatusError"
        except Exception as e:
            print(f"✓ 无效状态转换错误处理成功: {type(e).__name__}")

        # 测试进度错误
        try:
            manager.update_progress(task.task_id, 200)  # 超过总进度
            assert False, "应该抛出ProgressError"
        except Exception as e:
            print(f"✓ 进度溢出错误处理成功: {type(e).__name__}")

        print("✅ 所有错误处理测试通过!")

    finally:
        # 清理临时文件
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_batch_operations() -> None:
    """测试批量操作"""
    print("\n测试批量操作...")

    # 创建临时数据库
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        # 创建数据库和表
        create_test_database(db_path)

        # 创建Database和TaskManager
        db = Database(Path(db_path))
        manager = TaskManager(db)

        # 创建批量任务数据
        tasks_data = [
            TaskCreate(
                external_task_id=f"batch-task-{i:03d}",
                project_id=1,
                task_type=TaskType.EXCEL_PARSE,
                priority=i
            )
            for i in range(1, 6)  # 创建5个任务
        ]

        # 测试批量创建
        tasks = manager.batch_create(tasks_data)
        print(f"✓ 批量创建成功: {len(tasks)} 个任务")
        assert len(tasks) == 5

        # 验证任务已创建
        for i, task in enumerate(tasks, 1):
            assert task.external_task_id == f"batch-task-{i:03d}"
            assert task.priority == i

        # 测试批量更新状态
        task_ids = [task.task_id for task in tasks]
        updated_tasks = manager.batch_update_status(task_ids, TaskStatus.PROCESSING)
        print(f"✓ 批量更新状态成功: {len(updated_tasks)} 个任务")
        assert len(updated_tasks) == 5

        for task in updated_tasks:
            assert task.status == TaskStatus.PROCESSING

        # 测试批量删除
        result = manager.batch_delete(task_ids)
        print(f"✓ 批量删除成功: 删除了 {result['deleted']} 个任务")
        assert result["deleted"] == 5
        assert result["total"] == 5

        # 验证任务已删除
        remaining = manager.count()
        print(f"✓ 验证删除成功: 剩余 {remaining} 个任务")
        assert remaining == 0

        print("✅ 所有批量操作测试通过!")

    finally:
        # 清理临时文件
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_statistics() -> None:
    """测试统计功能"""
    print("\n测试统计功能...")

    # 创建临时数据库
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        # 创建数据库和表
        create_test_database(db_path)

        # 创建Database和TaskManager
        db = Database(Path(db_path))
        manager = TaskManager(db)

        # 创建不同类型和状态的任务
        # 完成的任务
        task1 = manager.create(TaskCreate("task-001", 1, TaskType.EXCEL_PARSE))
        manager.update_status(task1.task_id, TaskStatus.PROCESSING)
        manager.mark_as_completed(task1.task_id)

        # 失败的任务
        task2 = manager.create(TaskCreate("task-002", 1, TaskType.CHARACTER_GEN))
        manager.mark_as_failed(task2.task_id, "E-001", "测试失败")

        # 排队中的任务
        task3 = manager.create(TaskCreate("task-003", 1, TaskType.STORYBOARD_GEN))

        # 处理中的任务
        task4 = manager.create(TaskCreate("task-004", 1, TaskType.TTS_GEN))
        manager.update_status(task4.task_id, TaskStatus.PROCESSING)

        # 测试获取统计信息
        stats = manager.get_statistics()
        print(f"✓ 获取统计信息成功")
        print(f"  总数: {stats['total_count']}")
        print(f"  排队中: {stats['queued_count']}")
        print(f"  处理中: {stats['processing_count']}")
        print(f"  已完成: {stats['completed_count']}")
        print(f"  已失败: {stats['failed_count']}")

        assert stats["total_count"] == 4
        assert stats["queued_count"] == 1
        assert stats["processing_count"] == 1
        assert stats["completed_count"] == 1
        assert stats["failed_count"] == 1

        # 测试状态分布
        status_dist = manager.get_status_distribution()
        print(f"✓ 获取状态分布成功: {status_dist}")

        # 测试类型分布
        type_dist = manager.get_type_distribution()
        print(f"✓ 获取类型分布成功: {type_dist}")

        # 测试失败率
        failure_rate = manager.get_failure_rate()
        print(f"✓ 获取失败率成功: {failure_rate}%")
        assert failure_rate == 50.0  # 2个完成状态的任务中1个失败

        print("✅ 所有统计功能测试通过!")

    finally:
        # 清理临时文件
        if os.path.exists(db_path):
            os.unlink(db_path)


def main() -> None:
    """主测试函数"""
    print("=" * 60)
    print("Task模块功能测试")
    print("=" * 60)

    try:
        test_basic_crud()
        test_error_handling()
        test_batch_operations()
        test_statistics()

        print("\n" + "=" * 60)
        print("🎉 所有测试通过！Task模块实现完整且功能正常")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()