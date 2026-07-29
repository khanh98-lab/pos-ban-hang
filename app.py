import streamlit as st
import pandas as pd
from datetime import datetime
import data_helper

# Cấu hình trang
st.set_page_config(page_title="Hệ Thống Bán Hàng POS", layout="wide", page_icon="📦")

# Khởi tạo DB
data_helper.init_db()

# Hàm format tiền VND
def format_vnd(amount):
    return f"{amount:,.0f}".replace(",", ".")

# Hàm đọc dữ liệu từ Google Sheets
@st.cache_data(ttl=5)
def load_data():
    conn = data_helper.get_connection()
    
    # 1. Khách hàng
    try:
        df_kh = conn.read(worksheet="KhachHang", ttl=0).fillna("")
        df_kh = df_kh.astype(str)
    except Exception:
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
    except Exception:
        df_vt = pd.DataFrame(columns=['ma_vt', 'ten_vt', 'don_gia', 'nha_may'])

    # 3. Nhân viên
    try:
        df_nv = conn.read(worksheet="NhanVien", ttl=0).fillna("")
        df_nv = df_nv.astype(str)
        if 'pin' not in df_nv.columns:
            df_nv['pin'] = "1234"
    except Exception:
        df_nv = pd.DataFrame(columns=['ma_nv', 'ten_nv', 'chi_nhanh', 'nha_may', 'pin'])

    return df_kh, df_vt, df_nv

df_khach_hang, df_hang_hoa, df_nhan_vien = load_data()

# Quản lý giỏ hàng Session
if 'gio_hang' not in st.session_state:
    st.session_state.gio_hang = []

st.title("📦 HỆ THỐNG QUẢN LÝ BÁN HÀNG")

tab1, tab2, tab3 = st.tabs(["🛒 Lập Đơn Hàng", "📊 Báo Cáo Trong Ngày", "⚙️ Quản Lý Dữ Liệu (Admin)"])

# ================= TAB 1: LẬP ĐƠN HÀNG =================
with tab1:
    st.header("Tạo Đơn Hàng Mới")
    
    col_nv1, col_nv2 = st.columns([1, 2])
    with col_nv1:
        pin_input = st.text_input("🔑 Nhập mã PIN Nhân Viên:", type="password")
    
    current_nv = None
    if pin_input:
        nv_match = df_nhan_vien[df_nhan_vien['pin'] == pin_input]
        if not nv_match.empty:
            current_nv = nv_match.iloc[0]
            st.success(f"Xin chào: **{current_nv['ten_nv']}** | Chi nhánh: **{current_nv['chi_nhanh']}**")
        else:
            st.error("Mã PIN không đúng!")

    st.divider()

    col_kh1, col_kh2 = st.columns([1, 1])
    with col_kh1:
        list_kh = df_khach_hang['ten_kh'].tolist() if not df_khach_hang.empty else []
        selected_kh_name = st.selectbox("👤 Chọn Khách hàng:", ["-- Chọn khách hàng --"] + list_kh)
    
    kh_info = {}
    if selected_kh_name != "-- Chọn khách hàng --":
        kh_match = df_khach_hang[df_khach_hang['ten_kh'] == selected_kh_name].iloc[0]
        kh_info = kh_match.to_dict()
        with col_kh2:
            st.info(f"**Mã KH:** {kh_info.get('ma_kh')} | **MST:** {kh_info.get('ma_so_thue')}\n\n**Địa chỉ:** {kh_info.get('dia_chi')}")

    st.subheader("🛍️ Chọn Hàng Hóa")
    col_sp1, col_sp2, col_sp3 = st.columns([2, 1, 1])
    with col_sp1:
        list_vt = df_hang_hoa['ten_vt'].tolist() if not df_hang_hoa.empty else []
        selected_vt_name = st.selectbox("Sản phẩm:", ["-- Chọn sản phẩm --"] + list_vt)
    
    soluong = col_sp2.number_input("Số lượng:", min_value=1, value=100, step=10)
    
    if selected_vt_name != "-- Chọn sản phẩm --":
        vt_match = df_hang_hoa[df_hang_hoa['ten_vt'] == selected_vt_name].iloc[0]
        don_gia_mac_dinh = float(vt_match.get('don_gia', 0))
        don_gia = col_sp3.number_input("Đơn giá (VNĐ):", min_value=0.0, value=don_gia_mac_dinh, step=100.0, format="%.0f")

        if st.button("➕ THÊM VÀO ĐƠN HÀNG"):
            st.session_state.gio_hang.append({
                'ma_vt': vt_match['ma_vt'],
                'ten_vt': vt_match['ten_vt'],
                'nha_may': vt_match.get('nha_may', ''),
                'so_luong': soluong,
                'don_gia': don_gia,
                'thanh_tien': soluong * don_gia
            })
            st.toast("Đã thêm vào giỏ hàng!")

    # Hiển thị Giỏ Hàng
    if st.session_state.gio_hang:
        st.subheader("🛒 Danh Sách Hàng Đã Chọn")
        df_gio = pd.DataFrame(st.session_state.gio_hang)
        st.dataframe(df_gio[['ten_vt', 'so_luong', 'don_gia', 'thanh_tien']], use_container_width=True)
        
        tong_tien = df_gio['thanh_tien'].sum()
        st.markdown(f"### **Tổng Tiền Đơn Hàng:** :green[{format_vnd(tong_tien)} VNĐ]")

        col_tt1, col_tt2, col_tt3 = st.columns(3)
        tien_tm = col_tt1.number_input("Tiền tiền mặt:", min_value=0.0, value=0.0, step=100000.0)
        tien_ck = col_tt2.number_input("Tiền chuyển khoản:", min_value=0.0, value=0.0, step=100000.0)
        tien_no = tong_tien - (tien_tm + tien_ck)
        col_tt3.metric("Tiền Nợ (Còn lại)", f"{format_vnd(tien_no)} VNĐ")

        hinh_thuc_tt = "TM" if tien_ck == 0 else ("CK" if tien_tm == 0 else "TM + CK")
        xuat_hd = st.checkbox("Có xuất hóa đơn VAT")

        if st.button("✅ BẤM LƯU ĐƠN HÀNG NÀY", type="primary"):
            if not current_nv:
                st.error("Vui lòng nhập Mã PIN nhân viên trước khi lưu!")
            elif selected_kh_name == "-- Chọn khách hàng --":
                st.error("Vui lòng chọn khách hàng!")
            else:
                data_helper.luu_don_hang_danh_sach(
                    chi_nhanh=current_nv['chi_nhanh'],
                    ten_nv=current_nv['ten_nv'],
                    ma_kh=kh_info.get('ma_kh', ''),
                    ten_kh=kh_info.get('ten_kh', ''),
                    ten_nguoi_mua=kh_info.get('ten_nguoi_mua', ''),
                    mst=kh_info.get('ma_so_thue', ''),
                    dia_chi=kh_info.get('dia_chi', ''),
                    danh_sach_hang=st.session_state.gio_hang,
                    hinh_thuc_tt=hinh_thuc_tt,
                    xuat_hd="Co" if xuat_hd else "Khong",
                    tien_tm=tien_tm,
                    tien_ck=tien_ck,
                    tien_no=tien_no
                )
                st.success("🎉 Lưu đơn hàng thành công lên Google Sheets!")
                st.session_state.gio_hang = []
                st.cache_data.clear()

# ================= TAB 2: BÁO CÁO TRONG NGÀY =================
with tab2:
    st.header("📊 Báo Cáo Doanh Thu Trong Ngày")
    
    col_f1, col_f2 = st.columns(2)
    ngay_chon = col_f1.date_input("Chọn ngày xem báo cáo:", datetime.now())
    admin_code = col_f2.text_input("🔓 Nhập Mã Admin (Code 9999) để sửa SL & Đơn Giá:", type="password")
    
    is_admin = (admin_code == "9999")

    df_report = data_helper.lay_bao_cao_ngay(ngay_chon.strftime("%Y-%m-%d"))

    if not df_report.empty:
        st.subheader(f"📋 Báo Cáo Đơn Hàng Ngày {ngay_chon.strftime('%d/%m/%Y')}")
        
        if is_admin:
            st.write("🔓 **Chế độ Admin: Cho phép chỉnh sửa Số lượng & Đơn giá trực tiếp**")
            
            df_group = df_report.groupby('ten_vt').agg(
                Tong_So_Luong=('so_luong', 'sum'),
                Don_Gia=('don_gia', 'first')
            ).reset_index()

            df_group['Tong_Thanh_Tien'] = df_group['Tong_So_Luong'] * df_group['Don_Gia']

            edited_df_group = st.data_editor(
                df_group,
                column_config={
                    "ten_vt": st.column_config.TextColumn("Tên mặt hàng", disabled=True),
                    "Tong_So_Luong": st.column_config.NumberColumn("Tổng số lượng xuất (Sửa)", min_value=0, step=1, format="%d"),
                    "Don_Gia": st.column_config.NumberColumn("Đơn Giá (Sửa)", min_value=0, step=1000, format="%.0f"),
                    "Tong_Thanh_Tien": st.column_config.NumberColumn("Tổng thành tiền", disabled=True)
                },
                use_container_width=True,
                hide_index=True,
                key="admin_editor_baocao"
            )
            
            # TỰ ĐỘNG BẮT NHẢY TIỀN KHI ADMIN SỬA SL HOẶC ĐƠN GIÁ
            edited_df_group['Tong_Thanh_Tien'] = edited_df_group['Tong_So_Luong'] * edited_df_group['Don_Gia']
            
            sum_sl = edited_df_group['Tong_So_Luong'].sum()
            sum_tt = edited_df_group['Tong_Thanh_Tien'].sum()

            st.markdown(f"**Tổng sản lượng:** {sum_sl:,.0f} | **Tổng doanh thu sau điều chỉnh:** :red[{format_vnd(sum_tt)} VNĐ]")
        else:
            st.dataframe(df_report[['so_don_hang', 'ten_nv', 'ten_kh', 'ten_vt', 'so_luong', 'don_gia', 'thanh_tien']], use_container_width=True)
    else:
        st.info("Chưa có đơn hàng nào trong ngày được chọn.")

# ================= TAB 3: QUẢN LÝ DỮ LIỆU (ADMIN) =================
with tab3:
    st.header("⚙️ Quản Lý Danh Mục (Lưu trực tiếp lên Google Sheets)")
    
    p_admin = st.text_input("Nhập mật khẩu Admin để quản lý danh mục:", type="password", key="admin_tab3")
    if p_admin == "9999":
        st.success("Đã mở khóa quyền Admin!")
        
        sub_tab1, sub_tab2, sub_tab3 = st.tabs(["👥 Nhân Viên", "📦 Hàng Hóa", "🏢 Khách Hàng"])

        with sub_tab1:
            st.subheader("Danh sách Nhân Viên")
            edited_nv = st.data_editor(df_nhan_vien, num_rows="dynamic", use_container_width=True, key="ed_nv")
            if st.button("💾 Cập nhật Danh Sách Nhân Viên"):
                data_helper.update_sheet("NhanVien", edited_nv)
                st.cache_data.clear()

        with sub_tab2:
            st.subheader("Danh sách Hàng Hóa")
            edited_vt = st.data_editor(df_hang_hoa, num_rows="dynamic", use_container_width=True, key="ed_vt")
            if st.button("💾 Cập nhật Danh Sách Hàng Hóa"):
                data_helper.update_sheet("HangHoa", edited_vt)
                st.cache_data.clear()

        with sub_tab3:
            st.subheader("Danh sách Khách Hàng")
            edited_kh = st.data_editor(df_khach_hang, num_rows="dynamic", use_container_width=True, key="ed_kh")
            if st.button("💾 Cập nhật Danh Sách Khách Hàng"):
                data_helper.update_sheet("KhachHang", edited_kh)
                st.cache_data.clear()
