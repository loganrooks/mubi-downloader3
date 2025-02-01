import pytest
from unittest.mock import Mock, patch
from mubi_downloader import MovieSearch, DownloadManager, MovieInfo, AuthManager

@pytest.fixture
def movie_info():
    return MovieInfo(
        film_id="12345",
        title="Test Movie",
        year="2023",
        available_countries=["us", "uk"],
        film_slug="test-movie"
    )

@pytest.fixture
def movie_search():
    return MovieSearch()

@pytest.fixture
def download_manager():
    with patch('browser_cookie3.chrome'), \
         patch('browser_cookie3.firefox'), \
         patch('browser_cookie3.edge'):
        auth_manager = AuthManager()
        return DownloadManager(auth_manager)

class TestMovieSearch:
    @patch('requests.get')
    def test_get_user_location(self, mock_get, movie_search):
        """Test user location retrieval"""
        mock_response = Mock()
        mock_response.json.return_value = {'countryCode': 'US'}
        mock_get.return_value = mock_response
        
        result = movie_search.get_user_location()
        assert result == 'us'
        mock_get.assert_called_once_with('http://ip-api.com/json/')

    @patch('requests.get')
    def test_search_movie_success(self, mock_get, movie_search):
        """Test successful movie search"""
        mock_response = Mock()
        mock_response.text = """
            <div class="film" data-id="12345" data-year="2023">
                <h2>Test Movie</h2>
                <p class="film-showing">us,uk</p>
                <a href="/films/test-movie">Link</a>
            </div>
        """
        mock_get.return_value = mock_response
        
        result = movie_search.search_movie("test movie")
        assert result.film_id == "12345"
        assert result.title == "Test Movie"
        assert result.year == "2023"
        assert "us" in result.available_countries
        assert result.film_slug == "test-movie"

class TestDownloadManager:
    def test_ensure_download_folder(self, download_manager, tmp_path):
        """Test download folder creation"""
        download_manager.download_folder = str(tmp_path)
        download_manager._ensure_download_folder()
        
        assert tmp_path.exists()
        assert (tmp_path / "temp").exists()

    @patch('requests.get')
    def test_get_encryption_info(self, mock_get, download_manager, movie_info):
        """Test encryption info retrieval"""
        # Mock auth headers
        with patch.object(download_manager.auth_manager, 'generate_headers') as mock_headers:
            mock_headers.return_value = {
                'Authorization': 'Bearer test_token',
                'dt-custom-data': 'test_data'
            }
            
            # Mock secure URL response
            mock_response1 = Mock()
            mock_response1.json.return_value = {
                'url': 'https://test.com/video'
            }
            
            # Mock encryption key response
            mock_response2 = Mock()
            mock_response2.text = 'default_KID="12345678-1234-1234-1234-123456789012"'
            
            mock_get.side_effect = [mock_response1, mock_response2]
            
            # Mock CDM project response with proper hex format
            mock_post_response = Mock()
            mock_post_response.text = "abcd1234abcd1234:efef5678efef5678"
            
            with patch('requests.post') as mock_post:
                mock_post.return_value = mock_post_response
                
                decryption_key, secure_url = download_manager._get_encryption_info(
                    f'https://api.mubi.com/v3/films/{movie_info.film_id}/viewing/secure_url'
                )
                
                assert secure_url == 'https://test.com/video'
                assert decryption_key == 'key_id=abcd1234abcd1234:key=efef5678efef5678'

    @patch('os.system')
    def test_download_and_decrypt(self, mock_system, download_manager, movie_info, tmp_path):
        """Test download and decrypt process"""
        download_manager.download_folder = str(tmp_path)
        
        with patch.object(download_manager, '_get_encryption_info') as mock_get_info:
            mock_get_info.return_value = ("key_id=test:key=test", "test_url")
            
            # Run download and decrypt
            download_manager.download_and_decrypt(movie_info)
            
            # Check that commands were called
            calls = [call[0] for call in mock_system.call_args_list]
            
            # Verify N_m3u8DL-RE command
            assert any('N_m3u8DL-RE "test_url"' in str(call) for call in calls)
            
            # Verify shaka-packager command
            assert any('shaka-packager' in str(call) for call in calls)

def test_movie_info_properties(movie_info):
    """Test MovieInfo dataclass properties"""
    assert movie_info.full_title == "Test Movie (2023)"
    assert movie_info.mubi_url == "https://mubi.com/films/test-movie"