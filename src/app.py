import streamlit as st
import pytesseract
from PIL import Image
import re

# Set Tesseract path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def parse_receipt(text):
    """Extract items, totals, and tax from receipt"""
    items = []
    totals = {}
    lines = text.split('\n')
    
    for line in lines:
        line_lower = line.lower()
        
        # Skip promotion/discount lines
        if 'promotion' in line_lower or re.search(r'-\d+[\.\s]?\d{2}', line):
            continue
        
        # Capture tax
        if 'tax' in line_lower and 'total' not in line_lower:
            price_match = re.search(r'(\d+[\.\s]\d{2})', line)
            if price_match:
                price = price_match.group(1).replace(' ', '.')
                totals['tax'] = f'${price}'
        
        # Capture grand total
        elif 'grand total' in line_lower:
            price_match = re.search(r'(\d+[\.\s]\d{2})', line)
            if price_match:
                price = price_match.group(1).replace(' ', '.')
                totals['grand_total'] = f'${price}'
        
        # Capture order total
        elif 'order total' in line_lower:
            price_match = re.search(r'(\d+[\.\s]\d{2})', line)
            if price_match:
                price = price_match.group(1).replace(' ', '.')
                totals['order_total'] = f'${price}'
        
        # Regular items
        elif not any(word in line_lower for word in ['savings', 'payment', 'change', 'cash', 'credit', 'debit', 'manager', 'store', 'ocala', 'levi', 'johnson', 'tallahassee']):
            price_match = re.search(r'(\d+[\.\s]\d{2})', line)
            if price_match:
                price = price_match.group(1).replace(' ', '.')
                item_name = line[:price_match.start()].strip()
                if item_name and len(item_name) > 3:
                    items.append({'name': item_name, 'price': f'${price}'})
    
    return items, totals

# STREAMLIT UI
st.title("🥘 Smart Pantry Assistant")
st.write("Upload your grocery receipt to get started!")

# Initialize session state
if 'scanned_items' not in st.session_state:
    st.session_state.scanned_items = None
    st.session_state.totals = None
    st.session_state.step = 1

# File uploader
uploaded_file = st.file_uploader("Choose a receipt image", type=['png', 'jpg', 'jpeg'])

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="Your Receipt", width=400)
    
    # Step 1: Scan Receipt
    if st.button("Scan Receipt"):
        with st.spinner("Reading receipt..."):
            text = pytesseract.image_to_string(image)
            items, totals = parse_receipt(text)
            
            # Store in session state
            st.session_state.scanned_items = items
            st.session_state.totals = totals
            st.session_state.step = 1
            
            st.success(f"Found {len(items)} items!")
    
    # Step 2: Show scanned results
    if st.session_state.scanned_items and st.session_state.step == 1:
        st.subheader("📦 Items Found:")
        for item in st.session_state.scanned_items:
            st.write(f"• {item['name']} - {item['price']}")
        
        # Show receipt totals
        st.subheader("💰 Receipt Summary:")
        totals = st.session_state.totals
        
        if 'order_total' in totals:
            st.write(f"Order Total: {totals['order_total']}")
        if 'tax' in totals:
            st.write(f"Sales Tax: {totals['tax']}")
        if 'grand_total' in totals:
            st.write(f"**Grand Total: {totals['grand_total']}**")
        
        # Next button
        if st.button("Next: Select My Items"):
            st.session_state.step = 2
            st.rerun()
    
    # Step 3: Item selection
    if st.session_state.get('step') == 2:
        st.subheader("✅ Select Your Items:")
        st.write("Uncheck items that aren't yours")
        
        selected_items = []
        for i, item in enumerate(st.session_state.scanned_items):
            is_selected = st.checkbox(f"{item['name']} - {item['price']}", value=True, key=f"item_{i}")
            if is_selected:
                selected_items.append(item)
        
        st.write(f"**You selected: {len(selected_items)} out of {len(st.session_state.scanned_items)} items**")
        
        if selected_items:
            your_total = sum(float(item['price'].replace('$', '')) for item in selected_items)
            st.write(f"**Your Total: ${your_total:.2f}**")