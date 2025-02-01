#!/usr/bin/env python3
import sys
import requests
import json
import os
import logging
from urllib.request import urlopen
import glob
import re
import base64
import shutil
import time
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
            decryption_key, secure_url = self._get_encryption_info(
                f'https://api.mubi.com/v3/films/{movie_info.film_id}/viewing/secure_url'
            )
            
            # Download video
            dest_dir = os.path.join(self.download_folder, movie_info.full_title)
            os.makedirs(dest_dir, exist_ok=True)
            
            self.logger.info("Downloading video...")
            os.system(f'N_m3u8DL-RE "{secure_url}" --auto-select --save-name "{movie_info.full_title}" '
                     f'--save-dir {self.download_folder} --tmp-dir {self.download_folder}/temp')
            
            # Decrypt video
            self.logger.info("Decrypting video...")
            os.system(f'shaka-packager in="{self.download_folder}/{movie_info.full_title}.mp4",'
                     f'stream=video,output="{dest_dir}/decrypted-video.mp4" '
                     f'--enable_raw_key_decryption --keys {decryption_key}')
            
            # Process subtitles and audio
            self._process_additional_files(movie_info.full_title, dest_dir, decryption_key)
            
        except Exception as e:
            self.logger.error(f"Download/decrypt failed: {e}")
            raise
    
    def _process_additional_files(self, title: str, dest_dir: str, decryption_key: str):
        """Processes subtitle and audio files"""
        regex_pattern = re.escape(title) + r"\.[a-z]{2,}\.m4a"
        
        for filename in os.listdir(self.download_folder):
            # Move subtitle files
            if filename.endswith(".srt") and title in filename:
                shutil.move(
                    os.path.join(self.download_folder, filename),
                    os.path.join(dest_dir, filename)
                )
            
            # Process audio files
            if re.match(regex_pattern, filename):
                lang_match = re.search(re.escape(title) + r"\.([a-zA-Z]{2,})\.m4a", filename)
                if lang_match:
                    lang = lang_match.group(1)
                    os.system(f'shaka-packager in="{self.download_folder}/{title}.{lang}.m4a",'
                            f'stream=audio,output="{dest_dir}/decrypted-audio.{lang}.m4a" '
                            f'--enable_raw_key_decryption --keys {decryption_key}')
                    os.remove(f"{self.download_folder}/{title}.{lang}.m4a")
                    
        # Cleanup
        if os.path.exists(f"{self.download_folder}/{title}.mp4"):
            os.remove(f"{self.download_folder}/{title}.mp4")

def setup_logging():
    """Configures logging for the application"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('mubi_downloader.log')
        ]
    )

def main():
    """Main entry point for the Mubi downloader"""
    setup_logging()
    logger = logging.getLogger('main')
    
    try:
        auth_manager = AuthManager()
        movie_search = MovieSearch()
        download_manager = DownloadManager(auth_manager)
        
        # Get user's location
        user_country = movie_search.get_user_location()
        
        # Search for movie
        query = input("Enter movie name: ")
        movie_info = movie_search.search_movie(query)
        
        if not movie_info:
            logger.error("No movie information available")
            return
        
        logger.info(f"Found movie: {movie_info.full_title}")
        
        # Check availability
        if user_country in movie_info.available_countries:
            logger.info(f"Movie is available in your location ({user_country})")
            print(f"Please open {movie_info.mubi_url} in your browser and start playing the movie")
            input("Press Enter when ready to proceed with download")
        else:
            logger.error(f"Movie is not available in {user_country}")
            print(f"Available in: {', '.join(movie_info.available_countries)}")
            return
        
        # Download and decrypt
        download_manager.download_and_decrypt(movie_info)
        logger.info("Download and decryption completed successfully")
        
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
