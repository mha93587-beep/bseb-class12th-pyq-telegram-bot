import requests
import io
import os
import time
import re
import threading
from datetime import datetime
from typing import Optional, Dict, Any, Callable
import database
import crawler

# Read strictly from environment variables or runtime input
DEFAULT_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
DEFAULT_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "-1003918378426")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
}

def send_year_header(bot_token: str, chat_id: str, year: str, total_papers: int, subjects_summary: str) -> Optional[int]:
    """Sends the introductory index message for a given examination year."""
    if not bot_token or not chat_id:
        database.add_log('ERROR', 'Telegram Bot Token or Chat ID not configured.')
        return None

    text = (
        "📖 *BIHAR SCHOOL EXAMINATION BOARD (BSEB)*\n"
        "🎓 *Class 12th Intermediate Question Papers*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 *EXAMINATION YEAR:* *{year}*\n"
        f"📚 *Total Papers in this Batch:* *{total_papers}*\n"
        f"📑 *Key Subjects:* {subjects_summary}\n\n"
        "ℹ️ *Important Information:*\n"
        f"• All original BSEB Class 12 question papers for year *{year}* follow below.\n"
        "• PDFs are sent cleanly with zero captions for distraction-free offline studying.\n"
        "• Every file is named with Subject Name, Code, and Set for instant search.\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'Markdown',
        'disable_web_page_preview': True
    }
    
    for attempt in range(3):
        try:
            r = requests.post(url, json=payload, timeout=25)
            res = r.json()
            if res.get('ok'):
                msg_id = res['result']['message_id']
                database.update_year_status(year, status='in_progress', header_message_id=msg_id)
                database.add_log('INFO', f'Sent Year {year} header message (id: {msg_id})')
                return msg_id
            elif res.get('error_code') == 429:
                wait_sec = res.get('parameters', {}).get('retry_after', 10) + 1
                database.add_log('WARN', f'Telegram 429 rate limit hit. Waiting {wait_sec}s')
                time.sleep(wait_sec)
            else:
                database.add_log('ERROR', f'Failed to send year header: {res}')
        except Exception as e:
            database.add_log('ERROR', f'Exception sending year header attempt {attempt+1}: {e}')
            time.sleep(3)
            
    return None

def send_paper(bot_token: str, chat_id: str, paper: Dict[str, Any], session: Optional[requests.Session] = None) -> bool:
    """Streams the PDF from Selfstudys directly into Telegram channel with no caption."""
    if not bot_token or not chat_id:
        err = "Telegram Bot Token or Chat ID not configured."
        database.add_log('ERROR', err)
        return False

    s = session or requests.Session()
    paper_id = paper['id']
    clean_filename = paper['clean_filename']
    pdf_url = paper.get('pdf_url')
    
    # Resolve PDF URL if not cached
    if not pdf_url:
        pdf_url = crawler.resolve_pdf_url(paper['page_url'], session=s)
        if pdf_url:
            database.update_paper_pdf_url(paper_id, pdf_url)
        else:
            err = f"Could not extract PDF URL from {paper['page_url']}"
            database.update_paper_status(paper_id, status='failed', error_message=err)
            database.add_log('ERROR', err)
            return False
            
    # Download into RAM buffer (zero disk write)
    database.update_paper_status(paper_id, status='uploading')
    pdf_content = None
    
    for dl_attempt in range(3):
        try:
            r_pdf = s.get(pdf_url, headers=HEADERS, stream=True, timeout=60)
            if r_pdf.status_code == 200:
                pdf_content = r_pdf.content
                break
            else:
                time.sleep(2)
        except Exception as e:
            time.sleep(2)
            
    if not pdf_content:
        err = f"Failed to download PDF stream from {pdf_url}"
        database.update_paper_status(paper_id, status='failed', error_message=err)
        database.add_log('ERROR', err)
        return False
        
    file_size = len(pdf_content)
    
    # Upload directly to Telegram
    tg_url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    for up_attempt in range(3):
        try:
            files = {
                'document': (clean_filename, io.BytesIO(pdf_content), 'application/pdf')
            }
            data = {
                'chat_id': chat_id
            }
            # Strictly NO caption as requested by user
            res = requests.post(tg_url, data=data, files=files, timeout=120)
            resp_json = res.json()
            
            if resp_json.get('ok'):
                msg_id = resp_json['result']['message_id']
                database.update_paper_status(paper_id, status='sent', telegram_message_id=msg_id, file_size=file_size)
                database.add_log('INFO', f"Successfully sent '{clean_filename}' (size: {file_size}B, msg_id: {msg_id})")
                return True
            elif resp_json.get('error_code') == 429:
                wait_sec = resp_json.get('parameters', {}).get('retry_after', 10) + 1
                database.add_log('WARN', f'Telegram 429 rate limit hit. Waiting {wait_sec}s')
                time.sleep(wait_sec)
            else:
                err = f"Telegram API error: {resp_json}"
                database.add_log('ERROR', err)
                if up_attempt == 2:
                    database.update_paper_status(paper_id, status='failed', error_message=err)
        except Exception as e:
            database.add_log('ERROR', f"Upload exception for '{clean_filename}' attempt {up_attempt+1}: {e}")
            time.sleep(3)
            if up_attempt == 2:
                database.update_paper_status(paper_id, status='failed', error_message=str(e))
                
    return False

def dispatch_batch(bot_token: str, chat_id: str, year: Optional[str] = None, order: str = 'ASC',
                   delay: float = 2.5, progress_callback: Optional[Callable[[Dict[str, Any], int, int], None]] = None,
                   is_cancelled: Optional[Callable[[], bool]] = None) -> Dict[str, int]:
    """Dispatches question papers year by year in structured sequence."""
    if not bot_token or not chat_id:
        database.add_log('ERROR', 'Telegram Bot Token or Chat ID not provided for dispatch.')
        return {'sent': 0, 'failed': 0, 'skipped': 0}

    session = requests.Session()
    stats = {'sent': 0, 'failed': 0, 'skipped': 0}
    
    if year:
        year_objs = [y for y in database.get_years() if y['year'] == year]
    else:
        year_objs = database.get_years()
        if order.upper() == 'DESC':
            year_objs = sorted(year_objs, key=lambda x: int(x['year']), reverse=True)
        else:
            year_objs = sorted(year_objs, key=lambda x: int(x['year']), reverse=False)
            
    for y_obj in year_objs:
        curr_year = y_obj['year']
        papers = database.get_papers(year=curr_year)
        pending_papers = [p for p in papers if p['status'] in ('pending', 'failed')]
        
        if not pending_papers:
            database.update_year_status(curr_year, status='completed')
            continue
            
        # Send year header if not already sent
        if not y_obj.get('header_message_id'):
            subjects = list(set(p['subject'] for p in papers if p.get('subject')))
            subj_str = ", ".join(sorted(subjects[:8]))
            if len(subjects) > 8:
                subj_str += f" (+{len(subjects)-8} more)"
                
            send_year_header(bot_token, chat_id, curr_year, len(papers), subj_str)
            time.sleep(delay)
            
        for idx, paper in enumerate(pending_papers):
            if is_cancelled and is_cancelled():
                database.add_log('INFO', 'Dispatch halted by user.')
                return stats
                
            success = send_paper(bot_token, chat_id, paper, session=session)
            if success:
                stats['sent'] += 1
            else:
                stats['failed'] += 1
                
            if progress_callback:
                progress_callback(paper, idx + 1, len(pending_papers))
                
            time.sleep(delay)
            
        remaining = database.get_pending_papers(year=curr_year)
        if not remaining:
            database.update_year_status(curr_year, status='completed')
            database.add_log('INFO', f'Year {curr_year} completed successfully.')
            
    return stats

class BackgroundDispatcherManager:
    """
    Singleton Background Dispatcher that runs in a detached daemon thread.
    Continues running even if browser is closed or WebSocket disconnects!
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(BackgroundDispatcherManager, cls).__new__(cls)
                cls._instance._init_state()
            return cls._instance

    def _init_state(self):
        self.thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.is_running = False
        self.current_filename = ""
        self.current_year = ""
        self.sent_count = 0
        self.failed_count = 0
        self.start_time: Optional[datetime] = None
        self.finish_time: Optional[datetime] = None
        self.status_message = "Idle"

    def start(self, bot_token: str, chat_id: str, year: Optional[str] = None, order: str = 'ASC', delay: float = 2.5):
        with self._lock:
            if self.is_running and self.thread and self.thread.is_alive():
                return False, "Dispatcher is already running in background!"

            self.stop_event.clear()
            self.is_running = True
            self.sent_count = 0
            self.failed_count = 0
            self.start_time = datetime.utcnow()
            self.finish_time = None
            self.status_message = "Starting background dispatch..."

            self.thread = threading.Thread(
                target=self._worker_loop,
                args=(bot_token, chat_id, year, order, delay),
                daemon=True,
                name="BSEB-Background-Dispatcher"
            )
            self.thread.start()
            database.add_log('INFO', 'Background daemon thread launched successfully.')
            return True, "Background dispatcher started!"

    def stop(self):
        with self._lock:
            if self.is_running:
                self.stop_event.set()
                self.status_message = "Stopping dispatcher..."
                database.add_log('INFO', 'Stop signal sent to background dispatcher.')
                return True, "Stop signal sent."
            return False, "Dispatcher is not running."

    def get_info(self) -> Dict[str, Any]:
        with self._lock:
            alive = bool(self.thread and self.thread.is_alive())
            if not alive:
                self.is_running = False
            return {
                "is_running": self.is_running and alive,
                "current_filename": self.current_filename,
                "current_year": self.current_year,
                "sent_count": self.sent_count,
                "failed_count": self.failed_count,
                "status_message": self.status_message,
                "start_time": self.start_time,
                "finish_time": self.finish_time
            }

    def _worker_loop(self, bot_token: str, chat_id: str, year: Optional[str], order: str, delay: float):
        try:
            self.status_message = "Running background dispatch..."
            
            def is_cancelled():
                return self.stop_event.is_set()

            def cb(paper, curr, total):
                self.current_filename = paper['clean_filename']
                self.current_year = paper['year']
                self.status_message = f"Dispatching Year {paper['year']}: {paper['clean_filename']}"

            result = dispatch_batch(
                bot_token=bot_token,
                chat_id=chat_id,
                year=year,
                order=order,
                delay=delay,
                progress_callback=cb,
                is_cancelled=is_cancelled
            )

            self.sent_count = result.get('sent', 0)
            self.failed_count = result.get('failed', 0)
            self.finish_time = datetime.utcnow()
            
            if self.stop_event.is_set():
                self.status_message = f"Paused by user. Sent: {self.sent_count}, Failed: {self.failed_count}"
            else:
                self.status_message = f"Finished successfully! Sent: {self.sent_count}, Failed: {self.failed_count}"

        except Exception as e:
            self.status_message = f"Error in background dispatcher: {e}"
            database.add_log('ERROR', f"Background dispatcher exception: {e}")
        finally:
            self.is_running = False
            self.current_filename = ""
