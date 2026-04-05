#!/usr/bin/env python3
"""
Task模块调试脚本
"""

import tempfile
import os
import sqlite3
from pathlib import Path

# 导入模块
from reelforge.models.database import Database
from reelforge.models.task import TaskManager, TaskCreate, TaskType


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
    cursor.execute("INSERT INTO projects (name) VALUES ('测试项目')")

    conn.commit()
    conn.close()


def test_insert() -> None:
    """测试直接插入"""
    print("测试直接插入...")

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        # 创建数据库和表
        create_test_database(db_path)

        # 直接使用sqlite3测试
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 直接插入
        sql = """
        INSERT INTO tasks (
            task_id, project_id, status, task_type, priority,
            progress_current, progress_total,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """

        params = (
            "test-task-001",
            1,
            "queued",
            "excel_parse",
            0,
            0,
            1,
        )

        cursor.execute(sql, params)
        conn.commit()

        # 获取最后插入的ID
        cursor.execute("SELECT last_insert_rowid() as id")
        row = cursor.fetchone()
        print(f"直接插入结果: last_insert_rowid = {row[0]}")

        # 查询插入的记录
        cursor.execute("SELECT id, task_id FROM tasks WHERE id = ?", (row[0],))
        inserted = cursor.fetchone()
        print(f"查询插入记录: id={inserted[0]}, task_id={inserted[1]}")

        conn.close()

    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_with_database_class() -> None:
    """使用Database类测试"""
    print("\n使用Database类测试...")

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        # 创建数据库和表
        create_test_database(db_path)

        # 创建Database实例
        db = Database(Path(db_path))
        db.connect()

        # 测试查询
        result = db.query("SELECT * FROM projects")
        projects = list(result)
        print(f"查询项目表: {len(projects)} 个项目")

        # 测试插入
        sql = """
        INSERT INTO tasks (
            task_id, project_id, status, task_type, priority,
            progress_current, progress_total,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """

        params = (
            "test-task-002",
            1,
            "queued",
            "excel_parse",
            0,
            0,
            1,
        )

        affected = db.execute(sql, params)
        print(f"Database.execute结果: affected rows = {affected}")

        # 测试查询最后插入ID
        result = db.query("SELECT last_insert_rowid() as id", ())
        rows = list(result)
        print(f"查询last_insert_rowid: {rows[0]['id']}")

        # 查询插入的记录
        result = db.query("SELECT id, task_id FROM tasks WHERE id = ?", (rows[0]['id'],))
        inserted = list(result)
        print(f"查询插入记录: id={inserted[0]['id']}, task_id={inserted[0]['task_id']}")

        db.close()

    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_task_manager_create() -> None:
    """测试TaskManager.create方法"""
    print("\n测试TaskManager.create方法...")

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
            external_task_id="test-task-003",
            project_id=1,
            task_type=TaskType.EXCEL_PARSE,
            priority=1,
            progress_total=100
        )

        print(f"准备创建任务: {task_data.external_task_id}")

        try:
            task = manager.create(task_data)
            print(f"✓ 创建任务成功: ID={task.task_id}, 外部ID={task.external_task_id}")

            # 测试通过ID获取任务
            task_by_id = manager.get_by_id(task.task_id)
            print(f"✓ 通过ID获取任务成功: ID={task_by_id.task_id}")

            # 测试通过外部ID获取任务
            task_by_ext = manager.get_by_external_id("test-task-003")
            print(f"✓ 通过外部ID获取任务成功: ID={task_by_ext.task_id}")

        except Exception as e:
            print(f"✗ 创建任务失败: {e}")
            import traceback
            traceback.print_exc()

    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def main() -> None:
    """主调试函数"""
    print("=" * 60)
    print("Task模块调试")
    print("=" * 60)

    test_insert()
    test_with_database_class()
    test_task_manager_create()

    print("\n" + "=" * 60)
    print("调试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()