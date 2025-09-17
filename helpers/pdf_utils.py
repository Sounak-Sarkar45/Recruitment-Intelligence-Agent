import PyPDF2

def read_pdf(file_path: str) -> str:
    """Extract text from a PDF resume."""
    text = ""
    with open(file_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text += page.extract_text() + "\n"
    return text.strip()
