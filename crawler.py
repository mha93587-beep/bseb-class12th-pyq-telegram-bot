import requests
from bs4 import BeautifulSoup
import re
import time
from typing import List, Dict, Optional, Tuple, Callable
from urllib.parse import urljoin
import database

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
}

MASTER_INDEX_URL = 'https://www.selfstudys.com/books/bihar/state-books/class-12th/latest/25496'
STATE_INDEX_URL = 'https://www.selfstudys.com/state-wise/bihar/class-12th'

def clean_paper_filename(raw_name: str, year: str) -> str:
    """
    Cleans raw title into a standardized filename:
    'Subject - Code - Set - Year.pdf'
    """
    name = raw_name.strip()
    # Remove leading numbering like '1', '45', '1.'
    name = re.sub(r'^\d+[\.\s-]*', '', name).strip()
    # Remove parens around sets like (Set-D) -> Set-D
    name = name.replace('(', '').replace(')', '')
    # Remove redundant prefixes if present
    name = re.sub(r'Bihar Board (?:Class )?12th (?:Question Paper )?', '', name, flags=re.IGNORECASE).strip()
    
    # Ensure year is present
    if year not in name:
        name = f"{name} - {year}"
        
    # Replace illegal filesystem and telegram special chars
    name = re.sub(r'[\\/*?:"<>|]', '-', name)
    # Clean whitespace and repetitive dashes
    name = re.sub(r'\s+', ' ', name).strip()
    name = re.sub(r'-\s*-+', '-', name)
    
    if not name.lower().endswith('.pdf'):
        name = f"{name}.pdf"
    return name

def parse_metadata(raw_title: str, year: str) -> Tuple[str, str, str]:
    """Extracts subject, code, and set from the title."""
    clean = clean_paper_filename(raw_title, year).replace('.pdf', '')
    parts = [p.strip() for p in clean.split('-') if p.strip()]
    
    subject = parts[0] if parts else "General"
    code = ""
    set_name = ""
    
    for p in parts[1:]:
        if re.match(r'^\d{3}(?:-\d{3})?$', p):
            code = p
        elif 'set' in p.lower():
            set_name = p
            
    return subject, code, set_name

def crawl_years_list(session: Optional[requests.Session] = None) -> List[Tuple[str, str]]:
    """Crawls all available years (2015 - 2026) for Bihar Class 12th."""
    s = session or requests.Session()
    years = []
    
    try:
        r = s.get(MASTER_INDEX_URL, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(r.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            href = a['href']
            m = re.search(r'/books/bihar/state-books/class-12th/(\d{4})/(\d+)', href)
            if m:
                year = m.group(1)
                full_url = urljoin(MASTER_INDEX_URL, href)
                if (year, full_url) not in years:
                    years.append((year, full_url))
    except Exception as e:
        database.add_log('ERROR', f'Error crawling master index: {e}')
        
    if not years:
        try:
            r = s.get(STATE_INDEX_URL, headers=HEADERS, timeout=20)
            soup = BeautifulSoup(r.text, 'html.parser')
            for a in soup.find_all('a', href=True):
                href = a['href']
                m = re.search(r'/books/bihar/state-books/class-12th/(\d{4})/(\d+)', href)
                if m:
                    year = m.group(1)
                    full_url = urljoin(STATE_INDEX_URL, href)
                    if (year, full_url) not in years:
                        years.append((year, full_url))
        except Exception as e:
            database.add_log('ERROR', f'Error crawling fallback index: {e}')

    unique_years = {}
    for y, u in years:
        if y not in unique_years:
            unique_years[y] = u
            
    sorted_years = sorted(unique_years.items(), key=lambda x: int(x[0]), reverse=False)
    for y, u in sorted_years:
        database.upsert_year(y, u, status='pending')
        
    return sorted_years

def crawl_papers_for_year(year: str, base_url: str, session: Optional[requests.Session] = None) -> List[Dict]:
    """Crawls all paper listings for a specific year including pagination."""
    s = session or requests.Session()
    page = 1
    papers_found = []
    seen_urls = set()
    
    while True:
        url = f"{base_url}?page={page}" if page > 1 else base_url
        try:
            res = s.get(url, headers=HEADERS, timeout=25)
            if res.status_code != 200:
                break
            soup = BeautifulSoup(res.text, 'html.parser')
            lis = soup.find_all('li', class_='chapterLi')
            if not lis:
                break
                
            page_has_new = False
            for li in lis:
                ch_name_el = li.find('em', class_='chapterName')
                a_tag = li.find('a', href=True)
                if ch_name_el and a_tag:
                    raw_title = ch_name_el.get_text(strip=True)
                    page_url = urljoin(base_url, a_tag['href'])
                    
                    if page_url in seen_urls:
                        continue
                    seen_urls.add(page_url)
                    page_has_new = True
                    
                    clean_filename = clean_paper_filename(raw_title, year)
                    subject, code, set_name = parse_metadata(raw_title, year)
                    
                    paper_id = database.upsert_paper(
                        year=year,
                        raw_title=raw_title,
                        page_url=page_url,
                        pdf_url=None,
                        clean_filename=clean_filename,
                        subject=subject,
                        code=code
                    )
                    
                    papers_found.append({
                        'id': paper_id,
                        'year': year,
                        'raw_title': raw_title,
                        'page_url': page_url,
                        'clean_filename': clean_filename,
                        'subject': subject,
                        'code': code
                    })
                    
            if not page_has_new:
                break
                
            next_link = soup.find('a', href=re.compile(rf'\?page={page + 1}'))
            if not next_link:
                break
            page += 1
            time.sleep(0.3)
        except Exception as e:
            database.add_log('ERROR', f'Error crawling year {year} page {page}: {e}')
            break
            
    database.upsert_year(year, base_url, total_papers=len(papers_found))
    return papers_found

def resolve_pdf_url(page_url: str, session: Optional[requests.Session] = None) -> Optional[str]:
    """Fetches paper page and extracts direct selfstudys PDF CDN URL."""
    s = session or requests.Session()
    try:
        r = s.get(page_url, headers=HEADERS, timeout=25)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # 1. #PDFF element source attribute
        pdff = soup.find(id='PDFF') or soup.find(class_='PDFFlip') or soup.find(attrs={'source': True})
        if pdff and pdff.get('source'):
            src = pdff['source'].strip()
            if 'selfstudys.com/sitepdfs/' in src:
                return src
                
        # 2. regex search in HTML
        matches = re.findall(r'https?://(?:www\.)?selfstudys\.com/sitepdfs/[a-zA-Z0-9]+', r.text)
        if matches:
            return matches[0]
            
        # 3. direct download links
        for a in soup.find_all('a', href=True):
            if '/sitepdfs/' in a['href']:
                return urljoin(page_url, a['href'])
                
    except Exception as e:
        database.add_log('ERROR', f'Error resolving PDF URL for {page_url}: {e}')
        
    return None

def index_all(progress_callback: Optional[Callable[[str, float], None]] = None) -> Dict[str, int]:
    """Indexes all years and paper listings into SQLite."""
    database.init_db()
    session = requests.Session()
    
    if progress_callback:
        progress_callback("Discovering exam years (2015-2026)...", 0.05)
        
    years = crawl_years_list(session)
    total_years = len(years)
    grand_total_papers = 0
    
    for idx, (year, url) in enumerate(years):
        if progress_callback:
            progress_callback(f"Indexing Year {year} ({idx+1}/{total_years})...", 0.1 + 0.85 * (idx / total_years))
        papers = crawl_papers_for_year(year, url, session)
        grand_total_papers += len(papers)
        
    if progress_callback:
        progress_callback("Indexing complete!", 1.0)
        
    database.add_log('INFO', f'Indexing complete: {grand_total_papers} papers across {total_years} years.')
    return {'total_years': total_years, 'total_papers': grand_total_papers}
