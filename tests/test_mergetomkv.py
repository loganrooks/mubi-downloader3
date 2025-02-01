import pytest
import os
from unittest.mock import Mock, patch
from mubi_downloader import MkvMerger, MediaFile

@pytest.fixture
def mkv_merger(tmp_path):
    merger = MkvMerger(str(tmp_path / "output"))
    return merger

@pytest.fixture
def sample_media_files(tmp_path):
    # Create sample files
    video_file = tmp_path / "decrypted-video.mp4"
    audio_file_en = tmp_path / "decrypted-audio.en.m4a"
    audio_file_fr = tmp_path / "decrypted-audio.fr.m4a"
    subtitle_file = tmp_path / "movie.en.srt"
    
    # Touch files to create them
    for f in [video_file, audio_file_en, audio_file_fr, subtitle_file]:
        f.touch()
    
    return [
        MediaFile(str(video_file), 'video'),
        MediaFile(str(audio_file_en), 'audio', 'eng'),
        MediaFile(str(audio_file_fr), 'audio', 'fra'),
        MediaFile(str(subtitle_file), 'subtitle', 'eng')
    ]

def test_mkv_merger_init(mkv_merger):
    """Test MkvMerger initialization"""
    assert mkv_merger.logger is not None
    assert os.path.exists(mkv_merger.output_dir)

def test_collect_media_files(mkv_merger, tmp_path):
    """Test media file collection"""
    # Create test files
    (tmp_path / "decrypted-video.mp4").touch()
    (tmp_path / "decrypted-audio.en.m4a").touch()
    (tmp_path / "movie.en.srt").touch()
    
    files = mkv_merger.collect_media_files(str(tmp_path))
    
    assert len(files) == 3
    assert any(f.type == 'video' for f in files)
    assert any(f.type == 'audio' and f.language == 'en' for f in files)
    assert any(f.type == 'subtitle' and f.language == 'en' for f in files)

def test_extract_language_code(mkv_merger):
    """Test language code extraction"""
    assert mkv_merger._extract_language_code("file.en.m4a") == "en"
    assert mkv_merger._extract_language_code("file.fr.srt") == "fr"
    assert mkv_merger._extract_language_code("file.mp4") is None

@patch('subprocess.run')
def test_merge_to_mkv_success(mock_run, mkv_merger, sample_media_files):
    """Test successful MKV merge"""
    mock_run.return_value = Mock(returncode=0)
    
    success = mkv_merger.merge_to_mkv(sample_media_files, "test_output")
    
    assert success
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args[0] == 'mkvmerge'
    assert args[2].endswith('test_output.mkv')

@patch('subprocess.run')
def test_merge_to_mkv_failure(mock_run, mkv_merger, sample_media_files):
    """Test MKV merge failure"""
    mock_run.return_value = Mock(returncode=1, stderr="Error")
    
    success = mkv_merger.merge_to_mkv(sample_media_files, "test_output")
    
    assert not success

def test_merge_to_mkv_no_video(mkv_merger):
    """Test merge without video file"""
    media_files = [
        MediaFile("audio.m4a", 'audio', 'eng'),
        MediaFile("subs.srt", 'subtitle', 'eng')
    ]
    
    with pytest.raises(ValueError, match="No video file found"):
        mkv_merger.merge_to_mkv(media_files, "test_output")

def test_cleanup_source_files(mkv_merger, tmp_path):
    """Test source file cleanup"""
    # Create test files
    test_files = []
    for name in ["video.mp4", "audio.m4a", "subs.srt"]:
        path = tmp_path / name
        path.touch()
        test_files.append(MediaFile(str(path), 'video'))
    
    # Test cleanup
    mkv_merger.cleanup_source_files(test_files, cleanup=True)
    
    # Verify files are removed
    for media_file in test_files:
        assert not os.path.exists(media_file.path)

def test_main_function(tmp_path):
    """Test main function with arguments"""
    test_dir = tmp_path / "test_input"
    test_dir.mkdir()
    (test_dir / "decrypted-video.mp4").touch()
    
    with patch('sys.argv', ['mergetomkv.py', str(test_dir), 'output', '--cleanup']):
        with patch('mubi_downloader.mergetomkv.MkvMerger.merge_to_mkv') as mock_merge:
            mock_merge.return_value = True
            from mubi_downloader.mergetomkv import main
            main()
            mock_merge.assert_called_once()