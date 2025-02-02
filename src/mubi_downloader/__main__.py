#!/usr/bin/env python3
import sys
import os
import argparse
import logging
from typing import Optional

from .mubi_downloader import MovieSearch, DownloadManager, setup_logging
from .auth_manager import AuthManager
from .environment import EnvironmentDetector

BROWSERS = ['chrome', 'firefox', 'edge']

def get_browser_choice() -> str:
    """Interactive browser selection"""
    print("\nAvailable browsers:")
    for i, browser in enumerate(BROWSERS, 1):
        print(f"{i}. {browser.title()}")
    
    while True:
        try:
            choice = input("\nSelect your browser (1-3): ")
            idx = int(choice) - 1
            if 0 <= idx < len(BROWSERS):
                return BROWSERS[idx]
            print("Please enter a number between 1 and 3")
        except ValueError:
            print("Please enter a valid number")

def main():
    """Main CLI entry point"""
    prog_name = os.path.basename(sys.argv[0])
    if prog_name == '__main__.py':
        prog_name = 'mubi-downloader'
        
    parser = argparse.ArgumentParser(
        description='Mubi Downloader - Download movies from Mubi',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        prog=prog_name,
        epilog="""
Examples:
  %(prog)s                    # Interactive mode with browser selection
  %(prog)s -b chrome         # Use Chrome browser
  %(prog)s -b firefox -o movies    # Use Firefox and custom output directory
  %(prog)s --debug          # Enable debug logging
        """
    )
    
    parser.add_argument(
        '-b', '--browser',
        choices=BROWSERS,
        metavar='BROWSER',
        help=f'Browser to extract cookies from ({", ".join(BROWSERS)})'
    )
    
    parser.add_argument(
        '-o', '--output',
        default='download',
        metavar='DIR',
        help='Output directory for downloaded files'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    args = parser.parse_args()

    # Setup logging
    setup_logging(args.debug)
    logger = logging.getLogger('main')
    logger.debug("Starting Mubi Downloader in debug mode" if args.debug else "Starting Mubi Downloader")

    try:
        # Get browser choice if not provided
        browser = args.browser or get_browser_choice()
        
        # Initialize environment detector
        env = EnvironmentDetector(debug=args.debug)
        
        # Check for WSL2 environment
        if env.is_wsl:
            cookie_path = env.get_wsl_cookie_path(browser)
            if cookie_path:
                logger.debug(f"Using WSL2 cookie path: {cookie_path}")
                os.environ['BROWSER_COOKIE_PATH'] = cookie_path

        # Initialize components
        auth_manager = AuthManager(browser, debug=args.debug)
        movie_search = MovieSearch()
        download_manager = DownloadManager(auth_manager, args.output)
        logger.debug("Initialized all managers")
        
        # Get user's location
        user_country = movie_search.get_user_location()
        logger.debug(f"Detected user country: {user_country}")
        
        # Search for movie
        query = input("\nEnter movie name: ")
        logger.debug(f"Searching for movie: {query}")
        movie_info = movie_search.search_movie(query)
        
        if not movie_info:
            logger.error("No movie information available")
            return 1
        
        logger.info(f"\nFound movie: {movie_info.full_title}")
        logger.debug(f"Movie details: {vars(movie_info)}")
        
        # Check availability
        if user_country in movie_info.available_countries:
            logger.info(f"Movie is available in your location ({user_country})")
            logger.debug(f"Available countries: {movie_info.available_countries}")
            print(f"\nPlease open {movie_info.mubi_url} in your browser and start playing the movie")
            input("\nPress Enter when ready to proceed with download")
        else:
            logger.error(f"Movie is not available in {user_country}")
            print(f"Available in: {', '.join(movie_info.available_countries)}")
            return 1
        
        # Download and decrypt
        logger.debug(f"Starting download and decryption for: {movie_info.full_title}")
        logger.debug(f"Using download folder: {download_manager.download_folder}")
        output_dir = os.path.join(download_manager.download_folder, movie_info.full_title)
        logger.debug(f"Output directory will be: {output_dir}")
        
        try:
            download_manager.download_and_decrypt(movie_info)
            logger.info("Download and decryption completed successfully")
            logger.debug(f"Files saved to: {output_dir}")
        except Exception as e:
            logger.error(f"Download/decrypt failed: {e}")
            if args.debug:
                logger.exception("Detailed error information:")
            return 1
        
        return 0
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 1
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        if args.debug:
            logger.exception("Detailed error information:")
        return 1

if __name__ == "__main__":
    sys.exit(main())