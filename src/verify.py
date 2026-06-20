import google.generativeai as genai
import json
import time
import sqlite3
import hashlib
from tqdm import tqdm

def get_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def init_cache():
    conn = sqlite3.connect('cache.sqlite')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS verify_cache
                 (hash TEXT PRIMARY KEY, verified INT, reason TEXT)''')
    conn.commit()
    return conn

def verify_qa_pairs(qa_pairs: list[dict], api_keys: list[str]) -> list[dict]:
    """Verifies that the answer is supported by the source passage using cache and key rotation."""
    conn = init_cache()
    verified_qa = []
    print(f"Verifying {len(qa_pairs)} QA pairs using {len(api_keys)} API key(s)...")
    
    prompt_template = """
    You are a strict verifier evaluating a question answering dataset.
    Determine if the ANSWER is fully supported by the PASSAGE.
    The answer must not require outside knowledge and must not be hallucinated.
    
    PASSAGE: {passage}
    QUESTION: {question}
    ANSWER: {answer}
    
    Return a JSON object with two keys:
    - "verified": boolean (true/false) - true if supported, false otherwise
    - "reason": string explaining why it is verified or not
    """
    
    for i, qa in enumerate(tqdm(qa_pairs, desc="Verifying QA")):
        passage = qa.get('source_passage', '')
        question = qa.get('question', '')
        answer = qa.get('answer', '')
        
        prompt = prompt_template.format(passage=passage, question=question, answer=answer)
        h = get_hash(prompt)
        
        # Check cache
        c = conn.cursor()
        c.execute('SELECT verified, reason FROM verify_cache WHERE hash=?', (h,))
        row = c.fetchone()
        
        if row:
            qa['verified'] = bool(row[0])
            qa['verification_reason'] = row[1]
            if qa['verified']:
                verified_qa.append(qa)
            continue
            
        # Key rotation (Round Robin)
        current_key = api_keys[i % len(api_keys)]
        genai.configure(api_key=current_key)
        model = genai.GenerativeModel('gemini-3.1-flash-lite')
        
        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(response_mime_type="application/json")
            )
            result = json.loads(response.text)
            
            is_verified = result.get('verified', False)
            reason = result.get('reason', '')
            
            qa['verified'] = is_verified
            qa['verification_reason'] = reason
            
            # Save to cache
            c.execute('INSERT OR REPLACE INTO verify_cache VALUES (?, ?, ?)', (h, int(is_verified), reason))
            conn.commit()
            
            if qa['verified']:
                verified_qa.append(qa)
                
            time.sleep(1) # Backoff
            
        except Exception as e:
            print(f"\\nError verifying QA pair {i+1}: {e}")
            time.sleep(2)
            
    conn.close()
    print(f"Verification complete. {len(verified_qa)}/{len(qa_pairs)} passed.")
    return verified_qa
