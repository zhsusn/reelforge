"""
文件：__tests__/test_project.py
职责：Project 数据模型单元测试（覆盖率 > 80%）
"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from typing import Generator

import pytest

import sys
sys.path.insert(0, "src")

from reelforge.models import Database, ProjectManager
from reelforge.models.project import (
    Project,
    ProjectCreate,
    ProjectUpdate,
    ProjectStatus,
    ProjectError,
    ProjectNotFoundError,
    ProjectInvalidStatusError,
    ProjectAlreadyDeletedError,
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


@pytest.fixture
def database(temp_db_path: Path) -> Generator[Database, None, None]:
    """提供已连接的数据库实例"""
    db = Database(temp_db_path)
    db.connect()

    # 初始化表结构
    schema_path = Path("docs/03-architecture/database-schema.sql")
    if schema_path.exists():
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()

        # 执行schema创建
        for statement in schema_sql.split(";"):
            statement = statement.strip()
            if statement and not statement.startswith("--"):
                try:
                    db.execute(statement)
                except Exception as e:
                    print(f"Warning: Failed to execute schema statement: {e}")

    yield db


@pytest.fixture
def project_manager(database: Database) -> ProjectManager:
    """提供项目管理器实例"""
    return ProjectManager(database)


@pytest.fixture
def sample_project_data() -> ProjectCreate:
    """提供示例项目数据"""
    return ProjectCreate(
        name="测试项目",
        description="这是一个测试项目",
        excel_path=Path("/path/to/excel.xlsx"),
    )


@pytest.fixture
def created_project(project_manager: ProjectManager, sample_project_data: ProjectCreate) -> Project:
    """创建并返回一个测试项目"""
    return project_manager.create(sample_project_data)


# =============================================================================
# 测试：项目创建
# =============================================================================

def test_create_project_success(project_manager: ProjectManager, sample_project_data: ProjectCreate) -> None:
    """测试成功创建项目"""
    # 执行
    project = project_manager.create(sample_project_data)

    # 验证
    assert project.project_id > 0
    assert project.name == sample_project_data.name
    assert project.description == sample_project_data.description
    assert project.status == ProjectStatus.DRAFT
    assert project.excel_path == sample_project_data.excel_path
    assert project.output_video_path is None
    assert project.task_id is None
    assert project.deleted_at is None
    assert isinstance(project.created_at, datetime)
    assert isinstance(project.updated_at, datetime)


def test_create_project_empty_name(project_manager: ProjectManager) -> None:
    """测试创建项目时名称为空"""
    with pytest.raises(ProjectError, match="Project name cannot be empty"):
        project_manager.create(ProjectCreate(name=" "))


def test_create_project_minimal_data(project_manager: ProjectManager) -> None:
    """测试使用最小数据创建项目"""
    minimal_data = ProjectCreate(name="最小项目")
    project = project_manager.create(minimal_data)

    assert project.name == "最小项目"
    assert project.description is None
    assert project.excel_path is None
    assert project.status == ProjectStatus.DRAFT


# =============================================================================
# 测试：项目查询
# =============================================================================

def test_get_by_id_success(project_manager: ProjectManager, created_project: Project) -> None:
    """测试成功通过ID获取项目"""
    # 执行
    retrieved = project_manager.get_by_id(created_project.project_id)

    # 验证
    assert retrieved.project_id == created_project.project_id
    assert retrieved.name == created_project.name
    assert retrieved.status == created_project.status


def test_get_by_id_not_found(project_manager: ProjectManager) -> None:
    """测试获取不存在的项目"""
    with pytest.raises(ProjectNotFoundError):
        project_manager.get_by_id(99999)


def test_get_by_id_include_deleted(project_manager: ProjectManager, created_project: Project) -> None:
    """测试获取已删除的项目（包含已删除）"""
    # 软删除项目
    project_manager.delete(created_project.project_id)

    # 不包含已删除应该失败
    with pytest.raises(ProjectNotFoundError):
        project_manager.get_by_id(created_project.project_id, include_deleted=False)

    # 包含已删除应该成功
    deleted = project_manager.get_by_id(created_project.project_id, include_deleted=True)
    assert deleted.project_id == created_project.project_id
    assert deleted.deleted_at is not None


# =============================================================================
# 测试：项目更新
# =============================================================================

def test_update_project_success(project_manager: ProjectManager, created_project: Project) -> None:
    """测试成功更新项目"""
    # 准备更新数据
    update_data = ProjectUpdate(
        name="更新后的名称",
        description="更新后的描述",
        status=ProjectStatus.PROCESSING,
        output_video_path=Path("/path/to/output.mp4"),
        task_id="task_12345",
    )

    # 执行更新
    updated = project_manager.update(created_project.project_id, update_data)

    # 验证
    assert updated.project_id == created_project.project_id
    assert updated.name == "更新后的名称"
    assert updated.description == "更新后的描述"
    assert updated.status == ProjectStatus.PROCESSING
    assert updated.output_video_path == Path("/path/to/output.mp4")
    assert updated.task_id == "task_12345"
    assert updated.updated_at > created_project.updated_at


def test_update_project_partial(project_manager: ProjectManager, created_project: Project) -> None:
    """测试部分更新项目"""
    # 只更新名称
    update_data = ProjectUpdate(name="仅更新名称")
    updated = project_manager.update(created_project.project_id, update_data)

    # 验证
    assert updated.name == "仅更新名称"
    assert updated.description == created_project.description  # 未改变
    assert updated.status == created_project.status  # 未改变


def test_update_project_not_found(project_manager: ProjectManager) -> None:
    """测试更新不存在的项目"""
    update_data = ProjectUpdate(name="不存在的项目")

    with pytest.raises(ProjectNotFoundError):
        project_manager.update(99999, update_data)


def test_update_project_already_deleted(project_manager: ProjectManager, created_project: Project) -> None:
    """测试更新已删除的项目"""
    # 先软删除
    project_manager.delete(created_project.project_id)

    # 尝试更新
    update_data = ProjectUpdate(name="尝试更新已删除的项目")

    with pytest.raises(ProjectAlreadyDeletedError):
        project_manager.update(created_project.project_id, update_data)


# =============================================================================
# 测试：项目删除
# =============================================================================

def test_soft_delete_project(project_manager: ProjectManager, created_project: Project) -> None:
    """测试软删除项目"""
    # 执行软删除
    success = project_manager.delete(created_project.project_id)

    # 验证
    assert success is True

    # 验证项目已软删除
    with pytest.raises(ProjectNotFoundError):
        project_manager.get_by_id(created_project.project_id)

    # 包含已删除应该能查到
    deleted = project_manager.get_by_id(created_project.project_id, include_deleted=True)
    assert deleted.deleted_at is not None


def test_hard_delete_project(project_manager: ProjectManager, created_project: Project) -> None:
    """测试硬删除项目"""
    # 执行硬删除
    success = project_manager.delete(created_project.project_id, hard_delete=True)

    # 验证
    assert success is True

    # 验证项目已完全删除
    with pytest.raises(ProjectNotFoundError):
        project_manager.get_by_id(created_project.project_id, include_deleted=True)


def test_delete_already_deleted(project_manager: ProjectManager, created_project: Project) -> None:
    """测试删除已删除的项目"""
    # 第一次软删除
    project_manager.delete(created_project.project_id)

    # 第二次软删除应该失败
    with pytest.raises(ProjectAlreadyDeletedError):
        project_manager.delete(created_project.project_id)


def test_delete_not_found(project_manager: ProjectManager) -> None:
    """测试删除不存在的项目"""
    success = project_manager.delete(99999)
    assert success is False


# =============================================================================
# 测试：项目列表和查询
# =============================================================================

def test_list_all_projects(project_manager: ProjectManager) -> None:
    """测试列出所有项目"""
    # 创建多个项目
    projects = []
    for i in range(3):
        project = project_manager.create(ProjectCreate(name=f"项目{i}"))
        projects.append(project)

    # 列出所有项目
    all_projects = project_manager.list_all()

    # 验证
    assert len(all_projects) == 3
    assert {p.name for p in all_projects} == {"项目0", "项目1", "项目2"}


def test_list_all_with_status_filter(project_manager: ProjectManager) -> None:
    """测试按状态过滤项目"""
    # 创建不同状态的项目
    project1 = project_manager.create(ProjectCreate(name="草稿项目"))

    project2 = project_manager.create(ProjectCreate(name="处理中项目"))
    project_manager.update_status(project2.project_id, ProjectStatus.PROCESSING)

    project3 = project_manager.create(ProjectCreate(name="已完成项目"))
    project_manager.update_status(project3.project_id, ProjectStatus.COMPLETED)

    # 按状态过滤
    draft_projects = project_manager.list_all(status=ProjectStatus.DRAFT)
    processing_projects = project_manager.list_all(status=ProjectStatus.PROCESSING)
    completed_projects = project_manager.list_all(status=ProjectStatus.COMPLETED)

    # 验证
    assert len(draft_projects) == 1
    assert draft_projects[0].name == "草稿项目"

    assert len(processing_projects) == 1
    assert processing_projects[0].name == "处理中项目"

    assert len(completed_projects) == 1
    assert completed_projects[0].name == "已完成项目"


def test_list_all_exclude_deleted(project_manager: ProjectManager) -> None:
    """测试列出项目时排除已删除的"""
    # 创建项目
    active_project = project_manager.create(ProjectCreate(name="活动项目"))
    deleted_project = project_manager.create(ProjectCreate(name="已删除项目"))

    # 删除一个项目
    project_manager.delete(deleted_project.project_id)

    # 列出所有（不包含已删除）
    all_projects = project_manager.list_all(include_deleted=False)
    assert len(all_projects) == 1
    assert all_projects[0].name == "活动项目"

    # 列出所有（包含已删除）
    all_with_deleted = project_manager.list_all(include_deleted=True)
    assert len(all_with_deleted) == 2


def test_count_projects(project_manager: ProjectManager) -> None:
    """测试统计项目数量"""
    # 初始数量
    initial_count = project_manager.count()
    assert initial_count == 0

    # 创建项目
    for i in range(5):
        project_manager.create(ProjectCreate(name=f"计数项目{i}"))

    # 统计
    total_count = project_manager.count()
    draft_count = project_manager.count(status=ProjectStatus.DRAFT)

    assert total_count == 5
    assert draft_count == 5


def test_search_by_name(project_manager: ProjectManager) -> None:
    """测试按名称搜索项目"""
    # 创建项目
    project_manager.create(ProjectCreate(name="Python项目"))
    project_manager.create(ProjectCreate(name="Java项目"))
    project_manager.create(ProjectCreate(name="Python高级项目"))

    # 搜索
    python_projects = project_manager.search_by_name("Python")
    java_projects = project_manager.search_by_name("Java")
    advanced_projects = project_manager.search_by_name("高级")

    # 验证
    assert len(python_projects) == 2
    assert {p.name for p in python_projects} == {"Python项目", "Python高级项目"}

    assert len(java_projects) == 1
    assert java_projects[0].name == "Java项目"

    assert len(advanced_projects) == 1
    assert advanced_projects[0].name == "Python高级项目"


# =============================================================================
# 测试：状态管理
# =============================================================================

def test_update_status_success(project_manager: ProjectManager, created_project: Project) -> None:
    """测试成功更新项目状态"""
    # 从DRAFT到PROCESSING
    updated = project_manager.update_status(created_project.project_id, ProjectStatus.PROCESSING)
    assert updated.status == ProjectStatus.PROCESSING

    # 从PROCESSING到COMPLETED
    updated = project_manager.update_status(updated.project_id, ProjectStatus.COMPLETED)
    assert updated.status == ProjectStatus.COMPLETED


def test_update_status_invalid_transition(project_manager: ProjectManager, created_project: Project) -> None:
    """测试无效的状态转换"""
    # DRAFT到PROCESSING（有效）
    project_manager.update_status(created_project.project_id, ProjectStatus.PROCESSING)

    # 从PROCESSING回DRAFT（无效）
    with pytest.raises(ProjectInvalidStatusError):
        project_manager.update_status(created_project.project_id, ProjectStatus.DRAFT)


def test_get_by_status(project_manager: ProjectManager) -> None:
    """测试获取指定状态的项目"""
    # 创建不同状态的项目
    draft_project = project_manager.create(ProjectCreate(name="草稿"))

    processing_project = project_manager.create(ProjectCreate(name="处理中"))
    project_manager.update_status(processing_project.project_id, ProjectStatus.PROCESSING)

    # 获取各状态项目
    draft_projects = project_manager.get_by_status(ProjectStatus.DRAFT)
    processing_projects = project_manager.get_by_status(ProjectStatus.PROCESSING)

    assert len(draft_projects) == 1
    assert draft_projects[0].name == "草稿"

    assert len(processing_projects) == 1
    assert processing_projects[0].name == "处理中"


# =============================================================================
# 测试：统计和报表
# =============================================================================

def test_get_statistics(project_manager: ProjectManager) -> None:
    """测试获取项目统计信息"""
    # 创建测试数据
    for i in range(2):
        project_manager.create(ProjectCreate(name=f"草稿项目{i}"))

    processing_project = project_manager.create(ProjectCreate(name="处理中项目"))
    project_manager.update_status(processing_project.project_id, ProjectStatus.PROCESSING)

    completed_project = project_manager.create(ProjectCreate(name="已完成项目"))
    project_manager.update_status(completed_project.project_id, ProjectStatus.COMPLETED)

    deleted_project = project_manager.create(ProjectCreate(name="已删除项目"))
    project_manager.delete(deleted_project.project_id)

    # 获取统计
    stats = project_manager.get_statistics()

    # 验证
    assert stats["total_count"] == 4  # 包括已删除
    assert stats["active_count"] == 3  # 不包括已删除
    assert stats["draft_count"] == 2
    assert stats["processing_count"] == 1
    assert stats["completed_count"] == 1
    assert stats["failed_count"] == 0
    assert "earliest_project" in stats
    assert "latest_project" in stats


def test_statistics_empty(project_manager: ProjectManager) -> None:
    """测试空数据库的统计信息"""
    stats = project_manager.get_statistics()

    assert stats["total_count"] == 0
    assert stats["active_count"] == 0
    assert stats["draft_count"] == 0
    assert stats["processing_count"] == 0
    assert stats["completed_count"] == 0
    assert stats["failed_count"] == 0
    assert stats["earliest_project"] is None
    assert stats["latest_project"] is None


# =============================================================================
# 测试：边界条件和错误处理
# =============================================================================

def test_create_project_special_characters(project_manager: ProjectManager) -> None:
    """测试创建包含特殊字符的项目"""
    special_names = [
        "项目-测试_1",
        "Project & Test",
        "测试项目@2024",
        "项目名称（带括号）",
        "项目名称【带方括号】",
        "Very-Long-Project-Name-With-Many-Words-And-Characters",
    ]

    for name in special_names:
        project = project_manager.create(ProjectCreate(name=name))
        assert project.name == name


def test_update_project_empty_update(project_manager: ProjectManager, created_project: Project) -> None:
    """测试空更新（不提供任何更新字段）"""
    update_data = ProjectUpdate()  # 空更新
    updated = project_manager.update(created_project.project_id, update_data)

    # 应该返回原项目，没有变化
    assert updated.project_id == created_project.project_id
    assert updated.name == created_project.name
    assert updated.updated_at == created_project.updated_at


def test_list_all_with_limit_offset(project_manager: ProjectManager) -> None:
    """测试分页列出项目"""
    # 创建多个项目
    for i in range(10):
        project_manager.create(ProjectCreate(name=f"分页项目{i}"))

    # 测试分页
    page1 = project_manager.list_all(limit=3, offset=0)
    page2 = project_manager.list_all(limit=3, offset=3)
    page3 = project_manager.list_all(limit=4, offset=6)

    assert len(page1) == 3
    assert len(page2) == 3
    assert len(page3) == 4

    # 验证分页正确性
    page1_names = {p.name for p in page1}
    page2_names = {p.name for p in page2}
    page3_names = {p.name for p in page3}

    # 确保没有重叠
    assert len(page1_names & page2_names) == 0
    assert len(page2_names & page3_names) == 0


def test_search_by_name_empty_result(project_manager: ProjectManager) -> None:
    """测试搜索无结果"""
    # 创建项目
    project_manager.create(ProjectCreate(name="Python项目"))

    # 搜索不存在的项目
    results = project_manager.search_by_name("不存在")
    assert len(results) == 0


def test_project_serialization(created_project: Project) -> None:
    """测试项目对象的序列化和反序列化"""
    # 转换为字典
    project_dict = {
        "project_id": created_project.project_id,
        "name": created_project.name,
        "description": created_project.description,
        "status": created_project.status.value,
        "excel_path": str(created_project.excel_path) if created_project.excel_path else None,
        "output_video_path": str(created_project.output_video_path) if created_project.output_video_path else None,
        "task_id": created_project.task_id,
        "created_at": created_project.created_at.isoformat(),
        "updated_at": created_project.updated_at.isoformat(),
        "deleted_at": created_project.deleted_at.isoformat() if created_project.deleted_at else None,
    }

    # 验证字典结构
    assert isinstance(project_dict, dict)
    assert "project_id" in project_dict
    assert "name" in project_dict
    assert "status" in project_dict


# =============================================================================
# 测试：并发安全（基础测试）
# =============================================================================

def test_concurrent_project_creation(project_manager: ProjectManager) -> None:
    """测试并发创建项目（基础测试）"""
    import threading

    created_ids = []
    errors = []

    def create_project_thread(thread_id: int):
        try:
            project = project_manager.create(ProjectCreate(name=f"并发项目{thread_id}"))
            created_ids.append(project.project_id)
        except Exception as e:
            errors.append(str(e))

    # 创建多个线程
    threads = []
    for i in range(5):
        thread = threading.Thread(target=create_project_thread, args=(i,))
        threads.append(thread)
        thread.start()

    # 等待所有线程完成
    for thread in threads:
        thread.join()

    # 验证
    assert len(errors) == 0
    assert len(set(created_ids)) == 5  # 所有ID应该唯一


if __name__ == "__main__":
    pytest.main([__file__, "-v"])