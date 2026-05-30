"""
bot.py - البوت الرئيسي الكامل
محفظة USDT TRC20 آمنة واحترافية
"""

import os
import random
import string
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

import telebot
from telebot import types

from database import (
    init_db, add_user, get_user, get_balance,
    update_balance_atomic, add_transaction, get_transactions,
    is_banned, check_rate_limit, get_custom_buttons,
    get_user_language, set_user_language, get_all_users,
    get_all_social_links, save_pending_transfer, get_pending_transfer,
    clear_pending_transfer
)
from deposit import (
    get_deposit_address, register_pending_deposit,
    cancel_pending_deposit, start_deposit_monitor,
    generate_unique_deposit_amount
)
from withdraw import (
    validate_withdrawal, create_pending_withdrawal,
    get_pending_withdrawal_data, clear_pending_withdrawal_data,
    process_withdrawal, get_withdrawal_summary
)
from tron import is_valid_tron_address
from i18n import get_text

# ==================== CONFIG ====================
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
COMMISSION = float(os.getenv("COMMISSION", "0.2"))
MIN_WITHDRAW = float(os.getenv("MIN_WITHDRAW", "2.0"))
MIN_DEPOSIT = float(os.getenv("MIN_DEPOSIT", "1.0"))

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN غير محدد في .env")

bot = telebot.TeleBot(BOT_TOKEN)
init_db()
start_deposit_monitor(bot)

# ==================== MENUS ====================

def main_menu(lang) -> types.ReplyKeyboardMarkup:
    """القائمة الرئيسية"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton(get_text(lang, "btn_wallet")),
        types.KeyboardButton(get_text(lang, "btn_profile"))
    )
    markup.add(
        types.KeyboardButton(get_text(lang, "btn_support")),
        types.KeyboardButton(get_text(lang, "btn_settings"))
    )
    markup.add(types.KeyboardButton(get_text(lang, "btn_follow")))
    
    # أزرار مخصصة
    for btn in get_custom_buttons():
        markup.add(types.KeyboardButton(btn[1]))
    
    return markup

def wallet_menu(lang) -> types.ReplyKeyboardMarkup:
    """قائمة المحفظة"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton(get_text(lang, "btn_deposit")),
        types.KeyboardButton(get_text(lang, "btn_withdraw"))
    )
    markup.add(
        types.KeyboardButton(get_text(lang, "btn_balance")),
        types.KeyboardButton(get_text(lang, "btn_transfer"))
    )
    markup.add(
        types.KeyboardButton(get_text(lang, "btn_history")),
        types.KeyboardButton(get_text(lang, "btn_back"))
    )
    return markup

def settings_menu(lang) -> types.InlineKeyboardMarkup:
    """قائمة الإعدادات"""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(get_text(lang, "btn_language"), callback_data="settings_lang"))
    return markup

def languages_menu(lang) -> types.InlineKeyboardMarkup:
    """قائمة اللغات"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(get_text(lang, "lang_ar"), callback_data="lang_ar"),
        types.InlineKeyboardButton(get_text(lang, "lang_en"), callback_data="lang_en")
    )
    markup.add(
        types.InlineKeyboardButton(get_text(lang, "lang_fr"), callback_data="lang_fr"),
        types.InlineKeyboardButton(get_text(lang, "lang_de"), callback_data="lang_de")
    )
    markup.add(
        types.InlineKeyboardButton(get_text(lang, "lang_es"), callback_data="lang_es"),
        types.InlineKeyboardButton(get_text(lang, "lang_hi"), callback_data="lang_hi")
    )
    markup.add(types.InlineKeyboardButton(get_text(lang, "lang_zh"), callback_data="lang_zh"))
    return markup

def follow_menu(lang) -> types.InlineKeyboardMarkup:
    """قائمة المتابعة"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    links = get_all_social_links()
    for platform, url in links:
        if url:
            display_name = platform.upper()
            markup.add(types.InlineKeyboardButton(display_name, url=url))
    return markup

def guard(msg) -> bool:
    """حماية مشتركة"""
    uid = msg.from_user.id
    lang = get_user_language(uid)
    
    if is_banned(uid):
        bot.send_message(msg.chat.id, get_text(lang, "error_banned"))
        return False
    
    if not check_rate_limit(uid):
        bot.send_message(msg.chat.id, get_text(lang, "error_rate_limit"))
        return False
    
    return True

# ==================== START ====================

@bot.message_handler(commands=["start"])
def start(msg):
    uid = msg.from_user.id
    add_user(uid, msg.from_user.username)
    
    if not guard(msg):
        return
    
    lang = get_user_language(uid)
    
    # أدمن
    if uid == ADMIN_ID:
        from admin import admin_inline_menu
        bot.send_message(
            msg.chat.id,
            "👑 لوحة الأدمن",
            reply_markup=admin_inline_menu()
        )
        return
    
    # مستخدم عادي
    welcome_msg = get_text(lang, "welcome", name=msg.from_user.first_name)
    bot.send_message(msg.chat.id, welcome_msg, parse_mode="Markdown", reply_markup=main_menu(lang))

# ==================== WALLET ====================

@bot.message_handler(func=lambda m: m.text and m.text.startswith("💼"))
def wallet(msg):
    if not guard(msg):
        return
    
    uid = msg.from_user.id
    lang = get_user_language(uid)
    bal = get_balance(uid)
    
    text = f"{get_text(lang, 'wallet_title')}\n\n💰 `{bal:.4f} USDT`"
    bot.send_message(msg.chat.id, text, parse_mode="Markdown", reply_markup=wallet_menu(lang))

@bot.message_handler(func=lambda m: m.text and m.text.startswith("💰"))
def balance(msg):
    uid = msg.from_user.id
    lang = get_user_language(uid)
    
    if is_banned(uid):
        return
    
    bal = get_balance(uid)
    text = f"{get_text(lang, 'balance_title')}\n\n`{bal:.4f} USDT`"
    bot.send_message(msg.chat.id, text, parse_mode="Markdown")

# ==================== DEPOSIT ====================

@bot.message_handler(func=lambda m: m.text and m.text.startswith("📥"))
def deposit(msg):
    if not guard(msg):
        return
    
    uid = msg.from_user.id
    lang = get_user_language(uid)
    addr = get_deposit_address()
    
    if not addr:
        bot.send_message(msg.chat.id, "❌ خطأ في الإعدادات")
        return
    
    text = get_text(lang, "deposit_amount_req", min_dep=MIN_DEPOSIT)
    bot.send_message(msg.chat.id, text, parse_mode="Markdown")
    bot.register_next_step_handler(msg, lambda m: _handle_deposit_amount(m, addr, lang))

def _handle_deposit_amount(msg, addr, lang):
    """معالجة مبلغ الإيداع"""
    if msg.text in get_text(lang, "btn_back"):
        bot.process_new_messages([msg])
        return
    
    try:
        base_amt = float(msg.text.strip().replace(",", "."))
    except ValueError:
        bot.send_message(msg.chat.id, get_text(lang, "error_invalid_amount"))
        bot.register_next_step_handler(msg, lambda m: _handle_deposit_amount(m, addr, lang))
        return
    
    if base_amt < MIN_DEPOSIT:
        bot.send_message(msg.chat.id, f"❌ الحد الأدنى: `{MIN_DEPOSIT} USDT`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, lambda m: _handle_deposit_amount(m, addr, lang))
        return
    
    uid = msg.from_user.id
    unique_amt = generate_unique_deposit_amount(uid, base_amt)
    register_pending_deposit(uid)
    
    text = get_text(lang, "deposit_address_show", addr=addr, amt=unique_amt)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(get_text(lang, "btn_check"), callback_data=f"check_dep_{uid}"))
    
    bot.send_message(msg.chat.id, text, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("check_dep_"))
def check_deposit(call):
    uid = int(call.data.split("_")[2])
    
    if call.from_user.id != uid:
        bot.answer_callback_query(call.id, "❌ هذا ليس طلبك!")
        return
    
    lang = get_user_language(uid)
    bot.answer_callback_query(call.id, "✅ تم")
    bot.send_message(call.message.chat.id, "⏳ النظام يراقب تلقائياً كل 30 ثانية.", parse_mode="Markdown")

# ==================== WITHDRAW ====================

@bot.message_handler(func=lambda m: m.text and m.text.startswith("📤"))
def withdraw(msg):
    if not guard(msg):
        return
    
    uid = msg.from_user.id
    lang = get_user_language(uid)
    bal = get_balance(uid)
    fee = float(os.getenv("NETWORK_FEE", "1.0"))
    
    if bal < MIN_WITHDRAW + fee:
        bot.send_message(msg.chat.id, f"❌ رصيد غير كافٍ. المطلوب: `{MIN_WITHDRAW + fee:.4f} USDT`", parse_mode="Markdown")
        return
    
    text = get_text(lang, "withdraw_address_req", bal=bal, fee=fee)
    bot.send_message(msg.chat.id, text, parse_mode="Markdown")
    bot.register_next_step_handler(msg, _handle_withdraw_address)

def _handle_withdraw_address(msg):
    """معالجة عنوان السحب"""
    lang = get_user_language(msg.from_user.id)
    addr = msg.text.strip()
    
    if not is_valid_tron_address(addr):
        bot.send_message(msg.chat.id, get_text(lang, "error_invalid_address"))
        bot.register_next_step_handler(msg, _handle_withdraw_address)
        return
    
    bot.send_message(msg.chat.id, get_text(lang, "withdraw_amount_req", addr=addr), parse_mode="Markdown")
    bot.register_next_step_handler(msg, lambda m: _handle_withdraw_amount(m, addr))

def _handle_withdraw_amount(msg, addr):
    """معالجة مبلغ السحب"""
    lang = get_user_language(msg.from_user.id)
    
    try:
        amt = float(msg.text.strip())
    except ValueError:
        bot.send_message(msg.chat.id, get_text(lang, "error_invalid_amount"))
        bot.register_next_step_handler(msg, lambda m: _handle_withdraw_amount(m, addr))
        return
    
    ok, err = validate_withdrawal(msg.from_user.id, addr, amt)
    if not ok:
        bot.send_message(msg.chat.id, err, parse_mode="Markdown")
        bot.register_next_step_handler(msg, lambda m: _handle_withdraw_amount(m, addr))
        return
    
    create_pending_withdrawal(msg.from_user.id, addr, amt)
    
    summary = get_withdrawal_summary(addr, amt)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(get_text(lang, "btn_confirm"), callback_data="confirm_wd"),
        types.InlineKeyboardButton(get_text(lang, "btn_cancel"), callback_data="cancel_wd")
    )
    
    bot.send_message(msg.chat.id, summary, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "confirm_wd")
def confirm_withdraw(call):
    uid = call.from_user.id
    lang = get_user_language(uid)
    
    data = get_pending_withdrawal_data(uid)
    if not data:
        bot.answer_callback_query(call.id, "❌ انتهت الجلسة", show_alert=True)
        return
    
    addr, amt, _ = data
    
    bot.answer_callback_query(call.id, "⏳ جاري المعالجة...")
    bot.send_message(call.message.chat.id, "⏳ جاري إرسال المبلغ...", parse_mode="Markdown")
    
    ok, result_msg, txid = process_withdrawal(uid, addr, amt)
    
    clear_pending_withdrawal_data(uid)
    
    bot.send_message(call.message.chat.id, result_msg, parse_mode="Markdown")
    
    # إخطار أدمن
    if ok and txid and ADMIN_ID:
        try:
            bot.send_message(
                ADMIN_ID,
                f"📤 *سحب مكتمل*\n"
                f"👤 المستخدم: `{uid}`\n"
                f"📍 العنوان: `{addr}`\n"
                f"💰 المبلغ: `{amt:.4f} USDT`\n"
                f"🔗 TXID: `{txid}`",
                parse_mode="Markdown"
            )
        except Exception:
            pass

@bot.callback_query_handler(func=lambda c: c.data == "cancel_wd")
def cancel_withdraw(call):
    lang = get_user_language(call.from_user.id)
    clear_pending_withdrawal_data(call.from_user.id)
    bot.answer_callback_query(call.id, "❌ تم الإلغاء")
    bot.send_message(call.message.chat.id, "❌ تم إلغاء عملية السحب")

# ==================== TRANSFER ====================

@bot.message_handler(func=lambda m: m.text and m.text.startswith("🔄"))
def transfer(msg):
    if not guard(msg):
        return
    
    uid = msg.from_user.id
    lang = get_user_language(uid)
    bal = get_balance(uid)
    
    text = get_text(lang, "transfer_amount_req", bal=bal, comm=COMMISSION)
    bot.send_message(msg.chat.id, text, parse_mode="Markdown")
    bot.register_next_step_handler(msg, _handle_transfer)

def _handle_transfer(msg):
    """معالجة التحويل الداخلي"""
    lang = get_user_language(msg.from_user.id)
    
    try:
        parts = msg.text.strip().split()
        to_id = int(parts[0])
        amt = float(parts[1])
    except (ValueError, IndexError):
        bot.send_message(msg.chat.id, "❌ الصيغة: `ID المبلغ`\nمثال: `123456789 50`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, _handle_transfer)
        return
    
    uid = msg.from_user.id
    
    # فحوصات
    if to_id == uid:
        bot.send_message(msg.chat.id, get_text(lang, "error_self_transfer"))
        return
    
    receiver = get_user(to_id)
    if not receiver:
        bot.send_message(msg.chat.id, get_text(lang, "error_user_not_found"))
        return
    
    if is_banned(to_id):
        bot.send_message(msg.chat.id, get_text(lang, "error_user_banned"))
        return
    
    bal = get_balance(uid)
    total = amt + COMMISSION
    
    if total > bal:
        bot.send_message(msg.chat.id, get_text(lang, "error_insufficient_balance"))
        return
    
    # إنشاء معرّف عملية
    ref = "TX-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    expires_at = (datetime.now() + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
    transfer_id = save_pending_transfer(uid, to_id, amt, COMMISSION, expires_at)
    
    receiver_name = receiver[2] or "مستخدم"
    
    text = get_text(lang, "transfer_confirm", name=receiver_name, uid=to_id, amt=amt, comm=COMMISSION, ref=ref)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(get_text(lang, "btn_confirm"), callback_data=f"conf_tr_{transfer_id}"),
        types.InlineKeyboardButton(get_text(lang, "btn_cancel"), callback_data=f"canc_tr_{transfer_id}")
    )
    
    bot.send_message(msg.chat.id, text, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("conf_tr_"))
def confirm_transfer(call):
    try:
        transfer_id = int(call.data.split("_")[2])
    except (ValueError, IndexError):
        bot.answer_callback_query(call.id, "❌ خطأ", show_alert=True)
        return
    
    uid = call.from_user.id
    lang = get_user_language(uid)
    
    data = get_pending_transfer(transfer_id)
    if not data:
        bot.answer_callback_query(call.id, "❌ انتهت الجلسة", show_alert=True)
        return
    
    sender_id, receiver_id, amt, comm, expires_at = data
    
    # فحص الصلاحية
    exp_time = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S")
    if datetime.now() > exp_time:
        clear_pending_transfer(transfer_id)
        bot.answer_callback_query(call.id, "❌ انتهت صلاحية الجلسة", show_alert=True)
        return
    
    # فحص أن الضاغط هو المرسل
    if uid != sender_id:
        bot.answer_callback_query(call.id, "❌ هذا ليس طلبك!", show_alert=True)
        return
    
    # تنفيذ التحويل (ذري وآمن)
    total = amt + comm
    if not update_balance_atomic(sender_id, -total, min_balance=0):
        bot.answer_callback_query(call.id, "❌ فشل الخصم", show_alert=True)
        return
    
    update_balance_atomic(receiver_id, amt, min_balance=0)
    
    # تسجيل
    add_transaction(sender_id, "تحويل صادر", amt, "مكتمل", transaction_type="transfer_out", transaction_status="completed")
    add_transaction(receiver_id, "تحويل وارد", amt, "مكتمل", transaction_type="transfer_in", transaction_status="completed")
    
    clear_pending_transfer(transfer_id)
    
    # رسائل
    receiver = get_user(receiver_id)
    receiver_name = receiver[2] if receiver else "مستخدم"
    
    new_bal_sender = get_balance(sender_id)
    msg_sender = get_text(lang, "transfer_success", uid=receiver_id, name=receiver_name, amt=amt, comm=comm, bal=new_bal_sender)
    
    bot.answer_callback_query(call.id, "✅ تم التحويل!")
    bot.send_message(call.message.chat.id, msg_sender, parse_mode="Markdown")
    
    # إخطار المستقبل
    try:
        lang_receiver = get_user_language(receiver_id)
        new_bal_receiver = get_balance(receiver_id)
        msg_receiver = get_text(lang_receiver, "transfer_received", name=receiver_name, amt=amt, bal=new_bal_receiver)
        bot.send_message(receiver_id, msg_receiver, parse_mode="Markdown")
    except Exception:
        pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("canc_tr_"))
def cancel_transfer(call):
    try:
        transfer_id = int(call.data.split("_")[2])
    except (ValueError, IndexError):
        return
    
    uid = call.from_user.id
    data = get_pending_transfer(transfer_id)
    
    if data and data[0] == uid:
        clear_pending_transfer(transfer_id)
        bot.answer_callback_query(call.id, "❌ تم الإلغاء")
    else:
        bot.answer_callback_query(call.id, "❌ خطأ", show_alert=True)

# ==================== HISTORY ====================

@bot.message_handler(func=lambda m: m.text and m.text.startswith("📜"))
def history(msg):
    uid = msg.from_user.id
    lang = get_user_language(uid)
    
    if is_banned(uid):
        return
    
    txs = get_transactions(uid, limit=10)
    if not txs:
        bot.send_message(msg.chat.id, get_text(lang, "history_empty"))
        return
    
    text = f"{get_text(lang, 'history_title')}\n\n"
    for tx in txs:
        tx_type = tx[0]
        amt = tx[1]
        status = tx[2]
        txid = tx[3] or "—"
        
        emoji = "📥" if "إيداع" in tx_type or "وارد" in tx_type else "📤"
        txid_short = txid[:12] + "..." if len(txid) > 12 else txid
        
        text += f"{emoji} `{tx_type}`\n💰 `{amt:.4f} USDT` | {status}\n🔗 `{txid_short}`\n─────────────\n"
    
    bot.send_message(msg.chat.id, text, parse_mode="Markdown")

# ==================== PROFILE ====================

@bot.message_handler(func=lambda m: m.text and m.text.startswith("👤"))
def profile(msg):
    uid = msg.from_user.id
    lang = get_user_language(uid)
    
    if is_banned(uid):
        return
    
    user = get_user(uid)
    bal = get_balance(uid)
    
    text = get_text(lang, "profile_info", name=msg.from_user.first_name or "مستخدم", id=uid, bal=bal, date="—")
    bot.send_message(msg.chat.id, text, parse_mode="Markdown")

# ==================== SETTINGS ====================

@bot.message_handler(func=lambda m: m.text and m.text.startswith("⚙️"))
def settings(msg):
    lang = get_user_language(msg.from_user.id)
    
    text = get_text(lang, "settings_title")
    bot.send_message(msg.chat.id, text, parse_mode="Markdown", reply_markup=settings_menu(lang))

@bot.callback_query_handler(func=lambda c: c.data == "settings_lang")
def settings_lang(call):
    lang = get_user_language(call.from_user.id)
    
    text = get_text(lang, "lang_title")
    bot.send_message(call.message.chat.id, text, reply_markup=languages_menu(lang))
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("lang_"))
def set_language(call):
    new_lang = call.data.split("_")[1]
    set_user_language(call.from_user.id, new_lang)
    
    bot.answer_callback_query(call.id, get_text(new_lang, "lang_changed"), show_alert=True)

# ==================== FOLLOW ====================

@bot.message_handler(func=lambda m: m.text and m.text.startswith("📢"))
def follow(msg):
    lang = get_user_language(msg.from_user.id)
    
    text = get_text(lang, "follow_title")
    markup = follow_menu(lang)
    
    if not markup.keyboard:
        bot.send_message(msg.chat.id, "❌ لا توجد روابط متاحة")
        return
    
    bot.send_message(msg.chat.id, text, reply_markup=markup)

# ==================== SUPPORT ====================

@bot.message_handler(func=lambda m: m.text and m.text.startswith("💬"))
def support(msg):
    lang = get_user_language(msg.from_user.id)
    
    text = get_text(lang, "support_title")
    bot.send_message(msg.chat.id, text)
    
    bot.register_next_step_handler(msg, _handle_support_message)

def _handle_support_message(msg):
    """معالجة رسالة الدعم"""
    if not ADMIN_ID:
        bot.send_message(msg.chat.id, "❌ لا يوجد أدمن متاح")
        return
    
    # إرسال الرسالة للأدمن
    try:
        bot.send_message(
            ADMIN_ID,
            f"💬 *رسالة دعم جديدة*\n\n"
            f"👤 من: `{msg.from_user.id}`\n"
            f"📱 الاسم: {msg.from_user.first_name}\n\n"
            f"الرسالة:\n{msg.text}",
            parse_mode="Markdown",
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("الرد", callback_data=f"reply_{msg.from_user.id}")
            )
        )
        bot.send_message(msg.chat.id, "✅ تم إرسال رسالتك للدعم. سيتم الرد عليك قريباً.")
    except Exception as e:
        bot.send_message(msg.chat.id, f"❌ خطأ: {e}")

# ==================== BACK ====================

@bot.message_handler(func=lambda m: m.text and m.text.startswith("↩️"))
def back(msg):
    lang = get_user_language(msg.from_user.id)
    bot.send_message(msg.chat.id, get_text(lang, "main_menu"), reply_markup=main_menu(lang))

# ==================== CUSTOM BUTTONS ====================

@bot.message_handler(func=lambda m: True)
def handle_custom(msg):
    """معالجة الأزرار المخصصة"""
    if is_banned(msg.from_user.id):
        return
    
    for btn in get_custom_buttons():
        if msg.text == btn[1]:
            if btn[2] == "text":
                bot.send_message(msg.chat.id, btn[3])
            elif btn[2] == "url":
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton(btn[1], url=btn[3]))
                bot.send_message(msg.chat.id, f"🔗 {btn[1]}", reply_markup=markup)
            return

# ==================== MAIN ====================

if __name__ == "__main__":
    # استيراد معالجات الأدمن
    from admin import register_admin_handlers
    register_admin_handlers(bot)
    
    bot.remove_webhook()
    print("✅ البوت يعمل! 🚀")
    print(f"👑 أدمن ID: {ADMIN_ID}")
    print(f"💼 المحفظة: {os.getenv('WALLET_ADDRESS', 'غير محددة')}")
    
    bot.infinity_polling(none_stop=True, timeout=60)