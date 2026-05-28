"""
admin.py - لوحة تحكم الأدمن
"""

import os
import time
import sqlite3
from telebot import TeleBot, types
from database import (
    get_stats, get_all_users, get_all_transactions,
    get_balance, update_balance, add_transaction,
    ban_user, unban_user, get_user,
    get_custom_buttons, add_custom_button, delete_custom_button
)

ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))


def is_admin(telegram_id: int) -> bool:
    return telegram_id == ADMIN_ID


def admin_inline_menu() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 الإحصائيات",    callback_data="a_stats"),
        types.InlineKeyboardButton("👥 المستخدمين",    callback_data="a_users"),
        types.InlineKeyboardButton("🚫 حظر مستخدم",   callback_data="a_ban"),
        types.InlineKeyboardButton("✅ فك الحظر",      callback_data="a_unban"),
        types.InlineKeyboardButton("📢 إذاعة",         callback_data="a_broadcast"),
        types.InlineKeyboardButton("💰 إضافة رصيد",   callback_data="a_add_bal"),
        types.InlineKeyboardButton("➖ خصم رصيد",     callback_data="a_rem_bal"),
        types.InlineKeyboardButton("🔘 إضافة زر",     callback_data="a_add_btn"),
        types.InlineKeyboardButton("🗑️ حذف زر",       callback_data="a_del_btn"),
        types.InlineKeyboardButton("📋 سجل العمليات", callback_data="a_logs"),
        types.InlineKeyboardButton("💼 رصيد المحفظة", callback_data="a_wallet_bal"),
    )
    return markup


def register_admin_handlers(bot: TeleBot):
    """تسجيل جميع معالجات الأدمن"""

    @bot.message_handler(commands=["admin"])
    def admin_panel(msg):
        if not is_admin(msg.from_user.id):
            return
        bot.send_message(
            msg.chat.id,
            "👑 *لوحة تحكم الأدمن*\n\n"
            f"🔑 مرحباً، أنت مسجّل كمسؤول.\n"
            f"اختر الإجراء:",
            parse_mode="Markdown",
            reply_markup=admin_inline_menu()
        )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("a_"))
    def admin_callbacks(call):
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية")
            return
        bot.answer_callback_query(call.id)

        if call.data == "a_stats":
            _handle_stats(bot, call)
        elif call.data == "a_users":
            _handle_users(bot, call)
        elif call.data == "a_broadcast":
            bot.send_message(call.message.chat.id, "📢 أرسل نص رسالة الإذاعة:")
            bot.register_next_step_handler(call.message, lambda m: _do_broadcast(bot, m))
        elif call.data == "a_ban":
            bot.send_message(call.message.chat.id, "🚫 أرسل ID المستخدم للحظر:")
            bot.register_next_step_handler(call.message, lambda m: _do_ban(bot, m))
        elif call.data == "a_unban":
            bot.send_message(call.message.chat.id, "✅ أرسل ID المستخدم لفك الحظر:")
            bot.register_next_step_handler(call.message, lambda m: _do_unban(bot, m))
        elif call.data == "a_add_bal":
            bot.send_message(
                call.message.chat.id,
                "💰 أرسل: `ID_المستخدم المبلغ`\nمثال: `123456789 50`",
                parse_mode="Markdown"
            )
            bot.register_next_step_handler(call.message, lambda m: _do_add_balance(bot, m))
        elif call.data == "a_rem_bal":
            bot.send_message(
                call.message.chat.id,
                "➖ أرسل: `ID_المستخدم المبلغ`\nمثال: `123456789 10`",
                parse_mode="Markdown"
            )
            bot.register_next_step_handler(call.message, lambda m: _do_remove_balance(bot, m))
        elif call.data == "a_add_btn":
            bot.send_message(
                call.message.chat.id,
                "🔘 *إضافة زر مخصص*\n\n"
                "الصيغة: `اسم_الزر|نوع|المحتوى`\n\n"
                "النوع: `text` أو `url`\n\n"
                "مثال نص: `مساعدة|text|مرحباً!`\n"
                "مثال رابط: `قناتنا|url|https://t.me/channel`",
                parse_mode="Markdown"
            )
            bot.register_next_step_handler(call.message, lambda m: _do_add_button(bot, m))
        elif call.data == "a_del_btn":
            _handle_del_button_menu(bot, call)
        elif call.data == "a_logs":
            _handle_logs(bot, call)
        elif call.data == "a_wallet_bal":
            _handle_wallet_balance(bot, call)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("del_btn_"))
    def delete_button_callback(call):
        if not is_admin(call.from_user.id):
            return
        btn_id = int(call.data.split("_")[2])
        delete_custom_button(btn_id)
        bot.answer_callback_query(call.id, "✅ تم الحذف")
        bot.send_message(call.message.chat.id, "✅ تم حذف الزر بنجاح")


# ==================== دوال مساعدة ====================

def _handle_stats(bot: TeleBot, call):
    total_users, total_balance, total_tx, banned, total_dep, total_wd = get_stats()
    bot.send_message(
        call.message.chat.id,
        f"📊 *إحصائيات البوت*\n\n"
        f"👥 إجمالي المستخدمين: `{total_users}`\n"
        f"🚫 المحظورين: `{banned}`\n"
        f"💰 إجمالي الأرصدة: `{total_balance:.4f} USDT`\n"
        f"📈 إجمالي الإيداعات: `{total_dep:.4f} USDT`\n"
        f"📉 إجمالي السحوبات: `{total_wd:.4f} USDT`\n"
        f"📊 إجمالي العمليات: `{total_tx}`",
        parse_mode="Markdown"
    )


def _handle_users(bot: TeleBot, call):
    users = get_all_users()
    bot.send_message(
        call.message.chat.id,
        f"👥 *المستخدمون النشطون*\n\n"
        f"العدد: `{len(users)}`\n\n"
        f"استخدم /admin للرجوع للوحة التحكم",
        parse_mode="Markdown"
    )


def _handle_logs(bot: TeleBot, call):
    logs = get_all_transactions(limit=20)
    if not logs:
        bot.send_message(call.message.chat.id, "📋 لا توجد عمليات بعد")
        return

    text = "📋 *آخر 20 عملية:*\n\n"
    for log in logs:
        txid_short = (log["txid"] or "—")[:12] + "..." if log["txid"] else "—"
        text += (
            f"👤 `{log['telegram_id']}` | {log['type']}\n"
            f"💰 `{log['amount']:.4f}` | {log['status']}\n"
            f"🔗 `{txid_short}`\n"
            f"📅 {log['created_at']}\n"
            f"─────────────\n"
        )
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown")


def _handle_del_button_menu(bot: TeleBot, call):
    buttons = get_custom_buttons()
    if not buttons:
        bot.send_message(call.message.chat.id, "لا توجد أزرار مضافة")
        return
    markup = types.InlineKeyboardMarkup()
    for btn in buttons:
        markup.add(types.InlineKeyboardButton(
            f"🗑️ {btn['name']}", callback_data=f"del_btn_{btn['id']}"
        ))
    bot.send_message(call.message.chat.id, "اختر الزر للحذف:", reply_markup=markup)


def _handle_wallet_balance(bot: TeleBot, call):
    """عرض رصيد المحفظة الرئيسية على TRON"""
    from tron import get_trc20_balance, WALLET_ADDRESS
    bal = get_trc20_balance(WALLET_ADDRESS)
    bot.send_message(
        call.message.chat.id,
        f"💼 *رصيد المحفظة الرئيسية*\n\n"
        f"🏦 العنوان: `{WALLET_ADDRESS}`\n"
        f"💰 الرصيد: `{bal:.6f} USDT`\n\n"
        f"_هذا الرصيد الفعلي على شبكة TRON_",
        parse_mode="Markdown"
    )


def _do_broadcast(bot: TeleBot, msg):
    if not is_admin(msg.from_user.id):
        return
    users = get_all_users()
    success = failed = 0
    for user in users:
        try:
            bot.send_message(
                user["telegram_id"],
                f"📢 *إذاعة من الإدارة:*\n\n{msg.text}",
                parse_mode="Markdown"
            )
            success += 1
            time.sleep(0.05)
        except Exception:
            failed += 1

    bot.send_message(
        msg.chat.id,
        f"✅ *اكتملت الإذاعة*\n\n"
        f"✉️ أُرسلت لـ: `{success}`\n"
        f"❌ فشلت: `{failed}`",
        parse_mode="Markdown"
    )


def _do_ban(bot: TeleBot, msg):
    if not is_admin(msg.from_user.id):
        return
    try:
        user_id = int(msg.text.strip())
        if user_id == ADMIN_ID:
            bot.send_message(msg.chat.id, "❌ لا يمكنك حظر نفسك!")
            return
        ban_user(user_id)
        bot.send_message(msg.chat.id, f"✅ تم حظر `{user_id}`", parse_mode="Markdown")
        try:
            bot.send_message(user_id, "❌ تم حظر حسابك. تواصل مع الدعم.")
        except Exception:
            pass
    except ValueError:
        bot.send_message(msg.chat.id, "❌ ID غير صحيح")


def _do_unban(bot: TeleBot, msg):
    if not is_admin(msg.from_user.id):
        return
    try:
        user_id = int(msg.text.strip())
        unban_user(user_id)
        bot.send_message(msg.chat.id, f"✅ تم فك حظر `{user_id}`", parse_mode="Markdown")
        try:
            bot.send_message(user_id, "✅ تم فك حظر حسابك. أهلاً بعودتك!")
        except Exception:
            pass
    except ValueError:
        bot.send_message(msg.chat.id, "❌ ID غير صحيح")


def _do_add_balance(bot: TeleBot, msg):
    if not is_admin(msg.from_user.id):
        return
    try:
        parts = msg.text.strip().split()
        user_id, amount = int(parts[0]), float(parts[1])
        update_balance(user_id, amount)
        add_transaction(user_id, "إضافة رصيد (أدمن)", amount, "مكتمل",
                        transaction_type="admin_credit", transaction_status="completed")
        bot.send_message(
            msg.chat.id,
            f"✅ تم إضافة `{amount} USDT` للمستخدم `{user_id}`",
            parse_mode="Markdown"
        )
        try:
            new_bal = get_balance(user_id)
            bot.send_message(
                user_id,
                f"💰 تم إضافة `{amount} USDT` لرصيدك!\n"
                f"💳 رصيدك الجديد: `{new_bal:.4f} USDT`",
                parse_mode="Markdown"
            )
        except Exception:
            pass
    except (ValueError, IndexError):
        bot.send_message(msg.chat.id, "❌ الصيغة: `123456789 50`", parse_mode="Markdown")


def _do_remove_balance(bot: TeleBot, msg):
    if not is_admin(msg.from_user.id):
        return
    try:
        parts = msg.text.strip().split()
        user_id, amount = int(parts[0]), float(parts[1])
        bal = get_balance(user_id)
        if amount > bal:
            bot.send_message(
                msg.chat.id,
                f"❌ رصيد المستخدم `{bal:.4f} USDT` أقل من `{amount} USDT`",
                parse_mode="Markdown"
            )
            return
        update_balance(user_id, -amount)
        add_transaction(user_id, "خصم رصيد (أدمن)", amount, "مكتمل",
                        transaction_type="admin_debit", transaction_status="completed")
        bot.send_message(
            msg.chat.id,
            f"✅ تم خصم `{amount} USDT` من المستخدم `{user_id}`",
            parse_mode="Markdown"
        )
    except (ValueError, IndexError):
        bot.send_message(msg.chat.id, "❌ الصيغة: `123456789 10`", parse_mode="Markdown")


def _do_add_button(bot: TeleBot, msg):
    if not is_admin(msg.from_user.id):
        return
    try:
        parts = msg.text.strip().split("|")
        if len(parts) != 3:
            raise ValueError
        name, btn_type, content = parts[0].strip(), parts[1].strip(), parts[2].strip()
        if btn_type not in ["text", "url"]:
            bot.send_message(msg.chat.id, "❌ النوع يجب أن يكون `text` أو `url`",
                             parse_mode="Markdown")
            return
        add_custom_button(name, btn_type, content)
        bot.send_message(
            msg.chat.id,
            f"✅ تم إضافة الزر *{name}* بنجاح!",
            parse_mode="Markdown"
        )
    except ValueError:
        bot.send_message(
            msg.chat.id,
            "❌ الصيغة الصحيحة:\n`اسم_الزر|text|المحتوى`",
            parse_mode="Markdown"
        )