"""
deposit.py - نظام الإيداع التلقائي عبر TRON
يراقب البلوكتشين ويُضيف الرصيد تلقائياً
"""

import os
import time
import random
import threading
from typing import Dict, Optional
from telebot import TeleBot
from database import (
    get_balance, update_balance, add_transaction,
    save_deposit, is_txid_processed, mark_txid_processed,
    get_user
)
from tron import (
    get_recent_trc20_transactions,
    verify_transaction_confirmed,
    sun_to_usdt,
    WALLET_ADDRESS,
)

NETWORK_FEE = float(os.getenv("NETWORK_FEE", "1.0"))
MIN_DEPOSIT  = float(os.getenv("MIN_DEPOSIT", "1.0"))

# قاموس: pending_deposits[telegram_id] = timestamp (وقت بدء انتظار الإيداع)
pending_deposits = {}  # type: Dict[int, float]
DEPOSIT_TIMEOUT = 30 * 60  # 30 دقيقة

# ✅ جديد: قاموس يخزن المبلغ الفريد المتوقع لكل مستخدم
# pending_deposit_amounts[telegram_id] = expected_amount (float)
pending_deposit_amounts = {}  # type: Dict[int, float]

# ✅ جديد: هامش التطابق للمبالغ (للتعامل مع فروق الدقة في الأرقام العشرية)
AMOUNT_MATCH_TOLERANCE = 0.001


def register_pending_deposit(telegram_id):
    # type: (int) -> None
    """تسجيل المستخدم في قائمة انتظار الإيداع"""
    pending_deposits[telegram_id] = time.time()


def cancel_pending_deposit(telegram_id):
    # type: (int) -> None
    """إلغاء انتظار إيداع مستخدم"""
    pending_deposits.pop(telegram_id, None)
    # ✅ جديد: تنظيف المبلغ المتوقع أيضاً
    pending_deposit_amounts.pop(telegram_id, None)


def get_deposit_address():
    # type: () -> str
    """إرجاع عنوان المحفظة الرئيسية للإيداع"""
    return WALLET_ADDRESS


# ✅ دالة جديدة: توليد مبلغ فريد وتسجيله
def generate_unique_deposit_amount(telegram_id, base_amount):
    # type: (int, float) -> float
    """
    يُضيف رقماً عشوائياً صغيراً بين 0.01 و 0.5 على المبلغ الأساسي.
    يتحقق أن المبلغ الناتج غير مستخدم من مستخدم آخر حالياً.
    يعيد المبلغ الفريد ويحفظه.
    """
    max_attempts = 20
    for _ in range(max_attempts):
        # رقم عشوائي بين 0.01 و 0.50 بدقة سنتين
        random_addon = round(random.uniform(0.01, 0.50), 2)
        unique_amount = round(base_amount + random_addon, 2)

        # تحقق أن هذا المبلغ غير مستخدم من مستخدم آخر ينتظر حالياً
        already_used = any(
            uid != telegram_id and abs(amt - unique_amount) <= AMOUNT_MATCH_TOLERANCE
            for uid, amt in pending_deposit_amounts.items()
        )

        if not already_used:
            pending_deposit_amounts[telegram_id] = unique_amount
            return unique_amount

    # في الحالة النادرة جداً: زد النطاق قليلاً
    fallback = round(base_amount + random.uniform(0.51, 0.99), 2)
    pending_deposit_amounts[telegram_id] = fallback
    return fallback


def start_deposit_monitor(bot):
    # type: (TeleBot) -> None
    """
    تشغيل مراقب البلوكتشين في خيط منفصل.
    يفحص كل 30 ثانية المعاملات الواردة الجديدة.
    """
    def _monitor():
        print("[DEPOSIT] ✅ مراقب الإيداع يعمل...")
        while True:
            try:
                _check_new_deposits(bot)
            except Exception as e:
                print(f"[DEPOSIT] خطأ في المراقب: {e}")
            time.sleep(30)

    t = threading.Thread(target=_monitor, daemon=True)
    t.start()


def _check_new_deposits(bot):
    # type: (TeleBot) -> None
    """فحص المعاملات الواردة الجديدة وتحديث الأرصدة"""
    if not pending_deposits:
        return  # لا يوجد مستخدمون ينتظرون - وفّر API calls

    txs = get_recent_trc20_transactions(WALLET_ADDRESS, limit=20)

    for tx in txs:
        txid = tx.get("transaction_id", "")
        if not txid:
            continue

        # تجاهل المعاملات المعالجة مسبقاً
        if is_txid_processed(txid):
            continue

        # تحقق من التأكيد على البلوكتشين
        if not verify_transaction_confirmed(txid):
            continue

        # استخرج بيانات المعاملة
        token_info = tx.get("token_info", {})
        if token_info.get("symbol", "") != "USDT":
            continue

        raw_value = int(tx.get("value", "0"))
        amount_usdt = sun_to_usdt(raw_value)

        if amount_usdt < MIN_DEPOSIT:
            continue  # مبلغ أقل من الحد الأدنى

        from_address = tx.get("from", "")
        to_address   = tx.get("to", "")
        block_ts     = tx.get("block_timestamp", 0) / 1000  # ms → s

        # تحقق أن الوجهة هي محفظتنا
        if to_address != WALLET_ADDRESS:
            continue

        # سجّل المعاملة كمعالجة فوراً (لمنع التكرار)
        mark_txid_processed(txid)

        # ✅ معدّلة: المطابقة الآن تعتمد على المبلغ الفريد أولاً
        matched_user = _match_deposit_to_user(from_address, amount_usdt, block_ts)

        if matched_user:
            # ✅ يُضاف المبلغ الكامل الذي أرسله المستخدم (بما في الرقم العشوائي)
            _credit_deposit(bot, matched_user, amount_usdt, txid, from_address)
        else:
            # إيداع غير مرتبط بمستخدم - سجّله وأخطر الأدمن
            print(f"[DEPOSIT] ⚠️ إيداع غير معروف: {txid} من {from_address} بمبلغ {amount_usdt}")
            _notify_admin_unknown_deposit(bot, txid, from_address, amount_usdt)


def _match_deposit_to_user(from_address, amount, block_ts):
    # type: (str, float, float) -> Optional[int]
    """
    ✅ معدّلة: مطابقة الإيداع بالمبلغ الفريد أولاً.
    إذا تطابق مبلغ مع مستخدم بهامش 0.001 → ربط مباشر.
    إذا لم يوجد تطابق بالمبلغ → FIFO كاحتياط.
    """
    now = time.time()
    # تنظيف المستخدمين منتهي المهلة
    expired = [uid for uid, ts in pending_deposits.items() if now - ts > DEPOSIT_TIMEOUT]
    for uid in expired:
        pending_deposits.pop(uid, None)
        pending_deposit_amounts.pop(uid, None)

    if not pending_deposits:
        return None

    # ✅ أولاً: ابحث عن تطابق بالمبلغ الفريد
    for uid, expected_amount in pending_deposit_amounts.items():
        if uid not in pending_deposits:
            continue
        if abs(amount - expected_amount) <= AMOUNT_MATCH_TOLERANCE:
            return uid

    # ✅ ثانياً: إذا لم يوجد تطابق بالمبلغ (مستخدم أرسل بدون طلب مبلغ)
    # إذا كان هناك مستخدم واحد فقط ينتظر بدون مبلغ محدد: افترض أنه صاحبه
    pending_without_amount = [
        uid for uid in pending_deposits
        if uid not in pending_deposit_amounts
    ]
    if len(pending_without_amount) == 1:
        return pending_without_amount[0]

    # إذا كان هناك أكثر من مستخدم بدون مبلغ: خذ الأقدم (FIFO)
    if pending_without_amount:
        oldest = min(pending_without_amount, key=lambda uid: pending_deposits[uid])
        return oldest

    # لم يُوجد تطابق
    return None


def _credit_deposit(bot, telegram_id, amount, txid, from_address):
    # type: (TeleBot, int, float, str, str) -> None
    """إضافة الرصيد للمستخدم وإشعاره"""
    # تأكد أن المستخدم مسجل
    if not get_user(telegram_id):
        return

    # أضف الرصيد (المبلغ الكامل بما في الرقم العشوائي)
    update_balance(telegram_id, amount)

    # سجّل في قاعدة البيانات
    save_deposit(telegram_id, txid, amount, from_address)
    add_transaction(
        user_id=telegram_id,
        tx_type="إيداع",
        amount=amount,
        status="مكتمل",
        txid=txid,
        wallet_address=from_address,
        transaction_type="deposit",
        transaction_status="completed",
    )

    # أزل من قائمة الانتظار (يشمل المبلغ المتوقع)
    cancel_pending_deposit(telegram_id)

    new_balance = get_balance(telegram_id)

    try:
        bot.send_message(
            telegram_id,
            f"✅ *تم استلام إيداعك!*\n\n"
            f"💰 المبلغ المُضاف: `{amount:.4f} USDT`\n"
            f"💳 رصيدك الجديد: `{new_balance:.4f} USDT`\n"
            f"🔗 TXID: `{txid}`\n\n"
            f"شكراً لاستخدامك خدمتنا! 🎉",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"[DEPOSIT] لم أستطع إرسال إشعار للمستخدم {telegram_id}: {e}")

    # أخطر الأدمن
    admin_id = int(os.getenv("ADMIN_ID", "0"))
    if admin_id:
        try:
            bot.send_message(
                admin_id,
                f"✅ *إيداع مكتمل*\n"
                f"👤 المستخدم: `{telegram_id}`\n"
                f"💰 المبلغ: `{amount:.4f} USDT`\n"
                f"🔗 TXID: `{txid}`",
                parse_mode="Markdown"
            )
        except Exception:
            pass


def _notify_admin_unknown_deposit(bot, txid, from_address, amount):
    # type: (TeleBot, str, str, float) -> None
    """إشعار الأدمن بإيداع غير مرتبط بمستخدم"""
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