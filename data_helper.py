import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

def init_db():
    pass # Google Sheets tự quản lý cấu trúc

# ================= 1. XỬ LÝ ĐƠN HÀNG =================
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

# ================= 2. HÀM CẬP NHẬT CHUNG CHO CÁC TAB =================
def update_sheet(worksheet_name, df_data):
    conn = get_connection()
    try:
        conn.update(worksheet=worksheet_name, data=df_data)
        st.toast(f"Đã lưu dữ liệu lên Google Sheet tab '{worksheet_name}' thành công!", icon="✅")
    except Exception as e:
        st.error(f"Lỗi khi cập nhật tab {worksheet_name}: {e}")
