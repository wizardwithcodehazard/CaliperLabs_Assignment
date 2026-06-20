from bs4 import BeautifulSoup
import re

def parse_html(file_path: str) -> str:
    """Parses HTML and returns cleaned text with boilerplate stripped."""
    print(f"Parsing HTML from {file_path}...")
    with open(file_path, "r", encoding="utf-8") as f:
        html = f.read()
    
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator="\n", strip=True)
    
    # --- PHASE 2: STRIPPING BOILERPLATE ---
    print("Stripping legal boilerplate and empty lines...")
    lines = text.split('\n')
    cleaned_lines = []
    
    boilerplate_patterns = [
        r'^Table of Contents$',
        r'(?i)see accompanying notes',
        r'(?i)see notes to consolidated financial statements',
        r'^\d+$', # Solitary page numbers
        r'^Index$',
        r'^ITEM \d+[A-Z]?\.$' # Solitary item headers with no content
    ]
    
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue
            
        is_boilerplate = False
        for pattern in boilerplate_patterns:
            if re.search(pattern, line_stripped):
                is_boilerplate = True
                break
                
        if not is_boilerplate:
            cleaned_lines.append(line_stripped)
            
    text = '\n'.join(cleaned_lines)
    # Remove large gaps
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text
