"""
database.py - إدارة قاعدة البيانات SQLite
متوافق مع Python 3.8.2
"""
import os
import sqlite3
import threading
import time
from datetime import datetime

DB_PATH = "wallet.db"
db_lock = threading.Lock()

def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE NOT NULL,
        username TEXT,
        balance REAL DEFAULT 0.0 CHECK(balance >= 0),
        is_banned INTEGER DEFAULT 0,
        language TEXT DEFAULT 'ar',
        created_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        type TEXT,
        amount REAL,
        commission REAL DEFAULT 0.0,
        network_fee REAL DEFAULT 0.0,
        status TEXT,
        txid TEXT,
        wallet_address TEXT,
        transaction_type TEXT,
        transaction_status TEXT DEFAULT "pending",
        created_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS deposits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        txid TEXT UNIQUE,
        amount REAL,
        wallet_address TEXT,
        created_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS pending_withdrawals (
        user_id INTEGER PRIMARY KEY,
        address TEXT NOT NULL,
        amount REAL NOT NULL,
        expires_at TEXT NOT NULL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS pending_transfers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER,
        receiver_id INTEGER,
        amount REAL,
        commission REAL,
        expires_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS withdrawals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        address TEXT,
        amount REAL,
        txid TEXT,
        created_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS custom_buttons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        type TEXT,
        content TEXT,
        created_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS rate_limit (
        user_id INTEGER PRIMARY KEY,
        last_request REAL,
        count INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS processed_txids (
        txid TEXT PRIMARY KEY,
        processed_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS social_links (
        platform TEXT PRIMARY KEY,
        url TEXT
    )''')
    platforms = ["telegram", "facebook", "instagram", "tiktok", "x", "youtube", "website"]
    for p in platforms:
        try:
            c.execute("INSERT INTO social_links (platform, url) VALUES (?,?)", (p, ""))
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()

def add_user(telegram_id, username):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (telegram_id, username, created_at) VALUES (?,?,?)",
            (telegram_id, username or "مجهول", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()

def get_user(telegram_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
    user = c.fetchone()
    conn.close()
    return user

def get_balance(telegram_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE telegram_id=?", (telegram_id,))
    result = c.fetchone()
    conn.close()
    return float(result[0]) if result else 0.0

def update_balance_atomic(telegram_id, amount, min_balance=0.0):
    with db_lock:
        conn = get_conn()
        try:
            c = conn.cursor()
            c.execute("SELECT balance FROM users WHERE telegram_id=?", (telegram_id,))
            result = c.fetchone()
            if not result:
                conn.close()
                return False
            current_balance = float(result[0])
            new_balance = current_balance + amount
            if new_balance < min_balance or new_balance < 0:
                conn.close()
                return False
            c.execute("UPDATE users SET balance=? WHERE telegram_id=?", (new_balance, telegram_id))
            conn.commit()
            return True
        except Exception as e:
            print("خطأ: {0}".format(str(e)))
            return False
        finally:
            conn.close()

def is_banned(telegram_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT is_banned FROM users WHERE telegram_id=?", (telegram_id,))
    result = c.fetchone()
    conn.close()
    return result[0] == 1 if result else False

def ban_user(telegram_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned=1 WHERE telegram_id=?", (telegram_id,))
    conn.commit()
    conn.close()

def unban_user(telegram_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned=0 WHERE telegram_id=?", (telegram_id,))
    conn.commit()
    conn.close()

def get_all_users():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT telegram_id FROM users WHERE is_banned=0")
    rows = c.fetchall()
    conn.close()
    return [row[0] for row in rows]

def get_stats():
    with db_lock:
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        c.execute("SELECT COALESCE(SUM(balance),0) FROM users")
        total_balance = float(c.fetchone()[0])
        c.execute("SELECT COUNT(*) FROM transactions")
        total_tx = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users WHERE is_banned=1")
        banned = c.fetchone()[0]
        c.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type='إيداع' AND status='مكتمل'")
        total_deposits = float(c.fetchone()[0])
        c.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type='سحب' AND status='مكتمل'")
        total_withdrawals = float(c.fetchone()[0])
        conn.close()
        return total_users, total_balance, total_tx, banned, total_deposits, total_withdrawals

def set_user_language(telegram_id, lang):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET language=? WHERE telegram_id=?", (lang, telegram_id))
    conn.commit()
    conn.close()

def get_user_language(telegram_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT language FROM users WHERE telegram_id=?", (telegram_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else "ar"

def add_transaction(user_id, tx_type, amount, status, txid=None, wallet_address=None, 
                   commission=0.0, network_fee=0.0, transaction_type=None, transaction_status="pending"):
    conn = get_conn()
    c = conn.cursor()
    c.execute('''INSERT INTO transactions
        (user_id, type, amount, commission, network_fee, status, txid, wallet_address, 
         transaction_type, transaction_status, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
        (user_id, tx_type, amount, commission, network_fee, status, txid, wallet_address,
         transaction_type or tx_type, transaction_status, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def get_transactions(telegram_id, limit=10):
    conn = get_conn()
    c = conn.cursor()
    c.execute('''SELECT type, amount, status, txid, wallet_address, network_fee, 
                 transaction_status, created_at FROM transactions
                 WHERE user_id=? ORDER BY created_at DESC LIMIT ?''', (telegram_id, limit))
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_transactions(limit=20):
    conn = get_conn()
    c = conn.cursor()
    c.execute('''SELECT telegram_id, type, amount, status, txid, network_fee, created_at
                 FROM transactions ORDER BY created_at DESC LIMIT ?''', (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

def save_deposit(user_id, txid, amount, wallet_address):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute('''INSERT INTO deposits (user_id, txid, amount, wallet_address, created_at)
                     VALUES (?,?,?,?,?)''',
            (user_id, txid, amount, wallet_address, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()

def is_txid_processed(txid):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT 1 FROM processed_txids WHERE txid=?", (txid,))
    result = c.fetchone()
    conn.close()
    return result is not None

def mark_txid_processed(txid):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO processed_txids (txid, processed_at) VALUES (?,?)",
            (txid, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()

def save_pending_withdrawal(user_id, address, amount, expires_at):
    conn = get_conn()
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO pending_withdrawals (user_id, address, amount, expires_at)
                 VALUES (?,?,?,?)''', (user_id, address, amount, expires_at))
    conn.commit()
    conn.close()

def get_pending_withdrawal(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT address, amount, expires_at FROM pending_withdrawals WHERE user_id=?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result

def clear_pending_withdrawal(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM pending_withdrawals WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def save_pending_transfer(sender_id, receiver_id, amount, commission, expires_at):
    conn = get_conn()
    c = conn.cursor()
    c.execute('''INSERT INTO pending_transfers (sender_id, receiver_id, amount, commission, expires_at)
                 VALUES (?,?,?,?,?)''', (sender_id, receiver_id, amount, commission, expires_at))
    conn.commit()
    c.execute("SELECT last_insert_rowid()")
    transfer_id = c.fetchone()[0]
    conn.close()
    return transfer_id

def get_pending_transfer(transfer_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT sender_id, receiver_id, amount, commission, expires_at FROM pending_transfers WHERE id=?", (transfer_id,))
    result = c.fetchone()
    conn.close()
    return result

def clear_pending_transfer(transfer_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM pending_transfers WHERE id=?", (transfer_id,))
    conn.commit()
    conn.close()

def save_withdrawal(user_id, address, amount, txid):
    conn = get_conn()
    c = conn.cursor()
    c.execute('''INSERT INTO withdrawals (user_id, address, amount, txid, created_at)
                 VALUES (?,?,?,?,?)''',
        (user_id, address, amount, txid, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def check_rate_limit(telegram_id, max_requests=5, time_window=2):
    now = time.time()
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT last_request, count FROM rate_limit WHERE user_id=?", (telegram_id,))
    result = c.fetchone()
    if result:
        last_req, count = result
        if now - last_req < time_window:
            if count >= max_requests:
                conn.close()
                return False
            c.execute("UPDATE rate_limit SET count=count+1 WHERE user_id=?", (telegram_id,))
        else:
            c.execute("UPDATE rate_limit SET last_request=?, count=1 WHERE user_id=?", (now, telegram_id))
    else:
        c.execute("INSERT INTO rate_limit (user_id, last_request, count) VALUES (?,?,1)", (telegram_id, now))
    conn.commit()
    conn.close()
    return True

def get_custom_buttons():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM custom_buttons ORDER BY id")
    rows = c.fetchall()
    conn.close()
    return rows

def add_custom_button(name, btn_type, content):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO custom_buttons (name, type, content, created_at) VALUES (?,?,?,?)",
        (name, btn_type, content, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def delete_custom_button(btn_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM custom_buttons WHERE id=?", (btn_id,))
    conn.commit()
    conn.close()

def get_social_link(platform):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT url FROM social_links WHERE platform=?", (platform,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else ""

def update_social_link(platform, url):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE social_links SET url=? WHERE platform=?", (url, platform))
    conn.commit()
    conn.close()

def get_all_social_links():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT platform, url FROM social_links ORDER BY platform")
    rows = c.fetchall()
    conn.close()
    return rows

def get_advanced_stats():
    with db_lock:
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        c.execute("SELECT COUNT(DISTINCT user_id) FROM transactions WHERE created_at >= datetime('now', '-30 days')")
        active_users = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', 'start of day')")
        new_today = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', '-7 days')")
        new_week = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', 'start of month')")
        new_month = c.fetchone()[0]
        c.execute("SELECT COALESCE(SUM(balance),0) FROM users")
        total_balance = float(c.fetchone()[0])
        c.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type='إيداع' AND status='مكتمل'")
        total_deposits = float(c.fetchone()[0])
        c.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type='سحب' AND status='مكتمل'")
        total_withdrawals = float(c.fetchone()[0])
        c.execute("SELECT COUNT(*) FROM transactions WHERE type='إيداع' AND status='مكتمل'")
        deposit_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM transactions WHERE type='سحب' AND status='مكتمل'")
        withdrawal_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users WHERE is_banned=1")
        banned_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM pending_withdrawals")
        pending_withdrawals = c.fetchone()[0]
        conn.close()
        return {'total_users': total_users, 'active_users': active_users, 'new_today': new_today, 
                'new_week': new_week, 'new_month': new_month, 'total_balance': total_balance,
                'total_deposits': total_deposits, 'total_withdrawals': total_withdrawals,
                'deposit_count': deposit_count, 'withdrawal_count': withdrawal_count,
                'banned_count': banned_count, 'pending_withdrawals': pending_withdrawals}

def get_user_details(telegram_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
    user = c.fetchone()
    if not user:
        conn.close()
        return None
    c.execute("SELECT COALESCE(SUM(amount),0), COUNT(*) FROM transactions WHERE user_id=? AND type='إيداع' AND status='مكتمل'", (telegram_id,))
    deposit_row = c.fetchone()
    deposit_total = float(deposit_row[0]) if deposit_row else 0.0
    deposit_count = deposit_row[1] if deposit_row else 0
    c.execute("SELECT COALESCE(SUM(amount),0), COUNT(*) FROM transactions WHERE user_id=? AND type='سحب' AND status='مكتمل'", (telegram_id,))
    withdrawal_row = c.fetchone()
    withdrawal_total = float(withdrawal_row[0]) if withdrawal_row else 0.0
    withdrawal_count = withdrawal_row[1] if withdrawal_row else 0
    c.execute("SELECT MAX(created_at) FROM transactions WHERE user_id=?", (telegram_id,))
    last_activity_row = c.fetchone()
    last_activity = last_activity_row[0] if last_activity_row and last_activity_row[0] else "لا يوجد"
    conn.close()
    return {'telegram_id': user[1], 'username': user[2] or "لا يوجد", 'balance': float(user[3]),
            'is_banned': user[4] == 1, 'language': user[5], 'created_at': user[6],
            'deposit_total': deposit_total, 'deposit_count': deposit_count,
            'withdrawal_total': withdrawal_total, 'withdrawal_count': withdrawal_count,
            'last_activity': last_activity}

def get_all_users_paginated(page=1, per_page=10):
    conn = get_conn()
    c = conn.cursor()
    offset = (page - 1) * per_page
    c.execute("SELECT telegram_id, username FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?", (per_page, offset))
    users = c.fetchall()
    c.execute("SELECT COUNT(*) FROM users")
    total = c.fetchone()[0]
    total_pages = (total + per_page - 1) // per_page
    conn.close()
    return users, total_pages

def search_users(query):
    conn = get_conn()
    c = conn.cursor()
    if query.isdigit():
        c.execute("SELECT telegram_id, username FROM users WHERE telegram_id=?", (int(query),))
    else:
        c.execute("SELECT telegram_id, username FROM users WHERE username LIKE ? OR telegram_id LIKE ?",
            ("%{0}%".format(query), "%{0}%".format(query)))
    results = c.fetchall()
    conn.close()
    return results

def delete_user_completely(telegram_id):
    with db_lock:
        conn = get_conn()
        c = conn.cursor()
        try:
            c.execute("DELETE FROM users WHERE telegram_id=?", (telegram_id,))
            c.execute("DELETE FROM transactions WHERE user_id=?", (telegram_id,))
            c.execute("DELETE FROM deposits WHERE user_id=?", (telegram_id,))
            c.execute("DELETE FROM withdrawals WHERE user_id=?", (telegram_id,))
            c.execute("DELETE FROM pending_withdrawals WHERE user_id=?", (telegram_id,))
            c.execute("DELETE FROM rate_limit WHERE user_id=?", (telegram_id,))
            conn.commit()
            return True
        except Exception as e:
            print("خطأ: {0}".format(str(e)))
            return False
        finally:
            conn.close()

def reset_user_balance(telegram_id):
    with db_lock:
        conn = get_conn()
        c = conn.cursor()
        c.execute("UPDATE users SET balance=0 WHERE telegram_id=?", (telegram_id,))
        conn.commit()
        conn.close()

def get_recent_deposits(limit=10):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT d.user_id, d.amount, d.created_at, u.username FROM deposits d 
                 LEFT JOIN users u ON d.user_id = u.telegram_id ORDER BY d.created_at DESC LIMIT ?""", (limit,))
    results = c.fetchall()
    conn.close()
    return results

def get_recent_withdrawals(limit=10):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT w.user_id, w.amount, w.created_at, u.username FROM withdrawals w 
                 LEFT JOIN users u ON w.user_id = u.telegram_id ORDER BY w.created_at DESC LIMIT ?""", (limit,))
    results = c.fetchall()
    conn.close()
    return results

def get_recent_users(limit=10):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT telegram_id, username, created_at FROM users ORDER BY created_at DESC LIMIT ?", (limit,))
    results = c.fetchall()
    conn.close()
    return results

def get_user_transactions_detailed(telegram_id, limit=20):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT type, amount, status, txid, wallet_address, network_fee, created_at 
                 FROM transactions WHERE user_id=? ORDER BY created_at DESC LIMIT ?""", (telegram_id, limit))
    results = c.fetchall()
    conn.close()
    return results