"""
database.py - إدارة قاعدة البيانات SQLite
آمن من Race Condition عبر Locks و WAL Mode
"""
import os
import sqlite3
import threading
import time
from datetime import datetime

DB_PATH = "wallet.db"

# 🔐 Lock شامل لحماية العمليات المالية
db_lock = threading.Lock()

def get_conn():
    """فتح اتصال آمن مع WAL mode"""
    conn = sqlite3.connect(
        DB_PATH,
        timeout=10,
        check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

def init_db():
    """إنشاء جداول قاعدة البيانات"""
    conn = get_conn()
    c = conn.cursor()

    # جدول المستخدمين
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE NOT NULL,
        username TEXT,
        balance REAL DEFAULT 0.0 CHECK(balance >= 0),
        is_banned INTEGER DEFAULT 0,
        language TEXT DEFAULT 'ar',
        created_at TEXT
    )''')

    # جدول المعاملات
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
        created_at TEXT
    )''')

    # جدول السحوبات المعلقة (آمن)
    c.execute('''CREATE TABLE IF NOT EXISTS pending_withdrawals (
        user_id INTEGER PRIMARY KEY,
        address TEXT NOT NULL,
        amount REAL NOT NULL,
        expires_at TEXT NOT NULL
    )''')

    # جدول التحويلات المعلقة
    c.execute('''CREATE TABLE IF NOT EXISTS pending_transfers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER,
        receiver_id INTEGER,
        amount REAL,
        commission REAL,
        expires_at TEXT
    )''')

    # جدول السحوبات المنفذة
    c.execute('''CREATE TABLE IF NOT EXISTS withdrawals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        address TEXT,
        amount REAL,
        txid TEXT,
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

    # جدول معالجة TXID
    c.execute('''CREATE TABLE IF NOT EXISTS processed_txids (
        txid TEXT PRIMARY KEY,
        processed_at TEXT
    )''')

    # جدول روابط التواصل
    c.execute('''CREATE TABLE IF NOT EXISTS social_links (
        platform TEXT PRIMARY KEY,
        url TEXT
    )''')

    # إدراج روابط افتراضية
    platforms = ["telegram", "facebook", "instagram", "tiktok", "x", "youtube", "website"]
    for p in platforms:
        try:
            c.execute("INSERT INTO social_links (platform, url) VALUES (?,?)", (p, ""))
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    conn.close()

# ==================== المستخدمون ====================

def add_user(telegram_id, username):
    """إضافة مستخدم جديد"""
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
    """الحصول على بيانات المستخدم"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
    user = c.fetchone()
    conn.close()
    return user

def get_balance(telegram_id):
    """الحصول على رصيد المستخدم"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE telegram_id=?", (telegram_id,))
    result = c.fetchone()
    conn.close()
    return float(result[0]) if result else 0.0

def update_balance_atomic(telegram_id, amount, min_balance=0.0):
    """
    🔐 تحديث ذري آمن للرصيد مع حماية من Race Condition
    يُرجع: True إذا نجح، False إذا فشل
    """
    with db_lock:
        conn = get_conn()
        try:
            c = conn.cursor()
            
            # قراءة الرصيد الحالي
            c.execute("SELECT balance FROM users WHERE telegram_id=?", (telegram_id,))
            result = c.fetchone()
            
            if not result:
                conn.close()
                return False
            
            current_balance = float(result[0])
            new_balance = current_balance + amount
            
            # فحص الحدود
            if new_balance < min_balance or new_balance < 0:
                conn.close()
                return False
            
            # تحديث آمن
            c.execute(
                "UPDATE users SET balance=? WHERE telegram_id=?",
                (new_balance, telegram_id)
            )
            conn.commit()
            return True
            
        except Exception as e:
            print(f"❌ خطأ في تحديث الرصيد: {e}")
            return False
        finally:
            conn.close()

def is_banned(telegram_id):
    """التحقق من حظر المستخدم"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT is_banned FROM users WHERE telegram_id=?", (telegram_id,))
    result = c.fetchone()
    conn.close()
    return result[0] == 1 if result else False

def ban_user(telegram_id):
    """حظر مستخدم"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned=1 WHERE telegram_id=?", (telegram_id,))
    conn.commit()
    conn.close()

def unban_user(telegram_id):
    """إلغاء حظر مستخدم"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned=0 WHERE telegram_id=?", (telegram_id,))
    conn.commit()
    conn.close()

def get_all_users():
    """الحصول على جميع المستخدمين"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT telegram_id FROM users WHERE is_banned=0")
    rows = c.fetchall()
    conn.close()
    return [row[0] for row in rows]

def get_stats():
    """الحصول على إحصائيات"""
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
    """تعيين لغة المستخدم"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET language=? WHERE telegram_id=?", (lang, telegram_id))
    conn.commit()
    conn.close()

def get_user_language(telegram_id):
    """الحصول على لغة المستخدم"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT language FROM users WHERE telegram_id=?", (telegram_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else "ar"

# ==================== المعاملات ====================

def add_transaction(user_id, tx_type, amount, status, txid=None, wallet_address=None, 
                   commission=0.0, network_fee=0.0, transaction_type=None, transaction_status="pending"):
    """إضافة معاملة"""
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
    """الحصول على معاملات المستخدم"""
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
    """الحصول على آخر المعاملات"""
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        '''SELECT telegram_id, type, amount, status, txid, network_fee, created_at
           FROM transactions
           ORDER BY created_at DESC LIMIT ?''',
        (limit,)
    )
    rows = c.fetchall()
    conn.close()
    return rows

# ==================== الإيداعات ====================

def save_deposit(user_id, txid, amount, wallet_address):
    """حفظ إيداع"""
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute(
            '''INSERT INTO deposits
               (user_id, txid, amount, wallet_address, created_at)
               VALUES (?,?,?,?,?)''',
            (user_id, txid, amount, wallet_address,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()

def is_txid_processed(txid):
    """التحقق من معالجة TXID"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT 1 FROM processed_txids WHERE txid=?", (txid,))
    result = c.fetchone()
    conn.close()
    return result is not None

def mark_txid_processed(txid):
    """تسجيل TXID كمعالج"""
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

# ==================== السحوبات المعلقة ====================

def save_pending_withdrawal(user_id, address, amount, expires_at):
    """حفظ سحب معلق"""
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        '''INSERT OR REPLACE INTO pending_withdrawals (user_id, address, amount, expires_at)
           VALUES (?,?,?,?)''',
        (user_id, address, amount, expires_at)
    )
    conn.commit()
    conn.close()

def get_pending_withdrawal(user_id):
    """الحصول على سحب معلق"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT address, amount, expires_at FROM pending_withdrawals WHERE user_id=?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result

def clear_pending_withdrawal(user_id):
    """حذف سحب معلق"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM pending_withdrawals WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

# ==================== التحويلات المعلقة ====================

def save_pending_transfer(sender_id, receiver_id, amount, commission, expires_at):
    """حفظ تحويل معلق"""
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        '''INSERT INTO pending_transfers (sender_id, receiver_id, amount, commission, expires_at)
           VALUES (?,?,?,?,?)''',
        (sender_id, receiver_id, amount, commission, expires_at)
    )
    conn.commit()
    c.execute("SELECT last_insert_rowid()")
    transfer_id = c.fetchone()[0]
    conn.close()
    return transfer_id

def get_pending_transfer(transfer_id):
    """الحصول على تحويل معلق"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT sender_id, receiver_id, amount, commission, expires_at FROM pending_transfers WHERE id=?", (transfer_id,))
    result = c.fetchone()
    conn.close()
    return result

def clear_pending_transfer(transfer_id):
    """حذف تحويل معلق"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM pending_transfers WHERE id=?", (transfer_id,))
    conn.commit()
    conn.close()

# ==================== السحوبات المنفذة ====================

def save_withdrawal(user_id, address, amount, txid):
    """حفظ سحب منفذ"""
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        '''INSERT INTO withdrawals
           (user_id, address, amount, txid, created_at)
           VALUES (?,?,?,?,?)''',
        (user_id, address, amount, txid,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()

# ==================== Rate Limiting ====================

def check_rate_limit(telegram_id, max_requests=5, time_window=2):
    """فحص Rate Limit"""
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
    """الحصول على الأزرار"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM custom_buttons ORDER BY id")
    rows = c.fetchall()
    conn.close()
    return rows

def add_custom_button(name, btn_type, content):
    """إضافة زر"""
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO custom_buttons (name, type, content, created_at) VALUES (?,?,?,?)",
        (name, btn_type, content, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()

def delete_custom_button(btn_id):
    """حذف زر"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM custom_buttons WHERE id=?", (btn_id,))
    conn.commit()
    conn.close()

# ==================== روابط التواصل ====================

def get_social_link(platform):
    """الحصول على رابط"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT url FROM social_links WHERE platform=?", (platform,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else ""

def update_social_link(platform, url):
    """تحديث رابط"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE social_links SET url=? WHERE platform=?", (url, platform))
    conn.commit()
    conn.close()

def get_all_social_links():
    """الحصول على جميع الروابط"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT platform, url FROM social_links ORDER BY platform")
    rows = c.fetchall()
    conn.close()
    return rows