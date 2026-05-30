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
    get_user_language, get_balance
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
DEPOSIT_TIMEOUT = 30 * 60
AMOUNT_TOLERANCE = 0.001

pending_deposits = {}
pending_deposit_amounts = {}

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
    """توليد مبلغ فريد"""
    max_attempts = 20
    for attempt in range(max_attempts):
        random_addon = round(random.uniform(0.01, 0.50), 2)
        unique_amount = round(base_amount + random_addon, 2)
        
        already_used = False
        for uid, amt in pending_deposit_amounts.items():
            if uid != user_id and abs(amt - unique_amount) <= AMOUNT_TOLERANCE:
                already_used = True
                break
        
        if not already_used:
            pending_deposit_amounts[user_id] = unique_amount
            return unique_amount
    
    fallback = round(base_amount + random.uniform(0.51, 0.99), 2)
    pending_deposit_amounts[user_id] = fallback
    return fallback

def start_deposit_monitor(bot):
    """تشغيل مراقب الإيداع في خيط منفصل"""
    def _monitor():
        print("[DEPOSIT] اشتغال المراقب...")
        while True:
            try:
                _check_new_deposits(bot)
                _cleanup_expired_deposits(bot)
            except Exception as e:
                print("[DEPOSIT] خطأ: {0}".format(str(e)))
            time.sleep(30)
    
    t = threading.Thread(target=_monitor)
    t.daemon = True
    t.start()

def _check_new_deposits(bot):
    """فحص المعاملات الواردة الجديدة"""
    if not pending_deposits:
        return
    
    try:
        txs = get_recent_trc20_transactions(WALLET_ADDRESS, limit=20)
    except Exception:
        return
    
    if not txs:
        return
    
    for tx in txs:
        try:
            txid = tx.get("transaction_id", "")
            if not txid:
                continue
            
            if is_txid_processed(txid):
                continue
            
            if not verify_transaction_confirmed(txid):
                continue
            
            token_info = tx.get("token_info", {})
            if token_info.get("symbol", "") != "USDT":
                continue
            
            raw_value = int(tx.get("value", "0"))
            amount_usdt = sun_to_usdt(raw_value)
            
            if amount_usdt < MIN_DEPOSIT:
                continue
            
            to_address = tx.get("to", "")
            if to_address != WALLET_ADDRESS:
                continue
            
            from_address = tx.get("from", "")
            block_ts = tx.get("block_timestamp", 0) / 1000.0
            
            mark_txid_processed(txid)
            
            matched_user = _match_deposit_to_user(from_address, amount_usdt, block_ts)
            
            if matched_user:
                _credit_deposit(bot, matched_user, amount_usdt, txid, from_address)
            else:
                print("[DEPOSIT] إيداع غير معروف: {0}".format(txid))
                _notify_admin_unknown_deposit(bot, txid, from_address, amount_usdt)
        
        except Exception as e:
            print("[DEPOSIT] خطأ في معاملة: {0}".format(str(e)))
            continue

def _cleanup_expired_deposits(bot):
    """تنظيف الإيداعات المنتهية مع إشعار المستخدم"""
    now = time.time()
    expired_list = []
    
    for uid, ts in list(pending_deposits.items()):
        if now - ts > DEPOSIT_TIMEOUT:
            expired_list.append(uid)
    
    for uid in expired_list:
        pending_deposits.pop(uid, None)
        expected = pending_deposit_amounts.pop(uid, None)
        
        try:
            lang = get_user_language(uid)
            amt_text = "{0:.2f}".format(expected) if expected else "0"
            msg = get_text(lang, "deposit_timeout", amt=amt_text)
            bot.send_message(uid, msg, parse_mode="Markdown")
        except Exception as e:
            print("[DEPOSIT] لم يتمكن من الإرسال: {0}".format(str(e)))

def _match_deposit_to_user(from_address, amount, block_ts):
    """مطابقة الإيداع بالمبلغ الفريد"""
    now = time.time()
    
    expired_list = []
    for uid, ts in list(pending_deposits.items()):
        if now - ts > DEPOSIT_TIMEOUT:
            expired_list.append(uid)
    
    for uid in expired_list:
        pending_deposits.pop(uid, None)
        pending_deposit_amounts.pop(uid, None)
    
    if not pending_deposits:
        return None
    
    for uid, expected_amount in list(pending_deposit_amounts.items()):
        if uid not in pending_deposits:
            continue
        if abs(amount - expected_amount) <= AMOUNT_TOLERANCE:
            return uid
    
    return None

def _credit_deposit(bot, user_id, amount, txid, from_address):
    """إضافة الرصيد للمستخدم"""
    if not get_user(user_id):
        return
    
    if not update_balance_atomic(user_id, amount, min_balance=0):
        print("[DEPOSIT] فشل إضافة الرصيد لـ {0}".format(user_id))
        return
    
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
    
    cancel_pending_deposit(user_id)
    
    try:
        lang = get_user_language(user_id)
        bal = get_balance(user_id)
        msg = get_text(lang, "deposit_success", amt=amount, bal=bal, txid=txid)
        bot.send_message(user_id, msg, parse_mode="Markdown")
    except Exception as e:
        print("[DEPOSIT] لم أستطع إرسال إشعار: {0}".format(str(e)))
    
    admin_id = int(os.getenv("ADMIN_ID", "0"))
    if admin_id:
        try:
            bot.send_message(
                admin_id,
                "✅ *إيداع مكتمل*\n👤 المستخدم: `{0}`\n💰 المبلغ: `{1:.4f} USDT`\n🔗 TXID: `{2}`".format(
                    user_id, amount, txid
                ),
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
            "⚠️ *إيداع غير معروف*\n💰 المبلغ: `{0:.4f} USDT`\n📤 من: `{1}`\n🔗 TXID: `{2}`".format(
                amount, from_address, txid
            ),
            parse_mode="Markdown"
        )
    except Exception:
        pass