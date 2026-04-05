"""Models layer (Data Access) - Database models and CRUD operations."""

from .database import (
    Database,
    ConnectionPool,
    Transaction,
    DatabaseError,
    ConnectionError,
    TransactionError,
    PoolExhaustedError,
    ConnectionConfig,
    QueryResult,
)

# Project model exports
from .project import (
    Project,
    ProjectCreate,
    ProjectUpdate,
    ProjectStatus,
    ProjectError,
    ProjectNotFoundError,
    ProjectInvalidStatusError,
    ProjectAlreadyDeletedError,
    ProjectManager,
)

# Character model exports
from .character import (
    Character,
    CharacterCreate,
    CharacterUpdate,
    CharacterWithStats,
    VoiceProfile,
    CharacterError,
    CharacterNotFoundError,
    CharacterAlreadyDeletedError,
    InvalidFirstFrameError,
    ProjectMismatchError,
    CharacterManager,
)

__all__ = [
    # Database infrastructure
    "Database",
    "ConnectionPool",
    "Transaction",
    "DatabaseError",
    "ConnectionError",
    "TransactionError",
    "PoolExhaustedError",
    "ConnectionConfig",
    "QueryResult",
    # Project model
    "Project",
    "ProjectCreate",
    "ProjectUpdate",
    "ProjectStatus",
    "ProjectError",
    "ProjectNotFoundError",
    "ProjectInvalidStatusError",
    "ProjectAlreadyDeletedError",
    "ProjectManager",
    # Character model
    "Character",
    "CharacterCreate",
    "CharacterUpdate",
    "CharacterWithStats",
    "VoiceProfile",
    "CharacterError",
    "CharacterNotFoundError",
    "CharacterAlreadyDeletedError",
    "InvalidFirstFrameError",
    "ProjectMismatchError",
    "CharacterManager",
]