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
# 2. ตั้งค่าหน้าเว็บ & Custom CSS
# ==========================================
st.set_page_config(
    page_title="ระบบสั่งวัตถุดิบห้องครัว",
    page_icon="🍳",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Kanit:wght@300;400;500;600&display=swap');

    html, body, .stApp, p, label, input, select, textarea, button {
        font-family: 'Kanit', sans-serif !important;
    }

    .stApp {
        background-color: #0F172A !important;
        color: #F8FAFC !important;
    }

    .main-title {
        color: #FFFFFF !important;
        font-weight: 600 !important;
        font-size: 2.1rem !important;
        margin-bottom: 0.2rem !important;
    }
    
    .sub-title-text {
        color: #94A3B8 !important;
        font-size: 1rem !important;
        margin-bottom: 1.5rem !important;
    }

    /* ซ่อนไอคอนลูกศรเดิมที่บั๊ก */
    div[data-testid="stExpander"] details summary span[data-testid="stExpanderToggleIcon"] {
        display: none !important;
    }
    div[data-testid="stExpander"] details summary svg {
        display: none !important;
    }

    div[data-testid="stExpander"] {
        background-color: #1E293B !important;
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
        margin-bottom: 10px !important;
    }
    
    div[data-testid="stExpander"] details summary {
        background-color: #1E293B !important;
        color: #F8FAFC !important;
        font-weight: 500 !important;
        padding: 12px 16px !important;
        border-radius: 8px !important;
    }

    div[data-testid="stExpander"] details summary:hover {
        background-color: #2D3748 !important;
    }

    div.stButton > button[kind="primary"] {
        background-color: #059669 !important;
        border-color: #059669 !important;
        color: #FFFFFF !important;
        font-weight: 500 !important;
        border-radius: 8px !important;
    }
    
    div.stButton > button[kind="primary"]:hover {
        background-color: #047857 !important;
    }

    div.stButton > button {
        background-color: #334155 !important;
        border: 1px solid #475569 !important;
        color: #F8FAFC !important;
        border-radius: 8px !important;
    }

    div[data-baseweb="input"] > div, div[data-baseweb="select"] > div, textarea {
        background-color: #1E293B !important;
        color: #F8FAFC !important;
        border-color: #475569 !important;
    }

    label {
        color: #CBD5E1 !important;
    }

    div[data-testid="stDataFrame"] {
        background-color: #1E293B !important;
        border: 1px solid #475569 !important;
        border-radius: 8px !important;
    }

    button[data-baseweb="tab"] {
        color: #94A3B8 !important;
    }

    button[data-baseweb="tab"][aria-selected="true"] {
        color: #38BDF8 !important;
        border-bottom-color: #38BDF8 !important;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. กำหนดโครงสร้างตารางข้อมูล & Session State
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
if 'pax_input' not in st.session_state: st.session_state.pax_input = 0
if 'to_input' not in st.session_state: st.session_state.to_input = ""
if 'receive_date_input' not in st.session_state: st.session_state.receive_date_input = date.today()
if 'use_date_input' not in st.session_state: st.session_state.use_date_input = date.today()

# Cache ข้อมูลป้องกัน Flicker/รีเฟรชบ่อย
if 'cached_master_recipes' not in st.session_state: st.session_state.cached_master_recipes = None
if 'cached_orders' not in st.session_state: st.session_state.cached_orders = None

# ==========================================
# 4. ฟังก์ชันดึงข้อมูล & จัดฟอร์แมต
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

def parse_date_obj(date_val):
    if isinstance(date_val, (date, datetime)):
        return date_val
    try:
        return datetime.strptime(str(date_val), "%d/%m/%Y").date()
    except Exception:
        try:
            return datetime.strptime(str(date_val), "%Y-%m-%d").date()
        except Exception:
            return date.max

def format_qty(val):
    try:
        f_val = float(val)
        return int(f_val) if f_val.is_integer() else f_val
    except (ValueError, TypeError):
        return val

def load_master_recipes(force_reload=False):
    if st.session_state.cached_master_recipes is not None and not force_reload:
        return st.session_state.cached_master_recipes
        
    try:
        docs = db.collection('master_recipes').stream()
        data = []
        for doc in docs:
            d = doc.to_dict()
            d['doc_id'] = doc.id 
            data.append(d)
            
        initial_recipes = [
            {'Recipe_Code': 'EU001', 'Food_Name': 'แกะอบซอสไทม์', 'Kitchen_Dept': 'ครัว บุชเชอร์', 'Item_Code': 'BU-001', 'Item_Description': 'ซี่โครงแกะสไลด์', 'Std_Quantity': 1.0, 'Unit': 'Pc.'},
            {'Recipe_Code': 'EU002', 'Food_Name': 'ไก่กรอบปาปริก้าซอสทาร์ทาร์', 'Kitchen_Dept': 'ครัว บุชเชอร์', 'Item_Code': 'BU-002', 'Item_Description': 'ไก่กรอบปาปริก้า', 'Std_Quantity': 1.0, 'Unit': 'Pc.'},
            {'Recipe_Code': 'EU002', 'Food_Name': 'ไก่กรอบปาปริก้าซอสทาร์ทาร์', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-001', 'Item_Description': 'มายองเนส', 'Std_Quantity': 2.0, 'Unit': 'Pack'},
            {'Recipe_Code': 'EU002', 'Food_Name': 'ไก่กรอบปาปริก้าซอสทาร์ทาร์', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-002', 'Item_Description': 'ครีมสลัด', 'Std_Quantity': 1.0, 'Unit': 'Pack'},
            {'Recipe_Code': 'EU002', 'Food_Name': 'ไก่กรอบปาปริก้าซอสทาร์ทาร์', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-003', 'Item_Description': 'หอมแดง', 'Std_Quantity': 300.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU003', 'Food_Name': 'ไก่พิกกาต้า', 'Kitchen_Dept': 'ครัว บุชเชอร์', 'Item_Code': 'BU-003', 'Item_Description': 'อกไก่', 'Std_Quantity': 1.0, 'Unit': 'Kg.'},
            {'Recipe_Code': 'EU003', 'Food_Name': 'ไก่พิกกาต้า', 'Kitchen_Dept': 'ครัว บุชเชอร์', 'Item_Code': 'BU-004', 'Item_Description': 'แฮมไก่หั่นเส้น', 'Std_Quantity': 300.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU004', 'Food_Name': 'ไก่ย่างยากิโทริเสียบไม้', 'Kitchen_Dept': 'ครัว บุชเชอร์', 'Item_Code': 'BU-005', 'Item_Description': 'ไก่เสียบไม้ยากิโทริ', 'Std_Quantity': 2.0, 'Unit': 'Pc.'},
            {'Recipe_Code': 'EU004', 'Food_Name': 'ไก่ย่างยากิโทริเสียบไม้', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-004', 'Item_Description': 'ต้นหอมซอย', 'Std_Quantity': 200.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU005', 'Food_Name': 'ไก่ทอดเทอริยากิ', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-005', 'Item_Description': 'ต้นหอมซอย', 'Std_Quantity': 300.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU005', 'Food_Name': 'ไก่ทอดเทอริยากิ', 'Kitchen_Dept': 'ครัว บุชเชอร์', 'Item_Code': 'BU-006', 'Item_Description': 'สะโพกไก่เลาะกระดูก', 'Std_Quantity': 8.0, 'Unit': 'Kg'},
            {'Recipe_Code': 'EU006', 'Food_Name': 'หมูอบซอสไวน์หวานลูกพรุน', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-006', 'Item_Description': 'ลูกพรุน', 'Std_Quantity': 500.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU006', 'Food_Name': 'หมูอบซอสไวน์หวานลูกพรุน', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-007', 'Item_Description': 'บร็อคโคลี่ (ผักแต่ง)', 'Std_Quantity': 200.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU006', 'Food_Name': 'หมูอบซอสไวน์หวานลูกพรุน', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-008', 'Item_Description': 'แครอท (ผักแต่ง)', 'Std_Quantity': 200.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU006', 'Food_Name': 'หมูอบซอสไวน์หวานลูกพรุน', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-009', 'Item_Description': 'พาสลี่', 'Std_Quantity': 100.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU006', 'Food_Name': 'หมูอบซอสไวน์หวานลูกพรุน', 'Kitchen_Dept': 'ครัว บุชเชอร์', 'Item_Code': 'BU-007', 'Item_Description': 'หมูสันในยัดไส้ลูกพรุน', 'Std_Quantity': 1.0, 'Unit': 'Kg.'},
            {'Recipe_Code': 'EU007', 'Food_Name': 'สตูว์หมู', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-010', 'Item_Description': 'มันฝรั่งหั่นเต่ากลาง', 'Std_Quantity': 5.0, 'Unit': 'Kg.'},
            {'Recipe_Code': 'EU007', 'Food_Name': 'สตูว์หมู', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-011', 'Item_Description': 'แครอทหั่นเต่ากลาง', 'Std_Quantity': 5.0, 'Unit': 'Kg.'},
            {'Recipe_Code': 'EU007', 'Food_Name': 'สตูว์หมู', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-012', 'Item_Description': 'พริกยักษ์ 3 สีหั่นเต๋ากลาง', 'Std_Quantity': 3.0, 'Unit': 'Kg.'},
            {'Recipe_Code': 'EU007', 'Food_Name': 'สตูว์หมู', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-013', 'Item_Description': 'หอมหัวใหญ่หั่นเต๋าเล็ก', 'Std_Quantity': 200.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU007', 'Food_Name': 'สตูว์หมู', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-009', 'Item_Description': 'พาสลี่', 'Std_Quantity': 200.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU007', 'Food_Name': 'สตูว์หมู', 'Kitchen_Dept': 'ครัว บุชเชอร์', 'Item_Code': 'BU-008', 'Item_Description': 'เนื้อหมูหั่นเต๋าใหญ่', 'Std_Quantity': 7.0, 'Unit': 'Kg.'},
            {'Recipe_Code': 'EU008', 'Food_Name': 'ซี่โครงหมูอบซอสบาร์บิคิว', 'Kitchen_Dept': 'ครัว บุชเชอร์', 'Item_Code': 'BU-009', 'Item_Description': 'ซี่โครงหมูหั่น 1 นิ้ว', 'Std_Quantity': 9.0, 'Unit': 'Kg.'},
            {'Recipe_Code': 'EU008', 'Food_Name': 'ซี่โครงหมูอบซอสบาร์บิคิว', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-020', 'Item_Description': 'ผักซัสเซียน', 'Std_Quantity': 1.0, 'Unit': 'Kg.'},
            {'Recipe_Code': 'EU009', 'Food_Name': 'ไก่อบซอสพริกระฆัง 3 สี', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-014', 'Item_Description': 'พริกยักษ์ 3 สีสไลด์เส้น', 'Std_Quantity': 2.0, 'Unit': 'Kg.'},
            {'Recipe_Code': 'EU009', 'Food_Name': 'ไก่อบซอสพริกระฆัง 3 สี', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-009', 'Item_Description': 'พาสลี่', 'Std_Quantity': 200.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU009', 'Food_Name': 'ไก่อบซอสพริกระฆัง 3 สี', 'Kitchen_Dept': 'ครัว บุชเชอร์', 'Item_Code': 'BU-003', 'Item_Description': 'อกไก่', 'Std_Quantity': 8.0, 'Unit': 'Kg.'},
            {'Recipe_Code': 'EU010', 'Food_Name': 'หมูสันในย่างซอสเห็ดรวม', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-007', 'Item_Description': 'บร็อคโคลี่ (ผักแต่ง)', 'Std_Quantity': 500.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU010', 'Food_Name': 'หมูสันในย่างซอสเห็ดรวม', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-008', 'Item_Description': 'แครอท (ผักแต่ง)', 'Std_Quantity': 500.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU010', 'Food_Name': 'หมูสันในย่างซอสเห็ดรวม', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-009', 'Item_Description': 'พาสลี่', 'Std_Quantity': 200.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU010', 'Food_Name': 'หมูสันในย่างซอสเห็ดรวม', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-015', 'Item_Description': 'เห็ดฝางสไลด์', 'Std_Quantity': 300.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU010', 'Food_Name': 'หมูสันในย่างซอสเห็ดรวม', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-016', 'Item_Description': 'เห็ดหอมสไลด์', 'Std_Quantity': 200.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU010', 'Food_Name': 'หมูสันในย่างซอสเห็ดรวม', 'Kitchen_Dept': 'ครัว บุชเชอร์', 'Item_Code': 'BU-010', 'Item_Description': 'หมูสันในมัดเชือก', 'Std_Quantity': 8.0, 'Unit': 'Kg.'},
            {'Recipe_Code': 'EU011', 'Food_Name': 'ปลากะพงอบซอสเนยมะนาว', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-003', 'Item_Description': 'หอมแดง', 'Std_Quantity': 300.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU011', 'Food_Name': 'ปลากะพงอบซอสเนยมะนาว', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-017', 'Item_Description': 'กระเทียม', 'Std_Quantity': 300.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU011', 'Food_Name': 'ปลากะพงอบซอสเนยมะนาว', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-009', 'Item_Description': 'พาสลี่', 'Std_Quantity': 200.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU011', 'Food_Name': 'ปลากะพงอบซอสเนยมะนาว', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-018', 'Item_Description': 'มะเขือเทศหั่นเต๋าเล็ก', 'Std_Quantity': 400.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU011', 'Food_Name': 'ปลากะพงอบซอสเนยมะนาว', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-019', 'Item_Description': 'เนยจืด', 'Std_Quantity': 1.0, 'Unit': 'Box'},
            {'Recipe_Code': 'EU011', 'Food_Name': 'ปลากะพงอบซอสเนยมะนาว', 'Kitchen_Dept': 'ครัว บุชเชอร์', 'Item_Code': 'BU-011', 'Item_Description': 'ปลากะพงขาวสไลด์', 'Std_Quantity': 8.0, 'Unit': 'Kg.'},
            {'Recipe_Code': 'EU012', 'Food_Name': 'ไก่และเห็ดโวลโอวอง', 'Kitchen_Dept': 'ครัว Bakery', 'Item_Code': 'BA-001', 'Item_Description': 'โวลโอวอง', 'Std_Quantity': 1.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU012', 'Food_Name': 'ไก่และเห็ดโวลโอวอง', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-021', 'Item_Description': 'เห็ดฝางหั่นเต๋าเล็ก', 'Std_Quantity': 5.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU012', 'Food_Name': 'ไก่และเห็ดโวลโอวอง', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-022', 'Item_Description': 'ครีม', 'Std_Quantity': 1.0, 'Unit': 'Box'},
            {'Recipe_Code': 'EU012', 'Food_Name': 'ไก่และเห็ดโวลโอวอง', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-023', 'Item_Description': 'นม', 'Std_Quantity': 0.5, 'Unit': 'แกลอน'},
            {'Recipe_Code': 'EU012', 'Food_Name': 'ไก่และเห็ดโวลโอวอง', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'BU-012', 'Item_Description': 'อกไก่หั่นเต๋าเล็ก', 'Std_Quantity': 50.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU013', 'Food_Name': 'ไก่เสียบไม้ย่างซอส BBQ', 'Kitchen_Dept': 'ครัว บุชเชอร์', 'Item_Code': 'BU-013', 'Item_Description': 'ไก่เสียบไม้', 'Std_Quantity': 1.0, 'Unit': 'ไม้'},
            {'Recipe_Code': 'EU013', 'Food_Name': 'ไก่เสียบไม้ย่างซอส BBQ', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-024', 'Item_Description': 'พริกยักษ์ 3 สี สำหรับเสียบไม้', 'Std_Quantity': 10.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU013', 'Food_Name': 'ไก่เสียบไม้ย่างซอส BBQ', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-025', 'Item_Description': 'หอมหัวใหญ่ สำหรับเสียบไม้', 'Std_Quantity': 10.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU013', 'Food_Name': 'ไก่เสียบไม้ย่างซอส BBQ', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-026', 'Item_Description': 'มะเขือเทศราชินี', 'Std_Quantity': 5.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU014', 'Food_Name': 'ไก่อบซอสไทม์', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-007', 'Item_Description': 'บร็อคโคลี่ (ผักแต่ง)', 'Std_Quantity': 15.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU014', 'Food_Name': 'ไก่อบซอสไทม์', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-008', 'Item_Description': 'แครอท (ผักแต่ง)', 'Std_Quantity': 15.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU014', 'Food_Name': 'ไก่อบซอสไทม์', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-009', 'Item_Description': 'พาสลี่', 'Std_Quantity': 2.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU014', 'Food_Name': 'ไก่อบซอสไทม์', 'Kitchen_Dept': 'ครัว บุชเชอร์', 'Item_Code': 'BU-003', 'Item_Description': 'อกไก่', 'Std_Quantity': 70.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU015', 'Food_Name': 'ไก่อบซอสโรสแมรี่', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-007', 'Item_Description': 'บร็อคโคลี่ (ผักแต่ง)', 'Std_Quantity': 15.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU015', 'Food_Name': 'ไก่อบซอสโรสแมรี่', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-008', 'Item_Description': 'แครอท (ผักแต่ง)', 'Std_Quantity': 15.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU015', 'Food_Name': 'ไก่อบซอสโรสแมรี่', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-009', 'Item_Description': 'พาสลี่', 'Std_Quantity': 2.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU015', 'Food_Name': 'ไก่อบซอสโรสแมรี่', 'Kitchen_Dept': 'ครัว บุชเชอร์', 'Item_Code': 'BU-003', 'Item_Description': 'อกไก่', 'Std_Quantity': 70.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU016', 'Food_Name': 'ไก่อบซอสไวน์ขาว', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-007', 'Item_Description': 'บร็อคโคลี่ (ผักแต่ง)', 'Std_Quantity': 15.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU016', 'Food_Name': 'ไก่อบซอสไวน์ขาว', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-008', 'Item_Description': 'แครอท (ผักแต่ง)', 'Std_Quantity': 15.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU016', 'Food_Name': 'ไก่อบซอสไวน์ขาว', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-009', 'Item_Description': 'พาสลี่', 'Std_Quantity': 2.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU016', 'Food_Name': 'ไก่อบซอสไวน์ขาว', 'Kitchen_Dept': 'ครัว บุชเชอร์', 'Item_Code': 'BU-003', 'Item_Description': 'อกไก่', 'Std_Quantity': 70.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU016', 'Food_Name': 'ไก่อบซอสไวน์ขาว', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-022', 'Item_Description': 'ครีม', 'Std_Quantity': 1.0, 'Unit': 'Box'},
            {'Recipe_Code': 'EU016', 'Food_Name': 'ไก่อบซอสไวน์ขาว', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-023', 'Item_Description': 'นม', 'Std_Quantity': 0.5, 'Unit': 'แกลอน'},
            {'Recipe_Code': 'EU016', 'Food_Name': 'ไก่อบซอสไวน์ขาว', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-003', 'Item_Description': 'หอมแดง', 'Std_Quantity': 300.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU016', 'Food_Name': 'ไก่อบซอสไวน์ขาว', 'Kitchen_Dept': 'ครัว Prep', 'Item_Code': 'PE-017', 'Item_Description': 'กระเทียม', 'Std_Quantity': 300.0, 'Unit': 'g.'},
            {'Recipe_Code': 'EU017', 'Food_Name': 'ขนมปังกระเทียม', 'Kitchen_Dept': 'ครัว Bakery', 'Item_Code': 'BA-002', 'Item_Description': 'ขนมปังเฟรชเบรค', 'Std_Quantity': 1.0, 'Unit': 'แท่ง'}
        ]
        
        existing_foods = set([d.get('Food_Name') for d in data]) if data else set()
        for item in initial_recipes:
            if item['Food_Name'] not in existing_foods:
                db.collection('master_recipes').add(item)
                data.append(item)
                existing_foods.add(item['Food_Name'])
            
        res_df = pd.DataFrame(data)
        st.session_state.cached_master_recipes = res_df
        return res_df
    except Exception as e:
        st.error(f"ไม่สามารถดึงข้อมูลสูตรอาหารได้: {e}")
        return pd.DataFrame()

def load_orders(force_reload=False):
    if st.session_state.cached_orders is not None and not force_reload:
        return st.session_state.cached_orders
        
    try:
        docs = db.collection('orders').stream()
        data = []
        for doc in docs:
            d = doc.to_dict()
            d['doc_id'] = doc.id
            data.append(d)
        res_df = pd.DataFrame(data) if data else pd.DataFrame(columns=columns_format)
        st.session_state.cached_orders = res_df
        return res_df
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
# 5. ฟังก์ชันสร้าง HTML แบบฟอร์ม ISO สำหรับสั่งพิมพ์ (รวมทุกเมนูในงานเดียวกัน)
# ==========================================
def generate_printable_html(draft_df, event_type, pax, to_dept, no_func, rec_date, use_date):
    prep_items = draft_df[draft_df['ครัวที่รับผิดชอบ'].astype(str).str.strip() == 'ครัว Prep'].reset_index(drop=True)
    butcher_items = draft_df[draft_df['ครัวที่รับผิดชอบ'].astype(str).str.strip().isin(['ครัว บุชเชอร์', 'ครัวบุชเชอร์'])].reset_index(drop=True)
    
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
                    display_qty = format_qty(row.get('จำนวน', 0))
                    rows_html += f"""
                    <tr>
                        <td style="text-align:center;">{start_idx + idx + 1}</td>
                        <td style="text-align:center;">{display_qty}</td>
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
            body {{ font-family: 'Sarabun', 'Arial', sans-serif; font-size: 11px; margin: 0; padding: 10px; background-color: #fff; color: #000; }}
            .page-sheet {{ margin-bottom: 20px; }}
            .page-container {{ display: flex; justify-content: space-between; gap: 15px; width: 100%; }}
            .form-box {{ width: 49%; border: 2px solid #000; padding: 6px; box-sizing: border-box; position: relative; }}
            .doc-code-top {{ position: absolute; top: 6px; right: 8px; font-weight: bold; font-size: 10px; }}
            .header-title {{ text-align: center; font-weight: bold; font-size: 12px; text-decoration: underline; margin-bottom: 2px; padding-right: 60px; }}
            .sub-title {{ text-align: center; font-weight: bold; font-size: 11px; margin-bottom: 6px; }}
            .meta-table {{ width: 100%; border-collapse: collapse; margin-bottom: 5px; }}
            .meta-table td {{ padding: 2px 4px; font-size: 10px; border: 1px solid #000; color: #000; }}
            .bg-gray {{ background-color: #d9d9d9; font-weight: bold; }}
            .bg-yellow {{ background-color: #fff2cc; font-weight: bold; }}
            .main-table {{ width: 100%; border-collapse: collapse; margin-bottom: 5px; }}
            .main-table th, .main-table td {{ border: 1px solid #000; padding: 2px 4px; height: 17px; font-size: 10px; color: #000; }}
            .main-table th {{ background-color: #f2f2f2; text-align: center; font-weight: bold; }}
            .footer-table {{ width: 100%; border-collapse: collapse; margin-top: 4px; }}
            .footer-table td {{ padding: 2px; font-size: 10px; font-weight: bold; color: #000; }}
            .doc-version-bottom {{ font-size: 9px; font-weight: bold; margin-top: 2px; }}
            .print-btn {{ background-color: #059669; color: white; border: none; padding: 10px 20px; font-size: 14px; font-weight: bold; cursor: pointer; border-radius: 6px; margin-bottom: 15px; }}
            .print-btn:hover {{ background-color: #047857; }}
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

# ==========================================
# 6. หน้าล็อกอิน (Login Page)
# ==========================================
def login_page():
    st.markdown('<div class="main-title">🔐 เข้าสู่ระบบ (Kitchen Order System)</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title-text">ระบบสื่อสารการสั่งซื้อและจัดเตรียมวัตถุดิบระหว่างห้องครัว</div>', unsafe_allow_html=True)
    
    col_login, _ = st.columns([1, 1])
    with col_login:
        departments = ["Main Kitchen", "Prep", "Butcher", "Bakery", "Admin"]
        selected_dept = st.selectbox("เลือกแผนกปฏิบัติตามสายงาน (Department):", departments)
        if st.button("เข้าสู่ระบบการทำงาน", type="primary", use_container_width=True):
            st.session_state.logged_in_dept = selected_dept
            st.rerun()

# ==========================================
# 7. หน้าของครัวเมน (Main Kitchen)
# ==========================================
def main_kitchen_page():
    col1, col2 = st.columns([8, 2])
    with col1: 
        st.markdown('<div class="main-title">🍳 ครัวเมน (Main Kitchen)</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-title-text">ออกใบสั่งวัตถุดิบ คำนวณปริมาณตาม Pax และส่งงานไปยังครัวรับผิดชอบ</div>', unsafe_allow_html=True)
    with col2:
        if st.button("🚪 ออกจากระบบ", use_container_width=True):
            st.session_state.logged_in_dept = None
            st.rerun()
            
    master_df = load_master_recipes()
    if master_df.empty:
        st.warning("⚠️ ยังไม่มีข้อมูลสูตรอาหาร กรุณาไปเพิ่มข้อมูลที่เมนู Admin ก่อนครับ")
        return

    # --- ส่วนที่ 1: รายละเอียดงาน ---
    h_col1, h_col2 = st.columns([8, 2])
    with h_col1: st.subheader("📝 1. ข้อมูลรายละเอียดงาน")
    with h_col2:
        if st.button("🆕 ขึ้นใบงานใหม่ (Clear Form)", use_container_width=True):
            st.session_state.event_type_input = ""
            st.session_state.no_function_input = ""
            st.session_state.pax_input = 0  # 🟢 ปรับเปลี่ยนค่าเริ่มต้นช่องจำนวนคนเมื่อขึ้นใบงานใหม่เป็น 0
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
        pax = st.number_input("จำนวนคน (Pax):", min_value=0, key="pax_input")
        receive_date = st.date_input("วันที่รับสินค้า:", format="DD/MM/YYYY", key="receive_date_input")
    with c3:
        to_dept = st.text_input("To :", key="to_input")
        use_date = st.date_input("วันที่ใช้สินค้า:", format="DD/MM/YYYY", key="use_date_input")
        
    st.markdown("---")
    
    # --- ส่วนที่ 2: เลือกเมนูอาหาร & สินค้าเพิ่มเติม ---
    st.subheader("🛒 2. เลือกเมนู และ ปริมาณวัตถุดิบ")
    menu_list = master_df['Food_Name'].dropna().unique().tolist() if 'Food_Name' in master_df.columns else []
    
    selected_menu = st.selectbox("ค้นหาและเลือกเมนูอาหาร:", options=menu_list, index=None, placeholder="ค้นหาและเลือกเมนูอาหาร...")

    edited_prep_df, edited_butcher_df = pd.DataFrame(), pd.DataFrame()
    if selected_menu:
        recipe_df = master_df[master_df['Food_Name'] == selected_menu].copy()
        if 'Std_Quantity' in recipe_df.columns:
            recipe_df['Std_Quantity'] = pd.to_numeric(recipe_df['Std_Quantity'], errors='coerce').fillna(0)
            recipe_df['จำนวน'] = recipe_df['Std_Quantity'] * pax
            
            col_prep, col_butcher = st.columns(2)
            with col_prep:
                st.markdown("##### 🥗 ครัว Prep")
                p_df = recipe_df[recipe_df['Kitchen_Dept'].astype(str).str.strip() == 'ครัว Prep'].copy()
                if not p_df.empty: 
                    p_df.insert(0, '❌ ลบ', False)
                    display_cols = ['❌ ลบ', 'Item_Description', 'จำนวน', 'Unit']
                    edited_prep_df = st.data_editor(
                        p_df[display_cols].rename(columns={'Item_Description': 'รายการวัตถุดิบ'}),
                        use_container_width=True, hide_index=True, disabled=["รายการวัตถุดิบ"], key=f"prep_{selected_menu}"
                    )
                else: st.info("ไม่มีรายการส่งครัว Prep")

            with col_butcher:
                st.markdown("##### 🥩 ครัว บุชเชอร์")
                b_df = recipe_df[recipe_df['Kitchen_Dept'].astype(str).str.strip().isin(['ครัว บุชเชอร์', 'ครัวบุชเชอร์'])].copy()
                if not b_df.empty: 
                    b_df.insert(0, '❌ ลบ', False)
                    display_cols = ['❌ ลบ', 'Item_Description', 'จำนวน', 'Unit']
                    edited_butcher_df = st.data_editor(
                        b_df[display_cols].rename(columns={'Item_Description': 'รายการวัตถุดิบ'}),
                        use_container_width=True, hide_index=True, disabled=["รายการวัตถุดิบ"], key=f"butcher_{selected_menu}"
                    )
                else: st.info("ไม่มีรายการส่งครัว บุชเชอร์")

        if st.button(f"➕ เพิ่มเมนู '{selected_menu}' ลงในรายการสรุป", type="primary"):
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
                            if not row.get('❌ ลบ', False):
                                new_drafts.append({
                                    'No (Function)': no_function, 'ประเภทงาน': event_type, 'จำนวนคน': pax,
                                    'To': to_dept, 'วันที่รับสินค้า': rec_str, 'วันที่ใช้สินค้า': use_str, 'เมนู': selected_menu,
                                    'วัตถุดิบ': row.get('รายการวัตถุดิบ', '-'), 'ครัวที่รับผิดชอบ': dept_name,
                                    'จำนวน': row.get('จำนวน', 0), 'หน่วย': row.get('Unit', '-'), 'สถานะ': '🔴 รอรับออเดอร์',
                                    'วันที่สั่ง': now_str, 'หมายเหตุ': '', 'is_printed_prep': False, 'is_printed_butcher': False
                                })
                if new_drafts:
                    st.session_state.draft_orders = pd.concat([st.session_state.draft_orders, pd.DataFrame(new_drafts)], ignore_index=True)
                    st.success(f"เพิ่มเมนู {selected_menu} เรียบร้อย!")
                    st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("➕ กรอกวัตถุดิบเพิ่มเติมพิเศษ (นอกเหนือจากสูตร Recipe)", expanded=False):
        st.info("💡 ใช้ในกรณีต้องการสั่งวัตถุดิบเพิ่มเติมที่ไม่มีในสูตรอาหาร เช่น ผักตกแต่งพิเศษ, ซอสปรุงรสเพิ่มเติม ฯลฯ")
        
        custom_c1, custom_c2, custom_c3, custom_c4 = st.columns([2, 4, 2, 2])
        with custom_c1:
            custom_dept = st.selectbox("ครัวที่รับผิดชอบ:", ["ครัว Prep", "ครัว บุชเชอร์"], key="custom_dept")
        with custom_c2:
            custom_desc = st.text_input("ชื่อวัตถุดิบเพิ่มเติม:", placeholder="เช่น ผักชีฝรั่ง, พริกไทยอ่อน...", key="custom_desc")
        with custom_c3:
            custom_qty = st.number_input("จำนวน:", min_value=0.0, value=1.0, step=0.5, key="custom_qty")
        with custom_c4:
            custom_unit = st.text_input("หน่วย:", placeholder="เช่น กก., แพ็ค, ถุง...", key="custom_unit")
            
        custom_menu_ref = st.text_input("ชื่อเมนู / หมายเหตุอ้างอิง (เว้นว่างได้):", placeholder="เช่น สั่งพิเศษสำหรับไลน์บุฟเฟต์...", key="custom_menu_ref")
        
        if st.button("➕ เพิ่มวัตถุดิบพิเศษลงในออเดอร์"):
            if event_type == "":
                st.error("กรุณากรอก 'ประเภทงาน' ด้านบนก่อนครับ")
            elif custom_desc.strip() == "":
                st.error("กรุณากรอก 'ชื่อวัตถุดิบเพิ่มเติม' ครับ")
            else:
                rec_str = format_date_th(receive_date)
                use_str = format_date_th(use_date)
                tz_th = timezone(timedelta(hours=7))
                now_str = datetime.now(tz_th).strftime("%d/%m/%Y %H:%M")
                menu_text = custom_menu_ref.strip() if custom_menu_ref.strip() != "" else "รายการเพิ่มเติมพิเศษ"
                
                custom_item = {
                    'No (Function)': no_function, 'ประเภทงาน': event_type, 'จำนวนคน': pax,
                    'To': to_dept, 'วันที่รับสินค้า': rec_str, 'วันที่ใช้สินค้า': use_str, 
                    'เมนู': menu_text, 'วัตถุดิบ': custom_desc.strip(), 
                    'ครัวที่รับผิดชอบ': custom_dept, 'จำนวน': custom_qty, 
                    'หน่วย': custom_unit.strip() if custom_unit.strip() != "" else "หน่วย", 
                    'สถานะ': '🔴 รอรับออเดอร์', 'วันที่สั่ง': now_str, 'หมายเหตุ': '', 
                    'is_printed_prep': False, 'is_printed_butcher': False
                }
                
                st.session_state.draft_orders = pd.concat([st.session_state.draft_orders, pd.DataFrame([custom_item])], ignore_index=True)
                st.success(f"เพิ่มวัตถุดิบพิเศษ '{custom_desc}' ({custom_dept}) เรียบร้อยแล้ว!")
                st.rerun()

    # --- ส่วนที่ 3: สรุปรายการ & พิมพ์ตาราง ---
    st.markdown("---")
    st.subheader("📤 3. สรุปรายการวัตถุดิบในงานนี้")
    if st.session_state.draft_orders.empty:
        st.info("ยังไม่มีเมนูในรายการ กรุณาเลือกเมนูและกดปุ่ม '➕ เพิ่ม...' ด้านบน")
    else:
        draft_df = st.session_state.draft_orders.copy()
        draft_df['__index__'] = draft_df.index 
        draft_df.insert(0, '❌ ลบ', False)
        
        sum_c1, sum_c2 = st.columns(2)
        summary_cols = ['❌ ลบ', 'เมนู', 'วัตถุดิบ', 'จำนวน', 'หน่วย', '__index__']
        
        with sum_c1:
            st.markdown("##### 🥗 สรุปส่ง: ครัว Prep")
            p_sum = draft_df[draft_df['ครัวที่รับผิดชอบ'] == 'ครัว Prep']
            if not p_sum.empty:
                e_p = st.data_editor(p_sum[summary_cols], use_container_width=True, hide_index=True, disabled=['เมนู', 'วัตถุดิบ'], column_config={"__index__": None}, key="sum_p")
            else: st.info("ไม่มีรายการส่งครัว Prep")
        with sum_c2:
            st.markdown("##### 🥩 สรุปส่ง: ครัว บุชเชอร์")
            b_sum = draft_df[draft_df['ครัวที่รับผิดชอบ'] == 'ครัว บุชเชอร์']
            if not b_sum.empty:
                e_b = st.data_editor(b_sum[summary_cols], use_container_width=True, hide_index=True, disabled=['เมนู', 'วัตถุดิบ'], column_config={"__index__": None}, key="sum_b")
            else: st.info("ไม่มีรายการส่งครัว บุชเชอร์")

        st.markdown("<br>", unsafe_allow_html=True)
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
            if st.button("✅ ยืนยันการส่งออเดอร์ทั้งหมด", type="primary", use_container_width=True):
                if 'e_p' in locals() and not e_p.empty:
                    for _, r in e_p.iterrows(): st.session_state.draft_orders.at[r['__index__'], 'จำนวน'] = r['จำนวน']
                if 'e_b' in locals() and not e_b.empty:
                    for _, r in e_b.iterrows(): st.session_state.draft_orders.at[r['__index__'], 'จำนวน'] = r['จำนวน']

                for _, row in st.session_state.draft_orders.iterrows():
                    o_data = row.to_dict()
                    o_data['timestamp'] = firestore.SERVER_TIMESTAMP
                    db.collection('orders').add(o_data)
                st.session_state.draft_orders = pd.DataFrame(columns=columns_format)
                load_orders(force_reload=True)
                st.success("ส่งออเดอร์เข้าฐานข้อมูลสำเร็จ!")
                st.rerun()

        st.markdown("---")
        st.subheader("🖨️ พรีวิวแบบฟอร์ม ISO สั่งพิมพ์ (PM38-FM-001)")
        if st.button("🖨️ แสดงแบบฟอร์ม ISO สั่งพิมพ์"):
            st.session_state.show_main_preview = not st.session_state.get("show_main_preview", False)

        if st.session_state.get("show_main_preview", False):
            # 🟢 รวมวัตถุดิบจากทุกเมนูลงในฟอร์ม ISO แผ่นเดียวกัน
            html_view, total_p = generate_printable_html(st.session_state.draft_orders, event_type, pax, to_dept, no_function, receive_date, use_date)
            components.html(html_view, height=750 * total_p, scrolling=True)

    # --- ส่วนที่ 4: ติดตามสถานะออเดอร์ ---
    st.markdown("---")
    st.subheader("📊 ติดตามสถานะออเดอร์")
    
    m_tab1, m_tab2 = st.tabs(["📦 รายการออเดอร์ทั้งหมด", "📜 ประวัติการปรับเปลี่ยนวัตถุดิบจากครัวเตรียม"])
    all_orders_df = load_orders()
    
    with m_tab1:
        if not all_orders_df.empty:
            if 'วันที่สั่ง' not in all_orders_df.columns: all_orders_df['วันที่สั่ง'] = '-'
            if 'หมายเหตุ' not in all_orders_df.columns: all_orders_df['หมายเหตุ'] = ''
                
            unique_jobs = all_orders_df.drop_duplicates(subset=['To', 'ประเภทงาน', 'วันที่สั่ง']).reset_index(drop=True)
            
            # 🟢 เรียงลำดับจาก "วันที่ใช้สินค้า" โดยใกล้วันถึงก่อนอยู่แถวบน
            unique_jobs['parsed_use_date'] = unique_jobs['วันที่ใช้สินค้า'].apply(parse_date_obj)
            unique_jobs = unique_jobs.sort_values(by='parsed_use_date', ascending=True).reset_index(drop=True)
            
            # 🟢 ปรับลบตัวเลขนำหน้าออกจากชื่อหัวข้อตาราง
            h_c1, h_c2, h_c3, h_c4, h_c5, h_c6, h_c7 = st.columns([2.2, 2.5, 2, 1.2, 2, 2, 2])
            h_c1.markdown("**วันที่สั่ง**")
            h_c2.markdown("**ชื่องาน**")
            h_c3.markdown("**ประเภทงาน**")
            h_c4.markdown("**จำนวนคน**")
            h_c5.markdown("**วันที่รับสินค้า**")
            h_c6.markdown("**วันที่ใช้สินค้า**")
            h_c7.markdown("**พิมพ์เอกสาร**")
            st.markdown("<hr style='margin: 5px 0; border-top: 1px solid #334155;'>", unsafe_allow_html=True)

            for idx, job in unique_jobs.iterrows():
                job_to = job.get('To', '-')
                job_no = job.get('No (Function)', '-')
                job_event = job.get('ประเภทงาน', '-')
                job_pax = job.get('จำนวนคน', '-')
                job_rec_date = format_date_th(job.get('วันที่รับสินค้า', '-'))
                job_use_date = format_date_th(job.get('วันที่ใช้สินค้า', '-'))
                job_order_date = job.get('วันที่สั่ง', '-')
                
                job_items = all_orders_df[
                    (all_orders_df['To'] == job_to) & 
                    (all_orders_df['ประเภทงาน'] == job_event) &
                    (all_orders_df['วันที่สั่ง'] == job_order_date)
                ]

                col1, col2, col3, col4, col5, col6, col7 = st.columns([2.2, 2.5, 2, 1.2, 2, 2, 2])
                col1.write(job_order_date)
                col2.write(f"**{job_to}**")
                col3.write(job_event)
                col4.write(str(job_pax))
                col5.write(job_rec_date)
                col6.write(job_use_date)
                
                with col7:
                    if st.button(f"📄 เอกสาร", key=f"btn_print_{idx}", use_container_width=True):
                        st.session_state[f"show_modal_{idx}"] = not st.session_state.get(f"show_modal_{idx}", False)

                remarks_in_job = [str(r).strip() for r in job_items['หมายเหตุ'].dropna().unique() if str(r).strip() != '']
                if remarks_in_job:
                    st.info(f"💬 **หมายเหตุสื่อสาร ({job_to}):** {', '.join(remarks_in_job)}")

                if st.session_state.get(f"show_modal_{idx}", False):
                    with st.expander(f"📄 แบบฟอร์ม ISO สั่งพิมพ์: {job_to} ({job_event})", expanded=True):
                        hist_html, hist_pages = generate_printable_html(
                            job_items, job_event, job_pax, job_to, job_no, job_rec_date, job_use_date
                        )
                        components.html(hist_html, height=750 * hist_pages, scrolling=True)
                st.markdown("<hr style='margin: 5px 0; border-top: 1px dashed #334155;'>", unsafe_allow_html=True)
        else:
            st.info("ยังไม่มีประวัติการสั่งออเดอร์ครับ")

    with m_tab2:
        st.subheader("📜 ประวัติการแก้ไขชื่อ/ปริมาณวัตถุดิบ จากครัวรับงาน")
        logs_df = load_history_logs()
        if not logs_df.empty:
            rename_map = {
                'edit_time': 'เวลาที่แก้ไข',
                'editor_dept': 'ครัวที่แก้ไข',
                'job_to': 'ชื่องาน',
                'orig_desc': 'ชื่อเดิม',
                'new_desc': 'ชื่อใหม่',
                'orig_qty': 'จำนวนเดิม',
                'new_qty': 'จำนวนใหม่',
                'unit': 'หน่วย'
            }
            logs_df = logs_df.rename(columns=rename_map)
            show_cols = [c for c in ['เวลาที่แก้ไข', 'ครัวที่แก้ไข', 'ชื่องาน', 'ชื่อเดิม', 'ชื่อใหม่', 'จำนวนเดิม', 'จำนวนใหม่', 'หน่วย'] if c in logs_df.columns]
            if 'เวลาที่แก้ไข' in logs_df.columns:
                logs_df = logs_df.sort_values(by='เวลาที่แก้ไข', ascending=False)
            st.dataframe(logs_df[show_cols], use_container_width=True, hide_index=True)
        else:
            st.info("ยังไม่มีประวัติการแก้ไขข้อมูลวัตถุดิบจากครัวรับงานครับ")

# ==========================================
# 8. หน้า Admin (จัดการสูตรอาหาร)
# ==========================================
def admin_page():
    col1, col2 = st.columns([8, 2])
    with col1: 
        st.markdown('<div class="main-title">⚙️ ระบบหลังบ้าน: จัดการสูตรอาหาร (Master Recipes)</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-title-text">เพิ่ม แก้ไข หรือลบสูตรอาหารตั้งต้นสำหรับให้ครัวเมนเลือกสั่งซื้อ</div>', unsafe_allow_html=True)
    with col2:
        if st.button("🚪 ออกจากระบบ", use_container_width=True):
            st.session_state.logged_in_dept = None
            st.rerun()
            
    st.markdown("---")
    st.subheader("➕ เพิ่มสูตรอาหารใหม่ (Batch Input)")
    
    with st.form("batch_add_recipe_form"):
        rc1, rc2 = st.columns(2)
        with rc1:
            recipe_code = st.text_input("รหัสสูตร (Recipe Code):", placeholder="เช่น EU001")
        with rc2:
            food_name = st.text_input("ชื่อเมนูอาหาร (Food Name):", placeholder="เช่น แกะอบซอสไทม์")

        batch_df = pd.DataFrame([
            {"ครัวที่รับผิดชอบ": "", "ชื่อวัตถุดิบ (Description)": "", "อัตราส่วนต่อ 1 คน": 0.0, "หน่วย": ""} 
            for _ in range(20)
        ])
        
        edited_batch_df = st.data_editor(
            batch_df, 
            num_rows="dynamic", 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "ครัวที่รับผิดชอบ": st.column_config.SelectboxColumn(
                    "ครัวที่รับผิดชอบ",
                    options=["", "ครัว Prep", "ครัว บุชเชอร์", "ครัว Bakery"],
                    required=False
                )
            }
        )
        
        submitted = st.form_submit_button("💾 บันทึกสูตรอาหารลง Firebase", type="primary")
        
        if submitted:
            if food_name.strip() == "": st.error("กรุณากรอกชื่อเมนูอาหาร")
            else:
                success_count = 0
                temp_master = load_master_recipes(force_reload=True)
                for _, row in edited_batch_df.iterrows():
                    desc = str(row["ชื่อวัตถุดิบ (Description)"]).strip()
                    row_dept = str(row["ครัวที่รับผิดชอบ"]).strip()
                    if desc and desc != "nan":
                        target_dept_val = row_dept if row_dept != "" else "ครัว Prep"
                        auto_code = generate_next_item_code(target_dept_val, temp_master)
                        new_data = {
                            'Recipe_Code': recipe_code.strip(), 'Food_Name': food_name.strip(),
                            'Kitchen_Dept': target_dept_val, 'Item_Code': auto_code,
                            'Item_Description': desc,
                            'Std_Quantity': float(row["อัตราส่วนต่อ 1 คน"]) if pd.notna(row["อัตราส่วนต่อ 1 คน"]) else 0.0,
                            'Unit': str(row["หน่วย"]).strip() if pd.notna(row["หน่วย"]) else ""
                        }
                        db.collection('master_recipes').add(new_data)
                        temp_master = pd.concat([temp_master, pd.DataFrame([new_data])], ignore_index=True)
                        success_count += 1
                if success_count > 0:
                    # 🟢 ล้าง Cache และสั่ง Rerun รีเฟรชหน้าเว็บทันที 1 ที
                    load_master_recipes(force_reload=True)
                    st.success(f"บันทึกเมนู '{food_name}' สำเร็จ {success_count} รายการ!")
                    st.rerun()

    st.markdown("---")
    st.subheader("📋 รายการสูตรอาหารทั้งหมดในระบบ")
    current_master = load_master_recipes()
    if not current_master.empty:
        display_admin_df = current_master.copy()
        display_admin_df.insert(0, '🗑️ ลบ', False)
        cols_to_show = [c for c in ['🗑️ ลบ', 'Recipe_Code', 'Food_Name', 'Kitchen_Dept', 'Item_Code', 'Item_Description', 'Std_Quantity', 'Unit'] if c in display_admin_df.columns]
        edited_master = st.data_editor(display_admin_df[cols_to_show], use_container_width=True, hide_index=True, disabled=['Recipe_Code', 'Food_Name', 'Kitchen_Dept', 'Item_Code', 'Item_Description', 'Std_Quantity', 'Unit'])
        
        if st.button("❌ ลบรายการสูตรอาหารที่เลือก"):
            to_del_rows = edited_master[edited_master['🗑️ ลบ'] == True]
            if not to_del_rows.empty:
                count = 0
                for idx, row in to_del_rows.iterrows():
                    match_doc = current_master[(current_master['Food_Name'] == row['Food_Name']) & (current_master['Item_Description'] == row['Item_Description'])]
                    for doc_id in match_doc['doc_id']:
                        db.collection('master_recipes').document(doc_id).delete()
                        count += 1
                load_master_recipes(force_reload=True)
                st.success(f"ลบรายการสำเร็จ {count} รายการ!")
                st.rerun()

# ==========================================
# 9. หน้าของครัวรับงาน (Prep / Butcher / Bakery)
# ==========================================
def receiver_kitchen_page(dept_name):
    dept_mapping = {"Prep": "ครัว Prep", "Butcher": "ครัว บุชเชอร์", "Bakery": "ครัว Bakery"}
    target_dept = dept_mapping.get(dept_name, dept_name)
    print_field = "is_printed_prep" if target_dept == "ครัว Prep" else "is_printed_butcher"
    
    col1, col2 = st.columns([8, 2])
    with col1: 
        st.markdown(f'<div class="main-title">🔪 หน้าจอจัดการออเดอร์: {target_dept}</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-title-text">รับออเดอร์ แก้ไขจำนวนวัตถุดิบจริง และพิมพ์ใบเบิกตามงาน</div>', unsafe_allow_html=True)
    with col2:
        if st.button("🚪 ออกจากระบบ", use_container_width=True):
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

    tab1, tab2, tab3 = st.tabs(["📦 รายการออเดอร์ตามงาน", "📊 สรุปยอดวัตถุดิบรวมประจำวัน", "📜 ประวัติการแก้ไขออเดอร์"])

    with tab1:
        c_refresh, _ = st.columns([2, 8])
        with c_refresh:
            if st.button("🔄 อัปเดตข้อมูลล่าสุด", use_container_width=True): 
                load_orders(force_reload=True)
                st.rerun()
            
        if 'วันที่สั่ง' not in my_orders.columns: my_orders['วันที่สั่ง'] = '-'
        if 'หมายเหตุ' not in my_orders.columns: my_orders['หมายเหตุ'] = ''
        if print_field not in my_orders.columns: my_orders[print_field] = False
            
        unique_jobs = my_orders.drop_duplicates(subset=['To', 'ประเภทงาน', 'วันที่สั่ง']).reset_index(drop=True)
        
        # 🟢 เรียงลำดับจาก "วันที่ใช้สินค้า" โดยใกล้วันถึงก่อนอยู่แถวบน
        unique_jobs['parsed_use_date'] = unique_jobs['วันที่ใช้สินค้า'].apply(parse_date_obj)
        unique_jobs = unique_jobs.sort_values(by='parsed_use_date', ascending=True).reset_index(drop=True)

        for idx, job in unique_jobs.iterrows():
            job_to = job.get('To', '-')
            job_no = job.get('No (Function)', '-')
            job_event = job.get('ประเภทงาน', '-')
            job_pax = job.get('จำนวนคน', '-')
            job_rec_date = format_date_th(job.get('วันที่รับสินค้า', '-'))
            job_use_date = format_date_th(job.get('วันที่ใช้สินค้า', '-'))
            job_order_date = job.get('วันที่สั่ง', '-')
            
            full_job_items = all_orders[
                (all_orders['To'] == job_to) & 
                (all_orders['ประเภทงาน'] == job_event) &
                (all_orders['วันที่สั่ง'] == job_order_date)
            ].reset_index(drop=True)

            job_items = my_orders[
                (my_orders['To'] == job_to) & 
                (my_orders['ประเภทงาน'] == job_event) &
                (my_orders['วันที่สั่ง'] == job_order_date)
            ].reset_index(drop=True)

            is_job_printed = any(job_items[print_field].fillna(False)) if print_field in job_items.columns else False
            print_status_text = "  🟢 [พิมพ์ใบเบิกแล้ว]" if is_job_printed else "  ⚪ [ยังไม่พิมพ์]"

            header_text = f"📌 งาน: {job_to} | ประเภท: {job_event} | {job_pax} คน | รับ: {job_rec_date} | ใช้: {job_use_date}{print_status_text}"
            
            with st.expander(header_text, expanded=False):
                p_col1, p_col2 = st.columns([3, 7])
                with p_col1:
                    if st.button(f"🖨️ พิมพ์ใบเบิก", key=f"rec_btn_print_{idx}"):
                        st.session_state[f"rec_show_modal_{idx}"] = not st.session_state.get(f"rec_show_modal_{idx}", False)
                with p_col2:
                    st.write("🟢 **สถานะการพิมพ์เบิกแล้ว**" if is_job_printed else "⚪ **ยังไม่ได้พิมพ์ใบเบิก**")

                if st.session_state.get(f"rec_show_modal_{idx}", False):
                    with st.container():
                        st.markdown("---")
                        st.subheader(f"📄 แบบฟอร์ม ISO สำหรับสั่งพิมพ์ (งาน: {job_to})")
                        hist_html, hist_pages = generate_printable_html(
                            full_job_items, job_event, job_pax, job_to, job_no, job_rec_date, job_use_date
                        )
                        components.html(hist_html, height=750 * hist_pages, scrolling=True)
                        if st.button("☑️ ติ๊กเพื่อบันทึกว่าพิมพ์ใบเบิกงานนี้เรียบร้อยแล้ว", key=f"btn_confirm_print_{idx}", type="primary"):
                            for doc_id in job_items['doc_id']:
                                db.collection('orders').document(doc_id).update({print_field: True})
                            load_orders(force_reload=True)
                            st.success("บันทึกสถานะการพิมพ์เรียบร้อยแล้ว!")
                            st.rerun()

                st.markdown("---")
                st.markdown(f"🗓️ **วันที่สั่งออเดอร์:** `{job_order_date}`")
                st.markdown("**✏️ รายการวัตถุดิบ (แก้ไขชื่อและจำนวนได้ที่ตารางนี้):**")
                
                edit_cols = ['วัตถุดิบ', 'จำนวน', 'หน่วย', 'เมนู']
                available_cols = [c for c in edit_cols if c in job_items.columns]
                
                with st.form(key=f"form_job_{idx}"):
                    edited_df = st.data_editor(
                        job_items[available_cols],
                        use_container_width=True,
                        hide_index=True,
                        disabled=['หน่วย', 'เมนู'],
                        key=f"editor_job_{idx}"
                    )
                    btn_save_items = st.form_submit_button("💾 บันทึกการแก้ไขวัตถุดิบ", type="primary")

                if btn_save_items:
                    tz_th = timezone(timedelta(hours=7))
                    now_th = datetime.now(tz_th).strftime("%d/%m/%Y %H:%M")
                    changes_made = 0
                    
                    for i, row in edited_df.iterrows():
                        orig_row = job_items.iloc[i]
                        doc_id = orig_row.get('doc_id')
                        new_desc = str(row['วัตถุดิบ']).strip()
                        new_qty = float(row['จำนวน'])
                        orig_desc = str(orig_row['วัตถุดิบ']).strip()
                        orig_qty = float(orig_row['จำนวน'])
                        
                        if (new_desc != orig_desc) or (new_qty != orig_qty):
                            db.collection('orders').document(doc_id).update({
                                'วัตถุดิบ': new_desc,
                                'จำนวน': new_qty
                            })
                            
                            log_data = {
                                'job_to': job_to,
                                'job_event': job_event,
                                'editor_dept': target_dept,
                                'edit_time': now_th,
                                'orig_desc': orig_desc,
                                'new_desc': new_desc,
                                'orig_qty': orig_qty,
                                'new_qty': new_qty,
                                'unit': orig_row.get('หน่วย', '')
                            }
                            db.collection('order_history_logs').add(log_data)
                            changes_made += 1
                            
                    if changes_made > 0:
                        load_orders(force_reload=True)
                        st.success(f"บันทึกการปรับเปลี่ยนวัตถุดิบสำเร็จ {changes_made} รายการ")
                        st.rerun()
                    else:
                        st.info("ไม่มีการเปลี่ยนแปลงข้อมูลวัตถุดิบ")

                st.markdown("<br>", unsafe_allow_html=True)
                current_remark = ""
                if not job_items.empty and 'หมายเหตุ' in job_items.columns:
                    val = job_items['หมายเหตุ'].iloc[0]
                    current_remark = str(val) if pd.notna(val) else ""

                with st.form(key=f"form_remark_{idx}"):
                    new_remark = st.text_area("💬 หมายเหตุ / ข้อความสื่อสารระหว่างครัว (ส่งถึงครัวเมน):", value=current_remark, placeholder="ระบุข้อความเพิ่มเติมหรือแจ้งปัญหาวัตถุดิบที่นี่...", key=f"remark_{idx}")
                    btn_save_remark = st.form_submit_button("💬 บันทึกหมายเหตุ")
                
                if btn_save_remark:
                    for doc_id in job_items['doc_id']:
                        db.collection('orders').document(doc_id).update({'หมายเหตุ': new_remark.strip()})
                    load_orders(force_reload=True)
                    st.success("บันทึกหมายเหตุสื่อสารเรียบร้อยแล้ว!")
                    st.rerun()

    with tab2:
        st.subheader(f"📊 สรุปยอดรวมวัตถุดิบที่ต้องเตรียม ({target_dept})")
        st.info("💡 หน้านี้จะรวมยอดจำนวนวัตถุดิบชนิดเดียวกันของทุกงานเข้าด้วยกัน เพื่อให้เตรียมของทีเดียวได้สะดวกยิ่งขึ้น")
        
        all_rec_dates = my_orders['วันที่รับสินค้า'].unique().tolist()
        selected_filter_date = st.selectbox("เลือกวันที่รับสินค้า (Delivery Date):", ["ทั้งหมด"] + all_rec_dates)
        
        filtered_orders = my_orders.copy()
        if selected_filter_date != "ทั้งหมด":
            filtered_orders = filtered_orders[filtered_orders['วันที่รับสินค้า'] == selected_filter_date]

        if not filtered_orders.empty:
            summary_grouped = filtered_orders.groupby(['วัตถุดิบ', 'หน่วย'])['จำนวน'].sum().reset_index()
            summary_grouped['จำนวน'] = summary_grouped['จำนวน'].apply(format_qty)
            summary_grouped.columns = ['วัตถุดิบ', 'หน่วย', 'ยอดรวมจำนวนที่ต้องเตรียม']
            st.dataframe(summary_grouped, use_container_width=True, hide_index=True)
        else:
            st.warning("ไม่มีรายการวัตถุดิบตามวันที่เลือก")

    with tab3:
        st.subheader("📜 ประวัติการบันทึกแก้ไขวัตถุดิบ (Audit Log)")
        logs_df = load_history_logs()
        if not logs_df.empty and 'editor_dept' in logs_df.columns:
            dept_logs = logs_df[logs_df['editor_dept'] == target_dept].copy()
            if not dept_logs.empty:
                rename_map = {
                    'edit_time': 'เวลาที่แก้ไข',
                    'job_to': 'ชื่องาน',
                    'orig_desc': 'ชื่อเดิม',
                    'new_desc': 'ชื่อใหม่',
                    'orig_qty': 'จำนวนเดิม',
                    'new_qty': 'จำนวนใหม่',
                    'unit': 'หน่วย'
                }
                dept_logs = dept_logs.rename(columns=rename_map)
                show_cols = [c for c in ['เวลาที่แก้ไข', 'ชื่องาน', 'ชื่อเดิม', 'ชื่อใหม่', 'จำนวนเดิม', 'จำนวนใหม่', 'หน่วย'] if c in dept_logs.columns]
                
                if 'เวลาที่แก้ไข' in dept_logs.columns:
                    dept_logs = dept_logs.sort_values(by='เวลาที่แก้ไข', ascending=False)
                    
                st.dataframe(dept_logs[show_cols], use_container_width=True, hide_index=True)
            else:
                st.info("ยังไม่มีประวัติการแก้ไขข้อมูลวัตถุดิบในครัวนี้")
        else:
            st.info("ยังไม่มีประวัติการแก้ไขข้อมูลวัตถุดิบ")

# ==========================================
# 10. ระบบควบคุมเส้นทางหน้าจอ (Router)
# ==========================================
if st.session_state.logged_in_dept is None: login_page()
elif st.session_state.logged_in_dept == "Main Kitchen": main_kitchen_page()
elif st.session_state.logged_in_dept == "Admin": admin_page()
else: receiver_kitchen_page(st.session_state.logged_in_dept)
