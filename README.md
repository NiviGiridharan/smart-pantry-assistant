# 🥘 Smart Pantry Assistant

OCR-powered grocery receipt scanner with expiry tracking built with Streamlit and Tesseract.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28-red)

## 📋 Features

- **Multi-Receipt Scanning**: Upload multiple physical receipts or online order screenshots
- **Smart OCR Processing**: Extracts items, quantities, and prices using Tesseract OCR
- **Manual Editing**: Review and correct OCR results with intuitive inline editor
- **FoodKeeper Integration**: Auto-matches 60+ grocery items with USDA shelf life data
- **Expiry Tracking**: Organize items into Fridge/Shelf with automatic expiry suggestions
- **Tax Management**: Editable tax field with auto-calculated totals

## 🛠️ Tech Stack

- **Python 3.11**
- **Streamlit**: Interactive web interface
- **Tesseract OCR**: Receipt text extraction
- **PIL (Pillow)**: Image preprocessing and enhancement
- **USDA FoodKeeper API**: Shelf life database

## 📦 Installation

### Prerequisites
- Python 3.11+
- Tesseract OCR

**Install Tesseract:**
- **Windows**: Download from [Tesseract at UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki)
- **Mac**: `brew install tesseract`
- **Linux**: `sudo apt-get install tesseract-ocr`

### Setup
```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/smart-pantry-assistant.git
cd smart-pantry-assistant

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run application
streamlit run src/app.py
```

## 🚀 Usage

1. **Select Order Type**: Choose between physical receipt or online order
2. **Upload Images**: Multiple images supported (drag & drop)
3. **Review OCR Results**: Check extracted items in the debug panel
4. **Edit Items**: Fix names, quantities, and prices inline
5. **Adjust Tax**: Click "Edit Tax" to modify if needed
6. **Filter Grocery Items**: Uncheck non-food items
7. **Organize Pantry**: Drag items to Fridge or Shelf
8. **Set Expiry Dates**: Auto-populated from USDA data, adjustable
9. **Save**: View your organized pantry with expiry tracking

## 🖥️ Local Development

This is a **local-first application** optimized for desktop use due to Tesseract OCR dependencies. Best experienced by cloning and running locally.

## ⚠️ Known Limitations

- **OCR Accuracy**: Highly dependent on image quality. Works best with:
  - Clear, well-lit photos
  - Flat receipts (no wrinkles)
  - Photos taken from directly above
  - No shadows or glare
  
- **Receipt Format Support**: Parser optimized for standard US grocery receipts. Other formats may require manual editing.

- **FoodKeeper Database**: Limited to 60 common items. Unmatched items default to 7-day shelf life.

- **No Data Persistence**: Session-based storage only. Data is lost on page refresh.

## 🔮 Future Enhancements

- [ ] SQLite database for persistent pantry storage
- [ ] Expiry notification system with email alerts
- [ ] Expanded FoodKeeper database (500+ items)
- [ ] Advanced OCR preprocessing for varied receipt formats
- [ ] Barcode scanning support
- [ ] Export functionality (CSV, PDF)
- [ ] Recipe suggestions based on available ingredients
- [ ] Mobile app version

## 📊 Project Structure
```
smart-pantry-assistant/
├── src/
│   ├── app.py              # Main Streamlit application
│   └── foodkeeper.json     # USDA shelf life database
├── venv/                   # Virtual environment (not tracked)
├── .gitignore
├── requirements.txt
└── README.md
```

## 🤝 Contributing

Contributions welcome! Feel free to:
- Report bugs via Issues
- Suggest features
- Submit pull requests

## 📄 License

MIT License - feel free to use this project for learning or personal use.

## 👤 Author

**Niveda Giridharan**
- GitHub: [@NiviGiridharan](https://github.com/NiviGiridharan)
- LinkedIn: [Niveda Giridharan](https://www.linkedin.com/in/niveda-giridharan-b8836217a/)

---

*Built as part of a Data Science/Engineering portfolio project (December 2024)*

## 🙏 Acknowledgments

- USDA FoodKeeper API for shelf life data
- Tesseract OCR community
- Streamlit for the amazing framework