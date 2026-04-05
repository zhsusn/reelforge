"""
文件：__tests__/test_video_renderer.py
职责：Video Renderer 模块单元测试（覆盖率 > 80%）
"""

from __future__ import annotations

import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pytest

import sys

sys.path.insert(0, "src")

from reelforge.core.video_renderer import (
    FFmpegNotFoundError,
    RenderConfig,
    RenderError,
    ResourceError,
    Shot,
    SubtitleError,
    VideoRenderer,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_dir() -> Path:
    """提供临时目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_audio_file(temp_dir: Path) -> Path:
    """创建模拟音频文件"""
    audio_path = temp_dir / "audio.mp3"
    audio_path.touch()
    return audio_path


@pytest.fixture
def mock_image_file(temp_dir: Path) -> Path:
    """创建模拟图片文件"""
    image_path = temp_dir / "image.png"
    image_path.touch()
    return image_path


@pytest.fixture
def mock_shot(mock_audio_file: Path, mock_image_file: Path) -> Shot:
    """创建模拟分镜数据"""
    return Shot(
        sequence=1,
        dialogue="测试台词",
        audio_path=mock_audio_file,
        image_path=mock_image_file,
        duration=3.0,
        subtitle_start=0.0,
        subtitle_end=2.5,
    )


@pytest.fixture
def mock_config() -> RenderConfig:
    """创建模拟渲染配置"""
    return RenderConfig(
        resolution=(1080, 1920),
        fps=30,
        codec="libx264",
        bitrate="8000k",
        audio_codec="aac",
        audio_bitrate="192k",
        subtitle_color="#FFFFFF",
        bgm_volume=0.2,
    )


@pytest.fixture
def video_renderer() -> VideoRenderer:
    """提供VideoRenderer实例"""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        return VideoRenderer()


# =============================================================================
# Test Exceptions
# =============================================================================

class TestExceptions:
    """测试异常体系"""

    def test_render_error_with_original(self) -> None:
        """测试RenderError包装原始异常"""
        original = ValueError("original error")
        err = RenderError("render failed", original)

        assert err.message == "render failed"
        assert err.original_error is original

    def test_ffmpeg_not_found_error_inheritance(self) -> None:
        """测试FFmpegNotFoundError继承RenderError"""
        err = FFmpegNotFoundError("ffmpeg not found")
        assert isinstance(err, RenderError)

    def test_resource_error_inheritance(self) -> None:
        """测试ResourceError继承RenderError"""
        err = ResourceError("resource error")
        assert isinstance(err, RenderError)

    def test_subtitle_error_inheritance(self) -> None:
        """测试SubtitleError继承RenderError"""
        err = SubtitleError("subtitle error")
        assert isinstance(err, RenderError)


# =============================================================================
# Test FFmpeg Validation
# =============================================================================

class TestFFmpegValidation:
    """测试FFmpeg验证功能"""

    def test_validate_ffmpeg_success(self, video_renderer: VideoRenderer) -> None:
        """测试FFmpeg验证成功"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = video_renderer.validate_ffmpeg()
            assert result is True

    def test_validate_ffmpeg_file_not_found(self, video_renderer: VideoRenderer) -> None:
        """测试FFmpeg未找到"""
        with patch("subprocess.run", side_effect=FileNotFoundError("ffmpeg not found")):
            with pytest.raises(FFmpegNotFoundError) as exc_info:
                video_renderer.validate_ffmpeg()

            assert "FFmpeg未找到" in str(exc_info.value)

    def test_validate_ffmpeg_timeout(self, video_renderer: VideoRenderer) -> None:
        """测试FFmpeg验证超时"""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=5.0)):
            with pytest.raises(FFmpegNotFoundError) as exc_info:
                video_renderer.validate_ffmpeg()

            assert "超时" in str(exc_info.value)

    def test_validate_ffmpeg_failure(self, video_renderer: VideoRenderer) -> None:
        """测试FFmpeg执行失败"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            with pytest.raises(FFmpegNotFoundError):
                video_renderer.validate_ffmpeg()


# =============================================================================
# Test Shot and RenderConfig Models
# =============================================================================

class TestDataModels:
    """测试数据模型"""

    def test_shot_creation(self, mock_audio_file: Path, mock_image_file: Path) -> None:
        """测试创建Shot对象"""
        shot = Shot(
            sequence=1,
            dialogue="测试台词",
            audio_path=mock_audio_file,
            image_path=mock_image_file,
            duration=3.0,
            subtitle_start=0.0,
            subtitle_end=2.5,
        )

        assert shot.sequence == 1
        assert shot.dialogue == "测试台词"
        assert shot.audio_path == mock_audio_file
        assert shot.image_path == mock_image_file
        assert shot.duration == 3.0
        assert shot.subtitle_start == 0.0
        assert shot.subtitle_end == 2.5

    def test_render_config_defaults(self) -> None:
        """测试RenderConfig默认值"""
        config = RenderConfig()
        assert config.resolution == (1080, 1920)
        assert config.fps == 30
        assert config.codec == "libx264"
        assert config.bitrate == "8000k"
        assert config.audio_codec == "aac"
        assert config.audio_bitrate == "192k"
        assert config.subtitle_color == "#FFFFFF"
        assert config.bgm_volume == 0.2

    def test_render_config_custom(self) -> None:
        """测试RenderConfig自定义值"""
        config = RenderConfig(
            resolution=(720, 1280),
            fps=24,
            codec="h264",
            bitrate="4000k",
            audio_codec="mp3",
            audio_bitrate="128k",
            subtitle_color="#FF0000",
            bgm_volume=0.5,
        )

        assert config.resolution == (720, 1280)
        assert config.fps == 24
        assert config.codec == "h264"
        assert config.bitrate == "4000k"
        assert config.audio_codec == "mp3"
        assert config.audio_bitrate == "128k"
        assert config.subtitle_color == "#FF0000"
        assert config.bgm_volume == 0.5


# =============================================================================
# Test Estimate Duration
# =============================================================================

class TestEstimateDuration:
    """测试时长预估"""

    def test_estimate_duration_empty_list(self, video_renderer: VideoRenderer) -> None:
        """测试空列表"""
        duration = video_renderer.estimate_duration([])
        assert duration == 0.0

    def test_estimate_duration_single_shot(
        self, video_renderer: VideoRenderer, mock_shot: Shot
    ) -> None:
        """测试单个分镜"""
        with patch("librosa.get_duration", return_value=3.0):
            duration = video_renderer.estimate_duration([mock_shot])
            assert duration == 3.0

    def test_estimate_duration_multiple_shots(
        self, video_renderer: VideoRenderer, mock_shot: Shot
    ) -> None:
        """测试多个分镜"""
        shots = [
            Shot(
                sequence=1,
                dialogue="台词1",
                audio_path=Path("audio1.mp3"),
                image_path=Path("image1.png"),
                duration=2.0,
                subtitle_start=0.0,
                subtitle_end=1.5,
            ),
            Shot(
                sequence=2,
                dialogue="台词2",
                audio_path=Path("audio2.mp3"),
                image_path=Path("image2.png"),
                duration=3.0,
                subtitle_start=2.0,
                subtitle_end=2.8,
            ),
        ]

        with patch("librosa.get_duration") as mock_duration:
            mock_duration.side_effect = [2.0, 3.0]
            # 模拟文件存在
            with patch("pathlib.Path.exists", return_value=True):
                duration = video_renderer.estimate_duration(shots)
                assert duration == 5.0

    def test_estimate_duration_audio_not_found(
        self, video_renderer: VideoRenderer, mock_shot: Shot
    ) -> None:
        """测试音频文件不存在"""
        mock_shot.audio_path = Path("non_existent.mp3")

        with pytest.raises(ResourceError) as exc_info:
            video_renderer.estimate_duration([mock_shot])

        assert "音频文件不存在" in str(exc_info.value)

    def test_estimate_duration_audio_read_error(
        self, video_renderer: VideoRenderer, mock_shot: Shot
    ) -> None:
        """测试音频文件读取错误"""
        with patch("librosa.get_duration", side_effect=Exception("读取失败")):
            with pytest.raises(ResourceError) as exc_info:
                video_renderer.estimate_duration([mock_shot])

        assert "无法读取音频文件" in str(exc_info.value)


# =============================================================================
# Test Subtitle Generation
# =============================================================================

class TestSubtitleGeneration:
    """测试字幕生成"""

    def test_generate_subtitles_empty_list(
        self, video_renderer: VideoRenderer, temp_dir: Path, mock_config: RenderConfig
    ) -> None:
        """测试空分镜列表"""
        output_path = temp_dir / "subtitles.srt"
        with pytest.raises(SubtitleError) as exc_info:
            video_renderer.generate_subtitles([], output_path, mock_config)

        assert "没有分镜数据" in str(exc_info.value)

    def test_generate_subtitles_single_shot(
        self, video_renderer: VideoRenderer, mock_shot: Shot, temp_dir: Path, mock_config: RenderConfig
    ) -> None:
        """测试单个分镜的字幕生成"""
        output_path = temp_dir / "subtitles.srt"
        result_path = video_renderer.generate_subtitles([mock_shot], output_path, mock_config)

        assert result_path == output_path
        assert output_path.exists()

        # 验证SRT文件内容
        content = output_path.read_text(encoding="utf-8")
        assert "1" in content
        assert "00:00:00,000" in content  # 开始时间
        assert "00:00:02,500" in content  # 结束时间
        assert "测试台词" in content

    def test_generate_subtitles_multiple_shots(
        self, video_renderer: VideoRenderer, temp_dir: Path, mock_config: RenderConfig
    ) -> None:
        """测试多个分镜的字幕生成"""
        shots = [
            Shot(
                sequence=1,
                dialogue="第一句台词",
                audio_path=Path("audio1.mp3"),
                image_path=Path("image1.png"),
                duration=2.0,
                subtitle_start=0.0,
                subtitle_end=1.8,
            ),
            Shot(
                sequence=2,
                dialogue="第二句台词",
                audio_path=Path("audio2.mp3"),
                image_path=Path("image2.png"),
                duration=3.0,
                subtitle_start=2.0,
                subtitle_end=4.5,
            ),
        ]

        output_path = temp_dir / "subtitles.srt"
        result_path = video_renderer.generate_subtitles(shots, output_path, mock_config)

        assert result_path == output_path
        assert output_path.exists()

        content = output_path.read_text(encoding="utf-8")
        assert "1" in content
        assert "2" in content
        assert "第一句台词" in content
        assert "第二句台词" in content

    def test_generate_subtitles_write_error(
        self, video_renderer: VideoRenderer, mock_shot: Shot, temp_dir: Path, mock_config: RenderConfig
    ) -> None:
        """测试写入失败"""
        output_path = temp_dir / "subtitles.srt"

        # 模拟文件写入时抛出IOError
        with patch("builtins.open", side_effect=IOError("磁盘空间不足")):
            with pytest.raises(SubtitleError) as exc_info:
                video_renderer.generate_subtitles([mock_shot], output_path, mock_config)

        assert "无法写入字幕文件" in str(exc_info.value)


# =============================================================================
# Test Preview Frame
# =============================================================================

class TestPreviewFrame:
    """测试预览帧生成"""

    def test_preview_frame_image_not_found(
        self, video_renderer: VideoRenderer, mock_shot: Shot, mock_config: RenderConfig
    ) -> None:
        """测试图片文件不存在"""
        mock_shot.image_path = Path("non_existent.png")

        with pytest.raises(ResourceError) as exc_info:
            video_renderer.preview_frame(mock_shot, mock_config)

        assert "图片文件不存在" in str(exc_info.value)

    @patch("PIL.Image.open")
    def test_preview_frame_success(
        self, mock_image_open: Mock, video_renderer: VideoRenderer, mock_shot: Shot, mock_config: RenderConfig
    ) -> None:
        """测试预览帧生成成功"""
        # 模拟PIL Image对象
        mock_img = Mock()
        mock_img.mode = "RGB"
        mock_img.resize.return_value = mock_img
        mock_image_open.return_value = mock_img

        # 模拟numpy数组
        mock_array = np.zeros((1920, 1080, 3), dtype=np.uint8)
        mock_img.__array__ = Mock(return_value=mock_array)

        frame = video_renderer.preview_frame(mock_shot, mock_config)

        assert isinstance(frame, np.ndarray)
        assert frame.dtype == np.uint8
        assert frame.shape == (1920, 1080, 3)  # 高度, 宽度, 通道

        # 验证调用
        mock_image_open.assert_called_once_with(mock_shot.image_path)
        # 注意：实际的resize方法使用了Image.Resampling.LANCZOS参数
        from PIL import Image
        mock_img.resize.assert_called_once_with((1080, 1920), Image.Resampling.LANCZOS)

    @patch("PIL.Image.open")
    def test_preview_frame_convert_rgb(
        self, mock_image_open: Mock, video_renderer: VideoRenderer, mock_shot: Shot, mock_config: RenderConfig
    ) -> None:
        """测试非RGB图片转换"""
        mock_img = Mock()
        mock_img.mode = "L"  # 灰度图
        mock_img.convert.return_value = mock_img
        mock_img.resize.return_value = mock_img
        mock_image_open.return_value = mock_img

        mock_array = np.zeros((1920, 1080, 3), dtype=np.uint8)
        mock_img.__array__ = Mock(return_value=mock_array)

        video_renderer.preview_frame(mock_shot, mock_config)

        # 验证转换为RGB
        mock_img.convert.assert_called_once_with("RGB")

    @patch("PIL.Image.open", side_effect=IOError("文件损坏"))
    def test_preview_frame_io_error(
        self, mock_image_open: Mock, video_renderer: VideoRenderer, mock_shot: Shot, mock_config: RenderConfig
    ) -> None:
        """测试图片IO错误"""
        with pytest.raises(ResourceError) as exc_info:
            video_renderer.preview_frame(mock_shot, mock_config)

        assert "无法读取图片文件" in str(exc_info.value)


# =============================================================================
# Test Render (with Mocks)
# =============================================================================

class TestRender:
    """测试主渲染功能（使用Mock）"""

    def test_render_no_shots(self, video_renderer: VideoRenderer, mock_config: RenderConfig) -> None:
        """测试没有分镜数据"""
        with pytest.raises(ResourceError) as exc_info:
            video_renderer.render([], mock_config)

        assert "没有分镜数据" in str(exc_info.value)

    @patch("subprocess.run")
    @patch("moviepy.editor.ImageClip")
    @patch("moviepy.editor.AudioFileClip")
    @patch("moviepy.editor.concatenate_videoclips")
    def test_render_single_shot(
        self,
        mock_concat: Mock,
        mock_audio_clip: Mock,
        mock_image_clip: Mock,
        mock_subprocess: Mock,
        video_renderer: VideoRenderer,
        mock_shot: Shot,
        mock_config: RenderConfig,
        temp_dir: Path,
    ) -> None:
        """测试渲染单个分镜"""
        # 模拟FFmpeg验证
        mock_subprocess.return_value.returncode = 0

        # 模拟MoviePy对象
        mock_image_instance = Mock()
        mock_image_instance.with_duration.return_value = mock_image_instance
        mock_image_clip.return_value = mock_image_instance

        mock_audio_instance = Mock()
        mock_audio_clip.return_value = mock_audio_instance

        mock_final_clip = Mock()
        mock_final_clip.with_audio.return_value = mock_final_clip
        mock_final_clip.with_fps.return_value = mock_final_clip
        mock_final_clip.write_videofile = Mock()
        mock_concat.return_value = mock_final_clip

        # 创建输出目录
        output_dir = Path("workspace/output")
        output_dir.mkdir(parents=True, exist_ok=True)

        # 执行渲染
        with patch("pathlib.Path.exists", return_value=True):  # 模拟文件存在
            output_path = video_renderer.render([mock_shot], mock_config)

        # 验证输出路径格式
        assert output_path.parent == output_dir
        assert output_path.suffix == ".mp4"

        # 验证MoviePy调用
        mock_image_clip.assert_called_once_with(str(mock_shot.image_path))
        mock_audio_clip.assert_called_once_with(str(mock_shot.audio_path))
        mock_concat.assert_called_once()

    @patch("subprocess.run")
    @patch("moviepy.editor.ImageClip", side_effect=Exception("图片加载失败"))
    def test_render_image_load_error(
        self,
        mock_image_clip: Mock,
        mock_subprocess: Mock,
        video_renderer: VideoRenderer,
        mock_shot: Shot,
        mock_config: RenderConfig,
    ) -> None:
        """测试图片加载错误"""
        # 模拟FFmpeg验证
        mock_subprocess.return_value.returncode = 0

        with patch("pathlib.Path.exists", return_value=True):
            with pytest.raises(RenderError) as exc_info:
                video_renderer.render([mock_shot], mock_config)

        assert "视频渲染失败" in str(exc_info.value)
        # 原始错误被包装为ResourceError
        assert exc_info.value.original_error is not None
        assert isinstance(exc_info.value.original_error, ResourceError)

    def test_render_progress_callback(
        self, video_renderer: VideoRenderer, mock_shot: Shot, mock_config: RenderConfig
    ) -> None:
        """测试进度回调"""
        # 模拟所有依赖
        with patch("subprocess.run") as mock_subprocess, \
             patch("pathlib.Path.exists", return_value=True), \
             patch("moviepy.editor.ImageClip") as mock_image_clip, \
             patch("moviepy.editor.AudioFileClip") as mock_audio_clip, \
             patch("moviepy.editor.concatenate_videoclips") as mock_concat:

            mock_subprocess.return_value.returncode = 0
            mock_image_instance = Mock()
            mock_image_instance.with_duration.return_value = mock_image_instance
            mock_image_clip.return_value = mock_image_instance
            mock_audio_clip.return_value = Mock()
            mock_final_clip = Mock()
            mock_final_clip.with_audio.return_value = mock_final_clip
            mock_final_clip.with_fps.return_value = mock_final_clip
            mock_final_clip.write_videofile = Mock()
            mock_concat.return_value = mock_final_clip

            # 收集进度回调调用
            progress_calls = []

            def progress_callback(percent: int, message: str) -> None:
                progress_calls.append((percent, message))

            # 创建输出目录
            output_dir = Path("workspace/output")
            output_dir.mkdir(parents=True, exist_ok=True)

            video_renderer.render([mock_shot], mock_config, progress_callback)

            # 验证进度回调被调用
            assert len(progress_calls) > 0

            # 验证最后一个回调是100%
            last_call = progress_calls[-1]
            assert last_call[0] == 100
            assert "渲染完成" in last_call[1]


# =============================================================================
# Test Helper Methods
# =============================================================================

class TestHelperMethods:
    """测试辅助方法"""

    def test_format_srt_timestamp(self, video_renderer: VideoRenderer) -> None:
        """测试SRT时间戳格式化"""
        # 测试整数秒
        result = video_renderer._format_srt_timestamp(65.0)
        assert result == "00:01:05,000"

        # 测试带毫秒
        result = video_renderer._format_srt_timestamp(65.123)
        assert result == "00:01:05,123"

        # 测试小时
        result = video_renderer._format_srt_timestamp(3665.5)
        assert result == "01:01:05,500"

        # 测试边缘情况：0秒
        result = video_renderer._format_srt_timestamp(0.0)
        assert result == "00:00:00,000"

        # 测试边缘情况：大数值
        result = video_renderer._format_srt_timestamp(359999.999)
        assert result == "99:59:59,999"  # 虽然不现实，但测试格式化正确


if __name__ == "__main__":
    pytest.main([__file__, "-v"])