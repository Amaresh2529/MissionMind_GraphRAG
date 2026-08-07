import fitz  # PyMuPDF
import re
from pathlib import Path

def sanitize_text(text: str) -> str:
    """Removes excessive newlines, unprintable characters, and fixes broken formatting."""
    # Replace multiple spaces/newlines with a single space
    cleaned = re.sub(r'\s+', ' ', text)
    # Remove non-ASCII characters if necessary, keeping standard punctuation
    cleaned = re.sub(r'[^\x00-\x7F]+', ' ', cleaned)
    return cleaned.strip()

def process_all_pdfs():
    """Reads every PDF in data/raw, extracts clean text, and writes to data/processed."""
    # Define directory paths relative to the root folder
    base_dir = Path(__file__).resolve().parent.parent.parent
    raw_dir = base_dir / "data" / "raw"
    processed_dir = base_dir / "data" / "processed"
    
    processed_dir.mkdir(parents=True, exist_ok=True)
    
    pdf_files = list(raw_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in: {raw_dir}")
        return

    print(f"Found {len(pdf_files)} PDFs in data/raw/. Starting extraction...\n")

    for pdf_path in pdf_files:
        output_txt_path = processed_dir / f"{pdf_path.stem}.txt"
        
        # Skip if file has already been processed to avoid re-running expensive jobs
        if output_txt_path.exists():
            print(f"Skipping {pdf_path.name} (already processed at {output_txt_path.name})")
            continue

        print(f"Processing: {pdf_path.name}...")
        try:
            doc = fitz.open(pdf_path)
            extracted_pages = []
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                raw_page_text = page.get_text("text")
                clean_page_text = sanitize_text(raw_page_text)
                if clean_page_text:
                    extracted_pages.append(clean_page_text)
            
            # Join all pages with standard paragraph breaks
            full_document_text = "\n\n".join(extracted_pages)
            
            with open(output_txt_path, "w", encoding="utf-8") as f:
                f.write(full_document_text)
                
            print(f"Completed: Saved {output_txt_path.name}")

        except Exception as err:
            print(f"Error processing {pdf_path.name}: {err}")

if __name__ == "__main__":
    process_all_pdfs()