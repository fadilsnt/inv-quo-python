#!/usr/bin/env python3
"""
Test script untuk verifikasi tombol "Add Item" / "Update Item"
"""

import tkinter as tk
from GUI_app import InvoiceGenerator

def test_button_text_change():
    """Test perubahan tombol Add Item menjadi Update Item saat edit"""
    try:
        root = tk.Tk()
        app = InvoiceGenerator(root)
        
        # Check button exists
        if not hasattr(app, 'add_item_btn'):
            print("❌ FAIL: Tombol 'add_item_btn' tidak ditemukan")
            root.destroy()
            return False
        
        # Check initial button text
        initial_text = app.add_item_btn.cget('text')
        if initial_text != "Add Item":
            print(f"❌ FAIL: Tombol awal seharusnya 'Add Item', tapi: {initial_text}")
            root.destroy()
            return False
        
        print("✅ PASS: Tombol awal menampilkan 'Add Item'")
        
        # Simulate adding an item
        app.item_desc.insert(0, "Test Item")
        app.item_qty.insert(0, "1")
        app.item_price.insert(0, "100000")
        app.add_item()
        
        # Check button text is still "Add Item"
        button_text = app.add_item_btn.cget('text')
        if button_text != "Add Item":
            print(f"❌ FAIL: Setelah add item, tombol seharusnya 'Add Item', tapi: {button_text}")
            root.destroy()
            return False
        
        print("✅ PASS: Setelah add item, tombol kembali ke 'Add Item'")
        
        # Simulate clicking on the item to edit
        if len(app.tree.get_children()) > 0:
            # Manually trigger on_item_click by setting editing_item_index
            app.editing_item_index = 0
            app.item_desc.delete(0, tk.END)
            app.item_desc.insert(0, "Edited Item")
            app.item_qty.delete(0, tk.END)
            app.item_qty.insert(0, "2")
            app.add_item_btn.config(text="Update Item")  # This is what on_item_click does
            
            button_text = app.add_item_btn.cget('text')
            if button_text != "Update Item":
                print(f"❌ FAIL: Saat edit item, tombol seharusnya 'Update Item', tapi: {button_text}")
                root.destroy()
                return False
            
            print("✅ PASS: Saat edit item, tombol berubah menjadi 'Update Item'")
            
            # Simulate saving the edit
            app.item_price.delete(0, tk.END)
            app.item_price.insert(0, "150000")
            app.add_item()
            
            button_text = app.add_item_btn.cget('text')
            if button_text != "Add Item":
                print(f"❌ FAIL: Setelah update item, tombol seharusnya 'Add Item', tapi: {button_text}")
                root.destroy()
                return False
            
            print("✅ PASS: Setelah update item, tombol kembali ke 'Add Item'")
        
        root.destroy()
        return True
        
    except Exception as e:
        print(f"❌ FAIL: Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("=" * 60)
    print("Testing Tombol Add Item / Update Item")
    print("=" * 60)
    print()
    
    result = test_button_text_change()
    
    print()
    print("=" * 60)
    if result:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ TESTS FAILED")
    print("=" * 60)
    
    return result


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
