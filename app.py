import streamlit as st
import pandas as pd
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import data_helper

# 1. CẤU HÌNH TRANG & ẨN LOGO / MENU TRÁNH ĂN CẮP Ý TƯỞNG
st.set_page_config(page_title="POS Bán Hàng Thuốc Lá", layout="centered")

hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            [data-testid="stStatusWidget"] {visibility: hidden;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

data_helper.init_db()

# Hàm kết nối Google Sheets bảo mật từ Streamlit Secrets
def get_gsheet_client():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        return gspread.authorize(creds)
    except Exception as e:
        return None

# Hàm định dạng dấu chấm phân cách hàng ngàn
def format_vnd(amount):
    try:
        val = int(round(float(amount)))
        return f"{val:,}".replace(",", ".")
    except Exception:
        return "0"

# Hàm parse chuỗi có dấu chấm ngược lại thành số nguyên/thực
def parse_formatted_num(val_str):
    try:
        clean_str = str(val_str).replace(".", "").replace(",", "").strip()
        return float(clean_str)
    except Exception:
        return 0.0

# TRA CỨU MÃ SỐ THUẾ
def tra_cuu_mst_toi_uu(mst):
    mst = str(mst).strip().replace(" ", "").replace("-", "")
    if not mst:
        return None, None, "Vui lòng nhập Mã Số Thuế!"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    }

    try:
        url_vietqr = f"https://api.vietqr.io/v2/business/{mst}"
        r_vqr = requests.get(url_vietqr, headers=headers, timeout=5)
        if r_vqr.status_code == 200:
            d_vqr = r_vqr.json()
            if d_vqr.get("code") == "00" and d_vqr.get("data"):
                data = d_vqr["data"]
                ten = data.get("name", "")
                dia_chi = data.get("address", "")
                if ten:
                    return ten, dia_chi, "Thành công"
    except Exception:
        pass

    try:
        url_scrape = f"https://masothue.com/{mst}/"
        res = requests.get(url_scrape, headers=headers, timeout=5)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            ten_cty = ""
            h1_tag = soup.find('h1', class_='title-head') or soup.find('th', class_='table-title')
            if h1_tag:
                ten_cty = h1_tag.get_text(strip=True)

            dia_chi = ""
            td_address = soup.find('td', itemprop='address')
            if td_address:
                dia_chi = td_address.get_text(strip=True)
            else:
                for tr in soup.find_all('tr'):
                    if 'Địa chỉ' in tr.get_text():
                        tds = tr.find_all('td')
                        if len(tds) > 1:
                            dia_chi = tds[1].get_text(strip=True)
                            break

            if ten_cty:
                return ten_cty, dia_chi, "Thành công"
    except Exception:
        pass

    return None, None, "Không tìm thấy Mã số thuế này!"

def load_data():
    try:
        df_kh = pd.read_csv('data/khach_hang.csv', dtype=str).fillna("")
    except Exception:
        df_kh = pd.DataFrame(columns=['ma_kh', 'ten_kh', 'ten_nguoi_mua', 'ma_so_thue', 'dia_chi'])
        
    try:
        df_vt = pd.read_csv('data/hang_hoa.csv', dtype={'ma_vt': str, 'ten_vt': str, 'nha_may': str})
        if 'don_gia' in df_vt.columns:
            df_vt['don_gia'] = pd.to_numeric(df_vt['don_gia'], errors='coerce').fillna(0)
        df_vt = df_vt.fillna("")
        cols_needed = [c for c in ['ma_vt', 'ten_vt', 'don_gia', 'nha_may'] if c in df_vt.columns]
        df_vt = df_vt[cols_needed]
    except Exception:
        df_vt = pd.DataFrame(columns=['ma_vt', 'ten_vt', 'don_gia', 'nha_may'])
        
    try:
        df_nv = pd.read_csv('data/nhan_vien.csv', dtype=str).fillna("")
        if 'pin' not in df_nv.columns:
            df_nv['pin'] = "1234"
            df_nv.to_csv('data/nhan_vien.csv', index=False, encoding='utf-8')
    except Exception:
        df_nv = pd.DataFrame(columns=['ma_nv', 'ten_nv', 'chi_nhanh', 'nha_may', 'pin'])
        
    return df_kh, df_vt, df_nv

df_kh, df_vt, df_nv = load_data()

raw_nha_may = ["Khatoco", "BAT", "Marlboro", "Miền Nam", "Sài Gòn", "Thăng Long"]
if not df_vt.empty and 'nha_may' in df_vt.columns:
    raw_nha_may.extend(df_vt['nha_may'].dropna().unique().tolist())
if not df_nv.empty and 'nha_may' in df_nv.columns:
    raw_nha_may.extend(df_nv['nha_may'].dropna().unique().tolist())

ds_nha_may_goc = sorted(list(set([x for x in raw_nha_may if x != "Tất cả" and str(x).strip() != ""])))

# State hệ thống
if "gio_hang" not in st.session_state: st.session_state["gio_hang"] = []
if "selected_don_hang" not in st.session_state: st.session_state["selected_don_hang"] = None
if "confirm_delete_id" not in st.session_state: st.session_state["confirm_delete_id"] = None
if "admin_unlocked" not in st.session_state: st.session_state["admin_unlocked"] = False
if "is_nv_logged_in" not in st.session_state: st.session_state["is_nv_logged_in"] = False
if "logged_nv_info" not in st.session_state: st.session_state["logged_nv_info"] = {}

# State Khách Hàng Mới
if "txt_mst_moi" not in st.session_state: st.session_state["txt_mst_moi"] = ""
if "txt_ten_kh_moi" not in st.session_state: st.session_state["txt_ten_kh_moi"] = ""
if "txt_nguoi_mua_moi" not in st.session_state: st.session_state["txt_nguoi_mua_moi"] = ""
if "txt_dia_chi_moi" not in st.session_state: st.session_state["txt_dia_chi_moi"] = ""

# State Widget Khách Hàng Cũ
if "txt_nguoi_mua_cu" not in st.session_state: st.session_state["txt_nguoi_mua_cu"] = ""
if "txt_dia_chi_cu" not in st.session_state: st.session_state["txt_dia_chi_cu"] = ""

def cb_on_change_khach_cu():
    ten_kh_sel = st.session_state.get("sb_khach_cu")
    if ten_kh_sel and not df_kh.empty:
        dict_kh = dict(zip(df_kh['ten_kh'], df_kh['ma_kh']))
        if ten_kh_sel in dict_kh:
            ma_kh = dict_kh[ten_kh_sel]
            rows = df_kh[df_kh['ma_kh'] == ma_kh]
            if not rows.empty:
                row_kh = rows.iloc[0]
                nm = str(row_kh.get('ten_nguoi_mua', '')) if pd.notna(row_kh.get('ten_nguoi_mua')) else ''
                dc = str(row_kh.get('dia_chi', '')) if pd.notna(row_kh.get('dia_chi')) else ''
                st.session_state["txt_nguoi_mua_cu"] = nm
                st.session_state["txt_dia_chi_cu"] = dc
                return
    st.session_state["txt_nguoi_mua_cu"] = ""
    st.session_state["txt_dia_chi_cu"] = ""

def cb_luu_khach_moi():
    ten_kh = st.session_state.get("txt_ten_kh_moi", "").strip()
    ten_nm = st.session_state.get("txt_nguoi_mua_moi", "").strip()
    mst = str(st.session_state.get("txt_mst_moi", "")).strip()
    dia_chi = st.session_state.get("txt_dia_chi_moi", "").strip()

    ten_hien_thi = ten_kh if ten_kh else (ten_nm if ten_nm else "Khách lẻ")
    
    global df_kh
    new_ma_kh = f"KH{len(df_kh) + 1:03d}"
    
    new_row = pd.DataFrame([{
        'ma_kh': new_ma_kh,
        'ten_kh': ten_hien_thi,
        'ten_nguoi_mua': ten_nm,
        'ma_so_thue': mst,
        'dia_chi': dia_chi
    }])
    df_kh = pd.concat([df_kh, new_row], ignore_index=True)
    df_kh.to_csv('data/khach_hang.csv', index=False, encoding='utf-8')
    
    st.session_state["txt_mst_moi"] = ""
    st.session_state["txt_ten_kh_moi"] = ""
    st.session_state["txt_nguoi_mua_moi"] = ""
    st.session_state["txt_dia_chi_moi"] = ""
    st.session_state["msg_kh_success"] = f"Đã lưu thành công khách hàng: **{ten_hien_thi}**!"

st.title("🛒 POS BÁN HÀNG TẠI TUYẾN")

tab_pos, tab_baocao, tab_misa, tab_admin = st.tabs([
    "📝 Lập Đơn Hàng", 
    "📊 Báo Cáo Cuối Ngày", 
    "🔑 Xuất MISA", 
    "⚙️ Quản Lý Cấu Hình"
])

# ==================== TAB 1: LẬP ĐƠN HÀNG ====================
with tab_pos:
    st.subheader("1. Xác thực & Chọn Nhân viên")
    ds_chi_nhanh = list(set(["Đà Lạt", "Đức Trọng"] + (df_nv['chi_nhanh'].dropna().unique().tolist() if not df_nv.empty else [])))
    is_logged = st.session_state["is_nv_logged_in"]

    if not is_logged:
        col_cn, col_nv = st.columns(2)
        with col_cn:
            chi_nhanh_chon = st.selectbox("Chi nhánh:", options=ds_chi_nhanh, key="sb_chi_nhanh")

        if not df_nv.empty and 'chi_nhanh' in df_nv.columns:
            df_nv_filtered = df_nv[df_nv['chi_nhanh'].astype(str).str.strip() == chi_nhanh_chon.strip()]
            ds_nv = df_nv_filtered['ten_nv'].dropna().tolist()
        else:
            df_nv_filtered = pd.DataFrame()
            ds_nv = []

        if not ds_nv:
            ds_nv = ["Chưa có nhân viên"]

        with col_nv:
            ten_nv_chon = st.selectbox("Nhân viên bán hàng:", options=ds_nv, key="sb_nhan_vien")

        col_pin, col_btn_login = st.columns([2, 1])
        with col_pin:
            pin_input = st.text_input("🔑 Nhập Mã PIN:", type="password", key="input_nv_pin")
        with col_btn_login:
            st.write("")
            st.write("")
            if st.button("🔓 Đăng nhập phiên", use_container_width=True, type="primary"):
                if not df_nv_filtered.empty and ten_nv_chon in df_nv_filtered['ten_nv'].values:
                    row_nv = df_nv_filtered[df_nv_filtered['ten_nv'] == ten_nv_chon].iloc[0]
                    correct_pin = str(row_nv.get('pin', '1234')).strip()
                    
                    if pin_input.strip() == correct_pin:
                        st.session_state["is_nv_logged_in"] = True
                        st.session_state["logged_nv_info"] = {
                            "ten_nv": ten_nv_chon,
                            "chi_nhanh": chi_nhanh_chon,
                            "nha_may": row_nv.get('nha_may', 'Tất cả')
                        }
                        st.success(f"Xin chào {ten_nv_chon}, phiên bán hàng đã được KHÓA!")
                        st.rerun()
                    else:
                        st.error("❌ Mã PIN không chính xác!")
                else:
                    st.warning("Vui lòng chọn nhân viên hợp lệ!")

        st.warning("⚠️ Vui lòng chọn đúng tên và nhập mã PIN để KHÓA thông tin bán hàng tránh sai báo cáo.")

    else:
        info = st.session_state["logged_nv_info"]
        chi_nhanh_chon = info["chi_nhanh"]
        ten_nv_chon = info["ten_nv"]
        nha_may_nv = info["nha_may"]

        col_cn, col_nv = st.columns(2)
        with col_cn:
            st.selectbox("Chi nhánh:", options=[chi_nhanh_chon], disabled=True, key="sb_chi_nhanh_dis")
        with col_nv:
            st.selectbox("Nhân viên bán hàng:", options=[ten_nv_chon], disabled=True, key="sb_nhan_vien_dis")

        col_info_txt, col_logout = st.columns([3, 1])
        with col_info_txt:
            st.caption(f"🔒 Phiên làm việc của NV **{ten_nv_chon}** | Phụ trách: **{nha_may_nv}**")
        with col_logout:
            if st.button("🔒 Đăng xuất / Đổi NV", use_container_width=True):
                st.session_state["is_nv_logged_in"] = False
                st.session_state["logged_nv_info"] = {}
                st.rerun()

    st.divider()
    st.subheader("2. Thông tin Khách hàng")
    tab_kh1, tab_kh2 = st.tabs(["📋 Chọn Khách Có Sẵn", "➕ Nhập Khách Mới"])
    
    ten_kh_selected = ""
    ten_nguoi_mua_selected = ""
    mst_selected = ""
    dia_chi_selected = ""
    ma_kh_selected = "KH_LE"

    with tab_kh1:
        if not df_kh.empty:
            dict_kh = dict(zip(df_kh['ten_kh'], df_kh['ma_kh']))
            options_kh = list(dict_kh.keys())
            
            ten_kh_selected = st.selectbox(
                "Chọn Công ty / Hộ kinh doanh:", 
                options=options_kh, 
                index=None, 
                placeholder="Chọn công ty / hộ kinh doanh...",
                key="sb_khach_cu",
                on_change=cb_on_change_khach_cu
            )
            
            ten_nguoi_mua_selected = st.text_input("Tên người mua hàng:", key="txt_nguoi_mua_cu")
            dia_chi_selected = st.text_input("Địa chỉ khách hàng:", key="txt_dia_chi_cu")

            if ten_kh_selected and ten_kh_selected in dict_kh:
                ma_kh_selected = dict_kh[ten_kh_selected]
                rows = df_kh[df_kh['ma_kh'] == ma_kh_selected]
                if not rows.empty:
                    row_kh = rows.iloc[0]
                    mst_selected = str(row_kh.get('ma_so_thue', '')).replace('.0', '') if pd.notna(row_kh.get('ma_so_thue')) else ''
            else:
                ma_kh_selected = "KH_LE"
                ten_kh_selected = ""
                mst_selected = ""
        else:
            st.info("Chưa có danh sách khách cũ.")

    with tab_kh2:
        col_mst1, col_mst2 = st.columns([3, 1])
        with col_mst1:
            mst_input = st.text_input("Mã Số Thuế:", key="txt_mst_moi")
        with col_mst2:
            st.write("")
            st.write("")
            btn_tracuu = st.button("🔍 Tra cứu", key="btn_tracuu_mst", use_container_width=True)

        if btn_tracuu:
            if mst_input:
                with st.spinner("Đang tra cứu từ VietQR / Masothue..."):
                    ten_cq, dia_chi_cq, msg = tra_cuu_mst_toi_uu(mst_input)
                    if ten_cq:
                        st.session_state["txt_ten_kh_moi"] = ten_cq
                        st.session_state["txt_dia_chi_moi"] = dia_chi_cq
                        st.success("Tra cứu thành công!")
                        st.rerun()
                    else:
                        st.error(msg)
            else:
                st.warning("Vui lòng nhập MST trước khi tra cứu!")

        ten_kh_moi = st.text_input("Tên Cty / Hộ kinh doanh:", key="txt_ten_kh_moi")
        ten_nguoi_mua_moi = st.text_input("Tên người mua hàng:", key="txt_nguoi_mua_moi")
        dia_chi_moi = st.text_input("Địa chỉ:", key="txt_dia_chi_moi")

        st.button("💾 Lưu Khách Mới Này", key="btn_luu_kh_moi", type="primary", use_container_width=True, on_click=cb_luu_khach_moi)

        if "msg_kh_success" in st.session_state:
            st.success(st.session_state.pop("msg_kh_success"))

    st.divider()
    st.subheader("3. Chọn Thuốc lá & Thêm vào đơn hàng")

    nha_may_filter = nha_may_nv if is_logged else "Tất cả"

    if not df_vt.empty:
        if nha_may_filter != "Tất cả" and 'nha_may' in df_vt.columns:
            df_vt_filtered = df_vt[(df_vt['nha_may'] == nha_may_filter) | (df_vt['nha_may'] == "Tất cả")]
        else:
            df_vt_filtered = df_vt

        ds_ten_thuoc_nv = df_vt_filtered['ten_vt'].unique().tolist() if not df_vt_filtered.empty else []
        map_vt_nv = df_vt_filtered.set_index('ten_vt').to_dict('index') if not df_vt_filtered.empty else {}

        if ds_ten_thuoc_nv:
            ten_vt_selected = st.selectbox("Chọn Loại Thuốc:", options=ds_ten_thuoc_nv, key="sb_thuoc_la")
            ma_vt_selected = map_vt_nv[ten_vt_selected]['ma_vt']
            nha_may_selected = map_vt_nv[ten_vt_selected].get('nha_may', nha_may_filter)
            
            val_gia = map_vt_nv[ten_vt_selected].get('don_gia', 0)
            gia_goi_y = float(val_gia) if pd.notna(val_gia) else 0.0

            col_sl, col_dg = st.columns(2)
            with col_sl:
                so_luong_nhap = st.number_input("Số lượng:", min_value=1, value=1, step=1, key="num_so_luong")
            with col_dg:
                don_gia_nhap = st.number_input("Đơn giá thực tế:", min_value=0.0, value=gia_goi_y, step=1000.0, format="%.0f", key="num_don_gia")

            if st.button("➕ THÊM VÀO ĐƠN HÀNG", type="secondary", use_container_width=True, key="btn_them_gio_hang"):
                if not st.session_state["is_nv_logged_in"]:
                    st.error("⚠️ Bạn phải ĐĂNG NHẬP MÃ PIN ở Mục 1 trước khi lập đơn!")
                else:
                    sl_val = int(so_luong_nhap)
                    dg_val = float(don_gia_nhap)
                    
                    st.session_state["gio_hang"].append({
                        'ma_vt': ma_vt_selected,
                        'ten_vt': ten_vt_selected,
                        'nha_may': nha_may_selected,
                        'so_luong': sl_val,
                        'don_gia': dg_val,
                        'thanh_tien': float(sl_val * dg_val),
                        'xoa': False
                    })
                    st.toast(f"Đã thêm {ten_vt_selected}!")
                    st.rerun()
        else:
            st.warning(f"Không có mặt hàng nào thuộc nhà máy {nha_may_filter}!")

    st.markdown("### 🛒 Danh sách mặt hàng đã chọn:")
    
    if st.session_state["gio_hang"]:
        df_cart = pd.DataFrame(st.session_state["gio_hang"])
        if 'xoa' not in df_cart.columns: df_cart['xoa'] = False
        
        df_cart['sl_show'] = df_cart['so_luong'].apply(format_vnd)
        df_cart['dg_show'] = df_cart['don_gia'].apply(format_vnd)
        df_cart['tt_show'] = (df_cart['so_luong'] * df_cart['don_gia']).apply(format_vnd)

        edited_cart = st.data_editor(
            df_cart[['ten_vt', 'sl_show', 'dg_show', 'tt_show', 'xoa']],
            column_config={
                "ten_vt": st.column_config.SelectboxColumn("Tên hàng", options=ds_ten_thuoc_nv, required=True),
                "sl_show": st.column_config.TextColumn("SL"),
                "dg_show": st.column_config.TextColumn("Đơn giá"),
                "tt_show": st.column_config.TextColumn("Thành tiền (VNĐ)", disabled=True),
                "xoa": st.column_config.CheckboxColumn("🗑️", default=False)
            },
            use_container_width=True,
            hide_index=True,
            key="cart_editor"
        )

        updated_cart = []
        has_changed = False
        for idx, row in edited_cart.iterrows():
            if not row['xoa']:
                orig_item = st.session_state["gio_hang"][idx]
                
                new_ten_vt = row['ten_vt']
                if new_ten_vt != orig_item.get('ten_vt') and new_ten_vt in map_vt_nv:
                    has_changed = True
                    new_ma_vt = map_vt_nv[new_ten_vt]['ma_vt']
                    new_nha_may = map_vt_nv[new_ten_vt].get('nha_may', nha_may_filter)
                    val_new_gia = map_vt_nv[new_ten_vt].get('don_gia', orig_item.get('don_gia', 0))
                    new_dg = float(val_new_gia) if pd.notna(val_new_gia) else orig_item.get('don_gia', 0.0)
                else:
                    new_ma_vt = orig_item.get('ma_vt', '')
                    new_nha_may = orig_item.get('nha_may', nha_may_filter)
                    new_dg = parse_formatted_num(row['dg_show'])

                new_sl = parse_formatted_num(row['sl_show'])
                if new_sl <= 0: new_sl = orig_item.get('so_luong', 1)
                new_tt = float(new_sl * new_dg)
                
                if new_sl != orig_item.get('so_luong') or new_dg != orig_item.get('don_gia'):
                    has_changed = True

                updated_cart.append({
                    'ma_vt': new_ma_vt,
                    'ten_vt': new_ten_vt,
                    'nha_may': new_nha_may,
                    'so_luong': new_sl,
                    'don_gia': float(new_dg),
                    'thanh_tien': new_tt,
                    'xoa': False
                })
            else:
                has_changed = True

        if has_changed:
            st.session_state["gio_hang"] = updated_cart
            st.rerun()

        tong_tien_don = sum(item['thanh_tien'] for item in st.session_state["gio_hang"])
        st.markdown(f"### 🔴 **TỔNG TIỀN THANH TOÁN:** :red[{format_vnd(tong_tien_don)}]")
        
        if st.button("🗑️ Xóa toàn bộ giỏ hàng", key="btn_xoa_gio_hang"):
            st.session_state["gio_hang"] = []
            st.rerun()

        st.divider()
        st.subheader("4. Hình thức Thanh toán")
        loai_tt = st.radio("Chọn phương thức thanh toán:", ["Tiền mặt", "Chuyển khoản", "Ghi nợ", "Kết hợp (TM / CK / Nợ)"], horizontal=True, key="rad_hinh_thuc_tt")

        tien_tm = 0.0; tien_ck = 0.0; tien_no = 0.0; ht_tt_final = "Tiền mặt"

        if loai_tt == "Tiền mặt": tien_tm = tong_tien_don; ht_tt_final = "Tiền mặt"
        elif loai_tt == "Chuyển khoản": tien_ck = tong_tien_don; ht_tt_final = "Chuyển khoản"
        elif loai_tt == "Ghi nợ": tien_no = tong_tien_don; ht_tt_final = "Ghi nợ"
        else:
            col_pay1, col_pay2, col_pay3 = st.columns(3)
            with col_pay1: tien_tm = st.number_input("💵 Tiền mặt trả:", min_value=0.0, max_value=float(tong_tien_don), value=0.0, step=50000.0, format="%.0f", key="num_pay_tm")
            with col_pay2: tien_ck = st.number_input("🏦 Chuyển khoản trả:", min_value=0.0, max_value=float(tong_tien_don - tien_tm), value=0.0, step=50000.0, format="%.0f", key="num_pay_ck")
            with col_pay3: 
                tien_no = max(0.0, tong_tien_don - tien_tm - tien_ck)
                st.write("📝 **Còn ghi nợ:**")
                st.markdown(f"#### :red[{format_vnd(tien_no)}]")

            parts = []
            if tien_tm > 0: parts.append(f"TM: {format_vnd(tien_tm)}")
            if tien_ck > 0: parts.append(f"CK: {format_vnd(tien_ck)}")
            if tien_no > 0: parts.append(f"Nợ: {format_vnd(tien_no)}")
            ht_tt_final = " + ".join(parts) if parts else "Ghi nợ"

        xuat_hoa_don = st.checkbox("🧾 Xuất Hóa Đơn MISA", value=False, key="chk_xuat_misa")

        if st.button("✅ BẤM LƯU ĐƠN HÀNG NÀY", use_container_width=True, type="primary", key="btn_luu_don_hang"):
            if not st.session_state["is_nv_logged_in"]:
                st.error("⚠️ Lỗi: Bạn chưa đăng nhập xác thực nhân viên ở Mục 1!")
            else:
                final_ten_kh = ten_kh_selected if ten_kh_selected else ""
                final_ten_nguoi_mua = ten_nguoi_mua_selected
                
                data_helper.luu_don_hang_danh_sach(
                    chi_nhanh=chi_nhanh_chon,
                    ten_nv=ten_nv_chon,
                    ma_kh=ma_kh_selected,
                    ten_kh=final_ten_kh,
                    ten_nguoi_mua=final_ten_nguoi_mua,
                    mst=mst_selected,
                    dia_chi=dia_chi_selected,
                    danh_sach_hang=st.session_state["gio_hang"],
                    hinh_thuc_tt=ht_tt_final,
                    xuat_hd="Có" if xuat_hoa_don else "Không",
                    tien_tm=tien_tm,
                    tien_ck=tien_ck,
                    tien_no=tien_no
                )
                st.success("🎉 ĐÃ LƯU ĐƠN HÀNG THÀNH CÔNG!")
                st.session_state["gio_hang"] = []
                st.rerun()
    else:
        st.info("Giỏ hàng đang trống. Hãy chọn loại thuốc và bấm nút 'Thêm vào đơn hàng'.")

# ==================== TAB 2: BÁO CÁO & QUẢN LÝ ĐƠN HÀNG ====================
with tab_baocao:
    st.subheader("📊 Báo cáo & Quản lý đơn hàng trong ngày")
    
    # RÀNG BUỘC PHÂN QUYỀN NHÂN VIÊN/ADMIN TẠI TAB 2
    is_admin = st.session_state.get("admin_unlocked", False)
    is_nv_logged = st.session_state.get("is_nv_logged_in", False)
    logged_info = st.session_state.get("logged_nv_info", {})

    col_bc1, col_bc2, col_bc3 = st.columns(3)
    with col_bc1:
        ngay_bc = st.date_input("Chọn ngày:", datetime.now(), key="dt_ngay_bc")
        
    with col_bc2:
        if is_nv_logged and not is_admin:
            cn_bc = logged_info.get("chi_nhanh", "Đà Lạt")
            st.selectbox("Chi nhánh xem:", options=[cn_bc], disabled=True, key="sb_cn_bc_dis")
        else:
            cn_bc = st.selectbox("Chi nhánh xem:", options=["Tất cả"] + ds_chi_nhanh, key="sb_cn_bc")
            
    with col_bc3:
        if is_nv_logged and not is_admin:
            nv_bc = logged_info.get("ten_nv", "")
            st.selectbox("Nhân viên xem:", options=[nv_bc], disabled=True, key="sb_nv_bc_dis")
            st.caption(f"🔒 Bạn đang xem báo cáo cá nhân: **{nv_bc}**")
        else:
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
            df_display = df_selected
        else:
            st.session_state["selected_don_hang"] = None
            st.markdown("### 📦 Thống kê tổng sản lượng xuất bán trong ngày (Chỉnh sửa trực tiếp SL & Đơn giá bên dưới):")
            df_display = df_bc

        # YÊU CẦU KẾ TOÁN: THÊM CỘT ĐƠN GIÁ, CHO PHÉP SỬA SL VÀ ĐƠN GIÁ, THÀNH TIỀN NHẢY TRỰC TIẾP
        df_edit_group = df_display.copy()
        
        # Nếu đang xem tổng hợp nhiều đơn, nhóm theo sản phẩm và tính đơn giá trung bình / thực tế
        df_report = df_edit_group.groupby('ten_vt').agg(
            so_luong=('so_luong', 'sum'),
            don_gia=('don_gia', 'mean'),
            thanh_tien=('thanh_tien', 'sum')
        ).reset_index()

        df_report['so_luong'] = df_report['so_luong'].astype(float)
        df_report['don_gia'] = df_report['don_gia'].astype(float)
        df_report['thanh_tien'] = df_report['so_luong'] * df_report['don_gia']

        edited_report_df = st.data_editor(
            df_report,
            column_config={
                "ten_vt": st.column_config.TextColumn("Tên mặt hàng", disabled=True),
                "so_luong": st.column_config.NumberColumn("Số lượng", min_value=0.0, step=1.0, format="%.0f", required=True),
                "don_gia": st.column_config.NumberColumn("Đơn giá (VNĐ)", min_value=0.0, step=1000.0, format="%.0f", required=True),
                "thanh_tien": st.column_config.NumberColumn("Thành tiền (VNĐ)", disabled=True, format="%.0f")
            },
            use_container_width=True,
            hide_index=True,
            key="report_data_editor"
        )

        # Tính lại tổng thành tiền theo thời gian thực khi người dùng sửa trên data_editor
        edited_report_df['thanh_tien'] = edited_report_df['so_luong'] * edited_report_df['don_gia']
        
        sum_sl = edited_report_df['so_luong'].sum()
        sum_tt = edited_report_df['thanh_tien'].sum()

        st.markdown(f"#### 🔴 **TỔNG CỘNG:** Số lượng: **{int(sum_sl):,}** | Thành tiền: :red[**{format_vnd(sum_tt)} VNĐ**]")

        # Cập nhật thay đổi vào Cơ sở dữ liệu nếu có đơn cụ thể được chọn
        if selected_don and st.button("💾 Cập nhật số lượng & Đơn giá vào đơn hàng này", type="primary"):
            data_helper.cap_nhat_chi_tiet_don_hang(selected_don, edited_report_df)
            st.success(f"Đã cập nhật lại đơn hàng {selected_don} thành công!")
            st.rerun()

    else:
        st.warning("Chưa có đơn hàng nào phát sinh trong ngày được chọn!")

# ==================== TAB 3: XUẤT MISA ====================
with tab_misa:
    st.subheader("🔑 Xuất File Import MISA (Định Dạng Chuẩn)")
    ngay_xuat = st.date_input("Ngày xuất dữ liệu:", datetime.now(), key="misa_date")
    cn_misa = st.selectbox("Chi nhánh xuất:", options=["Tất cả"] + ds_chi_nhanh, key="misa_cn")
    
    if st.button("📥 Tải File Import MISA", key="btn_download_misa", type="primary", use_container_width=True):
        excel_bytes = data_helper.xuat_excel_misa_chuan(str(ngay_xuat), cn_misa)
        if excel_bytes:
            st.download_button(
                label=" Click để tải file Excel MISA (.xlsx)", 
                data=excel_bytes, 
                file_name=f"MISA_Import_{ngay_xuat}.xlsx", 
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("Không có dữ liệu trong ngày này!")

# ==================== TAB 4: QUẢN LÝ ADMIN ====================
with tab_admin:
    st.subheader("⚙️ Cấu Hình Hệ Thống Professional POS")
    
    if "msg_admin_success" in st.session_state:
        st.success(st.session_state.pop("msg_admin_success"))

    if not st.session_state["admin_unlocked"]:
        input_code = st.text_input("🔐 Nhập mã Code Security để thao tác:", type="password", key="pwd_admin")
        if st.button("🔓 Xác nhận Mã Code"):
            if input_code == "9999":
                st.session_state["admin_unlocked"] = True
                st.success("Đã mở khóa quyền Cấu hình phần mềm!")
                st.rerun()
            else:
                st.error("Mã Code không chính xác!")
    else:
        st.success("🟢 Trạng thái: Đã xác thực Mã Admin (9999)")
        if st.button("🔒 Khóa lại"):
            st.session_state["admin_unlocked"] = False
            st.rerun()
            
        st.divider()
        opts_nhamay_select = ["Tất cả"] + ds_nha_may_goc + ["➕ Thêm Nhà Máy Mới..."]

        with st.expander("➕ **Thêm Nhân Viên Theo Chi Nhánh / Nhà Máy**"):
            new_ma_nv = f"NV{len(df_nv) + 1:02d}"
            new_ten_nv = st.text_input("Tên nhân viên mới:", key="txt_add_nv_name")
            new_pin_nv = st.text_input("Mã PIN đăng nhập (Default: 1234):", value="1234", key="txt_add_nv_pin")
            new_cn_nv = st.selectbox("Gán vào chi nhánh:", options=ds_chi_nhanh, key="sb_add_nv_cn")
            
            nm_nv_choice = st.selectbox("Phụ trách nhà máy thuốc lá:", options=opts_nhamay_select, key="sb_add_nv_nm")
            if nm_nv_choice == "➕ Thêm Nhà Máy Mới...":
                final_nm_nv = st.text_input("Nhập tên Nhà Máy mới:", key="txt_custom_nm_nv")
            else:
                final_nm_nv = nm_nv_choice

            if st.button("💾 Lưu Nhân Viên Mới", key="btn_save_new_nv"):
                if new_ten_nv and final_nm_nv:
                    new_row_nv = pd.DataFrame([{
                        'ma_nv': new_ma_nv, 
                        'ten_nv': new_ten_nv, 
                        'chi_nhanh': new_cn_nv, 
                        'nha_may': final_nm_nv,
                        'pin': new_pin_nv.strip() if new_pin_nv.strip() else "1234"
                    }])
                    df_nv = pd.concat([df_nv, new_row_nv], ignore_index=True)
                    df_nv.to_csv('data/nhan_vien.csv', index=False, encoding='utf-8')
                    st.session_state["msg_admin_success"] = f"🎉 Đã thêm thành công nhân viên: **{new_ten_nv}**!"
                    st.rerun()

        with st.expander("➕ **Thêm Mặt Hàng / Loại Thuốc Mới**"):
            default_vt_code = f"VT{len(df_vt) + 1:03d}"
            new_ma_vt = st.text_input("Mã hàng (VD: VT001, BAT_01...):", value=default_vt_code, key="txt_add_vt_code")
            new_ten_vt = st.text_input("Tên mặt hàng / Thuốc lá:", key="txt_add_vt_name")
            
            nm_vt_choice = st.selectbox("Thuộc Nhà Máy / Hãng:", options=[x for x in opts_nhamay_select if x != "Tất cả"], key="sb_add_vt_nm")
            if nm_vt_choice == "➕ Thêm Nhà Máy Mới...":
                final_nm_vt = st.text_input("Nhập tên Nhà Máy mới:", key="txt_custom_nm_vt")
            else:
                final_nm_vt = nm_vt_choice

            new_gia_vt = st.number_input("Đơn giá mặc định:", min_value=0.0, value=0.0, step=1000.0, format="%.0f", key="num_add_vt_gia")

            if st.button("💾 Lưu Mặt Hàng Mới", key="btn_save_new_vt"):
                if new_ten_vt and final_nm_vt:
                    final_ma_vt = new_ma_vt.strip() if new_ma_vt.strip() else default_vt_code
                    new_row_vt = pd.DataFrame([{
                        'ma_vt': final_ma_vt, 
                        'ten_vt': new_ten_vt, 
                        'don_gia': float(new_gia_vt), 
                        'nha_may': final_nm_vt
                    }])
                    df_vt = pd.concat([df_vt, new_row_vt], ignore_index=True)
                    df_vt.to_csv('data/hang_hoa.csv', index=False, encoding='utf-8')
                    st.session_state["msg_admin_success"] = f"🎉 Đã thêm thành công mặt hàng: **[{final_ma_vt}] {new_ten_vt}**!"
                    st.rerun()

        st.subheader("📋 Tra Cứu & Chỉnh Sửa Dữ Liệu Hệ Thống")
        
        with st.expander("📁 **1. Quản Lý & Sửa Danh Sách Nhân Viên**"):
            if not df_nv.empty:
                col_flt_nv1, col_flt_nv2 = st.columns(2)
                with col_flt_nv1: filter_cn_nv = st.selectbox("🔍 Lọc theo Chi nhánh:", options=["Tất cả"] + ds_chi_nhanh, key="flt_cn_nv")
                with col_flt_nv2: search_nv = st.text_input("🔍 Tìm theo tên nhân viên:", key="txt_search_nv")

                df_nv_show = df_nv.copy()
                if filter_cn_nv != "Tất cả": df_nv_show = df_nv_show[df_nv_show['chi_nhanh'] == filter_cn_nv]
                if search_nv.strip(): df_nv_show = df_nv_show[df_nv_show['ten_nv'].astype(str).str.contains(search_nv.strip(), case=False, na=False)]

                edited_nv = st.data_editor(
                    df_nv_show,
                    column_config={
                        "ma_nv": st.column_config.TextColumn("Mã NV", disabled=True),
                        "ten_nv": st.column_config.TextColumn("Tên Nhân Viên", required=True),
                        "chi_nhanh": st.column_config.SelectboxColumn("Chi Nhánh", options=ds_chi_nhanh, required=True),
                        "nha_may": st.column_config.TextColumn("Nhà Máy Phụ Trách", required=True),
                        "pin": st.column_config.TextColumn("Mã PIN Login", required=True)
                    },
                    use_container_width=True,
                    hide_index=True,
                    num_rows="dynamic",
                    key="editor_nv"
                )
                if st.button("💾 Lưu Thay Đổi Nhân Viên", key="btn_save_nv_changes"):
                    edited_nv.to_csv('data/nhan_vien.csv', index=False, encoding='utf-8')
                    if "editor_nv" in st.session_state:
                        del st.session_state["editor_nv"]
                    st.session_state["msg_admin_success"] = "✅ Đã cập nhật danh sách nhân viên thành công!"
                    st.rerun()

        with st.expander("📁 **2. Quản Lý & Sửa Danh Sách Mặt Hàng**"):
            if not df_vt.empty:
                col_flt_vt1, col_flt_vt2 = st.columns(2)
                with col_flt_vt1: filter_nm_vt = st.selectbox("🔍 Lọc theo Nhà Máy / Hãng:", options=["Tất cả"] + ds_nha_may_goc, key="flt_nm_vt")
                with col_flt_vt2: search_vt = st.text_input("🔍 Tìm theo tên / mã mặt hàng:", key="txt_search_vt")

                cols_vt_show = [c for c in ['ma_vt', 'ten_vt', 'don_gia', 'nha_may'] if c in df_vt.columns]
                df_vt_show = df_vt[cols_vt_show].copy()

                if filter_nm_vt != "Tất cả": df_vt_show = df_vt_show[df_vt_show['nha_may'] == filter_nm_vt]
                if search_vt.strip():
                    df_vt_show = df_vt_show[
                        df_vt_show['ten_vt'].astype(str).str.contains(search_vt.strip(), case=False, na=False) |
                        df_vt_show['ma_vt'].astype(str).str.contains(search_vt.strip(), case=False, na=False)
                    ]

                for c_txt in ['ma_vt', 'ten_vt', 'nha_may']:
                    if c_txt in df_vt_show.columns:
                        df_vt_show[c_txt] = df_vt_show[c_txt].fillna("").astype(str)

                edited_vt = st.data_editor(
                    df_vt_show,
                    column_config={
                        "ma_vt": st.column_config.TextColumn("Mã VT", required=True),
                        "ten_vt": st.column_config.TextColumn("Tên Thuốc / Mặt Hàng", required=True),
                        "don_gia": st.column_config.NumberColumn("Đơn Giá", required=True),
                        "nha_may": st.column_config.TextColumn("Nhà Máy / Hãng", required=True)
                    },
                    use_container_width=True,
                    hide_index=True,
                    num_rows="dynamic",
                    key="editor_vt"
                )
                if st.button("💾 Lưu Thay Đổi Mặt Hàng", key="btn_save_vt_changes"):
                    edited_vt.to_csv('data/hang_hoa.csv', index=False, encoding='utf-8')
                    if "editor_vt" in st.session_state:
                        del st.session_state["editor_vt"]
                    st.session_state["msg_admin_success"] = "✅ Đã cập nhật danh sách mặt hàng thành công!"
                    st.rerun()

        with st.expander("📁 **3. Quản Lý & Sửa Danh Sách Khách Hàng**"):
            if not df_kh.empty:
                search_kh = st.text_input("🔍 Tìm kiếm Tên / MST Khách hàng:", key="txt_search_kh")
                df_kh_show = df_kh.copy()
                if search_kh.strip():
                    df_kh_show = df_kh_show[
                        df_kh_show['ten_kh'].astype(str).str.contains(search_kh.strip(), case=False, na=False) |
                        df_kh_show['ma_so_thue'].astype(str).str.contains(search_kh.strip(), case=False, na=False)
                    ]

                for c_txt in ['ma_kh', 'ten_kh', 'ten_nguoi_mua', 'ma_so_thue', 'dia_chi']:
                    if c_txt in df_kh_show.columns:
                        df_kh_show[c_txt] = df_kh_show[c_txt].fillna("").astype(str)

                edited_kh = st.data_editor(
                    df_kh_show,
                    column_config={
                        "ma_kh": st.column_config.TextColumn("Mã KH", disabled=True),
                        "ten_kh": st.column_config.TextColumn("Tên Công Ty / Hộ Kinh Doanh"),
                        "ten_nguoi_mua": st.column_config.TextColumn("Tên Người Mua"),
                        "ma_so_thue": st.column_config.TextColumn("Mã Số Thuế"),
                        "dia_chi": st.column_config.TextColumn("Địa Chỉ")
                    },
                    use_container_width=True,
                    hide_index=True,
                    num_rows="dynamic",
                    key="editor_kh"
                )
                if st.button("💾 Lưu Thay Đổi Khách Hàng", key="btn_save_kh_changes"):
                    edited_kh.to_csv('data/khach_hang.csv', index=False, encoding='utf-8')
                    if "editor_kh" in st.session_state:
                        del st.session_state["editor_kh"]
                    st.session_state["msg_admin_success"] = "✅ Đã cập nhật danh sách khách hàng thành công!"
                    st.rerun()
