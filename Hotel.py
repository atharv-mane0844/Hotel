import sqlite3
import csv
import io
import json
import os
from flask import Flask, render_template_string, request, jsonify, Response, send_file
from datetime import datetime

app = Flask(__name__)
DB_NAME = "hotel_jogeshwari.db"

DEFAULT_MENU = [
    # --- STARTERS ---
    {"id": 1, "name": "Paneer Tikka", "category": "Starters", "price": 220.00, "type": "Veg"},
    {"id": 2, "name": "Veg Crispy", "category": "Starters", "price": 180.00, "type": "Veg"},
    {"id": 3, "name": "Harabhara Kebab", "category": "Starters", "price": 190.00, "type": "Veg"},
    {"id": 4, "name": "Chicken 65", "category": "Starters", "price": 240.00, "type": "Non-Veg"},
    {"id": 5, "name": "Fish Koliwada", "category": "Starters", "price": 320.00, "type": "Non-Veg"},
    # --- MAIN COURSE ---
    {"id": 6, "name": "Paneer Butter Masala", "category": "Main Course", "price": 280.00, "type": "Veg"},
    {"id": 7, "name": "Veg Kadhai", "category": "Main Course", "price": 250.00, "type": "Veg"},
    {"id": 8, "name": "Dal Makhani", "category": "Main Course", "price": 210.00, "type": "Veg"},
    {"id": 9, "name": "Butter Chicken", "category": "Main Course", "price": 350.00, "type": "Non-Veg"},
    {"id": 10, "name": "Mutton Rogan Josh", "category": "Main Course", "price": 420.00, "type": "Non-Veg"},
    # --- RICE & BIRYANI ---
    {"id": 11, "name": "Jeera Rice", "category": "Rice & Biryani", "price": 140.00, "type": "Veg"},
    {"id": 12, "name": "Veg Biryani", "category": "Rice & Biryani", "price": 260.00, "type": "Veg"},
    {"id": 13, "name": "Chicken Dum Biryani", "category": "Rice & Biryani", "price": 320.00, "type": "Non-Veg"},
    # --- BREADS ---
    {"id": 14, "name": "Tandoori Roti", "category": "Breads", "price": 30.00, "type": "Veg"},
    {"id": 15, "name": "Butter Naan", "category": "Breads", "price": 60.00, "type": "Veg"},
    {"id": 16, "name": "Garlic Naan", "category": "Breads", "price": 75.00, "type": "Veg"},
    # --- BEVERAGES ---
    {"id": 17, "name": "Masala Chaas", "category": "Beverages", "price": 50.00, "type": "Veg"},
    {"id": 18, "name": "Sweet Lassi", "category": "Beverages", "price": 80.00, "type": "Veg"},
    {"id": 19, "name": "Mineral Water", "category": "Beverages", "price": 20.00, "type": "Veg"},
    # --- DESSERTS ---
    {"id": 20, "name": "Gulab Jamun (2 pcs)", "category": "Desserts", "price": 90.00, "type": "Veg"},
    {"id": 21, "name": "Sizzling Brownie", "category": "Desserts", "price": 180.00, "type": "Veg"}
]

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def add_column_if_not_exists(cursor, table, column, definition):
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    if column not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

def init_db():
    # Database corruption fallback recovery checks
    if os.path.exists(DB_NAME):
        try:
            test_conn = sqlite3.connect(DB_NAME)
            test_cursor = test_conn.cursor()
            test_cursor.execute("PRAGMA integrity_check(1)")
            res = test_cursor.fetchone()
            test_conn.close()
            if res and res[0] != "ok":
                raise sqlite3.DatabaseError("Corrupt database file")
        except sqlite3.DatabaseError:
            print("Database corruption detected. Rebuilding DB file...")
            try:
                os.rename(DB_NAME, f"{DB_NAME}.corrupt_{int(datetime.now().timestamp())}")
            except Exception:
                pass

    with get_db() as conn:
        cursor = conn.cursor()
        
        # 1. Menu Catalog Table
        cursor.execute('''CREATE TABLE IF NOT EXISTS menu (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, category TEXT, price REAL, type TEXT)''')
        
        # 2. Material Inward Expenses Table
        cursor.execute('''CREATE TABLE IF NOT EXISTS inward (
            id INTEGER PRIMARY KEY AUTOINCREMENT, item TEXT, supplier TEXT, qty REAL, unit TEXT, amount REAL, date TEXT)''')
        
        # 3. Waiter Directory Table
        cursor.execute('''CREATE TABLE IF NOT EXISTS waiters (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, daily_salary REAL)''')
            
        # 4. Waiter Salary Payout History Table
        cursor.execute('''CREATE TABLE IF NOT EXISTS payouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, waiter_id INTEGER, waiter_name TEXT, amount REAL, date TEXT)''')
        
        # 5. Orders Table
        cursor.execute('''CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT, guest_name TEXT, table_no TEXT, total REAL, status TEXT, payment_method TEXT, date TEXT, items_json TEXT)''')
            
        # 6. Settings configuration Table
        cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY, upi_id TEXT, merchant_name TEXT, qr_filename TEXT, admin_password TEXT)''')
        
        # 7. Users login Table
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY, password TEXT, role TEXT)''')

        # Add admin_password column if missing
        add_column_if_not_exists(cursor, "settings", "admin_password", "TEXT DEFAULT '123'")

        # Seed default staff logins
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", ("Hotel", "123", "manager"))
            cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", ("Cashier", "123", "cashier"))
            cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", ("Kitchen", "123", "kitchen"))

        # Populate Default Menu items if table is empty
        cursor.execute("SELECT COUNT(*) FROM menu")
        if cursor.fetchone()[0] == 0:
            for item in DEFAULT_MENU:
                cursor.execute("INSERT INTO menu (id, name, category, price, type) VALUES (?, ?, ?, ?, ?)",
                               (item['id'], item['name'], item['category'], item['price'], item['type']))
                
        # Populate Default Waiter Staff profiles if empty
        cursor.execute("SELECT COUNT(*) FROM waiters")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO waiters (name, daily_salary) VALUES (?, ?)", ("Ramesh Kumar", 450.00))
            cursor.execute("INSERT INTO waiters (name, daily_salary) VALUES (?, ?)", ("Santosh Patil", 500.00))
            
        # Populate Default merchant details if empty
        cursor.execute("SELECT COUNT(*) FROM settings")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO settings (key, upi_id, merchant_name, qr_filename, admin_password) VALUES (?, ?, ?, ?, ?)",
                           ('default', '9763344984-1@nyes', 'ATHARV SUDHIR MANE', 'WhatsApp Image 2026-06-27 at 10.39.14 PM.jpeg', '123'))
                           
        conn.commit()

init_db()

# Render Template incorporating exact design styles, interactive workflows, and print layers
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hotel Jogeshwari - Operational Terminal Desk</title>
    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400..900;1,400..900&family=Plus+Jakarta+Sans:ital,wght@0,200..800;1,200..800&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Plus Jakarta Sans', sans-serif; }
        .font-serif { font-family: 'Playfair Display', serif; }
        .brand-bg { background-color: #8B2611; }
        .brand-text { color: #8B2611; }
        
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: #f1f5f9; border-radius: 8px; }
        ::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 8px; }
        ::-webkit-scrollbar-thumb:hover { background: #94a3b8; }

        @media print {
            body { 
                background: white !important; 
                color: black !important;
                height: auto !important;
                overflow: visible !important;
            }
            header, main, #toast-container, #upi-modal, #checkout-modal, .fixed, .modal { 
                display: none !important; 
            }
            #print-area { 
                display: block !important; 
                width: 76mm !important;
                max-width: 76mm !important;
                margin: 0 auto !important;
                padding: 2mm !important;
                color: #000 !important;
                background: #fff !important;
                font-family: monospace !important;
                font-size: 11px !important;
                line-height: 1.3 !important;
            }
            @page {
                size: auto;
                margin: 0mm;
            }
        }
    </style>
</head>
<body class="bg-slate-50 text-slate-800 h-screen flex flex-col overflow-hidden">
    
    <!-- HEADER NAVBAR -->
    <header class="brand-bg text-white shadow-md z-20 flex-shrink-0">
        <div class="flex items-center justify-between px-6 py-3">
            <div class="flex items-center space-x-3">
                <div class="h-10 w-10 bg-white/10 rounded-full flex items-center justify-center border border-white/20 shadow-inner">
                    <span class="text-xl font-serif font-bold text-amber-400">J</span>
                </div>
                <div>
                    <h1 class="text-xl font-serif font-bold tracking-wide">Hotel Jogeshwari</h1>
                    <p class="text-[10px] text-amber-400 font-sans font-bold tracking-widest uppercase">Flavors of Heritage</p>
                </div>
            </div>
            <div class="flex items-center space-x-3">
                <a href="/menu-card" target="_blank" class="bg-amber-100 text-amber-900 hover:bg-amber-200 px-4 py-1.5 rounded-full text-xs font-black transition flex items-center space-x-1.5 shadow-sm">
                    <i class="fa-solid fa-book-open"></i> <span class="hidden sm:inline">Menu Card</span>
                </a>
                <button class="bg-white/10 text-white/90 px-4 py-1.5 rounded-full text-xs font-bold transition items-center space-x-1.5 hidden md:flex">
                    <span>Host Database: Active SQLite File</span>
                </button>
                <button onclick="switchDesk('customer')" class="px-5 py-2 rounded-full text-xs font-extrabold shadow-md flex items-center space-x-2 transition-all duration-200" id="btn-customer">
                    <i class="fa-solid fa-utensils text-orange-600 text-sm"></i> <span class="text-slate-900">Customer Desk</span>
                </button>
                <button onclick="switchDesk('admin')" class="px-5 py-2 rounded-full text-xs font-extrabold shadow-md flex items-center space-x-2 transition-all duration-200" id="btn-admin">
                    <i class="fa-solid fa-lock text-amber-400 text-sm"></i> <span class="text-white">Admin Desk</span>
                </button>
            </div>
        </div>
    </header>

    <div id="toast-container" class="fixed top-20 right-6 z-50 flex flex-col space-y-2 pointer-events-none"></div>

    <main class="flex-grow flex overflow-hidden relative">
        
        <!-- GUEST SELF-SERVICE MENU DESK -->
        <div id="customer-desk" class="w-full h-full flex flex-col md:flex-row absolute inset-0 transition-transform duration-300 transform translate-x-0">
            <div class="w-full md:w-2/3 h-full overflow-y-auto p-6 flex flex-col bg-slate-50">
                <div class="bg-amber-50 border border-amber-100 rounded-xl p-4 mb-6 flex items-center justify-between shadow-sm flex-shrink-0">
                    <div class="flex items-center space-x-4">
                        <div class="bg-amber-500/10 text-amber-800 p-2.5 rounded-lg">
                            <i class="fa-solid fa-database text-amber-700 text-base"></i>
                        </div>
                        <div>
                            <h4 class="text-xs font-black text-amber-900 tracking-wide">Persisted Python Backend Active</h4>
                            <p class="text-[11px] text-amber-700 font-medium">Connected directly to Flask web-server with automated storage file synchronization.</p>
                        </div>
                    </div>
                    <span class="bg-amber-100 text-amber-800 text-[9px] font-black px-2.5 py-1 rounded-lg tracking-wider uppercase">Active SQLite Database</span>
                </div>

                <div class="flex items-center justify-between mb-5 flex-shrink-0">
                    <div class="flex items-center">
                        <span class="bg-orange-600 text-white text-[9px] font-black px-2.5 py-1 rounded-lg tracking-wider uppercase shadow-sm">KIOSK</span>
                        <div class="ml-3">
                            <h2 class="text-lg font-serif font-black text-slate-800">Self-Service Guest Menu</h2>
                            <p class="text-xs text-slate-400">Place order directly from your screen. Prepared fresh and served hot.</p>
                        </div>
                    </div>
                    <span class="bg-emerald-50 text-emerald-700 border border-emerald-200 text-[9px] font-bold px-3 py-1 rounded-full flex items-center space-x-1.5">
                        <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                        <span>Kiosk Server Active</span>
                    </span>
                </div>

                <!-- Category and Search Controls -->
                <div class="bg-white p-3 rounded-2xl border border-slate-100 shadow-sm flex flex-wrap gap-3 items-center justify-between mb-6 flex-shrink-0">
                    <div class="flex space-x-1 overflow-x-auto pb-1 md:pb-0" id="category-filters"></div>
                    <div class="flex items-center space-x-2">
                        <div class="relative">
                            <i class="fa-solid fa-magnifying-glass absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-xs"></i>
                            <input type="text" id="menu-search" oninput="searchItems()" placeholder="Search dishes..." class="pl-8 pr-3 py-1.5 border border-slate-200 text-xs rounded-xl outline-none w-44 focus:ring-1 focus:ring-orange-500">
                        </div>
                        <select id="type-filter" onchange="searchItems()" class="px-2.5 py-1.5 border border-slate-200 text-xs font-bold rounded-xl outline-none bg-white focus:ring-1 focus:ring-orange-500 text-slate-600">
                            <option value="All">All Types</option>
                            <option value="Veg">Veg Only</option>
                            <option value="Non-Veg">Non-Veg Only</option>
                        </select>
                    </div>
                </div>

                <div id="customer-menu-grid" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 overflow-y-auto pr-1 flex-grow pb-12"></div>
            </div>

            <!-- Active Cart Sidebar -->
            <div class="w-full md:w-1/3 bg-white border-l border-slate-200 shadow-xl flex flex-col h-full">
                <div class="p-4 border-b flex justify-between items-center bg-white">
                    <h3 class="font-serif font-bold text-slate-800 flex items-center space-x-2">
                        <i class="fa-solid fa-basket-shopping text-orange-600 text-sm"></i>
                        <span class="text-sm font-black text-slate-800 tracking-wide uppercase">Active Order Cart</span>
                    </h3>
                    <button onclick="clearCart()" class="text-xs font-extrabold text-red-500 hover:text-red-700">Clear All</button>
                </div>
                
                <div class="p-4 bg-slate-50 border-b gap-3 grid grid-cols-2">
                    <div>
                        <label class="block text-[9px] font-black text-slate-400 uppercase tracking-wider mb-1">Guest Name</label>
                        <input type="text" id="cart-guest-name" placeholder="Name / Guest" class="w-full px-3 py-1.5 border border-slate-200 text-xs rounded-lg bg-white outline-none focus:ring-1 focus:ring-orange-500 text-slate-700">
                    </div>
                    <div>
                        <label class="block text-[9px] font-black text-slate-400 uppercase tracking-wider mb-1">Table Selection</label>
                        <select id="cart-table" class="w-full px-3 py-1.5 border border-slate-200 text-xs font-bold rounded-lg bg-white outline-none focus:ring-1 focus:ring-orange-500 text-slate-700">
                            <option value="Table 1">Table 1</option>
                            <option value="Table 2">Table 2</option>
                            <option value="Table 3">Table 3</option>
                            <option value="Table 4">Table 4</option>
                            <option value="Table 5">Table 5</option>
                            <option value="Takeaway">Takeaway</option>
                        </select>
                    </div>
                </div>

                <div id="cart-items" class="flex-grow overflow-y-auto p-4 space-y-3"></div>

                <!-- Subtotals and Place Order -->
                <div class="p-4 bg-slate-50 border-t border-slate-100">
                    <div class="space-y-1.5 mb-4 border-b border-slate-200 pb-3">
                        <div class="flex justify-between items-center text-xs">
                            <span class="text-slate-500 font-bold">Subtotal</span>
                            <span id="cart-subtotal" class="font-black text-slate-700">₹0.00</span>
                        </div>
                        <div class="flex justify-between items-center text-xs">
                            <span class="text-slate-500 font-bold">CGST & SGST (5%)</span>
                            <span id="cart-tax" class="font-black text-slate-700">₹0.00</span>
                        </div>
                        <div class="flex justify-between items-center text-sm pt-1.5">
                            <span class="text-slate-800 font-black">Total Payable</span>
                            <span id="cart-total" class="text-lg font-black text-orange-600">₹0.00</span>
                        </div>
                    </div>
                    <button onclick="submitOrder()" class="w-full py-3 bg-orange-600 hover:bg-orange-700 text-white font-extrabold text-xs rounded-xl shadow flex justify-center items-center space-x-2 uppercase tracking-wider">
                        <i class="fa-solid fa-file-invoice text-sm"></i>
                        <span>Place Order & Generate Bill</span>
                    </button>
                </div>
            </div>
        </div>

        <!-- MANAGER ADMIN PANEL WORKSPACE -->
        <div id="admin-desk" class="w-full h-full flex flex-col absolute inset-0 bg-slate-100 transition-transform duration-300 transform translate-x-full z-20">
            <!-- Security Gate Passcode Lock -->
            <div id="admin-login-container" class="absolute inset-0 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center z-50">
                <div class="bg-white p-6 rounded-2xl shadow-xl w-80 border border-slate-100">
                    <div class="brand-bg w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-3 text-white shadow-md">
                        <i class="fa-solid fa-user-shield text-lg text-amber-400"></i>
                    </div>
                    <h2 class="text-lg font-serif font-bold text-center text-slate-800 mb-1">Staff Sign In</h2>
                    <p class="text-xs text-center text-slate-400 mb-4">Authenticate to manage operations</p>
                    
                    <div class="space-y-3 mb-4">
                        <div>
                            <label class="block text-[9px] font-black text-slate-400 uppercase tracking-widest mb-1">Username</label>
                            <input type="text" id="login-username" value="Hotel" class="w-full px-4 py-2 border border-slate-200 rounded-xl text-sm outline-none font-bold text-slate-700">
                        </div>
                        <div>
                            <label class="block text-[9px] font-black text-slate-400 uppercase tracking-widest mb-1">Security Password</label>
                            <input type="password" id="login-password" value="123" class="w-full px-4 py-2 border border-slate-200 rounded-xl text-sm outline-none tracking-widest font-bold text-slate-700">
                        </div>
                    </div>
                    
                    <button onclick="handleAdminLogin()" class="w-full py-2.5 brand-bg text-white font-black text-xs uppercase tracking-wider rounded-xl shadow transition mb-3">Unlock System</button>
                    <button onclick="openResetModal()" class="w-full text-center text-xs font-extrabold text-orange-600 hover:text-orange-700 cursor-pointer">Forgot or Reset Password?</button>
                </div>
            </div>

            <!-- Password Reset Overriding Modal -->
            <div id="admin-reset-container" class="absolute inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center z-50 hidden">
                <div class="bg-white p-6 rounded-2xl shadow-xl w-80 border border-slate-100">
                    <div class="bg-orange-100 text-orange-700 w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-3">
                        <i class="fa-solid fa-key text-lg"></i>
                    </div>
                    <h2 class="text-lg font-serif font-bold text-center text-slate-800 mb-1">Reset Password</h2>
                    <p class="text-[11px] text-center text-slate-400 mb-4">Submit master recovery key to set a new admin password</p>
                    
                    <div class="space-y-3 mb-5">
                        <div>
                            <label class="block text-[9px] font-black text-slate-400 uppercase tracking-widest mb-1">Master Recovery Key</label>
                            <input type="password" id="reset-key" placeholder="Default: RESET123" class="w-full px-4 py-2 border border-slate-200 rounded-xl text-sm font-bold">
                        </div>
                        <div>
                            <label class="block text-[9px] font-black text-slate-400 uppercase tracking-widest mb-1">New Password</label>
                            <input type="password" id="reset-new-password" class="w-full px-4 py-2 border border-slate-200 rounded-xl text-sm font-bold">
                        </div>
                    </div>

                    <div class="flex space-x-2">
                        <button onclick="closeResetModal()" class="w-1/2 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-600 font-extrabold text-xs uppercase rounded-xl transition">Cancel</button>
                        <button onclick="handleAdminReset()" class="w-1/2 py-2.5 bg-orange-600 hover:bg-orange-700 text-white font-extrabold text-xs uppercase tracking-wider rounded-xl shadow transition">Save Password</button>
                    </div>
                </div>
            </div>

            <!-- Dashboard App Workspace Area -->
            <div id="admin-authenticated-content" class="w-full h-full flex flex-col p-6 overflow-y-auto hidden">
                <div class="bg-amber-50 border border-amber-100 rounded-xl p-4 mb-6 flex items-center justify-between shadow-sm flex-shrink-0">
                    <div class="flex items-center space-x-4">
                        <div class="bg-amber-500/10 text-amber-800 p-2.5 rounded-lg">
                            <i class="fa-solid fa-database text-amber-700 text-base"></i>
                        </div>
                        <div>
                            <h4 class="text-xs font-black text-amber-900 tracking-wide">Persisted Python Backend Active</h4>
                            <p class="text-[11px] text-amber-700 font-medium">Connected directly to Flask web-server with automated storage file synchronization.</p>
                        </div>
                    </div>
                    <span class="bg-amber-100 text-amber-800 text-[9px] font-black px-2.5 py-1 rounded-lg tracking-wider uppercase">Active SQLite Database</span>
                </div>

                <!-- Admin Operational Console Heading and Tabs -->
                <div class="bg-white p-6 rounded-3xl border border-slate-100 shadow-sm flex flex-col lg:flex-row lg:items-center justify-between mb-6 gap-4 flex-shrink-0">
                    <div class="flex items-center space-x-4">
                        <div class="bg-[#1e293b] text-white text-xs font-black px-4 py-2 rounded-xl tracking-wider uppercase" id="active-role-badge">ADMIN</div>
                        <div>
                            <h2 class="text-lg font-serif font-black text-slate-800">Operational Console</h2>
                            <p class="text-[11px] text-slate-400">Manage orders, catalog configurations, and transactions.</p>
                        </div>
                    </div>
                    <div class="flex flex-col sm:flex-row items-start sm:items-center gap-3">
                        <div class="bg-slate-100 p-1 rounded-2xl flex flex-wrap gap-1">
                            <button onclick="switchAdminTab('menu')" id="tab-menu" class="admin-tab-btn flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-bold transition">
                                <i class="fa-solid fa-burger"></i> <span>Manage Menu</span>
                            </button>
                            <button onclick="switchAdminTab('billing')" id="tab-billing" class="admin-tab-btn flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-bold transition">
                                <i class="fa-solid fa-receipt"></i> <span>Billing Queue</span>
                            </button>
                            <button onclick="switchAdminTab('waiters')" id="tab-waiters" class="admin-tab-btn flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-bold transition">
                                <i class="fa-solid fa-user-tie"></i> <span>Staff Payroll</span>
                            </button>
                            <button onclick="switchAdminTab('inward')" id="tab-inward" class="admin-tab-btn flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-bold transition">
                                <i class="fa-solid fa-boxes-packing"></i> <span>Material Inward</span>
                            </button>
                            <button onclick="switchAdminTab('settings-qr')" id="tab-settings-qr" class="admin-tab-btn flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-bold transition">
                                <i class="fa-solid fa-qrcode text-orange-600"></i> <span>UPI Setup</span>
                            </button>
                            <button onclick="switchAdminTab('users')" id="tab-users" class="admin-tab-btn flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-bold transition">
                                <i class="fa-solid fa-users-gear text-emerald-600"></i> <span>Logins</span>
                            </button>
                            <button onclick="switchAdminTab('reports')" id="tab-reports" class="admin-tab-btn flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-bold transition">
                                <i class="fa-solid fa-chart-line"></i> <span>Reports</span>
                            </button>
                        </div>
                        <button onclick="handleAdminLogout()" class="px-4 py-2 bg-rose-50 hover:bg-rose-100 text-rose-600 rounded-xl text-xs font-black transition flex items-center space-x-1 uppercase tracking-wide">
                            <span>LOGOUT</span> <i class="fa-solid fa-caret-down"></i>
                        </button>
                    </div>
                </div>

                <div class="flex-grow">
                    
                    <!-- TAB: Manage Menu Sub-View -->
                    <div id="view-menu" class="admin-view">
                        <div class="bg-white p-6 rounded-3xl border border-slate-100 shadow-sm mb-6 manager-only">
                            <h3 class="text-base font-serif font-black text-slate-800 mb-5">Add New Menu Item</h3>
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                                <div>
                                    <label class="block text-[10px] font-black text-slate-400 uppercase tracking-wider mb-1.5">Item Name</label>
                                    <input type="text" id="menu-item-name" placeholder="e.g. Garlic Bread" class="w-full px-4 py-2.5 border border-slate-200 rounded-xl text-xs font-medium outline-none focus:ring-1 focus:ring-orange-500">
                                </div>
                                <div>
                                    <label class="block text-[10px] font-black text-slate-400 uppercase tracking-wider mb-1.5">Category</label>
                                    <input type="text" id="menu-item-category" placeholder="Select or type new category" list="categories-list" class="w-full px-4 py-2.5 border border-slate-200 rounded-xl text-xs font-medium outline-none focus:ring-1 focus:ring-orange-500">
                                    <datalist id="categories-list">
                                        <option value="Starters"><option value="Main Course"><option value="Rice & Biryani"><option value="Breads"><option value="Beverages"><option value="Desserts">
                                    </datalist>
                                </div>
                            </div>
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-5">
                                <div>
                                    <label class="block text-[10px] font-black text-slate-400 uppercase tracking-wider mb-1.5">Price (₹)</label>
                                    <input type="number" id="menu-item-price" placeholder="e.g. 150" class="w-full px-4 py-2.5 border border-slate-200 rounded-xl text-xs font-medium outline-none focus:ring-1 focus:ring-orange-500">
                                </div>
                                <div>
                                    <label class="block text-[10px] font-black text-slate-400 uppercase tracking-wider mb-1.5">Type</label>
                                    <select id="menu-item-type" class="w-full px-4 py-2.5 border border-slate-200 rounded-xl text-xs font-bold bg-white outline-none focus:ring-1 focus:ring-orange-500 text-slate-600">
                                        <option value="Veg">Veg</option>
                                        <option value="Non-Veg">Non-Veg</option>
                                    </select>
                                </div>
                            </div>
                            <div class="flex justify-end">
                                <button onclick="addMenuItem()" class="px-6 py-2.5 bg-orange-600 hover:bg-orange-700 text-white text-xs font-black rounded-xl shadow-sm transition">+ Add Menu Item</button>
                            </div>
                        </div>

                        <div class="bg-white p-6 rounded-3xl border border-slate-100 shadow-sm">
                            <div class="flex flex-wrap justify-between items-center mb-5 gap-3">
                                <h3 class="text-base font-serif font-black text-slate-800">Current Menu Catalog</h3>
                                <button onclick="restoreDefaultMenu()" class="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-[10px] font-extrabold uppercase tracking-wide rounded-xl transition manager-only"><i class="fa-solid fa-rotate-left mr-1"></i> Restore Default Menu</button>
                            </div>
                            <div id="admin-menu-grid" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4"></div>
                        </div>
                    </div>

                    <!-- TAB: Billing History Sub-View -->
                    <div id="view-billing" class="admin-view hidden">
                        <div class="mb-6">
                            <h3 class="text-sm font-black text-slate-500 uppercase tracking-wider mb-3">Live Active Kitchen Bills</h3>
                            <div id="active-orders-grid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"></div>
                        </div>
                    </div>

                    <!-- TAB: Waiters and Payroll -->
                    <div id="view-waiters" class="admin-view hidden">
                        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                            <div class="bg-white p-5 rounded-2xl border shadow-sm h-fit manager-only">
                                <h3 class="font-black text-xs text-slate-500 uppercase tracking-wide mb-3">Add Floor Staff</h3>
                                <div class="space-y-3">
                                    <input type="text" id="waiter-name" placeholder="Full Name" class="w-full px-3 py-2 border border-slate-200 text-xs rounded-lg outline-none">
                                    <input type="number" id="waiter-salary" placeholder="Daily Salary (₹)" class="w-full px-3 py-2 border border-slate-200 text-xs rounded-lg outline-none">
                                    <button onclick="addWaiter()" class="w-full py-2 bg-slate-900 text-white font-extrabold text-xs rounded-lg shadow uppercase transition">Save Waiter Profile</button>
                                </div>

                                <h3 class="font-black text-xs text-slate-500 uppercase tracking-wide mt-6 mb-3">Disburse Daily Salary Payout</h3>
                                <div class="space-y-3">
                                    <select id="payout-waiter-id" class="w-full px-3 py-2 border border-slate-200 text-xs rounded-lg bg-white outline-none"></select>
                                    <input type="number" id="payout-amount" placeholder="Paid Salary amount (₹)" class="w-full px-3 py-2 border border-slate-200 text-xs rounded-lg outline-none">
                                    <button onclick="disburseSalary()" class="w-full py-2 bg-orange-600 text-white font-extrabold text-xs rounded-lg shadow uppercase transition">Record Payout</button>
                                </div>
                            </div>
                            <div class="lg:col-span-2 space-y-6">
                                <div class="bg-white rounded-2xl border shadow-sm overflow-hidden">
                                    <div class="px-5 py-3.5 bg-slate-50 border-b font-extrabold text-xs text-slate-700">Registered Waiter Directory</div>
                                    <div class="overflow-x-auto">
                                        <table class="w-full text-left text-xs font-sans">
                                            <thead class="bg-slate-50 border-b font-extrabold text-slate-600">
                                                <tr>
                                                    <th class="px-5 py-3">ID</th>
                                                    <th class="px-5 py-3">Waiter Name</th>
                                                    <th class="px-5 py-3">Daily Rate</th>
                                                    <th class="px-5 py-3 text-orange-800 bg-orange-50/50">Projected Monthly (30 Days)</th>
                                                    <th class="px-5 py-3 text-right manager-only">Actions</th>
                                                </tr>
                                            </thead>
                                            <tbody id="waiters-table" class="divide-y divide-slate-100 font-medium"></tbody>
                                        </table>
                                    </div>
                                </div>

                                <div class="bg-white rounded-2xl border shadow-sm overflow-hidden">
                                    <div class="px-5 py-3.5 bg-slate-50 border-b font-extrabold text-xs text-slate-700">Salary Payout History Log</div>
                                    <table class="w-full text-left text-xs">
                                        <thead class="bg-slate-50 border-b font-extrabold text-slate-600">
                                            <tr>
                                                <th class="px-5 py-3">Date</th>
                                                <th class="px-5 py-3">Waiter Name</th>
                                                <th class="px-5 py-3 text-right">Paid Amount</th>
                                            </tr>
                                        </thead>
                                        <tbody id="payouts-table" class="divide-y divide-slate-100"></tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- TAB: Material Inward Procurements -->
                    <div id="view-inward" class="admin-view hidden">
                        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                            <div class="bg-white p-5 rounded-2xl border shadow-sm h-fit">
                                <h3 class="font-black text-xs text-slate-500 uppercase tracking-wide mb-3">Log Expense Inward</h3>
                                <div class="space-y-3">
                                    <input type="text" id="in-item" placeholder="Material Name" class="w-full px-3 py-2 border border-slate-200 text-xs rounded-lg">
                                    <input type="text" id="in-supplier" placeholder="Supplier / Vendor" class="w-full px-3 py-2 border border-slate-200 text-xs rounded-lg">
                                    <div class="grid grid-cols-2 gap-2">
                                        <input type="number" id="in-qty" placeholder="Quantity" class="w-full px-3 py-2 border border-slate-200 text-xs rounded-lg">
                                        <input type="text" id="in-unit" placeholder="Unit (e.g. Kg)" class="w-full px-3 py-2 border border-slate-200 text-xs rounded-lg">
                                    </div>
                                    <input type="number" id="in-amount" placeholder="Total Paid Amount (₹)" class="w-full px-3 py-2 border border-slate-200 text-xs rounded-lg font-bold">
                                    <button onclick="addInward()" class="w-full py-2 bg-slate-900 text-white font-extrabold text-xs rounded-lg shadow uppercase transition">Save Invoice</button>
                                </div>
                            </div>
                            <div class="lg:col-span-2 bg-white rounded-2xl border shadow-sm overflow-hidden">
                                <table class="w-full text-left text-xs">
                                    <thead class="bg-slate-50 border-b font-extrabold text-slate-600">
                                        <tr>
                                            <th class="px-5 py-3">Item</th>
                                            <th class="px-5 py-3">Supplier</th>
                                            <th class="px-5 py-3">Qty</th>
                                            <th class="px-5 py-3">Date</th>
                                            <th class="px-5 py-3 text-right">Cost</th>
                                        </tr>
                                    </thead>
                                    <tbody id="inward-table-body" class="divide-y divide-slate-100"></tbody>
                                </table>
                            </div>
                        </div>
                    </div>

                    <!-- TAB: UPI QR Setup Configuration -->
                    <div id="view-settings-qr" class="admin-view hidden">
                        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            <div class="bg-white p-6 rounded-2xl border shadow-sm">
                                <h3 class="font-serif font-black text-slate-800 text-base mb-2">QR Code & UPI Settings</h3>
                                <p class="text-xs text-slate-400 mb-5">Configure payment triggers displayed on printed invoices.</p>
                                
                                <div class="space-y-4">
                                    <div>
                                        <label class="block text-[10px] font-black text-slate-400 uppercase tracking-wider mb-1.5">Merchant Display Name</label>
                                        <input type="text" id="setup-merchant-name" class="w-full px-4 py-2.5 border border-slate-200 rounded-xl text-xs font-bold outline-none text-slate-700">
                                    </div>
                                    <div>
                                        <label class="block text-[10px] font-black text-slate-400 uppercase tracking-wider mb-1.5">UPI ID Address</label>
                                        <input type="text" id="setup-upi-id" class="w-full px-4 py-2.5 border border-slate-200 rounded-xl text-xs font-bold outline-none text-slate-700">
                                    </div>
                                    <div class="manager-only">
                                        <label class="block text-[10px] font-black text-slate-400 uppercase tracking-wider mb-1.5">Upload Custom QR Scanner Image</label>
                                        <div class="flex items-center space-x-2">
                                            <label for="setup-qr-file" class="flex items-center justify-center px-4 py-2.5 border border-slate-200 rounded-xl text-xs font-bold bg-slate-50 hover:bg-slate-100 text-slate-700 cursor-pointer transition w-full">
                                                <i class="fa-solid fa-cloud-arrow-up mr-2 text-orange-600"></i>
                                                <span id="setup-file-label">Choose Image from Gallery</span>
                                            </label>
                                            <input type="file" id="setup-qr-file" accept="image/*" class="hidden" onchange="handleFileSelected(this)">
                                        </div>
                                        <p class="text-[10px] text-slate-400 mt-1 italic">Supports JPEG, JPG, PNG files.</p>
                                    </div>
                                    <button onclick="saveUpiSettings()" class="w-full py-2.5 bg-orange-600 hover:bg-orange-700 text-white font-extrabold text-xs uppercase rounded-xl shadow transition manager-only">Save Config Parameters</button>
                                </div>
                            </div>

                            <div class="bg-white p-6 rounded-2xl border shadow-sm flex flex-col items-center justify-center">
                                <span class="bg-orange-100 text-orange-800 text-[9px] font-black px-3 py-1 rounded-full uppercase tracking-widest mb-4">Live Preview Setup</span>
                                <div class="border rounded-2xl p-4 bg-slate-50 w-72 flex flex-col items-center">
                                    <img id="setup-preview-qr-img" src="/qr-code.jpeg" onerror="this.src='https://placehold.co/200x200?text=Scan+To+Pay'" alt="Merchant QR Scanner" class="w-48 h-auto border rounded-xl shadow-inner mb-3">
                                    <p id="setup-preview-name" class="font-black text-slate-800 text-xs uppercase">-</p>
                                    <p id="setup-preview-id" class="font-bold text-slate-500 text-[10px]">-</p>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- TAB: Staff Accounts View -->
                    <div id="view-users" class="admin-view hidden">
                        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                            <div class="bg-white p-5 rounded-2xl border shadow-sm h-fit manager-only">
                                <h3 class="font-black text-xs text-emerald-800 uppercase tracking-wide mb-3">Register Staff Login</h3>
                                <div class="space-y-3">
                                    <div>
                                        <label class="block text-[9px] font-black text-slate-400 uppercase tracking-wider mb-1">Username</label>
                                        <input type="text" id="new-user-username" class="w-full px-3 py-2 border border-slate-200 text-xs rounded-lg outline-none">
                                    </div>
                                    <div>
                                        <label class="block text-[9px] font-black text-slate-400 uppercase tracking-wider mb-1">Passcode</label>
                                        <input type="password" id="new-user-password" class="w-full px-3 py-2 border border-slate-200 text-xs rounded-lg outline-none">
                                    </div>
                                    <div>
                                        <label class="block text-[9px] font-black text-slate-400 uppercase tracking-wider mb-1">Role</label>
                                        <select id="new-user-role" class="w-full px-3 py-2 border border-slate-200 text-xs rounded-lg bg-white outline-none">
                                            <option value="manager">Manager (Full Access)</option>
                                            <option value="cashier">Cashier (Billing Only)</option>
                                            <option value="kitchen">Kitchen Staff (Queue Only)</option>
                                        </select>
                                    </div>
                                    <button onclick="saveUserAccount()" class="w-full py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-extrabold text-xs rounded-lg shadow uppercase transition">Save Staff Account</button>
                                </div>
                            </div>
                            <div class="lg:col-span-2 bg-white rounded-2xl border shadow-sm overflow-hidden">
                                <div class="px-5 py-3.5 bg-slate-50 border-b font-extrabold text-xs text-slate-700">Active Operational Logins</div>
                                <div class="overflow-x-auto">
                                    <table class="w-full text-left text-xs font-sans">
                                        <thead class="bg-slate-50 border-b font-extrabold text-slate-600">
                                            <tr>
                                                <th class="px-5 py-3">Username</th>
                                                <th class="px-5 py-3">Role Privilege</th>
                                                <th class="px-5 py-3 text-right manager-only">Actions</th>
                                            </tr>
                                        </thead>
                                        <tbody id="users-table" class="divide-y divide-slate-100 font-medium"></tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- TAB: Operational Reports -->
                    <div id="view-reports" class="admin-view hidden">
                        <div class="flex flex-wrap justify-between items-center mb-6 gap-3">
                            <div>
                                <h3 class="text-sm font-black text-slate-500 uppercase tracking-wider mb-1">Reports Overview</h3>
                                <p class="text-xs text-slate-400 font-semibold">Date-filtered sales statistics, expenses and item analytics.</p>
                            </div>
                            <div class="flex space-x-2">
                                <a href="/api/export/orders" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white font-extrabold text-xs rounded-xl shadow flex items-center space-x-1.5 transition">
                                    <i class="fa-solid fa-file-csv text-emerald-400"></i> <span>Export Orders CSV</span>
                                </a>
                                <a href="/api/export/expenses" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white font-extrabold text-xs rounded-xl shadow flex items-center space-x-1.5 transition">
                                    <i class="fa-solid fa-file-csv text-red-400"></i> <span>Export Expenses CSV</span>
                                </a>
                            </div>
                        </div>

                        <!-- Date Picker Component -->
                        <div class="bg-white p-4 rounded-3xl border border-slate-100 shadow-sm mb-6 flex flex-wrap gap-4 items-center justify-between">
                            <div class="flex items-center space-x-3 flex-wrap gap-2">
                                <div class="flex items-center space-x-1">
                                    <span class="text-xs font-black text-slate-500 uppercase tracking-wide">From:</span>
                                    <input type="date" id="report-start-date" onchange="calculateReports()" class="border border-slate-200 text-xs font-bold rounded-xl px-3 py-1.5 outline-none focus:ring-1 focus:ring-orange-500 text-slate-700 bg-slate-50">
                                </div>
                                <div class="flex items-center space-x-1">
                                    <span class="text-xs font-black text-slate-500 uppercase tracking-wide">To:</span>
                                    <input type="date" id="report-end-date" onchange="calculateReports()" class="border border-slate-200 text-xs font-bold rounded-xl px-3 py-1.5 outline-none focus:ring-1 focus:ring-orange-500 text-slate-700 bg-slate-50">
                                </div>
                            </div>
                            <div class="flex space-x-1 bg-slate-100 p-1 rounded-xl">
                                <button onclick="setReportPeriod('today')" class="px-3 py-1 bg-white hover:bg-slate-50 text-[10px] font-black text-slate-700 rounded-lg shadow-sm transition">Today</button>
                                <button onclick="setReportPeriod('week')" class="px-3 py-1 text-[10px] font-bold text-slate-500 hover:text-slate-700 transition">7 Days</button>
                                <button onclick="setReportPeriod('month')" class="px-3 py-1 text-[10px] font-bold text-slate-500 hover:text-slate-700 transition">30 Days</button>
                                <button onclick="setReportPeriod('all')" class="px-3 py-1 text-[10px] font-bold text-slate-500 hover:text-slate-700 transition">All Time</button>
                            </div>
                        </div>
                        
                        <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                            <div class="bg-white p-5 rounded-2xl border border-l-4 border-l-emerald-600 shadow-sm">
                                <p class="text-[9px] text-slate-400 font-extrabold uppercase tracking-wider">Gross Sales</p>
                                <h3 id="stat-revenue" class="text-2xl font-black text-slate-800 mt-1">₹0.00</h3>
                            </div>
                            <div class="bg-white p-5 rounded-2xl border border-l-4 border-l-red-600 shadow-sm">
                                <p class="text-[9px] text-slate-400 font-extrabold uppercase tracking-wider">Total Expenses</p>
                                <h3 id="stat-expenses" class="text-2xl font-black text-slate-800 mt-1">₹0.00</h3>
                            </div>
                            <div class="bg-slate-900 p-5 rounded-2xl text-white shadow-sm">
                                <p class="text-[9px] text-slate-400 font-bold uppercase tracking-wider">Net Margin</p>
                                <h3 id="stat-net" class="text-2xl font-black text-amber-400 mt-1">₹0.00</h3>
                            </div>
                        </div>

                        <!-- Dish Performance Analytics Panels -->
                        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
                            <div class="bg-white p-5 rounded-3xl border border-slate-100 shadow-sm">
                                <div class="flex items-center justify-between mb-4 border-b border-slate-50 pb-3">
                                    <div class="flex items-center space-x-2">
                                        <div class="p-1.5 bg-emerald-50 text-emerald-600 rounded-lg">
                                            <i class="fa-solid fa-fire text-xs"></i>
                                        </div>
                                        <h4 class="font-serif font-black text-slate-800 text-sm">Top Performance Dishes</h4>
                                    </div>
                                    <span class="text-[9px] bg-emerald-100 text-emerald-800 font-extrabold px-2 py-0.5 rounded-full uppercase tracking-wider">High Demand</span>
                                </div>
                                <div id="top-selling-dishes" class="space-y-4"></div>
                            </div>

                            <div class="bg-white p-5 rounded-3xl border border-slate-100 shadow-sm">
                                <div class="flex items-center justify-between mb-4 border-b border-slate-50 pb-3">
                                    <div class="flex items-center space-x-2">
                                        <div class="p-1.5 bg-rose-50 text-rose-600 rounded-lg">
                                            <i class="fa-solid fa-triangle-exclamation text-xs"></i>
                                        </div>
                                        <h4 class="font-serif font-black text-slate-800 text-sm">Low Performance Dishes</h4>
                                    </div>
                                    <span class="text-[9px] bg-red-100 text-red-800 font-extrabold px-2 py-0.5 rounded-full uppercase tracking-wider">Review Required</span>
                                </div>
                                <div id="worst-selling-dishes" class="space-y-3"></div>
                            </div>
                        </div>

                        <div class="bg-white rounded-2xl border shadow-sm overflow-hidden">
                            <div class="p-4 bg-slate-50 border-b font-extrabold text-slate-700 text-xs uppercase tracking-wider">Order Transaction Ledger History</div>
                            <div class="overflow-x-auto">
                                <table class="w-full text-left text-xs">
                                    <thead class="bg-slate-50 border-b font-extrabold text-slate-500">
                                        <tr>
                                            <th class="px-5 py-3">Order ID</th>
                                            <th class="px-5 py-3">Guest</th>
                                            <th class="px-5 py-3">Table</th>
                                            <th class="px-5 py-3">Date</th>
                                            <th class="px-5 py-3">Payment</th>
                                            <th class="px-5 py-3 text-right">Amount</th>
                                        </tr>
                                    </thead>
                                    <tbody id="historical-orders-table" class="divide-y divide-slate-100"></tbody>
                                </table>
                            </div>
                        </div>
                    </div>

                </div>
            </div>
        </div>
    </main>

    <!-- UPI SCANNER DIALOG MODAL -->
    <div id="upi-modal" class="hidden fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
        <div class="bg-white p-6 rounded-2xl text-center w-80 shadow-2xl border border-slate-100 relative">
            <button onclick="closeUpiModal()" class="absolute top-3 right-3 text-slate-400 hover:text-slate-600">
                <i class="fa-solid fa-circle-xmark text-lg"></i>
            </button>
            <h3 class="font-bold mb-3 text-slate-800 text-xs tracking-wide uppercase">Scan to Pay UPI</h3>
            
            <div class="bg-slate-50 p-2.5 rounded-xl border mb-3 flex flex-col items-center">
                <img id="modal-qr-img" src="/qr-code.jpeg" onerror="this.src='https://placehold.co/200x200?text=QR+Code'" alt="UPI QR Code" class="w-44 h-auto border rounded-xl shadow-inner mb-2">
                <p id="modal-merchant-name" class="font-black text-slate-800 text-xs uppercase tracking-wide">-</p>
                <p id="modal-upi-id" class="text-[10px] text-slate-500 font-semibold mt-0.5">-</p>
            </div>

            <div id="payment-status-container" class="py-2">
                <div id="payment-loader" class="hidden flex flex-col items-center justify-center mb-3">
                    <span class="w-6 h-6 border-4 border-orange-600 border-t-transparent rounded-full animate-spin"></span>
                    <span class="text-[11px] font-bold text-orange-600 mt-2 animate-pulse">Verifying UPI network transaction...</span>
                </div>
                <div id="payment-actions" class="flex gap-2">
                    <button onclick="closeUpiModal()" class="w-1/2 bg-slate-100 text-slate-600 py-2 rounded-lg text-xs font-bold transition hover:bg-slate-200">Cancel</button>
                    <button onclick="simulateOnlineVerification()" class="w-1/2 bg-emerald-600 text-white py-2 rounded-lg text-xs font-bold shadow transition hover:bg-emerald-700">Payment Paid</button>
                </div>
            </div>
        </div>
    </div>

    <!-- MAIN CHECKOUT DIALOG MODAL -->
    <div id="checkout-modal" class="hidden fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center z-50">
        <div class="bg-white p-6 rounded-2xl shadow-xl w-80 text-center border">
            <div class="w-12 h-12 bg-emerald-50 rounded-full flex items-center justify-center text-emerald-600 mx-auto mb-4">
                <i class="fa-solid fa-cash-register text-lg"></i>
            </div>
            <h3 class="font-serif font-black text-slate-800 text-lg mb-1">Process Bill Checkout</h3>
            <p id="checkout-modal-desc" class="text-xs text-slate-500 mb-4"></p>
            <div class="space-y-2">
                <button onclick="confirmCheckout('Cash')" class="w-full py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs uppercase tracking-wide rounded-xl shadow transition">Settle via CASH</button>
                <button onclick="triggerOnlineUpiCheckout()" class="w-full py-2.5 bg-orange-600 hover:bg-orange-700 text-white font-bold text-xs uppercase tracking-wide rounded-xl shadow transition flex items-center justify-center space-x-1.5">
                    <i class="fa-solid fa-qrcode text-xs"></i> <span>Settle via ONLINE UPI</span>
                </button>
                <button onclick="closeCheckoutModal()" class="w-full py-2 bg-slate-100 hover:bg-slate-200 text-slate-600 font-bold text-xs uppercase rounded-xl transition">Cancel</button>
            </div>
        </div>
    </div>

    <!-- PRINT OUT SLIP TEMPLATE -->
    <div id="print-area" class="hidden">
        <div style="text-align: center; margin-bottom: 8px;">
            <h2 style="font-size: 16px; font-weight: bold; margin: 0; text-transform: uppercase; letter-spacing: 0.5px;">Hotel Jogeshwari</h2>
            <p style="font-size: 9px; margin: 2px 0 4px 0; font-style: italic; letter-spacing: 1px; text-transform: uppercase;">Flavors of Heritage</p>
            <p style="font-size: 9px; margin: 1px 0;">Kolhapur-Ratnagiri Highway, Kolhapur</p>
            <p style="font-size: 9px; margin: 1px 0;">Contact: +91 97633 44984 | GSTIN: 27HJOM9984E1Z5</p>
            <div style="border-top: 1px dashed #000; border-bottom: 1px dashed #000; margin: 6px 0; padding: 3px 0; font-weight: bold; font-size: 11px; text-transform: uppercase; letter-spacing: 1px;">TAX INVOICE</div>
        </div>

        <table style="width: 100%; font-size: 10px; margin-bottom: 6px; font-family: monospace;">
            <tr>
                <td style="width: 45%;"><strong>Invoice:</strong> HJ-00<span id="p-inv"></span></td>
                <td style="width: 55%; text-align: right;"><strong>Date:</strong> <span id="p-date"></span></td>
            </tr>
            <tr>
                <td style="width: 45%;"><strong>Table:</strong> <span id="p-tab"></span></td>
                <td style="width: 55%; text-align: right;"><strong>Guest:</strong> <span id="p-gst"></span></td>
            </tr>
        </table>

        <div style="border-bottom: 1px dashed #000; margin-bottom: 4px;"></div>
        
        <table style="width: 100%; font-size: 10px; font-family: monospace; border-collapse: collapse;">
            <thead>
                <tr style="border-bottom: 1px dashed #000; font-weight: bold;">
                    <th style="text-align: left; padding: 2px 0;">Item Description</th>
                    <th style="text-align: center; padding: 2px 0; width: 40px;">Qty</th>
                    <th style="text-align: right; padding: 2px 0; width: 50px;">Rate</th>
                    <th style="text-align: right; padding: 2px 0; width: 60px;">Total</th>
                </tr>
            </thead>
            <tbody id="print-items" style="font-family: monospace;"></tbody>
        </table>

        <div style="border-bottom: 1px dashed #000; margin: 4px 0;"></div>

        <table style="width: 100%; font-size: 10px; font-family: monospace; line-height: 1.4;">
            <tr>
                <td style="width: 60%; text-align: right;">Subtotal:</td>
                <td style="width: 40%; text-align: right;" id="p-subtotal">₹0.00</td>
            </tr>
            <tr>
                <td style="width: 60%; text-align: right;">CGST & SGST (5%):</td>
                <td style="width: 40%; text-align: right;" id="p-tax">₹0.00</td>
            </tr>
            <tr style="font-size: 11px; font-weight: bold; border-top: 1px dashed #000; border-bottom: 1px dashed #000;">
                <td style="width: 60%; text-align: right; padding: 3px 0;">GRAND TOTAL:</td>
                <td style="width: 40%; text-align: right; padding: 3px 0;" id="print-total">₹0.00</td>
            </tr>
        </table>

        <div style="margin-top: 8px; text-align: center; font-size: 10px; line-height: 1.3;">
            <p style="margin: 2px 0;">Payment Mode: <strong style="text-transform: uppercase;" id="print-method"></strong></p>
            <p style="margin: 2px 0; font-weight: bold; text-transform: uppercase;">*** BILL STATUS: PAID ***</p>
            <div style="margin: 8px auto 4px auto; letter-spacing: 2px; font-weight: bold; font-size: 9px;" class="tracking-widest font-bold text-[8px] select-none">
                |||| | | ||| |||| | ||| | || ||||
            </div>
            <p style="margin-top: 6px; font-style: italic; font-size: 9px;">Thank you! Visit Again.</p>
        </div>
    </div>

    <script>
        let state = { 
            menu: [],
            inward: [], 
            waiters: [], 
            payouts: [], 
            orders: [], 
            cart: [], 
            activeCategory: 'All',
            settings: {
                upi_id: "9763344984-1@nyes",
                merchant_name: "ATHARV SUDHIR MANE",
                qr_filename: "WhatsApp Image 2026-06-27 at 10.39.14 PM.jpeg",
                admin_password: "123"
            },
            currentUser: {
                username: "None",
                role: "None"
            },
            staffAccounts: []
        };

        let activeCheckoutOrderId = null;

        document.addEventListener('DOMContentLoaded', () => { 
            setDefaultDates();
            fetchData(); 
            switchDesk('customer');
        });

        function setDefaultDates() {
            const today = new Date();
            const yyyy = today.getFullYear();
            let mm = today.getMonth() + 1;
            let dd = today.getDate();
            if (mm < 10) mm = '0' + mm;
            if (dd < 10) dd = '0' + dd;

            document.getElementById('report-end-date').value = `${yyyy}-${mm}-${dd}`;
            document.getElementById('report-start-date').value = `${yyyy}-${mm}-01`;
        }

        function setReportPeriod(period) {
            const today = new Date();
            let start = new Date();
            
            if (period === 'today') {
                // today matches start
            } else if (period === 'week') {
                start.setDate(today.getDate() - 7);
            } else if (period === 'month') {
                start.setMonth(today.getMonth() - 1);
            } else if (period === 'all') {
                document.getElementById('report-start-date').value = '';
                document.getElementById('report-end-date').value = '';
                calculateReports();
                return;
            }

            const formatDate = (date) => {
                const yyyy = date.getFullYear();
                let mm = date.getMonth() + 1;
                let dd = date.getDate();
                if (mm < 10) mm = '0' + mm;
                if (dd < 10) dd = '0' + dd;
                return `${yyyy}-${mm}-${dd}`;
            };

            document.getElementById('report-start-date').value = formatDate(start);
            document.getElementById('report-end-date').value = formatDate(today);
            calculateReports();
        }

        async function fetchData() {
            try {
                const response = await fetch('/api/data');
                const data = await response.json();
                state.menu = data.menu;
                state.inward = data.inward;
                state.waiters = data.waiters;
                state.payouts = data.payouts;
                state.orders = data.orders;
                state.settings = data.settings;

                renderCategoryFilters();
                renderCustomerMenu();
                renderCart();
                renderActiveOrders();
                renderWaiters();
                renderInward();
                calculateReports();
                renderAdminMenuCatalog();
                updateWaiterSelectDropdown();
                renderPayoutsTable();
                syncSetupFields();
                
                if (state.currentUser.role === 'manager') {
                    fetchStaffAccounts();
                }
            } catch (err) {
                showToast("Network sync error with python backend.", "error");
            }
        }

        function handleFileSelected(input) {
            const label = document.getElementById('setup-file-label');
            if (input.files && input.files[0]) {
                const file = input.files[0];
                label.innerText = file.name;
                
                const reader = new FileReader();
                reader.onload = function(e) {
                    document.getElementById('setup-preview-qr-img').src = e.target.result;
                    document.getElementById('modal-qr-img').src = e.target.result;
                };
                reader.readAsDataURL(file);
                showToast("New QR Image selected! Click Save Config below to apply.", "success");
            } else {
                label.innerText = "Choose Image from Gallery";
            }
        }

        async function fetchStaffAccounts() {
            try {
                const res = await fetch('/api/users');
                if (res.ok) {
                    state.staffAccounts = await res.json();
                    renderStaffAccountsTable();
                }
            } catch(e) {}
        }

        function renderStaffAccountsTable() {
            const table = document.getElementById('users-table');
            if (!table) return;
            if (state.staffAccounts.length === 0) {
                table.innerHTML = `<tr><td colspan="3" class="px-5 py-4 text-center text-slate-400">No staff accounts found.</td></tr>`;
                return;
            }
            table.innerHTML = state.staffAccounts.map(u => `
                <tr class="hover:bg-slate-50 transition">
                    <td class="px-5 py-3 font-bold text-slate-800 flex items-center space-x-2">
                        <i class="fa-solid fa-circle-user text-slate-400 text-sm"></i>
                        <span>${u.username}</span>
                    </td>
                    <td class="px-5 py-3">
                        <span class="px-2.5 py-1 text-[10px] font-black rounded-lg uppercase tracking-wide border ${
                            u.role === 'manager' ? 'bg-orange-50 text-orange-700 border-orange-200' :
                            u.role === 'cashier' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
                            'bg-blue-50 text-blue-700 border-blue-200'
                        }">
                            ${u.role}
                        </span>
                    </td>
                    <td class="px-5 py-3 text-right manager-only">
                        ${u.username.toLowerCase() !== 'hotel' ? `
                            <button onclick="deleteStaffAccount('${u.username}')" class="text-rose-600 hover:text-rose-800 font-extrabold flex items-center space-x-1.5 ml-auto bg-rose-50 px-2.5 py-1 rounded-xl border border-rose-100 transition hover:bg-rose-100">
                                <i class="fa-regular fa-trash-can"></i> <span>Delete</span>
                            </button>
                        ` : '<span class="text-slate-400 text-xs italic">System Primary</span>'}
                    </td>
                </tr>
            `).join('');
        }

        async function saveUserAccount() {
            const username = document.getElementById('new-user-username').value.trim();
            const password = document.getElementById('new-user-password').value;
            const role = document.getElementById('new-user-role').value;

            if (!username || !password) return showToast('Please enter username and password!', 'error');

            try {
                const res = await fetch('/api/users', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ username, password, role })
                });
                if (res.ok) {
                    showToast(`Staff login '${username}' saved!`, 'success');
                    document.getElementById('new-user-username').value = '';
                    document.getElementById('new-user-password').value = '';
                    fetchStaffAccounts();
                } else {
                    const err = await res.json();
                    showToast(err.error || 'Failed to register account.', 'error');
                }
            } catch(e) {
                showToast('Failed to connect to API.', 'error');
            }
        }

        async function deleteStaffAccount(username) {
            try {
                const res = await fetch('/api/users', {
                    method: 'DELETE',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ username })
                });
                if (res.ok) {
                    showToast(`Staff account removed.`, 'success');
                    fetchStaffAccounts();
                }
            } catch(e) {
                showToast('Network error.', 'error');
            }
        }

        function applyRolePermissions(role) {
            const tabMenu = document.getElementById('tab-menu');
            const tabBilling = document.getElementById('tab-billing');
            const tabWaiters = document.getElementById('tab-waiters');
            const tabInward = document.getElementById('tab-inward');
            const tabSettingsQr = document.getElementById('tab-settings-qr');
            const tabReports = document.getElementById('tab-reports');
            const tabUsers = document.getElementById('tab-users');
            
            const badge = document.getElementById('active-role-badge');
            badge.innerText = role.toUpperCase();

            tabMenu.classList.add('hidden');
            tabWaiters.classList.add('hidden');
            tabInward.classList.add('hidden');
            tabSettingsQr.classList.add('hidden');
            tabReports.classList.add('hidden');
            tabUsers.classList.add('hidden');
            tabBilling.classList.remove('hidden');

            if (role === 'manager') {
                tabMenu.classList.remove('hidden');
                tabWaiters.classList.remove('hidden');
                tabInward.classList.remove('hidden');
                tabSettingsQr.classList.remove('hidden');
                tabReports.classList.remove('hidden');
                tabUsers.classList.remove('hidden');
                document.querySelectorAll('.manager-only').forEach(el => el.classList.remove('hidden'));
                switchAdminTab('menu');
            } else if (role === 'cashier') {
                tabInward.classList.remove('hidden');
                tabSettingsQr.classList.remove('hidden');
                tabReports.classList.remove('hidden');
                document.querySelectorAll('.manager-only').forEach(el => el.classList.add('hidden'));
                switchAdminTab('billing');
            } else if (role === 'kitchen') {
                document.querySelectorAll('.manager-only').forEach(el => el.classList.add('hidden'));
                switchAdminTab('billing');
            }
        }

        function switchDesk(desk) {
            const custDesk = document.getElementById('customer-desk');
            const admDesk = document.getElementById('admin-desk');
            const btnCust = document.getElementById('btn-customer');
            const btnAdm = document.getElementById('btn-admin');

            if (desk === 'admin') {
                custDesk.classList.add('translate-x-full');
                custDesk.classList.remove('translate-x-0');
                admDesk.classList.remove('translate-x-full');
                admDesk.classList.add('translate-x-0');

                btnCust.className = "bg-black/20 hover:bg-black/40 text-white/90 px-5 py-2 rounded-full text-xs font-extrabold transition flex items-center space-x-2";
                btnCust.querySelector('i').className = "fa-solid fa-utensils text-white text-sm";
                btnCust.querySelector('span').className = "text-white";

                btnAdm.className = "bg-white text-slate-900 px-5 py-2 rounded-full text-xs font-extrabold shadow flex items-center space-x-2";
                btnAdm.querySelector('i').className = "fa-solid fa-lock text-[#8B2611] text-sm";
                btnAdm.querySelector('span').className = "text-slate-900";
            } else {
                custDesk.classList.remove('translate-x-full');
                custDesk.classList.add('translate-x-0');
                admDesk.classList.add('translate-x-full');
                admDesk.classList.remove('translate-x-0');

                btnCust.className = "bg-white text-slate-900 px-5 py-2 rounded-full text-xs font-extrabold shadow flex items-center space-x-2";
                btnCust.querySelector('i').className = "fa-solid fa-utensils text-orange-600 text-sm";
                btnCust.querySelector('span').className = "text-slate-900";

                btnAdm.className = "bg-black/20 hover:bg-black/40 text-white/90 px-5 py-2 rounded-full text-xs font-extrabold transition flex items-center space-x-2";
                btnAdm.querySelector('i').className = "fa-solid fa-lock text-amber-400 text-sm";
                btnAdm.querySelector('span').className = "text-white";
            }
        }

        function renderCategoryFilters() {
            const container = document.getElementById('category-filters');
            const categories = ['All', 'Starters', 'Main Course', 'Rice & Biryani', 'Breads', 'Beverages', 'Desserts'];
            container.innerHTML = categories.map(cat => {
                const isActive = cat === state.activeCategory;
                const activeStyle = "bg-orange-600 text-white text-xs font-extrabold rounded-xl shadow-sm px-4 py-1.5 shrink-0";
                const inactiveStyle = "bg-slate-100 text-slate-600 hover:bg-slate-200 text-xs font-extrabold rounded-xl px-4 py-1.5 shrink-0";
                return `<button onclick="filterCategory('${cat}')" class="cat-btn shrink-0 ${isActive ? activeStyle : inactiveStyle}">${cat}</button>`;
            }).join('');
        }

        function filterCategory(cat) {
            state.activeCategory = cat;
            renderCategoryFilters();
            renderCustomerMenu();
        }

        function searchItems() { renderCustomerMenu(); }

        function renderCustomerMenu() {
            const grid = document.getElementById('customer-menu-grid');
            const search = document.getElementById('menu-search').value.toLowerCase();
            const type = document.getElementById('type-filter').value;

            let items = state.menu;
            if (state.activeCategory !== 'All') items = items.filter(i => i.category === state.activeCategory);
            if (search) items = items.filter(i => i.name.toLowerCase().includes(search));
            if (type !== 'All') items = items.filter(i => i.type === type);

            if (items.length === 0) {
                grid.innerHTML = `
                <div class="col-span-full py-16 text-center text-slate-400 font-bold">
                    <i class="fa-solid fa-plate-wheat text-3xl mb-2 text-slate-300"></i>
                    <p class="text-xs">No matching dishes available right now.</p>
                </div>`;
                return;
            }

            grid.innerHTML = items.map(item => {
                const symbolColor = item.type === 'Veg' ? 'border-emerald-600' : 'border-red-600';
                const dotColor = item.type === 'Veg' ? 'bg-emerald-600' : 'bg-red-600';
                const vegSymbol = `
                    <span class="inline-flex items-center justify-center border-2 ${symbolColor} p-0.5 w-4.5 h-4.5 rounded shadow-sm flex-shrink-0">
                        <span class="w-1.5 h-1.5 rounded-full ${dotColor}"></span>
                    </span>
                `;

                return `
                <div class="bg-white p-5 rounded-2xl border border-slate-100 shadow-sm flex flex-col justify-between hover:shadow-md transition-all duration-200">
                    <div>
                        <div class="flex items-center justify-between mb-3">
                            ${vegSymbol}
                            <span class="text-[9px] text-slate-400 font-extrabold uppercase tracking-widest bg-slate-100 px-2.5 py-0.5 rounded-md">${item.category}</span>
                        </div>
                        <h4 class="font-black text-slate-800 text-sm mt-1">${item.name}</h4>
                        <p class="text-[11px] text-slate-400 italic mt-1 font-medium leading-relaxed">Made using heritage recipes and local organic ingredients.</p>
                    </div>
                    <div class="flex justify-between items-center mt-5 pt-3 border-t border-slate-50">
                        <span class="font-black text-slate-900 text-sm">₹${item.price.toFixed(2)}</span>
                        <button onclick="addToCart(${item.id})" class="px-3.5 py-1.5 bg-orange-600 hover:bg-orange-700 text-white text-[11px] font-black rounded-xl flex items-center space-x-1 shadow transition">
                            <i class="fa-solid fa-cart-plus text-[10px]"></i> <span>Add to Order</span>
                        </button>
                    </div>
                </div>
            `}).join('');
        }

        function addToCart(id) {
            const item = state.menu.find(m => m.id === id);
            const entry = state.cart.find(c => c.id === id);
            if (entry) entry.qty++; else state.cart.push({...item, qty: 1});
            renderCart();
        }

        function renderCart() {
            const container = document.getElementById('cart-items');
            if(state.cart.length === 0){
                container.innerHTML = `
                <div class="text-center py-20 flex flex-col items-center justify-center text-slate-300">
                    <i class="fa-solid fa-basket-shopping text-4xl mb-3 text-slate-200"></i>
                    <p class="text-xs font-bold text-slate-400">Your ordering cart is empty.</p>
                    <p class="text-[11px] text-slate-400 mt-0.5">Pick some appetizers from the menu!</p>
                </div>`;
                document.getElementById('cart-subtotal').innerText = '₹0.00';
                document.getElementById('cart-tax').innerText = '₹0.00';
                document.getElementById('cart-total').innerText = '₹0.00';
                return;
            }
            
            let subtotal = 0;
            container.innerHTML = state.cart.map(i => {
                subtotal += i.price * i.qty;
                return `
                    <div class="flex justify-between items-center bg-slate-50 p-3 rounded-xl border border-slate-100">
                        <div>
                            <h4 class="font-extrabold text-xs text-slate-800">${i.name}</h4>
                            <span class="text-[11px] text-orange-600 font-extrabold">₹${i.price} &times; ${i.qty}</span>
                        </div>
                        <div class="flex items-center space-x-2">
                            <button onclick="adjustQty(${i.id}, -1)" class="w-6 h-6 bg-white border border-slate-200 rounded-lg text-xs font-black shadow-sm flex items-center justify-center text-slate-600 hover:bg-slate-50 transition">-</button>
                            <span class="text-xs font-black text-slate-800 w-4 text-center">${i.qty}</span>
                            <button onclick="adjustQty(${i.id}, 1)" class="w-6 h-6 bg-white border border-slate-200 rounded-lg text-xs font-black shadow-sm flex items-center justify-center text-slate-600 hover:bg-slate-50 transition">+</button>
                        </div>
                    </div>`;
            }).join('');
            
            let tax = subtotal * 0.05;
            let total = subtotal + tax;

            document.getElementById('cart-subtotal').innerText = `₹${subtotal.toFixed(2)}`;
            document.getElementById('cart-tax').innerText = `₹${tax.toFixed(2)}`;
            document.getElementById('cart-total').innerText = `₹${total.toFixed(2)}`;
        }

        function adjustQty(id, delta) {
            const entry = state.cart.find(c => c.id === id);
            if (entry) {
                entry.qty += delta;
                if (entry.qty <= 0) state.cart = state.cart.filter(c => c.id !== id);
                renderCart();
            }
        }

        function clearCart() { state.cart = []; renderCart(); }

        async function submitOrder() {
            if(state.cart.length === 0) return showToast('Cart is currently empty!', 'error');
            const guest_name = document.getElementById('cart-guest-name').value || 'Walk-In Guest';
            const table_no = document.getElementById('cart-table').value;
            
            const subtotal = state.cart.reduce((sum, i) => sum + (i.price * i.qty), 0);
            const total = subtotal * 1.05; 

            try {
                const res = await fetch('/api/order', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ guest_name, table_no, total, items_json: JSON.stringify(state.cart) })
                });
                if (res.ok) {
                    state.cart = [];
                    document.getElementById('cart-guest-name').value = '';
                    renderCart();
                    showToast('Order pushed safely to Kitchen Admin Dashboard!', 'success');
                    fetchData();
                } else {
                    showToast('Failed to submit order.', 'error');
                }
            } catch (err) {
                showToast('Network submit error.', 'error');
            }
        }

        function triggerOnlineUpiCheckout() {
            document.getElementById('checkout-modal').classList.add('hidden');
            document.getElementById('upi-modal').classList.remove('hidden');
        }

        function simulateOnlineVerification() {
            document.getElementById('payment-actions').classList.add('hidden');
            document.getElementById('payment-loader').classList.remove('hidden');
            
            setTimeout(() => {
                document.getElementById('payment-loader').classList.add('hidden');
                document.getElementById('payment-actions').classList.remove('hidden');
                closeUpiModalOnly();
                confirmCheckout('UPI Online');
            }, 2500);
        }

        function closeUpiModalOnly() {
            document.getElementById('upi-modal').classList.add('hidden');
        }

        function closeUpiModal() {
            document.getElementById('upi-modal').classList.add('hidden');
            document.getElementById('payment-loader').classList.add('hidden');
            document.getElementById('payment-actions').classList.remove('hidden');
            activeCheckoutOrderId = null;
        }

        function renderAdminMenuCatalog() {
            const grid = document.getElementById('admin-menu-grid');
            if (state.menu.length === 0) {
                grid.innerHTML = `<div class="col-span-full py-10 text-center text-slate-400">Your Menu Catalog is empty. Add items above!</div>`;
                return;
            }

            grid.innerHTML = state.menu.map(item => {
                const indicatorDot = item.type === 'Veg' ? 'bg-emerald-500' : 'bg-rose-500';
                return `
                <div class="bg-white p-4 rounded-xl border border-slate-100 shadow-sm flex flex-col justify-between hover:shadow-md transition">
                    <div class="flex items-start justify-between">
                        <div class="flex items-center space-x-2">
                            <span class="w-2.5 h-2.5 rounded-full ${indicatorDot}"></span>
                            <h4 class="font-bold text-slate-800 text-sm">${item.name}</h4>
                        </div>
                        <span class="text-orange-500 font-extrabold text-sm">₹${item.price.toFixed(2)}</span>
                    </div>
                    <div class="flex items-center justify-between mt-3 pt-2 border-t border-slate-50 text-[11px]">
                        <span class="text-slate-400 font-bold uppercase tracking-wide">${item.category}</span>
                        <button onclick="deleteMenuItem(${item.id})" class="text-rose-500 hover:text-rose-700 font-extrabold flex items-center space-x-1 manager-only">
                            <i class="fa-regular fa-trash-can text-xs"></i> <span>Delete</span>
                        </button>
                    </div>
                </div>
                `;
            }).join('');
        }

        async function addMenuItem() {
            const name = document.getElementById('menu-item-name').value;
            const category = document.getElementById('menu-item-category').value;
            const price = parseFloat(document.getElementById('menu-item-price').value);
            const type = document.getElementById('menu-item-type').value;

            if(!name || !category || isNaN(price)) return showToast('Complete menu item fields appropriately.', 'error');

            try {
                const res = await fetch('/api/menu', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ name, category, price, type })
                });
                if (res.ok) {
                    showToast('New menu item registered!', 'success');
                    document.getElementById('menu-item-name').value = '';
                    document.getElementById('menu-item-category').value = '';
                    document.getElementById('menu-item-price').value = '';
                    fetchData();
                } else {
                    showToast('Could not register item.', 'error');
                }
            } catch (err) {
                showToast('API write failed.', 'error');
            }
        }

        async function deleteMenuItem(id) {
            try {
                const res = await fetch('/api/menu', {
                    method: 'DELETE',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ id })
                });
                if (res.ok) {
                    showToast('Dish item removed from catalog.', 'success');
                    fetchData();
                } else {
                    showToast('Failed to delete item.', 'error');
                }
            } catch (err) {
                showToast('Connection write failed.', 'error');
            }
        }

        async function restoreDefaultMenu() {
            if(!confirm("Are you sure you want to restore the default menu? This will replace your current catalog.")) return;
            try {
                const res = await fetch('/api/menu/restore', { method: 'POST' });
                if(res.ok) {
                    showToast('Default menu card restored!', 'success');
                    fetchData();
                } else {
                    showToast('Failed to restore menu.', 'error');
                }
            } catch(err) {
                showToast('Network error.', 'error');
            }
        }

        function renderWaiters() {
            const table = document.getElementById('waiters-table');
            if (state.waiters.length === 0) {
                table.innerHTML = `<tr><td colspan="5" class="px-5 py-4 text-center text-slate-400">No registered waiter staff yet.</td></tr>`;
                return;
            }
            table.innerHTML = state.waiters.map(w => `
                <tr class="hover:bg-slate-50 transition">
                    <td class="px-5 py-3 font-bold text-slate-400">${w.id}</td>
                    <td class="px-5 py-3 font-bold text-slate-800">${w.name}</td>
                    <td class="px-5 py-3 font-extrabold text-slate-700">₹${w.daily_salary.toFixed(2)}</td>
                    <td class="px-5 py-3 bg-orange-50/20 font-black text-orange-700">₹${(w.daily_salary * 30).toFixed(2)}</td>
                    <td class="px-5 py-3 text-right manager-only">
                        <button onclick="fireWaiter(${w.id})" class="text-rose-600 hover:text-rose-800 font-extrabold flex items-center space-x-1.5 ml-auto bg-rose-50 px-3 py-1.5 rounded-xl border border-rose-100 transition-all hover:bg-rose-100">
                            <i class="fa-solid fa-user-minus text-xs"></i> <span>Fire Staff</span>
                        </button>
                    </td>
                </tr>
            `).join('');
        }

        async function fireWaiter(id) {
            try {
                const res = await fetch('/api/waiter', {
                    method: 'DELETE',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ id })
                });
                if (res.ok) {
                    showToast('Waiter staff profile removed.', 'success');
                    fetchData();
                } else {
                    showToast('Failed to fire staff.', 'error');
                }
            } catch (err) {
                showToast('Database connection failed.', 'error');
            }
        }

        async function addWaiter() {
            const name = document.getElementById('waiter-name').value;
            const salary = parseFloat(document.getElementById('waiter-salary').value);
            if (!name || isNaN(salary)) return showToast('Please fill all waiter fields', 'error');

            try {
                const res = await fetch('/api/waiter', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ name, daily_salary: salary })
                });
                if (res.ok) {
                    showToast('Waiter registered successfully!', 'success');
                    document.getElementById('waiter-name').value = '';
                    document.getElementById('waiter-salary').value = '';
                    fetchData();
                } else {
                    showToast('Failed to save profile.', 'error');
                }
            } catch (err) {
                showToast('Server sync fail.', 'error');
            }
        }

        function updateWaiterSelectDropdown() {
            const select = document.getElementById('payout-waiter-id');
            if(!select) return;
            if(state.waiters.length === 0) {
                select.innerHTML = `<option value="">-- No Staff Members --</option>`;
                return;
            }
            select.innerHTML = state.waiters.map(w => `
                <option value="${w.id}">${w.name} (Daily Rate: ₹${w.daily_salary})</option>
            `).join('');
        }

        async function disburseSalary() {
            const waiter_id = parseInt(document.getElementById('payout-waiter-id').value);
            const amount = parseFloat(document.getElementById('payout-amount').value);
            
            if(!waiter_id || isNaN(amount)) return showToast('Select staff and state salary amount.', 'error');

            const waiter = state.waiters.find(w => w.id === waiter_id);
            if(waiter) {
                try {
                    const res = await fetch('/api/payout', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ waiter_id, waiter_name: waiter.name, amount })
                    });
                    if (res.ok) {
                        showToast('Salary disbursement saved!', 'success');
                        document.getElementById('payout-amount').value = '';
                        fetchData();
                    } else {
                        showToast('Failed to complete payout.', 'error');
                    }
                } catch (err) {
                    showToast('Network payout fail.', 'error');
                }
            }
        }

        function renderPayoutsTable() {
            const table = document.getElementById('payouts-table');
            if (!state.payouts || state.payouts.length === 0) {
                table.innerHTML = `<tr><td colspan="3" class="px-5 py-4 text-center text-slate-400">No salary ledger history entries recorded.</td></tr>`;
                return;
            }
            table.innerHTML = state.payouts.map(p => `
                <tr>
                    <td class="px-5 py-2.5 font-medium text-slate-500">${p.date}</td>
                    <td class="px-5 py-2.5 font-extrabold text-slate-800">${p.waiter_name}</td>
                    <td class="px-5 py-2.5 text-right font-black text-emerald-700">₹${p.amount.toFixed(2)}</td>
                </tr>
            `).join('');
        }

        function renderActiveOrders() {
            const grid = document.getElementById('active-orders-grid');
            const pendingOrders = state.orders.filter(o => o.status === 'pending');
            if (pendingOrders.length === 0) {
                grid.innerHTML = `
                <div class="col-span-full py-10 bg-white border rounded-2xl text-center text-slate-400 font-bold shadow-sm">
                    <i class="fa-solid fa-bell-slash text-2xl mb-2 text-slate-300"></i>
                    <p class="text-xs">No active kitchen orders right now.</p>
                </div>`;
                return;
            }
            grid.innerHTML = pendingOrders.map(o => {
                const items = JSON.parse(o.items_json);
                return `
                <div class="bg-white rounded-2xl border shadow-sm flex flex-col justify-between overflow-hidden">
                    <div class="bg-slate-50 p-4 border-b flex justify-between items-center text-xs">
                        <span class="font-black text-slate-700 text-sm">${o.table_no} (${o.guest_name})</span>
                        <span class="px-2 py-0.5 bg-amber-100 text-amber-800 rounded-full font-extrabold text-[9px] uppercase tracking-wide">Unpaid</span>
                    </div>
                    <div class="p-4 flex-grow space-y-2">
                        <span class="text-[10px] text-slate-400 font-bold block">ORDER NO: #${o.id} | DATE: ${o.date}</span>
                        <div class="space-y-1">
                            ${items.map(item => `
                                <div class="flex justify-between text-xs text-slate-600 font-medium">
                                    <span>${item.name} <strong class="text-slate-800">x ${item.qty}</strong></span>
                                    <span>₹${(item.price * item.qty).toFixed(2)}</span>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                    <div class="bg-slate-50 px-4 py-3 border-t flex items-center justify-between">
                        <span class="font-black text-slate-800 text-sm">₹${o.total.toFixed(2)}</span>
                        <button onclick="openCheckoutModal(${o.id}, '${o.guest_name}', ${o.total})" class="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white font-extrabold text-xs rounded-xl flex items-center space-x-1 shadow transition">
                            <i class="fa-solid fa-cash-register"></i> <span>Checkout</span>
                        </button>
                    </div>
                </div>`;
            }).join('');
        }

        function openCheckoutModal(orderId, guestName, total) {
            activeCheckoutOrderId = orderId;
            document.getElementById('checkout-modal-desc').innerHTML = `Complete the checkout for <strong class="text-slate-700">${guestName}</strong> total of <strong class="text-emerald-700">₹${total.toFixed(2)}</strong>.`;
            document.getElementById('checkout-modal').classList.remove('hidden');
        }

        function closeCheckoutModal() {
            document.getElementById('checkout-modal').classList.add('hidden');
            activeCheckoutOrderId = null;
        }

        async function confirmCheckout(method) {
            try {
                const res = await fetch('/api/order/complete', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ id: activeCheckoutOrderId, payment_method: method })
                });
                
                if (res.ok) {
                    showToast(`Settle receipt transaction: ${method}`, 'success');
                    
                    const orderObj = state.orders.find(o => o.id === activeCheckoutOrderId);
                    if (orderObj) {
                        document.getElementById('p-inv').innerText = String(orderObj.id).padStart(5, '0');
                        document.getElementById('p-tab').innerText = orderObj.table_no;
                        document.getElementById('p-gst').innerText = orderObj.guest_name;
                        document.getElementById('p-date').innerText = orderObj.date;
                        document.getElementById('print-method').innerText = method;

                        const billTotal = orderObj.total;
                        const billSubtotal = billTotal / 1.05;
                        const billTax = billTotal - billSubtotal;

                        document.getElementById('p-subtotal').innerText = '₹' + billSubtotal.toFixed(2);
                        document.getElementById('p-tax').innerText = '₹' + billTax.toFixed(2);
                        document.getElementById('print-total').innerText = '₹' + billTotal.toFixed(2);

                        const items = JSON.parse(orderObj.items_json);
                        document.getElementById('print-items').innerHTML = items.map(item => {
                            const rawTotal = item.price * item.qty;
                            return `
                                <tr>
                                    <td style="padding: 3px 0; text-align: left; text-transform: uppercase;">${item.name}</td>
                                    <td style="padding: 3px 0; text-align: center;">${item.qty}</td>
                                    <td style="padding: 3px 0; text-align: right;">${item.price.toFixed(2)}</td>
                                    <td style="padding: 3px 0; text-align: right;">${rawTotal.toFixed(2)}</td>
                                </tr>
                            `;
                        }).join('');

                        setTimeout(() => { 
                            window.print(); 
                            activeCheckoutOrderId = null;
                        }, 500);
                    }
                    closeCheckoutModal();
                    fetchData();
                } else {
                    showToast('Failed to checkout order.', 'error');
                }
            } catch (err) {
                showToast('Network checkout error.', 'error');
            }
        }

        function renderInward() {
            const body = document.getElementById('inward-table-body');
            if (state.inward.length === 0) {
                body.innerHTML = `<tr><td colspan="5" class="px-5 py-4 text-center text-slate-400">No registered raw procurements logged yet.</td></tr>`;
                return;
            }
            body.innerHTML = state.inward.map(i => `
                <tr class="hover:bg-slate-50 transition">
                    <td class="px-5 py-3 font-black text-slate-800">${i.item}</td>
                    <td class="px-5 py-3 font-bold text-slate-500">${i.supplier}</td>
                    <td class="px-5 py-3 font-extrabold text-slate-700">${i.qty} ${i.unit || 'Kg'}</td>
                    <td class="px-5 py-3 text-slate-400 font-medium">${i.date}</td>
                    <td class="px-5 py-3 text-right font-black text-slate-800">₹${i.amount.toFixed(2)}</td>
                </tr>
            `).join('');
        }

        async function addInward() {
            const item = document.getElementById('in-item').value;
            const supplier = document.getElementById('in-supplier').value;
            const qty = parseFloat(document.getElementById('in-qty').value);
            const unit = document.getElementById('in-unit').value || 'Kg';
            const amount = parseFloat(document.getElementById('in-amount').value);

            if (!item || !supplier || isNaN(qty) || isNaN(amount)) {
                return showToast('Complete all procurement details', 'error');
            }

            try {
                const res = await fetch('/api/inward', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ item, supplier, qty, unit, amount })
                });
                if (res.ok) {
                    showToast('Procurement bill log success!', 'success');
                    document.getElementById('in-item').value = '';
                    document.getElementById('in-supplier').value = '';
                    document.getElementById('in-qty').value = '';
                    document.getElementById('in-unit').value = '';
                    document.getElementById('in-amount').value = '';
                    fetchData();
                } else {
                    showToast('Could not register outward.', 'error');
                }
            } catch (err) {
                showToast('Network post fail.', 'error');
            }
        }

        function calculateReports() {
            const startDateStr = document.getElementById('report-start-date').value;
            const endDateStr = document.getElementById('report-end-date').value;

            // Filter completed orders by range
            const completed = state.orders.filter(o => {
                if (o.status !== 'completed') return false;
                const orderDateOnly = o.date.substring(0, 10);
                if (startDateStr && orderDateOnly < startDateStr) return false;
                if (endDateStr && orderDateOnly > endDateStr) return false;
                return true;
            });

            // Filter inward cost & payroll inside range
            const filteredInward = state.inward.filter(i => {
                const dateOnly = i.date.substring(0, 10);
                if (startDateStr && dateOnly < startDateStr) return false;
                if (endDateStr && dateOnly > endDateStr) return false;
                return true;
            });
            const inwardCost = filteredInward.reduce((sum, i) => sum + i.amount, 0);

            const filteredPayouts = state.payouts.filter(p => {
                const dateOnly = p.date.substring(0, 10);
                if (startDateStr && dateOnly < startDateStr) return false;
                if (endDateStr && dateOnly > endDateStr) return false;
                return true;
            });
            const payoutCost = filteredPayouts.reduce((sum, p) => sum + p.amount, 0);

            const grossSales = completed.reduce((sum, o) => sum + o.total, 0);
            const totalExpenses = inwardCost + payoutCost;
            const netMargin = grossSales - totalExpenses;

            document.getElementById('stat-revenue').innerText = `₹${grossSales.toFixed(2)}`;
            document.getElementById('stat-expenses').innerText = `₹${totalExpenses.toFixed(2)}`;
            
            const netEl = document.getElementById('stat-net');
            netEl.innerText = `₹${netMargin.toFixed(2)}`;
            if (netMargin >= 0) {
                netEl.className = "text-2xl font-black text-emerald-400 mt-1";
            } else {
                netEl.className = "text-2xl font-black text-red-400 mt-1";
            }

            // Aggregate Sales by Dish
            const dishSales = {};
            state.menu.forEach(item => {
                dishSales[item.name] = { id: item.id, qty: 0, revenue: 0, type: item.type, category: item.category };
            });

            completed.forEach(o => {
                try {
                    const items = JSON.parse(o.items_json);
                    items.forEach(item => {
                        if (dishSales[item.name]) {
                            dishSales[item.name].qty += item.qty;
                            dishSales[item.name].revenue += item.price * item.qty;
                        } else {
                            dishSales[item.name] = { id: item.id, qty: item.qty, revenue: item.price * item.qty, type: item.type, category: item.category };
                        }
                    });
                } catch(e) {}
            });

            const salesArray = Object.keys(dishSales).map(name => ({
                name: name,
                ...dishSales[name]
            }));

            const topSellers = [...salesArray].sort((a, b) => b.qty - a.qty);
            const worstSellers = [...salesArray].sort((a, b) => a.qty - b.qty);

            // Render Top Dishes UI
            const topContainer = document.getElementById('top-selling-dishes');
            if (completed.length === 0 || topSellers.every(item => item.qty === 0)) {
                topContainer.innerHTML = `
                <div class="py-12 text-center text-slate-400 font-bold text-xs flex flex-col items-center justify-center">
                    <i class="fa-solid fa-chart-bar text-2xl mb-2 text-slate-300 animate-pulse"></i>
                    No sales recorded for this date range.
                </div>`;
            } else {
                const maxQty = Math.max(...topSellers.map(i => i.qty)) || 1;
                topContainer.innerHTML = topSellers.slice(0, 5).map(item => {
                    const pct = Math.min(100, Math.round((item.qty / maxQty) * 100));
                    const dotColor = item.type === 'Veg' ? 'bg-emerald-500' : 'bg-rose-500';
                    return `
                        <div class="space-y-1 font-sans">
                            <div class="flex justify-between text-xs font-bold text-slate-700">
                                <span class="flex items-center space-x-1.5">
                                    <span class="w-2 h-2 rounded-full ${dotColor}"></span>
                                    <span>${item.name}</span>
                                </span>
                                <span class="text-slate-900">${item.qty} sold <span class="text-[10px] text-slate-400 font-normal">(₹${item.revenue.toFixed(0)})</span></span>
                            </div>
                            <div class="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                                <div class="bg-emerald-500 h-full rounded-full transition-all duration-500" style="width: ${pct}%"></div>
                            </div>
                        </div>
                    `;
                }).join('');
            }

            // Render Worst Dishes UI
            const worstContainer = document.getElementById('worst-selling-dishes');
            if (worstSellers.length === 0) {
                worstContainer.innerHTML = `<div class="text-xs text-slate-400 py-6 text-center">No catalog items available.</div>`;
            } else {
                worstContainer.innerHTML = worstSellers.slice(0, 5).map(item => {
                    const dotColor = item.type === 'Veg' ? 'bg-emerald-500' : 'bg-rose-500';
                    const badgeClass = item.qty === 0 ? "bg-rose-50 text-rose-700 border-rose-200" : "bg-slate-50 text-slate-600 border-slate-200";
                    return `
                        <div class="flex justify-between items-center p-2.5 rounded-xl border border-slate-100 bg-slate-50/50 text-xs font-bold">
                            <span class="flex items-center space-x-2">
                                <span class="w-2.5 h-2.5 rounded-full ${dotColor}"></span>
                                <span class="text-slate-700">${item.name}</span>
                            </span>
                            <span class="px-2.5 py-1 text-[10px] font-black rounded-lg border ${badgeClass}">
                                ${item.qty} units sold
                            </span>
                        </div>
                    `;
                }).join('');
            }

            const histBody = document.getElementById('historical-orders-table');
            if (completed.length === 0) {
                histBody.innerHTML = `<tr><td colspan="6" class="px-5 py-4 text-center text-slate-400">No completed transactions in history.</td></tr>`;
                return;
            }
            histBody.innerHTML = completed.map(o => `
                <tr class="hover:bg-slate-50 transition">
                    <td class="px-5 py-3 font-bold text-slate-400">#${o.id}</td>
                    <td class="px-5 py-3 font-extrabold text-slate-800">${o.guest_name}</td>
                    <td class="px-5 py-3 font-bold text-slate-500">${o.table_no}</td>
                    <td class="px-5 py-3 text-slate-400 font-medium">${o.date}</td>
                    <td class="px-5 py-3"><span class="px-2 py-0.5 bg-emerald-50 text-emerald-800 rounded font-black text-[9px] uppercase tracking-wide border border-emerald-200/50">${o.payment_method}</span></td>
                    <td class="px-5 py-3 text-right font-black text-slate-800">₹${o.total.toFixed(2)}</td>
                </tr>
            `).join('');
        }

        function mockExport(type) { showToast(`Exporting ${type} as CSV ledger file...`, 'success'); }

        async function handleAdminLogin() {
            const u = document.getElementById('login-username').value.trim();
            const p = document.getElementById('login-password').value;
            
            try {
                const res = await fetch('/api/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ username: u, password: p })
                });
                
                if (res.ok) {
                    const data = await res.json();
                    state.currentUser = { username: data.username, role: data.role };
                    
                    document.getElementById('admin-login-container').classList.add('hidden');
                    document.getElementById('admin-authenticated-content').classList.remove('hidden');
                    showToast(`Logged in successfully as ${data.username}!`, 'success');
                    
                    applyRolePermissions(data.role);
                    fetchData();
                } else {
                    showToast('Incorrect passcode or login credentials.', 'error');
                }
            } catch(e) {
                showToast('Authentication API failed to connect.', 'error');
            }
        }

        function handleAdminLogout() {
            state.currentUser = { username: "None", role: "None" };
            document.getElementById('admin-authenticated-content').classList.add('hidden');
            document.getElementById('admin-login-container').classList.remove('hidden');
            document.getElementById('login-password').value = '';
        }

        function switchAdminTab(tabId) {
            document.querySelectorAll('.admin-view').forEach(el => el.classList.add('hidden'));
            document.getElementById(`view-${tabId}`).classList.remove('hidden');
            document.querySelectorAll('.admin-tab-btn').forEach(btn => {
                btn.className = "admin-tab-btn flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-bold transition text-slate-500 hover:text-slate-800";
            });
            const activeBtn = document.getElementById(`tab-${tabId}`);
            if (activeBtn) {
                activeBtn.className = "admin-tab-btn flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-black bg-white text-slate-800 shadow-sm";
            }
        }

        function openResetModal() { document.getElementById('admin-reset-container').classList.remove('hidden'); }
        function closeResetModal() { document.getElementById('admin-reset-container').classList.add('hidden'); }
        
        async function handleAdminReset() {
            const key = document.getElementById('reset-key').value;
            const pass = document.getElementById('reset-new-password').value;
            if (!pass || pass.trim() === "") {
                return showToast('Password cannot be empty!', 'error');
            }
            
            try {
                const res = await fetch('/api/reset-password', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ key, new_password: pass })
                });
                if (res.ok) {
                    showToast('Admin password reset successful!', 'success');
                    document.getElementById('reset-key').value = '';
                    document.getElementById('reset-new-password').value = '';
                    closeResetModal();
                    fetchData();
                } else {
                    const errData = await res.json();
                    showToast(errData.error || 'Invalid key!', 'error');
                }
            } catch (err) {
                showToast('Failed to connect to reset API.', 'error');
            }
        }

        function syncSetupFields() {
            if (!state.settings) return;
            document.getElementById('setup-merchant-name').value = state.settings.merchant_name || '';
            document.getElementById('setup-upi-id').value = state.settings.upi_id || '';
            
            document.getElementById('setup-preview-name').innerText = state.settings.merchant_name || '-';
            document.getElementById('setup-preview-id').innerText = "UPI ID: " + (state.settings.upi_id || '-');
            
            document.getElementById('modal-merchant-name').innerText = state.settings.merchant_name || '-';
            document.getElementById('modal-upi-id').innerText = "UPI ID: " + (state.settings.upi_id || '-');

            const nocache = Date.now();
            document.getElementById('setup-preview-qr-img').src = `/qr-code.jpeg?t=${nocache}`;
            document.getElementById('modal-qr-img').src = `/qr-code.jpeg?t=${nocache}`;
            
            const fileLabel = document.getElementById('setup-file-label');
            if (fileLabel && state.settings.qr_filename) {
                fileLabel.innerText = state.settings.qr_filename;
            }
        }

        async function saveUpiSettings() {
            const name = document.getElementById('setup-merchant-name').value;
            const upi = document.getElementById('setup-upi-id').value;
            const fileInput = document.getElementById('setup-qr-file');
            
            if (!name || !upi) return showToast('Please enter valid details!', 'error');
            
            const formData = new FormData();
            formData.append('upi_id', upi);
            formData.append('merchant_name', name);
            if (fileInput && fileInput.files && fileInput.files[0]) {
                formData.append('qr_file', fileInput.files[0]);
            }

            try {
                const res = await fetch('/api/settings', {
                    method: 'POST',
                    body: formData
                });
                if (res.ok) {
                    showToast('UPI parameters updated!', 'success');
                    if (fileInput) fileInput.value = "";
                    const label = document.getElementById('setup-file-label');
                    if(label) label.innerText = "Choose Image from Gallery";
                    fetchData();
                } else {
                    showToast('Failed to update config.', 'error');
                }
            } catch (err) {
                showToast('API post failed.', 'error');
            }
        }

        function showToast(msg, type = "success") {
            const container = document.getElementById('toast-container');
            const toast = document.createElement('div');
            const bgClass = type === "success" ? "bg-emerald-600 text-white" : "bg-red-600 text-white";
            toast.className = `${bgClass} shadow-xl rounded-xl p-3 flex items-center space-x-2 text-xs font-bold transition-all duration-300 pointer-events-auto opacity-0 translate-y-2`;
            toast.innerHTML = `
                <i class="fa-solid ${type === 'success' ? 'fa-circle-check' : 'fa-circle-exclamation'} text-sm"></i>
                <span>${msg}</span>
            `;
            container.appendChild(toast);
            
            setTimeout(() => {
                toast.classList.remove('opacity-0', 'translate-y-2');
                toast.classList.add('opacity-100', 'translate-y-0');
            }, 50);

            setTimeout(() => {
                toast.classList.add('opacity-0', 'translate-y-2');
                setTimeout(() => { toast.remove(); }, 300);
            }, 3000);
        }
    </script>
</body>
</html>
"""

# -------------------------------------------------------------------
# FLASK BACKEND ROUTING APIS
# -------------------------------------------------------------------

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/qr-code.jpeg')
def serve_qr_code():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT qr_filename FROM settings WHERE key='default'")
        row = cursor.fetchone()
        target = row['qr_filename'] if row and row['qr_filename'] else None

    if target:
        if os.path.exists(target):
            return send_file(target)
        static_target = os.path.join("static", target)
        if os.path.exists(static_target):
            return send_file(static_target)

    # Fallbacks for missing entries
    try:
        for f in os.listdir('.'):
            if "WhatsApp" in f and f.lower().endswith(('.jpeg', '.jpg', '.png')):
                return send_file(f)
        if os.path.exists('static'):
            for f in os.listdir('static'):
                if "WhatsApp" in f and f.lower().endswith(('.jpeg', '.jpg', '.png')):
                    return send_file(os.path.join('static', f))
    except Exception:
        pass
        
    return "QR Code Image File is not found.", 404

@app.route("/menu-card")
def render_menu_card():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM menu ORDER BY category, name")
        items = [dict(row) for row in cursor.fetchall()]
        
    grouped_menu = {}
    for item in items:
        cat = item['category']
        if cat not in grouped_menu:
            grouped_menu[cat] = []
        grouped_menu[cat].append(item)
        
    return render_template_string(MENU_CARD_TEMPLATE, grouped_menu=grouped_menu)

@app.route("/api/login", methods=["POST"])
def api_login():
    req = request.get_json()
    username = req.get("username", "").strip()
    password = req.get("password", "")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT username, role FROM users WHERE LOWER(username) = LOWER(?) AND password = ?", (username, password))
        row = cursor.fetchone()
        if row:
            return jsonify({
                "success": True,
                "username": row["username"],
                "role": row["role"]
            })
    return jsonify({"success": False, "error": "Invalid credentials"}), 401

@app.route("/api/users", methods=["GET"])
def get_user_accounts():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT username, role FROM users ORDER BY username ASC")
        rows = cursor.fetchall()
        users_list = [dict(row) for row in rows]
    return jsonify(users_list)

@app.route("/api/users", methods=["POST"])
def save_user_account():
    req = request.get_json()
    username = req.get("username", "").strip()
    password = req.get("password", "")
    role = req.get("role", "cashier")

    if not username or not password:
        return jsonify({"success": False, "error": "Username & Passcode are required."}), 400

    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?) "
                "ON CONFLICT(username) DO UPDATE SET password=excluded.password, role=excluded.role",
                (username, password, role)
            )
            # If the Manager (primary system account 'Hotel') password was updated, keep setting sync intact
            if username.lower() == 'hotel':
                cursor.execute("UPDATE settings SET admin_password = ? WHERE key='default'", (password,))
            conn.commit()
            return jsonify({"success": True})
        except sqlite3.Error as e:
            return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/users", methods=["DELETE"])
def delete_user_account():
    req = request.get_json()
    username = req.get("username", "").strip()
    if username.lower() == 'hotel':
        return jsonify({"success": False, "error": "Primary manager account cannot be deleted."}), 400

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE LOWER(username) = LOWER(?)", (username,))
        conn.commit()
    return jsonify({"success": True})

@app.route("/api/data", methods=["GET"])
def get_all_data():
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM menu")
        menu = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("SELECT * FROM inward ORDER BY id DESC")
        inward = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("SELECT * FROM waiters ORDER BY id DESC")
        waiters = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("SELECT * FROM payouts ORDER BY id DESC")
        payouts = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("SELECT * FROM orders ORDER BY id DESC")
        orders = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("SELECT upi_id, merchant_name, qr_filename, admin_password FROM settings WHERE key='default'")
        row = cursor.fetchone()
        settings = dict(row) if row else {
            "upi_id": "9763344984-1@nyes",
            "merchant_name": "ATHARV SUDHIR MANE",
            "qr_filename": "WhatsApp Image 2026-06-27 at 10.39.14 PM.jpeg",
            "admin_password": "123"
        }
        
    return jsonify({
        "menu": menu,
        "inward": inward,
        "waiters": waiters,
        "payouts": payouts,
        "orders": orders,
        "settings": settings
    })

@app.route("/api/menu", methods=["POST"])
def post_menu_item():
    req = request.get_json()
    name = req.get("name")
    category = req.get("category")
    price = float(req.get("price", 0))
    type_ = req.get("type", "Veg")
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO menu (name, category, price, type) VALUES (?, ?, ?, ?)",
            (name, category, price, type_)
        )
        conn.commit()
    return jsonify({"success": True})

@app.route("/api/menu", methods=["DELETE"])
def delete_menu_item():
    req = request.get_json()
    item_id = req.get("id")
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM menu WHERE id = ?", (item_id,))
        conn.commit()
    return jsonify({"success": True})

@app.route("/api/menu/restore", methods=["POST"])
def restore_default_menu():
    """Allows administrators to restore the primary default menu structure instantly."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM menu")
        for item in DEFAULT_MENU:
            cursor.execute("INSERT INTO menu (name, category, price, type) VALUES (?, ?, ?, ?)",
                           (item['name'], item['category'], item['price'], item['type']))
        conn.commit()
    return jsonify({"success": True})

@app.route("/api/order", methods=["POST"])
def post_new_order():
    req = request.get_json()
    guest_name = req.get("guest_name", "Walk-In Guest")
    table_no = req.get("table_no", "Table 1")
    total = float(req.get("total", 0.0))
    items_json = req.get("items_json", "[]")
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO orders (guest_name, table_no, total, status, payment_method, date, items_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (guest_name, table_no, total, 'pending', 'Unpaid', date_str, items_json)
        )
        conn.commit()
    return jsonify({"success": True})

@app.route("/api/order/complete", methods=["POST"])
def complete_order():
    req = request.get_json()
    order_id = req.get("id")
    payment_method = req.get("payment_method", "Cash")
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE orders SET status = 'completed', payment_method = ? WHERE id = ?",
            (payment_method, order_id)
        )
        conn.commit()
    return jsonify({"success": True})

@app.route("/api/waiter", methods=["POST"])
def register_waiter():
    req = request.get_json()
    name = req.get("name")
    daily_salary = float(req.get("daily_salary", 0))
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO waiters (name, daily_salary) VALUES (?, ?)",
            (name, daily_salary)
        )
        conn.commit()
    return jsonify({"success": True})

@app.route("/api/waiter", methods=["DELETE"])
def fire_waiter():
    req = request.get_json()
    waiter_id = req.get("id")
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM waiters WHERE id = ?", (waiter_id,))
        conn.commit()
    return jsonify({"success": True})

@app.route("/api/payout", methods=["POST"])
def register_payout():
    req = request.get_json()
    waiter_id = int(req.get("waiter_id"))
    waiter_name = req.get("waiter_name")
    amount = float(req.get("amount", 0))
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO payouts (waiter_id, waiter_name, amount, date) VALUES (?, ?, ?, ?)",
            (waiter_id, waiter_name, amount, date_str)
        )
        conn.commit()
    return jsonify({"success": True})

@app.route("/api/inward", methods=["POST"])
def add_raw_material():
    req = request.get_json()
    item = req.get("item")
    supplier = req.get("supplier")
    qty = float(req.get("qty", 0))
    unit = req.get("unit", "Kg")
    amount = float(req.get("amount", 0))
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO inward (item, supplier, qty, unit, amount, date) VALUES (?, ?, ?, ?, ?, ?)",
            (item, supplier, qty, unit, amount, date_str)
        )
        conn.commit()
    return jsonify({"success": True})

@app.route("/api/settings", methods=["POST"])
def update_settings():
    upi_id = request.form.get("upi_id")
    merchant_name = request.form.get("merchant_name")
    qr_file = request.files.get("qr_file")
    
    qr_filename = None
    if qr_file and qr_file.filename:
        qr_filename = qr_file.filename
        if not os.path.exists("static"):
            os.makedirs("static")
        file_path = os.path.join("static", qr_filename)
        qr_file.save(file_path)
        
    with get_db() as conn:
        cursor = conn.cursor()
        if qr_filename:
            cursor.execute(
                "INSERT INTO settings (key, upi_id, merchant_name, qr_filename) VALUES ('default', ?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET upi_id=excluded.upi_id, merchant_name=excluded.merchant_name, qr_filename=excluded.qr_filename",
                (upi_id, merchant_name, qr_filename)
            )
        else:
            cursor.execute(
                "INSERT INTO settings (key, upi_id, merchant_name) VALUES ('default', ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET upi_id=excluded.upi_id, merchant_name=excluded.merchant_name",
                (upi_id, merchant_name)
            )
        conn.commit()
    return jsonify({"success": True})

@app.route("/api/reset-password", methods=["POST"])
def reset_password():
    req = request.get_json()
    key = req.get("key")
    new_password = req.get("new_password")
    if key == "RESET123":
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE settings SET admin_password = ? WHERE key='default'", (new_password,))
            cursor.execute("UPDATE users SET password = ? WHERE username = 'Hotel'", (new_password,))
            conn.commit()
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Invalid Recovery Passkey"}), 400

@app.route("/api/export/orders", methods=["GET"])
def export_orders_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Order ID", "Guest Name", "Table No", "Total Revenue", "Status", "Payment Method", "Date"])
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, guest_name, table_no, total, status, payment_method, date FROM orders")
        rows = cursor.fetchall()
        for r in rows:
            writer.writerow(list(r))
            
    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=orders_export.csv"
    return response

@app.route("/api/export/expenses", methods=["GET"])
def export_expenses_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Type", "ID", "Detail / Supplier Name", "Qty / Waiter ID", "Date", "Total Cost Paid (₹)"])
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Export Material Inwards
        cursor.execute("SELECT id, item, supplier, qty, unit, amount, date FROM inward")
        inwards = cursor.fetchall()
        for r in inwards:
            writer.writerow(["Material Inward", r["id"], f"{r['item']} ({r['supplier']})", f"{r['qty']} {r['unit']}", r["date"], r["amount"]])
            
        # Export Waiter Payroll Payouts
        cursor.execute("SELECT id, waiter_name, waiter_id, amount, date FROM payouts")
        payouts = cursor.fetchall()
        for r in payouts:
            writer.writerow(["Staff Payroll Payout", r["id"], f"Paid: {r['waiter_name']}", f"Waiter ID: {r['waiter_id']}", r["date"], r["amount"]])
            
    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=expenses_export.csv"
    return response

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)