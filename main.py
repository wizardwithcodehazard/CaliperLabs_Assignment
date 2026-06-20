import os
import argparse
import json
from src.download import download_filing
from src.parse import parse_html
from src.chunk import chunk_text, save_chunks
from src.generate import generate_qa_pairs, fix_rejected_qa
from src.verify import verify_qa_pairs
from src.export import export_to_csv

def main():
    parser = argparse.ArgumentParser(description="Caliper Lab QA Pipeline")
    parser.add_argument("--url", type=str, default="https://www.sec.gov/Archives/edgar/data/1045810/000104581024000029/nvda-20240128.htm", help="SEC EDGAR 10-K URL")
    parser.add_argument("--email", type=str, default="user@example.com", help="Email for SEC User-Agent")
    parser.add_argument("--generate-only", action="store_true", help="Skip download and chunking if already done")
    args = parser.parse_args()
    
    api_key_env = os.environ.get("GEMINI_API_KEY")
    if not api_key_env:
        print("ERROR: GEMINI_API_KEY environment variable not set.")
        print("You can provide multiple keys separated by commas: set GEMINI_API_KEY=key1,key2,key3")
        return
        
    api_keys = [k.strip() for k in api_key_env.split(',') if k.strip()]

    raw_path = "data/raw/filing.html"
    chunks_path = "data/chunks/chunks.json"
    qa_output_path = "data/output/qa_dataset.csv"
    
    if not args.generate_only:
        # Phase 1 & 2: Download & Parse
        download_filing(args.url, raw_path, args.email)
        text = parse_html(raw_path)
        
        # Phase 3: Chunking
        chunks = chunk_text(text)
        save_chunks(chunks, chunks_path)
    else:
        if not os.path.exists(chunks_path):
            print(f"Chunks file {chunks_path} not found. Run without --generate-only first.")
            return
        with open(chunks_path, "r", encoding="utf-8") as f:
            chunks = json.load(f)

    # Phase 4: Generate QA
    chunks_to_process = chunks[:25] 
    qa_pairs = generate_qa_pairs(chunks_to_process, api_keys, pairs_per_chunk=5)
    
    # Phase 5: Verification
    verified_qa = verify_qa_pairs(qa_pairs, api_keys)
    rejected_qa = [qa for qa in qa_pairs if not qa.get('verified', False)]
    
    # Phase 5.5: Reflection Loop (Fix rejected QA pairs)
    if rejected_qa:
        print(f"\\n--- REFLECTION LOOP ---")
        fixed_qa = fix_rejected_qa(rejected_qa, chunks_to_process, api_keys)
        if fixed_qa:
            print(f"\\n--- VERIFYING FIXED QA PAIRS ---")
            re_verified_qa = verify_qa_pairs(fixed_qa, api_keys)
            verified_qa.extend(re_verified_qa)
    
    # Phase 6: Export
    export_to_csv(verified_qa, qa_output_path)
    
    print("\\n=== PIPELINE SUMMARY ===")
    print(f"Total chunks processed: {len(chunks_to_process)}")
    print(f"Total initial QA pairs generated: {len(qa_pairs)}")
    print(f"Total QA pairs passed initial verification: {len(qa_pairs) - len(rejected_qa)}")
    if rejected_qa:
        print(f"Reflection loop recovered: {len(re_verified_qa) if 're_verified_qa' in locals() else 0} pairs")
    print(f"FINAL dataset size: {len(verified_qa)} verified pairs")
    print(f"Dataset saved to: {qa_output_path}")

if __name__ == "__main__":
    main()
