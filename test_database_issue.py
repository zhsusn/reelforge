#!/usr/bin/env python3
"""
Database类问题调试
"""

import tempfile
import os
import sqlite3
from pathlib import Path

# 导入模块
from reelforge.models.database import Database


def test_database_direct() -> None:
    """直接测试Database类"""
    print("直接测试Database类...")

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        # 创建简单表
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_table (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

        # 测试Database类
        db = Database(Path(db_path))
        db.connect()

        # 测试插入
        affected = db.execute("INSERT INTO test_table (name) VALUES (?)", ("测试1",))
        print(f"第一次插入受影响行数: {affected}")

        # 测试查询last_insert_rowid
        result = db.query("SELECT last_insert_rowid() as id", ())
        rows = list(result)
        print(f"查询last_insert_rowid结果: {len(rows)} 行")
        if rows:
            print(f"last_insert_rowid值: {rows[0]['id']}")

        # 查询实际插入的数据
        result = db.query("SELECT * FROM test_table", ())
        inserted = list(result)
        print(f"查询test_table结果: {len(inserted)} 行")
        for row in inserted:
            print(f"  id={row['id']}, name={row['name']}")

        # 第二次插入
        affected = db.execute("INSERT INTO test_table (name) VALUES (?)", ("测试2",))
        print(f"\n第二次插入受影响行数: {affected}")

        # 再次查询last_insert_rowid
        result = db.query("SELECT last_insert_rowid() as id", ())
        rows = list(result)
        print(f"第二次查询last_insert_rowid结果: {len(rows)} 行")
        if rows:
            print(f"第二次last_insert_rowid值: {rows[0]['id']}")

        # 查询所有数据
        result = db.query("SELECT * FROM test_table ORDER BY id", ())
        all_data = list(result)
        print(f"\n所有数据: {len(all_data)} 行")
        for row in all_data:
            print(f"  id={row['id']}, name={row['name']}")

        db.close()

    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_sqlite3_direct() -> None:
    """直接使用sqlite3测试"""
    print("\n直接使用sqlite3测试...")

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 创建表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_table (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL
            )
        """)

        # 插入数据
        cursor.execute("INSERT INTO test_table (name) VALUES (?)", ("直接测试1",))
        conn.commit()

        # 获取最后插入ID
        cursor.execute("SELECT last_insert_rowid() as id")
        row = cursor.fetchone()
        print(f"直接测试last_insert_rowid: {row[0]}")

        # 查询数据
        cursor.execute("SELECT * FROM test_table")
        rows = cursor.fetchall()
        print(f"直接测试查询结果: {len(rows)} 行")
        for row in rows:
            print(f"  id={row[0]}, name={row[1]}")

        conn.close()

    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def main() -> None:
    """主函数"""
    print("=" * 60)
    print("Database类问题调试")
    print("=" * 60)

    test_database_direct()
    test_sqlite3_direct()

    print("\n" + "=" * 60)
    print("调试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()