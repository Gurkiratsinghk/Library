import gspread
from google.oauth2.service_account import Credentials
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
import socket
import logging
import json
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from datetime import datetime

@dataclass
class BookMetadata:
    """Data class for book metadata."""
    title: str = ""
    authors: str = ""
    publisher: str = ""
    published_date: str = ""
    isbn: str = ""
    categories: str = ""
    page_count: int = 0
    language: str = ""
    description: str = ""

class BookMetadataUpdater:
    def __init__(self, config_file: str = 'config.json', credentials_file: str = 'credentials.json'):
        """
        Initialize the Book Metadata Updater.
        
        Args:
            config_file: Path to configuration file
            credentials_file: Path to Google credentials file
        """
        self.config = self._load_config(config_file)
        self.credentials_file = credentials_file
        
        # Setup logging
        self._setup_logging()
        
        # API configurations
        self.SCOPES = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        self.GOOGLE_BOOKS_API_URL = "https://www.googleapis.com/books/v1/volumes"
        self.OPEN_LIBRARY_API_URL = "https://openlibrary.org/search.json"
        
        # Configure retry strategy
        self.retry_strategy = Retry(
            total=self.config.get('retry_attempts', 5),
            backoff_factor=self.config.get('backoff_factor', 1),
            status_forcelist=[429, 500, 502, 503, 504],  # Added 429 for rate limiting
            allowed_methods=["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"]
        )
        
        # Create session with retry strategy
        self.http = requests.Session()
        self.http.mount("https://", HTTPAdapter(max_retries=self.retry_strategy))
        
        # Rate limiting
        self._api_lock = threading.Lock()
        self._last_request_time = {}
        
        # Progress tracking
        self.processed_count = 0
        self.updated_count = 0
        self.failed_count = 0

    def _load_config(self, config_file: str) -> Dict:
        """Load configuration from JSON file."""
        default_config = {
            "retry_attempts": 5,
            "backoff_factor": 1,
            "rate_limit_delay": 1.0,
            "max_workers": 3,
            "batch_size": 10,
            "spreadsheet_name": "Books list",
            "sheet_name": "Books",
            "log_level": "INFO",
            "backup_enabled": True,
            "field_mapping": {
                "Title": "title",
                "Author": "authors", 
                "Genre": "categories",
                "Publisher": "publisher",
                "Publication Year": "published_date",
                "ISBN": "isbn",
                "Pages": "page_count",
                "Language": "language",
                "Description": "description"
            }
        }
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
            except Exception as e:
                print(f"Warning: Could not load config file {config_file}: {e}")
                print("Using default configuration.")
        else:
            # Create default config file
            with open(config_file, 'w') as f:
                json.dump(default_config, f, indent=2)
            print(f"Created default config file: {config_file}")
        
        return default_config

    def _setup_logging(self):
        """Setup logging configuration."""
        log_level = getattr(logging, self.config.get('log_level', 'INFO').upper())
        
        # Create logs directory if it doesn't exist
        os.makedirs('logs', exist_ok=True)
        
        # Setup file handler with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = f'logs/book_updater_{timestamp}.log'
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Logging initialized. Log file: {log_file}")

    def check_internet_connection(self) -> bool:
        """Test internet connectivity with multiple endpoints."""
        test_endpoints = [
            ("8.8.8.8", 53),      # Google DNS
            ("1.1.1.1", 53),      # Cloudflare DNS
            ("208.67.222.222", 53) # OpenDNS
        ]
        
        for host, port in test_endpoints:
            try:
                socket.create_connection((host, port), timeout=3)
                return True
            except OSError:
                continue
        return False

    def authenticate_google_sheets(self):
        """Authenticate with Google Sheets API using service account."""
        if not self.check_internet_connection():
            raise ConnectionError("No internet connection available.")
            
        if not os.path.exists(self.credentials_file):
            raise FileNotFoundError(f"Credentials file '{self.credentials_file}' not found.")
            
        try:
            creds = Credentials.from_service_account_file(
                self.credentials_file,
                scopes=self.SCOPES
            )
            return gspread.authorize(creds)
        except Exception as e:
            self.logger.error(f"Authentication failed: {str(e)}")
            raise

    def _rate_limit(self, api_name: str):
        """Implement rate limiting for API calls."""
        with self._api_lock:
            now = time.time()
            if api_name in self._last_request_time:
                elapsed = now - self._last_request_time[api_name]
                min_delay = self.config.get('rate_limit_delay', 1.0)
                if elapsed < min_delay:
                    time.sleep(min_delay - elapsed)
            self._last_request_time[api_name] = time.time()

    def get_google_books_data(self, title: str, author: str = "") -> Optional[BookMetadata]:
        """Fetch book metadata from Google Books API with enhanced search."""
        if not title:
            return None
            
        self._rate_limit('google_books')
        
        try:
            # Enhanced search query
            query = f'intitle:"{title}"'
            if author:
                query += f' inauthor:"{author}"'
                
            params = {
                'q': query, 
                'maxResults': 5,  # Get more results for better matching
                'printType': 'books'
            }
            
            response = self.http.get(self.GOOGLE_BOOKS_API_URL, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            if 'items' in data and len(data['items']) > 0:
                # Find best match by title similarity
                best_match = self._find_best_book_match(title, data['items'])
                if best_match:
                    book_info = best_match['volumeInfo']
                    
                    # Extract ISBN (prefer ISBN-13, fallback to ISBN-10)
                    isbn = ""
                    for identifier in book_info.get('industryIdentifiers', []):
                        if identifier['type'] == 'ISBN_13':
                            isbn = identifier['identifier']
                            break
                        elif identifier['type'] == 'ISBN_10' and not isbn:
                            isbn = identifier['identifier']
                    
                    return BookMetadata(
                        title=book_info.get('title', ''),
                        authors=', '.join(book_info.get('authors', [])),
                        publisher=book_info.get('publisher', ''),
                        published_date=self._extract_year(book_info.get('publishedDate', '')),
                        isbn=isbn,
                        categories=', '.join(book_info.get('categories', [])),
                        page_count=book_info.get('pageCount', 0),
                        language=book_info.get('language', ''),
                        description=book_info.get('description', '')[:500] + '...' if len(book_info.get('description', '')) > 500 else book_info.get('description', '')
                    )
            return None
            
        except requests.RequestException as e:
            self.logger.error(f"Error fetching Google Books data for '{title}': {e}")
            return None

    def get_open_library_data(self, title: str, author: str = "") -> Optional[BookMetadata]:
        """Fetch book metadata from Open Library API with enhanced search."""
        if not title:
            return None
            
        self._rate_limit('open_library')
        
        try:
            params = {
                'title': title,
                'limit': 5
            }
            if author:
                params['author'] = author
                
            response = self.http.get(self.OPEN_LIBRARY_API_URL, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            if 'docs' in data and len(data['docs']) > 0:
                # Find best match
                best_match = self._find_best_book_match(title, data['docs'], 'title')
                if best_match:
                    return BookMetadata(
                        title=best_match.get('title', ''),
                        authors=', '.join(best_match.get('author_name', [])),
                        publisher=', '.join(best_match.get('publisher', [])[:3]),  # Limit publishers
                        published_date=str(best_match.get('first_publish_year', '')),
                        isbn=next(iter(best_match.get('isbn', [])), ''),
                        categories=', '.join(best_match.get('subject', [])[:5]),  # Limit subjects
                        page_count=best_match.get('number_of_pages_median', 0),
                        language=', '.join(best_match.get('language', [])[:2])  # Limit languages
                    )
            return None
            
        except requests.RequestException as e:
            self.logger.error(f"Error fetching Open Library data for '{title}': {e}")
            return None

    def _find_best_book_match(self, target_title: str, items: List[Dict], title_key: str = None) -> Optional[Dict]:
        """Find the best matching book from search results."""
        if not items:
            return None
            
        target_title_lower = target_title.lower().strip()
        best_match = None
        best_score = 0
        
        for item in items:
            if title_key:
                item_title = item.get(title_key, '')
            else:
                item_title = item.get('volumeInfo', {}).get('title', '')
                
            if not item_title:
                continue
                
            item_title_lower = item_title.lower().strip()
            
            # Calculate similarity score
            score = self._calculate_title_similarity(target_title_lower, item_title_lower)
            
            if score > best_score:
                best_score = score
                best_match = item
                
        # Only return match if similarity is above threshold
        return best_match if best_score > 0.6 else items[0]  # Fallback to first result

    def _calculate_title_similarity(self, title1: str, title2: str) -> float:
        """Calculate similarity between two titles."""
        # Simple similarity calculation based on common words
        words1 = set(title1.split())
        words2 = set(title2.split())
        
        if not words1 or not words2:
            return 0.0
            
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union) if union else 0.0

    def _extract_year(self, date_string: str) -> str:
        """Extract year from date string."""
        if not date_string:
            return ""
        
        # Try to extract 4-digit year
        import re
        year_match = re.search(r'\b(19|20)\d{2}\b', date_string)
        return year_match.group() if year_match else date_string[:4]

    def merge_metadata(self, google_data: Optional[BookMetadata], 
                      open_library_data: Optional[BookMetadata]) -> Optional[BookMetadata]:
        """Merge metadata from both APIs with intelligent preference."""
        if not google_data and not open_library_data:return None
            
        # Start with Google Books data (generally more reliable)
        if google_data:
            merged = google_data
        else:
            merged = open_library_data
            return merged
            
        # Fill in missing fields from Open Library
        if open_library_data:
            if not merged.authors and open_library_data.authors:
                merged.authors = open_library_data.authors
            if not merged.publisher and open_library_data.publisher:
                merged.publisher = open_library_data.publisher
            if not merged.published_date and open_library_data.published_date:
                merged.published_date = open_library_data.published_date
            if not merged.isbn and open_library_data.isbn:
                merged.isbn = open_library_data.isbn
            if not merged.categories and open_library_data.categories:
                merged.categories = open_library_data.categories
            if not merged.page_count and open_library_data.page_count:
                merged.page_count = open_library_data.page_count
            if not merged.language and open_library_data.language:
                merged.language = open_library_data.language
                
        return merged

    def backup_sheet(self, worksheet) -> str:
        """Create a backup of the current sheet data."""
        if not self.config.get('backup_enabled', True):
            return ""
            
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_dir = 'backups'
            os.makedirs(backup_dir, exist_ok=True)
            
            backup_file = f"{backup_dir}/sheet_backup_{timestamp}.json"
            
            records = worksheet.get_all_records()
            with open(backup_file, 'w') as f:
                json.dump(records, f, indent=2)
                
            self.logger.info(f"Backup created: {backup_file}")
            return backup_file
            
        except Exception as e:
            self.logger.error(f"Failed to create backup: {e}")
            return ""

    def process_book_batch(self, books_batch: List[Tuple[int, Dict]]) -> List[Tuple[int, Dict, Optional[BookMetadata]]]:
        """Process a batch of books concurrently."""
        results = []
        
        with ThreadPoolExecutor(max_workers=min(len(books_batch), self.config.get('max_workers', 3))) as executor:
            future_to_book = {
                executor.submit(self._process_single_book, row_idx, book): (row_idx, book)
                for row_idx, book in books_batch
            }
            
            for future in as_completed(future_to_book):
                row_idx, book = future_to_book[future]
                try:
                    metadata = future.result()
                    results.append((row_idx, book, metadata))
                except Exception as e:
                    self.logger.error(f"Error processing book '{book.get('Title', '')}': {e}")
                    results.append((row_idx, book, None))
                    
        return results

    def _process_single_book(self, row_idx: int, book: Dict) -> Optional[BookMetadata]:
        """Process a single book to get metadata."""
        title = str(book.get('Title', '')).strip()
        author = str(book.get('Author', '')).strip()
        
        if not title:
            return None
            
        self.logger.info(f"Processing: {title}")
        
        # Get metadata from both APIs
        google_data = self.get_google_books_data(title, author)
        open_library_data = self.get_open_library_data(title, author)
        
        # Merge metadata
        merged_data = self.merge_metadata(google_data, open_library_data)
        
        self.processed_count += 1
        
        if merged_data:
            self.logger.info(f"Found metadata for: {title}")
        else:
            self.logger.warning(f"No metadata found for: {title}")
            self.failed_count += 1
            
        return merged_data

    def update_sheet(self, spreadsheet_name: str = None, sheet_name: str = None, 
                    dry_run: bool = False) -> bool:
        """
        Update Google Sheet with merged metadata.
        
        Args:
            spreadsheet_name: Name of the Google Spreadsheet
            sheet_name: Name of the worksheet
            dry_run: If True, only simulate updates without making changes
            
        Returns:
            bool: True if successful, False otherwise
        """
        spreadsheet_name = spreadsheet_name or self.config.get('spreadsheet_name', 'Books list')
        sheet_name = sheet_name or self.config.get('sheet_name', 'Books')
        
        try:
            # Check internet connection
            if not self.check_internet_connection():
                self.logger.error("No internet connection available.")
                return False

            # Connect to Google Sheets
            self.logger.info("Authenticating with Google Sheets...")
            gc = self.authenticate_google_sheets()
            
            self.logger.info(f"Opening spreadsheet '{spreadsheet_name}'...")
            spreadsheet = gc.open(spreadsheet_name)
            worksheet = spreadsheet.worksheet(sheet_name)
            
            # Create backup
            backup_file = self.backup_sheet(worksheet)
            
            # Get all records
            self.logger.info("Fetching existing records...")
            records = worksheet.get_all_records()
            
            if not records:
                self.logger.warning("No records found in the sheet.")
                return False
            
            # Reset counters
            self.processed_count = 0
            self.updated_count = 0
            self.failed_count = 0
            
            total_books = len(records)
            batch_size = self.config.get('batch_size', 10)
            
            self.logger.info(f"Processing {total_books} books in batches of {batch_size}")
            
            # Process books in batches
            for i in range(0, total_books, batch_size):
                batch_end = min(i + batch_size, total_books)
                batch = [(i + j + 2, records[i + j]) for j in range(batch_end - i)]  # +2 for header row
                
                self.logger.info(f"Processing batch {i//batch_size + 1}/{(total_books + batch_size - 1)//batch_size}")
                
                batch_results = self.process_book_batch(batch)
                
                # Update sheet with batch results
                for row_idx, book, metadata in batch_results:
                    if metadata:
                        success = self._update_book_row(worksheet, row_idx, book, metadata, dry_run)
                        if success:
                            self.updated_count += 1
                
                # Progress update
                progress = min(batch_end, total_books)
                self.logger.info(f"Progress: {progress}/{total_books} books processed")
            
            # Final summary
            self.logger.info(f"Update completed! Processed: {self.processed_count}, "
                           f"Updated: {self.updated_count}, Failed: {self.failed_count}")
            
            if backup_file:
                self.logger.info(f"Backup saved to: {backup_file}")
                
            return True
            
        except gspread.exceptions.SpreadsheetNotFound:
            self.logger.error(f"Spreadsheet '{spreadsheet_name}' not found. Check name and permissions.")
            return False
        except gspread.exceptions.WorksheetNotFound:
            self.logger.error(f"Worksheet '{sheet_name}' not found.")
            return False
        except Exception as e:
            self.logger.error(f"Error updating sheet: {e}")
            return False

    def _update_book_row(self, worksheet, row_idx: int, book: Dict, 
                        metadata: BookMetadata, dry_run: bool = False) -> bool:
        """Update a single book row with metadata."""
        try:
            field_mapping = self.config.get('field_mapping', {})
            updates = []
            
            # Check which fields need updating
            for sheet_field, metadata_field in field_mapping.items():
                current_value = str(book.get(sheet_field, '')).strip()
                new_value = str(getattr(metadata, metadata_field, '')).strip()
                
                if not current_value and new_value:
                    updates.append((sheet_field, new_value))
            
            if not updates:
                self.logger.debug(f"No updates needed for: {book.get('Title', '')}")
                return False
            
            if dry_run:
                self.logger.info(f"DRY RUN - Would update {book.get('Title', '')} with: {updates}")
                return True
            
            # Apply updates
            for field, value in updates:
                try:
                    col_idx = worksheet.find(field).col
                    worksheet.update_cell(row_idx, col_idx, value)
                    self.logger.debug(f"Updated {field}: {value}")
                except Exception as e:
                    self.logger.error(f"Error updating {field}: {e}")
                    return False
            
            self.logger.info(f"Successfully updated: {book.get('Title', '')}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating row {row_idx}: {e}")
            return False

    def validate_sheet_structure(self, spreadsheet_name: str = None, 
                                sheet_name: str = None) -> bool:
        """Validate that the sheet has the expected structure."""
        try:
            gc = self.authenticate_google_sheets()
            spreadsheet = gc.open(spreadsheet_name or self.config.get('spreadsheet_name'))
            worksheet = spreadsheet.worksheet(sheet_name or self.config.get('sheet_name'))
            
            headers = worksheet.row_values(1)
            required_fields = list(self.config.get('field_mapping', {}).keys())
            
            missing_fields = [field for field in required_fields if field not in headers]
            
            if missing_fields:
                self.logger.error(f"Missing required fields in sheet: {missing_fields}")
                return False
                
            self.logger.info("Sheet structure validation passed.")
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating sheet structure: {e}")
            return False

def main():
    """Main function with command line interface."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Update book metadata in Google Sheets")
    parser.add_argument('--config', default='config.json', help='Configuration file path')
    parser.add_argument('--credentials', default='credentials.json', help='Google credentials file path')
    parser.add_argument('--spreadsheet', help='Spreadsheet name (overrides config)')
    parser.add_argument('--sheet', help='Sheet name (overrides config)')
    parser.add_argument('--dry-run', action='store_true', help='Simulate updates without making changes')
    parser.add_argument('--validate', action='store_true', help='Only validate sheet structure')
    
    args = parser.parse_args()
    
    try:
        updater = BookMetadataUpdater(args.config, args.credentials)
        
        if args.validate:
            success = updater.validate_sheet_structure(args.spreadsheet, args.sheet)
            return 0 if success else 1
        
        success = updater.update_sheet(args.spreadsheet, args.sheet, args.dry_run)
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        return 1
    except Exception as e:
        print(f"Fatal error: {e}")
        return 1

if __name__ == "__main__":
    exit(main())