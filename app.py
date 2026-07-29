import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# Cấu hình trang
st.set_page_config(page_title="POS Bán Hàng Tại Tuyến", layout="wide")

# Hàm khởi tạo kết nối Google Sheets
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

# 1. CẬP NHẬT HÀM LOAD DATA ĐỌC TRỰC TIẾP TỪ GOOGLE SHEETS
def load_data():
    conn = get_connection()
    
    # 1. Khách hàng
    try:
        df_kh = conn.read(worksheet="KhachHang", ttl=0).fillna("")
        df_kh = df_kh.astype(str)
    except Exception as e:
        st.error(f"Lỗi đọc Tab KhachHang: {e}")
        df_kh = pd.DataFrame(columns=['ma_kh', 'ten_kh', 'ten_nguoi_mua', 'ma_so_thue', 'dia_chi'])

    # 2. Hàng hóa
    try:
        df_vt = conn.read(worksheet="HangHoa", ttl=0)
        if 'don_gia' in df_vt.columns:
            df_vt['don_gia'] = pd.to_numeric(df_vt['don_gia'], errors='coerce').fillna(0)
        df_vt = df_vt.fillna("")
        for col in ['ma_vt', 'ten_vt', 'nha_may']:
            if col in df_vt.columns:
                df_vt[col] = df_vt[col].astype(str)
    except Exception as e:
        st.error(f"Lỗi đọc Tab HangHoa: {e}")
        df_vt = pd.DataFrame(columns=['ma_vt', 'ten_vt', 'don_gia', 'nha_may'])

    # 3. Nhân viên
    try:
        df_nv = conn.read(worksheet="NhanVien", ttl=0).fillna("")
        df_nv = df_nv.astype(str)
        if 'pin' not in df_nv.columns:
            df_nv['pin'] = "1234"
    except Exception as e:
        st.error(f"Lỗi đọc Tab NhanVien: {e}")
        df_nv = pd.DataFrame(columns=['ma_nv', 'ten_nv', 'chi_nhanh', 'nha_may', 'pin'])

    return df_kh, df_vt, df_nv

# 2. HÀM UPDATE DATA LÊN GOOGLE SHEETS
def update_sheet(worksheet_name, df_data):
    conn = get_connection()
    try:
        conn.update(worksheet=worksheet_name, data=df_data)
        st.toast(f"Đã đồng bộ {worksheet_name} lên Google Sheets thành công!")
    except Exception as e:
        st.error(f"Lỗi khi lưu {worksheet_name}: {e}")


# --- GIAO DIỆN ỨNG DỤNG ---

# Khai báo Session State cho Đăng nhập
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "current_user" not in st.session_state:
    st.session_state.current_user = None

# Header Navigation
st.title("🛒 POS BÁN HÀNG TẠI TUYẾN")
menu = ["📝 Lập Đơn Hàng", "📊 Báo Cáo Cuối Ngày", "🔑 Xuất MISA", "⚙️ Quản Lý Cấu Hình"]
st.radio("Menu Navigation", menu, horizontal=True, label_visibility="collapsed")

st.divider()

# Đọc dữ liệu từ Google Sheets
df_kh, df_vt, df_nv = load_data()

# PHẦN 1: XÁC THỰC & CHỌN NHÂN VIÊN
st.subheader("1. Xác thực & Chọn Nhân viên")

col1, col2 = st.columns(2)

with col1:
    # Lấy danh sách Chi nhánh từ data nhân viên
    available_branches = list(df_nv['chi_nhanh'].unique()) if not df_nv.empty and 'chi_nhanh' in df_nv.columns else ["Đà Lạt"]
    selected_branch = st.selectbox("Chi nhánh:", options=available_branches)

with col2:
    # Lọc danh sách nhân viên theo Chi nhánh đã chọn
    if not df_nv.empty and 'chi_nhanh' in df_nv.columns and 'ten_nv' in df_nv.columns:
        filtered_nv = df_nv[df_nv['chi_nhanh'] == selected_branch]['ten_nv'].tolist()
    else:
        filtered_nv = []

    if filtered_nv:
        selected_nv_name = st.selectbox("Nhân viên bán hàng:", options=filtered_nv)
    else:
        selected_nv_name = st.selectbox("Nhân viên bán hàng:", options=["Chưa có nhân viên"])

pin_input = st.text_input("🔑 Nhập Mã PIN:", type="password")

# Nút Đăng nhập phiên
if st.button("🔐 Đăng nhập phiên", type="primary", use_container_width=True):
    if selected_nv_name == "Chưa có nhân viên" or not selected_nv_name:
        st.error("Vui lòng chọn nhân viên trước khi đăng nhập!")
    else:
        # Kiểm tra PIN
        user_row = df_nv[(df_nv['ten_nv'] == selected_nv_name) & (df_nv['chi_nhanh'] == selected_branch)]
        if not user_row.empty:
            correct_pin = str(user_row.iloc[0]['pin'])
            if pin_input == correct_pin:
                st.session_state.logged_in = True
                st.session_state.current_user = selected_nv_name
                st.success(f"Đăng nhập thành công! Phiên làm việc của: {selected_nv_name}")
            else:
                st.error("Mã PIN không chính xác. Vui lòng thử lại!")
        else:
            st.error("Không tìm thấy thông tin nhân viên.")

# Cảnh báo
st.warning("⚠️ Vui lòng chọn đúng tên và nhập mã PIN để KHÓA thông tin bán hàng tránh sai báo cáo.")
