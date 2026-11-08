import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# 1. KẾT NỐI VÀ KHỞI TẠO CƠ SỞ DỮ LIỆU SQLITE
conn = sqlite3.connect('electronics_store.db', check_same_thread=False)
c = conn.cursor()

def init_db():
    # Bảng Người dùng (Phân quyền)
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT)''')
    # Bảng Sản phẩm
    c.execute('''CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, imei TEXT UNIQUE, price REAL, status TEXT)''')
    # Bảng Khách hàng
    c.execute('''CREATE TABLE IF NOT EXISTS customers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, phone TEXT UNIQUE)''')
    # Bảng Đơn hàng (POS)
    c.execute('''CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER, imei TEXT, sale_date TEXT, total REAL)''')
    conn.commit()

    # Tạo sẵn tài khoản mẫu để test
    c.execute("SELECT * FROM users")
    if not c.fetchall():
        c.execute("INSERT INTO users VALUES ('admin', '123', 'Admin')")
        c.execute("INSERT INTO users VALUES ('nhanvien', '123', 'Staff')")
        conn.commit()

init_db()

# 2. HỆ THỐNG ĐĂNG NHẬP (SESSION STATE)
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['role'] = ''
    st.session_state['username'] = ''

if not st.session_state['logged_in']:
    st.markdown("<h2 style='text-align: center;'>ĐĂNG NHẬP HỆ THỐNG QUẢN TRỊ</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        username = st.text_input("Tên đăng nhập")
        password = st.text_input("Mật khẩu", type='password')
        if st.button("Đăng nhập", use_container_width=True):
            c.execute("SELECT role FROM users WHERE username=? AND password=?", (username, password))
            user = c.fetchone()
            if user:
                st.session_state['logged_in'] = True
                st.session_state['role'] = user[0]
                st.session_state['username'] = username
                st.rerun()
            else:
                st.error("Sai thông tin! Dùng tài khoản mẫu: admin/123 (quản lý) hoặc nhanvien/123 (nhân viên)")
else:
    # 3. GIAO DIỆN QUẢN TRỊ & PHÂN QUYỀN
    st.sidebar.title(f"Xin chào, {st.session_state['username']}")
    st.sidebar.markdown(f"**Cấp bậc:** {st.session_state['role']}")
    
    # Chia quyền Menu
    if st.session_state['role'] == 'Admin':
        menu = ["1. Bán hàng (POS)", "2. Quản lý Kho hàng", "3. Quản lý Khách hàng", "4. Báo cáo & Thống kê", "5. Chuyển đổi dữ liệu (ETL)"]
    else:
        menu = ["1. Bán hàng (POS)", "3. Quản lý Khách hàng"] # Nhân viên không xem được báo cáo và kho
    
    choice = st.sidebar.radio("Chức năng:", menu)
    if st.sidebar.button("Đăng xuất"):
        st.session_state['logged_in'] = False
        st.rerun()

    # --- TÍNH NĂNG 1: BÁN HÀNG (POS) ---
    if choice == "1. Bán hàng (POS)":
        st.header("🛒 Hệ Thống Bán Hàng (POS)")
        st.write("Tạo đơn hàng và tự động trừ kho sản phẩm.")
        
        # Chọn khách hàng
        c.execute("SELECT id, name, phone FROM customers")
        cust_data = c.fetchall()
        cust_dict = {f"{row[1]} - {row[2]}": row[0] for row in cust_data}
        
        if not cust_dict:
            st.warning("Chưa có dữ liệu khách hàng. Vui lòng thêm khách hàng trước.")
        else:
            selected_cust = st.selectbox("Chọn Khách hàng:", list(cust_dict.keys()))
            
            # Chọn sản phẩm còn hàng
            c.execute("SELECT imei, name, price FROM products WHERE status = 'Còn hàng'")
            prod_data = c.fetchall()
            prod_dict = {f"IMEI: {row[0]} - {row[1]} ({row[2]:,.0f} VNĐ)": (row[0], row[2]) for row in prod_data}
            
            if not prod_dict:
                st.warning("Kho hiện tại đã hết sản phẩm có sẵn.")
            else:
                selected_prod = st.selectbox("Quét / Chọn Mã IMEI Sản phẩm:", list(prod_dict.keys()))
                
                if st.button("Thanh toán & Xuất hóa đơn", type="primary"):
                    cust_id = cust_dict[selected_cust]
                    imei, price = prod_dict[selected_prod]
                    date_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Cập nhật DB: Thêm đơn hàng + Đổi trạng thái sản phẩm
                    c.execute("INSERT INTO orders (customer_id, imei, sale_date, total) VALUES (?, ?, ?, ?)", (cust_id, imei, date_now, price))
                    c.execute("UPDATE products SET status = 'Đã bán' WHERE imei = ?", (imei,))
                    conn.commit()
                    st.success(f"Giao dịch thành công! Đã bán IMEI {imei} với giá {price:,.0f} VNĐ.")

    # --- TÍNH NĂNG 2: QUẢN LÝ KHO (ADMIN) ---
    elif choice == "2. Quản lý Kho hàng":
        st.header("📦 Quản lý Sản phẩm & Tồn kho")
        df_products = pd.read_sql_query("SELECT * FROM products", conn)
        st.dataframe(df_products, use_container_width=True)
        
        with st.expander("Thêm sản phẩm mới thủ công"):
            col1, col2 = st.columns(2)
            p_name = col1.text_input("Tên sản phẩm")
            p_imei = col2.text_input("Mã IMEI")
            p_price = col1.number_input("Giá bán", min_value=0)
            p_status = col2.selectbox("Trạng thái", ["Còn hàng", "Đã bán", "Lỗi"])
            if st.button("Lưu sản phẩm"):
                try:
                    c.execute("INSERT INTO products (name, imei, price, status) VALUES (?,?,?,?)", (p_name, p_imei, p_price, p_status))
                    conn.commit()
                    st.success("Đã thêm vào kho!")
                    st.rerun()
                except:
                    st.error("Mã IMEI đã tồn tại!")

    # --- TÍNH NĂNG 3: KHÁCH HÀNG & BẢO HÀNH ---
    elif choice == "3. Quản lý Khách hàng":
        st.header("👥 Hồ sơ Khách hàng & Bảo hành")
        df_customers = pd.read_sql_query("SELECT * FROM customers", conn)
        st.dataframe(df_customers, use_container_width=True)
        
        st.subheader("Thêm khách hàng mới")
        c_name = st.text_input("Tên khách hàng")
        c_phone = st.text_input("Số điện thoại")
        if st.button("Đăng ký khách hàng"):
            try:
                c.execute("INSERT INTO customers (name, phone) VALUES (?,?)", (c_name, c_phone))
                conn.commit()
                st.success("Tạo mới thành công!")
                st.rerun()
            except:
                st.error("Số điện thoại này đã được đăng ký!")

    # --- TÍNH NĂNG 4: BÁO CÁO THỐNG KÊ (ADMIN) ---
    elif choice == "4. Báo cáo & Thống kê":
        st.header("📊 Báo cáo Kinh doanh")
        # Dùng pandas join các bảng để báo cáo
        query = """
        SELECT orders.sale_date, customers.name, products.name, orders.total 
        FROM orders 
        JOIN customers ON orders.customer_id = customers.id
        JOIN products ON orders.imei = products.imei
        """
        df_orders = pd.read_sql_query(query, conn)
        
        if not df_orders.empty:
            total_revenue = df_orders['total'].sum()
            col1, col2 = st.columns(2)
            col1.metric("Tổng Doanh Thu", f"{total_revenue:,.0f} VNĐ")
            col2.metric("Số lượng đơn hàng", len(df_orders))
            st.dataframe(df_orders, use_container_width=True)
            st.bar_chart(df_orders.set_index('sale_date')['total'])
        else:
            st.info("Chưa có phát sinh giao dịch bán hàng.")

    # --- TÍNH NĂNG 5: ETL (ADMIN) ---
    elif choice == "5. Chuyển đổi dữ liệu (ETL)":
        st.header("🔄 Chuyển đổi dữ liệu (ETL)")
        uploaded_file = st.file_uploader("Tải lên file CSV chứa dữ liệu cũ", type=["csv"])
        if uploaded_file:
            df_upload = pd.read_csv(uploaded_file)
            st.write("Bản xem trước:", df_upload.head())
            if st.button("Bắt đầu Migrate Data (ETL)"):
                success_count = 0
                for index, row in df_upload.iterrows():
                    try:
                        c.execute("INSERT INTO products (name, imei, price, status) VALUES (?,?,?,?)", 
                                  (row['name'], row['imei'], row['price'], row['status']))
                        success_count += 1
                    except sqlite3.IntegrityError:
                        pass # Bỏ qua trùng IMEI
                conn.commit()
                st.success(f"Hoàn tất! Đã nạp thành công {success_count} sản phẩm mới.")