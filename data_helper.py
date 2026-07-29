import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import io

def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

def init_db():
    pass

# ================= 1. ĐỌC DỮ LIỆU TỪ GOOGLE SHEETS =================
def load_all_sheets():
    conn = get_connection()
    
    # Đọc Khách Hàng
    try:
        df_kh = conn.read(worksheet="KhachHang", ttl=0).fillna("")
        df_kh = df_kh.astype(str)
    except Exception:
        df_kh = pd.DataFrame(columns=['ma_kh', 'ten_kh', 'ten_nguoi_mua', 'ma_so_thue', 'dia_chi'])

    # Đọc Hàng Hóa
    try:
        df_vt = conn.read(worksheet="HangHoa", ttl=0)
        if 'don_gia' in df_vt.columns:
            df_vt['don_gia'] = pd.to_numeric(df_vt['don_gia'], errors='coerce').fillna(0)
        df_vt = df_vt.fillna("")
        for col in ['ma_vt', 'ten_vt', 'nha_may']:
            if col in df_vt.columns:
                df_vt[col] = df_vt[col].astype(str)
    except Exception:
        df_vt = pd.DataFrame(columns=['ma_vt', 'ten_vt', 'don_gia', 'nha_may'])

    # Đọc Nhân Viên
    try:
        df_nv = conn.read(worksheet="NhanVien", ttl=0).fillna("")
        df_nv = df_nv.astype(str)
        if 'pin' not in df_nv.columns:
            df_nv['pin'] = "1234"
    except Exception:
        df_nv = pd.DataFrame(columns=['ma_nv', 'ten_nv', 'chi_nhanh', 'nha_may', 'pin'])

    return df_kh, df_vt, df_nv

# ================= 2. QUẢN LÝ ĐƠN HÀNG =================
def luu_don_hang_danh_sach(chi_nhanh, ten_nv, ma_kh, ten_kh, ten_nguoi_mua, mst, dia_chi, 
                           danh_sach_hang, hinh_thuc_tt, xuat_hd, tien_tm, tien_ck, tien_no):
    conn = get_connection()
    try:
        df_existing = conn.read(worksheet="DonHang", ttl=0)
    except Exception:
        df_existing = pd.DataFrame()

    so_don_hang = f"DH_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    ngay_tao = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    new_rows = []
    for item in danh_sach_hang:
        new_rows.append({
            'so_don_hang': so_don_hang,
            'ngay_tao': ngay_tao,
            'chi_nhanh': chi_nhanh,
            'ten_nv': ten_nv,
            'ma_kh': ma_kh,
            'ten_kh': ten_kh,
            'ten_nguoi_mua': ten_nguoi_mua,
            'mst': mst,
            'dia_chi': dia_chi,
            'ma_vt': item['ma_vt'],
            'ten_vt': item['ten_vt'],
            'nha_may': item.get('nha_may', ''),
            'so_luong': item['so_luong'],
            'don_gia': item['don_gia'],
            'thanh_tien': item['thanh_tien'],
            'hinh_thuc_tt': hinh_thuc_tt,
            'xuat_hd': xuat_hd,
            'tien_tm': tien_tm,
            'tien_ck': tien_ck,
            'tien_no': tien_no
        })

    df_new = pd.DataFrame(new_rows)
    df_final = pd.concat([df_existing, df_new], ignore_index=True)
    conn.update(worksheet="DonHang", data=df_final)

def lay_bao_cao_ngay(ngay_str, chi_nhanh="Tất cả", ten_nv="Tất cả"):
    conn = get_connection()
    try:
        df = conn.read(worksheet="DonHang", ttl=0)
    except Exception:
        return pd.DataFrame()

    if df.empty or 'ngay_tao' not in df.columns:
        return pd.DataFrame()

    df['ngay_only'] = df['ngay_tao'].astype(str).str.slice(0, 10)
    df_filtered = df[df['ngay_only'] == ngay_str]

    if chi_nhanh != "Tất cả":
        df_filtered = df_filtered[df_filtered['chi_nhanh'] == chi_nhanh]
    if ten_nv != "Tất cả":
        df_filtered = df_filtered[df_filtered['ten_nv'] == ten_nv]

    for col in ['so_luong', 'don_gia', 'thanh_tien', 'tien_tm', 'tien_ck', 'tien_no']:
        if col in df_filtered.columns:
            df_filtered[col] = pd.to_numeric(df_filtered[col], errors='coerce').fillna(0)

    return df_filtered

def xoa_don_hang_by_so_don(so_don_hang):
    conn = get_connection()
    try:
        df = conn.read(worksheet="DonHang", ttl=0)
        if not df.empty and 'so_don_hang' in df.columns:
            df_updated = df[df['so_don_hang'] != so_don_hang]
            conn.update(worksheet="DonHang", data=df_updated)
    except Exception as e:
        st.error(f"Lỗi khi xóa đơn: {e}")

# ================= 3. CẬP NHẬT TAB TỪ ADMIN =================
def update_sheet(worksheet_name, df_data):
    conn = get_connection()
    try:
        conn.update(worksheet=worksheet_name, data=df_data)
        st.toast(f"Đã cập nhật Google Sheet tab '{worksheet_name}'!", icon="✅")
    except Exception as e:
        st.error(f"Lỗi khi cập nhật tab {worksheet_name}: {e}")

# ================= 4. XUẤT MISA EXCEL =================
def xuat_excel_misa_chuan(ngay_str, chi_nhanh="Tất cả"):
    df = lay_bao_cao_ngay(ngay_str, chi_nhanh)
    if df.empty:
        return None
    
    df_misa = pd.DataFrame({
        'Số chứng từ': df['so_don_hang'],
        'Ngày chứng từ': df['ngay_tao'],
        'Mã khách hàng': df['ma_kh'],
        'Tên khách hàng': df['ten_kh'],
        'Mã số thuế': df['mst'],
        'Địa chỉ': df['dia_chi'],
        'Mã hàng': df['ma_vt'],
        'Tên hàng': df['ten_vt'],
        'Số lượng': df['so_luong'],
        'Đơn giá': df['don_gia'],
        'Thành tiền': df['thanh_tien'],
        'Hình thức thanh toán': df['hinh_thuc_tt'],
        'Xuất hóa đơn': df['xuat_hd']
    })

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_misa.to_excel(writer, index=False, sheet_name='Import_MISA')
    return output.getvalue()
