#!/usr/bin/env python3
import os
import logging
from typing import List, Optional
from dataclasses import dataclass
import subprocess
import glob
import shutil

@dataclass
class MediaFile:
    """Data class for media file information"""
    path: str
    type: str  # 'video', 'audio', or 'subtitle'
    language: Optional[str] = None

class MkvMerger:
    """
    Handles the merging of video, audio, and subtitle files into MKV format.
    Uses mkvmerge for combining media files.
    """
    
    def __init__(self, output_dir: str = "output"):
        """
        Initialize MkvMerger with output directory.
        
        Args:
            output_dir (str): Directory where merged files will be saved
        """
        self.output_dir = output_dir
        self.logger = self._setup_logging()
        os.makedirs(output_dir, exist_ok=True)
    
    def _setup_logging(self) -> logging.Logger:
        """
        Sets up logging configuration.
        
        Returns:
            logging.Logger: Configured logger instance
        """
        logger = logging.getLogger('MkvMerger')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
            # Add file handler
            file_handler = logging.FileHandler('mkv_merger.log')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        
        return logger

    def collect_media_files(self, input_dir: str) -> List[MediaFile]:
        """
        Collects all relevant media files from the input directory.
        
        Args:
            input_dir (str): Directory containing the media files
            
        Returns:
            List[MediaFile]: List of found media files with their types
        """
        media_files = []
        
        # Find video file
        video_files = glob.glob(os.path.join(input_dir, "*video*.mp4"))
        if video_files:
            media_files.append(MediaFile(video_files[0], 'video'))
        
        # Find audio files
        for audio_file in glob.glob(os.path.join(input_dir, "*audio*.m4a")):
            lang = self._extract_language_code(audio_file)
            media_files.append(MediaFile(audio_file, 'audio', lang))
        
        # Find subtitle files
        for subtitle_file in glob.glob(os.path.join(input_dir, "*.srt")):
            lang = self._extract_language_code(subtitle_file)
            media_files.append(MediaFile(subtitle_file, 'subtitle', lang))
        
        return media_files

    def _extract_language_code(self, filename: str) -> Optional[str]:
        """
        Extracts language code from filename.
        
        Args:
            filename (str): Name of the file
            
        Returns:
            Optional[str]: Two-letter language code if found, None otherwise
        """
        import re
        match = re.search(r'\.([a-z]{2})\.(m4a|srt)$', filename.lower())
        return match.group(1) if match else None

    def merge_to_mkv(self, 
                     media_files: List[MediaFile], 
                     output_name: str,
                     default_audio_lang: str = 'eng') -> bool:
        """
        Merges media files into an MKV container.
        
        Args:
            media_files (List[MediaFile]): List of media files to merge
            output_name (str): Name for the output file
            default_audio_lang (str): Default language for audio tracks
            
        Returns:
            bool: True if merge was successful, False otherwise
            
        Raises:
            ValueError: If no video file is found in the media files
        """
        try:
            # Add video track
            video_file = next((f for f in media_files if f.type == 'video'), None)
            if not video_file:
                raise ValueError("No video file found")
                
            # Prepare output path
            output_path = os.path.join(self.output_dir, f"{output_name}.mkv")
            
            # Build mkvmerge command
            cmd = ['mkvmerge', '-o', output_path]
            cmd.extend([video_file.path])
            
            # Add audio tracks
            audio_files = [f for f in media_files if f.type == 'audio']
            for audio in audio_files:
                cmd.extend([
                    '--language', f'0:{audio.language or default_audio_lang}',
                    '--track-name', f'0:Audio ({audio.language or default_audio_lang})',
                    '(', audio.path, ')'
                ])
            
            # Add subtitle tracks
            subtitle_files = [f for f in media_files if f.type == 'subtitle']
            for sub in subtitle_files:
                cmd.extend([
                    '--language', f'0:{sub.language or "eng"}',
                    '--track-name', f'0:Subtitles ({sub.language or "eng"})',
                    '(', sub.path, ')'
                ])
            
            # Execute merge command
            self.logger.info(f"Merging files into: {output_path}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                self.logger.error(f"Merge failed: {result.stderr}")
                return False
            
            self.logger.info("Merge completed successfully")
            return True
            
        except ValueError as e:
            self.logger.error(f"Error during merge: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Error during merge: {str(e)}")
            return False

    def cleanup_source_files(self, media_files: List[MediaFile], cleanup: bool = False):
        """
        Optionally removes source files after successful merge.
        
        Args:
            media_files (List[MediaFile]): List of files to clean up
            cleanup (bool): Whether to perform cleanup
        """
        if cleanup:
            self.logger.info("Cleaning up source files...")
            for media_file in media_files:
                try:
                    os.remove(media_file.path)
                    self.logger.debug(f"Removed: {media_file.path}")
                except Exception as e:
                    self.logger.warning(f"Failed to remove {media_file.path}: {str(e)}")

def main():
    """
    Main entry point for testing the MKV merger functionality.
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Merge media files into MKV format')
    parser.add_argument('input_dir', help='Directory containing media files')
    parser.add_argument('output_name', help='Name for the output file')
    parser.add_argument('--cleanup', action='store_true', help='Clean up source files after merge')
    args = parser.parse_args()
    
    merger = MkvMerger()
    media_files = merger.collect_media_files(args.input_dir)
    
    if not media_files:
        print("No media files found")
        return
    
    print(f"Found {len(media_files)} media files")
    success = merger.merge_to_mkv(media_files, args.output_name)
    
    if success and args.cleanup:
        merger.cleanup_source_files(media_files, True)

if __name__ == "__main__":
    main()