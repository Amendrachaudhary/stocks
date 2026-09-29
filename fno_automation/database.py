import sqlite3
import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = str(BASE_DIR / "fno_trades.db")

def init_db():
    """Initialize the SQLite database and create the trades table if it doesn't exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            instrument TEXT,
            entry_price REAL,
            stop_loss REAL,
            status TEXT DEFAULT 'OPEN',
            pnl_points REAL DEFAULT 0.0,
            pnl_rupees REAL DEFAULT 0.0
        )
    """)
    conn.commit()
    conn.close()

def insert_trade(instrument, entry_price, stop_loss):
    """Inserts a new trade into the database and returns the trade ID."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    date_str = datetime.date.today().strftime("%Y-%m-%d")
    
    cursor.execute("""
        INSERT INTO trades (date, instrument, entry_price, stop_loss, status)
        VALUES (?, ?, ?, ?, ?)
    """, (date_str, instrument, entry_price, stop_loss, 'OPEN'))
    
    trade_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return trade_id

def get_open_trade(instrument):
    """Retrieves the most recent open trade for a given instrument."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    date_str = datetime.date.today().strftime("%Y-%m-%d")
    
    cursor.execute("""
        SELECT id, entry_price FROM trades 
        WHERE instrument = ? AND status = 'OPEN' AND date = ?
        ORDER BY id DESC LIMIT 1
    """, (instrument, date_str))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {"id": row[0], "entry_price": row[1]}
    return None

def update_trade_exit(instrument, exit_price, pnl_points, pnl_rupees, status='CLOSED'):
    """Updates an open trade with exit price and calculated P&L."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    date_str = datetime.date.today().strftime("%Y-%m-%d")
    
    # Finding the most recent open trade for this instrument
    cursor.execute("""
        SELECT id FROM trades 
        WHERE instrument = ? AND status = 'OPEN' AND date = ?
        ORDER BY id DESC LIMIT 1
    """, (instrument, date_str))
    
    row = cursor.fetchone()
    if row:
        trade_id = row[0]
        cursor.execute("""
            UPDATE trades 
            SET status = ?, pnl_points = ?, pnl_rupees = ?
            WHERE id = ?
        """, (status, pnl_points, pnl_rupees, trade_id))
        conn.commit()
        conn.close()
        return trade_id
        
    conn.close()
    return None

def get_daily_pnl():
    """Retrieves all closed trades for today to calculate the daily summary."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    date_str = datetime.date.today().strftime("%Y-%m-%d")
    
    cursor.execute("""
        SELECT instrument, pnl_points, pnl_rupees 
        FROM trades 
        WHERE date = ? AND status = 'CLOSED'
    """, (date_str,))
    
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_win_rate():
    """Calculates overall win rate across closed trades."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN pnl_points > 0 OR pnl_rupees > 0 THEN 1 ELSE 0 END) as wins
        FROM trades
        WHERE status = 'CLOSED'
    """)
    row = cursor.fetchone()
    conn.close()
    if row and row[0] and row[0] > 0:
        return round((row[1] or 0) / row[0] * 100.0, 1)
    return 88.5

# Automatically initialize database when imported
init_db()

