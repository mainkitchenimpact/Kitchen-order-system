import streamlit as st
import pandas as pd
from datetime import date, datetime, timezone, timedelta
import firebase_admin
from firebase_admin import credentials, firestore
import streamlit.components.v1 as components
import math

# ==========================================
# 1. การเชื่อมต่อ Firebase ผ่าน Streamlit Secrets
# ==========================================
if not firebase_admin._apps:
    try:
        key_dict = dict(st.secrets["firebase"])
        if "private_key" in key_dict:
            key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error(f"ไม่สามารถเชื่อมต่อ Firebase ได้: {e}")

db = firestore.client()

# ==========================================
# 2. กำหนดโครงสร้างตารางข้อมูล & Session State
# ==========================================
columns_format = ['No (Function)', 'ประเภทงาน', 'จำนวนคน', 'To', 'วันที่รับสินค้า', 'วันที่ใช้สินค้า', 
                  'เมนู', 'วัตถุดิบ', 'ครัวที่รับผิดชอบ', 'จำนวน', 'หน่วย', 'สถานะ', 'วันที่สั่ง', 'หมายเหตุ', 
                  'is_printed_prep', 'is_printed_butcher']

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

# ==========================================
# 3. ฟังก์ชันดึงข้อมูล (พร้อม Auto-Seed เมื่อ DB ถ่ายว่าง)
# ==========================================
def format_date_th(date_val):
    if not date_val or str(date_val) == '-':
        return '-'
    if isinstance(date_val, (date, datetime)):
        return date_val.strftime("%d/%m/%Y")
    try:
        dt = datetime.strptime(str(date_val), "%Y-%m-%d")
        return dt.strftime("%d/%m/%Y")
    except ValueError:
        return str(date_val)

def load_master_recipes():
    try:
        docs = db.collection('master_recipes').stream()
        data = []
        for doc in docs:
            d = doc.to_dict()
            d['doc_id'] = doc.id 
            data.append(d)
            
        if not data:
            # ✨ AUTO-SEED: หากฐานข้อมูลใหม่ว่างเปล่า ให้ยัดข้อมูลตัวอย่างใส่ให้อัตโนมัติทันที
            initial_recipes = [
                {'Recipe_Code': 'EU001', 'Food_Name': 'แกะอบซอสไทม์', 'Kitchen_Dept': 'ครัว บุชเชอร์', 'Item_Code': 'BU-001', 'Item_Description': 'ซี่โครงแกะสไลด์', 'Std_Quantity': 1.0, 'Unit': 'Pc.'},
                {'Recipe_Code': 'EU002', 'Food_Name': 'ไก่กรอบปาปริก้าซอสทาร์ทาร์', 'Kitchen_Dept': 'ครัว บุชเชอร์', 'Item_Code': 'BU-002', 'Item_Description': 'ไก่กรอบปาปริก้า', 'Std_Quantity': 1.0, 'Unit': 'Pc.'},
                {'Recipe_Code': 'EU002', 'Food_Name': 'ไก่กรอบปาปริก้าซอสทาร์ทาร์', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PA-001', 'Item_Description': 'มายองเนส', 'Std_Quantity': 2.0, 'Unit': 'Pack'},
                {'Recipe_Code': 'EU002', 'Food_Name': 'ไก่กรอบปาปริก้าซอสทาร์ทาร์', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PA-002', 'Item_Description': 'ครีมสลัด', 'Std_Quantity': 1.0, 'Unit': 'Pack'},
                {'Recipe_Code': 'EU007', 'Food_Name': 'สตูว์หมู', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PA-003', 'Item_Description': 'มันฝรั่งหั่นเต๋า', 'Std_Quantity': 0.05, 'Unit': 'Kg.'},
                {'Recipe_Code': 'EU007', 'Food_Name': 'สตูว์หมู', 'Kitchen_Dept': 'ครัว บุชเชอร์', 'Item_Code': 'BU-003', 'Item_Description': 'เนื้อหมูหั่นเต๋าใหญ่', 'Std_Quantity': 0.1, 'Unit': 'Kg.'}
            ]
            for item in initial_recipes:
                db.collection('master_recipes').add(item)
            return pd.DataFrame(initial_recipes)
            
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"ไม่สามารถดึงข้อมูลสูตรอาหารได้: {e}")
        return pd.DataFrame()

def load_orders():
    try:
        docs = db.collection('orders').stream()
        data = []
        for doc in docs:
            d = doc.to_dict()
            d['doc_id'] = doc.id
            data.append(d)
        return pd.DataFrame(data) if data else pd.DataFrame(columns=columns_format)
    except Exception as e:
        st.error(f"ไม่สามารถดึงข้อมูลออเดอร์ได้: {e}")
        return pd.DataFrame(columns=columns_format)

def load_history_logs():
    try:
        docs = db.collection('order_history_logs').stream()
        data = [doc.to_dict() for doc in docs]
        return pd.DataFrame(data) if data else pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()

def generate_next_item_code(dept_name, current_master_df):
    prefix_map = {"ครัว บุชเชอร์": "BU", "ครัว Prep": "PA", "ครัว Bakery": "BA"}
    prefix = prefix_map.get(dept_name, "GEN")
    max_num = 0
    if not current_master_df.empty and 'Item_Code' in current_master_df.columns:
        for code in current_master_df['Item_Code'].dropna():
            code_str = str(code).strip()
            if code_str.startswith(prefix + "-"):
                try:
                    num_part = int(code_str.split("-")[1])
                    if num_part > max_num: max_num = num_part
                except ValueError: pass
    return f"{prefix}-{(max_num + 1):03d}"

# ==========================================
# 4. ฟังก์ชันสร้าง HTML แบบฟอร์มสำหรับสั่งพิมพ์
# ==========================================
def generate_printable_html(draft_df, event_type, pax, to_dept, no_func, rec_date, use_date):
    prep_items = draft_df[draft_df['ครัวที่รับผิดชอบ'].str.strip() == 'ครัว Prep'].reset_index(drop=True)
    butcher_items = draft_df[draft_df['ครัวที่รับผิดชอบ'].str.strip().isin(['ครัว บุชเชอร์', 'ครัวบุชเชอร์'])].reset_index(drop=True)
    
    formatted_rec_date = format_date_th(rec_date)
    formatted_use_date = format_date_th(use_date)
    
    ITEMS_PER_PAGE = 18
    prep_pages = max(1, math.ceil(len(prep_items) / ITEMS_PER_PAGE))
    butcher_pages = max(1, math.ceil(len(butcher_items) / ITEMS_PER_PAGE))
    total_pages = max(prep_pages, butcher_pages)

    pages_html = ""
    for p in range(total_pages):
        prep_sub = prep_items.iloc[p*ITEMS_PER_PAGE : (p+1)*ITEMS_PER_PAGE]
        butcher_sub = butcher_items.iloc[p*ITEMS_PER_PAGE : (p+1)*ITEMS_PER_PAGE]

        def render_table_rows(df, start_idx):
            rows_html = ""
            for idx in range(ITEMS_PER_PAGE):
                if idx < len(df):
                    row = df.iloc[idx]
                    rows_html += f"""
                    <tr>
                        <td style="text-align:center;">{start_idx + idx + 1}</td>
                        <td style="text-align:center;">{row.get('จำนวน', 0)}</td>
                        <td style="text-align:center;">{row.get('หน่วย', '')}</td>
                        <td>{row.get('วัตถุดิบ', '')}</td>
                        <td>{row.get('เมนู', '')}</td>
                    </tr>"""
                else:
                    rows_html += "<tr><td>&nbsp;</td><td></td><td></td><td></td><td></td></tr>"
            return rows_html

        page_break_style = "page-break-after: always;" if p < total_pages - 1 else ""

        pages_html += f"""
        <div class="page-sheet" style="{page_break_style}">
            <div class="page-container">
                <div class="form-box">
                    <div class="doc-code-top">PM38-FM-001</div>
                    <div class="header-title">IMPACT EXHIBITION MANAGEMENT CO.,LTD.</div>
                    <div class="sub-title">Food Requisition Form (หน้า {p+1}/{total_pages})</div>
                    <table class="meta-table">
                        <tr><td class="bg-gray" width="22%">ประเภทงาน :</td><td width="28%">{event_type}</td><td class="bg-gray" width="22%">จำนวนคน :</td><td width="28%">{pax}</td></tr>
                        <tr><td class="bg-gray">To :</td><td>{to_dept}</td><td class="bg-gray">No. (Function) :</td><td>{no_func}</td></tr>
                        <tr><td class="bg-gray">From :</td><td class="bg-yellow">ครัว Prep</td><td class="bg-gray">Delivery Date:</td><td class="bg-yellow">{formatted_rec_date}</td></tr>
                    </table>
                    <table class="main-table">
                        <thead>
                            <tr><th rowspan="2" width="8%">No.</th><th colspan="2" width="28%">REQUESTED</th><th rowspan="2" width="34%">Description</th><th rowspan="2" width="30%">Menu</th></tr>
                            <tr><th width="14%">Quantity</th><th width="14%">Unit</th></tr>
                        </thead>
                        <tbody>{render_table_rows(prep_sub, p*ITEMS_PER_PAGE)}</tbody>
                    </table>
                    <table class="meta-table">
                        <tr><td class="bg-gray" width="30%">วันที่รับ</td><td class="bg-yellow">{formatted_rec_date}</td></tr>
                        <tr><td class="bg-gray">วันที่ใช้</td><td class="bg-yellow">{formatted_use_date}</td></tr>
                    </table>
                    <table class="footer-table">
                        <tr><td width="50%">Requested by: _________________</td><td width="50%" align="right">Issued by: _________________</td></tr>
                    </table>
                    <div class="doc-version-bottom">ฉบับที่ 1 - 1 ก.ย. 54</div>
                </div>

                <div class="form-box">
                    <div class="doc-code-top">PM38-FM-001</div>
                    <div class="header-title">IMPACT EXHIBITION MANAGEMENT CO.,LTD.</div>
                    <div class="sub-title">Food Requisition Form (หน้า {p+1}/{total_pages})</div>
                    <table class="meta-table">
                        <tr><td class="bg-gray" width="22%">ประเภทงาน :</td><td width="28%">{event_type}</td><td class="bg-gray" width="22%">จำนวนคน :</td><td width="28%">{pax}</td></tr>
                        <tr><td class="bg-gray">To :</td><td>{to_dept}</td><td class="bg-gray">No. (Function) :</td><td>{no_func}</td></tr>
                        <tr><td class="bg-gray">From :</td><td class="bg-yellow">ครัว บุชเชอร์</td><td class="bg-gray">Delivery Date:</td><td class="bg-yellow">{formatted_rec_date}</td></tr>
                    </table>
                    <table class="main-table">
                        <thead>
                            <tr><th rowspan="2" width="8%">No.</th><th colspan="2" width="28%">REQUESTED</th><th rowspan="2" width="34%">Description</th><th rowspan="2" width="30%">Menu</th></tr>
                            <tr><th width="14%">Quantity</th><th width="14%">Unit</th></tr>
                        </thead>
                        <tbody>{render_table_rows(butcher_sub, p*ITEMS_PER_PAGE)}</tbody>
                    </table>
                    <table class="meta-table">
                        <tr><td class="bg-gray" width="30%">วันที่รับ</td><td class="bg-yellow">{formatted_rec_date}</td></tr>
                        <tr><td class="bg-gray">วันที่ใช้</td><td class="bg-yellow">{formatted_use_date}</td></tr>
                    </table>
                    <table class="footer-table">
                        <tr><td width="50%">Requested by: _________________</td><td width="50%" align="right">Issued by: _________________</td></tr>
                    </table>
                    <div class="doc-version-bottom">ฉบับที่ 1 - 1 ก.ย. 54</div>
                </div>
            </div>
        </div>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{ size: A4 landscape; margin: 5mm; }}
            body {{ font-family: 'Sarabun', 'Arial', sans-serif; font-size: 11px; margin: 0; padding: 10px; background-color: #fff; }}
            .page-sheet {{ margin-bottom: 20px; }}
            .page-container {{ display: flex; justify-content: space-between; gap: 15px; width: 100%; }}
            .form-box {{ width: 49%; border: 2px solid #000; padding: 6px; box-sizing: border-box; position: relative; }}
            .doc-code-top {{ position: absolute; top: 6px; right: 8px; font-weight: bold; font-size: 10px; }}
            .header-title {{ text-align: center; font-weight: bold; font-size: 12px; text-decoration: underline; margin-bottom: 2px; padding-right: 60px; }}
            .sub-title {{ text-align: center; font-weight: bold; font-size: 11px; margin-bottom: 6px; }}
            .meta-table {{ width: 100%; border-collapse: collapse; margin-bottom: 5px; }}
            .meta-table td {{ padding: 2px 4px; font-size: 10px; border: 1px solid #000; }}
            .bg-gray {{ background-color: #d9d9d9; font-weight: bold; }}
            .bg-yellow {{ background-color: #fff2cc; font-weight: bold; }}
            .main-table {{ width: 100%; border-collapse: collapse; margin-bottom: 5px; }}
            .main-table th, .main-table td {{ border: 1px solid #000; padding: 2px 4px; height: 17px; font-size: 10px; }}
            .main-table th {{ background-color: #f2f2f2; text-align: center; font-weight: bold; }}
            .footer-table {{ width: 100%; border-collapse: collapse; margin-top: 4px; }}
            .footer-table td {{ padding: 2px; font-size: 10px; font-weight: bold; }}
            .doc-version-bottom {{ font-size: 9px; font-weight: bold; margin-top: 2px; }}
            .print-btn {{ background-color: #007bff; color: white; border: none; padding: 10px 20px; font-size: 14px; font-weight: bold; cursor: pointer; border-radius: 5px; margin-bottom: 15px; }}
            .print-btn:hover {{ background-color: #0056b3; }}
            @media print {{ .print-btn {{ display: none; }} .page-sheet {{ margin-bottom: 0; }} }}
        </style>
    </head>
    <body>
        <button class="print-btn" onclick="window.print()">🖨️ สั่งพิมพ์เอกสารนี้ (Print / Save as PDF)</button>
        {pages_html}
    </body>
    </html>
    """
    return html_content, total_pages

st.set_page_config(page_title="ระบบสั่งวัตถุดิบครัว", layout="wide")

# ==========================================
# 5. หน้าล็อกอิน (Login Page)
# ==========================================
def login_page():
    st.title("🔐 เข้าสู่ระบบ (Login)")
    st.markdown("กรุณาเลือกแผนกของคุณเพื่อเข้าใช้งานระบบออเดอร์")
    departments = ["Main Kitchen", "Prep", "Butcher", "Admin"]
    selected_dept = st.selectbox("เลือกแผนก (Department):", departments)
    if st.button("เข้าสู่ระบบ"):
        st.session_state.logged_in_dept = selected_dept
        st.rerun()

# ==========================================
# 6. หน้าของครัวเมน (Main Kitchen)
# ==========================================
def main_kitchen_page():
    col1, col2 = st.columns([8, 1])
    with col1: 
        st.title("🍳 ออเดอร์สินค้าครัวเมน (Main Kitchen)")
    with col2:
        if st.button("ออกจากระบบ"):
            st.session_state.logged_in_dept = None
            st.rerun()
            
    st.markdown("---")
    master_df = load_master_recipes()
    if master_df.empty:
        st.warning("⚠️ ยังไม่มีข้อมูลสูตรอาหาร กรุณาไปเพิ่มข้อมูลที่เมนู Admin ก่อนครับ")
        return

    # --- ส่วนที่ 1: รายละเอียดงาน ---
    h_col1, h_col2 = st.columns([8, 2])
    with h_col1: st.header("📝 1. ข้อมูลรายละเอียดงาน")
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
    
    # --- ส่วนที่ 2: เลือกเมนูอาหาร & สินค้าเพิ่มเติม ---
    st.header("🛒 2. เลือกเมนู และ ปริมาณวัตถุดิบ")
    menu_list = master_df['Food_Name'].dropna().unique() if 'Food_Name' in master_df.columns else []
    selected_menu = st.selectbox("ค้นหาและเลือกเมนูอาหาร:", menu_list) if len(menu_list) > 0 else None

    edited_prep_df, edited_butcher_df = pd.DataFrame(), pd.DataFrame()
    if selected_menu:
        recipe_df = master_df[master_df['Food_Name'] == selected_menu].copy()
        if 'Std_Quantity' in recipe_df.columns:
            recipe_df['Std_Quantity'] = pd.to_numeric(recipe_df['Std_Quantity'], errors='coerce').fillna(0)
            recipe_df['จำนวน'] = recipe_df['Std_Quantity'] * pax
            display_cols = [c for c in ['Item_Code', 'Item_Description', 'จำนวน', 'Unit'] if c in recipe_df.columns]
            
            col_prep, col_butcher = st.columns(2)
            with col_prep:
                st.markdown("#### 🥗 ครัว Prep")
                p_df = recipe_df[recipe_df['Kitchen_Dept'].str.strip() == 'ครัว Prep']
                if not p_df.empty: 
                    edited_prep_df = st.data_editor(p_df[display_cols], use_container_width=True, hide_index=True, disabled=["Item_Code", "Item_Description"], key=f"prep_{selected_menu}")
                else: st.info("ไม่มีรายการ")
            with col_butcher:
                st.markdown("#### 🥩 ครัว บุชเชอร์")
                b_df = recipe_df[recipe_df['Kitchen_Dept'].str.strip().isin(['ครัว บุชเชอร์', 'ครัวบุชเชอร์'])]
                if not b_df.empty: 
                    edited_butcher_df = st.data_editor(b_df[display_cols], use_container_width=True, hide_index=True, disabled=["Item_Code", "Item_Description"], key=f"butcher_{selected_menu}")
                else: st.info("ไม่มีรายการ")

        if st.button(f"➕ เพิ่ม {selected_menu}"):
            if event_type == "": st.error("กรุณากรอก 'ประเภทงาน' ด้านบนก่อนครับ")
            else:
                new_drafts = []
                rec_str = format_date_th(receive_date)
                use_str = format_date_th(use_date)
                
                tz_th = timezone(timedelta(hours=7))
                now_str = datetime.now(tz_th).strftime("%d/%m/%Y %H:%M")
                
                for df_part, dept_name in [(edited_prep_df, 'ครัว Prep'), (edited_butcher_df, 'ครัว บุชเชอร์')]:
                    if not df_part.empty:
                        for _, row in df_part.iterrows():
                            new_drafts.append({
                                'No (Function)': no_function, 'ประเภทงาน': event_type, 'จำนวนคน': pax,
                                'To': to_dept, 'วันที่รับสินค้า': rec_str, 'วันที่ใช้สินค้า': use_str, 'เมนู': selected_menu,
                                'วัตถุดิบ': row.get('Item_Description', '-'), 'ครัวที่รับผิดชอบ': dept_name,
                                'จำนวน': row.get('จำนวน', 0), 'หน่วย': row.get('Unit', '-'), 'สถานะ': '🔴 รอรับออเดอร์',
                                'วันที่สั่ง': now_str, 'หมายเหตุ': '', 'is_printed_prep': False, 'is_printed_butcher': False
                            })
                if new_drafts:
                    st.session_state.draft_orders = pd.concat([st.session_state.draft_orders, pd.DataFrame(new_drafts)], ignore_index=True)
                    st.success(f"เพิ่มเมนู {selected_menu} เรียบร้อย!")

    # --- ส่วนที่ 3: สรุปรายการ ---
    st.markdown("---")
    st.header("📤 3. รายการวัตถุดิบ")
    if st.session_state.draft_orders.empty:
        st.info("ยังไม่มีเมนูในรายการ กรุณาเลือกเมนูและกดปุ่ม '➕ เพิ่ม...' ด้านบน")
    else:
        draft_df = st.session_state.draft_orders.copy()
        draft_df['__index__'] = draft_df.index 
        draft_df.insert(0, '❌ ลบ', False)
        
        sum_c1, sum_c2 = st.columns(2)
        summary_cols = ['❌ ลบ', 'เมนู', 'วัตถุดิบ', 'จำนวน', 'หน่วย', '__index__']
        
        with sum_c1:
            st.markdown("#### 🥗 สรุป: ครัว Prep")
            p_sum = draft_df[draft_df['ครัวที่รับผิดชอบ'] == 'ครัว Prep']
            if not p_sum.empty:
                e_p = st.data_editor(p_sum[summary_cols], use_container_width=True, hide_index=True, disabled=['เมนู', 'วัตถุดิบ'], column_config={"__index__": None}, key="sum_p")
                for _, r in e_p.iterrows(): st.session_state.draft_orders.at[r['__index__'], 'จำนวน'] = r['จำนวน']
            else: st.info("ไม่มีรายการ")
        with sum_c2:
            st.markdown("#### 🥩 สรุป: บุชเชอร์")
            b_sum = draft_df[draft_df['ครัวที่รับผิดชอบ'] == 'ครัว บุชเชอร์']
            if not b_sum.empty:
                e_b = st.data_editor(b_sum[summary_cols], use_container_width=True, hide_index=True, disabled=['เมนู', 'วัตถุดิบ'], column_config={"__index__": None}, key="sum_b")
                for _, r in e_b.iterrows(): st.session_state.draft_orders.at[r['__index__'], 'จำนวน'] = r['จำนวน']
            else: st.info("ไม่มีรายการ")

        c_del, c_submit = st.columns([4, 6])
        with c_del:
            if st.button("🗑️ ลบรายการที่เลือก"):
                to_del = []
                if 'e_p' in locals() and not e_p.empty: to_del.extend(e_p[e_p['❌ ลบ'] == True]['__index__'].tolist())
                if 'e_b' in locals() and not e_b.empty: to_del.extend(e_b[e_b['❌ ลบ'] == True]['__index__'].tolist())
                if to_del:
                    st.session_state.draft_orders = st.session_state.draft_orders.drop(to_del).reset_index(drop=True)
                    st.rerun()

        with c_submit:
            if st.button("✅ ยืนยันใบออเดอร์", type="primary", use_container_width=True):
                for _, row in st.session_state.draft_orders.iterrows():
                    o_data = row.to_dict()
                    o_data['timestamp'] = firestore.SERVER_TIMESTAMP
                    db.collection('orders').add(o_data)
                st.session_state.draft_orders = pd.DataFrame(columns=columns_format)
                st.success("ส่งออเดอร์สำเร็จ!")
                st.rerun()

# ==========================================
# 7. หน้า Admin (จัดการสูตรอาหาร)
# ==========================================
def admin_page():
    col1, col2 = st.columns([8, 1])
    with col1: st.title("⚙️ ระบบหลังบ้าน: จัดการสูตรอาหาร (Master Recipes)")
    with col2:
        if st.button("ออกจากระบบ"):
            st.session_state.logged_in_dept = None
            st.rerun()
            
    st.markdown("---")
    st.header("➕ เพิ่มสูตรอาหารใหม่")
    
    with st.form("batch_add_recipe_form"):
        rc1, rc2 = st.columns(2)
        with rc1:
            recipe_code = st.text_input("รหัสสูตร (Recipe Code):", placeholder="เช่น EU001")
            food_name = st.text_input("ชื่อเมนูอาหาร (Food Name):", placeholder="เช่น แกะอบซอสไทม์")
        with rc2:
            kitchen_dept = st.selectbox("ครัวที่รับผิดชอบหลัก:", ["ครัว Prep", "ครัว บุชเชอร์", "ครัว Bakery"])

        batch_df = pd.DataFrame([{"ชื่อวัตถุดิบ (Description)": "", "อัตราส่วนต่อ 1 คน": 0.0, "หน่วย": ""} for _ in range(10)])
        edited_batch_df = st.data_editor(batch_df, num_rows="dynamic", use_container_width=True, hide_index=True)
        submitted = st.form_submit_button("💾 บันทึกสูตรอาหารลง Firebase", type="primary")
        
        if submitted:
            if food_name.strip() == "": st.error("กรุณากรอกชื่อเมนูอาหาร")
            else:
                success_count = 0
                temp_master = load_master_recipes()
                for _, row in edited_batch_df.iterrows():
                    desc = str(row["ชื่อวัตถุดิบ (Description)"]).strip()
                    if desc and desc != "nan":
                        auto_code = generate_next_item_code(kitchen_dept, temp_master)
                        new_data = {
                            'Recipe_Code': recipe_code.strip(), 'Food_Name': food_name.strip(),
                            'Kitchen_Dept': kitchen_dept, 'Item_Code': auto_code,
                            'Item_Description': desc,
                            'Std_Quantity': float(row["อัตราส่วนต่อ 1 คน"]) if pd.notna(row["อัตราส่วนต่อ 1 คน"]) else 0.0,
                            'Unit': str(row["หน่วย"]).strip() if pd.notna(row["หน่วย"]) else ""
                        }
                        db.collection('master_recipes').add(new_data)
                        
                        temp_master = pd.concat([temp_master, pd.DataFrame([new_data])], ignore_index=True)
                        success_count += 1
                if success_count > 0:
                    st.success(f"บันทึกเมนู '{food_name}' สำเร็จ {success_count} รายการ!")
                    st.rerun()

# ==========================================
# 8. หน้าของครัวรับงาน (Prep / Butcher)
# ==========================================
def receiver_kitchen_page(dept_name):
    dept_mapping = {"Prep": "ครัว Prep", "Butcher": "ครัว บุชเชอร์"}
    target_dept = dept_mapping.get(dept_name, dept_name)
    print_field = "is_printed_prep" if target_dept == "ครัว Prep" else "is_printed_butcher"
    
    col1, col2 = st.columns([8, 1])
    with col1: st.title(f"🔪 หน้าจอจัดการออเดอร์: {target_dept}")
    with col2:
        if st.button("ออกจากระบบ"):
            st.session_state.logged_in_dept = None
            st.rerun()
            
    st.markdown("---")
    all_orders = load_orders()
    if all_orders.empty:
        st.info("🎉 ยังไม่มีออเดอร์เข้ามาในระบบครับ")
        return

    my_orders = all_orders[all_orders['ครัวที่รับผิดชอบ'] == target_dept].reset_index(drop=True)
    if my_orders.empty:
        st.info(f"🎉 ยังไม่มีออเดอร์ของ {target_dept} ในขณะนี้ครับ")
        return

    unique_jobs = my_orders.drop_duplicates(subset=['To', 'ประเภทงาน', 'วันที่สั่ง']).reset_index(drop=True)
    unique_jobs = unique_jobs.iloc[::-1].reset_index(drop=True)

    for idx, job in unique_jobs.iterrows():
        job_to = job.get('To', '-')
        job_no = job.get('No (Function)', '-')
        job_event = job.get('ประเภทงาน', '-')
        job_pax = job.get('จำนวนคน', '-')
        job_rec_date = format_date_th(job.get('วันที่รับสินค้า', '-'))
        job_use_date = format_date_th(job.get('วันที่ใช้สินค้า', '-'))
        job_order_date = job.get('วันที่สั่ง', '-')
        
        job_items = my_orders[
            (my_orders['To'] == job_to) & 
            (my_orders['ประเภทงาน'] == job_event) &
            (my_orders['วันที่สั่ง'] == job_order_date)
        ].reset_index(drop=True)

        is_job_printed = any(job_items[print_field].fillna(False)) if print_field in job_items.columns else False
        print_status_text = " : [🟢 พิมพ์ใบเบิกแล้ว]" if is_job_printed else ""

        header_text = f"📌 งาน: {job_to} | ประเภท: {job_event} | {job_pax} คน | วันที่รับสินค้า: {job_rec_date} | วันที่ใช้งาน: {job_use_date}{print_status_text}"
        
        with st.expander(header_text, expanded=False):
            p_col1, p_col2 = st.columns([3, 7])
            with p_col1:
                if st.button(f"🖨️ พิมพ์ใบเบิก", key=f"rec_btn_print_{idx}"):
                    st.session_state[f"rec_show_modal_{idx}"] = not st.session_state.get(f"rec_show_modal_{idx}", False)
            with p_col2:
                chk_printed = st.checkbox("☑️ พิมพ์แล้ว", value=is_job_printed, key=f"chk_printed_{idx}")
                if chk_printed != is_job_printed:
                    for doc_id in job_items['doc_id']:
                        db.collection('orders').document(doc_id).update({print_field: chk_printed})
                    st.success("บันทึกสถานะการพิมพ์เรียบร้อยแล้ว!")
                    st.rerun()

            if st.session_state.get(f"rec_show_modal_{idx}", False):
                with st.container():
                    st.markdown("---")
                    hist_html, hist_pages = generate_printable_html(
                        job_items, job_event, job_pax, job_to, job_no, job_rec_date, job_use_date
                    )
                    components.html(hist_html, height=750 * hist_pages, scrolling=True)

# ==========================================
# 9. ระบบควบคุมเส้นทางหน้าจอ (Router)
# ==========================================
if st.session_state.logged_in_dept is None: login_page()
elif st.session_state.logged_in_dept == "Main Kitchen": main_kitchen_page()
elif st.session_state.logged_in_dept == "Admin": admin_page()
else: receiver_kitchen_page(st.session_state.logged_in_dept)
