"""
deposit.py - نظام الإيداع التلقائي عبر TRON
يراقب البلوكتشين ويُضيف الرصيد تلقائياً
"""

import os
import time
import random
import threading
from datetime import datetime, timedelta
from telebot import TeleBot
from database import (
    update_balance_atomic, add_transaction, save_deposit,
    is_txid_processed, mark_txid_processed, get_user,
    get_user_language
)
from tron import (
    get_recent_trc20_transactions,
    verify_transaction_confirmed,
    sun_to_usdt,
    WALLET_ADDRESS,
)
from i18n import get_text

NETWORK_FEE = float(os.getenv("NETWORK_FEE", "1.0"))
MIN_DEPOSIT = float(os.getenv("MIN_DEPOSIT", "1.0"))
DEPOSIT_TIMEOUT = 30 * 60  # 30 دقيقة
AMOUNT_TOLERANCE = 0.001

# قواميس الانتظار
pending_deposits = {}        # {user_id: timestamp}
pending_deposit_amounts = {} # {user_id: unique_amount}

def get_deposit_address():
    """إرجاع عنوان المحفظة للإيداع"""
    return WALLET_ADDRESS

def register_pending_deposit(user_id):
    """تسجيل المستخدم في قائمة الانتظار"""
    pending_deposits[user_id] = time.time()

def cancel_pending_deposit(user_id):
    """إلغاء انتظار الإيداع"""
    pending_deposits.pop(user_id, None)
    pending_deposit_amounts.pop(user_id, None)

def generate_unique_deposit_amount(user_id, base_amount):
    """
    توليد مبلغ فريد
    يُضيف رقماً عشوائياً صغيراً على المبلغ الأساسي (0.01 - 0.99)
    للتمكن من ربط الإيداع تلقائياً بالمستخدم
    """
    max_attempts = 20
    for _ in range(max_attempts):
        random_addon = round(random.uniform(0.01, 0.50), 2)
        unique_amount = round(base_amount + random_addon, 2)
        
        # تحقق أن المبلغ غير مستخدم من مستخدم آخر
        already_used = any(
            uid != user_id and abs(amt - unique_amount) <= AMOUNT_TOLERANCE
            for uid, amt in pending_deposit_amounts.items()
        )
        
        if not already_used:
            pending_deposit_amounts[user_id] = unique_amount
            return unique_amount
    
    # احتياط: نطاق أوسع
    fallback = round(base_amount + random.uniform(0.51, 0.99), 2)
    pending_deposit_amounts[user_id] = fallback
    return fallback

def start_deposit_monitor(bot):
    """تشغيل مراقب الإيداع في خيط منفصل"""
    def _monitor():
        print("[DEPOSIT] ✅ مراقب الإيداع يعمل...")
        while True:
            try:
                _check_new_deposits(bot)
                _cleanup_expired_deposits(bot)
            except Exception as e:
                print(f"[DEPOSIT] خطأ: {e}")
            time.sleep(30)
    
    t = threading.Thread(target=_monitor, daemon=True)
    t.start()

def _check_new_deposits(bot):
    """فحص المعاملات الواردة الجديدة"""
    if not pending_deposits:
        return
    
    txs = get_recent_trc20_transactions(WALLET_ADDRESS, limit=20)
    
    for tx in txs:
        txid = tx.get("transaction_id", "")
        if not txid:
            continue
        
        # تجاهل المعاملات المعالجة مسبقاً
        if is_txid_processed(txid):
            continue
        
        # تحقق من التأكيد
        if not verify_transaction_confirmed(txid):
            continue
        
        # تحقق من العملة
        token_info = tx.get("token_info", {})
        if token_info.get("symbol", "") != "USDT":
            continue
        
        # احسب المبلغ
        raw_value = int(tx.get("value", "0"))
        amount_usdt = sun_to_usdt(raw_value)
        
        if amount_usdt < MIN_DEPOSIT:
            continue
        
        # تحقق من الوجهة
        to_address = tx.get("to", "")
        if to_address != WALLET_ADDRESS:
            continue
        
        # استخرج المعلومات
        from_address = tx.get("from", "")
        block_ts = tx.get("block_timestamp", 0) / 1000
        
        # سجّل TXID كمعالج فوراً (منع التكرار)
        mark_txid_processed(txid)
        
        # طابق بالمستخدم
        matched_user = _match_deposit_to_user(from_address, amount_usdt, block_ts)
        
        if matched_user:
            _credit_deposit(bot, matched_user, amount_usdt, txid, from_address)
        else:
            print(f"[DEPOSIT] ⚠️ إيداع غير معروف: {txid} من {from_address} بـ {amount_usdt}")
            _notify_admin_unknown_deposit(bot, txid, from_address, amount_usdt)

def _cleanup_expired_deposits(bot):
    """تنظيف الإيداعات المنتهية مع إشعار المستخدم"""
    now = time.time()
    expired = [
        uid for uid, ts in list(pending_deposits.items())
        if now - ts > DEPOSIT_TIMEOUT
    ]
    
    for uid in expired:
        pending_deposits.pop(uid, None)
        expected = pending_deposit_amounts.pop(uid, None)
        
        try:
            lang = get_user_language(uid)
            msg = get_text(lang, "deposit_timeout", amt=expected or 0)
            bot.send_message(uid, msg, parse_mode="Markdown")
        except Exception as e:
            print(f"[DEPOSIT] لم أستطع إرسال إشعار لـ {uid}: {e}")

def _match_deposit_to_user(from_address, amount, block_ts):
    """مطابقة الإيداع بالمبلغ الفريد"""
    now = time.time()
    
    # تنظيف منتهي الصلاحية
    expired = [uid for uid, ts in pending_deposits.items() if now - ts > DEPOSIT_TIMEOUT]
    for uid in expired:
        pending_deposits.pop(uid, None)
        pending_deposit_amounts.pop(uid, None)
    
    if not pending_deposits:
        return None
    
    # ابحث عن تطابق بالمبلغ الفريد
    for uid, expected_amount in pending_deposit_amounts.items():
        if uid not in pending_deposits:
            continue
        if abs(amount - expected_amount) <= AMOUNT_TOLERANCE:
            return uid
    
    return None

def _credit_deposit(bot, user_id, amount, txid, from_address):
    """إضافة الرصيد للمستخدم"""
    # تأكد أن المستخدم مسجل
    if not get_user(user_id):
        return
    
    # أضف الرصيد (ذري وآمن)
    if not update_balance_atomic(user_id, amount, min_balance=0):
        print(f"[DEPOSIT] ❌ فشل إضافة الرصيد لـ {user_id}")
        return
    
    # سجّل في DB
    save_deposit(user_id, txid, amount, from_address)
    add_transaction(
        user_id=user_id,
        tx_type="إيداع",
        amount=amount,
        status="مكتمل",
        txid=txid,
        wallet_address=from_address,
        transaction_type="deposit",
        transaction_status="completed",
    )
    
    # أزل من الانتظار
    cancel_pending_deposit(user_id)
    
    # إرسال إشعار
    try:
        lang = get_user_language(user_id)
        from database import get_balance
        bal = get_balance(user_id)
        msg = get_text(lang, "deposit_success", amt=amount, bal=bal, txid=txid)
        bot.send_message(user_id, msg, parse_mode="Markdown")
    except Exception as e:
        print(f"[DEPOSIT] لم أستطع إرسال إشعار: {e}")
    
    # إخطار الأدمن
    admin_id = int(os.getenv("ADMIN_ID", "0"))
    if admin_id:
        try:
            bot.send_message(
                admin_id,
                f"✅ *إيداع مكتمل*\n"
                f"👤 المستخدم: `{user_id}`\n"
                f"💰 المبلغ: `{amount:.4f} USDT`\n"
                f"🔗 TXID: `{txid}`",
                parse_mode="Markdown"
            )
        except Exception:
            pass

def _notify_admin_unknown_deposit(bot, txid, from_address, amount):
    """إشعار الأدمن بإيداع غير معروف"""
    admin_id = int(os.getenv("ADMIN_ID", "0"))
    if not admin_id:
        return
    try:
        bot.send_message(
            admin_id,
            f"⚠️ *إيداع غير معروف*\n\n"
            f"💰 المبلغ: `{amount:.4f} USDT`\n"
            f"📤 من: `{from_address}`\n"
            f"🔗 TXID: `{txid}`\n\n"
            f"لم يتم ربطه بأي مستخدم تلقائياً.",
            parse_mode="Markdown"
        )
    except Exception:
        pass