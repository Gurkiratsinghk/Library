# Book Metadata Updater

This Python project is designed to automatically update a Google Sheet containing a list of books with metadata from two different book APIs: Google Books and Open Library. The script fetches metadata for each book in the sheet and updates missing details such as authors, publisher, genre, ISBN, and publication year.

## Features

- Fetches book metadata from **Google Books API** and **Open Library API**.
- Merges data from both APIs, preferring data from Google Books where available.
- Updates the Google Sheet with missing metadata fields (Author, Genre, Publisher, Publication Year, ISBN).
- Includes retry logic for API requests to handle intermittent connectivity issues.
- Checks for an internet connection before proceeding with the API requests and Google Sheets update.

## Requirements

- Python 3.6+
- Google Sheets API credentials (service account) to access and update your Google Sheets.
- Libraries:
  - `gspread`: Google Sheets API client.
  - `google-auth`: Google authentication library.
  - `requests`: To make HTTP requests to external APIs.
  - `urllib3`: For retry handling.
  
You can install the required dependencies using the following command:

```bash
pip install gspread google-auth requests urllib3
```

## Setup

1. **Google Sheets API Setup**: 
   - Create a Google Cloud Project and enable the Google Sheets API and Google Drive API.
   - Create a service account in the Google Cloud Console and download the `credentials.json` file.
   - Share your Google Sheet with the service account's email (found in `credentials.json`) to grant it access.

2. **Google Sheet Structure**:
   - The script assumes the Google Sheet has the following columns:
     - `Title` (for the book title)
     - `Author` (for the book author)
     - `Genre` (for the book genre)
     - `Publisher` (for the book publisher)
     - `Publication Year` (for the book publication year)
     - `ISBN` (for the book ISBN)

3. **Authentication**:
   - Ensure the `credentials.json` file is in the same directory as the script.
   - The script uses the credentials to authenticate with the Google Sheets API.

## Usage

1. **Run the Script**:
   To run the script, simply execute it with Python:

   ```bash
   python book_metadata_updater.py
   ```

   The script will:
   - Authenticate with Google Sheets using the provided credentials.
   - Fetch metadata for each book listed in the Google Sheet.
   - Update missing fields (Author, Genre, Publisher, Publication Year, ISBN) with data retrieved from the APIs.

2. **API Retry and Internet Connection**:
   - The script includes retry logic for the API requests. It will automatically retry up to 5 times in case of temporary server errors (e.g., HTTP 500-504).
   - The script checks for an internet connection before performing any operations.

## Error Handling

- The script will handle errors related to API requests (e.g., network issues or invalid responses) and will retry automatically.
- If the Google Sheets or worksheet cannot be found, the script will output an error message.
- If a book has no metadata available from either API, it will be skipped.

## Customization

You can customize the script by:
- Modifying the API URLs if you'd like to use a different API.
- Changing the structure of the Google Sheet if your columns differ.
- Adjusting the retry strategy, such as the number of retries or the backoff factor.

## Code Overview

### Class: `BookMetadataUpdater`

- **Methods**:
  - `check_internet_connection()`: Checks if the system has an active internet connection.
  - `authenticate_google_sheets()`: Authenticates with the Google Sheets API using the service account credentials.
  - `get_google_books_data(title)`: Fetches book metadata from the Google Books API.
  - `get_open_library_data(title)`: Fetches book metadata from the Open Library API.
  - `merge_metadata(google_data, open_library_data)`: Merges metadata from both APIs, preferring Google Books data.
  - `update_sheet(spreadsheet_name, sheet_name)`: Updates the Google Sheet with the merged metadata.

### Example of Google Sheet

| Title         | Author     | Genre    | Publisher    | Publication Year | ISBN         |
|---------------|------------|----------|--------------|------------------|--------------|
| Example Book  | John Doe   | Fiction  | Example Pub  | 2020             | 9781234567890|
| Another Book  | Jane Smith | Non-Fiction| Another Pub  | 2019             | 9789876543210|

<!-- ## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. -->