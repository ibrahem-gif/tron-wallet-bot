"""
bot.py - البوت الرئيسي
محفظة USDT TRC20 مباشرة عبر شبكة TRON بدون أي وسيط
"""

import os
from dotenv import load_dotenv

# تحميل متغيرات البيئة أولاً
load_dotenv()

import telebot
from telebot import types

from database import (
    init_db, add_user, get_user, get_balance,
    update_balance, add_transaction, get_transactions,
    is_banned, check_rate_limit, get_custom_buttons
)
from deposit import (
    get_deposit_address, register_pending_deposit,
    cancel_pending_deposit, start_deposit_monitor, NETWORK_FEE, MIN_DEPOSIT,
    generate_unique_deposit_amount  # ✅ جديد: توليد مبلغ فريد
)
from withdraw import validate_withdrawal, process_withdrawal, get_withdrawal_summary
from tron import is_valid_tron_address
from admin import register_admin_handlers, is_admin, admin_inline_menu

# ==================== CONFIG ====================
BOT_TOKEN   = os.getenv("BOT_TOKEN", "")
ADMIN_ID    = int(os.getenv("ADMIN_ID", "0"))
COMMISSION  = float(os.getenv("COMMISSION", "0.2"))
NETWORK_FEE_VAL = float(os.getenv("NETWORK_FEE", "1.0"))

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN غير محدد في .env")

bot = telebot.TeleBot(BOT_TOKEN)
init_db()


# ==================== MENUS ====================

def main_menu() -> types.ReplyKeyboardMarkup:
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("💼 المحفظة"),
        types.KeyboardButton("👤 حسابي"),
        types.KeyboardButton("⚙️ الإعدادات"),
    )
    for btn in get_custom_buttons():
        markup.add(types.KeyboardButton(btn["name"]))
    return markup


def wallet_menu() -> types.ReplyKeyboardMarkup:
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("📥 إيداع"),
        types.KeyboardButton("📤 سحب"),
        types.KeyboardButton("💰 الرصيد"),
        types.KeyboardButton("🔄 تحويل داخلي"),
        types.KeyboardButton("📜 سجل المعاملات"),
        types.KeyboardButton("↩️ رجوع"),
    )
    return markup


MENU_BUTTONS = {
    "📥 إيداع", "📤 سحب", "💰 الرصيد", "↩️ رجوع",
    "💼 المحفظة", "👤 حسابي", "⚙️ الإعدادات",
    "📜 سجل المعاملات", "🔄 تحويل داخلي",
}


def guard(msg) -> bool:
    """حماية مشتركة: تحقق من الحظر + rate limit"""
    if is_banned(msg.from_user.id):
        bot.send_message(msg.chat.id, "❌ حسابك محظور. تواصل مع الدعم.")
        return False
    if not check_rate_limit(msg.from_user.id):
        bot.send_message(msg.chat.id, "⚠️ لا تضغط بسرعة! انتظر لحظة.")
        return False
    return True


# ==================== START ====================

@bot.message_handler(commands=["start"])
def start(msg):
    if not guard(msg):
        return
    add_user(msg.from_user.id, msg.from_user.username)

    if is_admin(msg.from_user.id):
        bot.send_message(
            msg.chat.id,
            f"👑 *مرحباً أدمن!*\n\nاختر من لوحة التحكم:",
            parse_mode="Markdown",
            reply_markup=admin_inline_menu()
        )
        return

    bot.send_message(
        msg.chat.id,
        f"👋 أهلاً *{msg.from_user.first_name}*!\n\n"
        f"🏦 مرحباً في محفظتك الإلكترونية\n"
        f"💎 العملة: USDT (TRC20)\n"
        f"🌐 الشبكة: TRON مباشر\n"
        f"🔒 عمليات آمنة ومباشرة على البلوكتشين\n\n"
        f"اختر من القائمة:",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )


# ==================== WALLET ====================

@bot.message_handler(func=lambda m: m.text == "💼 المحفظة")
def wallet(msg):
    if not guard(msg):
        return
    bal = get_balance(msg.from_user.id)
    bot.send_message(
        msg.chat.id,
        f"💼 *المحفظة*\n\n💰 رصيدك: *{bal:.4f} USDT*",
        parse_mode="Markdown",
        reply_markup=wallet_menu()
    )


@bot.message_handler(func=lambda m: m.text == "💰 الرصيد")
def balance(msg):
    if is_banned(msg.from_user.id):
        return
    bal = get_balance(msg.from_user.id)
    bot.send_message(
        msg.chat.id,
        f"💰 *رصيدك الحالي*\n\n`{bal:.4f} USDT`",
        parse_mode="Markdown",
        reply_markup=wallet_menu()
    )


# ==================== DEPOSIT ====================

@bot.message_handler(func=lambda m: m.text == "📥 إيداع")
def deposit(msg):
    if not guard(msg):
        return

    address = get_deposit_address()
    if not address:
        bot.send_message(msg.chat.id, "❌ خطأ في إعدادات المحفظة. تواصل مع الدعم.")
        return

    # ✅ جديد: اطلب المبلغ أولاً قبل عرض العنوان
    bot.send_message(
        msg.chat.id,
        f"📥 *الإيداع عبر USDT TRC20*\n\n"
        f"💸 الحد الأدنى للإيداع: `{MIN_DEPOSIT} USDT`\n\n"
        f"أدخل المبلغ الذي تريد إيداعه:\n"
        f"_(مثال: `10` أو `25.5`)_",
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(msg, lambda m: _get_deposit_amount(m, address))


def _get_deposit_amount(msg, address: str):
    """✅ جديد: استقبال مبلغ الإيداع وعرض المبلغ الفريد"""
    if msg.text in MENU_BUTTONS or (msg.text and msg.text.startswith("/")):
        bot.process_new_messages([msg])
        return

    try:
        base_amount = float(msg.text.strip().replace(",", "."))
    except ValueError:
        bot.send_message(
            msg.chat.id,
            "❌ أدخل رقماً صحيحاً مثل: `10` أو `25.5`",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, lambda m: _get_deposit_amount(m, address))
        return

    if base_amount < MIN_DEPOSIT:
        bot.send_message(
            msg.chat.id,
            f"❌ الحد الأدنى للإيداع هو `{MIN_DEPOSIT} USDT`\n\nأدخل مبلغاً أكبر:",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, lambda m: _get_deposit_amount(m, address))
        return

    # ✅ توليد مبلغ فريد وتسجيل المستخدم في قائمة الانتظار
    unique_amount = generate_unique_deposit_amount(msg.from_user.id, base_amount)
    register_pending_deposit(msg.from_user.id)

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "✅ تم الإرسال - تحقق الآن",
            callback_data=f"manual_check_{msg.from_user.id}"
        )
    )

    bot.send_message(
        msg.chat.id,
        f"📥 *الإيداع عبر USDT TRC20*\n\n"
        f"📍 *عنوان المحفظة:*\n"
        f"`{address}`\n\n"
        f"💎 *المبلغ المطلوب إرساله بالضبط:*\n"
        f"➡️ `{unique_amount:.2f} USDT`\n\n"
        f"🌐 الشبكة: `TRON (TRC20)` فقط\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"⚠️ *مهم جداً:* أرسل المبلغ أعلاه *بالضبط* `{unique_amount:.2f}`\n"
        f"هذا الرقم يُستخدم لربط إيداعك بحسابك تلقائياً ✅\n\n"
        f"📌 سيُضاف *كامل المبلغ* `{unique_amount:.2f} USDT` لرصيدك\n"
        f"⏱️ مدة التأكيد: ~1-3 دقائق\n\n"
        f"⚠️ أرسل على شبكة TRON فقط!",
        parse_mode="Markdown",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("manual_check_"))
def manual_check_deposit(call):
    user_id = int(call.data.split("_")[2])

    if call.from_user.id != user_id:
        bot.answer_callback_query(call.id, "❌ هذا ليس طلبك!")
        return

    bot.answer_callback_query(call.id, "⏳ جاري فحص البلوكتشين...")
    bot.send_message(
        call.message.chat.id,
        "⏳ *جاري التحقق من البلوكتشين...*\n\n"
        "النظام يراقب المعاملات تلقائياً كل 30 ثانية.\n"
        "إذا أرسلت المبلغ، سيُضاف رصيدك تلقائياً خلال دقيقة إلى دقيقتين.\n\n"
        "🔍 تأكد من أن:\n"
        "• العنوان صحيح\n"
        "• الشبكة TRC20\n"
        "• المبلغ لا يقل عن 1 USDT",
        parse_mode="Markdown"
    )


# ==================== WITHDRAW ====================

@bot.message_handler(func=lambda m: m.text == "📤 سحب")
def withdraw(msg):
    if not guard(msg):
        return

    bal = get_balance(msg.from_user.id)
    min_needed = float(os.getenv("MIN_WITHDRAW", "2.0")) + NETWORK_FEE_VAL

    if bal < min_needed:
        bot.send_message(
            msg.chat.id,
            f"❌ *رصيد غير كافٍ للسحب*\n\n"
            f"رصيدك: `{bal:.4f} USDT`\n"
            f"الحد الأدنى للسحب: `{float(os.getenv('MIN_WITHDRAW', '2.0')):.2f} USDT`\n"
            f"رسوم الشبكة: `{NETWORK_FEE_VAL:.2f} USDT`\n"
            f"إجمالي المطلوب: `{min_needed:.2f} USDT`",
            parse_mode="Markdown",
            reply_markup=wallet_menu()
        )
        return

    bot.send_message(
        msg.chat.id,
        f"📤 *السحب عبر TRC20*\n\n"
        f"💰 رصيدك: `{bal:.4f} USDT`\n"
        f"🌐 رسوم الشبكة: `{NETWORK_FEE_VAL:.2f} USDT` (تُخصم منك)\n\n"
        f"أرسل عنوان محفظتك TRC20:\n"
        f"(عنوان يبدأ بـ T ويكون 34 حرفاً)",
        parse_mode="Markdown",
        reply_markup=wallet_menu()
    )
    bot.register_next_step_handler(msg, _get_withdraw_address)


def _get_withdraw_address(msg):
    if msg.text in MENU_BUTTONS or (msg.text and msg.text.startswith("/")):
        bot.process_new_messages([msg])
        return

    address = msg.text.strip()

    if not is_valid_tron_address(address):
        bot.send_message(
            msg.chat.id,
            "❌ عنوان TRC20 غير صحيح!\n"
            "• يبدأ بحرف `T`\n"
            "• طوله 34 حرفاً\n"
            "• شبكة TRON فقط\n\n"
            "أرسل العنوان مرة أخرى أو اضغط رجوع:",
            parse_mode="Markdown",
            reply_markup=wallet_menu()
        )
        return

    bot.send_message(
        msg.chat.id,
        f"✅ العنوان صحيح: `{address}`\n\n"
        f"الآن أدخل المبلغ بالـ USDT:\n"
        f"(مثال: `10` أو `25.5`)",
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(msg, lambda m: _get_withdraw_amount(m, address))


def _get_withdraw_amount(msg, address: str):
    if msg.text in MENU_BUTTONS or (msg.text and msg.text.startswith("/")):
        bot.process_new_messages([msg])
        return

    try:
        amount = float(msg.text.strip())
    except ValueError:
        bot.send_message(msg.chat.id, "❌ أدخل رقماً صحيحاً مثل: `10`",
                         parse_mode="Markdown")
        return

    ok, err_msg = validate_withdrawal(msg.from_user.id, address, amount)
    if not ok:
        bot.send_message(msg.chat.id, err_msg, parse_mode="Markdown",
                         reply_markup=wallet_menu())
        return

    # عرض ملخص التأكيد
    summary = get_withdrawal_summary(address, amount)
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "✅ تأكيد السحب",
            callback_data=f"confirm_wd|{address}|{amount}|{msg.from_user.id}"
        ),
        types.InlineKeyboardButton("❌ إلغاء", callback_data="cancel_wd")
    )
    bot.send_message(msg.chat.id, summary, parse_mode="Markdown", reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data.startswith("confirm_wd|"))
def confirm_withdraw(call):
    parts = call.data.split("|")
    address   = parts[1]
    amount    = float(parts[2])
    user_id   = int(parts[3])

    if call.from_user.id != user_id:
        bot.answer_callback_query(call.id, "❌ هذا ليس طلبك!")
        return

    bot.answer_callback_query(call.id, "⏳ جاري المعالجة...")
    bot.send_message(call.message.chat.id, "⏳ *جاري إرسال المبلغ على شبكة TRON...*",
                     parse_mode="Markdown")

    success, result_msg, txid = process_withdrawal(user_id, address, amount)

    bot.send_message(
        call.message.chat.id,
        result_msg,
        parse_mode="Markdown",
        reply_markup=wallet_menu()
    )

    if success and txid:
        # إشعار الأدمن
        try:
            bot.send_message(
                ADMIN_ID,
                f"📤 *سحب مكتمل*\n"
                f"👤 المستخدم: `{user_id}`\n"
                f"📍 العنوان: `{address}`\n"
                f"💰 المبلغ: `{amount:.4f} USDT`\n"
                f"🌐 رسوم الشبكة: `{NETWORK_FEE_VAL:.4f} USDT`\n"
                f"🔗 TXID: `{txid}`",
                parse_mode="Markdown"
            )
        except Exception:
            pass


@bot.callback_query_handler(func=lambda c: c.data == "cancel_wd")
def cancel_withdraw(call):
    bot.answer_callback_query(call.id, "❌ تم الإلغاء")
    bot.send_message(call.message.chat.id, "❌ تم إلغاء عملية السحب",
                     reply_markup=wallet_menu())


# ==================== TRANSFER ====================

@bot.message_handler(func=lambda m: m.text == "🔄 تحويل داخلي")
def internal_transfer(msg):
    if not guard(msg):
        return
    bal = get_balance(msg.from_user.id)
    bot.send_message(
        msg.chat.id,
        f"🔄 *التحويل الداخلي*\n\n"
        f"💰 رصيدك: `{bal:.4f} USDT`\n"
        f"💸 العمولة: `{COMMISSION} USDT`\n\n"
        f"أرسل: `ID_المستخدم المبلغ`\n"
        f"مثال: `123456789 5`",
        parse_mode="Markdown",
        reply_markup=wallet_menu()
    )
    bot.register_next_step_handler(msg, _process_transfer)


def _process_transfer(msg):
    if msg.text in MENU_BUTTONS or (msg.text and msg.text.startswith("/")):
        bot.process_new_messages([msg])
        return

    try:
        parts = msg.text.strip().split()
        to_id  = int(parts[0])
        amount = float(parts[1])
    except (ValueError, IndexError):
        bot.send_message(msg.chat.id, "❌ الصيغة: `123456789 5`", parse_mode="Markdown")
        return

    from database import get_user as db_get_user
    if to_id == msg.from_user.id:
        bot.send_message(msg.chat.id, "❌ لا يمكنك التحويل لنفسك")
        return

    if not db_get_user(to_id):
        bot.send_message(msg.chat.id, "❌ المستخدم غير موجود في النظام")
        return

    if is_banned(to_id):
        bot.send_message(msg.chat.id, "❌ المستخدم محظور")
        return

    bal   = get_balance(msg.from_user.id)
    total = amount + COMMISSION

    if total > bal:
        bot.send_message(
            msg.chat.id,
            f"❌ رصيد غير كافٍ\n"
            f"رصيدك: `{bal:.4f} USDT`\n"
            f"المطلوب: `{total:.4f} USDT`",
            parse_mode="Markdown"
        )
        return

    update_balance(msg.from_user.id, -total)
    update_balance(to_id, amount)
    add_transaction(msg.from_user.id, "تحويل صادر", amount, "مكتمل",
                    transaction_type="transfer_out", transaction_status="completed")
    add_transaction(to_id, "تحويل وارد", amount, "مكتمل",
                    transaction_type="transfer_in", transaction_status="completed")

    new_bal = get_balance(msg.from_user.id)
    bot.send_message(
        msg.chat.id,
        f"✅ *تم التحويل بنجاح!*\n\n"
        f"📤 إلى: `{to_id}`\n"
        f"💰 المبلغ: `{amount:.4f} USDT`\n"
        f"💸 العمولة: `{COMMISSION} USDT`\n"
        f"💳 رصيدك الجديد: `{new_bal:.4f} USDT`",
        parse_mode="Markdown",
        reply_markup=wallet_menu()
    )

    try:
        bot.send_message(
            to_id,
            f"💸 *استلمت تحويل!*\n\n"
            f"💰 المبلغ: `{amount:.4f} USDT`\n"
            f"💳 رصيدك الجديد: `{get_balance(to_id):.4f} USDT`",
            parse_mode="Markdown"
        )
    except Exception:
        pass


# ==================== HISTORY ====================

@bot.message_handler(func=lambda m: m.text == "📜 سجل المعاملات")
def history(msg):
    if is_banned(msg.from_user.id):
        return
    txs = get_transactions(msg.from_user.id, limit=10)
    if not txs:
        bot.send_message(msg.chat.id, "📜 لا توجد معاملات بعد", reply_markup=wallet_menu())
        return

    text = "📜 *آخر 10 معاملات:*\n\n"
    for tx in txs:
        tx_type   = tx["type"]
        amount    = tx["amount"]
        status    = tx["status"]
        txid      = tx["txid"] or "—"
        net_fee   = tx["network_fee"] or 0
        created   = tx["created_at"]

        emoji = "📥" if "إيداع" in tx_type or "وارد" in tx_type else "📤"
        txid_short = txid[:16] + "..." if len(txid) > 16 else txid
        fee_line = f"🌐 رسوم: `{net_fee:.4f}`\n" if net_fee > 0 else ""

        text += (
            f"{emoji} *{tx_type}*\n"
            f"💰 `{amount:.4f} USDT` | {status}\n"
            f"{fee_line}"
            f"🔗 `{txid_short}`\n"
            f"📅 {created}\n"
            f"─────────────\n"
        )

    bot.send_message(msg.chat.id, text, parse_mode="Markdown", reply_markup=wallet_menu())


# ==================== ACCOUNT ====================

@bot.message_handler(func=lambda m: m.text == "👤 حسابي")
def account(msg):
    if is_banned(msg.from_user.id):
        return
    user = get_user(msg.from_user.id)
    bal  = get_balance(msg.from_user.id)
    registered = user["created_at"] if user else "غير معروف"
    bot.send_message(
        msg.chat.id,
        f"👤 *حسابي*\n\n"
        f"الاسم: {msg.from_user.first_name}\n"
        f"🆔 ID: `{msg.from_user.id}`\n"
        f"💰 الرصيد: `{bal:.4f} USDT`\n"
        f"📅 تاريخ التسجيل: `{registered}`\n\n"
        f"🌐 الشبكة: TRON (TRC20)",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )


# ==================== SETTINGS ====================

@bot.message_handler(func=lambda m: m.text == "⚙️ الإعدادات")
def settings(msg):
    bot.send_message(
        msg.chat.id,
        "⚙️ *الإعدادات*\n\n"
        "🔜 تغيير اللغة — قريباً\n"
        "🔜 الإشعارات — قريباً",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )


@bot.message_handler(func=lambda m: m.text == "↩️ رجوع")
def back(msg):
    bot.send_message(msg.chat.id, "🏠 الرئيسية", reply_markup=main_menu())


# ==================== CUSTOM BUTTONS ====================

@bot.message_handler(func=lambda m: True)
def handle_custom_buttons(msg):
    if is_banned(msg.from_user.id):
        return
    for btn in get_custom_buttons():
        if msg.text == btn["name"]:
            if btn["type"] == "text":
                bot.send_message(msg.chat.id, btn["content"])
            elif btn["type"] == "url":
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton(btn["name"], url=btn["content"]))
                bot.send_message(msg.chat.id, f"🔗 {btn['name']}", reply_markup=markup)
            return


# ==================== MAIN ====================

if __name__ == "__main__":
    # تسجيل معالجات الأدمن
    register_admin_handlers(bot)

    # تشغيل مراقب الإيداع التلقائي
    start_deposit_monitor(bot)

    bot.remove_webhook()
    print("✅ البوت شغال! 🚀")
    print(f"🌐 يراقب شبكة TRON مباشرة")
    print(f"💼 محفظة الإيداع: {os.getenv('WALLET_ADDRESS', 'غير محددة')}")
    bot.infinity_polling(none_stop=True, timeout=60)