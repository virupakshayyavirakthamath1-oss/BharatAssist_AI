from pathlib import Path

def extract_text(file):
    name = file.filename.lower()
    if name.endswith(".txt"):
        return file.read().decode("utf-8", errors="ignore")
    if name.endswith(".pdf"):
        from PyPDF2 import PdfReader
        reader = PdfReader(file)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return "This starter supports text and PDF extraction. Image OCR can be added with Tesseract or another OCR service."
