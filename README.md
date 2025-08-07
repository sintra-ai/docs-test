# Intercom Knowledge Base Exporter

This script exports all help articles from your Intercom Help Center to local Markdown files.

## Setup

1. Install required dependencies:
```bash
pip install -r requirements.txt
```

2. Get your Intercom Access Token:
   - Go to https://app.intercom.com/a/apps/_/developer-hub
   - Create a new app or use an existing one
   - Navigate to "Authentication" section
   - Copy your Access Token

3. Configure your API key:
   - Edit the `.env` file
   - Replace `your_access_token_here` with your actual Intercom Access Token

## Usage

Run the export script (it will use the token from .env):

```bash
python export_intercom_articles.py
```

Or pass the token directly:

```bash
python export_intercom_articles.py --token YOUR_ACCESS_TOKEN
```

Optional parameters:
- `--output` or `-o`: Specify output directory (default: "articles")

Example:
```bash
python export_intercom_articles.py --token YOUR_ACCESS_TOKEN --output my-help-articles
```

## Output Structure

The script will create the following directory structure:

```
articles/
├── collections/
│   └── [collection-name]/
│       └── [article-id]_[article-title].md
├── sections/
│   └── [section-id]/
│       └── [article-id]_[article-title].md
├── uncategorized/
│   └── [article-id]_[article-title].md
└── export_metadata.json
```

Each Markdown file includes:
- Article title
- Author information
- Creation and update timestamps
- Article ID and parent information
- Full article content converted from HTML to Markdown

## Features

- Exports all public help center articles
- Converts HTML content to clean Markdown format
- Organizes articles by collections and sections
- Handles rate limiting automatically
- Saves metadata about the export
- Sanitizes filenames for filesystem compatibility

## Notes

- The script only exports public-facing help center articles
- Internal knowledge base articles are not accessible via the API
- Rate limit: 1000 API calls per minute
- The script includes delays to avoid hitting rate limits