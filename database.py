import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Any

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bseb_pyq.db")

def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: str = DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cur = conn.cursor()
    # Enable WAL mode for high concurrency between background worker and UI
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA busy_timeout=30000;")
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS years (
            year TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            total_papers INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            header_message_id INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year TEXT NOT NULL,
            raw_title TEXT NOT NULL,
            page_url TEXT UNIQUE NOT NULL,
            pdf_url TEXT,
            clean_filename TEXT NOT NULL,
            subject TEXT,
            code TEXT,
            status TEXT DEFAULT 'pending',
            telegram_message_id INTEGER,
            file_size INTEGER,
            error_message TEXT,
            sent_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (year) REFERENCES years(year)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            level TEXT DEFAULT 'INFO',
            message TEXT NOT NULL
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_papers_year ON papers(year)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_papers_status ON papers(status)")
    conn.commit()
    conn.close()

def upsert_year(year: str, url: str, total_papers: int = 0, status: str = 'pending', db_path: str = DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO years (year, url, total_papers, status, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(year) DO UPDATE SET
            url=excluded.url,
            total_papers=CASE WHEN excluded.total_papers > 0 THEN excluded.total_papers ELSE years.total_papers END,
            updated_at=CURRENT_TIMESTAMP
    """, (year, url, total_papers, status))
    conn.commit()
    conn.close()

def upsert_paper(year: str, raw_title: str, page_url: str, pdf_url: Optional[str], 
                 clean_filename: str, subject: str, code: str, db_path: str = DEFAULT_DB_PATH) -> int:
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO papers (year, raw_title, page_url, pdf_url, clean_filename, subject, code, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
        ON CONFLICT(page_url) DO UPDATE SET
            raw_title=excluded.raw_title,
            clean_filename=excluded.clean_filename,
            subject=excluded.subject,
            code=excluded.code,
            pdf_url=COALESCE(excluded.pdf_url, papers.pdf_url)
    """, (year, raw_title, page_url, pdf_url, clean_filename, subject, code))
    paper_id = cur.lastrowid
    conn.commit()
    conn.close()
    return paper_id

def get_years(db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM years ORDER BY CAST(year AS INTEGER) ASC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def get_year(year: str, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM years WHERE year = ?", (year,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def update_year_status(year: str, status: str, header_message_id: Optional[int] = None, db_path: str = DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cur = conn.cursor()
    if header_message_id is not None:
        cur.execute("""
            UPDATE years 
            SET status = ?, header_message_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE year = ?
        """, (status, header_message_id, year))
    else:
        cur.execute("""
            UPDATE years 
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE year = ?
        """, (status, year))
    conn.commit()
    conn.close()

def get_papers(year: Optional[str] = None, status: Optional[str] = None, 
               search_query: Optional[str] = None, limit: Optional[int] = None, 
               offset: int = 0, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    cur = conn.cursor()
    query = "SELECT * FROM papers WHERE 1=1"
    params = []
    if year:
        query += " AND year = ?"
        params.append(year)
    if status:
        query += " AND status = ?"
        params.append(status)
    if search_query:
        query += " AND (clean_filename LIKE ? OR raw_title LIKE ? OR subject LIKE ? OR code LIKE ?)"
        term = f"%{search_query}%"
        params.extend([term, term, term, term])
    query += " ORDER BY CAST(year AS INTEGER) ASC, clean_filename ASC"
    if limit is not None:
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def get_pending_papers(year: Optional[str] = None, order: str = 'ASC', db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    cur = conn.cursor()
    order_dir = "DESC" if order.upper() == "DESC" else "ASC"
    if year:
        cur.execute(f"""
            SELECT * FROM papers 
            WHERE year = ? AND status IN ('pending', 'failed')
            ORDER BY id ASC
        """, (year,))
    else:
        cur.execute(f"""
            SELECT * FROM papers 
            WHERE status IN ('pending', 'failed')
            ORDER BY CAST(year AS INTEGER) {order_dir}, id ASC
        """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def get_paper_by_id(paper_id: int, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM papers WHERE id = ?", (paper_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def update_paper_pdf_url(paper_id: int, pdf_url: str, db_path: str = DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE papers SET pdf_url = ? WHERE id = ?", (pdf_url, paper_id))
    conn.commit()
    conn.close()

def update_paper_status(paper_id: int, status: str, telegram_message_id: Optional[int] = None,
                        file_size: Optional[int] = None, error_message: Optional[str] = None,
                        db_path: str = DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cur = conn.cursor()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
        UPDATE papers 
        SET status = ?,
            telegram_message_id = COALESCE(?, telegram_message_id),
            file_size = COALESCE(?, file_size),
            error_message = ?,
            sent_at = CASE WHEN ? = 'sent' THEN ? ELSE sent_at END
        WHERE id = ?
    """, (status, telegram_message_id, file_size, error_message, status, now, paper_id))
    conn.commit()
    conn.close()

def get_stats(db_path: str = DEFAULT_DB_PATH) -> Dict[str, Any]:
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM papers")
    total_papers = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM papers WHERE status = 'sent'")
    sent_papers = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM papers WHERE status = 'pending'")
    pending_papers = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM papers WHERE status = 'failed'")
    failed_papers = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT year) FROM papers")
    total_years = cur.fetchone()[0]
    cur.execute("""
        SELECT year, 
               COUNT(*) as total,
               SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as sent,
               SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
               SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
        FROM papers
        GROUP BY year
        ORDER BY CAST(year AS INTEGER) ASC
    """)
    year_stats = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {
        "total_papers": total_papers,
        "sent_papers": sent_papers,
        "pending_papers": pending_papers,
        "failed_papers": failed_papers,
        "total_years": total_years,
        "year_stats": year_stats
    }

def reset_failed(db_path: str = DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE papers SET status = 'pending', error_message = NULL WHERE status = 'failed'")
    conn.commit()
    conn.close()

def add_log(level: str, message: str, db_path: str = DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO logs (level, message) VALUES (?, ?)", (level, message))
    conn.commit()
    conn.close()

def get_recent_logs(limit: int = 50, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows
