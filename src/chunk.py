import re
import json
import os

def chunk_text(text: str) -> list[dict]:
    """Chunks the 10-K text by major sections with overlap."""
    print("Chunking text by major sections...")
    
    # Look for "Item X." headings which are standard in SEC filings
    pattern = re.compile(r'^(?:PART|Item)\s+([0-9A-Z]+)\.', re.MULTILINE | re.IGNORECASE)
    
    matches = list(pattern.finditer(text))
    chunks = []
    
    if not matches:
        print("Warning: Could not find SEC Items. Falling back to simple chunking.")
        chunk_size = 2000
        overlap = 200
        words = text.split()
        for i in range(0, len(words), chunk_size - overlap):
            chunks.append({
                "section": f"Chunk {i//(chunk_size - overlap) + 1}",
                "text": " ".join(words[i:i+chunk_size])
            })
            if i + chunk_size >= len(words):
                break
        return chunks

    for i in range(len(matches)):
        start = matches[i].end()
        end = matches[i+1].start() if i + 1 < len(matches) else len(text)
        
        section_name = matches[i].group(0).strip()
        section_text = text[start:end].strip()
        
        # Filter out very small chunks (e.g. Table of Contents items)
        if len(section_text.split()) > 150:
            # If a section is still too large, we can sub-chunk it with overlap
            words = section_text.split()
            chunk_size = 2000
            overlap = 200
            for j in range(0, len(words), chunk_size - overlap):
                sub_text = " ".join(words[j:j+chunk_size])
                chunks.append({
                    "section": f"{section_name} (Part {j//(chunk_size - overlap) + 1})",
                    "text": sub_text
                })
                if j + chunk_size >= len(words):
                    break
            
    print(f"Created {len(chunks)} chunks.")
    return chunks

def save_chunks(chunks: list[dict], output_path: str):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2)
