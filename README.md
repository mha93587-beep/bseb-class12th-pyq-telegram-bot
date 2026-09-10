# 📚 Bihar Board (BSEB) Class 12th PYQ Telegram Automated Dispatcher

An end-to-end automated pipeline and Streamlit dashboard that crawls official Bihar School Examination Board (BSEB) Class 12th Previous Year Question Papers (2015–2026) from [Selfstudys.com](https://www.selfstudys.com/) and streams them directly into a Telegram Channel without local disk storage.

---

## 🌟 Key Highlights & Features

1. **⚡ Zero Local Disk Overhead (Direct CDN-to-Telegram In-Memory Streaming)**:
   - Fetches PDF byte streams from Selfstudys CDN directly into memory buffers (`io.BytesIO`).
   - Immediately pipes into Telegram Bot API (`sendDocument`).
   - No disk clutter, no temporary file management, and no storage limits.

2. **📄 Clean PDF Presentation (No Captions & Standardized Filenames)**:
   - Files are uploaded as clean PDF documents without captions for distraction-free offline studying.
   - Every file is automatically named with **Subject Name**, **Subject Code**, **Question Set**, and **Year** (e.g. `Mathematics - 121-327 - Set-A - 2026.pdf`).

3. **🗓️ Structured Year Announcement Headers**:
   - Before uploading question papers for any exam year, an introductory index message is posted in the channel detailing the examination year, total papers, and key subjects.
   - Serves as a searchable separator in the Telegram channel feed.

4. **🗃️ SQLite Database (liteSQL)**:
   - Tracks all 205 question papers across 11 examination years (2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024, 2025, 2026).
   - Records status (`pending`, `uploading`, `sent`, `failed`), Telegram `message_id`, direct PDF CDN URL, file size, and timestamps.
   - Prevents duplicate uploads and allows resuming interrupted runs seamlessly.

5. **🛡️ Telegram Rate-Limit & Error Handling**:
   - Built-in safe dispatch delay (default 2.5s).
   - Automatically catches HTTP 429 `Retry-After` headers and safely pauses until Telegram lifts the rate limit.
   - Automatic retry mechanism for transient network dropouts.

6. **☁️ Streamlit Community Cloud Ready**:
   - Built-in interactive Web UI for monitoring real-time dispatch progress, searching papers, filtering by year/status, and manual triggering.
   - Free, 24/7 cloud hosting with high-bandwidth gigabit datacenter uplinks.

---

## 📱 Telegram Channel Setup

- **Target Channel:** [@bsebclass12thpyq](https://t.me/bsebclass12thpyq) (or your own channel)
- **Bot Setup:** Create a bot with [@BotFather](https://t.me/BotFather), add it as an Administrator to your channel with Post Messages permission.

---

## 🚀 Deployment on Streamlit Community Cloud (Recommended)

1. **Fork or connect this repository:**
   - Repo: `https://github.com/mha93587-beep/bseb-class12th-pyq-telegram-bot`
2. **Log into Streamlit Cloud:**
   - Visit [share.streamlit.io](https://share.streamlit.io/) with your GitHub account.
3. **Deploy the App:**
   - Click **"New app"**
   - Repository: `mha93587-beep/bseb-class12th-pyq-telegram-bot`
   - Branch: `main`
   - Main file path: `app.py`
4. **Configure Secrets**:
   - In App Settings ➔ **Secrets**, add:
     ```toml
     TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
     TELEGRAM_CHAT_ID = "-1003918378426"
     ```
5. Click **Deploy!** Once the app loads, simply press **⚡ Start Sending to Telegram**.

---

## 💻 Local CLI Usage

You can also run commands directly via command line:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. View database statistics
python3 main.py status

# 3. Index/Re-crawl papers from Selfstudys
python3 main.py index

# 4. Pre-resolve direct PDF CDN links
python3 main.py resolve

# 5. Dispatch papers to Telegram
export TELEGRAM_BOT_TOKEN="YOUR_BOT_TOKEN"
export TELEGRAM_CHAT_ID="-1003918378426"
python3 main.py dispatch --order ASC --delay 2.5

# Dispatch a specific year only
python3 main.py dispatch --year 2026

# 6. Run Streamlit web UI locally
streamlit run app.py
```

---

## 📂 Project Architecture

```
bseb-class12th-pyq-telegram-bot/
├── app.py                  # Streamlit Community Cloud Web Dashboard
├── crawler.py              # Selfstudys scraper, pagination & PDF resolver
├── database.py             # SQLite database layer (schema, queries, stats)
├── telegram_dispatcher.py  # Zero-disk in-memory PDF streaming & rate limit handler
├── main.py                 # CLI interface
├── requirements.txt        # Python dependencies
├── bseb_pyq.db             # Pre-indexed SQLite database
└── README.md               # Documentation
```
