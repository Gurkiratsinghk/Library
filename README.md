# Enhanced Book Metadata Updater

A Python code that automatically updates Google Sheets with comprehensive book metadata from multiple APIs. The application fetches detailed information from Google Books and Open Library APIs, merges the data, and updates your spreadsheet with missing book details.

## Features

- **Multi-API Integration**: Fetches metadata from Google Books API and Open Library API
- **Intelligent Data Merging**: Smart algorithm to combine and prioritize data from multiple sources
- **Concurrent Processing**: Parallel API calls for improved performance
- **Comprehensive Logging**: Detailed logs with configurable levels and file output
- **Backup System**: Automatic backup of your sheet data before making changes
- **Flexible Configuration**: JSON-based configuration for easy customization
- **Batch Processing**: Processes books in configurable batches to optimize performance
- **Enhanced Matching**: Advanced title matching algorithm for better accuracy
- **Progress Tracking**: Real-time progress updates and detailed statistics
- **Dry Run Mode**: Preview changes without modifying your sheet
- **Error Recovery**: Robust retry logic and graceful error handling
- **Field Validation**: Ensures your sheet has the required structure

## Requirements

- Python 3.7+
- Google Sheets API credentials (service account)

## Installation

1. **Clone or download the project files**

2. **Install required dependencies**:
   ```bash
   pip install gspread google-auth requests urllib3
   ```

   Or use the requirements file:
   ```bash
   pip install -r requirements.txt
   ```

## Google Sheets API Setup

### Step 1: Create a Google Cloud Project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" → "New Project"
3. Enter a project name (e.g., "Book Metadata Updater")
4. Click "Create"

### Step 2: Enable Required APIs

1. In your Google Cloud project, go to "APIs & Services" → "Library"
2. Search for and enable these APIs:
   - **Google Sheets API**
   - **Google Drive API**

### Step 3: Create Service Account Credentials

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "Service Account"
3. Fill in the service account details:
   - **Name**: `book-metadata-updater`
   - **Description**: `Service account for updating book metadata`
4. Click "Create and Continue"
5. Skip the optional steps and click "Done"

### Step 4: Generate and Download Credentials

1. In the Credentials page, click on your newly created service account
2. Go to the "Keys" tab
3. Click "Add Key" → "Create New Key"
4. Select "JSON" format
5. Click "Create"
6. The credentials file will download automatically
7. **Rename the file to `credentials.json`** and place it in your project directory

### Step 5: Share Your Google Sheet

1. Open your Google Sheet containing the book list
2. Click the "Share" button (top right)
3. In the credentials file you downloaded, find the `client_email` field (looks like: `book-metadata-updater@your-project.iam.gserviceaccount.com`)
4. Add this email address to your sheet with "Editor" permissions
5. **Important**: You can uncheck "Notify people" since this is a service account

### Step 6: Verify Setup

Your project directory should now contain:
- `library.py` (the main script)
- `credentials.json` (your Google service account credentials)
- `config.json` (will be created automatically on first run)

## Google Sheet Structure

Your Google Sheet should have the following columns (customizable in config.json):

| Column Name | Description | Required |
|-------------|-------------|----------|
| Title | Book title | ✅ Yes |
| Author | Book author(s) | No |
| Genre | Book genre/categories | No |
| Publisher | Publisher name | No |
| Publication Year | Year of publication | No |
| ISBN | ISBN number | No |
| Pages | Number of pages | No |
| Language | Book language | No |
| Description | Book description | No |

**Note**: Only the Title column is required. The script will populate empty fields in other columns.

##  Configuration

The application uses a `config.json` file for customization. On first run, a default configuration will be created:

```json
{
  "retry_attempts": 5,
  "backoff_factor": 1,
  "rate_limit_delay": 1.0,
  "max_workers": 3,
  "batch_size": 10,
  "spreadsheet_name": "Books list",
  "sheet_name": "Books",
  "log_level": "INFO",
  "backup_enabled": true,
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
```

### Configuration Options

- **retry_attempts**: Number of retry attempts for failed API calls
- **rate_limit_delay**: Delay between API calls (seconds)
- **max_workers**: Number of concurrent threads for processing
- **batch_size**: Number of books to process in each batch
- **spreadsheet_name**: Name of your Google Spreadsheet
- **sheet_name**: Name of the worksheet within the spreadsheet
- **log_level**: Logging verbosity (DEBUG, INFO, WARNING, ERROR)
- **backup_enabled**: Whether to create backups before updating
- **field_mapping**: Maps sheet columns to metadata fields

## Usage

### Basic Usage

Run the script with default settings:
```bash
python library.py
```

### Command Line Options

```bash
# Use custom configuration file
python library.py --config my_config.json

# Use custom credentials file
python library.py --credentials my_credentials.json

# Override spreadsheet name
python library.py --spreadsheet "My Book Collection"

# Override sheet name  
python library.py --sheet "Sheet1"

# Dry run (preview changes without modifying)
python library.py --dry-run

# Validate sheet structure only
python library.py --validate

# Combine multiple options
python library.py --spreadsheet "My Books" --sheet "List" --dry-run
```

### Example Workflow

1. **First, validate your sheet structure**:
   ```bash
   python library.py --validate
   ```

2. **Run a dry run to preview changes**:
   ```bash
   python library.py --dry-run
   ```

3. **Execute the actual update**:
   ```bash
   python library.py
   ```

## Logging and Monitoring

The application creates detailed logs in the `logs/` directory:

- **Console Output**: Real-time progress and status updates
- **Log Files**: Detailed logs with timestamps (`logs/book_updater_YYYYMMDD_HHMMSS.log`)
- **Progress Tracking**: Shows processed, updated, and failed counts
- **Error Details**: Comprehensive error information for troubleshooting

### Sample Log Output
```
2024-08-04 10:30:15 - INFO - Logging initialized. Log file: logs/book_updater_20240804_103015.log
2024-08-04 10:30:16 - INFO - Authenticating with Google Sheets...
2024-08-04 10:30:17 - INFO - Opening spreadsheet 'Books list'...
2024-08-04 10:30:18 - INFO - Processing 50 books in batches of 10
2024-08-04 10:30:19 - INFO - Processing: The Great Gatsby
2024-08-04 10:30:21 - INFO - Found metadata for: The Great Gatsby
2024-08-04 10:30:22 - INFO - Successfully updated: The Great Gatsby
```

## Backup and Recovery

- **Automatic Backups**: Created before any modifications (if enabled)
- **Backup Location**: `backups/sheet_backup_YYYYMMDD_HHMMSS.json`
- **Backup Format**: JSON format containing all sheet data
- **Recovery**: Manual restoration from backup files if needed

## Troubleshooting

### Common Issues

1. **"Spreadsheet not found" Error**
   - Verify the spreadsheet name in your config matches exactly
   - Ensure the service account email has access to the sheet

2. **"No internet connection" Error**
   - Check your internet connectivity
   - Verify firewall/proxy settings aren't blocking API calls

3. **"Authentication failed" Error**
   - Ensure `credentials.json` is in the correct location
   - Verify the service account has the required permissions
   - Check that APIs are enabled in Google Cloud Console

4. **Rate limiting issues**
   - Increase `rate_limit_delay` in config.json
   - Reduce `max_workers` for slower processing

5. **"Missing required fields" Error**
   - Run with `--validate` to check sheet structure
   - Update `field_mapping` in config.json to match your sheet

### Debug Mode

Enable detailed debugging:
```json
{
  "log_level": "DEBUG"
}
```

## Performance Tips

1. **Optimize batch size**: Larger batches process faster but use more memory
2. **Adjust worker threads**: More workers = faster processing (but respect API limits)
3. **Use dry run first**: Test with small datasets before processing large sheets
4. **Monitor rate limits**: Increase delays if you encounter rate limiting

## Security Notes

- Keep your `credentials.json` file secure and never commit it to version control
- Add `credentials.json` to your `.gitignore` file
- The service account only needs access to your specific Google Sheet
- Consider using environment variables for sensitive configuration in production



## Contributing

Feel free to submit issues, fork the repository, and create pull requests for any improvements.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

If you encounter issues:

1. Check the troubleshooting section above
2. Review the log files for detailed error information
3. Ensure your Google Sheets setup follows the guide exactly
4. Test with a small dataset first using dry-run mode

## Example Results

After running the script, your Google Sheet will be populated with rich metadata:

| Title | Author | Genre | Publisher | Publication Year | ISBN | Pages | Language |
|-------|--------|-------|-----------|------------------|------|-------|----------|
| The Great Gatsby | F. Scott Fitzgerald | Fiction, Classics | Scribner | 1925 | 9780743273565 | 180 | en |
| To Kill a Mockingbird | Harper Lee | Fiction, Drama | J.B. Lippincott & Co. | 1960 | 9780061120084 | 376 | en |