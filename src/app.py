def parse_receipt(text):
    """Extract items, totals, and tax from receipt"""
    items = []
    totals = {}
    lines = text.split('\n')
    
    for line in lines:
        line_lower = line.lower()
        
        # Capture tax
        if 'tax' in line_lower and 'total' not in line_lower:
            price_match = re.search(r'(\d+\.\d{2})', line)
            if price_match:
                totals['tax'] = f'${price_match.group(1)}'
        
        # Capture grand total
        elif 'grand total' in line_lower:
            price_match = re.search(r'(\d+\.\d{2})', line)
            if price_match:
                totals['grand_total'] = f'${price_match.group(1)}'
        
        # Capture order total (fallback)
        elif 'order total' in line_lower or ('total' in line_lower and 'grand' not in line_lower):
            if 'grand_total' not in totals:  # Only if we haven't found grand total
                price_match = re.search(r'(\d+\.\d{2})', line)
                if price_match:
                    totals['grand_total'] = f'${price_match.group(1)}'
        
        # Regular items
        elif not any(word in line_lower for word in ['savings', 'payment', 'change', 'cash', 'credit', 'debit', 'manager', 'store', 'ocala']):
            price_match = re.search(r'(\d+\.\d{2})', line)
            if price_match:
                price = price_match.group(1)
                item_name = line[:price_match.start()].strip()
                if item_name and len(item_name) > 3:
                    # Don't deduplicate - add every item even if duplicate
                    items.append({'name': item_name, 'price': f'${price}'})
    
    return items, totals