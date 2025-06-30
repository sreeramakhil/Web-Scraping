from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import time
import re
from urllib.parse import urljoin, urlparse
import csv
import io
from datetime import datetime

app = Flask(__name__)
CORS(app)

class WebScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def scrape_basic_data(self, url, selectors=None):
        """Basic web scraping with BeautifulSoup"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            data = {
                'url': url,
                'title': soup.title.string.strip() if soup.title else 'No title',
                'scraped_at': datetime.now().isoformat(),
                'content': {}
            }
            
            if selectors:
                for name, selector in selectors.items():
                    elements = soup.select(selector)
                    if elements:
                        data['content'][name] = [elem.get_text(strip=True) for elem in elements]
                    else:
                        data['content'][name] = []
            else:
                # Default extraction
                data['content'] = {
                    'headings': [h.get_text(strip=True) for h in soup.find_all(['h1', 'h2', 'h3'])],
                    'paragraphs': [p.get_text(strip=True) for p in soup.find_all('p')],
                    'links': [{'text': a.get_text(strip=True), 'href': urljoin(url, a.get('href', ''))} 
                             for a in soup.find_all('a', href=True)],
                    'images': [{'alt': img.get('alt', ''), 'src': urljoin(url, img.get('src', ''))} 
                              for img in soup.find_all('img', src=True)]
                }
            
            return data
            
        except Exception as e:
            return {'error': str(e), 'url': url}
    
    def scrape_table_data(self, url, table_selector='table'):
        """Extract table data from web pages"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            tables = soup.select(table_selector)
            
            if not tables:
                return {'error': 'No tables found', 'url': url}
            
            all_tables = []
            for i, table in enumerate(tables):
                rows = []
                for tr in table.find_all('tr'):
                    row = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
                    if row:  # Only add non-empty rows
                        rows.append(row)
                
                if rows:
                    all_tables.append({
                        'table_index': i,
                        'headers': rows[0] if rows else [],
                        'data': rows[1:] if len(rows) > 1 else [],
                        'total_rows': len(rows)
                    })
            
            return {
                'url': url,
                'scraped_at': datetime.now().isoformat(),
                'tables': all_tables
            }
            
        except Exception as e:
            return {'error': str(e), 'url': url}
    
    def scrape_multiple_pages(self, urls, selectors=None, delay=1):
        """Scrape multiple pages with delay"""
        results = []
        for url in urls:
            result = self.scrape_basic_data(url, selectors)
            results.append(result)
            time.sleep(delay)  # Be respectful to servers
        
        return results

# Initialize scraper
scraper = WebScraper()

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/scrape', methods=['POST'])
def scrape_data():
    data = request.json
    url = data.get('url')
    scrape_type = data.get('type', 'basic')
    selectors = data.get('selectors', {})
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    try:
        if scrape_type == 'basic':
            result = scraper.scrape_basic_data(url, selectors if selectors else None)
        elif scrape_type == 'table':
            table_selector = data.get('table_selector', 'table')
            result = scraper.scrape_table_data(url, table_selector)
        else:
            return jsonify({'error': 'Invalid scrape type'}), 400
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/scrape-multiple', methods=['POST'])
def scrape_multiple():
    data = request.json
    urls = data.get('urls', [])
    selectors = data.get('selectors', {})
    delay = data.get('delay', 1)
    
    if not urls:
        return jsonify({'error': 'URLs are required'}), 400
    
    try:
        results = scraper.scrape_multiple_pages(urls, selectors if selectors else None, delay)
        return jsonify({'results': results, 'total_scraped': len(results)})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/export-csv', methods=['POST'])
def export_csv():
    data = request.json
    scraped_data = data.get('data', [])
    
    if not scraped_data:
        return jsonify({'error': 'No data to export'}), 400
    
    try:
        # Flatten the data for CSV export
        flattened_data = []
        for item in scraped_data:
            if 'error' not in item:
                flat_item = {
                    'url': item.get('url', ''),
                    'title': item.get('title', ''),
                    'scraped_at': item.get('scraped_at', ''),
                }
                
                # Add content fields
                content = item.get('content', {})
                for key, value in content.items():
                    if isinstance(value, list):
                        flat_item[key] = '; '.join([str(v) for v in value])
                    else:
                        flat_item[key] = str(value)
                
                flattened_data.append(flat_item)
        
        # Create CSV
        output = io.StringIO()
        if flattened_data:
            fieldnames = flattened_data[0].keys()
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(flattened_data)
        
        csv_content = output.getvalue()
        output.close()
        
        return jsonify({'csv_data': csv_content})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)