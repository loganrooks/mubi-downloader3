#!/usr/bin/env python3
import sys
import os
import argparse
import logging
from typing import Optional
from .mubi_downloader import MovieSearch, DownloadManager, setup_logging
from .auth_manager import AuthManager

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

def get_wsl_cookie_path(browser: str) -> Optional[str]:
    """Get the cookie path for browsers in WSL2"""
    windows_home = None
    
    # Try to get Windows username from environment
    if 'USERPROFILE' in os.environ:
        windows_home = os.environ['USERPROFILE'].replace('\\', '/')
        if windows_home.startswith('C:'):
            windows_home = f"/mnt/c{windows_home[2:]}"
    
    # If not found, try to detect from /mnt/c/Users
    if not windows_home and os.path.exists('/mnt/c/Users'):
        try:
            users = os.listdir('/mnt/c/Users')
            # Filter out default Windows folders
            users = [u for u in users if u not in ['Public', 'Default', 'Default User', 'All Users']]
            if len(users) == 1:
                windows_home = f'/mnt/c/Users/{users[0]}'
        except (FileNotFoundError, PermissionError):
            pass
    
    if windows_home:
        cookie_paths = {
            'chrome': f"{windows_home}/AppData/Local/Google/Chrome/User Data/Default/Cookies",
            'firefox': f"{windows_home}/AppData/Roaming/Mozilla/Firefox/Profiles",
            'edge': f"{windows_home}/AppData/Local/Microsoft/Edge/User Data/Default/Cookies"
        }
        return cookie_paths.get(browser)
    return None

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
  %(prog)s                          # Interactive mode with browser selection
  %(prog)s -b chrome               # Use Chrome browser
  %(prog)s -b firefox -o movies    # Use Firefox and custom output directory
  %(prog)s -v                      # Enable verbose logging
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
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()

    # Setup logging
    setup_logging(level=logging.DEBUG if args.verbose else logging.INFO)
    logger = logging.getLogger('main')

    try:
        # Get browser choice if not provided
        browser = args.browser or get_browser_choice()
        
        # Check for WSL2 environment
        cookie_path = get_wsl_cookie_path(browser)
        if cookie_path:
            logger.info(f"Using WSL2 cookie path: {cookie_path}")
            os.environ['BROWSER_COOKIE_PATH'] = cookie_path

        # Initialize components
        auth_manager = AuthManager(browser)
        movie_search = MovieSearch()
        download_manager = DownloadManager(auth_manager, args.output)
        
        # Get user's location
        user_country = movie_search.get_user_location()
        
        # Search for movie
        query = input("\nEnter movie name: ")
        movie_info = movie_search.search_movie(query)
        
        if not movie_info:
            logger.error("No movie information available")
            return 1
        
        logger.info(f"\nFound movie: {movie_info.full_title}")
        
        # Check availability
        if user_country in movie_info.available_countries:
            logger.info(f"Movie is available in your location ({user_country})")
            print(f"\nPlease open {movie_info.mubi_url} in your browser and start playing the movie")
            input("\nPress Enter when ready to proceed with download")
        else:
            logger.error(f"Movie is not available in {user_country}")
            print(f"Available in: {', '.join(movie_info.available_countries)}")
            return 1
        
        # Download and decrypt
        download_manager.download_and_decrypt(movie_info)
        logger.info("Download and decryption completed successfully")
        return 0
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 1
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        if args.verbose:
            logger.exception(e)
        return 1

if __name__ == "__main__":
    sys.exit(main())