"""
文件：src/reelforge/modules/database/connection.py
职责：SQLite数据库管理主类，封装连接池和基础查询接口
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator, List, Optional, Union, final

from reelforge.models.database.exceptions import ConnectionError, DatabaseError

if TYPE_CHECKING:
    from reelforge.models.database.pool import ConnectionPool
    from reelforge.models.database.transaction import Transaction


ConnectionConfig = dict[str, Union[str, int, bool]]
"""连接配置类型：{"timeout": 30, "wal_mode": True, "max_connections": 5}"""

QueryResult = Iterator[sqlite3.Row]
"""查询结果类型：行迭代器"""

_DEFAULT_CONFIG: ConnectionConfig = {
    "timeout": 30,
    "wal_mode": True,
    "max_connections": 5,
}


@final
class Database:
    """SQLite数据库管理主类
    
    职责：
        1. 连接生命周期管理（打开/关闭）
        2. 连接池封装（引用 pool.ConnectionPool）
        3. 基础查询接口（execute/query）
        4. 事务管理（引用 transaction.Transaction）
    """
    
    def __init__(
        self, 
        db_path: Path, 
        config: Optional[ConnectionConfig] = None
    ) -> None:
        """初始化数据库管理器
        
        Args:
            db_path: 数据库文件路径（不存在自动创建）
            config: 连接配置（可选，默认 WAL 模式开启）
        """
        self._db_path: Path = Path(db_path)
        self._config: ConnectionConfig = {**_DEFAULT_CONFIG, **(config or {})}
        self._pool: Optional[ConnectionPool] = None
    
    def connect(self) -> None:
        """建立连接（初始化连接池）
        
        Raises:
            ConnectionError: 连接失败（路径不可写、文件损坏等）
        """
        if self._pool is not None:
            return
        
        try:
            self._ensure_directory()
            self._pool = self._create_pool()
            self._setup_wal_mode()
        except sqlite3.Error as e:
            raise ConnectionError(f"Failed to connect: {e}", e)
    
    def _ensure_directory(self) -> None:
        """确保数据库目录存在"""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _create_pool(self) -> ConnectionPool:
        """创建连接池（延迟导入避免循环依赖）"""
        from reelforge.models.database.pool import ConnectionPool
        
        max_conn = int(self._config.get("max_connections", 5))
        return ConnectionPool(
            self._db_path,
            max_connections=max_conn,
            timeout=self._config.get("timeout", 30),
        )
    
    def _setup_wal_mode(self) -> None:
        """设置 WAL 模式"""
        if self._pool is None:
            raise ConnectionError("Pool not initialized")
        if self._config.get("wal_mode", True):
            conn = self._pool.acquire(timeout=5.0)
            try:
                conn.execute("PRAGMA journal_mode=WAL")
            finally:
                self._pool.release(conn)
    
    def disconnect(self) -> None:
        """断开所有连接（释放资源）"""
        if self._pool is not None:
            self._pool.close_all()
            self._pool = None
    
    def is_alive(self) -> bool:
        """检查数据库连接是否有效
        
        Returns:
            bool: 能正常执行 PRAGMA 查询返回 True
        """
        if self._pool is None:
            return False
        
        try:
            conn = self._pool.acquire(timeout=1.0)
            try:
                conn.execute("PRAGMA user_version")
                return True
            finally:
                self._pool.release(conn)
        except Exception:
            return False
    
    def execute(self, sql: str, parameters: Optional[tuple[Any, ...]] = None) -> int:
        """执行 SQL（INSERT/UPDATE/DELETE）
        
        Args:
            sql: SQL 语句（使用 ? 占位符防注入）
            parameters: SQL 参数元组
            
        Returns:
            int: 影响的行数（rowcount）
            
        Raises:
            DatabaseError: 执行失败
        """
        if self._pool is None:
            raise ConnectionError("Database not connected")
        
        conn = self._pool.acquire()
        try:
            with conn:
                cursor = conn.execute(sql, parameters or ())
                return cursor.rowcount
        except sqlite3.Error as e:
            raise DatabaseError(f"Execute failed: {e}", e)
    
    def query(self, sql: str, parameters: Optional[tuple[Any, ...]] = None) -> QueryResult:
        """执行查询（SELECT）返回迭代器
        
        Args:
            sql: SELECT 语句
            parameters: 查询参数
            
        Returns:
            QueryResult: 行迭代器（sqlite3.Row）
        """
        if self._pool is None:
            raise ConnectionError("Database not connected")
        
        conn = self._pool.acquire()
        try:
            cursor = conn.execute(sql, parameters or ())
            return iter(cursor.fetchall())
        except sqlite3.Error as e:
            raise DatabaseError(f"Query failed: {e}", e)
        finally:
            self._pool.release(conn)
    
    def query_one(
        self, 
        sql: str, 
        parameters: Optional[tuple[Any, ...]] = None
    ) -> Optional[sqlite3.Row]:
        """执行查询返回单行（或无结果）
        
        Args:
            sql: SELECT 语句
            parameters: 查询参数
            
        Returns:
            Optional[sqlite3.Row]: 单行结果，无结果返回 None
        """
        if self._pool is None:
            raise ConnectionError("Database not connected")
        
        conn = self._pool.acquire()
        try:
            cursor = conn.execute(sql, parameters or ())
            result: Optional[sqlite3.Row] = cursor.fetchone()
            return result
        except sqlite3.Error as e:
            raise DatabaseError(f"Query failed: {e}", e)
        finally:
            self._pool.release(conn)
    
    def transaction(
        self, 
        isolation_level: Optional[str] = "DEFERRED"
    ) -> Transaction:
        """创建事务上下文
        
        Args:
            isolation_level: 隔离级别（DEFERRED/IMMEDIATE/EXCLUSIVE）
            
        Returns:
            Transaction: 事务上下文管理器
            
        Raises:
            ConnectionError: 数据库未连接
        """
        if self._pool is None:
            raise ConnectionError("Database not connected")
        
        from reelforge.models.database.transaction import Transaction
        
        conn = self._pool.acquire()
        return Transaction(conn, self._pool, isolation_level)
    
    @property
    def pool(self) -> ConnectionPool:
        """获取连接池实例（只读）
        
        Raises:
            ConnectionError: 数据库未连接
        """
        if self._pool is None:
            raise ConnectionError("Database not connected")
        return self._pool
    
    @property
    def db_path(self) -> Path:
        """获取数据库路径（只读）"""
        return self._db_path

    def init_tables(self, schema_file: Optional[Path] = None) -> None:
        """
        初始化数据库表结构

        Args:
            schema_file: SQL schema文件路径，None则使用内置默认schema

        Raises:
            DatabaseError: 初始化失败
        """
        if self._pool is None:
            raise ConnectionError("Database not connected")

        sql_content: str
        if schema_file is not None:
            if not schema_file.exists():
                raise FileNotFoundError(f"Schema file not found: {schema_file}")
            sql_content = schema_file.read_text(encoding="utf-8")
        else:
            # 尝试从多个可能的位置查找database-schema.sql文件
            possible_paths = [
                # 从项目根目录开始
                Path("docs/03-architecture/database-schema.sql"),
                Path("../docs/03-architecture/database-schema.sql"),
                Path("../../docs/03-architecture/database-schema.sql"),
                # 从src目录开始
                Path("src/reelforge/docs/03-architecture/database-schema.sql"),
                # 绝对路径（如果运行在项目根目录）
                Path(__file__).parent.parent.parent.parent.parent / "docs" / "03-architecture" / "database-schema.sql",
            ]

            schema_path = None
            for path in possible_paths:
                if path.exists():
                    schema_path = path
                    break

            if schema_path is None:
                raise FileNotFoundError(
                    f"Default schema file not found. Tried: {[str(p) for p in possible_paths]}"
                )

            sql_content = schema_path.read_text(encoding="utf-8")

        # 执行SQL语句
        conn = self._pool.acquire()
        try:
            # SQLite不支持一次执行多条语句，需要分割
            statements = self._split_sql_statements(sql_content)

            with conn:
                for statement in statements:
                    if statement.strip():
                        conn.execute(statement)

            # 标记初始化完成
            conn.execute("INSERT OR IGNORE INTO migrations (version, name, checksum) VALUES (1, 'initial_schema_v1', ?)",
                        (self._calculate_checksum(sql_content),))

        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to initialize tables: {e}", e)
        finally:
            self._pool.release(conn)

    def _split_sql_statements(self, sql: str) -> List[str]:
        """分割SQL语句（基于分号分割，处理特殊语句）"""
        import re

        # 移除SQL注释
        sql = re.sub(r'--[^\n]*', '', sql)  # 移除单行注释
        sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)  # 移除多行注释

        # 分割SQL语句（基于分号）
        statements = []
        current = ""
        paren_depth = 0

        for char in sql:
            if char == '(':
                paren_depth += 1
                current += char
            elif char == ')':
                paren_depth -= 1
                current += char
            elif char == ';' and paren_depth == 0:
                # 语句结束
                current = current.strip()
                if current and not self._is_comment_or_empty(current):
                    statements.append(current)
                current = ""
            else:
                current += char

        # 处理最后一个语句（如果没有分号结尾）
        current = current.strip()
        if current and not self._is_comment_or_empty(current):
            statements.append(current)

        return statements

    def _is_comment_or_empty(self, sql: str) -> bool:
        """检查SQL语句是否为注释或空行"""
        if not sql:
            return True
        # 移除首尾空白后检查是否以--开头
        return sql.strip().upper().startswith('--') or not sql.strip()

    def _calculate_checksum(self, content: str) -> str:
        """计算内容的MD5校验和"""
        import hashlib
        return hashlib.md5(content.encode("utf-8")).hexdigest()
