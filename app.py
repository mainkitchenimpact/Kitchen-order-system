import pandas as pd
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore

# ดึงข้อมูล Credential จาก Streamlit Secrets
if not firebase_admin._apps:
    key_dict = dict(st.secrets["firebase"])
    # แปลง \n ใน private_key ให้ทำงานถูกต้อง
    key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
    
    cred = credentials.Certificate(key_dict)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ==========================================
# ฟังก์ชันดึงข้อมูลจาก Firebase
# ==========================================
def load_master_recipes():
    try:
        docs = db.collection('master_recipes').stream()
        data = []
        for doc in docs:
            d = doc.to_dict()
            d['doc_id'] = doc.id 
            data.append(d)
        return pd.DataFrame(data) if data else pd.DataFrame()
    except Exception as e:
        st.error(f"ไม่สามารถดึงข้อมูลสูตรอาหารได้: {e}")
        return pd.DataFrame()

def load_orders():
    try:
        docs = db.collection('orders').stream()
        data = [doc.to_dict() for doc in docs]
        if data:
            return pd.DataFrame(data)
        else:
            return pd.DataFrame(columns=columns_format)
    except Exception as e:
        st.error(f"ไม่สามารถดึงข้อมูลออเดอร์ได้: {e}")
        return pd.DataFrame(columns=columns_format)

# ฟังก์ชันช่วยสร้างรหัสวัตถุดิบอัตโนมัติ (Auto-generate Item Code)
def generate_next_item_code(dept_name, current_master_df):
    prefix_map = {
        "ครัว บุชเชอร์": "BU",
        "ครัว Prep": "PA",
        "ครัว Bakery": "BA"
    }
    prefix = prefix_map.get(dept_name, "GEN")
    
    max_num = 0
    if not current_master_df.empty and 'Item_Code' in current_master_df.columns:
        for code in current_master_df['Item_Code'].dropna():
            code_str = str(code).strip()
            if code_str.startswith(prefix + "-"):
                try:
                    num_part = int(code_str.split("-")[1])
                    if num_part > max_num:
                        max_num = num_part
                except ValueError:
                    pass
                    
    next_num = max_num + 1
    return f"{prefix}-{next_num:03d}"

# กำหนดโครงสร้างตารางข้อมูลออเดอร์
columns_format = ['No (Function)', 'ประเภทงาน', 'จำนวนคน', 'To', 'วันที่รับสินค้า', 'วันที่ใช้สินค้า', 
                 'เมนู', 'วัตถุดิบ', 'ครัวที่รับผิดชอบ', 'จำนวน', 'หน่วย', 'สถานะ']

if 'draft_orders' not in st.session_state:
    st.session_state.draft_orders = pd.DataFrame(columns=columns_format)

if 'logged_in_dept' not in st.session_state:
    st.session_state.logged_in_dept = None

# สร้างตัวแปร Session State สำหรับเก็บค่าในฟอร์ม Main Kitchen
if 'event_type_input' not in st.session_state: st.session_state.event_type_input = ""
if 'no_function_input' not in st.session_state: st.session_state.no_function_input = ""
if 'pax_input' not in st.session_state: st.session_state.pax_input = 70
if 'to_input' not in st.session_state: st.session_state.to_input = ""
if 'receive_date_input' not in st.session_state: st.session_state.receive_date_input = date.today()
if 'use_date_input' not in st.session_state: st.session_state.use_date_input = date.today()

master_df = load_master_recipes()

st.set_page_config(page_title="ระบบสั่งวัตถุดิบครัว", layout="wide")

st.markdown("""
<style>
div.stButton > button[kind="primary"] {
    background-color: #28a745 !important;
    border-color: #28a745 !important;
    color: white !important;
}
div.stButton > button[kind="primary"]:hover {
    background-color: #218838 !important;
    border-color: #1e7e34 !important;
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# ฟังก์ชัน 1: หน้าล็อกอิน (Login Page)
# ==========================================
def login_page():
    st.title("🔐 เข้าสู่ระบบ (Login)")
    st.markdown("กรุณาเลือกแผนกของคุณเพื่อเข้าใช้งานระบบออเดอร์")
    departments = ["Main Kitchen", "Prep", "Butcher", "Bakery", "Admin"]
    selected_dept = st.selectbox("เลือกแผนก (Department):", departments)
    
    if st.button("เข้าสู่ระบบ"):
        st.session_state.logged_in_dept = selected_dept
        st.rerun()

# ==========================================
# ฟังก์ชัน 2: หน้าของครัวเมน (Main Kitchen)
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
    
    if master_df.empty:
        st.warning("⚠️ ยังไม่มีข้อมูลสูตรอาหาร กรุณาไปเพิ่มข้อมูลที่เมนู Admin ก่อนครับ")
        return

    h_col1, h_col2 = st.columns([8, 2])
    with h_col1:
        st.header("📝 1. ข้อมูลรายละเอียดงาน")
    with h_col2:
        st.write("") 
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
        no_function = st.text_input("No (Function):", placeholder="ระบุหมายเลขงาน (เว้นว่างได้)", key="no_function_input")
    with c2:
        pax = st.number_input("จำนวนคน (Pax):", min_value=1, key="pax_input")
        receive_date = st.date_input("1. วันที่รับสินค้า:", key="receive_date_input")
    with c3:
        to_dept = st.text_input("To :", key="to_input")
        use_date = st.date_input("2. วันที่ใช้สินค้า:", key="use_date_input")
        
    st.markdown("---")
    
    st.header("🛒 2. เลือกและจัดเตรียมเมนูอาหาร")
    
    if 'Food_Name' in master_df.columns:
        menu_list = master_df['Food_Name'].dropna().unique()
        selected_menu = st.selectbox("ค้นหาและเลือกเมนูอาหาร:", menu_list)
    else:
        st.error("ไม่พบคอลัมน์ 'Food_Name' ในตารางอ้างอิง")
        selected_menu = None

    edited_prep_df = pd.DataFrame()
    edited_butcher_df = pd.DataFrame()
    edited_bakery_df = pd.DataFrame()
    
    if selected_menu:
        st.markdown(f"**รายการวัตถุดิบสำหรับ: {selected_menu}** *(คลิกที่ช่องตัวเลขเพื่อแก้ไขได้)*")
        recipe_df = master_df[master_df['Food_Name'] == selected_menu].copy()
        
        if 'Std_Quantity' in recipe_df.columns:
            recipe_df['Std_Quantity'] = pd.to_numeric(recipe_df['Std_Quantity'], errors='coerce').fillna(0)
            recipe_df['จำนวน'] = recipe_df['Std_Quantity'] * pax
            
            display_cols = ['Item_Code', 'Item_Description', 'จำนวน', 'Unit']
            display_cols = [col for col in display_cols if col in recipe_df.columns]
            
            col_prep, col_butcher, col_bakery = st.columns(3)
            
            with col_prep:
                st.markdown("#### 🥗 ครัว Prep")
                prep_df = recipe_df[recipe_df['Kitchen_Dept'] == 'ครัว Prep']
                if not prep_df.empty:
                    edited_prep_df = st.data_editor(prep_df[display_cols], use_container_width=True, hide_index=True, disabled=["Item_Code", "Item_Description"], key=f"prep_{selected_menu}")
                else:
                    st.info("ไม่มีรายการ")
                    
            with col_butcher:
                st.markdown("#### 🥩 ครัว บุชเชอร์")
                butcher_df = recipe_df[recipe_df['Kitchen_Dept'] == 'ครัว บุชเชอร์']
                if not butcher_df.empty:
                    edited_butcher_df = st.data_editor(butcher_df[display_cols], use_container_width=True, hide_index=True, disabled=["Item_Code", "Item_Description"], key=f"butcher_{selected_menu}")
                else:
                    st.info("ไม่มีรายการ")

            with col_bakery:
                st.markdown("#### 🍞 ครัว Bakery")
                bakery_df = recipe_df[recipe_df['Kitchen_Dept'] == 'ครัว Bakery']
                if not bakery_df.empty:
                    edited_bakery_df = st.data_editor(bakery_df[display_cols], use_container_width=True, hide_index=True, disabled=["Item_Code", "Item_Description"], key=f"bakery_{selected_menu}")
                else:
                    st.info("ไม่มีรายการ")
        
        if st.button(f"➕ เพิ่ม '{selected_menu}' ลงในรายการสรุป"):
            if event_type == "":
                st.error("กรุณากรอก 'ประเภทงาน' ด้านบนก่อนเพิ่มเมนูครับ")
            else:
                new_drafts = []
                rec_str = receive_date.strftime("%Y-%m-%d") if receive_date else ""
                use_str = use_date.strftime("%Y-%m-%d") if use_date else ""
                
                for df_part, dept_name in [(edited_prep_df, 'ครัว Prep'), (edited_butcher_df, 'ครัว บุชเชอร์'), (edited_bakery_df, 'ครัว Bakery')]:
                    if not df_part.empty:
                        for _, row in df_part.iterrows():
                            new_drafts.append({
                                'No (Function)': no_function, 'ประเภทงาน': event_type, 'จำนวนคน': pax,
                                'To': to_dept, 'วันที่รับสินค้า': rec_str, 'วันที่ใช้สินค้า': use_str, 'เมนู': selected_menu,
                                'วัตถุดิบ': row.get('Item_Description', '-'), 'ครัวที่รับผิดชอบ': dept_name,
                                'จำนวน': row.get('จำนวน', 0), 'หน่วย': row.get('Unit', '-'), 'สถานะ': '🔴 รอรับออเดอร์'
                            })
                
                if new_drafts:
                    draft_df = pd.DataFrame(new_drafts)
                    st.session_state.draft_orders = pd.concat([st.session_state.draft_orders, draft_df], ignore_index=True)
                    st.success(f"เพิ่มเมนู {selected_menu} ลงในรายการสรุปเรียบร้อยแล้ว!")

    st.markdown("---")
    
    # --- ส่วนที่ 3: สรุปและส่ง ---
    st.header("📤 3. สรุปรายการในงานนี้ (รอส่งให้ครัวอื่น)")
    
    if st.session_state.draft_orders.empty:
        st.info("ยังไม่มีเมนูในรายการ กรุณาเลือกเมนูและกดปุ่ม '➕ เพิ่ม...' ด้านบน")
    else:
        sum_c1, sum_c2, sum_c3 = st.columns(3)
        draft_df = st.session_state.draft_orders.copy()
        draft_df['__index__'] = draft_df.index 
        draft_df.insert(0, '❌ ลบ', False) 
        
        summary_display_cols = ['❌ ลบ', 'เมนู', 'วัตถุดิบ', 'จำนวน', 'หน่วย', '__index__']
        edited_prep_sum = pd.DataFrame()
        edited_butcher_sum = pd.DataFrame()
        edited_bakery_sum = pd.DataFrame()
        
        with sum_c1:
            st.markdown("#### 🥗 สรุป: ครัว Prep")
            prep_summary = draft_df[draft_df['ครัวที่รับผิดชอบ'] == 'ครัว Prep']
            if not prep_summary.empty:
                edited_prep_sum = st.data_editor(prep_summary[summary_display_cols], use_container_width=True, hide_index=True, disabled=['เมนู', 'วัตถุดิบ'], column_config={"__index__": None}, key="summary_prep_editor")
                for _, row in edited_prep_sum.iterrows():
                    st.session_state.draft_orders.at[row['__index__'], 'จำนวน'] = row['จำนวน']
                    st.session_state.draft_orders.at[row['__index__'], 'หน่วย'] = row['หน่วย']
            else:
                st.info("ไม่มีรายการ")
                
        with sum_c2:
            st.markdown("#### 🥩 สรุป: บุชเชอร์")
            butcher_summary = draft_df[draft_df['ครัวที่รับผิดชอบ'] == 'ครัว บุชเชอร์']
            if not butcher_summary.empty:
                edited_butcher_sum = st.data_editor(butcher_summary[summary_display_cols], use_container_width=True, hide_index=True, disabled=['เมนู', 'วัตถุดิบ'], column_config={"__index__": None}, key="summary_butcher_editor")
                for _, row in edited_butcher_sum.iterrows():
                    st.session_state.draft_orders.at[row['__index__'], 'จำนวน'] = row['จำนวน']
                    st.session_state.draft_orders.at[row['__index__'], 'หน่วย'] = row['หน่วย']
            else:
                st.info("ไม่มีรายการ")

        with sum_c3:
            st.markdown("#### 🍞 สรุป: Bakery")
            bakery_summary = draft_df[draft_df['ครัวที่รับผิดชอบ'] == 'ครัว Bakery']
            if not bakery_summary.empty:
                edited_bakery_sum = st.data_editor(bakery_summary[summary_display_cols], use_container_width=True, hide_index=True, disabled=['เมนู', 'วัตถุดิบ'], column_config={"__index__": None}, key="summary_bakery_editor")
                for _, row in edited_bakery_sum.iterrows():
                    st.session_state.draft_orders.at[row['__index__'], 'จำนวน'] = row['จำนวน']
                    st.session_state.draft_orders.at[row['__index__'], 'หน่วย'] = row['หน่วย']
            else:
                st.info("ไม่มีรายการ")
        
        st.markdown("<br>", unsafe_allow_html=True)
        c_del, c_submit = st.columns([3, 7])
        
        with c_del:
            if st.button("🗑️ ลบรายการที่เลือก"):
                to_delete_indices = []
                if not edited_prep_sum.empty: to_delete_indices.extend(edited_prep_sum[edited_prep_sum['❌ ลบ'] == True]['__index__'].tolist())
                if not edited_butcher_sum.empty: to_delete_indices.extend(edited_butcher_sum[edited_butcher_sum['❌ ลบ'] == True]['__index__'].tolist())
                if not edited_bakery_sum.empty: to_delete_indices.extend(edited_bakery_sum[edited_bakery_sum['❌ ลบ'] == True]['__index__'].tolist())
                    
                if to_delete_indices:
                    st.session_state.draft_orders = st.session_state.draft_orders.drop(to_delete_indices).reset_index(drop=True)
                    st.rerun()
                else:
                    st.warning("คุณยังไม่ได้ติ๊กเลือกรายการที่ต้องการลบครับ")

        with c_submit:
            if st.button("✅ ยืนยันการส่งออเดอร์ทั้งหมด", type="primary", use_container_width=True):
                with st.spinner('กำลังส่งออเดอร์ขึ้นระบบ...'):
                    for _, row in st.session_state.draft_orders.iterrows():
                        order_data = row.to_dict()
                        order_data['timestamp'] = firestore.SERVER_TIMESTAMP
                        db.collection('orders').add(order_data)
                        
                st.session_state.draft_orders = pd.DataFrame(columns=columns_format)
                st.success("ส่งออเดอร์สำเร็จ!")
                st.rerun() 

    st.markdown("---")
    st.header("📊 ประวัติออเดอร์ที่ส่งไปแล้ว (ทุกงาน)")
    
    all_orders_df = load_orders()
    if not all_orders_df.empty:
        display_df = all_orders_df.drop(columns=['timestamp'], errors='ignore')
        st.dataframe(display_df, use_container_width=True)
    else:
        st.info("ยังไม่มีประวัติการส่งออเดอร์ครับ")

# ==========================================
# ฟังก์ชัน 3: หน้าหลังบ้าน Admin (จัดการสูตรอาหาร)
# ==========================================
def admin_page():
    col1, col2 = st.columns([8, 1])
    with col1:
        st.title("⚙️ ระบบหลังบ้าน: จัดการสูตรอาหาร (Master Recipes)")
    with col2:
        if st.button("🚪 ออกจากระบบ"):
            st.session_state.logged_in_dept = None
            st.rerun()
            
    st.markdown("---")
    
    st.header("➕ เพิ่มสูตรอาหารใหม่ (รองรับหลายวัตถุดิบพร้อมกัน)")
    
    # ฟอร์มหลักสำหรับกรอกชื่อเมนูและเลือกครัว
    with st.form("batch_add_recipe_form"):
        rc1, rc2 = st.columns(2)
        with rc1:
            recipe_code = st.text_input("รหัสสูตร (Recipe Code):", placeholder="เช่น EU001")
            food_name = st.text_input("ชื่อเมนูอาหาร (Food Name):", placeholder="เช่น แกะอบซอสไทม์")
        with rc2:
            kitchen_dept = st.selectbox("ครัวที่รับผิดชอบหลักสำหรับชุดนี้:", ["ครัว Prep", "ครัว บุชเชอร์", "ครัว Bakery"])
            st.write("")
            st.info("💡 เคล็ดลับ: ช่องรหัสวัตถุดิบ (Item Code) ด้านล่างจะถูกสร้างให้อัตโนมัติตามครัวที่คุณเลือกครับ")

        st.markdown("---")
        st.markdown("**📋 ตารางกรอกส่วนผสม/วัตถุดิบ (สามารถพิมพ์เพิ่มได้หลายบรรทัด)**")
        
        # เตรียมตารางเปล่า 10 แถว สำหรับให้ผู้ใช้กรอกวัตถุดิบ
        current_master_for_code = load_master_recipes()
        default_auto_code = generate_next_item_code(kitchen_dept, current_master_for_code)
        
        initial_data = []
        for i in range(10):
            initial_data.append({
                "รหัสวัตถุดิบ (Auto)": "",
                "ชื่อวัตถุดิบ (Description)": "",
                "อัตราส่วนต่อ 1 คน": 0.0,
                "หน่วย": ""
            })
        
        batch_df = pd.DataFrame(initial_data)
        
        # ใช้ data_editor ให้กรอกข้อมูล 10 บรรทัด
        edited_batch_df = st.data_editor(
            batch_df,
            num_rows="dynamic", # อนุญาตให้กดเพิ่มแถวเองได้ถ้า 10 แถวไม่พอ
            use_container_width=True,
            hide_index=True,
            key="batch_recipe_editor"
        )
            
        submitted = st.form_submit_button("💾 บันทึกสูตรอาหารทั้งหมดลง Firebase", type="primary")
        
        if submitted:
            if food_name.strip() == "":
                st.error("กรุณากรอก 'ชื่อเมนูอาหาร' ก่อนบันทึกครับ")
            else:
                # วิ่งลูปสร้างรหัสอัตโนมัติทีละแถวที่ผู้ใช้กรอกเข้ามา
                success_count = 0
                temp_master = load_master_recipes()
                
                for _, row in edited_batch_df.iterrows():
                    desc = str(row["ชื่อวัตถุดิบ (Description)"]).strip()
                    if desc != "" and desc != "nan":
                        # สร้างรหัสอัตโนมัติตามลำดับปัจจุบัน
                        auto_code = generate_next_item_code(kitchen_dept, temp_master)
                        
                        qty = float(row["อัตราส่วนต่อ 1 คน"]) if pd.notna(row["อัตราส่วนต่อ 1 คน"]) else 0.0
                        unit_val = str(row["หน่วย"]).strip() if pd.notna(row["หน่วย"]) else ""
                        
                        new_data = {
                            'Recipe_Code': recipe_code.strip(),
                            'Food_Name': food_name.strip(),
                            'Kitchen_Dept': kitchen_dept,
                            'Item_Code': auto_code,
                            'Item_Description': desc,
                            'Std_Quantity': qty,
                            'Unit': unit_val
                        }
                        db.collection('master_recipes').add(new_data)
                        success_count += 1
                        
                        # อัปเดตตารางชั่วคราวจำลองเพื่อให้รหัสถัดไปไม่ซ้ำกันในรอบถัดไปของลูป
                        new_row_df = pd.DataFrame([new_data])
                        temp_master = pd.concat([temp_master, new_row_df], ignore_index=True)
                
                if success_count > 0:
                    load_master_recipes.clear()
                    st.success(f"บันทึกเมนู '{food_name}' สำเร็จ! เพิ่มวัตถุดิบเข้าระบบทั้งหมด {success_count} รายการ")
                    st.rerun()
                else:
                    st.warning("กรุณากรอกข้อมูลวัตถุดิบอย่างน้อย 1 รายการในตารางครับ")

    st.markdown("---")
    st.header("📋 รายการสูตรอาหารทั้งหมดในฐานข้อมูล (Firebase)")
    
    current_master = load_master_recipes()
    if not current_master.empty:
        display_admin_df = current_master.copy()
        display_admin_df.insert(0, '🗑️ ลบ', False)
        
        cols_to_show = ['🗑️ ลบ', 'Recipe_Code', 'Food_Name', 'Kitchen_Dept', 'Item_Code', 'Item_Description', 'Std_Quantity', 'Unit']
        cols_to_show = [c for c in cols_to_show if c in display_admin_df.columns]
        
        edited_master = st.data_editor(
            display_admin_df[cols_to_show],
            use_container_width=True,
            hide_index=True,
            disabled=['Recipe_Code', 'Food_Name', 'Kitchen_Dept', 'Item_Code', 'Item_Description', 'Std_Quantity', 'Unit'],
            key="admin_master_editor"
        )
        
        if st.button("❌ ลบรายการสูตรอาหารที่เลือก"):
            to_delete_rows = edited_master[edited_master['🗑️ ลบ'] == True]
            if not to_delete_rows.empty:
                count = 0
                for idx, row in to_delete_rows.iterrows():
                    match_doc = current_master[
                        (current_master['Food_Name'] == row['Food_Name']) & 
                        (current_master['Item_Description'] == row['Item_Description'])
                    ]
                    for doc_id in match_doc['doc_id']:
                        db.collection('master_recipes').document(doc_id).delete()
                        count += 1
                
                load_master_recipes.clear()
                st.success(f"ลบรายการออก {count} รายการเรียบร้อยแล้ว!")
                st.rerun()
            else:
                st.warning("กรุณาติ๊กเลือกช่อง '🗑️ ลบ' หน้าวัตถุดิบที่ต้องการลบก่อนครับ")
    else:
        st.info("ยังไม่มีข้อมูลสูตรอาหารในระบบครับ")

# ==========================================
# ฟังก์ชัน 4: หน้าของครัวรับงาน (Prep, Butcher, Bakery)
# ==========================================
def receiver_kitchen_page(dept_name):
    col1, col2 = st.columns([8, 1])
    with col1:
        st.title(f"🔪 หน้าจอรับออเดอร์: {dept_name}")
    with col2:
        if st.button("🚪 ออกจากระบบ"):
            st.session_state.logged_in_dept = None
            st.rerun()
            
    st.markdown("---")
    
    if st.button("🔄 ดึงออเดอร์ล่าสุด"):
        st.rerun()
        
    st.header(f"📥 รายการออเดอร์ที่ต้องเตรียม")
    
    dept_mapping = {
        "Prep": "ครัว Prep",
        "Butcher": "ครัว บุชเชอร์",
        "Bakery": "ครัว Bakery"
    }
    target_dept = dept_mapping.get(dept_name, dept_name)
    
    all_orders = load_orders()
    if not all_orders.empty:
        my_orders = all_orders[all_orders['ครัวที่รับผิดชอบ'] == target_dept]
        
        if my_orders.empty:
            st.info("🎉 ยังไม่มีออเดอร์ของแผนกคุณเข้ามาในขณะนี้ครับ")
        else:
            display_df = my_orders.drop(columns=['timestamp'], errors='ignore')
            st.dataframe(display_df, use_container_width=True)
            st.info("💡 (ในอนาคตเราจะเพิ่มปุ่ม 'กดรับออเดอร์' ตรงนี้ เพื่อให้สถานะเปลี่ยนเป็นสีเขียวครับ)")
    else:
        st.info("🎉 ยังไม่มีออเดอร์เข้ามาในขณะนี้ครับ")

# ==========================================
# ระบบควบคุมเส้นทางหน้าจอ (Router)
# ==========================================
if st.session_state.logged_in_dept is None:
    login_page()
elif st.session_state.logged_in_dept == "Main Kitchen":
    main_kitchen_page()
elif st.session_state.logged_in_dept == "Admin":
    admin_page()
else:
    receiver_kitchen_page(st.session_state.logged_in_dept)
