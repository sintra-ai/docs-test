#!/usr/bin/env python3

import requests
import json
import os
import html2text
import time
from typing import Dict, List, Optional
import argparse
import sys
from dotenv import load_dotenv

class IntercomArticleExporter:
    def __init__(self, access_token: str, output_dir: str = "articles"):
        self.access_token = access_token
        self.base_url = "https://api.intercom.io"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Intercom-Version": "2.11"
        }
        self.output_dir = output_dir
        self.h2t = html2text.HTML2Text()
        self.h2t.ignore_links = False
        self.h2t.body_width = 0
        
    def make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make a request to the Intercom API with rate limit handling."""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get('X-RateLimit-Reset', 60))
                print(f"Rate limited. Waiting {retry_after} seconds...")
                time.sleep(retry_after)
                return self.make_request(endpoint, params)
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"Error making request to {endpoint}: {e}")
            if hasattr(e.response, 'text'):
                print(f"Response: {e.response.text}")
            raise
    
    def get_all_collections(self) -> List[Dict]:
        """Fetch all help center collections."""
        print("Fetching collections...")
        collections = []
        endpoint = "/help_center/collections"
        page = 1
        per_page = 50
        
        while True:
            params = {'page': page, 'per_page': per_page}
            data = self.make_request(endpoint, params)
            collections_data = data.get('data', [])
            
            if not collections_data:
                break
                
            collections.extend(collections_data)
            
            # Check for more pages
            if 'pages' in data:
                total_pages = data['pages'].get('total_pages', 1)
                if page >= total_pages:
                    break
                page += 1
            else:
                break
                
        print(f"Found {len(collections)} collections")
        return collections
    
    def get_all_articles(self) -> List[Dict]:
        """Fetch all articles from the help center."""
        print("Fetching all articles...")
        articles = []
        endpoint = "/articles"
        page = 1
        per_page = 50
        
        while True:
            params = {
                'page': page,
                'per_page': per_page
            }
            
            data = self.make_request(endpoint, params)
            articles_data = data.get('data', [])
            
            if not articles_data:
                break
                
            articles.extend(articles_data)
            print(f"Fetched {len(articles)} articles so far...")
            
            # Check for more pages
            if 'pages' in data:
                total_pages = data['pages'].get('total_pages', 1)
                if page >= total_pages:
                    break
                page += 1
            else:
                break
            
            # Small delay to avoid hitting rate limits
            time.sleep(0.5)
        
        print(f"Total articles found: {len(articles)}")
        return articles
    
    def get_article_content(self, article_id: str) -> Dict:
        """Fetch detailed content for a specific article."""
        endpoint = f"/articles/{article_id}"
        return self.make_request(endpoint)
    
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for filesystem compatibility."""
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Limit length
        if len(filename) > 200:
            filename = filename[:200]
            
        return filename.strip()
    
    def convert_to_markdown(self, article: Dict) -> str:
        """Convert article HTML content to Markdown."""
        title = article.get('title', 'Untitled')
        author = article.get('author', {}).get('name', 'Unknown')
        created_at = article.get('created_at', '')
        updated_at = article.get('updated_at', '')
        
        # Get the body content
        body_html = article.get('body', '')
        
        # Convert HTML to Markdown
        body_md = self.h2t.handle(body_html) if body_html else ''
        
        # Build the Markdown document
        markdown = f"# {title}\n\n"
        markdown += f"**Author:** {author}  \n"
        markdown += f"**Created:** {created_at}  \n"
        markdown += f"**Updated:** {updated_at}  \n"
        markdown += f"**Article ID:** {article.get('id', 'Unknown')}  \n"
        
        # Add parent information if available
        if article.get('parent_id'):
            markdown += f"**Parent ID:** {article.get('parent_id')}  \n"
        if article.get('parent_type'):
            markdown += f"**Parent Type:** {article.get('parent_type')}  \n"
        
        markdown += "\n---\n\n"
        markdown += body_md
        
        return markdown
    
    def export_articles_with_hierarchy(self):
        """Export articles organizing them by collection hierarchy."""
        # Create output directory
        os.makedirs(self.output_dir, exist_ok=True)
        
        try:
            # Step 1: Get all collections
            collections = self.get_all_collections()
            collections_by_id = {c['id']: c for c in collections}
            
            # Step 2: Get all articles
            all_articles = self.get_all_articles()
            
            if not all_articles:
                print("No articles found to export.")
                return
            
            # Step 3: Organize articles by their parent structure
            articles_by_collection = {}
            articles_by_section = {}
            uncategorized_articles = []
            
            for article in all_articles:
                parent_type = article.get('parent_type')
                parent_id = article.get('parent_id')
                
                if parent_type == 'collection' and parent_id:
                    if parent_id not in articles_by_collection:
                        articles_by_collection[parent_id] = []
                    articles_by_collection[parent_id].append(article)
                elif parent_type == 'section' and parent_id:
                    if parent_id not in articles_by_section:
                        articles_by_section[parent_id] = {
                            'articles': [],
                            'collection_id': None
                        }
                    articles_by_section[parent_id]['articles'].append(article)
                else:
                    uncategorized_articles.append(article)
            
            # Try to determine collection for sections by checking article parents
            # Since we can't get sections directly, we'll infer the structure
            section_names = {}
            for section_id, section_data in articles_by_section.items():
                # Use the first article's information to infer section details
                if section_data['articles']:
                    first_article = section_data['articles'][0]
                    # Try to get more details about the article
                    try:
                        full_article = self.get_article_content(first_article['id'])
                        # Sometimes the full article has more parent information
                        if 'parent' in full_article:
                            parent_info = full_article['parent']
                            if 'name' in parent_info:
                                section_names[section_id] = parent_info['name']
                    except:
                        pass
            
            # Step 4: Export articles organized by structure
            total_articles = 0
            
            # Process articles by collection
            for collection_id, articles in articles_by_collection.items():
                collection = collections_by_id.get(collection_id, {})
                collection_name = self.sanitize_filename(collection.get('name', f'Collection_{collection_id}'))
                collection_path = os.path.join(self.output_dir, collection_name)
                os.makedirs(collection_path, exist_ok=True)
                
                print(f"\nProcessing collection: {collection.get('name', collection_id)}")
                print(f"  Found {len(articles)} articles directly in collection")
                
                for article in articles:
                    article_id = article['id']
                    
                    # Get full article content
                    try:
                        full_article = self.get_article_content(article_id)
                    except Exception as e:
                        print(f"    Failed to get full content for article {article_id}: {e}")
                        full_article = article
                    
                    # Convert to Markdown
                    markdown_content = self.convert_to_markdown(full_article)
                    
                    # Save file
                    filename = f"{self.sanitize_filename(full_article.get('title', 'untitled'))}.md"
                    file_path = os.path.join(collection_path, filename)
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(markdown_content)
                    
                    print(f"    Saved: {filename}")
                    total_articles += 1
                    
                    # Small delay to avoid rate limits
                    time.sleep(0.2)
            
            # Process articles by section
            if articles_by_section:
                print(f"\nProcessing {len(articles_by_section)} sections with articles")
                
                for section_id, section_data in articles_by_section.items():
                    section_name = section_names.get(section_id, f'Section_{section_id}')
                    section_name = self.sanitize_filename(section_name)
                    
                    # Try to determine the collection this section belongs to
                    # by looking at article metadata or using a sections folder
                    section_path = os.path.join(self.output_dir, 'Sections', section_name)
                    os.makedirs(section_path, exist_ok=True)
                    
                    print(f"\nProcessing section: {section_name}")
                    print(f"  Found {len(section_data['articles'])} articles")
                    
                    for article in section_data['articles']:
                        article_id = article['id']
                        
                        # Get full article content
                        try:
                            full_article = self.get_article_content(article_id)
                        except Exception as e:
                            print(f"    Failed to get full content for article {article_id}: {e}")
                            full_article = article
                        
                        # Convert to Markdown
                        markdown_content = self.convert_to_markdown(full_article)
                        
                        # Save file
                        filename = f"{self.sanitize_filename(full_article.get('title', 'untitled'))}.md"
                        file_path = os.path.join(section_path, filename)
                        
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(markdown_content)
                        
                        print(f"    Saved: {filename}")
                        total_articles += 1
                        
                        # Small delay to avoid rate limits
                        time.sleep(0.2)
            
            # Process uncategorized articles
            if uncategorized_articles:
                uncategorized_path = os.path.join(self.output_dir, 'Uncategorized')
                os.makedirs(uncategorized_path, exist_ok=True)
                
                print(f"\nProcessing {len(uncategorized_articles)} uncategorized articles")
                
                for article in uncategorized_articles:
                    article_id = article['id']
                    
                    # Get full article content
                    try:
                        full_article = self.get_article_content(article_id)
                    except Exception as e:
                        print(f"  Failed to get full content for article {article_id}: {e}")
                        full_article = article
                    
                    # Convert to Markdown
                    markdown_content = self.convert_to_markdown(full_article)
                    
                    # Save file
                    filename = f"{self.sanitize_filename(full_article.get('title', 'untitled'))}.md"
                    file_path = os.path.join(uncategorized_path, filename)
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(markdown_content)
                    
                    print(f"  Saved: {filename}")
                    total_articles += 1
                    
                    # Small delay to avoid rate limits
                    time.sleep(0.2)
            
            # Save metadata
            metadata = {
                'total_articles': total_articles,
                'collections': [
                    {
                        'id': c['id'], 
                        'name': c.get('name'),
                        'article_count': len(articles_by_collection.get(c['id'], []))
                    } 
                    for c in collections
                ],
                'sections_count': len(articles_by_section),
                'uncategorized_count': len(uncategorized_articles),
                'export_date': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            metadata_path = os.path.join(self.output_dir, 'export_metadata.json')
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            
            print(f"\nExport completed successfully!")
            print(f"Total articles exported: {total_articles}")
            print(f"  - In collections: {sum(len(a) for a in articles_by_collection.values())}")
            print(f"  - In sections: {sum(len(s['articles']) for s in articles_by_section.values())}")
            print(f"  - Uncategorized: {len(uncategorized_articles)}")
            print(f"Output directory: {os.path.abspath(self.output_dir)}")
            
        except Exception as e:
            print(f"Export failed: {e}")
            raise

def main():
    # Load environment variables
    load_dotenv()
    
    parser = argparse.ArgumentParser(description='Export Intercom Help Center articles to Markdown files')
    parser.add_argument('--token', '-t', help='Intercom Access Token (or set INTERCOM_ACCESS_TOKEN in .env)')
    parser.add_argument('--output', '-o', default='articles', help='Output directory (default: articles)')
    
    args = parser.parse_args()
    
    # Try to get token from args or environment
    access_token = args.token or os.getenv('INTERCOM_ACCESS_TOKEN')
    
    if not access_token or access_token == 'your_access_token_here':
        print("Error: Intercom Access Token is required")
        print("Please either:")
        print("1. Set INTERCOM_ACCESS_TOKEN in your .env file")
        print("2. Pass it via --token argument")
        print("\nYou can find your access token at: https://app.intercom.com/a/apps/_/developer-hub")
        sys.exit(1)
    
    exporter = IntercomArticleExporter(access_token, args.output)
    
    try:
        exporter.export_articles_with_hierarchy()
    except KeyboardInterrupt:
        print("\nExport interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Export failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()