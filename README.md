# 📚 Bihar Board (BSEB) Class 12th PYQ Telegram Automated Dispatcher

An end-to-end automated pipeline, Streamlit dashboard, and GitHub Actions worker that crawls official Bihar School Examination Board (BSEB) Class 12th Previous Year Question Papers (2015–2026) from [Selfstudys.com](https://www.selfstudys.com/) and streams them directly into a Telegram Channel without local disk storage.

---

## 🌟 Key Highlights & Features

1. **⚡ Zero Local Disk Overhead (Direct CDN-to-Telegram In-Memory Streaming)**:
   - Fetches PDF byte streams from Selfstudys CDN directly into memory buffers (`io.BytesIO`).
   - Immediately pipes into Telegram Bot API (`sendDocument`).
   - No disk clutter, no temporary file management, and no storage limits.

2. **🚀 True Persistent Background Execution**:
   - **Streamlit Community Cloud:** Powered by `BackgroundDispatcherManager` running on a detached daemon server thread. Closing your browser tab or locking your phone will **NOT** stop the upload!
   - **GitHub Actions (1-Click):** Dedicated cloud server runner that dispatches all papers in the background with zero browser dependency.

3. **📄 Clean PDF Presentation (No Captions & Standardized Filenames)**:
   - Files are uploaded as clean PDF documents without captions for distraction-free offline studying.
   - Every file is automatically named with **Subject Name**, **Subject Code**, **Question Set**, and **Year** (e.g. `Mathematics - 121-327 - Set-A - 2026.pdf`).

4. **🗓️ Structured Year Announcement Headers**:
   - Before uploading question papers for any exam year, an introductory index message is posted in the channel detailing the examination year, total papers, and key subjects.
   - Serves as a searchable separator in the Telegram channel feed.

5. **🗃️ SQLite Database (liteSQL with WAL mode)**:
   - Tracks all 205 question papers across 11 examination years (2015–2026).
   - High-concurrency Write-Ahead Logging (WAL) allows the UI and background worker to interact simultaneously with zero database locking conflicts.
   - Records status (`pending`, `uploading`, `sent`, `failed`), Telegram `message_id`, direct PDF CDN URL, file size, and timestamps.

6. **🛡️ Telegram Rate-Limit & Error Handling**:
   - Built-in safe dispatch delay (default 2.5s).
   - Automatically catches HTTP 429 `Retry-After` headers and safely pauses until Telegram lifts the rate limit.
   - Automatic retry mechanism for transient network dropouts.

---

## 📱 Telegram Channel Setup

- **Target Channel:** [@bsebclass12thpyq](https://t.me/bsebclass12thpyq) (or your own channel)
- **Bot Setup:** Add your bot as Administrator to your channel with Post Messages permission.

---

## 🚀 Option 1: Streamlit Community Cloud (Persistent Background Thread)

1. **Log into Streamlit Cloud:** [share.streamlit.io](https://share.streamlit.io/) with your GitHub account.
2. **Create New App:**
   - Repository: `mha93587-beep/bseb-class12th-pyq-telegram-bot`
   - Branch: `main`
   - Main file path: `app.py`
3. **Configure Secrets**:
   - In App Settings ➔ **Secrets**:
     ```toml
     TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
     TELEGRAM_CHAT_ID = "-1003918378426"
     ```
4. Click **Deploy!**
5. Once loaded, click **"⚡ Start Background Dispatch"**.
   > **Note:** You can close your browser tab or lock your phone immediately! The server daemon thread will continue dispatching until all papers are sent.

---

## ⚡ Option 2: GitHub Actions (1-Click Headless Cloud Dispatcher)

1. Go to your GitHub repository:
   `https://github.com/mha93587-beep/bseb-class12th-pyq-telegram-bot`
2. Add your Bot Token to GitHub Secrets:
   - Go to **Settings** ➔ **Secrets and variables** ➔ **Actions** ➔ **New repository secret**
   - Name: `TELEGRAM_BOT_TOKEN`
   - Value: `YOUR_BOT_TOKEN`
3. Go to the **"Actions"** tab.
4. Select **"Dispatch BSEB Class 12th PYQs to Telegram"** in the left sidebar.
5. Click **"Run workflow"**.
   > GitHub's cloud runners will execute the entire dispatch pipeline in the background.

---

## 💻 Local CLI Usage

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. View database statistics
python3 main.py status

# 3. Dispatch papers to Telegram
export TELEGRAM_BOT_TOKEN="YOUR_BOT_TOKEN"
export TELEGRAM_CHAT_ID="-1003918378426"
python3 main.py dispatch --order ASC --delay 2.5
```

---

## 📂 Project Architecture

```
bseb-class12th-pyq-telegram-bot/
├── .github/workflows/
│   └── dispatch.yml        # 1-Click GitHub Actions Background Runner
├── app.py                  # Streamlit Dashboard with Persistent Background Worker
├── crawler.py              # Selfstudys scraper & PDF resolver
├── database.py             # SQLite WAL-mode concurrency layer
├── telegram_dispatcher.py  # Background daemon dispatcher & in-memory PDF streamer
├── main.py                 # CLI interface
├── requirements.txt        # Python dependencies
├── bseb_pyq.db             # Pre-indexed SQLite database
└── README.md               # Documentation
```
