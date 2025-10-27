import re
import textwrap
import requests
from bs4 import BeautifulSoup
from ddgs import DDGS

def _clean_and_format_text(text: str, width: int = 80) -> str:
    """
    Cleans and formats text for readability:
    - Collapses multiple spaces
    - Preserves paragraphs
    - Wraps lines at a given width
    - Standardizes quotes and dashes
    """
    text = text.replace('“', '"').replace('”', '"')
    text = text.replace('‘', "'").replace('’', "'")
    text = text.replace('–', '-').replace('—', '-')
    paragraphs = [re.sub(r'\s+', ' ', p).strip() for p in text.split('\n') if p.strip()]
    wrapped_paragraphs = [textwrap.fill(p, width=width) for p in paragraphs]
    return '\n\n'.join(wrapped_paragraphs)

def get_text_from_search(query: str) -> dict:
    """
    Searches Dux Distributed Global Search for a query, fetches the first result,
    and returns cleaned, formatted text content.
    
    Note: This isn't a perfect implementation, this is simply for showing how MCP Servers can interact with external systems.
    """
    with DDGS() as ddg:
        results = ddg.text(query, max_results=1)
        if not results:
            return {"url": None, "text": None}

        url = results[0]['href']
        print(f"\tFetching text from: {url}")

        try:
            response = requests.get(url)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"\tFailed to fetch page: {e}")
            return {"url": url, "text": None}

        soup = BeautifulSoup(response.text, 'html.parser')
        raw_text = soup.get_text(separator='\n', strip=True)
        formatted_text = _clean_and_format_text(raw_text)
        display_text = formatted_text[:100].replace("\n", " ")
        print(f"\t\tRetrieved Text (Sample): {display_text} ...")
        return {"url": url, "text": formatted_text}