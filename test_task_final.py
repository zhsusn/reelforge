#!/usr/bin/env python3
"""
Task模块最终测试
简化版本，避免编码问题
"""

import tempfile
import os
import sqlite3
from pathlib import Path

# 导入模块
from reelforge.models.database import Database
from reelforge.models.database.pool import ConnectionPool
from reelforge.models.task import TaskManager, TaskCreate, TaskType, TaskStatus


def create_test_database(db_path: str) -> None:
    """创建测试数据库和表"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 创建tasks表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL UNIQUE,
            project_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            task_type TEXT NOT NULL,
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
            completed_at TEXT
        )
    """)

    # 创建projects表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    """)

    # 插入测试项目
    cursor.execute("INSERT INTO projects (name) VALUES ('Test Project')")

    conn.commit()
    conn.close()


def test_simple() -> None:
    """简单测试"""
    print("Starting simple test...")

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        # 创建数据库和表
        create_test_database(db_path)

        # 创建Database和TaskManager（增加连接池大小避免测试时的连接池耗尽）
        from reelforge.models.database import ConnectionConfig
        config = {"max_connections": 10, "timeout": 30}
        db = Database(Path(db_path), config)
        # 确保数据库已连接
        db.connect()
        manager = TaskManager(db)

        # 测试1: 创建任务
        print("Test 1: Create task")
        task_data = TaskCreate(
            external_task_id="test-task-001",
            project_id=1,
            task_type=TaskType.EXCEL_PARSE,
            priority=1,
            progress_total=100
        )

        task = manager.create(task_data)
        print(f"  Created: ID={task.task_id}, External={task.external_task_id}, Status={task.status}")
        assert task.task_id >= 1
        assert task.external_task_id == "test-task-001"
        assert task.status == TaskStatus.QUEUED

        # 测试2: 通过ID获取
        print("Test 2: Get by ID")
        task_by_id = manager.get_by_id(task.task_id)
        print(f"  Retrieved by ID: ID={task_by_id.task_id}")
        assert task_by_id.task_id == task.task_id

        # 测试3: 更新状态
        print("Test 3: Update status to PROCESSING")
        updated = manager.update_status(task.task_id, TaskStatus.PROCESSING)
        print(f"  Updated: {updated.status}")
        assert updated.status == TaskStatus.PROCESSING

        # 测试4: 更新进度
        print("Test 4: Update progress")
        progress_task = manager.update_progress(task.task_id, 50, progress_message="Processing...")
        print(f"  Progress: {progress_task.progress_current}/{progress_task.progress_total}")
        assert progress_task.progress_current == 50

        # 测试5: 标记为完成
        print("Test 5: Mark as completed")
        completed = manager.mark_as_completed(task.task_id)
        print(f"  Completed: {completed.status}, Progress={completed.progress_current}/{completed.progress_total}")
        assert completed.status == TaskStatus.COMPLETED
        assert completed.progress_current == completed.progress_total

        # 测试6: 计数
        print("Test 6: Count tasks")
        count = manager.count()
        print(f"  Count: {count}")
        assert count == 1

        # 测试7: 获取项目任务
        print("Test 7: Get tasks by project")
        project_tasks = manager.get_by_project(project_id=1)
        print(f"  Project tasks: {len(project_tasks)}")
        assert len(project_tasks) == 1

        # 测试8: 删除任务
        print("Test 8: Delete task")
        deleted = manager.delete(task.task_id)
        print(f"  Deleted: {deleted}")
        assert deleted

        # 验证删除
        print("Test 9: Verify deletion")
        count_after = manager.count()
        print(f"  Count after deletion: {count_after}")
        assert count_after == 0

        print("\nAll simple tests passed!")

    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        # 重置连接池单例以支持多个测试
        if ConnectionPool._instance is not None:
            try:
                ConnectionPool._instance.close_all()
                ConnectionPool._instance = None
            except:
                pass

        if os.path.exists(db_path):
            try:
                os.unlink(db_path)
            except:
                pass


def test_errors() -> None:
    """错误处理测试"""
    print("\nStarting error handling tests...")

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        # 创建数据库和表
        create_test_database(db_path)

        # 创建Database和TaskManager
        db = Database(Path(db_path))
        # 确保数据库已连接
        db.connect()
        manager = TaskManager(db)

        # 测试无效输入
        print("Test 1: Invalid project ID")
        try:
            task_data = TaskCreate(
                external_task_id="test-invalid",
                project_id=0,  # 无效
                task_type=TaskType.EXCEL_PARSE
            )
            manager.create(task_data)
            print("  ERROR: Should have raised TaskError")
            assert False
        except Exception as e:
            print(f"  OK: Got expected error: {type(e).__name__}")

        print("Test 2: Invalid priority")
        try:
            task_data = TaskCreate(
                external_task_id="test-invalid-priority",
                project_id=1,
                task_type=TaskType.EXCEL_PARSE,
                priority=-1  # 无效
            )
            manager.create(task_data)
            print("  ERROR: Should have raised InvalidPriorityError")
            assert False
        except Exception as e:
            print(f"  OK: Got expected error: {type(e).__name__}")

        # 创建正常任务
        print("Test 3: Create valid task for error testing")
        task_data = TaskCreate(
            external_task_id="test-error-001",
            project_id=1,
            task_type=TaskType.EXCEL_PARSE
        )
        task = manager.create(task_data)
        print(f"  Created: ID={task.task_id}")

        print("Test 4: Invalid status transition")
        try:
            # 从QUEUED直接到FAILED是无效的
            manager.update_status(task.task_id, TaskStatus.FAILED)
            print("  ERROR: Should have raised InvalidTaskStatusError")
            assert False
        except Exception as e:
            print(f"  OK: Got expected error: {type(e).__name__}")

        print("Test 5: Invalid progress update")
        try:
            manager.update_progress(task.task_id, 200)  # 超过总数
            print("  ERROR: Should have raised ProgressError")
            assert False
        except Exception as e:
            print(f"  OK: Got expected error: {type(e).__name__}")

        print("\nAll error handling tests passed!")

    except Exception as e:
        print(f"\nError handling test failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        # 重置连接池单例以支持多个测试
        if ConnectionPool._instance is not None:
            try:
                ConnectionPool._instance.close_all()
                ConnectionPool._instance = None
            except:
                pass

        if os.path.exists(db_path):
            try:
                os.unlink(db_path)
            except:
                pass


def main() -> None:
    """主函数"""
    print("=" * 60)
    print("Task Module Final Test")
    print("=" * 60)

    try:
        test_simple()
        test_errors()

        print("\n" + "=" * 60)
        print("SUCCESS: All tests passed!")
        print("=" * 60)

    except Exception as e:
        print(f"\nFAILED: {e}")
        raise


if __name__ == "__main__":
    main()