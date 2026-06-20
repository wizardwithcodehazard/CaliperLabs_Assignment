import pandas as pd
import os

def export_to_csv(qa_pairs: list[dict], output_path: str):
    """Exports the QA pairs to a CSV file."""
    if not qa_pairs:
        print("No QA pairs to export.")
        return
        
    print(f"Exporting {len(qa_pairs)} pairs to {output_path}...")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    df = pd.DataFrame(qa_pairs)
    # Ensure columns are in a nice order
    cols = ['section', 'question', 'answer', 'source_passage', 'question_type', 'difficulty', 'verified', 'verification_reason']
    # keep only existing cols
    cols = [c for c in cols if c in df.columns]
    df = df[cols]
    
    df.to_csv(output_path, index=False)
    print("Export complete.")
