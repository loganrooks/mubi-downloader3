#!/usr/bin/env python3
import os
import re
import json
import logging
import requests
import base64
import shutil
from dataclasses import dataclass
from typing import Optional, Dict, List
from bs4 import BeautifulSoup
from .auth_manager import AuthManager

@dataclass
class MovieInfo:
    """Data class for storing movie information"""
    film_id: str
    title: str
    year: str
    available_countries: List[str]
    film_slug: str
    
    @property
    def full_title(self) -> str:
        return f"{self.title} ({self.year})"
    
    @property
    def mubi_url(self) -> str:
        return f"https://mubi.com/films/{self.film_slug}"

class MovieSearch:
    """Handles movie search functionality and result parsing"""
    
    def __init__(self, base_url: str = "https://whatsonmubi.com/?q="):
        self.base_url = base_url
        self.logger = logging.getLogger('MovieSearch')
    
    def get_user_location(self) -> str:
        """
        Determines user's country code based on IP address.
        
        Returns:
            str: Two-letter country code in lowercase
        """
        try:
            response = requests.get('http://ip-api.com/json/')
            data = response.json()
            return data['countryCode'].lower()
        except Exception as e:
            self.logger.error(f"Failed to get location: {e}")
            return input("Enter your country code (e.g., us, uk): ").lower()

    def search_movie(self, query: str) -> Optional[MovieInfo]:
        """
        Searches for a movie on Mubi.
        
        Args:
            query (str): Movie search query
            
        Returns:
            Optional[MovieInfo]: Movie information if found, None otherwise
        """
        try:
            response = requests.get(self.base_url + query)
            soup = BeautifulSoup(response.text, 'html.parser')
            result = soup.find('div', class_='film')
            
            if not result:
                self.logger.info("No results found, entering manual mode")
                return self._handle_manual_entry()
            
            return MovieInfo(
                film_id=result['data-id'],
                title=result.find('h2').text,
                year=result['data-year'],
                available_countries=result.find('p', class_='film-showing').text.split(","),
                film_slug=result.find('a')['href'].split('/')[-1]
            )
            
        except Exception as e:
            self.logger.error(f"Search failed: {e}")
            return self._handle_manual_entry()
    
    def _handle_manual_entry(self) -> MovieInfo:
        """Handles manual entry of movie information"""
        return MovieInfo(
            film_id=input("Enter the film ID: "),
            title=input("Enter the film title: "),
            year=input("Enter the film year: "),
            available_countries=[],
            film_slug=""
        )

class DownloadManager:
    """Handles video download and decryption operations"""
    
    def __init__(self, auth_manager: AuthManager, download_folder: str = "download"):
        self.auth_manager = auth_manager
        self.download_folder = download_folder
        self.logger = logging.getLogger('DownloadManager')
        self._ensure_download_folder()
    
    def _ensure_download_folder(self):
        """Creates download folder if it doesn't exist"""
        os.makedirs(self.download_folder, exist_ok=True)
        os.makedirs(os.path.join(self.download_folder, "temp"), exist_ok=True)
    
    def _get_encryption_info(self, mubi_url: str) -> tuple:
        """
        Retrieves encryption information for the video.
        
        Returns:
            tuple: (decryption_key, secure_url)
        """
        try:
            headers = self._prepare_headers()
            
            # Get secure URL
            response = requests.get(mubi_url, headers=headers)
            mubi_data = response.json()
            secure_url = mubi_data['url']
            
            # Get encryption key
            kid_response = requests.get(secure_url)
            kid_match = re.search(r'default_KID="([^"]+)"', str(kid_response.text))
            if not kid_match:
                raise ValueError("Failed to extract encryption key ID")
                
            kid = kid_match.group(1).replace('-', '')
            pssh = self._generate_pssh(kid)
            
            # Get decryption key
            decryption_key = self._fetch_decryption_key(pssh, headers.get('dt-custom-data'))
            
            return decryption_key, secure_url
        except Exception as e:
            self.logger.error(f"Failed to get encryption info: {str(e)}")
            raise
    
    def _generate_pssh(self, key_id: str) -> str:
        """Generates PSSH box for decryption"""
        array_of_bytes = bytearray(b'2pssh')
        array_of_bytes.extend(bytes.fromhex("edef8ba979d64acea3c827dcd51d21ed"))
        array_of_bytes.extend(b'')
        array_of_bytes.extend(bytes.fromhex(key_id))
        return base64.b64encode(bytes.fromhex(array_of_bytes.hex())).decode('utf-8')
    
    def _fetch_decryption_key(self, pssh: str, dt_custom_data: str) -> str:
        """Fetches decryption key from CDM project"""
        response = requests.post('https://cdrm-project.com/wv', 
            headers={'Content-Type': 'application/json'},
            json={
                'license': 'https://lic.drmtoday.com/license-proxy-widevine/cenc/?specConform=true',
                'headers': dt_custom_data,
                'pssh': pssh,
                'buildInfo': '',
                'proxy': '',
                'cache': False,
            })
        
        key_match = re.search(r"([a-f0-9]{16,}:[a-f0-9]{16,})", str(response.text))
        if not key_match:
            raise ValueError("Failed to obtain decryption key")
            
        return f"key_id={key_match.group(1).replace(':', ':key=')}"
    
    def _prepare_headers(self) -> Dict:
        """Prepares headers for API requests"""
        try:
            auth_headers = self.auth_manager.generate_headers()
            base_headers = {
                'authority': 'api.mubi.com',
                'accept': '*/*',
                'client': 'web',
                'client-accept-audio-codecs': 'aac',
                'client-accept-video-codecs': 'h265,vp9,h264',
                'origin': 'https://mubi.com',
                'referer': 'https://mubi.com/',
            }
            return {**base_headers, **auth_headers}
        except Exception as e:
            self.logger.error(f"Failed to prepare headers: {str(e)}")
            raise
    
    def download_and_decrypt(self, movie_info: MovieInfo):
        """
        Downloads and decrypts the movie.
        
        Args:
            movie_info (MovieInfo): Information about the movie to download
        """
        try:
            api_url = f'https://api.mubi.com/v3/films/{movie_info.film_id}/viewing/secure_url'
            self.logger.debug(f"Fetching secure URL from: {api_url}")
            decryption_key, secure_url = self._get_encryption_info(api_url)
            self.logger.debug("Successfully obtained encryption info")
            
            # Download video
            dest_dir = os.path.join(self.download_folder, movie_info.full_title)
            os.makedirs(dest_dir, exist_ok=True)
            self.logger.debug(f"Created destination directory: {dest_dir}")
            
            self.logger.info("Downloading video...")
            download_cmd = f'N_m3u8DL-RE "{secure_url}" --auto-select --save-name "{movie_info.full_title}" ' \
                         f'--save-dir {self.download_folder} --tmp-dir {self.download_folder}/temp'
            self.logger.debug(f"Download command: {download_cmd}")
            os.system(download_cmd)
            
            input_file = f"{self.download_folder}/{movie_info.full_title}.mp4"
            output_file = f"{dest_dir}/decrypted-video.mp4"
            if not os.path.exists(input_file):
                self.logger.error(f"Downloaded file not found: {input_file}")
                raise FileNotFoundError(f"Downloaded file not found: {input_file}")
            
            # Decrypt video
            self.logger.info("Decrypting video...")
            decrypt_cmd = f'shaka-packager in="{input_file}",stream=video,output="{output_file}" ' \
                       f'--enable_raw_key_decryption --keys {decryption_key}'
            self.logger.debug(f"Decryption command: {decrypt_cmd}")
            os.system(decrypt_cmd)
            
            if not os.path.exists(output_file):
                self.logger.error(f"Decrypted file not found: {output_file}")
                raise FileNotFoundError(f"Decryption failed - output file not found: {output_file}")
                
            self.logger.debug("Video decryption completed successfully")
            
            # Process subtitles and audio
            self.logger.debug("Processing additional files...")
            self._process_additional_files(movie_info.full_title, dest_dir, decryption_key)
            self.logger.debug("Additional file processing completed")
            
        except Exception as e:
            self.logger.error(f"Download/decrypt failed: {e}")
            raise
    
    def _process_additional_files(self, title: str, dest_dir: str, decryption_key: str):
        """
        Processes subtitle and audio files
        
        Args:
            title (str): Movie title
            dest_dir (str): Destination directory for processed files
            decryption_key (str): Decryption key for audio files
        """
        self.logger.debug(f"Processing additional files for: {title}")
        self.logger.debug(f"Destination directory: {dest_dir}")
        
        regex_pattern = re.escape(title) + r"\.[a-z]{2,}\.m4a"
        self.logger.debug(f"Using audio file pattern: {regex_pattern}")
        
        processed_files = []
        
        for filename in os.listdir(self.download_folder):
            src_path = os.path.join(self.download_folder, filename)
            
            # Move subtitle files
            if filename.endswith(".srt") and title in filename:
                self.logger.debug(f"Found subtitle file: {filename}")
                dest_path = os.path.join(dest_dir, filename)
                try:
                    shutil.move(src_path, dest_path)
                    self.logger.debug(f"Moved subtitle file to: {dest_path}")
                    processed_files.append(dest_path)
                except Exception as e:
                    self.logger.error(f"Failed to move subtitle file: {str(e)}")
            
            # Process audio files
            if re.match(regex_pattern, filename):
                lang_match = re.search(re.escape(title) + r"\.([a-zA-Z]{2,})\.m4a", filename)
                if lang_match:
                    lang = lang_match.group(1)
                    self.logger.debug(f"Found audio track for language: {lang}")
                    
                    output_path = os.path.join(dest_dir, f"decrypted-audio.{lang}.m4a")
                    decrypt_cmd = f'shaka-packager in="{src_path}",' \
                                f'stream=audio,output="{output_path}" ' \
                                f'--enable_raw_key_decryption --keys {decryption_key}'
                    
                    self.logger.debug(f"Decrypting audio track: {lang}")
                    self.logger.debug(f"Decryption command: {decrypt_cmd}")
                    os.system(decrypt_cmd)
                    
                    if os.path.exists(output_path):
                        self.logger.debug(f"Successfully decrypted audio track: {lang}")
                        processed_files.append(output_path)
                        os.remove(src_path)
                        self.logger.debug(f"Removed encrypted audio file: {src_path}")
                    else:
                        self.logger.error(f"Failed to decrypt audio track: {lang}")
                    
        # Cleanup
        src_video = os.path.join(self.download_folder, f"{title}.mp4")
        if os.path.exists(src_video):
            self.logger.debug(f"Removing source video file: {src_video}")
            os.remove(src_video)
        
        self.logger.debug(f"Processed files: {processed_files}")

def setup_logging(debug: bool = False):
    """
    Configures logging for the application
    
    Args:
        debug (bool): Enable debug logging
    """
    level = logging.DEBUG if debug else logging.INFO
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        format=log_format,
        handlers=[
            logging.StreamHandler()
        ]
    )
    
    # Add file handler for all levels
    file_handler = logging.FileHandler('mubi_downloader.log')
    file_handler.setFormatter(logging.Formatter(log_format))
    file_handler.setLevel(level)
    logging.getLogger().addHandler(file_handler)
