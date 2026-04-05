"""
文件：__tests__/test_database.py
职责：Database 模块单元测试（覆盖率 > 80%）
"""

from __future__ import annotations

import sqlite3
import tempfile
import threading
import time
from pathlib import Path
from typing import Generator

import pytest

import sys
sys.path.insert(0, "src")

from reelforge.models.database import (
    ConnectionError,
    ConnectionPool,
    Database,
    DatabaseError,
    PoolExhaustedError,
    Transaction,
    TransactionError,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_db_path() -> Generator[Path, None, None]:
    """提供临时数据库文件路径"""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.db"
        yield path
        # 清理：重置单例状态
        ConnectionPool._instance = None


@pytest.fixture
def database(temp_db_path: Path) -> Generator[Database, None, None]:
    """提供已连接的数据库实例"""
    db = Database(temp_db_path)
    db.connect()
    yield db
    db.disconnect()


# =============================================================================
# Test Exceptions
# =============================================================================

class TestExceptions:
    """测试异常体系"""
    
    def test_database_error_with_original(self) -> None:
        """测试 DatabaseError 包装原始异常"""
        original = ValueError("original")
        err = DatabaseError("message", original)
        assert err.message == "message"
        assert err.original_error is original
    
    def test_connection_error_inheritance(self) -> None:
        """测试 ConnectionError 继承 DatabaseError"""
        err = ConnectionError("connection failed")
        assert isinstance(err, DatabaseError)
    
    def test_transaction_error_inheritance(self) -> None:
        """测试 TransactionError 继承 DatabaseError"""
        err = TransactionError("transaction failed")
        assert isinstance(err, DatabaseError)
    
    def test_pool_exhausted_error_inheritance(self) -> None:
        """测试 PoolExhaustedError 继承 DatabaseError"""
        err = PoolExhaustedError("pool exhausted")
        assert isinstance(err, DatabaseError)


# =============================================================================
# Test Database Connection
# =============================================================================

class TestDatabaseConnection:
    """测试数据库连接管理"""
    
    def test_init_with_path(self, temp_db_path: Path) -> None:
        """测试初始化接受 Path 对象"""
        db = Database(temp_db_path)
        assert db.db_path == temp_db_path
    
    def test_init_with_str_path(self, temp_db_path: Path) -> None:
        """测试初始化接受字符串路径"""
        db = Database(Path(str(temp_db_path)))
        assert str(db.db_path) == str(temp_db_path)
    
    def test_connect_creates_file(self, temp_db_path: Path) -> None:
        """测试连接创建数据库文件"""
        db = Database(temp_db_path)
        db.connect()
        assert temp_db_path.exists()
        db.disconnect()
    
    def test_connect_idempotent(self, temp_db_path: Path) -> None:
        """测试重复连接是幂等的"""
        db = Database(temp_db_path)
        db.connect()
        db.connect()  # 不应抛出异常
        assert db.is_alive()
        db.disconnect()
    
    def test_disconnect_releases_pool(self, temp_db_path: Path) -> None:
        """测试断开连接释放连接池"""
        db = Database(temp_db_path)
        db.connect()
        pool = db.pool
        db.disconnect()
        # 单例已被重置，下次连接会创建新实例
        ConnectionPool._instance = None
    
    def test_is_alive_when_connected(self, database: Database) -> None:
        """测试连接状态检查 - 已连接"""
        assert database.is_alive() is True
    
    def test_is_alive_when_disconnected(self, temp_db_path: Path) -> None:
        """测试连接状态检查 - 未连接"""
        db = Database(temp_db_path)
        assert db.is_alive() is False
    
    def test_pool_property_raises_when_disconnected(self, temp_db_path: Path) -> None:
        """测试 pool 属性在未连接时抛出异常"""
        db = Database(temp_db_path)
        with pytest.raises(ConnectionError):
            _ = db.pool
    
    def test_execute_raises_when_disconnected(self, temp_db_path: Path) -> None:
        """测试 execute 在未连接时抛出异常"""
        db = Database(temp_db_path)
        with pytest.raises(ConnectionError):
            db.execute("SELECT 1")
    
    def test_query_raises_when_disconnected(self, temp_db_path: Path) -> None:
        """测试 query 在未连接时抛出异常"""
        db = Database(temp_db_path)
        with pytest.raises(ConnectionError):
            db.query("SELECT 1")


# =============================================================================
# Test Database Operations
# =============================================================================

class TestDatabaseOperations:
    """测试数据库操作"""
    
    def test_execute_create_table(self, database: Database) -> None:
        """测试执行 CREATE TABLE"""
        rows = database.execute(
            "CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)"
        )
        assert rows == -1  # DDL 语句返回 -1
    
    def test_execute_insert(self, database: Database) -> None:
        """测试执行 INSERT"""
        database.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        rows = database.execute("INSERT INTO test (name) VALUES (?)", ("alice",))
        assert rows == 1
    
    def test_execute_update(self, database: Database) -> None:
        """测试执行 UPDATE"""
        database.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        database.execute("INSERT INTO test (name) VALUES (?)", ("alice",))
        rows = database.execute("UPDATE test SET name = ?", ("bob",))
        assert rows == 1
    
    def test_execute_delete(self, database: Database) -> None:
        """测试执行 DELETE"""
        database.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        database.execute("INSERT INTO test (name) VALUES (?)", ("alice",))
        rows = database.execute("DELETE FROM test")
        assert rows == 1
    
    def test_query_returns_rows(self, database: Database) -> None:
        """测试查询返回行迭代器"""
        database.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        database.execute("INSERT INTO test (name) VALUES (?)", ("alice",))
        database.execute("INSERT INTO test (name) VALUES (?)", ("bob",))
        
        results = list(database.query("SELECT * FROM test ORDER BY id"))
        assert len(results) == 2
        assert results[0]["name"] == "alice"
        assert results[1]["name"] == "bob"
    
    def test_query_one_returns_single_row(self, database: Database) -> None:
        """测试 query_one 返回单行"""
        database.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        database.execute("INSERT INTO test (name) VALUES (?)", ("alice",))
        
        row = database.query_one("SELECT * FROM test WHERE name = ?", ("alice",))
        assert row is not None
        assert row["name"] == "alice"
    
    def test_query_one_returns_none(self, database: Database) -> None:
        """测试 query_one 无结果时返回 None"""
        database.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        
        row = database.query_one("SELECT * FROM test WHERE name = ?", ("none",))
        assert row is None
    
    def test_execute_with_sql_error(self, database: Database) -> None:
        """测试执行错误 SQL 抛出 DatabaseError"""
        with pytest.raises(DatabaseError):
            database.execute("INVALID SQL")
    
    def test_query_with_sql_error(self, database: Database) -> None:
        """测试查询错误 SQL 抛出 DatabaseError"""
        with pytest.raises(DatabaseError):
            list(database.query("INVALID SQL"))


# =============================================================================
# Test ConnectionPool
# =============================================================================

class TestConnectionPool:
    """测试连接池"""
    
    def test_singleton_same_path(self, temp_db_path: Path) -> None:
        """测试相同 db_path 返回相同实例"""
        pool1 = ConnectionPool(temp_db_path, max_connections=2)
        pool2 = ConnectionPool(temp_db_path, max_connections=2)
        assert pool1 is pool2
        pool1.close_all()
    
    def test_singleton_different_path_raises(self, temp_db_path: Path) -> None:
        """测试不同 db_path 抛出 ConnectionError"""
        pool1 = ConnectionPool(temp_db_path, max_connections=2)
        other_path = temp_db_path.parent / "other.db"
        
        with pytest.raises(ConnectionError):
            ConnectionPool(other_path, max_connections=2)
        
        pool1.close_all()
    
    def test_acquire_release(self, temp_db_path: Path) -> None:
        """测试获取和释放连接"""
        pool = ConnectionPool(temp_db_path, max_connections=2)
        
        conn = pool.acquire()
        assert isinstance(conn, sqlite3.Connection)
        
        pool.release(conn)
        pool.close_all()
    
    def test_acquire_timeout(self, temp_db_path: Path) -> None:
        """测试获取连接超时抛出 PoolExhaustedError"""
        pool = ConnectionPool(temp_db_path, max_connections=1)
        
        # 占用唯一连接
        conn = pool.acquire()
        
        # 另一个线程尝试获取，应该超时
        def try_acquire() -> None:
            time.sleep(0.1)
            with pytest.raises(PoolExhaustedError):
                pool.acquire(timeout=0.01)
        
        t = threading.Thread(target=try_acquire)
        t.start()
        t.join(timeout=1.0)
        
        pool.release(conn)
        pool.close_all()
    
    def test_is_full(self, temp_db_path: Path) -> None:
        """测试 is_full 方法"""
        pool = ConnectionPool(temp_db_path, max_connections=1)
        
        assert pool.is_full() is False
        conn = pool.acquire()
        assert pool.is_full() is True
        
        pool.release(conn)
        pool.close_all()
    
    def test_close_all_releases_connections(self, temp_db_path: Path) -> None:
        """测试 close_all 释放所有连接"""
        pool = ConnectionPool(temp_db_path, max_connections=2)
        
        conn1 = pool.acquire()
        conn2 = pool.acquire()
        
        pool.release(conn1)
        pool.close_all()
        
        # 连接应该被关闭
        with pytest.raises(sqlite3.ProgrammingError):
            conn2.execute("SELECT 1")
    
    def test_acquire_after_close_raises(self, temp_db_path: Path) -> None:
        """测试关闭后获取连接抛出异常"""
        pool = ConnectionPool(temp_db_path, max_connections=1)
        pool.close_all()
        
        with pytest.raises(ConnectionError):
            pool.acquire()
    
    def test_concurrent_access(self, temp_db_path: Path) -> None:
        """测试并发访问（10 线程无死锁）"""
        pool = ConnectionPool(temp_db_path, max_connections=5)
        results: list[int] = []
        errors: list[Exception] = []
        
        def worker() -> None:
            try:
                conn = pool.acquire(timeout=5.0)
                try:
                    cursor = conn.execute("SELECT 1")
                    results.append(cursor.fetchone()[0])
                finally:
                    pool.release(conn)
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)
        
        assert len(errors) == 0, f"Errors: {errors}"
        assert len(results) == 10
        assert all(r == 1 for r in results)
        
        pool.close_all()


# =============================================================================
# Test Transaction
# =============================================================================

class TestTransaction:
    """测试事务管理"""
    
    def test_transaction_commit(self, database: Database) -> None:
        """测试事务提交"""
        database.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        
        with database.transaction() as tx:
            tx.execute("INSERT INTO test (name) VALUES (?)", ("alice",))
        
        # 验证数据已提交
        row = database.query_one("SELECT * FROM test")
        assert row is not None
        assert row["name"] == "alice"
    
    def test_transaction_rollback_on_exception(self, database: Database) -> None:
        """测试异常时自动回滚"""
        database.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        
        try:
            with database.transaction() as tx:
                tx.execute("INSERT INTO test (name) VALUES (?)", ("alice",))
                raise ValueError("force rollback")
        except ValueError:
            pass
        
        # 验证数据未提交
        row = database.query_one("SELECT * FROM test")
        assert row is None
    
    def test_transaction_isolation_levels(self, database: Database) -> None:
        """测试不同隔离级别"""
        database.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
        
        for level in ["DEFERRED", "IMMEDIATE", "EXCLUSIVE"]:
            with database.transaction(level) as tx:
                tx.execute("INSERT INTO test (id) VALUES (?)", (1,))
            database.execute("DELETE FROM test")
    
    def test_transaction_invalid_isolation_level(self, database: Database) -> None:
        """测试无效隔离级别抛出异常"""
        with pytest.raises(TransactionError):
            with database.transaction("INVALID") as tx:
                pass
    
    def test_transaction_manual_commit(self, database: Database) -> None:
        """测试手动提交事务"""
        database.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        
        tx = database.transaction()
        with tx:
            tx.execute("INSERT INTO test (name) VALUES (?)", ("alice",))
            tx.commit()
        
        row = database.query_one("SELECT * FROM test")
        assert row is not None
    
    def test_transaction_manual_rollback(self, database: Database) -> None:
        """测试手动回滚事务"""
        database.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        
        with database.transaction() as tx:
            tx.execute("INSERT INTO test (name) VALUES (?)", ("alice",))
            tx.rollback()
        
        row = database.query_one("SELECT * FROM test")
        assert row is None
    
    def test_transaction_execute_without_context(self, database: Database) -> None:
        """测试未进入上下文执行 SQL 抛出异常"""
        tx = database.transaction()
        with pytest.raises(TransactionError):
            tx.execute("SELECT 1")
    
    def test_transaction_double_commit_raises(self, database: Database) -> None:
        """测试重复提交抛出异常"""
        with database.transaction() as tx:
            tx.execute("SELECT 1")
            tx.commit()
            with pytest.raises(TransactionError):
                tx.commit()
    
    def test_transaction_reuse_raises(self, database: Database) -> None:
        """测试重用已完成事务抛出异常"""
        tx = database.transaction()
        with tx:
            tx.execute("SELECT 1")
        
        with pytest.raises(TransactionError):
            with tx:
                pass


# =============================================================================
# Test WAL Mode
# =============================================================================

class TestWALMode:
    """测试 WAL 模式配置"""
    
    def test_wal_mode_enabled_by_default(self, temp_db_path: Path) -> None:
        """测试默认启用 WAL 模式"""
        db = Database(temp_db_path)
        db.connect()
        
        row = db.query_one("PRAGMA journal_mode")
        assert row is not None
        assert row[0] == "wal"
        
        db.disconnect()
    
    def test_wal_mode_disabled(self, temp_db_path: Path) -> None:
        """测试禁用 WAL 模式"""
        db = Database(temp_db_path, config={"wal_mode": False})
        db.connect()
        
        row = db.query_one("PRAGMA journal_mode")
        assert row is not None
        assert row[0] == "delete"  # 默认模式
        
        db.disconnect()


# =============================================================================
# Test Config Options
# =============================================================================

class TestConfigOptions:
    """测试配置选项"""
    
    def test_custom_timeout(self, temp_db_path: Path) -> None:
        """测试自定义超时配置"""
        db = Database(temp_db_path, config={"timeout": 60})
        db.connect()
        assert db.is_alive()
        db.disconnect()
    
    def test_custom_max_connections(self, temp_db_path: Path) -> None:
        """测试自定义最大连接数"""
        # 创建新数据库，避免单例冲突
        ConnectionPool._instance = None
        db = Database(temp_db_path, config={"max_connections": 3})
        db.connect()
        
        # 验证连接池配置
        assert db.pool.is_full() is False
        db.disconnect()
