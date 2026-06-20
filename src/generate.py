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
    c.execute('''CREATE TABLE IF NOT EXISTS generation_cache
                 (hash TEXT PRIMARY KEY, qa_json TEXT)''')
    conn.commit()
    return conn

def generate_qa_pairs(chunks: list[dict], api_keys: list[str], pairs_per_chunk: int = 5) -> list[dict]:
    """Generates QA pairs with caching, key rotation, and few-shot diversity."""
    conn = init_cache()
    all_qa = []
    print(f"Generating QA pairs for {len(chunks)} chunks using {len(api_keys)} API key(s)...")
    
    prompt_template = """
    You are an expert financial analyst creating benchmark questions from SEC 10-K filings.
    For the passage below, generate exactly {count} question-answer pairs.
    You MUST output a diverse set of questions. For a set of 5, include exactly:
    - 2 Fact Extraction
    - 1 Numeric Calculation
    - 1 Comparison
    - 1 Multi-step Reasoning

    EXAMPLE QA PAIRS:
    1. Fact Extraction: "What are the company's two operating segments?" -> "Compute & Networking and Graphics"
    2. Numeric Calculation: "If revenue was $10M in 2023 and $15M in 2024, what is the YoY percentage growth?" -> "50%"
    3. Comparison: "Which segment generated higher revenue in 2024, Compute or Graphics?" -> "Compute"
    4. Multi-step Reasoning: "Based on the risk factors, how does the company's reliance on third-party foundries affect its gross margin?" -> "Reliance limits pricing power, which in periods of high demand, restricts gross margin expansion."
    
    Return the result STRICTLY as a JSON array of objects.
    Each object must have the following keys:
    - "question": The question text
    - "answer": The ground truth answer
    - "source_passage": The exact sentence or short passage from the text supporting the answer
    - "question_type": One of [fact extraction, numeric calculation, comparison, multi-step reasoning]
    - "difficulty": One of [easy, medium, hard]
    
    Passage:
    {text}
    """
    
    for i, chunk in enumerate(tqdm(chunks, desc="Generating QA")):
        chunk_text_content = chunk['text'][:30000]
        h = get_hash(chunk_text_content)
        
        # Check cache
        c = conn.cursor()
        c.execute('SELECT qa_json FROM generation_cache WHERE hash=?', (h,))
        row = c.fetchone()
        
        if row:
            # Cache hit!
            qa_list = json.loads(row[0])
            for qa in qa_list:
                qa['section'] = chunk['section']
                all_qa.append(qa)
            continue
            
        prompt = prompt_template.format(count=pairs_per_chunk, text=chunk_text_content)
        
        # Key rotation (Round Robin)
        current_key = api_keys[i % len(api_keys)]
        genai.configure(api_key=current_key)
        model = genai.GenerativeModel('gemini-3.1-flash-lite')
        
        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(response_mime_type="application/json")
            )
            qa_list = json.loads(response.text)
            
            # Save to cache
            c.execute('INSERT OR REPLACE INTO generation_cache VALUES (?, ?)', (h, json.dumps(qa_list)))
            conn.commit()
            
            for qa in qa_list:
                qa['section'] = chunk['section']
                all_qa.append(qa)
                
            time.sleep(2) # Backoff
            
        except Exception as e:
            print(f"\\nError generating QA for chunk {i+1}: {e}")
            time.sleep(4) # Longer backoff on error
            
    conn.close()
    return all_qa

def fix_rejected_qa(rejected_qa: list[dict], chunks: list[dict], api_keys: list[str]) -> list[dict]:
    """Takes rejected QA pairs, feeds the verifier's critique back to the LLM, and gets replacements."""
    conn = init_cache()
    fixed_qa = []
    print(f"Attempting to fix {len(rejected_qa)} rejected QA pairs via Reflection Loop...")
    
    # Create a lookup for chunks by section
    chunk_map = {c['section']: c['text'][:30000] for c in chunks}
    
    prompt_template = """
    You previously generated a question-answer pair from a financial text, but a human reviewer rejected it.
    
    PREVIOUS QUESTION: {question}
    PREVIOUS ANSWER: {answer}
    PREVIOUS SOURCE PASSAGE: {source_passage}
    REJECTION REASON: {reason}
    
    Please read the PASSAGE below and generate ONE new, high-quality question-answer pair that fixes this issue. 
    It must be strictly supported by the text. Do not make the same mistake.
    
    Return the result STRICTLY as a JSON array containing EXACTLY ONE object with keys:
    - "question"
    - "answer"
    - "source_passage"
    - "question_type"
    - "difficulty"
    
    PASSAGE:
    {text}
    """
    
    for i, qa in enumerate(tqdm(rejected_qa, desc="Fixing QA")):
        section = qa.get('section')
        chunk_text_content = chunk_map.get(section, "")
        if not chunk_text_content:
            continue
            
        prompt = prompt_template.format(
            question=qa.get('question'),
            answer=qa.get('answer'),
            source_passage=qa.get('source_passage'),
            reason=qa.get('verification_reason'),
            text=chunk_text_content
        )
        h = get_hash("fix_" + prompt)
        
        # Check cache
        c = conn.cursor()
        c.execute('SELECT qa_json FROM generation_cache WHERE hash=?', (h,))
        row = c.fetchone()
        
        if row:
            try:
                new_qa_list = json.loads(row[0])
                if new_qa_list:
                    new_qa = new_qa_list[0]
                    new_qa['section'] = section
                    fixed_qa.append(new_qa)
            except:
                pass
            continue
            
        current_key = api_keys[i % len(api_keys)]
        genai.configure(api_key=current_key)
        model = genai.GenerativeModel('gemini-3.1-flash-lite')
        
        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(response_mime_type="application/json")
            )
            new_qa_list = json.loads(response.text)
            
            c.execute('INSERT OR REPLACE INTO generation_cache VALUES (?, ?)', (h, json.dumps(new_qa_list)))
            conn.commit()
            
            if new_qa_list:
                new_qa = new_qa_list[0]
                new_qa['section'] = section
                fixed_qa.append(new_qa)
                
            time.sleep(2)
        except Exception as e:
            print(f"\\nError fixing QA: {e}")
            time.sleep(4)
            
    conn.close()
    return fixed_qa
