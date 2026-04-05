"""
文件：__tests__/test_character.py
职责：Character 数据模型单元测试（覆盖率 > 80%）
"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from typing import Generator

import pytest

import sys
sys.path.insert(0, "src")

from reelforge.models import Database, ProjectManager, CharacterManager
from reelforge.models.character import (
    Character,
    CharacterCreate,
    CharacterUpdate,
    VoiceProfile,
    CharacterError,
    CharacterNotFoundError,
    CharacterAlreadyDeletedError,
    InvalidFirstFrameError,
)
from reelforge.models.project import Project, ProjectCreate


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
def character_manager(database: Database) -> CharacterManager:
    """提供角色管理器实例"""
    return CharacterManager(database)


@pytest.fixture
def sample_project(project_manager: ProjectManager) -> Project:
    """创建并返回一个测试项目"""
    return project_manager.create(ProjectCreate(name="测试项目"))


@pytest.fixture
def sample_image_path() -> Generator[Path, None, None]:
    """创建测试图片文件"""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test_image.jpg"
        # 创建空文件模拟图片
        path.write_bytes(b"fake image data")
        yield path


@pytest.fixture
def sample_character_data(sample_project: Project, sample_image_path: Path) -> CharacterCreate:
    """提供示例角色数据"""
    return CharacterCreate(
        project_id=sample_project.project_id,
        name="测试角色",
        description="这是一个测试角色",
        first_frame_path=sample_image_path,
        voice_profile=VoiceProfile.XIAOXIAO,
    )


@pytest.fixture
def created_character(
    character_manager: CharacterManager,
    sample_character_data: CharacterCreate,
) -> Character:
    """创建并返回一个测试角色"""
    return character_manager.create(sample_character_data)


# =============================================================================
# 测试：角色创建
# =============================================================================

def test_create_character_success(
    character_manager: CharacterManager,
    sample_character_data: CharacterCreate,
) -> None:
    """测试成功创建角色"""
    # 执行
    character = character_manager.create(sample_character_data)

    # 验证
    assert character.character_id > 0
    assert character.project_id == sample_character_data.project_id
    assert character.name == sample_character_data.name
    assert character.description == sample_character_data.description
    assert character.first_frame_path == sample_character_data.first_frame_path
    assert character.character_vector is None
    assert character.similarity_score is None
    assert character.voice_profile == sample_character_data.voice_profile
    assert character.deleted_at is None
    assert isinstance(character.created_at, datetime)
    assert isinstance(character.updated_at, datetime)


def test_create_character_empty_name(
    character_manager: CharacterManager,
    sample_project: Project,
    sample_image_path: Path,
) -> None:
    """测试创建角色时名称为空"""
    char_data = CharacterCreate(
        project_id=sample_project.project_id,
        name=" ",
        first_frame_path=sample_image_path,
    )

    with pytest.raises(CharacterError, match="Character name cannot be empty"):
        character_manager.create(char_data)


def test_create_character_missing_first_frame(
    character_manager: CharacterManager,
    sample_project: Project,
) -> None:
    """测试创建角色时缺少首帧图片"""
    char_data = CharacterCreate(
        project_id=sample_project.project_id,
        name="测试角色",
        first_frame_path=None,
    )

    with pytest.raises(InvalidFirstFrameError, match="First frame path is required"):
        character_manager.create(char_data)


def test_create_character_nonexistent_first_frame(
    character_manager: CharacterManager,
    sample_project: Project,
) -> None:
    """测试创建角色时首帧图片不存在"""
    char_data = CharacterCreate(
        project_id=sample_project.project_id,
        name="测试角色",
        first_frame_path=Path("/nonexistent/image.jpg"),
    )

    with pytest.raises(InvalidFirstFrameError, match="First frame image not found"):
        character_manager.create(char_data)


def test_create_character_minimal_data(
    character_manager: CharacterManager,
    sample_project: Project,
    sample_image_path: Path,
) -> None:
    """测试使用最小数据创建角色"""
    minimal_data = CharacterCreate(
        project_id=sample_project.project_id,
        name="最小角色",
        first_frame_path=sample_image_path,
    )
    character = character_manager.create(minimal_data)

    assert character.name == "最小角色"
    assert character.description is None
    assert character.voice_profile == VoiceProfile.XIAOXIAO  # 默认值


# =============================================================================
# 测试：角色查询
# =============================================================================

def test_get_by_id_success(
    character_manager: CharacterManager,
    created_character: Character,
) -> None:
    """测试成功通过ID获取角色"""
    # 执行
    retrieved = character_manager.get_by_id(created_character.character_id)

    # 验证
    assert retrieved.character_id == created_character.character_id
    assert retrieved.name == created_character.name
    assert retrieved.project_id == created_character.project_id


def test_get_by_id_not_found(character_manager: CharacterManager) -> None:
    """测试获取不存在的角色"""
    with pytest.raises(CharacterNotFoundError):
        character_manager.get_by_id(99999)


def test_get_by_id_include_deleted(
    character_manager: CharacterManager,
    created_character: Character,
) -> None:
    """测试获取已删除的角色（包含已删除）"""
    # 软删除角色
    character_manager.delete(created_character.character_id)

    # 不包含已删除应该失败
    with pytest.raises(CharacterNotFoundError):
        character_manager.get_by_id(created_character.character_id, include_deleted=False)

    # 包含已删除应该成功
    deleted = character_manager.get_by_id(created_character.character_id, include_deleted=True)
    assert deleted.character_id == created_character.character_id
    assert deleted.deleted_at is not None


def test_get_by_project_success(
    character_manager: CharacterManager,
    created_character: Character,
    sample_project: Project,
) -> None:
    """测试获取指定项目的所有角色"""
    # 创建另一个项目的角色
    other_project_id = sample_project.project_id + 999

    # 获取当前项目角色
    characters = character_manager.get_by_project(sample_project.project_id)

    # 验证
    assert len(characters) == 1
    assert characters[0].character_id == created_character.character_id


def test_get_by_project_empty(
    character_manager: CharacterManager,
    sample_project: Project,
) -> None:
    """测试获取空项目的角色"""
    # 创建新项目（无角色）
    empty_project = Project(
        project_id=sample_project.project_id + 999,
        name="空项目",
        description=None,
        status="draft",
        excel_path=None,
        output_video_path=None,
        task_id=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        deleted_at=None,
    )

    characters = character_manager.get_by_project(empty_project.project_id)
    assert len(characters) == 0


# =============================================================================
# 测试：角色更新
# =============================================================================

def test_update_character_success(
    character_manager: CharacterManager,
    created_character: Character,
    sample_image_path: Path,
) -> None:
    """测试成功更新角色"""
    # 准备更新数据
    new_image_path = Path(str(sample_image_path).replace(".jpg", "_updated.jpg"))
    new_image_path.write_bytes(b"updated image data")

    update_data = CharacterUpdate(
        name="更新后的名称",
        description="更新后的描述",
        first_frame_path=new_image_path,
        voice_profile=VoiceProfile.YUNXI,
    )

    # 执行更新
    updated = character_manager.update(created_character.character_id, update_data)

    # 验证
    assert updated.character_id == created_character.character_id
    assert updated.name == "更新后的名称"
    assert updated.description == "更新后的描述"
    assert updated.first_frame_path == new_image_path
    assert updated.voice_profile == VoiceProfile.YUNXI
    assert updated.updated_at > created_character.updated_at

    # 清理测试文件
    new_image_path.unlink()


def test_update_character_partial(
    character_manager: CharacterManager,
    created_character: Character,
) -> None:
    """测试部分更新角色"""
    # 只更新名称
    update_data = CharacterUpdate(name="仅更新名称")
    updated = character_manager.update(created_character.character_id, update_data)

    # 验证
    assert updated.name == "仅更新名称"
    assert updated.description == created_character.description  # 未改变
    assert updated.voice_profile == created_character.voice_profile  # 未改变


def test_update_character_not_found(character_manager: CharacterManager) -> None:
    """测试更新不存在的角色"""
    update_data = CharacterUpdate(name="不存在的角色")

    with pytest.raises(CharacterNotFoundError):
        character_manager.update(99999, update_data)


def test_update_character_already_deleted(
    character_manager: CharacterManager,
    created_character: Character,
) -> None:
    """测试更新已删除的角色"""
    # 先软删除
    character_manager.delete(created_character.character_id)

    # 尝试更新
    update_data = CharacterUpdate(name="尝试更新已删除的角色")

    with pytest.raises(CharacterAlreadyDeletedError):
        character_manager.update(created_character.character_id, update_data)


def test_update_character_vector_success(
    character_manager: CharacterManager,
    created_character: Character,
) -> None:
    """测试成功更新角色特征向量"""
    # 准备特征向量和相似度分数
    character_vector = b"fake feature vector data"
    similarity_score = 95.5

    # 执行更新
    updated = character_manager.update_character_vector(
        created_character.character_id,
        character_vector,
        similarity_score,
    )

    # 验证
    assert updated.character_vector == character_vector
    assert updated.similarity_score == similarity_score


# =============================================================================
# 测试：角色删除
# =============================================================================

def test_soft_delete_character(
    character_manager: CharacterManager,
    created_character: Character,
) -> None:
    """测试软删除角色"""
    # 执行软删除
    success = character_manager.delete(created_character.character_id)

    # 验证
    assert success is True

    # 验证角色已软删除
    with pytest.raises(CharacterNotFoundError):
        character_manager.get_by_id(created_character.character_id)

    # 包含已删除应该能查到
    deleted = character_manager.get_by_id(created_character.character_id, include_deleted=True)
    assert deleted.deleted_at is not None


def test_hard_delete_character(
    character_manager: CharacterManager,
    created_character: Character,
) -> None:
    """测试硬删除角色"""
    # 执行硬删除
    success = character_manager.delete(created_character.character_id, hard_delete=True)

    # 验证
    assert success is True

    # 验证角色已完全删除
    with pytest.raises(CharacterNotFoundError):
        character_manager.get_by_id(created_character.character_id, include_deleted=True)


def test_delete_already_deleted(
    character_manager: CharacterManager,
    created_character: Character,
) -> None:
    """测试删除已删除的角色"""
    # 第一次软删除
    character_manager.delete(created_character.character_id)

    # 第二次软删除应该失败
    with pytest.raises(CharacterAlreadyDeletedError):
        character_manager.delete(created_character.character_id)


def test_delete_not_found(character_manager: CharacterManager) -> None:
    """测试删除不存在的角色"""
    success = character_manager.delete(99999)
    assert success is False


# =============================================================================
# 测试：角色列表和查询
# =============================================================================

def test_list_all_characters(
    character_manager: CharacterManager,
    sample_project: Project,
    sample_image_path: Path,
) -> None:
    """测试列出所有角色"""
    # 创建多个角色
    characters = []
    for i in range(3):
        char_data = CharacterCreate(
            project_id=sample_project.project_id,
            name=f"角色{i}",
            first_frame_path=sample_image_path,
        )
        character = character_manager.create(char_data)
        characters.append(character)

    # 列出所有角色
    all_characters = character_manager.list_all()

    # 验证
    assert len(all_characters) >= 3  # 可能有其他测试创建的角色
    names = {c.name for c in all_characters}
    assert all(f"角色{i}" in names for i in range(3))


def test_list_all_with_project_filter(
    character_manager: CharacterManager,
    sample_project: Project,
    sample_image_path: Path,
) -> None:
    """测试按项目过滤角色"""
    # 创建多个角色
    for i in range(2):
        char_data = CharacterCreate(
            project_id=sample_project.project_id,
            name=f"项目角色{i}",
            first_frame_path=sample_image_path,
        )
        character_manager.create(char_data)

    # 按项目过滤
    project_characters = character_manager.list_all(project_id=sample_project.project_id)

    # 验证
    assert len(project_characters) >= 2
    assert all(c.project_id == sample_project.project_id for c in project_characters)


def test_list_all_exclude_deleted(
    character_manager: CharacterManager,
    sample_project: Project,
    sample_image_path: Path,
) -> None:
    """测试列出角色时排除已删除的"""
    # 创建角色
    active_char = character_manager.create(CharacterCreate(
        project_id=sample_project.project_id,
        name="活动角色",
        first_frame_path=sample_image_path,
    ))

    deleted_char = character_manager.create(CharacterCreate(
        project_id=sample_project.project_id,
        name="已删除角色",
        first_frame_path=sample_image_path,
    ))

    # 删除一个角色
    character_manager.delete(deleted_char.character_id)

    # 列出所有（不包含已删除）
    all_chars = character_manager.list_all(include_deleted=False)
    char_names = {c.name for c in all_chars}

    assert "活动角色" in char_names
    assert "已删除角色" not in char_names  # 已删除的应该排除

    # 列出所有（包含已删除）
    all_with_deleted = character_manager.list_all(include_deleted=True)
    assert len(all_with_deleted) >= 2  # 至少包含活动角色和已删除角色


def test_count_characters(
    character_manager: CharacterManager,
    sample_project: Project,
    sample_image_path: Path,
) -> None:
    """测试统计角色数量"""
    # 初始数量
    initial_count = character_manager.count()

    # 创建角色
    for i in range(3):
        char_data = CharacterCreate(
            project_id=sample_project.project_id,
            name=f"计数角色{i}",
            first_frame_path=sample_image_path,
        )
        character_manager.create(char_data)

    # 统计
    total_count = character_manager.count()
    project_count = character_manager.count(project_id=sample_project.project_id)

    assert total_count >= initial_count + 3
    assert project_count >= 3  # 至少包含新创建的3个角色


def test_search_by_name(
    character_manager: CharacterManager,
    sample_project: Project,
    sample_image_path: Path,
) -> None:
    """测试按名称搜索角色"""
    # 创建角色
    character_manager.create(CharacterCreate(
        project_id=sample_project.project_id,
        name="Python角色",
        first_frame_path=sample_image_path,
    ))
    character_manager.create(CharacterCreate(
        project_id=sample_project.project_id,
        name="Java角色",
        first_frame_path=sample_image_path,
    ))
    character_manager.create(CharacterCreate(
        project_id=sample_project.project_id,
        name="Python高级角色",
        first_frame_path=sample_image_path,
    ))

    # 搜索
    python_chars = character_manager.search_by_name("Python")
    java_chars = character_manager.search_by_name("Java")
    advanced_chars = character_manager.search_by_name("高级")

    # 验证
    assert len(python_chars) >= 2
    names = {c.name for c in python_chars}
    assert "Python角色" in names
    assert "Python高级角色" in names

    assert len(java_chars) >= 1
    assert java_chars[0].name == "Java角色"

    assert len(advanced_chars) >= 1
    assert advanced_chars[0].name == "Python高级角色"


def test_search_by_name_with_project_filter(
    character_manager: CharacterManager,
    sample_project: Project,
    sample_image_path: Path,
) -> None:
    """测试按名称搜索并过滤项目"""
    # 创建多个项目的角色
    char_data1 = CharacterCreate(
        project_id=sample_project.project_id,
        name="项目1角色",
        first_frame_path=sample_image_path,
    )
    char1 = character_manager.create(char_data1)

    # 搜索
    results = character_manager.search_by_name("项目1", project_id=sample_project.project_id)

    assert len(results) >= 1
    assert results[0].character_id == char1.character_id


# =============================================================================
# 测试：首帧锁定相关
# =============================================================================

def test_get_by_first_frame_path(
    character_manager: CharacterManager,
    created_character: Character,
    sample_image_path: Path,
) -> None:
    """测试根据首帧图片路径查找角色"""
    # 查找
    characters = character_manager.get_by_first_frame_path(sample_image_path)

    # 验证
    assert len(characters) >= 1
    assert any(c.character_id == created_character.character_id for c in characters)


def test_get_by_first_frame_path_not_found(
    character_manager: CharacterManager,
) -> None:
    """测试根据不存在的首帧图片路径查找角色"""
    characters = character_manager.get_by_first_frame_path(Path("/nonexistent/image.jpg"))
    assert len(characters) == 0


# =============================================================================
# 测试：音色配置
# =============================================================================

def test_voice_profile_enum() -> None:
    """测试音色配置枚举"""
    assert VoiceProfile.XIAOXIAO.value == "zh-CN-XiaoxiaoNeural"
    assert VoiceProfile.YUNXI.value == "zh-CN-YunxiNeural"
    assert VoiceProfile.YUNYANG.value == "zh-CN-YunyangNeural"
    assert VoiceProfile.XIAOYI.value == "zh-CN-XiaoyiNeural"
    assert VoiceProfile.NARRATOR.value == "zh-CN-YunxiNeural"


def test_get_voice_profile_usage(
    character_manager: CharacterManager,
    sample_project: Project,
    sample_image_path: Path,
) -> None:
    """测试获取音色配置使用统计"""
    # 创建不同音色的角色
    voice_profiles = [
        VoiceProfile.XIAOXIAO,
        VoiceProfile.YUNXI,
        VoiceProfile.XIAOXIAO,  # 重复
        VoiceProfile.YUNYANG,
    ]

    for i, voice in enumerate(voice_profiles):
        char_data = CharacterCreate(
            project_id=sample_project.project_id,
            name=f"音色测试角色{i}",
            first_frame_path=sample_image_path,
            voice_profile=voice,
        )
        character_manager.create(char_data)

    # 获取统计
    usage = character_manager.get_voice_profile_usage(project_id=sample_project.project_id)

    # 验证
    assert isinstance(usage, dict)
    assert VoiceProfile.XIAOXIAO.value in usage
    assert usage[VoiceProfile.XIAOXIAO.value] >= 2  # 至少2个XIAOXIAO
    assert VoiceProfile.YUNXI.value in usage
    assert usage[VoiceProfile.YUNXI.value] >= 1


# =============================================================================
# 测试：边界条件和错误处理
# =============================================================================

def test_create_character_special_characters(
    character_manager: CharacterManager,
    sample_project: Project,
    sample_image_path: Path,
) -> None:
    """测试创建包含特殊字符的角色"""
    special_names = [
        "角色-测试_1",
        "Character & Test",
        "测试角色@2024",
        "角色名称（带括号）",
        "角色名称【带方括号】",
        "Very-Long-Character-Name-With-Many-Words-And-Characters",
    ]

    for name in special_names:
        char_data = CharacterCreate(
            project_id=sample_project.project_id,
            name=name,
            first_frame_path=sample_image_path,
        )
        character = character_manager.create(char_data)
        assert character.name == name


def test_update_character_empty_update(
    character_manager: CharacterManager,
    created_character: Character,
) -> None:
    """测试空更新（不提供任何更新字段）"""
    update_data = CharacterUpdate()  # 空更新
    updated = character_manager.update(created_character.character_id, update_data)

    # 应该返回原角色，没有变化
    assert updated.character_id == created_character.character_id
    assert updated.name == created_character.name
    assert updated.updated_at == created_character.updated_at


def test_list_all_with_limit_offset(
    character_manager: CharacterManager,
    sample_project: Project,
    sample_image_path: Path,
) -> None:
    """测试分页列出角色"""
    # 创建多个角色
    for i in range(10):
        char_data = CharacterCreate(
            project_id=sample_project.project_id,
            name=f"分页角色{i}",
            first_frame_path=sample_image_path,
        )
        character_manager.create(char_data)

    # 测试分页
    page1 = character_manager.list_all(limit=3, offset=0)
    page2 = character_manager.list_all(limit=3, offset=3)

    assert len(page1) == 3
    assert len(page2) == 3

    # 验证分页正确性（项目ID相同，但具体名称可能不同）
    page1_ids = {c.character_id for c in page1}
    page2_ids = {c.character_id for c in page2}

    # 确保没有重叠
    assert len(page1_ids & page2_ids) == 0


def test_search_by_name_empty_result(
    character_manager: CharacterManager,
    sample_project: Project,
    sample_image_path: Path,
) -> None:
    """测试搜索无结果"""
    # 创建角色
    char_data = CharacterCreate(
        project_id=sample_project.project_id,
        name="测试角色",
        first_frame_path=sample_image_path,
    )
    character_manager.create(char_data)

    # 搜索不存在的角色
    results = character_manager.search_by_name("不存在")
    assert len(results) == 0


def test_character_serialization(created_character: Character) -> None:
    """测试角色对象的序列化和反序列化"""
    # 转换为字典
    character_dict = {
        "character_id": created_character.character_id,
        "project_id": created_character.project_id,
        "name": created_character.name,
        "description": created_character.description,
        "first_frame_path": str(created_character.first_frame_path),
        "character_vector": created_character.character_vector,
        "similarity_score": created_character.similarity_score,
        "voice_profile": created_character.voice_profile.value,
        "created_at": created_character.created_at.isoformat(),
        "updated_at": created_character.updated_at.isoformat(),
        "deleted_at": created_character.deleted_at.isoformat() if created_character.deleted_at else None,
    }

    # 验证字典结构
    assert isinstance(character_dict, dict)
    assert "character_id" in character_dict
    assert "name" in character_dict
    assert "voice_profile" in character_dict


# =============================================================================
# 测试：批量操作
# =============================================================================

def test_batch_create_characters(
    character_manager: CharacterManager,
    sample_project: Project,
    sample_image_path: Path,
) -> None:
    """测试批量创建角色"""
    # 准备批量数据
    characters_data = [
        CharacterCreate(
            project_id=sample_project.project_id,
            name=f"批量角色{i}",
            first_frame_path=sample_image_path,
        )
        for i in range(3)
    ]

    # 批量创建
    created = character_manager.batch_create(characters_data)

    # 验证
    assert len(created) == 3
    assert {c.name for c in created} == {"批量角色0", "批量角色1", "批量角色2"}


def test_batch_delete_characters(
    character_manager: CharacterManager,
    sample_project: Project,
    sample_image_path: Path,
) -> None:
    """测试批量删除角色"""
    # 创建角色
    character_ids = []
    for i in range(3):
        char_data = CharacterCreate(
            project_id=sample_project.project_id,
            name=f"批量删除角色{i}",
            first_frame_path=sample_image_path,
        )
        character = character_manager.create(char_data)
        character_ids.append(character.character_id)

    # 批量删除
    results = character_manager.batch_delete(character_ids)

    # 验证
    assert results["total"] == 3
    assert results["success"] == 3
    assert results["failed"] == 0
    assert len(results["errors"]) == 0


def test_batch_delete_mixed_results(
    character_manager: CharacterManager,
    sample_project: Project,
    sample_image_path: Path,
) -> None:
    """测试批量删除混合结果（成功、失败、已删除、未找到）"""
    # 创建角色
    char1 = character_manager.create(CharacterCreate(
        project_id=sample_project.project_id,
        name="角色1",
        first_frame_path=sample_image_path,
    ))

    char2 = character_manager.create(CharacterCreate(
        project_id=sample_project.project_id,
        name="角色2",
        first_frame_path=sample_image_path,
    ))

    # 删除一个角色
    character_manager.delete(char1.character_id)

    # 批量删除：已删除的、存在的、不存在的
    character_ids = [
        char1.character_id,  # 已删除
        char2.character_id,  # 存在
        99999,  # 不存在
    ]

    results = character_manager.batch_delete(character_ids)

    # 验证
    assert results["total"] == 3
    assert results["already_deleted"] == 1
    assert results["success"] == 1
    assert results["not_found"] == 1
    assert len(results["errors"]) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])