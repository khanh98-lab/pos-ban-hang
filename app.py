import streamlit as st
import pandas as pd
from datetime import datetime
import data_helper

# Khởi tạo DB SQLite
data_helper.init_db()

st.set_page_config(page_title="POS Bán Hàng", layout="wide")

# Hàm load dữ liệu từ Google Sheets
@st.cache_data(ttl=60)
def load_data_from_gsheet(sheet_name):
    try:
        gc = data_helper.get_gsheet_client()
        sh = gc.open(data_helper.SPREADSHEET_NAME)
        worksheet = sh.worksheet(sheet_name)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Lỗi tải dữ liệu sheet {sheet_name}: {e}")
        return pd.DataFrame()

# Tải danh mục từ Google Sheets
df_nv = load_data_from_gsheet("NhanVien")
df_vt = load_data_from_gsheet("HangHoa")
df_kh = load_data_from_gsheet("KhachHang")

def format_vnd(amount):
    return f"{int(amount):,} VNĐ".replace(",", ".")

# Quản lý Giỏ hàng trong session_state
if "gio_hang" not in st.session_state:
    st.session_state["gio_hang"] = []

# TABS CHÍNH
tab_pos, tab_baocao, tab_misa, tab_admin = st.tabs([
    "🛒 Ban Hàng (POS)", 
    "📊 Báo Cáo & Sửa Đơn", 
    "📁 Xuất Excel MISA", 
    "🔑 Quản Tri"
])

# ==================== TAB 1: BÁN HÀNG (POS) ====================
with tab_pos:
    st.subheader("🛒 Bán hàng tại quầy")

    col_h1, col_h2 = st.columns(2)
    with col_h1:
        ds_chi_nhanh = ["Chi nhánh 1", "Chi nhánh 2", "Chi nhánh 3"]
        chi_nhanh = st.selectbox("Chi nhánh:", ds_chi_nhanh)
    with col_h2:
        ds_nv = df_nv['ten_nv'].dropna().unique().tolist() if not df_nv.empty else ["Nhân viên A"]
        ten_nv = st.selectbox("Nhân viên bán:", ds_nv)

    st.divider()

    col_kh1, col_kh2 = st.columns(2)
    with col_kh1:
        ds_kh_label = ["Khách lẻ"]
        if not df_kh.empty:
            for idx, row in df_kh.iterrows():
                ds_kh_label.append(f"{row.get('ma_kh', '')} - {row.get('ten_kh', '')}")
        
        select_kh = st.selectbox("Chọn khách hàng:", ds_kh_label)
        
        ma_kh = ""
        ten_kh = "Khách lẻ"
        ten_nguoi_mua = ""
        mst = ""
        dia_chi = ""

        if select_kh != "Khách lẻ":
            ma_kh_sel = select_kh.split(" - ")[0]
            kh_info = df_kh[df_kh['ma_kh'].astype(str) == ma_kh_sel].iloc[0]
            ma_kh = str(kh_info.get('ma_kh', ''))
            ten_kh = str(kh_info.get('ten_kh', ''))
            ten_nguoi_mua = str(kh_info.get('ten_nguoi_mua', ''))
            mst = str(kh_info.get('ma_so_thue', ''))
            dia_chi = str(kh_info.get('dia_chi', ''))

    with col_kh2:
        st.caption(f"📌 **Mã KH:** {ma_kh} | **MST:** {mst}")
        st.caption(f"🏠 **Địa chỉ:** {dia_chi}")

    st.divider()

    # Chọn Hàng hóa
    col_hh1, col_hh2, col_hh3 = st.columns([4, 2, 2])
    with col_hh1:
        ds_vt_label = []
        if not df_vt.empty:
            for idx, row in df_vt.iterrows():
                ds_vt_label.append(f"{row.get('ma_vt', '')} - {row.get('ten_vt', '')}")
        select_vt = st.selectbox("Chọn vật tư/hàng hóa:", ds_vt_label)

    with col_hh2:
        so_luong_input = st.number_input("Số lượng:", min_value=1.0, value=1.0, step=1.0)

    with col_hh3:
        don_gia_default = 0.0
        nha_may_sel = ""
        ma_vt_sel = ""
        ten_vt_sel = ""
        if select_vt and not df_vt.empty:
            m_vt = select_vt.split(" - ")[0]
            vt_info = df_vt[df_vt['ma_vt'].astype(str) == m_vt].iloc[0]
            don_gia_default = float(vt_info.get('don_gia', 0))
            nha_may_sel = str(vt_info.get('nha_may', ''))
            ma_vt_sel = str(vt_info.get('ma_vt', ''))
            ten_vt_sel = str(vt_info.get('ten_vt', ''))

        don_gia_input = st.number_input("Đơn giá (VNĐ):", value=don_gia_default, step=1000.0)

    if st.button("➕ Thêm vào giỏ hàng", type="primary"):
        if ma_vt_sel:
            st.session_state["gio_hang"].append({
                "ma_vt": ma_vt_sel,
                "ten_vt": ten_vt_sel,
                "nha_may": nha_may_sel,
                "so_luong": so_luong_input,
                "don_gia": don_gia_input,
                "thanh_tien": so_luong_input * don_gia_input
            })
            st.success("Đã thêm vào giỏ hàng!")
            st.rerun()

    # Bảng Giỏ hàng
    if st.session_state["gio_hang"]:
        st.markdown("### 🛒 Danh sách sản phẩm đã chọn")
        df_gio = pd.DataFrame(st.session_state["gio_hang"])
        st.dataframe(df_gio[['ma_vt', 'ten_vt', 'nha_may', 'so_luong', 'don_gia', 'thanh_tien']], use_container_width=True)
        
        tong_thanh_tien = df_gio['thanh_tien'].sum()
        st.markdown(f"#### 💰 Tổng thanh toán: :red[{format_vnd(tong_thanh_tien)}]")

        c_tt1, c_tt2 = st.columns(2)
        with c_tt1:
            hinh_thuc_tt = st.selectbox("Hình thức thanh toán:", ["Tiền mặt", "Chuyển khoản", "Ghi nợ", "Hỗn hợp"])
            xuat_hd = st.radio("Xuất hóa đơn:", ["Không", "Có"], horizontal=True)

        with c_tt2:
            tien_tm = 0.0
            tien_ck = 0.0
            tien_no = 0.0
            if hinh_thuc_tt == "Tiền mặt":
                tien_tm = tong_thanh_tien
            elif hinh_thuc_tt == "Chuyển khoản":
                tien_ck = tong_thanh_tien
            elif hinh_thuc_tt == "Ghi nợ":
                tien_no = tong_thanh_tien
            else:
                tien_tm = st.number_input("Tiền mặt:", value=0.0)
                tien_ck = st.number_input("Chuyển khoản:", value=0.0)
                tien_no = tong_thanh_tien - (tien_tm + tien_ck)

        c_btn1, c_btn2 = st.columns(2)
        with c_btn1:
            if st.button("✅ HOÀN TẤT LƯU ĐƠN HÀNG", type="primary", use_container_width=True):
                data_helper.luu_don_hang_danh_sach(
                    chi_nhanh, ten_nv, ma_kh, ten_kh, ten_nguoi_mua, mst, dia_chi,
                    st.session_state["gio_hang"], hinh_thuc_tt, xuat_hd,
                    tien_tm, tien_ck, tien_no
                )
                st.session_state["gio_hang"] = []
                st.balloons()
                st.success("Đã lưu đơn hàng thành công và đồng bộ lên Google Sheets!")
                st.rerun()

        with c_btn2:
            if st.button("🗑️ Hủy giỏ hàng", use_container_width=True):
                st.session_state["gio_hang"] = []
                st.rerun()

# ==================== TAB 2: BÁO CÁO & QUẢN LÝ ĐƠN HÀNG ====================
with tab_baocao:
    st.subheader("📊 Báo cáo & Quản lý đơn hàng trong ngày")
    
    col_bc1, col_bc2, col_bc3 = st.columns(3)
    with col_bc1:
        ngay_bc = st.date_input("Chọn ngày:", datetime.now(), key="dt_ngay_bc")
    with col_bc2:
        cn_bc = st.selectbox("Chi nhánh xem:", options=["Tất cả"] + ds_chi_nhanh, key="sb_cn_bc")
    with col_bc3:
        ds_nv_bc = df_nv['ten_nv'].dropna().unique().tolist() if not df_nv.empty else []
        nv_bc = st.selectbox("Nhân viên xem:", options=["Tất cả"] + ds_nv_bc, key="sb_nv_bc")

    df_bc = data_helper.lay_bao_cao_ngay(str(ngay_bc), cn_bc, nv_bc)

    if not df_bc.empty:
        tong_doanh_thu = df_bc['thanh_tien'].sum()
        df_unique_don = df_bc.groupby('so_don_hang').first().reset_index()
        
        tien_mat = df_unique_don['tien_tm'].sum() if 'tien_tm' in df_unique_don.columns else 0.0
        chuyen_khoan = df_unique_don['tien_ck'].sum() if 'tien_ck' in df_unique_don.columns else 0.0
        ghi_no = df_unique_don['tien_no'].sum() if 'tien_no' in df_unique_don.columns else 0.0

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(f"🔴 **TỔNG DOANH THU**<br><span style='font-size:18px; font-weight:bold; color:#ff4b4b;'>{format_vnd(tong_doanh_thu)}</span>", unsafe_allow_html=True)
        with m2:
            st.markdown(f"💵 **Tiền mặt**<br><span style='font-size:18px; font-weight:bold;'>{format_vnd(tien_mat)}</span>", unsafe_allow_html=True)
        with m3:
            st.markdown(f"🏦 **Chuyển khoản**<br><span style='font-size:18px; font-weight:bold;'>{format_vnd(chuyen_khoan)}</span>", unsafe_allow_html=True)
        with m4:
            st.markdown(f"📝 **Ghi nợ**<br><span style='font-size:18px; font-weight:bold;'>{format_vnd(ghi_no)}</span>", unsafe_allow_html=True)

        st.divider()
        
        df_don_hang = df_bc.groupby('so_don_hang').agg(
            ngay_tao=('ngay_tao', 'first'),
            ten_kh=('ten_kh', 'first'),
            ten_nguoi_mua=('ten_nguoi_mua', 'first'),
            ten_nv=('ten_nv', 'first'),
            tong_tien=('thanh_tien', 'sum'),
            hinh_thuc_tt=('hinh_thuc_tt', 'first'),
            xuat_hd=('xuat_hd', 'first')
        ).reset_index().sort_values(by='ngay_tao', ascending=False)

        with st.expander(f"📄 **Danh sách {len(df_don_hang)} đơn phát sinh trong ngày (Bấm để xem/xóa)**", expanded=False):
            for idx, row in df_don_hang.iterrows():
                so_don = row['so_don_hang']
                
                kh_str = str(row['ten_kh']).strip() if pd.notna(row['ten_kh']) else ""
                nm_str = str(row['ten_nguoi_mua']).strip() if pd.notna(row['ten_nguoi_mua']) else ""
                
                ten_kh_display = kh_str if (kh_str and kh_str.lower() != "****") else (nm_str if nm_str else "Khách lẻ")

                c_info, c_view, c_del = st.columns([6, 1.5, 1.5])
                
                with c_info:
                    st.write(f"🧾 **{so_don}** | KH: **{ten_kh_display}** | NV: {row['ten_nv']} | 💳 **{row['hinh_thuc_tt']}** | Tổng: **{format_vnd(row['tong_tien'])}**")
                    
                with c_view:
                    if st.button("👁️ Xem", key=f"btn_view_{so_don}"):
                        st.session_state["selected_don_hang"] = so_don
                        st.rerun()

                with c_del:
                    if st.button("🗑️ Xóa", key=f"btn_del_{so_don}"):
                        st.session_state["confirm_delete_id"] = so_don
                        st.rerun()

                if st.session_state.get("confirm_delete_id") == so_don:
                    st.warning(f"⚠️ Bạn có chắc chắn muốn xóa đơn **{so_don}** của khách **{ten_kh_display}** không?")
                    col_yes, col_no = st.columns(2)
                    with col_yes:
                        if st.button("❌ CÓ, XÓA NGAY!", key=f"confirm_yes_{so_don}"):
                            data_helper.xoa_don_hang_by_so_don(so_don)
                            st.session_state["confirm_delete_id"] = None
                            if st.session_state.get("selected_don_hang") == so_don:
                                st.session_state["selected_don_hang"] = None
                            st.success(f"Đã xóa thành công đơn {so_don}!")
                            st.rerun()
                    with col_no:
                        if st.button("Hủy bỏ", key=f"confirm_no_{so_don}"):
                            st.session_state["confirm_delete_id"] = None
                            st.rerun()

                st.markdown("---")

        st.divider()

        selected_don = st.session_state.get("selected_don_hang")
        df_selected = df_bc[df_bc['so_don_hang'] == selected_don] if selected_don else pd.DataFrame()

        if selected_don and not df_selected.empty:
            info_don = df_selected.iloc[0]
            kh_str = str(info_don['ten_kh']).strip() if pd.notna(info_don['ten_kh']) else ""
            nm_str = str(info_don['ten_nguoi_mua']).strip() if pd.notna(info_don['ten_nguoi_mua']) else ""
            ten_kh_disp = kh_str if (kh_str and kh_str.lower() != "****") else (nm_str if nm_str else "Khách lẻ")

            st.markdown(f"### 📦 Chi tiết đơn hàng: :red[{selected_don}]")
            st.info(f"👤 Khách hàng: **{ten_kh_disp}** | 💳 Hình thức: **{info_don['hinh_thuc_tt']}** | 📝 NV Bán: **{info_don['ten_nv']}**")
            
            if st.button("🔄 Xem tất cả các đơn trong ngày"):
                st.session_state["selected_don_hang"] = None
                st.rerun()

            is_admin = st.session_state.get("admin_unlocked", False)
            if is_admin:
                st.warning("🔑 **QUYỀN ADMIN (9999):** Bạn có thể sửa trực tiếp Số lượng và Đơn giá dưới bảng bên dưới.")
                df_edit_single = df_selected[['id', 'ten_vt', 'so_luong', 'don_gia', 'thanh_tien']].copy()
                
                edited_df = st.data_editor(
                    df_edit_single,
                    column_config={
                        "id": st.column_config.TextColumn("ID", disabled=True),
                        "ten_vt": st.column_config.TextColumn("Tên mặt hàng", disabled=True),
                        "so_luong": st.column_config.NumberColumn("Số lượng", min_value=1.0, step=1.0, required=True),
                        "don_gia": st.column_config.NumberColumn("Đơn giá", min_value=0.0, step=1000.0, required=True),
                        "thanh_tien": st.column_config.NumberColumn("Thành tiền (Tự tính)", disabled=True)
                    },
                    use_container_width=True,
                    hide_index=True,
                    key=f"editor_don_{selected_don}"
                )

                if st.button("💾 CẬP NHẬT LẠI ĐƠN HÀNG NÀY", type="primary"):
                    for idx_row, row_edit in edited_df.iterrows():
                        r_id = int(row_edit['id'])
                        r_sl = float(row_edit['so_luong'])
                        r_dg = float(row_edit['don_gia'])
                        data_helper.cap_nhat_chi_tiet_don_hang(r_id, r_sl, r_dg)
                    st.success("✅ Đã cập nhật thành công số lượng, đơn giá và thành tiền!")
                    st.rerun()
            else:
                st.caption("🔒 *Đăng nhập Mã Code 9999 ở Tab 4 để mở khóa quyền sửa đơn giá & số lượng.*")
                
            df_display = df_selected
        else:
            st.session_state["selected_don_hang"] = None
            st.markdown("### 📦 Thống kê tổng sản lượng xuất bán trong ngày:")
            df_display = df_bc

        df_group = df_display.groupby('ten_vt').agg(
            Tong_So_Luong=('so_luong', 'sum'),
            Tong_Thanh_Tien=('thanh_tien', 'sum')
        ).reset_index()

        sum_sl = df_group['Tong_So_Luong'].sum()
        sum_tt = df_group['Tong_Thanh_Tien'].sum()

        df_group['Tong_So_Luong'] = df_group['Tong_So_Luong'].apply(lambda x: f"{int(x):,}".replace(",", "."))
        df_group['Tong_Thanh_Tien'] = df_group['Tong_Thanh_Tien'].apply(format_vnd)
        df_group.columns = ['Tên mặt hàng', 'Tổng số lượng xuất', 'Tổng thành tiền']
        
        df_group.index = range(1, len(df_group) + 1)
        df_group.index.name = "STT"

        df_sum_row = pd.DataFrame({
            'Tên mặt hàng': ['🔴 TỔNG CỘNG'],
            'Tổng số lượng xuất': [f"{int(sum_sl):,}".replace(",", ".")],
            'Tổng thành tiền': [format_vnd(sum_tt)]
        }, index=['TỔNG'])

        df_final_show = pd.concat([df_group, df_sum_row])
        st.dataframe(df_final_show, use_container_width=True)

    else:
        st.warning("Chưa có đơn hàng nào phát sinh trong ngày được chọn!")

# ==================== TAB 3: XUẤT EXCEL MISA ====================
with tab_misa:
    st.subheader("📁 Xuất dữ liệu Excel chuẩn MISA")
    
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        ngay_misa = st.date_input("Chọn ngày xuất Excel:", datetime.now(), key="dt_ngay_misa")
    with col_m2:
        cn_misa = st.selectbox("Chọn chi nhánh:", options=["Tất cả"] + ds_chi_nhanh, key="sb_cn_misa")

    if st.button("📥 BẮT ĐẦU XUẤT EXCEL MISA", type="primary"):
        excel_data = data_helper.xuat_excel_misa_chuan(str(ngay_misa), cn_misa)
        if excel_data:
            file_name_out = f"MISA_Export_{str(ngay_misa)}.xlsx"
            st.download_button(
                label="💾 TẢI FILE EXCEL VỀ MÁY",
                data=excel_data,
                file_name=file_name_out,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("Không có dữ liệu đơn hàng trong ngày đã chọn để xuất!")

# ==================== TAB 4: QUẢN TRỊ ADMIN ====================
with tab_admin:
    st.subheader("🔑 Xác thực Quản trị viên (Admin)")
    
    admin_code = st.text_input("Nhập mã PIN Admin:", type="password")
    
    if st.button("Đăng nhập Admin"):
        if admin_code == "9999":
            st.session_state["admin_unlocked"] = True
            st.success("🔑 Mở khóa quyền Admin thành công! Mày có thể sang Tab 2 để sửa Số lượng và Đơn giá.")
        else:
            st.session_state["admin_unlocked"] = False
            st.error("Mã PIN không chính xác!")

    if st.session_state.get("admin_unlocked", False):
        st.success("Trạng thái hiện tại: ĐÃ ĐĂNG NHẬP ADMIN (9999)")
        if st.button("Đăng xuất Admin"):
            st.session_state["admin_unlocked"] = False
            st.rerun()
