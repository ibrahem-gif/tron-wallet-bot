"""
database.py - إدارة قاعدة البيانات SQLite
"""

import sqlite3
from datetime import datetime


DB_PATH = "wallet.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    # جدول المستخدمين
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE,
        username TEXT,
        balance REAL DEFAULT 0.0,
        is_banned INTEGER DEFAULT 0,
        created_at TEXT
    )''')

    # جدول المعاملات الموحّد (إيداع + سحب + تحويل)
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

    # جدول الإيداعات
    c.execute('''CREATE TABLE IF NOT EXISTS deposits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        txid TEXT UNIQUE,
        amount REAL,
        wallet_address TEXT,
        network_fee REAL DEFAULT 0.0,
        transaction_type TEXT DEFAULT "deposit",
        transaction_status TEXT DEFAULT "waiting",
        created_at TEXT
    )''')

    # جدول السحوبات
    c.execute('''CREATE TABLE IF NOT EXISTS withdrawals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        address TEXT,
        amount REAL,
        network_fee REAL DEFAULT 0.0,
        txid TEXT,
        transaction_type TEXT DEFAULT "withdrawal",
        transaction_status TEXT DEFAULT "pending",
        created_at TEXT
    )''')

    # جدول الأزرار المخصصة
    c.execute('''CREATE TABLE IF NOT EXISTS custom_buttons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        type TEXT,
        content TEXT,
        created_at TEXT
    )''')

    # جدول Rate Limiting
    c.execute('''CREATE TABLE IF NOT EXISTS rate_limit (
        user_id INTEGER PRIMARY KEY,
        last_request REAL,
        count INTEGER DEFAULT 0
    )''')

    # جدول تتبع معالجة TXID (لمنع التكرار)
    c.execute('''CREATE TABLE IF NOT EXISTS processed_txids (
        txid TEXT PRIMARY KEY,
        processed_at TEXT
    )''')

    conn.commit()
    conn.close()


# ==================== المستخدمون ====================

def add_user(telegram_id, username):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO users (telegram_id, username, created_at) VALUES (?,?,?)",
            (telegram_id, username or "مجهول", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
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
    return float(result["balance"]) if result else 0.0


def update_balance(telegram_id, amount):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "UPDATE users SET balance = balance + ? WHERE telegram_id=?",
        (amount, telegram_id)
    )
    conn.commit()
    conn.close()


def is_banned(telegram_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT is_banned FROM users WHERE telegram_id=?", (telegram_id,))
    result = c.fetchone()
    conn.close()
    return result["is_banned"] == 1 if result else False


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
    return rows


def get_stats():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as cnt FROM users")
    total_users = c.fetchone()["cnt"]
    c.execute("SELECT COALESCE(SUM(balance),0) as s FROM users")
    total_balance = c.fetchone()["s"]
    c.execute("SELECT COUNT(*) as cnt FROM transactions")
    total_tx = c.fetchone()["cnt"]
    c.execute("SELECT COUNT(*) as cnt FROM users WHERE is_banned=1")
    banned = c.fetchone()["cnt"]
    c.execute("SELECT COALESCE(SUM(amount),0) as s FROM transactions WHERE type='إيداع' AND status='مكتمل'")
    total_deposits = c.fetchone()["s"]
    c.execute("SELECT COALESCE(SUM(amount),0) as s FROM transactions WHERE type='سحب' AND status='مكتمل'")
    total_withdrawals = c.fetchone()["s"]
    conn.close()
    return total_users, total_balance, total_tx, banned, total_deposits, total_withdrawals


# ==================== المعاملات ====================

def add_transaction(user_id, tx_type, amount, status,
                    txid=None, wallet_address=None,
                    commission=0.0, network_fee=0.0,
                    transaction_type=None, transaction_status="pending"):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        '''INSERT INTO transactions
           (user_id, type, amount, commission, network_fee, status,
            txid, wallet_address, transaction_type, transaction_status, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
        (user_id, tx_type, amount, commission, network_fee, status,
         txid, wallet_address, transaction_type or tx_type, transaction_status,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()


def get_transactions(telegram_id, limit=10):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        '''SELECT type, amount, status, txid, wallet_address,
                  network_fee, transaction_status, created_at
           FROM transactions
           WHERE user_id=? ORDER BY created_at DESC LIMIT ?''',
        (telegram_id, limit)
    )
    rows = c.fetchall()
    conn.close()
    return rows


def get_all_transactions(limit=20):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        '''SELECT u.telegram_id, t.type, t.amount, t.status,
                  t.txid, t.network_fee, t.created_at
           FROM transactions t
           JOIN users u ON t.user_id = u.telegram_id
           ORDER BY t.created_at DESC LIMIT ?''',
        (limit,)
    )
    rows = c.fetchall()
    conn.close()
    return rows


# ==================== الإيداعات ====================

def save_deposit(user_id, txid, amount, wallet_address, network_fee=0.0):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute(
            '''INSERT INTO deposits
               (user_id, txid, amount, wallet_address, network_fee, created_at)
               VALUES (?,?,?,?,?,?)''',
            (user_id, txid, amount, wallet_address, network_fee,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()


def get_deposit_by_txid(txid):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM deposits WHERE txid=?", (txid,))
    result = c.fetchone()
    conn.close()
    return result


def update_deposit_status(txid, status):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE deposits SET transaction_status=? WHERE txid=?", (status, txid))
    conn.commit()
    conn.close()


# ==================== السحوبات ====================

def save_withdrawal(user_id, address, amount, txid, network_fee=0.0):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        '''INSERT INTO withdrawals
           (user_id, address, amount, txid, network_fee, transaction_status, created_at)
           VALUES (?,?,?,?,?,"completed",?)''',
        (user_id, address, amount, txid, network_fee,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()


# ==================== TXID المعالجة ====================

def is_txid_processed(txid):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT txid FROM processed_txids WHERE txid=?", (txid,))
    result = c.fetchone()
    conn.close()
    return result is not None


def mark_txid_processed(txid):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO processed_txids (txid, processed_at) VALUES (?,?)",
            (txid, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()


# ==================== Rate Limiting ====================

def check_rate_limit(telegram_id):
    import time
    now = time.time()
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT last_request, count FROM rate_limit WHERE user_id=?", (telegram_id,))
    result = c.fetchone()
    if result:
        last_req = result["last_request"]
        count = result["count"]
        if now - last_req < 2:
            if count >= 5:
                conn.close()
                return False
            c.execute("UPDATE rate_limit SET count=count+1 WHERE user_id=?", (telegram_id,))
        else:
            c.execute(
                "UPDATE rate_limit SET last_request=?, count=1 WHERE user_id=?",
                (now, telegram_id)
            )
    else:
        c.execute(
            "INSERT INTO rate_limit (user_id, last_request, count) VALUES (?,?,1)",
            (telegram_id, now)
        )
    conn.commit()
    conn.close()
    return True


# ==================== الأزرار المخصصة ====================

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
    c.execute(
        "INSERT INTO custom_buttons (name, type, content, created_at) VALUES (?,?,?,?)",
        (name, btn_type, content, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()


def delete_custom_button(btn_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM custom_buttons WHERE id=?", (btn_id,))
    conn.commit()
    conn.close()