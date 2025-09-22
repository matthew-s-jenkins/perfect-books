from engine_v1 import BusinessSimulator
import os

def print_status(sim):
    """Prints a formatted summary of the business status."""
    summary = sim.get_status_summary()
    os.system('cls' if os.name == 'nt' else 'clear') # Clear the screen
    print("=" * 60)
    print("      DIGITAL HARVEST - BUSINESS STATUS")
    print("=" * 60)
    print(f"Date: {summary['date'].strftime('%Y-%m-%d')}      Cash: ${summary['cash']:,.2f}")
    print("-" * 60)
    
    print("INVENTORY ON HAND:")
    if not summary['inventory']:
        print("  - No inventory in stock.")
    else:
        for item in summary['inventory']:
            print(f"  - (ID: {item['id']}) {item['name']}: {item['stock']} units @ ${item['price']:,.2f}/unit")
    print("-" * 60)

    print("OPEN PURCHASE ORDERS:")
    if not summary['open_pos']:
        print("  - No open purchase orders.")
    else:
        for po in summary['open_pos']:
            print(f"  - PO #{po['order_id']} from {po['vendor_name']}, due {po['expected_arrival_date'].strftime('%Y-%m-%d')}")
    print("=" * 60)

def handle_place_order(sim):
    """Handles the user input for placing a new order."""
    print("\n--- Place New Purchase Order ---")
    
    # --- NEW: Display vendors first ---
    vendors = sim.get_all_vendors()
    if not vendors:
        print("No vendors available.")
        input("\nPress Enter to return to the menu...")
        return
        
    print("Available Vendors:")
    for v in vendors:
        print(f"  - ID: {v['vendor_id']} | {v['name']} ({v['location']}) | Min. Order: ${v['minimum_order_value']:,.2f}")
    print("-" * 30)
    # --- END NEW ---

    try:
        vendor_id = int(input("Enter Vendor ID: "))
        
        items = {}
        while True:
            product_id_str = input("Enter Product ID to add (or 'done' to finish): ")
            if product_id_str.lower() == 'done':
                break
            quantity_str = input(f"Enter quantity for Product ID {product_id_str}: ")
            items[int(product_id_str)] = int(quantity_str)
        
        if items:
            sim.place_order(vendor_id, items)
        else:
            print("No items entered. Order cancelled.")

    except ValueError:
        print("Invalid input. Please enter numbers for IDs and quantities.")
    input("\nPress Enter to return to the menu...")

def handle_set_price(sim):
    """Handles user input for setting a new price."""
    print("\n--- Set Selling Price ---")
    try:
        product_id = int(input("Enter Product ID to price: "))
        new_price = float(input(f"Enter new selling price for Product ID {product_id}: $"))
        sim.set_selling_price(product_id, new_price)
    except ValueError:
        print("Invalid input. Please enter numbers.")
    input("\nPress Enter to return to the menu...")
    
def handle_advance_time(sim):
    """Handles user input for advancing time."""
    print("\n--- Advance Time ---")
    try:
        days = int(input("How many days to simulate? (1-30): "))
        if 1 <= days <= 30:
            sim.advance_time(days)
        else:
            print("Please enter a number between 1 and 30.")
    except ValueError:
        print("Invalid input. Please enter a number.")
    input("\nPress Enter to return to the menu...")

def main():
    """Main game loop."""
    try:
        sim = BusinessSimulator()
    except Exception as e:
        print(f"FATAL: Could not initialize simulator. Is the database running? Error: {e}")
        return

    while True:
        print_status(sim)
        print("\n--- MAIN MENU ---")
        print("1. Place Purchase Order")
        print("2. Set Selling Price")
        print("3. Advance Time")
        print("4. Exit")
        
        choice = input("> ")
        
        if choice == '1':
            handle_place_order(sim)
        elif choice == '2':
            handle_set_price(sim)
        elif choice == '3':
            handle_advance_time(sim)
        elif choice == '4':
            print("Goodbye!")
            break
        else:
            print("Invalid choice, please try again.")
            input("Press Enter to continue...")

if __name__ == "__main__":
    main()