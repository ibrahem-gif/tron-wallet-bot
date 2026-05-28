"""
withdraw.py - نظام السحب التلقائي عبر TRON
يُرسل USDT مباشرة من المحفظة الرئيسية
"""

import os
from typing import Optional, Tuple
from database import (
    get_balance, update_balance, add_transaction, save_withdrawal
)
from tron import send_usdt, is_valid_tron_address

NETWORK_FEE  = float(os.getenv("NETWORK_FEE", "1.0"))
COMMISSION   = float(os.getenv("COMMISSION", "0.2"))
MIN_WITHDRAW = float(os.getenv("MIN_WITHDRAW", "2.0"))

# ─────────────────────────────────────────────
# 🔒 نظام قفل السحب - يمنع Race Condition
# withdraw_locks[telegram_id] = True  →  عملية قيد التنفيذ
# ─────────────────────────────────────────────
withdraw_locks = {}  # type: dict


def is_withdraw_locked(telegram_id):
    # type: (int) -> bool
    """هل يوجد سحب قيد التنفيذ لهذا المستخدم؟"""
    return withdraw_locks.get(telegram_id, False)


def _lock_withdraw(telegram_id):
    # type: (int) -> None
    """قفل السحب للمستخدم - يُستدعى عند بدء العملية"""
    withdraw_locks[telegram_id] = True


def _unlock_withdraw(telegram_id):
    # type: (int) -> None
    """فك قفل السحب - يُستدعى دائماً عند انتهاء العملية (نجاح أو فشل)"""
    withdraw_locks.pop(telegram_id, None)


# ─────────────────────────────────────────────


def validate_withdrawal(telegram_id, address, amount):
    # type: (int, str, float) -> Tuple[bool, str]
    """
    التحقق من صحة طلب السحب.
    يُرجع (True, "") إذا صحيح، أو (False, "رسالة الخطأ")
    """
    # 🔒 تحقق من القفل قبل أي شيء
    if is_withdraw_locked(telegram_id):
        return False, (
            "⏳ لديك عملية سحب قيد المعالجة، "
            "انتظر حتى تنتهي العملية الحالية."
        )

    # التحقق من صحة العنوان
    if not is_valid_tron_address(address):
        return False, (
            "❌ عنوان TRC20 غير صحيح!\n"
            "العنوان يجب أن:\n"
            "• يبدأ بحرف `T`\n"
            "• يكون 34 حرفاً\n"
            "• يكون على شبكة TRON (TRC20)"
        )

    # التحقق من الحد الأدنى
    if amount < MIN_WITHDRAW:
        return False, f"❌ الحد الأدنى للسحب: `{MIN_WITHDRAW} USDT`"

    # التحقق من الرصيد
    total_cost = amount + NETWORK_FEE
    balance = get_balance(telegram_id)

    if balance < total_cost:
        return False, (
            f"❌ *رصيد غير كافٍ*\n\n"
            f"رصيدك: `{balance:.4f} USDT`\n"
            f"المبلغ المطلوب: `{amount:.4f} USDT`\n"
            f"رسوم الشبكة: `{NETWORK_FEE:.4f} USDT`\n"
            f"الإجمالي المطلوب: `{total_cost:.4f} USDT`"
        )

    return True, ""


def process_withdrawal(telegram_id, address, amount):
    # type: (int, str, float) -> Tuple[bool, str, Optional[str]]
    """
    تنفيذ عملية السحب الكاملة:
    1. التحقق من القفل ومنع التكرار
    2. التحقق من الرصيد
    3. خصم المبلغ + رسوم الشبكة
    4. إرسال USDT عبر TRON
    5. تسجيل العملية
    6. فك القفل دائماً في النهاية

    يُرجع: (نجح, رسالة, txid)
    """
    # 🔒 تحقق من القفل - منع الضغط المتكرر
    if is_withdraw_locked(telegram_id):
        return False, (
            "⏳ لديك عملية سحب قيد المعالجة، "
            "انتظر حتى تنتهي العملية الحالية."
        ), None

    # 🔒 اقفل فوراً قبل أي عملية
    _lock_withdraw(telegram_id)

    try:
        total_cost = amount + NETWORK_FEE
        balance = get_balance(telegram_id)

        # تحقق نهائي من الرصيد قبل الخصم
        if balance < total_cost:
            return False, "❌ رصيد غير كافٍ", None

        # خصم الرصيد أولاً (يُمنع من السحب مرتين)
        update_balance(telegram_id, -total_cost)

        # إرسال USDT عبر TRON
        txid = send_usdt(to_address=address, amount_usdt=amount)

        if not txid:
            # فشل الإرسال - أعِد الرصيد للمستخدم
            update_balance(telegram_id, total_cost)
            add_transaction(
                user_id=telegram_id,
                tx_type="سحب",
                amount=amount,
                status="فشل",
                wallet_address=address,
                network_fee=NETWORK_FEE,
                transaction_type="withdrawal",
                transaction_status="failed",
            )
            return False, (
                "❌ فشل إرسال المبلغ من الشبكة.\n"
                "تم إرجاع رصيدك كاملاً.\n"
                "يرجى المحاولة لاحقاً أو التواصل مع الدعم."
            ), None

        # نجح الإرسال - سجّل العملية
        save_withdrawal(telegram_id, address, amount, txid, NETWORK_FEE)
        add_transaction(
            user_id=telegram_id,
            tx_type="سحب",
            amount=amount,
            status="مكتمل",
            txid=txid,
            wallet_address=address,
            network_fee=NETWORK_FEE,
            transaction_type="withdrawal",
            transaction_status="completed",
        )

        new_balance = get_balance(telegram_id)
        success_msg = (
            f"✅ *تم السحب بنجاح!*\n\n"
            f"💸 المبلغ المُرسَل: `{amount:.4f} USDT`\n"
            f"🌐 رسوم الشبكة: `{NETWORK_FEE:.4f} USDT`\n"
            f"📤 العنوان: `{address}`\n"
            f"🔗 TXID: `{txid}`\n\n"
            f"💳 رصيدك المتبقي: `{new_balance:.4f} USDT`\n\n"
            f"⏳ سيُؤكَّد على البلوكتشين خلال دقائق."
        )

        return True, success_msg, txid

    finally:
        # 🔓 فك القفل دائماً - سواء نجح أو فشل أو حدث استثناء
        _unlock_withdraw(telegram_id)


def get_withdrawal_summary(address, amount):
    # type: (str, float) -> str
    """إنشاء ملخص تأكيد السحب للمستخدم"""
    total_cost = amount + NETWORK_FEE
    return (
        f"📤 *تأكيد السحب*\n\n"
        f"📍 العنوان:\n`{address}`\n\n"
        f"💰 المبلغ: `{amount:.4f} USDT`\n"
        f"🌐 رسوم الشبكة: `{NETWORK_FEE:.4f} USDT`\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💳 الإجمالي المخصوم: `{total_cost:.4f} USDT`\n\n"
        f"⚠️ تأكد من صحة العنوان!\n"
        f"العمليات على TRON *لا يمكن التراجع عنها*."
    )