import streamlit as st
import pytesseract
from PIL import Image
import re
from datetime import datetime, timedelta

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
                    items.append({'name': item_name, 'price': f'${price}', 'category': 'unsorted', 'expiry_days': 7})
    
    return items, totals

def auto_categorize(item_name):
    """Suggest category based on item name"""
    fridge_keywords = ['milk', 'yogurt', 'cheese', 'meat', 'chicken', 'beef', 
                       'fish', 'egg', 'butter', 'vegetable', 'fruit', 'lettuce',
                       'tomato', 'carrot', 'broccoli', 'spinach', 'juice']
    
    name_lower = item_name.lower()
    if any(keyword in name_lower for keyword in fridge_keywords):
        return 'fridge', 3
    return 'shelf', 7

# STREAMLIT UI
st.set_page_config(page_title="Smart Pantry Assistant", layout="wide")
st.title("🥘 Smart Pantry Assistant")
st.write("Upload your grocery receipt to get started!")

# Initialize session state
if 'scanned_items' not in st.session_state:
    st.session_state.scanned_items = None
    st.session_state.totals = None
    st.session_state.step = 1
    st.session_state.selected_items = []

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
            
            # Next button to categorization
            if st.button("Next: Organize Pantry →", type="primary"):
                st.session_state.selected_items = selected_items
                st.session_state.step = 3
                st.rerun()
    
    # Step 4: Drag-Drop Categorization
    if st.session_state.get('step') == 3:
        st.subheader("🗂️ Organize Your Pantry")
        st.write("Move items to Fridge or Shelf using the arrow buttons")
        
        # Create 3 columns
        col_unsorted, col_fridge, col_shelf = st.columns(3)
        
        with col_unsorted:
            st.markdown("### 📦 Unsorted")
            unsorted_count = 0
            
            for idx, item in enumerate(st.session_state.selected_items):
                if item['category'] == 'unsorted':
                    unsorted_count += 1
                    
                    # Item card
                    with st.container():
                        st.write(f"**{item['name']}**")
                        st.caption(f"{item['price']}")
                        
                        # Action buttons in a row
                        btn_col1, btn_col2 = st.columns(2)
                        
                        with btn_col1:
                            if st.button("→ 🧊", key=f"to_fridge_{idx}", help="Move to Fridge"):
                                suggested_cat, suggested_days = auto_categorize(item['name'])
                                item['category'] = 'fridge'
                                item['expiry_days'] = 3
                                st.rerun()
                        
                        with btn_col2:
                            if st.button("→ 🗄️", key=f"to_shelf_{idx}", help="Move to Shelf"):
                                item['category'] = 'shelf'
                                item['expiry_days'] = 7
                                st.rerun()
                        
                        st.divider()
            
            if unsorted_count == 0:
                st.info("✓ All items organized!")
        
        with col_fridge:
            st.markdown("### 🧊 Refrigerator")
            st.caption("Items expire in 3 days")
            fridge_count = 0
            
            for idx, item in enumerate(st.session_state.selected_items):
                if item['category'] == 'fridge':
                    fridge_count += 1
                    
                    with st.container():
                        st.write(f"**{item['name']}**")
                        st.caption(f"{item['price']}")
                        
                        # Expiry date input
                        expiry = st.number_input(
                            "Days until expiry:",
                            min_value=1,
                            max_value=30,
                            value=item['expiry_days'],
                            key=f"fridge_exp_{idx}"
                        )
                        item['expiry_days'] = expiry
                        
                        expiry_date = datetime.now() + timedelta(days=expiry)
                        st.caption(f"📅 Expires: {expiry_date.strftime('%b %d')}")
                        
                        # Move back button
                        if st.button("← Back", key=f"fridge_back_{idx}"):
                            item['category'] = 'unsorted'
                            st.rerun()
                        
                        st.divider()
            
            st.metric("Items", fridge_count)
        
        with col_shelf:
            st.markdown("### 🗄️ Pantry Shelf")
            st.caption("Items expire in 7 days")
            shelf_count = 0
            
            for idx, item in enumerate(st.session_state.selected_items):
                if item['category'] == 'shelf':
                    shelf_count += 1
                    
                    with st.container():
                        st.write(f"**{item['name']}**")
                        st.caption(f"{item['price']}")
                        
                        # Expiry date input
                        expiry = st.number_input(
                            "Days until expiry:",
                            min_value=1,
                            max_value=365,
                            value=item['expiry_days'],
                            key=f"shelf_exp_{idx}"
                        )
                        item['expiry_days'] = expiry
                        
                        expiry_date = datetime.now() + timedelta(days=expiry)
                        st.caption(f"📅 Expires: {expiry_date.strftime('%b %d')}")
                        
                        # Move back button
                        if st.button("← Back", key=f"shelf_back_{idx}"):
                            item['category'] = 'unsorted'
                            st.rerun()
                        
                        st.divider()
            
            st.metric("Items", shelf_count)
        
        # Bottom action bar
        st.markdown("---")
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            categorized = sum(1 for item in st.session_state.selected_items if item['category'] != 'unsorted')
            total = len(st.session_state.selected_items)
            st.progress(categorized / total if total > 0 else 0)
            st.caption(f"Progress: {categorized}/{total} items organized")
        
        with col2:
            if st.button("← Back to Selection"):
                st.session_state.step = 2
                st.rerun()
        
        with col3:
            all_categorized = all(item['category'] != 'unsorted' for item in st.session_state.selected_items)
            if all_categorized:
                if st.button("✅ Save to Pantry", type="primary"):
                    st.success("🎉 Items saved to your pantry!")
                    st.balloons()
                    
                    # Show summary
                    with st.expander("📊 View Saved Items"):
                        for item in st.session_state.selected_items:
                            expiry_date = datetime.now() + timedelta(days=item['expiry_days'])
                            st.write(f"• {item['name']} ({item['category']}) - Expires {expiry_date.strftime('%b %d, %Y')}")
                    
                    if st.button("🔄 Start Over"):
                        st.session_state.step = 1
                        st.session_state.selected_items = []
                        st.rerun()
            else:
                st.button("✅ Save to Pantry", disabled=True, help="Organize all items first!")