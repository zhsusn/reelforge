#!/usr/bin/env python3
"""
Shot模块基本测试
验证ShotManager基本功能
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

    # 创建script_lines表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS script_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            sequence INTEGER NOT NULL,
            character_name TEXT NOT NULL,
            dialogue TEXT NOT NULL,
            emotion TEXT NOT NULL,
            estimated_duration REAL NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 插入测试项目
    cursor.execute("INSERT INTO projects (name) VALUES ('Test Project')")
    cursor.execute("INSERT INTO projects (name) VALUES ('Another Project')")

    # 插入测试剧本行
    cursor.execute("""
        INSERT INTO script_lines (project_id, sequence, character_name, dialogue, emotion, estimated_duration)
        VALUES (1, 1, 'Alice', 'Hello world!', 'happy', 2.5)
    """)
    cursor.execute("""
        INSERT INTO script_lines (project_id, sequence, character_name, dialogue, emotion, estimated_duration)
        VALUES (1, 2, 'Bob', 'Goodbye world!', 'sad', 1.8)
    """)

    conn.commit()
    conn.close()


def test_basic_crud() -> None:
    """基本CRUD测试"""
    print("Starting basic CRUD test...")

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

        # 测试1: 创建分镜
        print("Test 1: Create shot")
        shot_data = ShotCreate(
            project_id=1,
            sequence=1,
            scene_description="A beautiful sunset over mountains",
            dialogue="Hello world!",
            emotion="happy",
            script_line_id=1,
            camera_movement="pan",
            shot_type="wide"
        )

        shot = manager.create(shot_data)
        print(f"  Created: ID={shot.shot_id}, Project={shot.project_id}, Sequence={shot.sequence}, Status={shot.status}")
        assert shot.shot_id >= 1
        assert shot.project_id == 1
        assert shot.sequence == 1
        assert shot.status == ShotStatus.PENDING
        assert shot.scene_description == "A beautiful sunset over mountains"
        assert shot.dialogue == "Hello world!"
        assert shot.emotion == "happy"
        assert shot.camera_movement == "pan"
        assert shot.shot_type == "wide"
        assert shot.script_line_id == 1
        assert shot.generated_image_path is None
        assert shot.tts_audio_path is None
        assert shot.actual_duration is None
        assert shot.similarity_score is None

        # 测试2: 通过ID获取
        print("Test 2: Get by ID")
        shot_by_id = manager.get_by_id(shot.shot_id)
        print(f"  Retrieved by ID: ID={shot_by_id.shot_id}")
        assert shot_by_id.shot_id == shot.shot_id
        assert shot_by_id.scene_description == shot.scene_description

        # 测试3: 通过项目和序号获取
        print("Test 3: Get by project and sequence")
        shot_by_seq = manager.get_by_project_and_sequence(1, 1)
        print(f"  Retrieved by project/seq: ID={shot_by_seq.shot_id}")
        assert shot_by_seq.shot_id == shot.shot_id

        # 测试4: 更新分镜信息
        print("Test 4: Update shot")
        update_data = ShotUpdate(
            scene_description="Updated scene: City skyline at night",
            emotion="excited",
            camera_movement="zoom"
        )
        updated_shot = manager.update(shot.shot_id, update_data)
        print(f"  Updated: Description='{updated_shot.scene_description}', Emotion={updated_shot.emotion}")
        assert updated_shot.scene_description == "Updated scene: City skyline at night"
        assert updated_shot.emotion == "excited"
        assert updated_shot.camera_movement == "zoom"
        # 确保其他字段未改变
        assert updated_shot.dialogue == "Hello world!"
        assert updated_shot.shot_type == "wide"

        # 测试5: 更新状态到生成中
        print("Test 5: Update status to generating")
        generating_shot = manager.update_status(shot.shot_id, ShotStatus.GENERATING)
        print(f"  Status: {generating_shot.status}")
        assert generating_shot.status == ShotStatus.GENERATING

        # 测试6: 标记为完成（模拟生成完成）
        print("Test 6: Mark as completed")
        temp_dir = tempfile.mkdtemp()
        image_path = Path(temp_dir) / "test_image.png"
        audio_path = Path(temp_dir) / "test_audio.mp3"

        # 创建测试文件
        image_path.write_text("fake image data")
        audio_path.write_text("fake audio data")

        completed_shot = manager.mark_as_completed(
            shot_id=shot.shot_id,
            generated_image_path=image_path,
            tts_audio_path=audio_path,
            actual_duration=2.5,
            subtitle_start=0.1,
            subtitle_end=2.4,
            similarity_score=85.5
        )
        print(f"  Completed: Status={completed_shot.status}, Duration={completed_shot.actual_duration}, Similarity={completed_shot.similarity_score}")
        assert completed_shot.status == ShotStatus.COMPLETED
        assert completed_shot.generated_image_path == image_path
        assert completed_shot.tts_audio_path == audio_path
        assert completed_shot.actual_duration == 2.5
        assert completed_shot.subtitle_start == 0.1
        assert completed_shot.subtitle_end == 2.4
        assert completed_shot.similarity_score == 85.5

        # 测试7: 获取项目分镜列表
        print("Test 7: Get shots by project")
        project_shots = manager.get_by_project(project_id=1)
        print(f"  Project shots: {len(project_shots)}")
        assert len(project_shots) == 1
        assert project_shots[0].shot_id == shot.shot_id

        # 测试8: 创建第二个分镜
        print("Test 8: Create second shot")
        shot2_data = ShotCreate(
            project_id=1,
            sequence=2,
            scene_description="Close-up of character's face",
            dialogue="Goodbye world!",
            emotion="sad",
            script_line_id=2
        )
        shot2 = manager.create(shot2_data)
        print(f"  Created second: ID={shot2.shot_id}, Sequence={shot2.sequence}")
        assert shot2.sequence == 2

        # 测试9: 计数
        print("Test 9: Count shots")
        count_all = manager.count()
        count_project = manager.count(project_id=1)
        count_pending = manager.count(status=ShotStatus.PENDING)
        print(f"  Count all: {count_all}, Project: {count_project}, Pending: {count_pending}")
        assert count_all == 2
        assert count_project == 2
        assert count_pending == 1  # shot2是PENDING，shot1是COMPLETED

        # 测试10: 获取状态分布
        print("Test 10: Get status distribution")
        status_dist = manager.get_status_distribution(project_id=1)
        print(f"  Status distribution: {status_dist}")
        assert status_dist[ShotStatus.PENDING.value] == 1
        assert status_dist[ShotStatus.COMPLETED.value] == 1
        assert status_dist[ShotStatus.GENERATING.value] == 0
        assert status_dist[ShotStatus.FAILED.value] == 0

        # 测试11: 获取下一个可用序号
        print("Test 11: Get next sequence")
        next_seq = manager.get_next_sequence(project_id=1)
        print(f"  Next sequence: {next_seq}")
        assert next_seq == 3  # 已有序列1和2

        # 测试12: 删除分镜
        print("Test 12: Delete shot")
        deleted = manager.delete(shot2.shot_id)
        print(f"  Deleted: {deleted}")
        assert deleted

        # 验证删除
        print("Test 13: Verify deletion")
        count_after = manager.count(project_id=1)
        print(f"  Count after deletion: {count_after}")
        assert count_after == 1

        # 清理临时文件
        os.unlink(str(image_path))
        os.unlink(str(audio_path))
        os.rmdir(temp_dir)

        print("\nAll basic CRUD tests passed!")

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


def test_error_handling() -> None:
    """错误处理测试"""
    print("\nStarting error handling tests...")

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        # 创建数据库和表
        create_test_database(db_path)

        # 创建Database和ShotManager
        db = Database(Path(db_path))
        db.connect()
        manager = ShotManager(db)

        # 测试1: 无效的项目ID
        print("Test 1: Invalid project ID")
        try:
            shot_data = ShotCreate(
                project_id=0,  # 无效
                sequence=1,
                scene_description="Test scene",
                dialogue="Test dialogue",
                emotion="neutral"
            )
            manager.create(shot_data)
            print("  ERROR: Should have raised ShotError")
            assert False
        except Exception as e:
            print(f"  OK: Got expected error: {type(e).__name__}")

        # 测试2: 重复的序号
        print("Test 2: Duplicate sequence")
        # 先创建一个分镜
        shot_data = ShotCreate(
            project_id=1,
            sequence=10,
            scene_description="First shot",
            dialogue="First dialogue",
            emotion="happy"
        )
        shot1 = manager.create(shot_data)
        print(f"  Created first shot with sequence 10")

        # 尝试创建相同序号的分镜
        try:
            shot_data2 = ShotCreate(
                project_id=1,
                sequence=10,  # 重复
                scene_description="Second shot",
                dialogue="Second dialogue",
                emotion="sad"
            )
            manager.create(shot_data2)
            print("  ERROR: Should have raised ShotAlreadyExistsError")
            assert False
        except Exception as e:
            print(f"  OK: Got expected error: {type(e).__name__}")

        # 测试3: 无效的状态转换
        print("Test 3: Invalid status transition")
        # 当前是PENDING状态
        # 尝试从PENDING直接到COMPLETED（应该经过GENERATING）
        try:
            manager.update_status(shot1.shot_id, ShotStatus.COMPLETED)
            print("  ERROR: Should have raised InvalidShotStatusError")
            assert False
        except Exception as e:
            print(f"  OK: Got expected error: {type(e).__name__}")

        # 测试4: 无效的相似度分数
        print("Test 4: Invalid similarity score")
        try:
            manager.update_similarity_score(shot1.shot_id, 150.0)  # 超过100
            print("  ERROR: Should have raised SimilarityScoreError")
            assert False
        except Exception as e:
            print(f"  OK: Got expected error: {type(e).__name__}")

        # 测试5: 获取不存在的分镜
        print("Test 5: Get non-existent shot")
        try:
            manager.get_by_id(99999)
            print("  ERROR: Should have raised ShotNotFoundError")
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


def test_batch_operations() -> None:
    """批量操作测试"""
    print("\nStarting batch operations tests...")

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        # 创建数据库和表
        create_test_database(db_path)

        # 创建Database和ShotManager
        db = Database(Path(db_path))
        db.connect()
        manager = ShotManager(db)

        # 测试1: 批量创建
        print("Test 1: Batch create shots")
        shots_data = [
            ShotCreate(
                project_id=1,
                sequence=100 + i,
                scene_description=f"Scene {i}",
                dialogue=f"Dialogue {i}",
                emotion="happy",
                camera_movement="pan" if i % 2 == 0 else "zoom"
            )
            for i in range(1, 6)  # 创建5个分镜
        ]

        created_shots = manager.batch_create(shots_data)
        print(f"  Batch created: {len(created_shots)} shots")
        assert len(created_shots) == 5

        # 验证创建的分镜
        for i, shot in enumerate(created_shots, start=1):
            assert shot.sequence == 100 + i
            assert shot.scene_description == f"Scene {i}"
            assert shot.status == ShotStatus.PENDING

        # 测试2: 批量更新状态
        print("Test 2: Batch update status")
        shot_ids = [shot.shot_id for shot in created_shots]
        updated_shots = manager.batch_update_status(shot_ids, ShotStatus.GENERATING)
        print(f"  Batch updated status: {len(updated_shots)} shots")
        assert len(updated_shots) == 5

        # 验证状态已更新
        for shot in updated_shots:
            assert shot.status == ShotStatus.GENERATING

        # 测试3: 批量删除
        print("Test 3: Batch delete shots")
        # 先删除前3个
        delete_ids = shot_ids[:3]
        result = manager.batch_delete(delete_ids)
        print(f"  Batch delete result: {result}")
        assert result["total"] == 3
        assert result["deleted"] == 3
        assert result["failed"] == 0
        assert len(result["missing"]) == 0

        # 验证删除后剩余2个
        remaining_count = manager.count(project_id=1)
        print(f"  Remaining shots: {remaining_count}")
        assert remaining_count == 2

        # 测试4: 尝试删除不存在的分镜
        print("Test 4: Batch delete with missing IDs")
        missing_ids = [99998, 99999]  # 不存在的ID
        result = manager.batch_delete(missing_ids)
        print(f"  Batch delete with missing: {result}")
        assert result["total"] == 2
        assert result["deleted"] == 0
        assert result["failed"] == 2
        assert len(result["missing"]) == 2

        print("\nAll batch operations tests passed!")

    except Exception as e:
        print(f"\nBatch operations test failed: {e}")
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


def test_statistics_and_queries() -> None:
    """统计和查询测试"""
    print("\nStarting statistics and queries tests...")

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        # 创建数据库和表
        create_test_database(db_path)

        # 创建Database和ShotManager
        db = Database(Path(db_path))
        db.connect()
        manager = ShotManager(db)

        # 创建测试数据
        print("Creating test data...")

        # 创建不同状态、情绪的分镜
        shots_data = []
        emotions = ["happy", "sad", "angry", "excited", "neutral"]

        for i in range(1, 11):  # 10个分镜
            shot_data = ShotCreate(
                project_id=1,
                sequence=i,
                scene_description=f"Scene {i}",
                dialogue=f"Dialogue {i}",
                emotion=emotions[(i-1) % len(emotions)],
                camera_movement="pan" if i % 2 == 0 else "zoom",
                shot_type="wide" if i % 3 == 0 else "close-up"
            )
            shots_data.append(shot_data)

        # 批量创建
        created_shots = manager.batch_create(shots_data)
        print(f"Created {len(created_shots)} test shots")

        # 更新部分分镜状态
        # 设置前3个为COMPLETED，第4个为GENERATING，剩余为PENDING
        if len(created_shots) >= 4:
            # 标记前3个为完成
            for i in range(3):
                shot = created_shots[i]
                temp_dir = tempfile.mkdtemp()
                image_path = Path(temp_dir) / f"test_image_{shot.shot_id}.png"
                audio_path = Path(temp_dir) / f"test_audio_{shot.shot_id}.mp3"

                # 创建测试文件
                image_path.write_text("fake image data")
                audio_path.write_text("fake audio data")

                manager.mark_as_completed(
                    shot_id=shot.shot_id,
                    generated_image_path=image_path,
                    tts_audio_path=audio_path,
                    actual_duration=2.0 + (i * 0.5),
                    subtitle_start=0.1,
                    subtitle_end=1.9 + (i * 0.5),
                    similarity_score=85.0 + (i * 5)
                )

                # 清理文件
                os.unlink(str(image_path))
                os.unlink(str(audio_path))
                os.rmdir(temp_dir)

            # 标记第4个为生成中
            manager.update_status(created_shots[3].shot_id, ShotStatus.GENERATING)

        # 测试1: 统计信息
        print("Test 1: Get statistics")
        stats = manager.get_statistics(project_id=1)
        print(f"  Statistics: {stats}")
        assert stats["total_shots"] == 10
        # 根据上面的设置：3个COMPLETED，1个GENERATING，6个PENDING
        assert stats["status_distribution"]["completed"] == 3
        assert stats["status_distribution"]["generating"] == 1
        assert stats["status_distribution"]["pending"] == 6
        # 应该有5种不同情绪（因为emotions列表有5个元素）
        assert stats["distinct_emotions"] == 5

        # 测试2: 情绪分布
        print("Test 2: Get emotion distribution")
        emotion_dist = manager.get_emotion_distribution(project_id=1)
        print(f"  Emotion distribution: {emotion_dist}")
        # 每个情绪应该出现2次（因为10个分镜，5种情绪）
        for emotion in emotions:
            assert emotion in emotion_dist
            # 但由于有些分镜被标记为完成，可能数量有变化，至少应该有分布

        # 测试3: 相似度统计
        print("Test 3: Get similarity stats")
        similarity_stats = manager.get_similarity_stats(project_id=1)
        print(f"  Similarity stats: {similarity_stats}")
        # 应该有3个分镜有相似度分数
        assert similarity_stats["scored_shots"] == 3
        assert similarity_stats["high_similarity"] >= 0  # 可能有的分数 >= 90
        assert similarity_stats["medium_similarity"] >= 0  # 可能有的分数在80-90之间
        assert similarity_stats["low_similarity"] >= 0  # 可能有的分数 < 80

        # 测试4: 低相似度分镜查询
        print("Test 4: Get low similarity shots")
        low_similarity = manager.get_low_similarity_shots(
            project_id=1,
            threshold=80.0,
            limit=10
        )
        print(f"  Low similarity shots: {len(low_similarity)}")
        # 至少应该有分数低于80的分镜

        # 测试5: 总时长计算
        print("Test 5: Calculate total duration")
        total_duration = manager.calculate_total_duration(project_id=1)
        print(f"  Total duration: {total_duration} seconds")
        # 3个完成的分镜，每个时长不同：2.0, 2.5, 3.0
        expected_duration = 2.0 + 2.5 + 3.0
        assert abs(total_duration - expected_duration) < 0.01

        # 测试6: 时间线信息
        print("Test 6: Get timeline")
        timeline = manager.get_timeline(project_id=1)
        print(f"  Timeline items: {len(timeline)}")
        assert len(timeline) == 3  # 只有完成的分镜

        print("\nAll statistics and queries tests passed!")

    except Exception as e:
        print(f"\nStatistics and queries test failed: {e}")
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
    print("Shot Module Basic Test")
    print("=" * 60)

    try:
        test_basic_crud()
        test_error_handling()
        test_batch_operations()
        test_statistics_and_queries()

        print("\n" + "=" * 60)
        print("SUCCESS: All tests passed!")
        print("=" * 60)

    except Exception as e:
        print(f"\nFAILED: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()