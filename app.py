import streamlit as st
import pandas as pd
import sqlite3
from datetime import date

# ==========================================
# 1. ตั้งค่าฐานข้อมูล SQLite & Auto-Seed Data
# ==========================================
DB_FILE = "kitchen.db"

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # สร้างตาราง master_recipes
    c.execute('''
        CREATE TABLE IF NOT EXISTS master_recipes (
            doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
            Recipe_Code TEXT,
            Food_Name TEXT,
            Kitchen_Dept TEXT,
            Item_Code TEXT,
            Item_Description TEXT,
            Std_Quantity REAL,
            Unit TEXT
        )
    ''')
    
    # สร้างตาราง orders
    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            no_function TEXT,
            event_type TEXT,
            pax INTEGER,
            to_dept TEXT,
            receive_date TEXT,
            use_date TEXT,
            menu TEXT,
            item_desc TEXT,
            kitchen_dept TEXT,
            qty REAL,
            unit TEXT,
            status TEXT,
            is_printed INTEGER DEFAULT 0,
            order_date TEXT
        )
    ''')
    conn.commit()
    
    # Auto-Seed: ใส่ข้อมูลสูตรอาหารตัวอย่างหากตารางยังว่างอยู่
    c.execute("SELECT COUNT(*) FROM master_recipes")
    if c.fetchone()[0] == 0:
        seed_data = [
            ('EU001', 'แกะอบซอสไทม์', 'ครัว บุชเชอร์', 'BU-001', 'ซี่โครงแกะสไลด์', 1.0, 'Pc.'),
            ('EU002', 'ไก่กรอบปาปริก้าซอสทาร์ทาร์', 'ครัว บุชเชอร์', 'BU-002', 'ไก่กรอบปาปริก้า', 1.0, 'Pc.'),
            ('EU002', 'ไก่กรอบปาปริก้าซอสทาร์ทาร์', 'ครัว Prep', 'PA-001', 'มายองเนส', 2.0, 'Pack'),
            ('EU002', 'ไก่กรอบปาปริก้าซอสทาร์ทาร์', 'ครัว Prep', 'PA-002', 'ครีมสลัด', 1.0, 'Pack'),
            ('EU007', 'สตูว์หมู', 'ครัว Prep', 'PA-003', 'มันฝรั่งหั่นเต๋า', 0.05, 'Kg.'),
            ('EU007', 'สตูว์หมู', 'ครัว Prep', 'PA-004', 'แครอทหั่นเต๋า', 0.05, 'Kg.'),
            ('EU007', 'สตูว์หมู', 'ครัว บุชเชอร์', 'BU-003', 'เนื้อหมูหั่นเต๋าใหญ่', 0.1, 'Kg.')
        ]
        c.executemany('''
            INSERT INTO master_recipes (Recipe_Code, Food_Name, Kitchen_Dept, Item_Code, Item_Description, Std_Quantity, Unit)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', seed_data)
        conn.commit()
    conn.close()

# เรียกใช้งานเตรียมฐานข้อมูล
init_db()

# ==========================================
# 2. ฟังก์ชันจัดการข้อมูล (SQLite Wrappers)
# ==========================================
def load_master_recipes():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM master_recipes", conn)
    conn.close()
    return df

def load_orders():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM orders ORDER BY id DESC", conn)
    conn.close()
    return df

def update_print_status(order_id, is_printed):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE orders SET is_printed = ? WHERE id = ?", (1 if is_printed else 0, order_id))
    conn.commit()
    conn.close()

# ==========================================
# 3. ตั้งค่า Session State & Page Config
# ==========================================
st.set_page_config(page_title="ระบบสั่งวัตถุดิบครัว (Presentation Mode)", layout="wide")

columns_format = ['No (Function)', 'ประเภทงาน', 'จำนวนคน', 'To', 'วันที่รับสินค้า', 'วันที่ใช้สินค้า', 'เมนู', 'วัตถุดิบ', 'ครัวที่รับผิดชอบ', 'จำนวน', 'หน่วย', 'สถานะ']

if 'draft_orders' not in st.session_state:
    st.session_state.draft_orders = pd.DataFrame(columns=columns_format)
if 'logged_in_dept' not in st.session_state:
    st.session_state.logged_in_dept = None

if 'event_type_input' not in st.session_state: st.session_state.event_type_input = ""
if 'no_function_input' not in st.session_state: st.session_state.no_function_input = ""
if 'pax_input' not in st.session_state: st.session_state.pax_input = 70
if 'to_input' not in st.session_state: st.session_state.to_input = ""
if 'receive_date_input' not in st.session_state: st.session_state.receive_date_input = date.today()
if 'use_date_input' not in st.session_state: st.session_state.use_date_input = date.today()

master_df = load_master_recipes()

# ==========================================
# 4. หน้าล็อกอิน (Login Page)
# ==========================================
def login_page():
    st.title("🔐 เข้าสู่ระบบ (Login)")
    st.info("💡 ระบบกำลังอยู่ใน [Presentation Mode] พร้อมใช้งานสำหรับการนำเสนอ")
    departments = ["Main Kitchen", "Prep", "Butcher", "Admin"]
    selected_dept = st.selectbox("เลือกแผนก (Department):", departments)
    if st.button("เข้าสู่ระบบ"):
        st.session_state.logged_in_dept = selected_dept
        st.rerun()

# ==========================================
# 5. หน้าครัวเมน (Main Kitchen)
# ==========================================
def main_kitchen_page():
    col1, col2 = st.columns([8, 1])
    with col1:
        st.title("🍳 ศูนย์บัญชาการ: ครัวเมน (Main Kitchen)")
    with col2:
        if st.button("🚪 ออกจากระบบ"):
            st.session_state.logged_in_dept = None
            st.rerun()
            
    st.markdown("---")
    
    # ข้อมูลรายละเอียดงาน
    h_col1, h_col2 = st.columns([8, 2])
    with h_col1:
        st.header("📝 1. ข้อมูลรายละเอียดงาน")
    with h_col2:
        if st.button("🆕 ขึ้นใบงานใหม่ (Clear Form)"):
            st.session_state.event_type_input = ""
            st.session_state.no_function_input = ""
            st.session_state.pax_input = 70
            st.session_state.to_input = ""
            st.session_state.receive_date_input = date.today()
            st.session_state.use_date_input = date.today()
            st.session_state.draft_orders = pd.DataFrame(columns=columns_format)
            st.rerun()

    c1, c2, c3 = st.columns(3)
    with c1:
        event_type = st.text_input("ประเภทงาน:", placeholder="เช่น Buffet, Set Menu...", key="event_type_input")
        no_function = st.text_input("No (Function):", placeholder="ระบุหมายเลขงาน", key="no_function_input")
    with c2:
        pax = st.number_input("จำนวนคน (Pax):", min_value=1, key="pax_input")
        receive_date = st.date_input("1. วันที่รับสินค้า:", key="receive_date_input")
    with c3:
        to_dept = st.text_input("To :", key="to_input")
        use_date = st.date_input("2. วันที่ใช้สินค้า:", key="use_date_input")

    st.markdown("---")
    st.header("🛒 2. เลือกและจัดเตรียมเมนูอาหาร")
    
    if 'Food_Name' in master_df.columns and not master_df.empty:
        menu_list = master_df['Food_Name'].dropna().unique()
        selected_menu = st.selectbox("ค้นหาและเลือกเมนูอาหาร:", menu_list)
    else:
        st.warning("⚠️ ยังไม่มีข้อมูลเมนูในระบบ")
        selected_menu = None

    edited_prep_df, edited_butcher_df = pd.DataFrame(), pd.DataFrame()

    if selected_menu:
        st.markdown(f"**รายการวัตถุดิบสำหรับ: {selected_menu}** (คำนวณตามจำนวนคนอัตโนมัติ)")
        recipe_df = master_df[master_df['Food_Name'] == selected_menu].copy()
        
        if 'Std_Quantity' in recipe_df.columns:
            recipe_df['Std_Quantity'] = pd.to_numeric(recipe_df['Std_Quantity'], errors='coerce').fillna(0)
            recipe_df['จำนวน'] = recipe_df['Std_Quantity'] * pax
            display_cols = [c for c in ['Item_Code', 'Item_Description', 'จำนวน', 'Unit'] if c in recipe_df.columns]

            col_prep, col_butcher = st.columns(2)
            with col_prep:
                st.markdown("#### 🥗 ครัว Prep")
                prep_df = recipe_df[recipe_df['Kitchen_Dept'] == 'ครัว Prep']
                if not prep_df.empty:
                    edited_prep_df = st.data_editor(prep_df[display_cols], use_container_width=True, hide_index=True, disabled=["Item_Code", "Item_Description"], key=f"prep_{selected_menu}")
                else:
                    st.info("ไม่มีรายการส่งครัว Prep")

            with col_butcher:
                st.markdown("#### 🥩 ครัว บุชเชอร์")
                butcher_df = recipe_df[recipe_df['Kitchen_Dept'] == 'ครัว บุชเชอร์']
                if not butcher_df.empty:
                    edited_butcher_df = st.data_editor(butcher_df[display_cols], use_container_width=True, hide_index=True, disabled=["Item_Code", "Item_Description"], key=f"butcher_{selected_menu}")
                else:
                    st.info("ไม่มีรายการส่งครัว บุชเชอร์")

            if st.button(f"➕ เพิ่ม '{selected_menu}' ลงในรายการสรุป"):
                if event_type == "":
                    st.error("กรุณากรอก 'ประเภทงาน' ด้านบนก่อนครับ")
                else:
                    new_drafts = []
                    rec_str = receive_date.strftime("%Y-%m-%d") if receive_date else ""
                    use_str = use_date.strftime("%Y-%m-%d") if use_date else ""

                    for df_part, dept_name in [(edited_prep_df, 'ครัว Prep'), (edited_butcher_df, 'ครัว บุชเชอร์')]:
                        if not df_part.empty:
                            for _, row in df_part.iterrows():
                                new_drafts.append({
                                    'No (Function)': no_function, 'ประเภทงาน': event_type, 'จำนวนคน': pax,
                                    'To': to_dept, 'วันที่รับสินค้า': rec_str, 'วันที่ใช้สินค้า': use_str,
                                    'เมนู': selected_menu, 'วัตถุดิบ': row.get('Item_Description', '-'),
                                    'ครัวที่รับผิดชอบ': dept_name, 'จำนวน': row.get('จำนวน', 0),
                                    'หน่วย': row.get('Unit', '-'), 'สถานะ': '🔴 รอรับออเดอร์'
                                })
                    if new_drafts:
                        draft_df = pd.DataFrame(new_drafts)
                        st.session_state.draft_orders = pd.concat([st.session_state.draft_orders, draft_df], ignore_index=True)
                        st.success(f"เพิ่มเมนู {selected_menu} เรียบร้อยแล้ว!")

    st.markdown("---")
    st.header("📤 3. สรุปรายการในงานนี้ (รอส่งให้ครัวอื่น)")
    
    if st.session_state.draft_orders.empty:
        st.info("ยังไม่มีรายการในตารางสรุป")
    else:
        st.dataframe(st.session_state.draft_orders[['เมนู', 'วัตถุดิบ', 'ครัวที่รับผิดชอบ', 'จำนวน', 'หน่วย']], use_container_width=True)
        
        if st.button("✅ ยืนยันการส่งออเดอร์ทั้งหมด", type="primary", use_container_width=True):
            conn = get_db_connection()
            c = conn.cursor()
            today_str = date.today().strftime("%Y-%m-%d")
            
            for _, row in st.session_state.draft_orders.iterrows():
                c.execute('''
                    INSERT INTO orders (no_function, event_type, pax, to_dept, receive_date, use_date, menu, item_desc, kitchen_dept, qty, unit, status, is_printed, order_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                ''', (
                    row['No (Function)'], row['ประเภทงาน'], row['จำนวนคน'], row['To'],
                    row['วันที่รับสินค้า'], row['วันที่ใช้สินค้า'], row['เมนู'], row['วัตถุดิบ'],
                    row['ครัวที่รับผิดชอบ'], row['จำนวน'], row['หน่วย'], row['สถานะ'], today_str
                ))
            conn.commit()
            conn.close()
            st.session_state.draft_orders = pd.DataFrame(columns=columns_format)
            st.success("ส่งออเดอร์เข้าฐานข้อมูลสำเร็จ!")
            st.rerun()

# ==========================================
# 6. หน้าครัวรับงาน (Prep / Butcher)
# ==========================================
def receiver_kitchen_page(dept_name):
    col1, col2 = st.columns([8, 1])
    dept_map = {"Prep": "ครัว Prep", "Butcher": "ครัว บุชเชอร์"}
    target_dept = dept_map.get(dept_name, dept_name)

    with col1:
        st.title(f"🔪 หน้าจอรับออเดอร์: {target_dept}")
    with col2:
        if st.button("🚪 ออกจากระบบ"):
            st.session_state.logged_in_dept = None
            st.rerun()

    st.markdown("---")
    if st.button("🔄 ดึงออเดอร์ล่าสุด"):
        st.rerun()

    orders_df = load_orders()
    if not orders_df.empty:
        my_orders = orders_df[orders_df['kitchen_dept'] == target_dept]
        if my_orders.empty:
            st.info("🎉 ยังไม่มีออเดอร์ส่งเข้ามา")
        else:
            grouped = my_orders.groupby(['no_function', 'event_type', 'pax', 'receive_date', 'use_date'])
            for (no_func, ev_type, pax_val, rec_date, u_date), group in grouped:
                first_row = group.iloc[0]
                is_printed = bool(first_row['is_printed'])
                print_tag = " [🟢 พิมพ์ใบเบิกแล้ว]" if is_printed else ""
                
                header_text = f"งาน: {ev_type} | Pax: {pax_val} | รับ: {rec_date} | ใช้: {u_date}{print_tag}"
                
                with st.expander(header_text):
                    top_c1, top_c2 = st.columns([3, 7])
                    with top_c1:
                        if st.button(f"🖨️ พิมพ์ใบเบิก (ID: {first_row['id']})", key=f"print_btn_{first_row['id']}"):
                            st.success("กำลังส่งคำสั่งพิมพ์เอกสาร ISO Form...")
                    with top_c2:
                        chk = st.checkbox("☑️ พิมพ์แล้ว", value=is_printed, key=f"chk_{first_row['id']}")
                        if chk != is_printed:
                            update_print_status(first_row['id'], chk)
                            st.rerun()
                    
                    st.write(f"**วันที่สั่งออเดอร์:** {first_row['order_date']}")
                    st.table(group[['menu', 'item_desc', 'qty', 'unit']].rename(columns={
                        'menu': 'เมนู', 'item_desc': 'วัตถุดิบ', 'qty': 'จำนวน', 'unit': 'หน่วย'
                    }))
    else:
        st.info("🎉 ยังไม่มีออเดอร์ส่งเข้ามา")

# ==========================================
# 7. หน้า Admin (จัดการสูตรอาหาร)
# ==========================================
def admin_page():
    st.title("⚙️ ระบบหลังบ้าน: จัดการสูตรอาหาร (Master Recipes)")
    if st.button("🚪 ออกจากระบบ"):
        st.session_state.logged_in_dept = None
        st.rerun()
    st.markdown("---")
    
    current_master = load_master_recipes()
    st.dataframe(current_master, use_container_width=True)

# ==========================================
# 8. Router
# ==========================================
if st.session_state.logged_in_dept is None:
    login_page()
elif st.session_state.logged_in_dept == "Main Kitchen":
    main_kitchen_page()
elif st.session_state.logged_in_dept == "Admin":
    admin_page()
else:
    receiver_kitchen_page(st.session_state.logged_in_dept)
