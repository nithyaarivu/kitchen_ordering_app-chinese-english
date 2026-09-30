import streamlit as st
import pandas as pd
from datetime import datetime
import os

# Page configuration
st.set_page_config(
    page_title="Kitchen Ordering System",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for mobile-friendly design
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        background-color: #2563eb;
        color: white;
        border-radius: 8px;
        padding: 0.5rem;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #1e40af;
    }
    .price-tag {
        color: #2563eb;
        font-size: 1.25rem;
        font-weight: bold;
    }
    .success-box {
        background-color: #dcfce7;
        padding: 1.5rem;
        border-radius: 8px;
        border: 2px solid #16a34a;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# ===========================================
# CONFIGURATION - Set your Excel file path here
# ===========================================
# Put your Excel file in the SAME FOLDER as this Python file
# Then set the filename here:
EXCEL_FILE_NAME = "EXCEL FILE NAME"  # Change this to your file name

#TELEGRAM_BOT_TOKEN = "TOKEN"
#TELEGRAM_CHAT_ID = "ID"  #
GOOGLE_SCRIPT_URL = " https:"#
MANAGER_PASSWORD = "MANAGER PASSWORD"  #
# ===========================================

# Initialize session state
if 'cart' not in st.session_state:
    st.session_state.cart = {}
if 'order_history' not in st.session_state:
    st.session_state.order_history = []
if 'inventory' not in st.session_state:
    st.session_state.inventory = None
if 'show_success' not in st.session_state:
    st.session_state.show_success = False
if 'user_name' not in st.session_state:
    st.session_state.user_name = ""


# Function to load Excel file
@st.cache_data
def load_excel_data(file_path):
    """Load and parse Excel file with multiple sheets"""
    all_items = []
    item_id = 1

    try:
        # Determine engine based on file extension
        if file_path.endswith('.xls'):
            engine = 'xlrd'
        else:
            engine = 'openpyxl'

        # Read all sheets
        excel_file = pd.ExcelFile(file_path, engine=engine)

        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel('Food_items.xls', sheet_name=sheet_name, header=None, engine=engine)

            # Start from row 2 (index 2)
            for idx in range(2, len(df)):
                row = df.iloc[idx]

                # Each row has 3 sets of items (columns 0-2, 4-6, 8-10)
                item_sets = [
                    {'name': 0, 'spec': 1, 'price': 2},
                    {'name': 4, 'spec': 5, 'price': 6},
                    {'name': 8, 'spec': 9, 'price': 10}
                ]

                for item_set in item_sets:
                    try:
                        name = row[item_set['name']]
                        spec = row[item_set['spec']]
                        price_str = row[item_set['price']]

                        # Skip empty rows
                        if pd.isna(name) or str(name).strip() == '':
                            continue

                        # Extract price
                        import re
                        price_match = re.search(r'[\d.]+', str(price_str))
                        price = float(price_match.group()) if price_match else 0

                        all_items.append({
                            'id': item_id,
                            'name': str(name).strip(),
                            'category': sheet_name,
                            'unit': str(spec).strip() if not pd.isna(spec) else '',
                            'price': price
                        })
                        item_id += 1
                    except:
                        continue

        return pd.DataFrame(all_items)
    except Exception as e:
        st.error(f"Error loading Excel file: {e}")
        return None


# Function to add item to cart
def add_to_cart(item_id, item_name, price, unit, category):
    if item_id in st.session_state.cart:
        st.session_state.cart[item_id]['quantity'] += 1
    else:
        st.session_state.cart[item_id] = {
            'name': item_name,
            'price': price,
            'unit': unit,
            'category': category,
            'quantity': 1
        }


# Function to update quantity
def update_quantity(item_id, change):
    if item_id in st.session_state.cart:
        st.session_state.cart[item_id]['quantity'] += change
        if st.session_state.cart[item_id]['quantity'] <= 0:
            del st.session_state.cart[item_id]


# Function to calculate cart total
def calculate_total():
    total = 0
    for item in st.session_state.cart.values():
        total += item['price'] * item['quantity']
    return total


# Function to complete order
# Function to complete order
# Function to complete order
def complete_order():
    """Complete the order and save to CSV"""
    try:
        from datetime import datetime, timedelta
        from pathlib import Path
        import csv

        if not st.session_state.cart:
            return False

        # Create orders directory if it doesn't exist
        orders_dir = Path("orders")
        orders_dir.mkdir(exist_ok=True)

        orders_file = orders_dir / "all_orders.csv"

        # Get UAE time (UTC+4)
        uae_time = datetime.utcnow() + timedelta(hours=4)
        order_date = uae_time.strftime("%Y-%m-%d")
        order_time = uae_time.strftime("%H:%M:%S")

        # Prepare order data
        total = calculate_total()
        user_name = st.session_state.get('user_name', 'Guest User')

        # Check if file exists to determine if we need headers
        file_exists = orders_file.exists()

        # Write to CSV
        with open(orders_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # Write header if file is new - IN THE CORRECT ORDER
            if not file_exists:
                writer.writerow(['Order Date', 'Order Time', 'User Name', 'Item Name',
                                 'Category', 'Unit', 'Quantity', 'Unit Price (AED)',
                                 'Item Total (AED)', 'Order Total (AED)'])

            # Write each item in the cart - IN THE CORRECT ORDER
            for item in st.session_state.cart.values():
                writer.writerow([
                    order_date,  # Order Date
                    order_time,  # Order Time
                    user_name,  # User Name
                    item['name'],  # Item Name
                    item['category'],  # Category
                    item['unit'],  # Unit
                    item['quantity'],  # Quantity
                    f"{item['price']:.2f}",  # Unit Price (AED)
                    f"{item['price'] * item['quantity']:.2f}",  # Item Total (AED)
                    f"{total:.2f}"  # Order Total (AED)
                ])

        # Send Telegram notification
        send_telegram_notification(user_name, st.session_state.cart, total, order_date, order_time)

        # Save to order history
        st.session_state.order_history.append({
            'date': f"{order_date} {order_time}",
            'user_name': user_name,
            'items': dict(st.session_state.cart),
            'total': total
        })

        # Clear the cart
        st.session_state.cart.clear()

        return True

    except Exception as e:
        st.error(f"Error completing order: {str(e)}")
        return False

# Function to save order to CSV file
def save_order_to_file(order):
    """Save order to a CSV file that the manager can access"""
    try:
        import csv
        from pathlib import Path

        # Create orders directory if it doesn't exist
        orders_dir = Path("orders")
        orders_dir.mkdir(exist_ok=True)

        # CSV file for all orders
        csv_file = orders_dir / "all_orders.csv"

        # ... rest of CSV saving code ...

        # Send notification AFTER saving
        st.write("DEBUG: Calling send_order_notification...")
        send_order_notification(order)
        st.write("DEBUG: Notification function called")

        return True
    except Exception as e:
        st.error(f"Error saving order: {e}")
        return False


# Function to send order notification
def send_order_notification(order):
    """Send order to Google Sheets and Telegram"""

    # Send to Google Sheets
    send_to_google_sheets(order)

    # Send Telegram notification
    send_telegram_notification(order)


def send_to_google_sheets(order):
    """Send order to Google Sheets via Apps Script"""
    try:
        if not GOOGLE_SCRIPT_URL:
            return

        import requests

        # Prepare order data
        order_items = []
        for item in order['items'].values():
            order_items.append({
                'name': item['name'],
                'category': item['category'],
                'quantity': item['quantity'],
                'unit': item['unit'],
                'price': item['price'],
                'total': item['price'] * item['quantity']
            })

        notification_data = {
            'date': order['date'],
            'user_name': order['user_name'],
            'items': order_items,
            'total': order['total']
        }

        # Send to Google Sheets
        response = requests.post(
            GOOGLE_SCRIPT_URL,
            json=notification_data,
            timeout=10
        )

        if response.status_code == 200:
            print(f"✅ Order sent to Google Sheets!")
        else:
            print(f"⚠️ Google Sheets error: {response.status_code}")

    except Exception as e:
        print(f"⚠️ Could not send to Google Sheets: {e}")


def send_telegram_notification(user_name, cart, total, order_date, order_time):
    """Send order notification via Telegram"""
    try:
        import requests

        # Get Telegram credentials from secrets
        BOT_TOKEN = st.secrets.get("8292262434:AAFvu-cODj6uKciqjox-hlCuGAvQrZu-QCk", "")
        CHAT_ID = st.secrets.get("6935996612", "")

        # Check if credentials are configured
        if not BOT_TOKEN or not CHAT_ID:
            st.warning("⚠️ Telegram notifications not configured. Order saved successfully.")
            return False

        # Build the message
        message = f"🔔 *NEW ORDER RECEIVED*\n\n"
        message += f"📅 Date: {order_date}\n"
        message += f"⏰ Time: {order_time}\n"
        message += f"👤 User: {user_name}\n"
        message += f"{'=' * 30}\n\n"

        message += "*📦 Order Items:*\n"
        for item in cart.values():
            item_total = item['price'] * item['quantity']
            message += f"• {item['name']}\n"
            message += f"  └ {item['quantity']} x {item['price']:.2f} AED = {item_total:.2f} AED\n"

        message += f"\n{'=' * 30}\n"
        message += f"💰 *TOTAL: {total:.2f} AED*"

        # Send via Telegram
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': CHAT_ID,
            'text': message,
            'parse_mode': 'Markdown'
        }

        response = requests.post(url, json=payload)

        if response.status_code == 200:
            return True
        else:
            st.warning(f"Telegram notification failed: {response.text}")
            return False

    except Exception as e:
        st.warning(f"Could not send Telegram notification: {str(e)}")
        return False

# Load inventory on first run
if st.session_state.inventory is None:
    # Look for the file in the same directory as this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    excel_file_path = os.path.join(script_dir, EXCEL_FILE_NAME)

    # If not found, try current working directory
    if not os.path.exists(excel_file_path):
        excel_file_path = EXCEL_FILE_NAME

    # Check if file exists
    if not os.path.exists(excel_file_path):
        st.error(f"❌ Excel file not found: {EXCEL_FILE_NAME}")
        st.warning("""
        **Setup Instructions for Deployment:**
        1. Make sure your Excel file is uploaded to GitHub
        2. The file should be in the same folder as kitchen_app.py
        3. Update EXCEL_FILE_NAME at the top of the code to match your file name exactly
        4. The file name is case-sensitive!
        """)
        st.info(f"Looking for: {EXCEL_FILE_NAME}")
        st.info(f"Current directory: {os.getcwd()}")
        st.info(f"Files in current directory: {os.listdir('.')}")
        st.stop()

    # Load the file
    with st.spinner(f"Loading inventory from {EXCEL_FILE_NAME}..."):
        st.session_state.inventory = load_excel_data(excel_file_path)

    if st.session_state.inventory is None or len(st.session_state.inventory) == 0:
        st.error("❌ Could not load inventory!")
        st.stop()

# Main App
inventory = st.session_state.inventory

# Get user name if not set
if not st.session_state.user_name:
    st.title("🍽️ Kitchen Ordering System")
    st.subheader("Welcome! Please enter your name")

    user_name = st.text_input("Your Name", placeholder="e.g., John Doe")

    if st.button("Start Ordering", type="primary"):
        if user_name.strip():
            st.session_state.user_name = user_name.strip()
            st.rerun()
        else:
            st.error("Please enter your name")
    st.stop()

# Header
st.title("🍽️ Kitchen Ordering System")
st.markdown(f"**Welcome, {st.session_state.user_name}!** • {len(inventory)} items available")

# Add logout button in sidebar
with st.sidebar:
    st.write(f"👤 Logged in as: **{st.session_state.user_name}**")
    if st.button("Switch User"):
        st.session_state.user_name = ""
        st.rerun()

# Show success message after order
if st.session_state.show_success:
    st.markdown("""
    <div class='success-box'>
        <h2>✅ Order Placed Successfully!</h2>
        <p>Your order has been recorded. You can place a new order below.</p>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Continue Shopping"):
        st.session_state.show_success = False
        st.rerun()
    st.divider()

# Navigation
page = st.radio(
    "Navigation",
    ["🏠 Browse Items", "🛒 Cart", "📜 Order History", "👨‍💼 Manager View"],  # ✅ Correct
    horizontal=True,
    label_visibility="collapsed"
)

# Page 1: Browse Items
if page == "🏠 Browse Items":  # ✅ Has colon
    st.subheader("Browse Items")

    # Search and filter
    col1, col2 = st.columns([2, 1])
    with col1:
        search_query = st.text_input("🔍 Search items", "", key="search")
    with col2:
        categories = ['All'] + sorted(inventory['category'].unique().tolist())
        selected_category = st.selectbox("Category", categories)

    # Filter inventory
    filtered_df = inventory.copy()
    if search_query:
        filtered_df = filtered_df[
            filtered_df['name'].str.contains(search_query, case=False, na=False)
        ]
    if selected_category != 'All':
        filtered_df = filtered_df[filtered_df['category'] == selected_category]

    st.markdown(f"**{len(filtered_df)} items found**")

    # Display items
    for idx, row in filtered_df.iterrows():
        col1, col2, col3 = st.columns([4, 2, 2])

        with col1:
            st.markdown(f"**{row['name']}**")
            st.caption(f"{row['category']} • {row['unit']}")

        with col2:
            st.markdown(f"<span class='price-tag'>{row['price']:.2f} AED</span>", unsafe_allow_html=True)

        with col3:
            if row['id'] in st.session_state.cart:
                qty = st.session_state.cart[row['id']]['quantity']
                st.success(f"In cart: {qty}")

            if st.button("➕ Add", key=f"add_{row['id']}"):
                add_to_cart(row['id'], row['name'], row['price'], row['unit'], row['category'])
                st.rerun()

        st.divider()

    # Cart summary at bottom
    if st.session_state.cart:
        cart_count = sum(item['quantity'] for item in st.session_state.cart.values())
        st.info(f"🛒 Cart: {cart_count} items • Total: {calculate_total():.2f} AED")
# cart
elif page == "🛒 Cart":
    st.subheader("Your Order")

    if not st.session_state.cart:
        st.info("🛒 Your cart is empty. Add items from the Browse page!")
    else:
        # Display cart items
        for item_id, item in st.session_state.cart.items():
            col1, col2, col3, col4 = st.columns([4, 2, 2, 1])

            with col1:
                st.markdown(f"**{item['name']}**")
                st.caption(f"{item['category']} • {item['unit']}")

            with col2:
                st.markdown(f"{item['price']:.2f} AED")

            with col3:
                subcol1, subcol2, subcol3 = st.columns(3)
                with subcol1:
                    if st.button("➖", key=f"dec_{item_id}"):
                        update_quantity(item_id, -1)
                        st.rerun()
                with subcol2:
                    st.markdown(f"**{item['quantity']}**")
                with subcol3:
                    if st.button("➕", key=f"inc_{item_id}"):
                        update_quantity(item_id, 1)
                        st.rerun()

            with col4:
                if st.button("🗑️", key=f"del_{item_id}"):
                    del st.session_state.cart[item_id]
                    st.rerun()

            st.markdown(f"**Subtotal: {item['price'] * item['quantity']:.2f} AED**")
            st.divider()

        # Order summary
        st.markdown("### 📊 Order Summary")
        total_items = sum(item['quantity'] for item in st.session_state.cart.values())
        total_price = calculate_total()

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Items", total_items)
        with col2:
            st.metric("Total Amount", f"{total_price:.2f} AED")

        st.divider()

        # Complete order button (INSIDE else block!)
        if st.button("✅ Complete Order", type="primary", use_container_width=True):
            result = complete_order()
            if result:
                st.balloons()
                st.success("✅ Order placed successfully!")
                st.info("📧 Order has been saved and sent to kitchen manager.")
                import time
                time.sleep(2)
                st.rerun()
            else:
                st.error("❌ Something went wrong. Please try again.")

# Page 3: Order History
elif page == "📜 Order History":
    st.subheader("Order History")

    if not st.session_state.order_history:
        st.info("📜 No orders yet. Place your first order!")
    else:
        st.success(f"**Total Orders: {len(st.session_state.order_history)}**")

        for idx, order in enumerate(reversed(st.session_state.order_history)):
            order_num = len(st.session_state.order_history) - idx

            with st.expander(f"📦 Order #{order_num} • {order['date']} • {order['total']:.2f} AED", expanded=(idx == 0)):
                # Display items in a table format
                items_data = []
                for item in order['items'].values():
                    items_data.append({
                        'Item': item['name'],
                        'Category': item['category'],
                        'Unit Price': f"{item['price']:.2f} AED",
                        'Quantity': item['quantity'],
                        'Total': f"{item['price'] * item['quantity']:.2f} AED"
                    })

                df_order = pd.DataFrame(items_data)
                st.dataframe(df_order, use_container_width=True, hide_index=True)

                st.markdown(f"### 💰 Order Total: {order['total']:.2f} AED")
# Page 4: Manager View
elif page == "👨‍💼 Manager View":
    st.subheader("👨‍💼 Manager Dashboard")

    # Password protection
    if 'manager_authenticated' not in st.session_state:
        st.session_state.manager_authenticated = False

    if not st.session_state.manager_authenticated:
        st.warning("🔒 This section is for kitchen managers only")
        password = st.text_input("Enter Manager Password", type="password")

        if st.button("Access Manager View"):
            # Simple password - change this to your desired password
            if password == "manager123":
                st.session_state.manager_authenticated = True
                st.rerun()
            else:
                st.error("❌ Invalid password")

        st.info("💡 Default password: manager123 (change this in the code)")
        st.stop()

    # Manager is authenticated - show all orders
    st.success("✅ Manager Access Granted")

    if st.button("🔓 Logout from Manager View"):
        st.session_state.manager_authenticated = False
        st.rerun()

    st.divider()

    # Define orders file path
    from pathlib import Path

    orders_file = Path("orders/all_orders.csv")

    if orders_file.exists():
        st.subheader("📊 All Orders Summary")

        # Read the CSV file
        try:
            df_orders = pd.read_csv(orders_file)

            # Remove empty rows
            df_orders = df_orders[df_orders['Item Name'].notna()]

            # Check if dataframe has data
            if df_orders.empty:
                st.info("📭 No orders in the file yet.")
            else:
                # Display summary statistics
                col1, col2, col3 = st.columns(3)

                with col1:
                    unique_users = df_orders['User Name'].dropna().unique()
                    st.metric("Total Users", len(unique_users))

                with col2:
                    # Count unique orders
                    unique_orders = df_orders.groupby(['Order Date', 'Order Time', 'User Name']).size()
                    total_orders = len(unique_orders)
                    st.metric("Total Orders", total_orders)

                with col3:
                    # Calculate total using Item Total column
                    df_orders_clean = df_orders.copy()
                    df_orders_clean['Item Total (AED)'] = df_orders_clean['Item Total (AED)'].astype(str).str.replace(
                        ' AED', '').str.strip()
                    total_amount = pd.to_numeric(df_orders_clean['Item Total (AED)'], errors='coerce').sum()
                    st.metric("Total Amount", f"{total_amount:.2f} AED")

                st.divider()

                # Show all orders
                st.subheader("📋 Detailed Orders")
                st.dataframe(df_orders, use_container_width=True, hide_index=True)

                # Download button
                st.download_button(
                    label="📥 Download Orders CSV",
                    data=df_orders.to_csv(index=False).encode('utf-8'),
                    file_name=f"kitchen_orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )



        except Exception as e:
            st.error(f"Error reading orders: {e}")
            st.info("The orders file might be empty or have a different format.")
            import traceback

            st.code(traceback.format_exc())

    else:
        st.info("📭 No orders yet. Orders will appear here once users start ordering.")
        st.write("Orders are saved to: `orders/all_orders.csv`")
# Footer
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col1:
    st.caption(f"📦 Items: {len(inventory)}")
with col2:
    cart_items = sum(item['quantity'] for item in st.session_state.cart.values())
    st.caption(f"🛒 In Cart: {cart_items}")
with col3:
    st.caption(f"📜 Orders: {len(st.session_state.order_history)}")




