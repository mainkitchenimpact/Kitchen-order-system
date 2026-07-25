import streamlit as st
import pandas as pd
from datetime import date
import firebase_admin
from firebase_admin import credentials, firestore

# --- 1. ตรวจสอบการเชื่อมต่อ Firebase ---
if not firebase_admin._apps:
    key_dict = dict(st.secrets["firebase"])
    if "private_key" in key_dict:
        key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
    cred = credentials.Certificate(key_dict)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# --- 2. ตั้งค่า Initial Session State ---
columns_format = ["Kitchen", "Item", "Quantity", "Unit", "Receive Date", "Notes"]

if "draft_orders" not in st.session_state:
    st.session_state.draft_orders = pd.DataFrame(columns=columns_format)

if 'receive_date_input' not in st.session_state:
    st.session_state.receive_date_input = date.today()

# --- 3. หน้าจอหลัก Main Kitchen Order Form ---
st.title("👨‍🍳 ระบบสั่งซื้อวัตถุดิบ (Main Kitchen)")

# 1. รายชื่อครัวที่เปิดให้สั่งซื้อ (ตัด Bakery ออกแล้ว)
KITCHEN_OPTIONS = [
    "Hot Kitchen",
    "Cold Kitchen",
    "Butchery / Prep",
    "Pastry & Dessert", # ปรับเปลี่ยนตามชื่อครัวที่คุณใช้งานจริงได้เลยครับ
    "General Store / Dry Goods"
]

# 2. ฟอร์มสั่งซื้อสินค้าแบบแพทเทิร์น (Order Form Template)
st.subheader("📝 ฟอร์มสั่งซื้อวัตถุดิบ")

with st.form("order_template_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    
    with col1:
        selected_kitchen = st.selectbox("เลือกครัว/แผนกที่ต้องการสั่ง", KITCHEN_OPTIONS)
        item_name = st.text_input("ชื่อวัตถุดิบ / สินค้า", placeholder="เช่น อกไก่สด, มะเขือเทศ")
        quantity = st.number_input("จำนวน", min_value=0.1, step=0.5, value=1.0)
        
    with col2:
        unit = st.selectbox("หน่วยนับ", ["กก. (kg)", "กรัม (g)", "ลิตร (L)", "มล. (ml)", "แพ็ค (Pack)", "ชิ้น (Pcs)", "กล่อง (Box)"])
        receive_date = st.date_input("วันที่ต้องการรับสินค้า", value=st.session_state.receive_date_input)
        notes = st.text_input("หมายเหตุเพิ่มเติม (ถ้ามี)", placeholder="เช่น ขอสเปกไซส์ใหญ่พิเศษ")

    submit_button = st.form_submit_button("➕ เพิ่มรายการเข้าดราฟต์")

    if submit_button:
        if not item_name.strip():
            st.error("กรุณากรอกชื่อวัตถุดิบก่อนเพิ่มรายการครับ")
        else:
            # เพิ่มรายการใหม่ลง DataFrame ใน Session State
            new_row = {
                "Kitchen": selected_kitchen,
                "Item": item_name,
                "Quantity": quantity,
                "Unit": unit,
                "Receive Date": receive_date.strftime("%Y-%m-%d"),
                "Notes": notes
            }
            st.session_state.draft_orders = pd.concat(
                [st.session_state.draft_orders, pd.DataFrame([new_row])], 
                ignore_index=True
            )
            st.success(f"เพิ่ม '{item_name}' ลงรายการดราฟต์เรียบร้อยแล้ว!")

# --- 4. แสดงรายการสั่งซื้อที่รอการยืนยัน (Draft Orders) ---
st.divider()
st.subheader("🛒 รายการสั่งซื้อรอส่ง (Draft Orders)")

if not st.session_state.draft_orders.empty:
    st.dataframe(st.session_state.draft_orders, use_container_width=True)
    
    col_btn1, col_btn2 = st.columns([1, 4])
    with col_btn1:
        if st.button("🗑️ ล้างดราฟต์ทั้งหมด", type="secondary"):
            st.session_state.draft_orders = pd.DataFrame(columns=columns_format)
            st.rerun()
            
    with col_btn2:
        if st.button("🚀 ยืนยันและส่งใบสั่งซื้อเข้าระบบ (Save to Firestore)", type="primary"):
            try:
                # บันทึกลง Firestore
                order_data = {
                    "created_at": firestore.SERVER_TIMESTAMP,
                    "orders": st.session_state.draft_orders.to_dict(orient="records"),
                    "status": "Pending"
                }
                db.collection("kitchen_orders").add(order_data)
                
                st.success("บันทึกใบสั่งซื้อลงระบบสำเร็จเรียบร้อยแล้ว! 🎉")
                # เคลียร์ดราฟต์
                st.session_state.draft_orders = pd.DataFrame(columns=columns_format)
                st.rerun()
            except Exception as e:
                st.error(f"เกิดข้อผิดพลาดในการบันทึกข้อมูล: {e}")
else:
    st.info("ยังไม่มีรายการวัตถุดิบในดราฟต์ สามารถกรอกฟอร์มด้านบนเพื่อเพิ่มรายการได้เลยครับ")
