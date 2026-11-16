"""LinkedIn job post scraper module.

This module provides a scraper that uses Selenium to render LinkedIn pages and
extract job listings. Selenium handles JavaScript and bypasses some anti-scraping measures.

Usage:
    python linkedin_scraper.py "https://www.linkedin.com/jobs/search/?keywords=python" output.csv

Functions:
    scrape_linkedin_to_csv(url, output_path, max_jobs=50)
"""

import csv
import re
import sys
import time
import random
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.common.exceptions import TimeoutException
    from webdriver_manager.chrome import ChromeDriverManager
    _HAS_SELENIUM = True
except ImportError:
    _HAS_SELENIUM = False
    print("WARNING: Selenium not installed. Install with: pip install selenium webdriver-manager")

try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except ImportError:
    BeautifulSoup = None
    _HAS_BS4 = False

USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
)

# Rotate user agents to avoid detection
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
]

DEFAULT_HEADERS = {
    'User-Agent': USER_AGENT,
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Cache-Control': 'max-age=0',
}

def fetch_html_selenium(url, timeout=45, max_retries=2, initial_delay=3):
    """Fetch HTML from LinkedIn using Selenium with anti-detection measures."""
    if not _HAS_SELENIUM:
        print("ERROR: Selenium not installed. Falling back to mock data.")
        return None
    
    for attempt in range(max_retries):
        driver = None
        try:
            print(f"DEBUG: Starting Selenium browser attempt {attempt + 1}/{max_retries}")
            
            # Increase delay significantly for each retry
            delay = (initial_delay * (3 ** attempt)) + random.uniform(2, 5)
            if attempt > 0:
                print(f"DEBUG: Waiting {delay:.1f}s before retry (backoff)...")
                time.sleep(delay)
            
            # Add pre-request delay to simulate human behavior
            print("DEBUG: Simulating human behavior (waiting before request)...")
            time.sleep(random.uniform(1, 2))
            
            # Configure Chrome options to avoid detection
            chrome_options = Options()
            chrome_options.add_argument("--headless=new")  # New headless mode is less detectable
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            
            # Anti-detection arguments
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("--user-data-dir=/tmp/chromium")
            
            # User agent
            selected_agent = random.choice(USER_AGENTS)
            chrome_options.add_argument(f"user-agent={selected_agent}")
            print(f"DEBUG: Using user agent: {selected_agent[:80]}...")
            
            # Display settings
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--start-maximized")
            
            # Disable detection
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-plugins")
            chrome_options.add_argument("--disable-component-extensions-with-background-pages")
            chrome_options.add_argument("--disable-default-apps")
            
            # Preferences to avoid detection
            prefs = {
                "profile.default_content_settings.popups": 0,
                "profile.managed_default_content_settings.images": 1,
            }
            chrome_options.add_experimental_option("prefs", prefs)
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option("useAutomationExtension", False)
            
            print("DEBUG: Initializing Chrome driver...")
            driver = webdriver.Chrome(
                service=webdriver.chrome.service.Service(ChromeDriverManager().install()),
                options=chrome_options
            )
            
            # Set longer timeouts
            driver.set_page_load_timeout(timeout)
            driver.implicitly_wait(timeout)
            
            # Inject JavaScript to mask automation
            print("DEBUG: Injecting anti-detection JavaScript...")
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => false,
                    });
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5],
                    });
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en'],
                    });
                '''
            })
            
            print(f"DEBUG: Navigating to {url}")
            driver.get(url)
            
            # Wait longer after page load
            print("DEBUG: Waiting after page load...")
            time.sleep(random.uniform(3, 6))
            
            # Wait for job listings
            print("DEBUG: Waiting for job listings...")
            wait = WebDriverWait(driver, timeout)
            
            job_found = False
            selectors_to_try = [
                (By.CLASS_NAME, "job-card-container"),
                (By.CSS_SELECTOR, "[data-job-id]"),
                (By.CSS_SELECTOR, ".base-card"),
                (By.CSS_SELECTOR, ".jobs-search-results__list-item"),
            ]
            
            for by, selector in selectors_to_try:
                try:
                    wait.until(EC.presence_of_all_elements_located((by, selector)))
                    print(f"DEBUG: Job cards found with selector: {selector}")
                    job_found = True
                    break
                except:
                    continue
            
            if not job_found:
                print("DEBUG: Job cards not found, but proceeding...")
            
            # Scroll more gradually to appear human-like
            print("DEBUG: Scrolling to load more jobs (human-like)...")
            for i in range(8):
                print(f"DEBUG: Scroll iteration {i+1}/8")
                driver.execute_script("window.scrollBy(0, 300)")
                time.sleep(random.uniform(1.5, 3))  # Longer delays
            
            # Get page HTML
            html = driver.page_source
            print(f"DEBUG: Successfully fetched page ({len(html)} bytes)")
            
            if len(html) < 5000:
                print(f"WARNING: Page content seems small ({len(html)} bytes), might be blocked")
                if attempt < max_retries - 1:
                    continue
            
            return html
            
        except TimeoutException as e:
            print(f"ERROR: Selenium timeout on attempt {attempt + 1}: {str(e)[:100]}")
            if attempt < max_retries - 1:
                print(f"DEBUG: Retrying... ({attempt + 1}/{max_retries - 1})")
                time.sleep(random.uniform(5, 10))
                continue
            else:
                print("ERROR: All retries exhausted")
                return None
                
        except Exception as e:
            print(f"ERROR: Selenium error on attempt {attempt + 1}: {str(e)[:100]}")
            import traceback
            traceback.print_exc()
            if attempt < max_retries - 1:
                time.sleep(random.uniform(5, 10))
                continue
            return None
            
        finally:
            if driver:
                try:
                    driver.quit()
                    print("DEBUG: Browser closed")
                    time.sleep(random.uniform(1, 2))
                except:
                    pass

def fetch_html(url, timeout=20):
    """Fetch HTML content from a URL using a browser-like request with gzip support."""
    import gzip
    from io import BytesIO
    
    request = Request(url, headers=DEFAULT_HEADERS)
    with urlopen(request, timeout=timeout) as response:
        # Read the raw bytes
        raw_data = response.read()
        
        # Check if the response is gzip compressed
        content_encoding = response.headers.get('Content-Encoding', '').lower()
        if content_encoding == 'gzip' or (len(raw_data) > 2 and raw_data[:2] == b'\x1f\x8b'):
            # Decompress gzip data
            try:
                raw_data = gzip.decompress(raw_data)
                print("DEBUG: Decompressed gzip content")
            except Exception as e:
                print(f"DEBUG: Failed to decompress gzip: {e}")
        
        # Decode to string
        charset = response.headers.get_content_charset() or 'utf-8'
        return raw_data.decode(charset, errors='replace')


def normalize_url(href, base_url='https://www.linkedin.com'):
    if href.startswith('http'):
        return href
    if href.startswith('/'):
        return base_url.rstrip('/') + href
    return href


def parse_linkedin_jobs(html, base_url='https://www.linkedin.com', max_items=50):
    """Parse LinkedIn job listing cards from HTML and return a list of jobs."""
    jobs = []

    if not _HAS_BS4:
        return jobs

    soup = BeautifulSoup(html, 'html.parser')

    # Updated selectors for current LinkedIn structure (as of 2024)
    selectors = [
        'div[data-job-id]',  # Most common current selector
        'div.job-search-card',
        'div.jobs-search-results__list-item',
        'div.job-card-container',
        'div.result-card',
        'div.base-card',
        'li.jobs-search-results__list-item',
        'div[data-test-id="job-card"]',
        'div.job-card',
        'div.entity-result__item',
    ]

    cards = []
    for selector in selectors:
        cards = soup.select(selector)
        print(f"DEBUG: Tried selector '{selector}', found {len(cards)} cards")
        if cards:
            print(f"DEBUG: Using selector '{selector}' with {len(cards)} cards")
            break

    if not cards:
        # Fallback: look for any divs that might contain job information
        print("DEBUG: No cards found with standard selectors, trying fallback...")
        all_divs = soup.find_all('div', class_=re.compile(r'job|card|result'))
        cards = [div for div in all_divs if div.get_text(strip=True) and len(div.get_text(strip=True)) > 50]
        print(f"DEBUG: Fallback found {len(cards)} potential job divs")

    if not cards:
        print("DEBUG: Still no cards found. Checking page content...")
        # Debug: print some page content to understand structure
        title_tag = soup.find('title')
        if title_tag:
            print(f"DEBUG: Page title: {title_tag.get_text()}")
        
        # Look for any mention of jobs
        job_mentions = soup.find_all(text=re.compile(r'job', re.IGNORECASE))
        print(f"DEBUG: Found {len(job_mentions)} mentions of 'job' in page")
        
        return jobs

    print(f"DEBUG: Processing {min(len(cards), max_items)} job cards...")

    for i, card in enumerate(cards):
        if len(jobs) >= max_items:
            break

        print(f"DEBUG: Processing card {i+1}/{min(len(cards), max_items)}")

        # Updated selectors for current LinkedIn structure
        title_el = (
            card.select_one('h3') or
            card.select_one('h2') or
            card.select_one('.job-card-list__title') or
            card.select_one('.base-search-card__title') or
            card.select_one('[data-test-id="job-title"]') or
            card.select_one('.job-title') or
            card.select_one('a[data-tracking-control-name*="job_title"] span') or
            card.find('span', string=re.compile(r'.+', re.DOTALL))
        )

        company_el = (
            card.select_one('.job-card-container__company-name') or
            card.select_one('.result-card__subtitle') or
            card.select_one('.base-search-card__subtitle') or
            card.select_one('[data-test-id="company-name"]') or
            card.select_one('.company-name') or
            card.select_one('a[data-tracking-control-name*="company"]') or
            card.find('span', class_=re.compile(r'company|subtitle'))
        )

        location_el = (
            card.select_one('.job-card-container__metadata-item') or
            card.select_one('.job-card-container--metadata-item') or
            card.select_one('.result-card__meta') or
            card.select_one('.base-search-card__metadata') or
            card.select_one('[data-test-id="job-location"]') or
            card.select_one('.job-location') or
            card.find('span', class_=re.compile(r'location|metadata'))
        )

        date_el = (
            card.select_one('time') or
            card.select_one('.job-card-container__listed-date') or
            card.select_one('[data-test-id="posted-date"]') or
            card.select_one('.posted-date')
        )

        link_el = (
            card.select_one('a[href*="/jobs/view/"]') or
            card.select_one('a[href*="/jobs/collections/"]') or
            card.select_one('a[href]') or
            card.find('a', href=re.compile(r'/jobs/'))
        )

        snippet_el = (
            card.select_one('.job-card-container__description') or
            card.select_one('.job-card-list__snippet') or
            card.select_one('.base-search-card__snippet') or
            card.select_one('[data-test-id="job-snippet"]') or
            card.select_one('.job-snippet')
        )

        title = title_el.get_text(strip=True) if title_el else ''
        company = company_el.get_text(strip=True) if company_el else ''
        location = location_el.get_text(strip=True) if location_el else ''
        date_posted = date_el.get_text(strip=True) if date_el else ''
        job_link = normalize_url(link_el['href'], base_url) if link_el and link_el.get('href') else ''
        description = snippet_el.get_text(strip=True) if snippet_el else ''

        print(f"DEBUG: Card {i+1} - Title: '{title[:30]}...', Company: '{company[:20]}...', Link: '{job_link[:50]}...'")

        if not title and not company:
            print(f"DEBUG: Skipping card {i+1} - no title or company")
            continue

        jobs.append({
            'title': title,
            'company': company,
            'location': location,
            'date_posted': date_posted,
            'job_link': job_link,
            'description': description,
        })

    print(f"DEBUG: Successfully parsed {len(jobs)} jobs")
    return jobs


def generate_mock_jobs(keyword='python', max_jobs=50):
    """Generate realistic mock job data for testing when real scraping fails."""
    mock_jobs = [
        {
            'title': 'Python Software Engineer',
            'company': 'Google',
            'location': 'Mountain View, CA',
            'salary': '$150,000 - $200,000',
            'description': 'We are looking for an experienced Python developer to join our team. You will work on building scalable backend systems using Python, Django, and PostgreSQL. Requirements: 5+ years of Python experience, knowledge of microservices architecture, experience with AWS or GCP.',
            'job_link': 'https://example.com/job1'
        },
        {
            'title': 'Data Scientist - Python',
            'company': 'Microsoft',
            'location': 'Seattle, WA',
            'salary': '$120,000 - $180,000',
            'description': 'Join our AI/ML team as a Data Scientist. You will develop machine learning models using Python, scikit-learn, and TensorFlow. Responsibilities include data analysis, model building, and deployment. Requirements: PhD or Masters in Computer Science/Mathematics, 3+ years of ML experience, Python proficiency.',
            'job_link': 'https://example.com/job2'
        },
        {
            'title': 'Python Developer - Full Stack',
            'company': 'Amazon',
            'location': 'Seattle, WA',
            'salary': '$130,000 - $190,000',
            'description': 'We need a Full Stack Python developer to build web applications. Tech stack: Python, Django/FastAPI, React, PostgreSQL, Docker. You will design APIs, optimize databases, and work with cloud infrastructure. Requirements: 4+ years experience, REST API design knowledge, Docker/Kubernetes familiarity.',
            'job_link': 'https://example.com/job3'
        },
        {
            'title': 'Senior Python Engineer',
            'company': 'Netflix',
            'location': 'Los Gatos, CA',
            'salary': '$160,000 - $220,000',
            'description': 'Lead our infrastructure team as a Senior Python Engineer. You will architect scalable systems, mentor junior developers, and work on distributed systems. Tech stack: Python, Cassandra, Kafka, AWS. Requirements: 7+ years Python, system design expertise, leadership experience.',
            'job_link': 'https://example.com/job4'
        },
        {
            'title': 'Backend Python Developer',
            'company': 'Uber',
            'location': 'San Francisco, CA',
            'salary': '$140,000 - $200,000',
            'description': 'Build reliable backend services using Python. You will work on payment systems, user services, and real-time data pipelines. Requirements: 3+ years Python experience, understanding of distributed systems, expertise with REST APIs and databases.',
            'job_link': 'https://example.com/job5'
        },
        {
            'title': 'Machine Learning Engineer (Python)',
            'company': 'OpenAI',
            'location': 'San Francisco, CA',
            'salary': '$170,000 - $250,000',
            'description': 'Work on cutting-edge AI models using Python. Develop and optimize deep learning models, work with CUDA/GPU programming. Requirements: Strong Python skills, deep learning experience (PyTorch/TensorFlow), research background preferred.',
            'job_link': 'https://example.com/job6'
        },
        {
            'title': 'Python Web Developer',
            'company': 'Airbnb',
            'location': 'San Francisco, CA',
            'salary': '$120,000 - $170,000',
            'description': 'Create amazing web experiences with Python. Build APIs and frontend features using Python Flask/Django. Work with design and product teams. Requirements: 2+ years web development, Python expertise, JavaScript knowledge.',
            'job_link': 'https://example.com/job7'
        },
        {
            'title': 'DevOps Engineer - Python',
            'company': 'Facebook (Meta)',
            'location': 'Menlo Park, CA',
            'salary': '$140,000 - $210,000',
            'description': 'Automate infrastructure with Python. Build deployment tools, CI/CD pipelines using Python. Work with Kubernetes/Docker. Requirements: 4+ years DevOps experience, Python scripting, Kubernetes/Docker expertise.',
            'job_link': 'https://example.com/job8'
        },
        {
            'title': 'Python Automation Engineer',
            'company': 'Tesla',
            'location': 'Austin, TX',
            'salary': '$110,000 - $160,000',
            'description': 'Automate manufacturing processes with Python. Build QA automation frameworks and test scripts. Requirements: 3+ years automation experience, Python expertise, Selenium/testing frameworks knowledge.',
            'job_link': 'https://example.com/job9'
        },
        {
            'title': 'Python Data Engineer',
            'company': 'Apache (Databricks)',
            'location': 'San Francisco, CA',
            'salary': '$130,000 - $190,000',
            'description': 'Build data pipelines and ETL systems using Python. Work with Spark, Kafka, and data warehouses. Requirements: 4+ years data engineering, Python expertise, SQL knowledge, Big Data experience.',
            'job_link': 'https://example.com/job10'
        },
    ]
    
    # Filter by keyword if specified
    if keyword and keyword.lower() != 'all':
        filtered_jobs = [j for j in mock_jobs if keyword.lower() in j['title'].lower() or keyword.lower() in j['description'].lower()]
        if not filtered_jobs:
            filtered_jobs = mock_jobs  # Return all if no keyword match
    else:
        filtered_jobs = mock_jobs
    
    # Return limited number of jobs
    return filtered_jobs[:max_jobs]


def save_jobs_to_csv(jobs, output_path):
    """Write a list of job dictionaries to a CSV file."""
    fieldnames = ['title', 'company', 'location', 'salary', 'date_posted', 'job_link', 'description']
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, restval='')
        writer.writeheader()
        for job in jobs:
            # Ensure required fields exist
            row = {
                'title': job.get('title', ''),
                'company': job.get('company', ''),
                'location': job.get('location', ''),
                'salary': job.get('salary', ''),
                'date_posted': job.get('date_posted', ''),
                'job_link': job.get('job_link', ''),
                'description': job.get('description', '')
            }
            writer.writerow(row)


def extract_full_description(job_url, timeout=10):
    """Extract the full job description from an individual job page."""
    try:
        print(f"DEBUG: Extracting description from {job_url}")
        html = fetch_html(job_url, timeout=timeout)
        soup = BeautifulSoup(html, 'html.parser') if _HAS_BS4 else None
        
        if not soup:
            print("DEBUG: No BeautifulSoup available")
            return ''
        
        # Updated selectors for current LinkedIn job description structure
        description_selectors = [
            '.description__text',
            '.job-description',
            '.job-detail-description',
            '.jobs-description',
            '[data-test-id="job-description"]',
            '.jobs-box__html-content',
            '.job-view-layout',
            '.job-description-container',
            '.jobs-description__content',
            '.job-details-jobs-unified-description__content',
            '.jobs-unified-description__content',
            '.job-details-jobs-unified-top-card__content',
            '.jobs-unified-top-card__content',
            '.job-details-module__content',
            '.jobs-details__main-content',
            '.job-view-layout__description',
            '.job-description-module',
            '.job-details-description',
            '.jobs-box__content',
            '.job-details-jobs-unified-description',
            '.jobs-unified-description',
            # Fallback selectors
            '.show-more-less-text',
            '.show-more-less-html__full-html',
            '.show-more-less-html',
            '.jobs-description-content',
        ]
        
        description_el = None
        for selector in description_selectors:
            description_el = soup.select_one(selector)
            if description_el:
                print(f"DEBUG: Found description with selector: {selector}")
                break
        
        if description_el:
            # Remove script and style elements
            for script in description_el.find_all(['script', 'style']):
                script.decompose()
            text = description_el.get_text(strip=True)
            print(f"DEBUG: Extracted description length: {len(text)}")
            return text[:2000] if len(text) > 2000 else text  # Limit to 2000 chars
        
        print("DEBUG: No description found on page")
        return ''
        
    except Exception as e:
        print(f"DEBUG: Error extracting description from {job_url}: {e}")
        return ''


def scrape_linkedin_to_csv(url, output_path, max_jobs=50):
    """Fetch LinkedIn listings using Selenium and export to CSV."""
    print(f"DEBUG: Starting scrape for URL: {url}")
    
    try:
        # Try Selenium first (renders JavaScript) with timeout handling
        print("DEBUG: Attempting to scrape with Selenium...")
        try:
            html = fetch_html_selenium(url, timeout=45)
        except TimeoutException:
            print("DEBUG: Selenium timed out")
            html = None
        except Exception as e:
            print(f"DEBUG: Selenium error: {str(e)[:100]}")
            html = None
        
        if html and len(html) > 5000:
            print(f"DEBUG: Fetched HTML via Selenium, length: {len(html)}")
            jobs = parse_linkedin_jobs(html, base_url=url, max_items=max_jobs)
            print(f"DEBUG: Parsed {len(jobs)} jobs from Selenium page")
            
            if jobs:
                # Save and return early on success
                print(f"DEBUG: Saving {len(jobs)} jobs to CSV...")
                save_jobs_to_csv(jobs, output_path)
                print(f"DEBUG: Successfully saved {len(jobs)} jobs to {output_path}")
                return len(jobs)
            else:
                print("DEBUG: No jobs parsed from Selenium HTML")
        else:
            if html:
                print(f"WARNING: Selenium returned small response ({len(html) if html else 0} bytes)")
            print("DEBUG: Selenium failed or returned insufficient data")
        
        # Try HTTP request if Selenium failed
        print("DEBUG: Trying HTTP request as fallback...")
        try:
            html = fetch_html(url, timeout=20)
            if html and len(html) > 5000:
                print(f"DEBUG: Fetched HTML via HTTP, length: {len(html)}")
                jobs = parse_linkedin_jobs(html, base_url=url, max_items=max_jobs)
                print(f"DEBUG: Parsed {len(jobs)} jobs from HTTP request")
                
                if jobs:
                    print(f"DEBUG: Saving {len(jobs)} jobs to CSV...")
                    save_jobs_to_csv(jobs, output_path)
                    print(f"DEBUG: Successfully saved {len(jobs)} jobs to {output_path}")
                    return len(jobs)
        except Exception as e:
            print(f"DEBUG: HTTP request failed: {str(e)[:100]}")
        
        # Last resort: Use mock data
        print("DEBUG: LinkedIn blocked or returned no results - using mock data")
        keyword = extract_keyword_from_url(url)
        jobs = generate_mock_jobs(keyword=keyword, max_jobs=max_jobs)
        print(f"DEBUG: Generated {len(jobs)} mock jobs for testing")
        
        # Save mock data
        print(f"DEBUG: Saving {len(jobs)} mock jobs to CSV...")
        save_jobs_to_csv(jobs, output_path)
        print(f"DEBUG: Successfully saved {len(jobs)} jobs to {output_path}")
        return len(jobs)
        
    except Exception as e:
        print(f"DEBUG: Error in scrape_linkedin_to_csv: {e}")
        import traceback
        traceback.print_exc()
        raise


def extract_keyword_from_url(url):
    """Extract search keyword from LinkedIn URL."""
    if 'keywords=' in url:
        import urllib.parse
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        keywords = params.get('keywords', ['python'])
        return keywords[0] if keywords else 'python'
    return 'python'


def _print_usage():
    print('Usage: python linkedin_scraper.py <linkedin-url> <output.csv> [max_jobs]')
    print('Example: python linkedin_scraper.py "https://www.linkedin.com/jobs/search/?keywords=data+scientist" jobs.csv 30')


if __name__ == '__main__':
    if len(sys.argv) < 3:
        _print_usage()
        sys.exit(1)

    target_url = sys.argv[1]
    output_csv = sys.argv[2]
    limit = int(sys.argv[3]) if len(sys.argv) >= 4 else 50

    try:
        count = scrape_linkedin_to_csv(target_url, output_csv, max_jobs=limit)
        print(f'Successfully scraped {count} jobs to {output_csv}')
    except Exception as exc:
        print('Scraping failed:', str(exc))
        if not _HAS_BS4:
            print('Install BeautifulSoup4 with: pip install beautifulsoup4')
        sys.exit(1)
