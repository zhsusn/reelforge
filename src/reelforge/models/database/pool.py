"""
文件：src/reelforge/modules/database/pool.py
职责：SQLite 连接池实现（线程安全单例）
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from queue import Empty, Full, Queue
from typing import Any, Optional, final

from reelforge.models.database.exceptions import ConnectionError, PoolExhaustedError


@final
class ConnectionPool:
    """SQLite 连接池（线程安全单例）
    
    约束：
        - 最大连接数默认 5，可配置
        - 获取连接超时默认 30 秒
        - 线程安全（threading.Lock 保护）
    """
    
    _instance: Optional[ConnectionPool] = None
    _lock: threading.Lock = threading.Lock()
    
    def __new__(
        cls, 
        db_path: Path, 
        max_connections: int = 5,
        **config: Any
    ) -> ConnectionPool:
        """单例构造器
        
        Args:
            db_path: 数据库文件路径
            max_connections: 最大连接数（1-10）
            **config: 额外配置（超时、WAL 模式等）
            
        Raises:
            ConnectionError: 尝试用不同 db_path 创建第二个实例
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialize(db_path, max_connections, config)
                return cls._instance
            
            if Path(db_path) != cls._instance._db_path:
                raise ConnectionError(
                    f"Cannot create pool for different db_path. "
                    f"Existing: {cls._instance._db_path}, Requested: {db_path}"
                )
            return cls._instance
    
    def _initialize(
        self, 
        db_path: Path, 
        max_connections: int,
        config: dict[str, Any]
    ) -> None:
        """初始化实例属性（仅调用一次）"""
        self._db_path: Path = Path(db_path)
        self._max_connections: int = max(1, min(10, max_connections))
        self._timeout: float = float(config.get("timeout", 30.0))
        self._pool: Queue[sqlite3.Connection] = Queue()
        self._active_connections: set[sqlite3.Connection] = set()
        self._pool_lock: threading.Lock = threading.Lock()
        self._connection_count: int = 0
        self._closed: bool = False
    
    def _create_connection(self) -> sqlite3.Connection:
        """创建新的数据库连接"""
        conn = sqlite3.connect(
            str(self._db_path),
            timeout=self._timeout,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        return conn
    
    def acquire(
        self, 
        timeout: Optional[float] = 30.0
    ) -> sqlite3.Connection:
        """获取连接（阻塞直到可用或超时）
        
        Args:
            timeout: 等待秒数，None 表示无限等待
            
        Returns:
            sqlite3.Connection: 数据库连接
            
        Raises:
            PoolExhaustedError: 超时未获取到连接
            ConnectionError: 连接池已关闭
        """
        if self._closed:
            raise ConnectionError("Connection pool is closed")
        
        wait_timeout: Optional[float] = timeout
        
        with self._pool_lock:
            # 尝试从池获取现有连接
            try:
                conn = self._pool.get_nowait()
                self._active_connections.add(conn)
                return conn
            except Empty:
                pass
            
            # 如果未达到最大连接数，创建新连接
            if self._connection_count < self._max_connections:
                try:
                    conn = self._create_connection()
                    self._connection_count += 1
                    self._active_connections.add(conn)
                    return conn
                except sqlite3.Error as e:
                    raise ConnectionError(f"Failed to create connection: {e}", e)
        
        # 等待可用连接（释放锁后等待，避免阻塞其他线程）
        try:
            conn = self._pool.get(timeout=wait_timeout)
            with self._pool_lock:
                self._active_connections.add(conn)
            return conn
        except Empty:
            raise PoolExhaustedError(
                f"Failed to acquire connection within {timeout} seconds"
            )
    
    def release(self, conn: sqlite3.Connection) -> None:
        """释放连接回池
        
        Args:
            conn: 要释放的连接
        """
        with self._pool_lock:
            if conn in self._active_connections:
                self._active_connections.discard(conn)
                if not self._closed:
                    try:
                        self._pool.put_nowait(conn)
                    except Full:
                        conn.close()
                        self._connection_count -= 1
                else:
                    conn.close()
                    self._connection_count -= 1
    
    def is_full(self) -> bool:
        """检查连接池是否已满"""
        with self._pool_lock:
            return self._connection_count >= self._max_connections
    
    def close_all(self) -> None:
        """关闭所有连接（用于程序退出）"""
        with self._pool_lock:
            self._closed = True
            
            # 关闭活跃连接
            for conn in list(self._active_connections):
                try:
                    conn.close()
                except Exception:
                    pass
            self._active_connections.clear()
            
            # 关闭池中的空闲连接
            while not self._pool.empty():
                try:
                    conn = self._pool.get_nowait()
                    conn.close()
                except (Empty, Exception):
                    break
            
            self._connection_count = 0
            
            # 重置单例
            ConnectionPool._instance = None
