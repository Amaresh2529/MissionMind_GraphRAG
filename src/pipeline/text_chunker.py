import json
import time
from pathlib import Path

def chunk_text_by_words(text: str, chunk_size: int = 250, overlap: int = 50) -> list[str]:
    """Slices text into overlapping chunks based on word count to preserve context."""
    words = text.split()
    chunks = []
    
    # Slide the window across the text
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
        
        # Stop if we have reached the end of the document
        if i + chunk_size >= len(words):
            break
            
    return chunks

def process_and_chunk():
    """Reads cleaned text files, chunks them, and saves them as structured JSON."""
    base_dir = Path(__file__).resolve().parent.parent.parent
    processed_dir = base_dir / "data" / "processed"
    chunked_dir = processed_dir / "chunks"
    
    # Create the chunks directory if it doesn't exist
    chunked_dir.mkdir(parents=True, exist_ok=True)
    
    txt_files = list(processed_dir.glob("*.txt"))
    if not txt_files:
        print(f"No text files found in {processed_dir}. Run pdf_loader.py first.")
        return

    print(f"Starting chunking process for {len(txt_files)} documents...\n{'='*60}")
    
    total_chunks_created = 0

    for txt_path in txt_files:
        output_json_path = chunked_dir / f"{txt_path.stem}_chunks.json"
        
        print(f"🔪 Chunking: {txt_path.name}")
        start_time = time.time()
        
        try:
            with open(txt_path, "r", encoding="utf-8") as f:
                full_text = f.read()
            
            # Create chunks of 250 words with a 50-word overlap
            document_chunks = chunk_text_by_words(full_text, chunk_size=250, overlap=50)
            total_chunks_created += len(document_chunks)
            
            # Structure the data for our graph database ingestion later
            structured_data = {
                "document_id": txt_path.stem,
                "total_chunks": len(document_chunks),
                "chunks": [
                    {"chunk_id": f"{txt_path.stem}_{idx}", "text": chunk_text}
                    for idx, chunk_text in enumerate(document_chunks)
                ]
            }
            
            # Save as JSON
            with open(output_json_path, "w", encoding="utf-8") as f:
                json.dump(structured_data, f, indent=4)
                
            end_time = time.time()
            print(f"   ✅ Created {len(document_chunks)} chunks in {(end_time - start_time):.2f} seconds.")
            
        except Exception as e:
            print(f"   ❌ Error chunking {txt_path.name}: {e}")

    print(f"{'='*60}\n🎉 Pipeline Complete: Generated a total of {total_chunks_created} overlapping chunks.")

if __name__ == "__main__":
    process_and_chunk()