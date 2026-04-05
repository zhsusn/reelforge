#!/usr/bin/env python3
"""
Shot模块调试测试
调试batch_create问题
"""

import tempfile
import os
import sqlite3
from pathlib import Path

# 导入模块
from reelforge.models.database import Database
from reelforge.models.database.pool import ConnectionPool
from reelforge.models.shot import ShotManager, ShotCreate, ShotUpdate, ShotStatus


def create_test_database(db_path: str) -> None:
    """创建测试数据库和表"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 创建shots表（从docs/02-architecture/database-schema.sql复制）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            script_line_id INTEGER,
            sequence INTEGER NOT NULL,
            scene_description TEXT NOT NULL,
            dialogue TEXT NOT NULL,
            emotion TEXT NOT NULL,
            camera_movement TEXT,
            shot_type TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            generated_image_path TEXT,
            tts_audio_path TEXT,
            actual_duration REAL,
            subtitle_start REAL,
            subtitle_end REAL,
            similarity_score REAL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CHECK (sequence > 0),
            CHECK (actual_duration IS NULL OR actual_duration > 0),
            CHECK (similarity_score IS NULL OR (similarity_score >= 0 AND similarity_score <= 100)),
            UNIQUE(project_id, sequence)
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
    cursor.execute("INSERT INTO projects (name) VALUES ('Another Project')")

    conn.commit()
    conn.close()


def test_simple_batch_create() -> None:
    """简单批量创建测试"""
    print("Starting simple batch create test...")

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        # 创建数据库和表
        create_test_database(db_path)

        # 创建Database和ShotManager（增加连接池大小避免测试时的连接池耗尽）
        config = {"max_connections": 10, "timeout": 30}
        db = Database(Path(db_path), config)
        # 确保数据库已连接
        db.connect()
        manager = ShotManager(db)

        # 先创建一个单独的分镜来验证数据库连接正常
        print("Test 1: Create single shot")
        shot_data = ShotCreate(
            project_id=1,
            sequence=1,
            scene_description="Single scene",
            dialogue="Single dialogue",
            emotion="happy"
        )
        single_shot = manager.create(shot_data)
        print(f"  Created single: ID={single_shot.shot_id}")

        # 测试2: 创建第一个批量（使用不同序号）
        print("\nTest 2: Batch create with different sequences")
        shots_data = [
            ShotCreate(
                project_id=1,
                sequence=10,
                scene_description="Scene 10",
                dialogue="Dialogue 10",
                emotion="happy"
            ),
            ShotCreate(
                project_id=1,
                sequence=11,
                scene_description="Scene 11",
                dialogue="Dialogue 11",
                emotion="sad"
            ),
            ShotCreate(
                project_id=2,  # 不同项目
                sequence=1,
                scene_description="Scene in project 2",
                dialogue="Dialogue in project 2",
                emotion="neutral"
            )
        ]

        try:
            created_shots = manager.batch_create(shots_data)
            print(f"  Batch created: {len(created_shots)} shots")
            for shot in created_shots:
                print(f"    - ID={shot.shot_id}, Project={shot.project_id}, Sequence={shot.sequence}")

            # 验证创建的分镜
            assert len(created_shots) == 3

            # 检查计数
            count1 = manager.count(project_id=1)
            count2 = manager.count(project_id=2)
            print(f"  Count project 1: {count1}, project 2: {count2}")
            assert count1 == 3  # 1个单独 + 2个批量
            assert count2 == 1

            print("  Batch create succeeded!")
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
            raise

        # 测试3: 创建重复序号（应该失败）
        print("\nTest 3: Batch create with duplicate sequence (should fail)")
        duplicate_shots = [
            ShotCreate(
                project_id=1,
                sequence=20,
                scene_description="Scene 20",
                dialogue="Dialogue 20",
                emotion="angry"
            ),
            ShotCreate(
                project_id=1,
                sequence=20,  # 重复序号
                scene_description="Scene 20 duplicate",
                dialogue="Dialogue 20 duplicate",
                emotion="excited"
            )
        ]

        try:
            manager.batch_create(duplicate_shots)
            print("  ERROR: Should have raised exception for duplicate sequence")
            assert False
        except Exception as e:
            print(f"  OK: Got expected error: {type(e).__name__}")

        print("\nAll simple batch create tests passed!")

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


def test_db_transaction() -> None:
    """数据库事务测试"""
    print("\nStarting database transaction test...")

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        # 创建数据库和表
        create_test_database(db_path)

        # 创建Database和ShotManager
        config = {"max_connections": 10, "timeout": 30}
        db = Database(Path(db_path), config)
        db.connect()
        manager = ShotManager(db)

        # 测试事务中的批量创建
        print("Test: Batch create in transaction")
        shots_data = [
            ShotCreate(
                project_id=1,
                sequence=100,
                scene_description=f"Scene {100}",
                dialogue=f"Dialogue {100}",
                emotion="happy"
            ),
            ShotCreate(
                project_id=1,
                sequence=101,
                scene_description=f"Scene {101}",
                dialogue=f"Dialogue {101}",
                emotion="sad"
            )
        ]

        created_shots = manager.batch_create(shots_data)
        print(f"  Created {len(created_shots)} shots in transaction")
        assert len(created_shots) == 2

        # 验证数据确实插入
        count = manager.count(project_id=1)
        print(f"  Total shots in project 1: {count}")
        assert count == 2

        # 测试批量更新状态
        print("\nTest: Batch update status in transaction")
        shot_ids = [shot.shot_id for shot in created_shots]
        updated_shots = manager.batch_update_status(shot_ids, ShotStatus.GENERATING)
        print(f"  Updated {len(updated_shots)} shots to GENERATING")
        assert len(updated_shots) == 2
        for shot in updated_shots:
            assert shot.status == ShotStatus.GENERATING

        # 测试批量删除
        print("\nTest: Batch delete in transaction")
        result = manager.batch_delete(shot_ids)
        print(f"  Batch delete result: {result}")
        assert result["total"] == 2
        assert result["deleted"] == 2
        assert result["failed"] == 0

        # 验证删除
        count_after = manager.count(project_id=1)
        print(f"  Shots after delete: {count_after}")
        assert count_after == 0

        print("\nAll database transaction tests passed!")

    except Exception as e:
        print(f"\nTransaction test failed: {e}")
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
    print("Shot Module Debug Test")
    print("=" * 60)

    try:
        test_simple_batch_create()
        test_db_transaction()

        print("\n" + "=" * 60)
        print("SUCCESS: All debug tests passed!")
        print("=" * 60)

    except Exception as e:
        print(f"\nFAILED: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()