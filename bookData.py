import gspread
from google.oauth2.service_account import Credentials
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
import socket
import urllib3

class BookMetadataUpdater:
    def __init__(self):
        self.SCOPES = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        self.GOOGLE_BOOKS_API_URL = "https://www.googleapis.com/books/v1/volumes"
        self.OPEN_LIBRARY_API_URL = "https://openlibrary.org/search.json"
        
        # Configure retry strategy
        self.retry_strategy = Retry(
            total=5,  # number of retries
            backoff_factor=1,  # wait 1, 2, 4, 8, 16 seconds between retries
            status_forcelist=[500, 502, 503, 504],  # HTTP status codes to retry on
            allowed_methods=["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"]
        )
        # Create session with retry strategy
        self.http = requests.Session()
        self.http.mount("https://", HTTPAdapter(max_retries=self.retry_strategy))
        
    def check_internet_connection(self):
        """Test internet connectivity."""
        try:
            # Try to resolve Google's DNS
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except OSError:
            return False

    def authenticate_google_sheets(self):
        """Authenticate with Google Sheets API using service account."""
        if not self.check_internet_connection():
            raise ConnectionError("No internet connection available. Please check your connection and try again.")
            
        try:
            creds = Credentials.from_service_account_file(
                'credentials.json',
                scopes=self.SCOPES
            )
            return gspread.authorize(creds)
        except Exception as e:
            raise Exception(f"Authentication failed: {str(e)}")

    def get_google_books_data(self, title):
        """Fetch book metadata from Google Books API with retries."""
        if not title:
            return None
            
        try:
            params = {'q': title, 'maxResults': 1}
            response = self.http.get(self.GOOGLE_BOOKS_API_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if 'items' in data and len(data['items']) > 0:
                book_info = data['items'][0]['volumeInfo']
                return {
                    'title': book_info.get('title', ''),
                    'authors': ', '.join(book_info.get('authors', [])),
                    'publisher': book_info.get('publisher', ''),
                    'published_date': book_info.get('publishedDate', '')[:4],  # Get year only
                    'isbn': next((id for id in book_info.get('industryIdentifiers', []) 
                                if id['type'] == 'ISBN_13'), {}).get('identifier', ''),
                    'categories': ', '.join(book_info.get('categories', []))
                }
            return None
        except requests.RequestException as e:
            print(f"Error fetching Google Books data for '{title}': {e}")
            return None

    def get_open_library_data(self, title):
        """Fetch book metadata from Open Library API with retries."""
        if not title:
            return None
            
        try:
            params = {'title': title, 'limit': 1}
            response = self.http.get(self.OPEN_LIBRARY_API_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if 'docs' in data and len(data['docs']) > 0:
                book_info = data['docs'][0]
                return {
                    'title': book_info.get('title', ''),
                    'authors': ', '.join(book_info.get('author_name', [])),
                    'publisher': ', '.join(book_info.get('publisher', [])),
                    'published_date': str(book_info.get('first_publish_year', '')),
                    'isbn': next(iter(book_info.get('isbn', [])), ''),
                    'subjects': ', '.join(book_info.get('subject', []))
                }
            return None
        except requests.RequestException as e:
            print(f"Error fetching Open Library data for '{title}': {e}")
            return None

    def merge_metadata(self, google_data, open_library_data):
        """Merge metadata from both APIs, preferring Google Books data."""
        if not google_data and not open_library_data:
            return None
            
        merged = {}
        if google_data:
            merged.update(google_data)
        if open_library_data:
            # Fill in missing data from Open Library
            for key in merged.keys():
                if not merged[key] and open_library_data.get(key):
                    merged[key] = open_library_data[key]
            # Add genre from Open Library subjects if missing
            if 'categories' not in merged or not merged['categories']:
                merged['categories'] = open_library_data.get('subjects', '')
                
        return merged

    def update_sheet(self, spreadsheet_name='Books list', sheet_name='Books'):
        """Update Google Sheet with merged metadata."""
        try:
            # Check internet connection first
            if not self.check_internet_connection():
                print("No internet connection. Please check your connection and try again.")
                return

            # Connect to Google Sheets
            print("Authenticating with Google Sheets...")
            gc = self.authenticate_google_sheets()
            
            print(f"Opening spreadsheet '{spreadsheet_name}'...")
            spreadsheet = gc.open(spreadsheet_name)
            worksheet = spreadsheet.worksheet(sheet_name)
            
            # Get all records
            print("Fetching existing records...")
            records = worksheet.get_all_records()
            
            # Update each row
            for i, row in enumerate(records, start=2):  # start=2 because row 1 is headers
                title = str(row.get('Title', '')).strip()
                if not bool(title):
                    continue
                    
                print(f"\nProcessing: {title}")
                
                # Get metadata from both APIs
                print("Fetching from Google Books API...")
                google_data = self.get_google_books_data(title)
                time.sleep(1)  # Rate limiting
                
                print("Fetching from Open Library API...")
                open_library_data = self.get_open_library_data(title)
                time.sleep(1)  # Rate limiting
                
                # Merge metadata
                merged_data = self.merge_metadata(google_data, open_library_data)
                
                if merged_data:
                    # Update only empty cells
                    updates = []
                    if not row.get('Author'):
                        updates.append(('Author', merged_data.get('authors', '')))
                    if not row.get('Genre'):
                        updates.append(('Genre', merged_data.get('categories', '')))
                    if not row.get('Publisher'):
                        updates.append(('Publisher', merged_data.get('publisher', '')))
                    if not row.get('Publication Year'):
                        updates.append(('Publication Year', merged_data.get('published_date', '')))
                    if not row.get('ISBN'):
                        updates.append(('ISBN', merged_data.get('isbn', '')))
                        
                    # Apply updates
                    for field, value in updates:
                        try:
                            col_idx = worksheet.find(field).col
                            worksheet.update_cell(i, col_idx, value)
                            print(f"Updated {field}: {value}")
                        except Exception as e:
                            print(f"Error updating {field}: {e}")
                    
                    if updates:
                        print(f"Successfully updated metadata for: {title}")
                    else:
                        print(f"No new metadata to update for: {title}")
                else:
                    print(f"No metadata found for: {title}")
                    
        except gspread.exceptions.SpreadsheetNotFound:
            print(f"Error: Could not find spreadsheet '{spreadsheet_name}'. Please check the name and permissions.")
        except gspread.exceptions.WorksheetNotFound:
            print(f"Error: Could not find worksheet '{sheet_name}'. Please check the sheet name.")
        except Exception as e:
            print(f"Error updating sheet: {e}")
            print("Please check your internet connection and try again.")

if __name__ == "__main__":
    updater = BookMetadataUpdater()
    updater.update_sheet()