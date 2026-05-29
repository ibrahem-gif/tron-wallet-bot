"""
withdraw.py - نظام السحب التلقائي عبر TRON
يُرسل USDT مباشرة من المحفظة الرئيسية
"""

import os
from datetime import datetime, timedelta
from database import (
    get_balance, update_balance_atomic, add_transaction,
    save_withdrawal, save_pending_withdrawal, get_pending_withdrawal,
    clear_pending_withdrawal
)
from tron import send_usdt, is_valid_tron_address

NETWORK_FEE = float(os.getenv("NETWORK_FEE", "1.0"))
COMMISSION = float(os.getenv("COMMISSION", "0.2"))
MIN_WITHDRAW = float(os.getenv("MIN_WITHDRAW", "2.0"))
MAX_WITHDRAW = float(os.getenv("MAX_WITHDRAW", "10000.0"))

def validate_withdrawal(user_id, address, amount):
    """التحقق من صحة طلب السحب"""
    
    # فحص المبلغ (يجب أن يكون موجب)
    if amount <= 0:
        return False, "❌ المبلغ يجب أن يكون أكبر من صفر"
    
    # فحص الحد الأدنى
    if amount < MIN_WITHDRAW:
        return False, f"❌ الحد الأدنى للسحب: `{MIN_WITHDRAW} USDT`"
    
    # فحص الحد الأقصى
    if amount > MAX_WITHDRAW:
        return False, f"❌ الحد الأقصى للسحب: `{MAX_WITHDRAW} USDT`"
    
    # فحص العنوان
    if not is_valid_tron_address(address):
        return False, "❌ عنوان TRC20 غير صحيح!\n• يبدأ بـ `T`\n• طول 34 حرفاً"
    
    # فحص الرصيد
    total_cost = amount + NETWORK_FEE
    balance = get_balance(user_id)
    
    if balance < total_cost:
        return False, (
            f"❌ *رصيد غير كافٍ*\n\n"
            f"رصيدك: `{balance:.4f} USDT`\n"
            f"المبلغ: `{amount:.4f} USDT`\n"
            f"الرسوم: `{NETWORK_FEE:.4f} USDT`\n"
            f"الإجمالي: `{total_cost:.4f} USDT`"
        )
    
    return True, ""

def create_pending_withdrawal(user_id, address, amount):
    """حفظ السحب المعلق"""
    expires_at = (datetime.now() + timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
    save_pending_withdrawal(user_id, address, amount, expires_at)

def get_pending_withdrawal_data(user_id):
    """الحصول على السحب المعلق"""
    data = get_pending_withdrawal(user_id)
    if data:
        address, amount, expires_at = data
        expires = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S")
        if datetime.now() > expires:
            clear_pending_withdrawal(user_id)
            return None
        return address, float(amount), expires
    return None

def clear_pending_withdrawal_data(user_id):
    """حذف السحب المعلق"""
    clear_pending_withdrawal(user_id)

def process_withdrawal(user_id, address, amount):
    """
    تنفيذ عملية السحب الكاملة
    يُرجع: (نجح, رسالة, txid)
    """
    
    # فحص نهائي للرصيد
    total_cost = amount + NETWORK_FEE
    balance = get_balance(user_id)
    
    if balance < total_cost:
        return False, "❌ رصيد غير كافٍ", None
    
    # خصم الرصيد (ذري وآمن)
    if not update_balance_atomic(user_id, -total_cost, min_balance=0):
        return False, "❌ فشل الخصم - قد يكون هناك عملية أخرى قيد التنفيذ", None
    
    # إرسال USDT عبر TRON
    txid = send_usdt(to_address=address, amount_usdt=amount)
    
    if not txid:
        # فشل الإرسال - أعِد الرصيد
        update_balance_atomic(user_id, total_cost, min_balance=0)
        add_transaction(
            user_id=user_id,
            tx_type="سحب",
            amount=amount,
            status="فشل",
            wallet_address=address,
            network_fee=NETWORK_FEE,
            transaction_type="withdrawal",
            transaction_status="failed",
        )
        return False, "❌ فشل إرسال المبلغ من الشبكة.\nتم إرجاع رصيدك كاملاً.", None
    
    # نجح الإرسال - سجّل العملية
    save_withdrawal(user_id, address, amount, txid)
    add_transaction(
        user_id=user_id,
        tx_type="سحب",
        amount=amount,
        status="مكتمل",
        txid=txid,
        wallet_address=address,
        network_fee=NETWORK_FEE,
        transaction_type="withdrawal",
        transaction_status="completed",
    )
    
    new_balance = get_balance(user_id)
    success_msg = (
        f"✅ *تم السحب بنجاح!*\n\n"
        f"💸 المبلغ: `{amount:.4f} USDT`\n"
        f"🌐 الرسوم: `{NETWORK_FEE:.4f} USDT`\n"
        f"📤 العنوان: `{address}`\n"
        f"🔗 TXID: `{txid}`\n\n"
        f"💳 رصيدك المتبقي: `{new_balance:.4f} USDT`\n\n"
        f"⏳ سيُؤكَّد على البلوكتشين خلال دقائق."
    )
    
    return True, success_msg, txid

def get_withdrawal_summary(address, amount):
    """ملخص التأكيد"""
    total_cost = amount + NETWORK_FEE
    return (
        f"📤 *تأكيد السحب*\n\n"
        f"📍 العنوان:\n`{address}`\n\n"
        f"💰 المبلغ: `{amount:.4f} USDT`\n"
        f"🌐 الرسوم: `{NETWORK_FEE:.4f} USDT`\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💳 الإجمالي: `{total_cost:.4f} USDT`\n\n"
        f"⚠️ تأكد من صحة العنوان!\n"
        f"العمليات على TRON *لا يمكن التراجع عنها*."
    )