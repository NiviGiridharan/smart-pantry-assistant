import pytesseract

# Set Tesseract path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

try:
    version = pytesseract.get_tesseract_version()
    print(f"Tesseract version: {version}")
    print("✅ OCR is working!")
except Exception as e:
    print(f"❌ Error: {e}")