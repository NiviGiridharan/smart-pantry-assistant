import streamlit as st
import pytesseract
from PIL import Image
import re
import json
from datetime import datetime, timedelta
from difflib import SequenceMatcher

# Configure Tesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

@st.cache_data
def load_foodkeeper():
    """Load FoodKeeper database with shelf life info"""
    try:
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        filepath = os.path.join(current_dir, 'foodkeeper.json')
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {food['name'].lower(): food for food in data['foods']}
    except Exception as e:
        st.warning(f"⚠️ Could not load FoodKeeper database. Using default shelf life estimates.")
        return {}

FOODKEEPER = load_foodkeeper()

def fuzzy_match(item_name, threshold=0.6):
    """Match item name to FoodKeeper database using fuzzy string matching"""
    item_lower = item_name.lower().strip()
    best_match = None
    best_score = threshold
    
    # Try exact substring match first (faster)
    for food_name in FOODKEEPER.keys():
        if food_name in item_lower or item_lower in food_name:
            return FOODKEEPER[food_name]
    
    # Fall back to fuzzy matching
    for food_name in FOODKEEPER.keys():
        score = SequenceMatcher(None, item_lower, food_name).ratio()
        if score > best_score:
            best_score = score
            best_match = food_name
    
    return FOODKEEPER.get(best_match) if best_match else None

def get_shelf_life(item_name):
    """Get shelf life data for an item"""
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
        return {
            'found': False,
            'category': 'unknown',
            'recommended_storage': 'shelf',
            'shelf_life_fridge': 7,
            'shelf_life_shelf': 7,
            'tips': 'No specific data found. Using default estimate.'
        }

def parse_walmart_order(texts):
    """Extract items from Walmart app screenshots - returns raw items without matching"""
    items = []
    combined_text = '\n'.join(texts)
    lines = combined_text.split('\n')
    
    # Lines to skip - these aren't grocery items
    skip_keywords = [
        'delivered', 'items received', 'weight-adjusted', 'shopped', 'review item', 
        'return eligible', 'delivery from', 'final weight', 'subtotal', 'driver tip',
        'payment method', 'temporary hold', 'ending in', 'charge history',
        'wove', 'congratulations', 'track order', 'contact', 'unavailable', 'how can we help',
        'start a return', 'transaction activity', 'order#', 'your payment', 'charge',
        'free delivery', 'sponsored'
    ]
    
    totals_keywords = ['tax', 'total', 'subtotal', 'driver tip']
    totals = {}

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        line_lower = line.lower()
        
        if not line:
            i += 1
            continue
        
        # Capture order totals
        if any(total_word in line_lower for total_word in totals_keywords):
            price_match = re.search(r'\$(\d+[\.\s]\d{2})', line)
            if price_match:
                price = price_match.group(1).replace(' ', '.')
                if 'tax' in line_lower:
                    totals['tax'] = f'${price}'
                elif 'subtotal' in line_lower:
                    totals['subtotal'] = f'${price}'
                elif 'driver tip' in line_lower:
                    totals['driver_tip'] = f'${price}'
                elif 'total' in line_lower and 'subtotal' not in line_lower:
                    totals['total'] = f'${price}'
            i += 1
            continue

        if any(skip in line_lower for skip in skip_keywords):
            i += 1
            continue
        
        # Look for price pattern
        price_match = re.search(r'\$(\d+[\.\s]\d{2})', line)
        
        if price_match:
            price = price_match.group(1).replace(' ', '.')
            item_name = line[:price_match.start()].strip()
            
            # Item names can span multiple lines - look backwards if needed
            if not item_name or len(item_name) < 2:
                for back_idx in range(1, min(4, i+1)):
                    prev_line = lines[i-back_idx].strip()
                    prev_line_lower = prev_line.lower()
                    
                    if any(skip in prev_line_lower for skip in skip_keywords) or \
                       any(unit in prev_line_lower for unit in ['/lb', '/oz', '/fl', '/ea', 'multipack', 'qty']) or \
                       any(total in prev_line_lower for total in totals_keywords):
                        continue
                    
                    if item_name:
                        item_name = prev_line + " " + item_name
                    else:
                        item_name = prev_line
            
            # Skip if we still don't have a valid item name
            if not item_name or len(item_name) < 2 or item_name.isdigit() or item_name.startswith('$'):
                i += 1
                continue
            
            # Look for quantity in the next few lines
            qty = 1
            j = i + 1
            
            while j < len(lines) and j < i + 5:
                next_line = lines[j].strip().lower()
                
                qty_match = re.search(r'qty\s*(\d+)', next_line)
                if qty_match:
                    qty = int(qty_match.group(1))
                    break
                
                if any(unit in next_line for unit in ['/lb', '/oz', '/fl', '/ea', 'flavor:', 'size:', 'final weight', 'multipack']):
                    j += 1
                    continue
                
                if (re.search(r'\$\d+[\.\s]\d{2}', next_line) and j > i + 1) or \
                   any(skip in next_line for skip in skip_keywords):
                    break
                
                j += 1
            
            # Filter out obvious fragments
            word_count = len(item_name.split())
            if word_count == 1 and len(item_name) < 5:
                i += 1
                continue
            
            items.append({
                'name': item_name,
                'price': float(price),
                'qty': qty
            })
            
            i = j
            continue
        
        i += 1
    
    totals = {'walmart_order': True, 'items_count': len(items)}
    return items, totals

def parse_receipt(text):
    """Extract items from physical receipt - returns raw items without matching"""
    items = []
    totals = {}
    lines = text.split('\n')
    
    for line in lines:
        line_lower = line.lower()
        
        # Skip discounts
        if 'promotion' in line_lower or re.search(r'-\d+[\.\s]?\d{2}', line):
            continue
        
        # Capture totals
        if 'tax' in line_lower and 'total' not in line_lower:
            price_match = re.search(r'(\d+[\.\s]\d{2})', line)
            if price_match:
                totals['tax'] = f"${price_match.group(1).replace(' ', '.')}"
        
        elif 'grand total' in line_lower:
            price_match = re.search(r'(\d+[\.\s]\d{2})', line)
            if price_match:
                totals['grand_total'] = f"${price_match.group(1).replace(' ', '.')}"
        
        elif 'order total' in line_lower:
            price_match = re.search(r'(\d+[\.\s]\d{2})', line)
            if price_match:
                totals['order_total'] = f"${price_match.group(1).replace(' ', '.')}"
        
        # Extract items
        elif not any(word in line_lower for word in ['savings', 'payment', 'change', 'cash', 'credit', 'debit', 'manager', 'store']):
            price_match = re.search(r'(\d+[\.\s]\d{2})', line)
            if price_match:
                price = price_match.group(1).replace(' ', '.')
                item_name = line[:price_match.start()].strip()
                if item_name and len(item_name) > 2:
                    items.append({
                        'name': item_name,
                        'price': float(price),
                        'qty': 1
                    })
    
    return items, totals

def apply_foodkeeper_matching(items):
    """Apply FoodKeeper matching to cleaned items after user edits"""
    matched_items = []
    for item in items:
        shelf_data = get_shelf_life(item['name'])
        matched_items.append({
            'name': item['name'],
            'price': f"${item['price']:.2f}",
            'qty': item['qty'],
            'category': shelf_data['category'],
            'category_display': shelf_data.get('category', 'unknown'),
            'recommended_storage': shelf_data['recommended_storage'],
            'shelf_life_fridge': shelf_data['shelf_life_fridge'],
            'shelf_life_shelf': shelf_data['shelf_life_shelf'],
            'tips': shelf_data['tips'],
            'storage_location': 'unsorted',
            'expiry_days': None,
            'is_produce': shelf_data['found']
        })
    return matched_items

# ============================================================================
# STREAMLIT UI
# ============================================================================

st.set_page_config(page_title="Smart Pantry Assistant", layout="wide")
st.title("🥘 Smart Pantry Assistant")
st.write("Upload your grocery receipt or Walmart screenshots to track your pantry!")

# Initialize session state
if 'raw_items' not in st.session_state:
    st.session_state.raw_items = None
if 'scanned_items' not in st.session_state:
    st.session_state.scanned_items = None
if 'totals' not in st.session_state:
    st.session_state.totals = None
if 'step' not in st.session_state:
    st.session_state.step = 0
if 'selected_items' not in st.session_state:
    st.session_state.selected_items = []
if 'order_type' not in st.session_state:
    st.session_state.order_type = None

# Step 0: Choose order type
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

# File uploader
if st.session_state.order_type == "receipt":
    uploaded_file = st.file_uploader("Choose a receipt image", type=['png', 'jpg', 'jpeg'])
else:
    uploaded_files = st.file_uploader("Upload Walmart app screenshots (multiple OK)", 
                                      type=['png', 'jpg', 'jpeg'], 
                                      accept_multiple_files=True)
    uploaded_file = uploaded_files if uploaded_files else None

if uploaded_file:
    # Scan receipts
    if st.session_state.order_type == "receipt":
        image = Image.open(uploaded_file)
        st.image(image, caption="Your Receipt", width=400)
        
        if st.button("Scan Receipt"):
            with st.spinner("Reading receipt..."):
                text = pytesseract.image_to_string(image)
                items, totals = parse_receipt(text)
                
                st.session_state.raw_items = items
                st.session_state.totals = totals
                st.session_state.step = 1
                
                st.success(f"Found {len(items)} items!")
                st.rerun()
    
    else:  # Walmart
        st.write(f"📸 {len(uploaded_file)} screenshots uploaded")
        
        with st.expander("Preview screenshots"):
            cols = st.columns(min(3, len(uploaded_file)))
            for idx, img_file in enumerate(uploaded_file):
                img = Image.open(img_file)
                with cols[idx % 3]:
                    st.image(img, caption=f"Image {idx+1}", use_column_width=True)
        
        if st.button("Scan Walmart Order"):
            with st.spinner("Reading screenshots..."):
                texts = []
                for img_file in uploaded_file:
                    image = Image.open(img_file)
                    text = pytesseract.image_to_string(image)
                    texts.append(text)
                
                items, totals = parse_walmart_order(texts)
                
                st.session_state.raw_items = items
                st.session_state.totals = totals
                st.session_state.step = 1
                
                st.success(f"Found {len(items)} items from {len(uploaded_file)} screenshots!")
                st.rerun()
    
    # ========================================================================
    # Step 1: EDIT ITEMS
    # ========================================================================
    if st.session_state.raw_items and st.session_state.step == 1:
        st.subheader("✏️ Review & Edit Items")
        st.info("💡 Fix any OCR errors. Delete junk items, correct names/prices, or add missing items.")
        
        # Initialize "adding new item" state
        if 'adding_new_item' not in st.session_state:
            st.session_state.adding_new_item = False
        
        # Column headers
        col1, col2, col3, col4 = st.columns([5, 2, 2, 1])
        with col1:
            st.markdown("**Item Name**")
        with col2:
            st.markdown("**Qty**")
        with col3:
            st.markdown("**Total Price**")
        with col4:
            st.markdown("**Delete**")
        
        st.divider()
        
        edited_items = []
        items_to_delete = []
        
        # Edit existing items
        for idx, item in enumerate(st.session_state.raw_items):
            col1, col2, col3, col4 = st.columns([5, 2, 2, 1])
            
            with col1:
                new_name = st.text_input("Item Name", value=item['name'], key=f"name_{idx}", 
                                        label_visibility="collapsed", placeholder="Item name")
            
            with col2:
                new_qty = st.number_input("Qty", value=item['qty'], min_value=1, key=f"qty_{idx}", 
                                         label_visibility="collapsed")
            
            with col3:
                # Single total price field
                total_price = item['price'] * item['qty'] if 'qty' in item else item['price']
                new_total = st.number_input("Total Price", value=total_price, min_value=0.01, 
                                           step=0.01, format="%.2f", key=f"total_{idx}", 
                                           label_visibility="collapsed")
            
            with col4:
                if st.button("🗑️", key=f"del_{idx}", help="Delete this item"):
                    items_to_delete.append(idx)
            
            if idx not in items_to_delete:
                edited_items.append({
                    'name': new_name,
                    'qty': new_qty,
                    'price': new_total / new_qty
                })
        
        # Show new item form if user clicked "Add Item"
        if st.session_state.adding_new_item:
            col1, col2, col3, col4 = st.columns([5, 2, 2, 1])
            
            with col1:
                add_name = st.text_input("Item Name", key="add_name", placeholder="e.g., Pesto Sauce",
                                        label_visibility="collapsed")
            
            with col2:
                add_qty = st.number_input("Qty", value=1, min_value=1, key="add_qty",
                                         label_visibility="collapsed")
            
            with col3:
                add_price = st.number_input("Total Price", value=0.00, min_value=0.00, step=0.01, 
                                           format="%.2f", key="add_price",
                                           label_visibility="collapsed")
            
            with col4:
                if st.button("➕", key="confirm_add", help="Add this item", use_container_width=True):
                    if add_name.strip() and add_price > 0:
                        edited_items.append({
                            'name': add_name.strip(),
                            'qty': add_qty,
                            'price': add_price / add_qty
                        })
                        st.session_state.raw_items = edited_items
                        st.session_state.adding_new_item = False
                        st.success(f"✅ Added {add_name.strip()}")
                        st.rerun()
                    else:
                        st.error("Please enter item name and price")
        
        st.divider()
        
        # Add Item button (shows form above)
        if not st.session_state.adding_new_item:
            if st.button("➕ Add Missing Item", use_container_width=True):
                st.session_state.adding_new_item = True
                st.rerun()
        
        # Summary and next
        st.markdown("---")
        col1, col2 = st.columns([3, 1])
        
        with col1:
            total = sum(item['price'] * item['qty'] for item in edited_items)
            st.write(f"**Total: ${total:.2f}** • {len(edited_items)} items")
        
        with col2:
            if edited_items:
                if st.button("Next: Match Items →", type="primary", use_container_width=True):
                    st.session_state.raw_items = edited_items
                    st.session_state.scanned_items = apply_foodkeeper_matching(edited_items)
                    st.session_state.step = 2
                    st.rerun()
            else:
                st.button("Next: Match Items →", disabled=True, help="Add at least one item")
    
    # ========================================================================
    # Step 2: FILTER GROCERY ITEMS
    # ========================================================================
    if st.session_state.get('step') == 2:
        st.subheader("🥕 Select Items to Track")
        st.write("Choose which items you want to track in your pantry (uncheck non-food items like gift bags, toiletries, etc.)")
        
        filtered_items = []
        for i, item in enumerate(st.session_state.scanned_items):
            # Auto-check items that matched FoodKeeper database
            default_checked = item.get('is_produce', False)
            
            col1, col2 = st.columns([5, 1])
            with col1:
                is_selected = st.checkbox(
                    f"{item['name']} ({item['category'].capitalize()}) - {item['price']}", 
                    value=default_checked, 
                    key=f"filter_{i}"
                )
            with col2:
                if item.get('is_produce'):
                    st.write("✅ Food")
                else:
                    st.write("⚠️ Other")
            
            if is_selected:
                filtered_items.append(item)
        
        st.markdown("---")
        st.write(f"**Tracking {len(filtered_items)} of {len(st.session_state.scanned_items)} items**")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("← Back to Edit", use_container_width=True):
                st.session_state.step = 1
                st.rerun()
        
        with col2:
            if filtered_items:
                if st.button("Next: Select Your Items →", type="primary", use_container_width=True):
                    st.session_state.scanned_items = filtered_items
                    st.session_state.step = 3
                    st.rerun()
            else:
                st.button("Next: Select Your Items →", disabled=True, 
                         help="Select at least one item to track")
    
    # ========================================================================
    # Step 3: SELECT YOUR ITEMS (split bills)
    # ========================================================================
    if st.session_state.get('step') == 3:
        st.subheader("✅ Select Your Items")
        st.write("If you're splitting a bill, uncheck items that aren't yours")
        
        selected_items = []
        for i, item in enumerate(st.session_state.scanned_items):
            is_selected = st.checkbox(f"{item['name']} - {item['price']}", value=True, key=f"item_{i}")
            if is_selected:
                selected_items.append(item)
        
        st.markdown("---")
        st.write(f"**You selected {len(selected_items)} of {len(st.session_state.scanned_items)} items**")
        
        if selected_items:
            your_total = sum(float(item['price'].replace('$', '')) for item in selected_items)
            st.write(f"**Your Total: ${your_total:.2f}**")
            
            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("← Back to Filter", use_container_width=True):
                    st.session_state.step = 2
                    st.rerun()
            
            with col2:
                if st.button("Next: Organize Pantry →", type="primary", use_container_width=True):
                    st.session_state.selected_items = selected_items
                    st.session_state.step = 4
                    st.rerun()
    
    # ========================================================================
    # Step 4: ORGANIZE INTO FRIDGE/SHELF
    # ========================================================================
    if st.session_state.get('step') == 4:
        st.subheader("🗂️ Organize Your Pantry")
        st.write("Drag items into Fridge or Shelf. Expiry dates are auto-filled based on USDA guidelines.")
        
        col_unsorted, col_fridge, col_shelf = st.columns(3)
        
        # Unsorted column
        with col_unsorted:
            st.markdown("### 📦 Unsorted")
            unsorted_count = 0
            
            for idx, item in enumerate(st.session_state.selected_items):
                if item['storage_location'] == 'unsorted':
                    unsorted_count += 1
                    
                    st.write(f"**{item['name']}**")
                    st.caption(f"{item['price']} • Qty: {item['qty']}")
                    if item['category'] != 'unknown':
                        st.caption(f"📚 {item['category'].capitalize()}")
                    
                    btn_col1, btn_col2 = st.columns(2)
                    with btn_col1:
                        if st.button("→ Fridge", key=f"to_fridge_{idx}", use_container_width=True):
                            item['storage_location'] = 'fridge'
                            if item['shelf_life_fridge']:
                                item['expiry_days'] = item['shelf_life_fridge']
                            st.rerun()
                    
                    with btn_col2:
                        if st.button("→ Shelf", key=f"to_shelf_{idx}", use_container_width=True):
                            item['storage_location'] = 'shelf'
                            if item['shelf_life_shelf']:
                                item['expiry_days'] = item['shelf_life_shelf']
                            st.rerun()
                    
                    st.divider()
            
            if unsorted_count == 0:
                st.success("✓ All items organized!")
        
        # Fridge column
        with col_fridge:
            st.markdown("### 🧊 Refrigerator")
            fridge_count = 0
            
            for idx, item in enumerate(st.session_state.selected_items):
                if item['storage_location'] == 'fridge':
                    fridge_count += 1
                    
                    st.write(f"**{item['name']}**")
                    st.caption(f"{item['price']} • {item['category'].capitalize()}")
                    
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
                    st.caption(f"📅 Expires: {expiry_date.strftime('%b %d, %Y')}")
                    
                    if item['tips'] and 'No specific data' not in item['tips']:
                        st.caption(f"💡 {item['tips'][:50]}...")
                    
                    if st.button("← Back", key=f"fridge_back_{idx}", use_container_width=True):
                        item['storage_location'] = 'unsorted'
                        st.rerun()
                    
                    st.divider()
            
            st.metric("Items in Fridge", fridge_count)
        
        # Shelf column
        with col_shelf:
            st.markdown("### 🗄️ Pantry Shelf")
            shelf_count = 0
            
            for idx, item in enumerate(st.session_state.selected_items):
                if item['storage_location'] == 'shelf':
                    shelf_count += 1
                    
                    st.write(f"**{item['name']}**")
                    st.caption(f"{item['price']} • {item['category'].capitalize()}")
                    
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
                    st.caption(f"📅 Expires: {expiry_date.strftime('%b %d, %Y')}")
                    
                    if item['tips'] and 'No specific data' not in item['tips']:
                        st.caption(f"💡 {item['tips'][:50]}...")
                    
                    if st.button("← Back", key=f"shelf_back_{idx}", use_container_width=True):
                        item['storage_location'] = 'unsorted'
                        st.rerun()
                    
                    st.divider()
            
            st.metric("Items on Shelf", shelf_count)
        
        # Progress bar
        st.markdown("---")
        categorized = sum(1 for item in st.session_state.selected_items 
                         if item['storage_location'] != 'unsorted')
        total = len(st.session_state.selected_items)
        
        st.progress(categorized / total if total > 0 else 0)
        st.caption(f"Progress: {categorized}/{total} items organized")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if st.button("← Back to Selection", use_container_width=True):
                st.session_state.step = 3
                st.rerun()
        
        with col2:
            all_categorized = all(item['storage_location'] != 'unsorted' 
                                 for item in st.session_state.selected_items)
            if all_categorized:
                if st.button("✅ Save to Pantry", type="primary", use_container_width=True):
                    st.success("🎉 Items saved to your pantry!")
                    st.balloons()
                    
                    with st.expander("📊 View Saved Items"):
                        for item in st.session_state.selected_items:
                            expiry_date = datetime.now() + timedelta(days=item['expiry_days'])
                            location_icon = "🧊" if item['storage_location'] == 'fridge' else "🗄️"
                            st.write(f"{location_icon} {item['name']} - Expires {expiry_date.strftime('%b %d, %Y')}")
                    
                    if st.button("🔄 Start Over"):
                        # Reset everything
                        st.session_state.step = 0
                        st.session_state.selected_items = []
                        st.session_state.raw_items = None
                        st.session_state.scanned_items = None
                        st.session_state.order_type = None
                        st.rerun()
            else:
                st.button("✅ Save to Pantry", disabled=True, 
                         help="Please organize all items first!")