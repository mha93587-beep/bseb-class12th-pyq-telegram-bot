import streamlit as st
import pandas as pd
import time
import os
import sys

import database
import crawler
import telegram_dispatcher

st.set_page_config(
    page_title="BSEB 12th PYQ Dispatcher",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Database
database.init_db()

# Custom CSS styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        border-left: 5px solid #1E88E5;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .stButton>button {
        border-radius: 6px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Session state initialization
if 'is_running' not in st.session_state:
    st.session_state.is_running = False
if 'stop_requested' not in st.session_state:
    st.session_state.stop_requested = False

# Sidebar Configuration
st.sidebar.title("📚 BSEB 12th PYQ Bot")
st.sidebar.caption("Automated Selfstudys.com to Telegram Cloud Dispatcher")

st.sidebar.markdown("---")
st.sidebar.subheader("🔑 Telegram Credentials")

# Load dynamically from secrets or environment
initial_bot_token = ""
if hasattr(st, "secrets") and "TELEGRAM_BOT_TOKEN" in st.secrets:
    initial_bot_token = st.secrets["TELEGRAM_BOT_TOKEN"]
elif "TELEGRAM_BOT_TOKEN" in os.environ:
    initial_bot_token = os.environ["TELEGRAM_BOT_TOKEN"]

initial_chat_id = "-1003918378426"
if hasattr(st, "secrets") and "TELEGRAM_CHAT_ID" in st.secrets:
    initial_chat_id = st.secrets["TELEGRAM_CHAT_ID"]
elif "TELEGRAM_CHAT_ID" in os.environ:
    initial_chat_id = os.environ["TELEGRAM_CHAT_ID"]

bot_token = st.sidebar.text_input(
    "Bot Token", 
    value=initial_bot_token, 
    type="password",
    help="Enter Telegram Bot Token from @BotFather, or configure in Streamlit Secrets."
)
chat_id = st.sidebar.text_input(
    "Channel Chat ID / @username", 
    value=initial_chat_id,
    help="Channel ID (e.g. -1003918378426) or public username (e.g. @bsebclass12thpyq)"
)

if not bot_token:
    st.sidebar.warning("⚠️ Enter Bot Token above or set TELEGRAM_BOT_TOKEN in Secrets.")

st.sidebar.markdown("[📢 Open Telegram Channel](https://t.me/bsebclass12thpyq)")

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Dispatch Settings")

dispatch_order = st.sidebar.radio(
    "Year Order",
    options=["Ascending (2015 ➔ 2026)", "Descending (2026 ➔ 2015)"],
    index=0
)
order_key = "ASC" if "Ascending" in dispatch_order else "DESC"

delay_sec = st.sidebar.slider("Delay Between Uploads (Seconds)", min_value=1.5, max_value=8.0, value=2.5, step=0.5)

years_list = [y['year'] for y in database.get_years()]
selected_year_filter = st.sidebar.selectbox("Target Year Batch", options=["ALL YEARS"] + years_list, index=0)
target_year = None if selected_year_filter == "ALL YEARS" else selected_year_filter

st.sidebar.markdown("---")
st.sidebar.info("💡 **Tip**: Running on Streamlit Community Cloud streams directly from CDN with high-speed uplinks.")

# Header
st.title("📚 Bihar Board (BSEB) Class 12th PYQ Dispatcher")
st.markdown("Automated crawler & direct cloud streaming pipeline for Class 12th Previous Year Question Papers (2015–2026).")

# Fetch Stats
stats = database.get_stats()
total_p = stats['total_papers']
sent_p = stats['sent_papers']
pending_p = stats['pending_papers']
failed_p = stats['failed_papers']
pct_done = (sent_p / total_p * 100) if total_p > 0 else 0.0

# Metrics
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total Papers", f"{total_p}")
col2.metric("Sent to Channel", f"{sent_p} ✅")
col3.metric("Pending", f"{pending_p} ⏳")
col4.metric("Failed", f"{failed_p} ❌")
col5.metric("Completion", f"{pct_done:.1f}%")

st.markdown("---")

# Navigation Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "🚀 Dispatcher & Monitor", 
    "📑 Question Papers Database", 
    "☁️ Streamlit Cloud Hosting Guide", 
    "🛠️ System Logs & Maintenance"
])

# ================= TAB 1: DISPATCHER =================
with tab1:
    st.subheader("Control Panel")
    btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4)
    
    with btn_col1:
        start_btn = st.button("⚡ Start Sending to Telegram", type="primary", use_container_width=True, disabled=st.session_state.is_running)
    with btn_col2:
        stop_btn = st.button("⏹️ Stop / Pause", use_container_width=True, disabled=not st.session_state.is_running)
    with btn_col3:
        scan_btn = st.button("🔍 Scan & Re-Index Selfstudys", use_container_width=True, disabled=st.session_state.is_running)
    with btn_col4:
        retry_btn = st.button("🔄 Retry Failed Papers", use_container_width=True, disabled=st.session_state.is_running)
        
    if stop_btn:
        st.session_state.stop_requested = True
        st.warning("Halting dispatcher after current file...")

    if retry_btn:
        database.reset_failed()
        st.success("All failed papers reset to 'pending' status.")
        st.rerun()

    if scan_btn:
        st.session_state.is_running = True
        prog_bar = st.progress(0.0)
        status_text = st.empty()
        
        def index_cb(msg, pct):
            prog_bar.progress(pct)
            status_text.info(f"🔍 {msg}")
            
        res = crawler.index_all(progress_callback=index_cb)
        status_text.success(f"✅ Scanning complete! Indexed {res['total_papers']} papers across {res['total_years']} years.")
        st.session_state.is_running = False
        time.sleep(1)
        st.rerun()

    if start_btn:
        if not bot_token or not chat_id:
            st.error("Please enter your Telegram Bot Token and Channel Chat ID in the sidebar.")
        else:
            st.session_state.is_running = True
            st.session_state.stop_requested = False
            
            prog_container = st.container()
            with prog_container:
                prog_bar = st.progress(0.0)
                status_text = st.empty()
                live_info = st.empty()
                
            def is_cancelled_check():
                return st.session_state.stop_requested

            def progress_cb(paper, curr, total):
                overall_stats = database.get_stats()
                curr_sent = overall_stats['sent_papers']
                total_all = overall_stats['total_papers']
                pct = (curr_sent / total_all) if total_all > 0 else 0.0
                prog_bar.progress(min(pct, 1.0))
                status_text.markdown(f"**Dispatching ({curr}/{total} in current year)**: `{paper['clean_filename']}`")
                live_info.caption(f"Overall Progress: {curr_sent}/{total_all} papers sent ({pct*100:.1f}%)")

            status_text.info("🚀 Starting dispatch pipeline...")
            batch_res = telegram_dispatcher.dispatch_batch(
                bot_token=bot_token,
                chat_id=chat_id,
                year=target_year,
                order=order_key,
                delay=delay_sec,
                progress_callback=progress_cb,
                is_cancelled=is_cancelled_check
            )
            
            st.session_state.is_running = False
            if st.session_state.stop_requested:
                st.warning("Dispatcher paused by user.")
            else:
                st.success(f"🎉 Dispatch completed! Sent: {batch_res['sent']}, Failed: {batch_res['failed']}")
            time.sleep(1.5)
            st.rerun()

    st.markdown("### 📊 Year-by-Year Breakdown")
    if stats['year_stats']:
        y_df = pd.DataFrame(stats['year_stats'])
        y_df['Completion'] = (y_df['sent'] / y_df['total'] * 100).round(1).astype(str) + '%'
        y_df.rename(columns={
            'year': 'Year',
            'total': 'Total Papers',
            'sent': 'Sent ✅',
            'pending': 'Pending ⏳',
            'failed': 'Failed ❌'
        }, inplace=True)
        st.dataframe(y_df, use_container_width=True, hide_index=True)
    else:
        st.info("No papers indexed yet. Click 'Scan & Re-Index Selfstudys' above.")

# ================= TAB 2: PAPERS DATABASE =================
with tab2:
    st.subheader("Indexed Question Papers")
    
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        f_year = st.selectbox("Filter by Year", options=["All"] + years_list, key="f_year")
    with f_col2:
        f_status = st.selectbox("Filter by Status", options=["All", "pending", "sent", "failed"], key="f_status")
    with f_col3:
        f_search = st.text_input("Search filename, subject, or code", "", key="f_search")
        
    papers_data = database.get_papers(
        year=None if f_year == "All" else f_year,
        status=None if f_status == "All" else f_status,
        search_query=f_search if f_search else None
    )
    
    st.caption(f"Showing {len(papers_data)} matching papers")
    
    if papers_data:
        display_df = pd.DataFrame(papers_data)[[
            'id', 'year', 'clean_filename', 'subject', 'code', 'status', 'telegram_message_id', 'sent_at'
        ]]
        display_df.rename(columns={
            'id': 'ID',
            'year': 'Year',
            'clean_filename': 'Filename (PDF)',
            'subject': 'Subject',
            'code': 'Code',
            'status': 'Status',
            'telegram_message_id': 'Telegram Msg ID',
            'sent_at': 'Sent At'
        }, inplace=True)
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        # Single paper sender
        st.markdown("---")
        st.markdown("#### 📤 Send Single Paper Manually")
        paper_options = {f"#{p['id']} - {p['clean_filename']} ({p['status']})": p for p in papers_data}
        selected_paper_label = st.selectbox("Select paper to dispatch", list(paper_options.keys()))
        
        if st.button("Send Selected Paper Now"):
            if not bot_token or not chat_id:
                st.error("Please enter Telegram Bot Token and Chat ID in the sidebar.")
            else:
                p_to_send = paper_options[selected_paper_label]
                with st.spinner(f"Streaming '{p_to_send['clean_filename']}' to Telegram..."):
                    ok = telegram_dispatcher.send_paper(bot_token, chat_id, p_to_send)
                    if ok:
                        st.success(f"Successfully sent '{p_to_send['clean_filename']}' to channel!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Failed to send paper. Check system logs.")
    else:
        st.info("No matching papers found.")

# ================= TAB 3: STREAMLIT CLOUD GUIDE =================
with tab3:
    st.subheader("☁️ Deploying to Streamlit Community Cloud")
    st.markdown("""
    Host this entire automation pipeline on **Streamlit Community Cloud** (free forever) so it runs with **gigabit cloud bandwidth** directly streaming PDFs from Selfstudys CDN to Telegram!
    
    ### 📋 Step-by-Step Deployment:
    1. **GitHub Repository**:
       This repository is hosted at:
       `https://github.com/mha93587-beep/bseb-class12th-pyq-telegram-bot`
       
    2. **Log in to Streamlit Cloud**:
       Go to [share.streamlit.io](https://share.streamlit.io/) and sign in with GitHub.
       
    3. **Create New App**:
       - Click **"New app"**
       - Select Repository: `mha93587-beep/bseb-class12th-pyq-telegram-bot`
       - Branch: `main`
       - Main file path: `app.py`
       
    4. **Configure Secrets (Recommended)**:
       Under **Advanced settings** ➔ **Secrets**, paste your credentials:
       ```toml
       TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
       TELEGRAM_CHAT_ID = "-1003918378426"
       ```
       
    5. **Deploy**:
       Click **"Deploy!"**.
       Once deployed, you can click **"Start Sending to Telegram"** anytime and it will dispatch all 205 papers continuously in the background!
    """)

# ================= TAB 4: SYSTEM LOGS =================
with tab4:
    st.subheader("🛠️ System Event Logs")
    logs = database.get_recent_logs(limit=50)
    if logs:
        log_df = pd.DataFrame(logs)[['timestamp', 'level', 'message']]
        st.dataframe(log_df, use_container_width=True, hide_index=True)
    else:
        st.info("No logs recorded yet.")
        
    st.markdown("---")
    st.subheader("Database Maintenance")
    if st.button("Reset Entire Database (Re-init)", type="secondary"):
        if os.path.exists(database.DEFAULT_DB_PATH):
            os.remove(database.DEFAULT_DB_PATH)
        database.init_db()
        st.success("Database reset successfully.")
        st.rerun()
