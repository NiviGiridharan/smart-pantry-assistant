import streamlit as st
import pytesseract
from PIL import Image
import re
import json
from datetime import datetime, timedelta
from difflib import SequenceMatcher

# Set Tesseract path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Load FoodKeeper data
@st.cache_data
def load_foodkeeper():
    try:
        with open('foodkeeper.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {food['name'].lower(): food for food in data['foods']}
    except FileNotFoundError:
        st.warning("⚠️ foodkeeper.json not found! Using default shelf life estimates.")
        return {}

FOODKEEPER = load_foodkeeper()

def fuzzy_match(item_name, threshold=0.6):
    """Find best match for item in FoodKeeper database using fuzzy matching"""
    item_lower = item_name.lower().strip()
    
    best_match = None
    best_score = threshold
    
    for food_name in FOODKEEPER.keys():
        score = SequenceMatcher(None, item_lower, food_name).ratio()
        if score > best_score:
            best_score = score
            best_match = food_name
    
    return FOODKEEPER.get(best_match) if best_match else None

def get_shelf_life(item_name):
    """Get shelf life info for an item"""
    food_data = fuzzy_match(item_name)
    
    if food_data:
        return {
            'found': True,
            'category': food_data.get('category', 'unknown'),
            'recommended_storage': food_data.get('recommended_storage', 'shelf'),
            'shelf_life_fridge': food_data.get('shelf_life_fridge'),
            'shelf_life_shelf': food_data.get('shelf_life_shelf'),
            'tips': food_data.get('tips', '')
        }
    else:
        # Fallback to defaults
        return {
            'found': False,
            'category': 'unknown',
            'recommended_storage': 'shelf',
            'shelf_life_fridge': 7,
            'shelf_life_shelf': 7,
            'tips': 'No specific data found. Using default estimate.'
        }

def parse_walmart_order(texts):
    """Extract items from Walmart app screenshots (multiple images)
    texts: list of OCR text from multiple Walmart app screenshots
    """
    items = []
    combined_text = '\n'.join(texts)
    lines = combined_text.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        line_lower = line.lower()
        
        # Skip empty lines and headers
        if not line or any(skip in line_lower for skip in ['delivered', 'items received', 'weight-adjusted', 'shopped', 'review item', 'return eligible', 'delivery from', 'final weight']):
            i += 1
            continue
        
        # Look for price pattern (starts with $)
        price_match = re.search(r'\$(\d+[\.\s]\d{2})', line)
        
        if price_match:
            price = price_match.group(1).replace(' ', '.')
            item_name = line[:price_match.start()].strip()
            
            # Extract quantity from next few lines
            qty = 1
            unit_price_line = ""
            j = i + 1
            qty_found = False
            
            while j < len(lines) and j < i + 5:
                next_line = lines[j].strip().lower()
                
                # Look for Qty X pattern
                qty_match = re.search(r'qty\s*(\d+)', next_line)
                if qty_match:
                    qty = int(qty_match.group(1))
                    qty_found = True
                
                # Skip unit price lines ($/oz, $/fl oz, $/ea, etc.)
                if any(unit in next_line for unit in ['/lb', '/oz', '/fl', '/ea', 'flavor:', 'size:', 'final weight']):
                    unit_price_line = next_line
                    j += 1
                    continue
                
                # Stop at next price or empty line
                if re.search(r'\$\d+[\.\s]\d{2}', next_line) and j > i + 1:
                    break
                
                j += 1
            
            if item_name and len(item_name) > 3:
                shelf_data = get_shelf_life(item_name)
                items.append({
                    'name': item_name,
                    'price': f'${price}',
                    'qty': qty,
                    'category': shelf_data['category'],
                    'category_display': shelf_data.get('category', 'unknown'),
                    'recommended_storage': shelf_data['recommended_storage'],
                    'shelf_life_fridge': shelf_data['shelf_life_fridge'],
                    'shelf_life_shelf': shelf_data['shelf_life_shelf'],
                    'tips': shelf_data['tips'],
                    'storage_location': 'unsorted',
                    'expiry_days': None
                })
                
                i = j
                continue
        
        i += 1
    
    totals = {'walmart_order': True, 'items_count': len(items)}
    return items, totals

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
                    # Get shelf life data from FoodKeeper
                    shelf_data = get_shelf_life(item_name)
                    items.append({
                        'name': item_name,
                        'price': f'${price}',
                        'qty': 1,
                        'category': shelf_data['category'],
                        'category_display': shelf_data.get('category', 'unknown'),
                        'recommended_storage': shelf_data['recommended_storage'],
                        'shelf_life_fridge': shelf_data['shelf_life_fridge'],
                        'shelf_life_shelf': shelf_data['shelf_life_shelf'],
                        'tips': shelf_data['tips'],
                        'storage_location': 'unsorted',
                        'expiry_days': None
                    })
    
    return items, totals

# STREAMLIT UI
st.set_page_config(page_title="Smart Pantry Assistant", layout="wide")
st.title("🥘 Smart Pantry Assistant")
st.write("Upload your grocery receipt to get started!")

# Initialize session state FIRST
if 'scanned_items' not in st.session_state:
    st.session_state.scanned_items = None
if 'totals' not in st.session_state:
    st.session_state.totals = None
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'selected_items' not in st.session_state:
    st.session_state.selected_items = []
if 'order_type' not in st.session_state:
    st.session_state.order_type = None

# DEBUG MODE (set to False to disable)
DEBUG_MODE = True

# Choose order type
st.subheader("📱 What type of order?")
col1, col2 = st.columns(2)

with col1:
    if st.button("🏪 Physical Receipt", use_container_width=True):
        st.session_state.order_type = "receipt"

with col2:
    if st.button("📲 Walmart Online", use_container_width=True):
        st.session_state.order_type = "walmart"

if st.session_state.order_type is None:
    st.info("👆 Select an order type above to get started")
    st.stop()

# File uploader based on order type
if st.session_state.order_type == "receipt":
    uploaded_file = st.file_uploader("Choose a receipt image", type=['png', 'jpg', 'jpeg'])
else:  # walmart
    uploaded_files = st.file_uploader("Upload Walmart app screenshots (multiple OK)", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)
    uploaded_file = uploaded_files if uploaded_files else None

if uploaded_file:
    if st.session_state.order_type == "receipt":
        image = Image.open(uploaded_file)
        st.image(image, caption="Your Receipt", width=400)
        
        # DEBUG: Show raw OCR text
        if DEBUG_MODE:
            with st.expander("🔍 DEBUG: See Raw OCR Text"):
                raw_text = pytesseract.image_to_string(image)
                st.text_area("Raw OCR Output:", raw_text, height=200, disabled=True)
                st.write("**Line-by-line breakdown:**")
                for idx, line in enumerate(raw_text.split('\n')):
                    if line.strip():
                        st.write(f"Line {idx}: `{line}`")
        
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
    
    else:  # walmart
        st.write(f"📸 {len(uploaded_file)} screenshots selected")
        
        # Show previews
        with st.expander("Preview screenshots"):
            cols = st.columns(min(3, len(uploaded_file)))
            for idx, img_file in enumerate(uploaded_file):
                img = Image.open(img_file)
                with cols[idx % 3]:
                    st.image(img, caption=f"Image {idx+1}", use_column_width=True)
        
        # DEBUG: Show raw OCR text for each image
        if DEBUG_MODE:
            with st.expander("🔍 DEBUG: See Raw OCR Text (All Screenshots)"):
                for img_idx, img_file in enumerate(uploaded_file):
                    st.write(f"**Screenshot {img_idx + 1}:**")
                    raw_text = pytesseract.image_to_string(Image.open(img_file))
                    st.text_area(f"OCR Output {img_idx + 1}:", raw_text, height=150, disabled=True, key=f"debug_walmart_{img_idx}")
                    st.divider()
        
        # Step 1: Scan Walmart Order
        if st.button("Scan Walmart Order"):
            with st.spinner("Reading screenshots..."):
                texts = []
                for img_file in uploaded_file:
                    image = Image.open(img_file)
                    text = pytesseract.image_to_string(image)
                    texts.append(text)
                
                items, totals = parse_walmart_order(texts)
                
                # Store in session state
                st.session_state.scanned_items = items
                st.session_state.totals = totals
                st.session_state.step = 1
                
                st.success(f"Found {len(items)} items from {len(uploaded_file)} screenshots!")
    
    # Step 2: Show scanned results
    if st.session_state.scanned_items and st.session_state.step == 1:
        st.subheader("📦 Items Found:")
        for item in st.session_state.scanned_items:
            col1, col2, col3, col4 = st.columns([3, 1, 1, 2])
            with col1:
                st.write(f"• {item['name']}")
            with col2:
                st.write(f"Qty: {item['qty']}")
            with col3:
                st.write(f"{item['price']}")
            with col4:
                if item['tips'] and 'No specific data' not in item['tips']:
                    st.caption(f"✓ FoodKeeper matched")
                else:
                    st.caption(f"⚠️ Default estimate")
        
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
        st.write("Move items to Fridge or Shelf. Expiry dates auto-populated from FoodKeeper.")
        
        # Create 3 columns
        col_unsorted, col_fridge, col_shelf = st.columns(3)
        
        with col_unsorted:
            st.markdown("### 📦 Unsorted")
            unsorted_count = 0
            
            for idx, item in enumerate(st.session_state.selected_items):
                if item['storage_location'] == 'unsorted':
                    unsorted_count += 1
                    
                    with st.container():
                        st.write(f"**{item['name']}**")
                        st.caption(f"{item['price']}")
                        if item['tips'] and 'No specific data' not in item['tips']:
                            st.caption(f"📚 {item['category'].capitalize()}")
                        
                        # Action buttons
                        btn_col1, btn_col2 = st.columns(2)
                        
                        with btn_col1:
                            if st.button("→ 🧊", key=f"to_fridge_{idx}", help="Move to Fridge"):
                                item['storage_location'] = 'fridge'
                                if item['shelf_life_fridge']:
                                    item['expiry_days'] = item['shelf_life_fridge']
                                st.rerun()
                        
                        with btn_col2:
                            if st.button("→ 🗄️", key=f"to_shelf_{idx}", help="Move to Shelf"):
                                item['storage_location'] = 'shelf'
                                if item['shelf_life_shelf']:
                                    item['expiry_days'] = item['shelf_life_shelf']
                                st.rerun()
                        
                        st.divider()
            
            if unsorted_count == 0:
                st.info("✓ All items organized!")
        
        with col_fridge:
            st.markdown("### 🧊 Refrigerator")
            fridge_count = 0
            
            for idx, item in enumerate(st.session_state.selected_items):
                if item['storage_location'] == 'fridge':
                    fridge_count += 1
                    
                    with st.container():
                        st.write(f"**{item['name']}**")
                        st.caption(f"{item['price']} | {item['category'].capitalize()}")
                        
                        # Expiry date input
                        default_days = item['expiry_days'] or item['shelf_life_fridge'] or 7
                        expiry = st.number_input(
                            "Days until expiry:",
                            min_value=1,
                            max_value=365,
                            value=default_days,
                            key=f"fridge_exp_{idx}"
                        )
                        item['expiry_days'] = expiry
                        
                        expiry_date = datetime.now() + timedelta(days=expiry)
                        st.caption(f"📅 Expires: {expiry_date.strftime('%b %d')}")
                        
                        if item['tips']:
                            st.caption(f"💡 {item['tips'][:60]}...")
                        
                        # Move back button
                        if st.button("← Back", key=f"fridge_back_{idx}"):
                            item['storage_location'] = 'unsorted'
                            st.rerun()
                        
                        st.divider()
            
            st.metric("Items", fridge_count)
        
        with col_shelf:
            st.markdown("### 🗄️ Pantry Shelf")
            shelf_count = 0
            
            for idx, item in enumerate(st.session_state.selected_items):
                if item['storage_location'] == 'shelf':
                    shelf_count += 1
                    
                    with st.container():
                        st.write(f"**{item['name']}**")
                        st.caption(f"{item['price']} | {item['category'].capitalize()}")
                        
                        # Expiry date input
                        default_days = item['expiry_days'] or item['shelf_life_shelf'] or 30
                        expiry = st.number_input(
                            "Days until expiry:",
                            min_value=1,
                            max_value=730,
                            value=default_days,
                            key=f"shelf_exp_{idx}"
                        )
                        item['expiry_days'] = expiry
                        
                        expiry_date = datetime.now() + timedelta(days=expiry)
                        st.caption(f"📅 Expires: {expiry_date.strftime('%b %d')}")
                        
                        if item['tips']:
                            st.caption(f"💡 {item['tips'][:60]}...")
                        
                        # Move back button
                        if st.button("← Back", key=f"shelf_back_{idx}"):
                            item['storage_location'] = 'unsorted'
                            st.rerun()
                        
                        st.divider()
            
            st.metric("Items", shelf_count)
        
        # Bottom action bar
        st.markdown("---")
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            categorized = sum(1 for item in st.session_state.selected_items if item['storage_location'] != 'unsorted')
            total = len(st.session_state.selected_items)
            st.progress(categorized / total if total > 0 else 0)
            st.caption(f"Progress: {categorized}/{total} items organized")
        
        with col2:
            if st.button("← Back to Selection"):
                st.session_state.step = 2
                st.rerun()
        
        with col3:
            all_categorized = all(item['storage_location'] != 'unsorted' for item in st.session_state.selected_items)
            if all_categorized:
                if st.button("✅ Save to Pantry", type="primary"):
                    st.success("🎉 Items saved to your pantry!")
                    st.balloons()
                    
                    # Show summary
                    with st.expander("📊 View Saved Items"):
                        for item in st.session_state.selected_items:
                            expiry_date = datetime.now() + timedelta(days=item['expiry_days'])
                            st.write(f"• {item['name']} ({item['storage_location']}) - Expires {expiry_date.strftime('%b %d, %Y')}")
                    
                    if st.button("🔄 Start Over"):
                        st.session_state.step = 1
                        st.session_state.selected_items = []
                        st.rerun()
            else:
                st.button("✅ Save to Pantry", disabled=True, help="Organize all items first!")