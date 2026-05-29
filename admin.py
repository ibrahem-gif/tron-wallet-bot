"""
admin.py - لوحة تحكم الأدمن الكاملة
"""

import os
import time
from telebot import TeleBot, types
from database import (
    get_stats, get_all_users, ban_user, unban_user,
    get_balance, update_balance_atomic, add_transaction,
    get_user, get_custom_buttons, add_custom_button, delete_custom_button,
    get_all_transactions, update_social_link, get_all_social_links,
    get_user_language
)

ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

def is_admin(telegram_id: int) -> bool:
    """التحقق من أنه أدمن"""
    return telegram_id == ADMIN_ID

def admin_inline_menu() -> types.InlineKeyboardMarkup:
    """قائمة الأدمن الرئيسية"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 الإحصائيات", callback_data="a_stats"),
        types.InlineKeyboardButton("👥 المستخدمين", callback_data="a_users")
    )
    markup.add(
        types.InlineKeyboardButton("🚫 حظر", callback_data="a_ban"),
        types.InlineKeyboardButton("✅ فك حظر", callback_data="a_unban")
    )
    markup.add(
        types.InlineKeyboardButton("📢 إذاعة", callback_data="a_broadcast"),
        types.InlineKeyboardButton("💰 إضافة رصيد", callback_data="a_add_bal")
    )
    markup.add(
        types.InlineKeyboardButton("➖ خصم رصيد", callback_data="a_rem_bal"),
        types.InlineKeyboardButton("🔘 أزرار", callback_data="a_btn")
    )
    markup.add(
        types.InlineKeyboardButton("🌐 روابط", callback_data="a_social"),
        types.InlineKeyboardButton("📋 سجل", callback_data="a_logs")
    )
    return markup

def register_admin_handlers(bot: TeleBot):
    """تسجيل معالجات الأدمن"""

    @bot.message_handler(commands=["admin"])
    def admin_panel(msg):
        """لوحة الأدمن الرئيسية"""
        if not is_admin(msg.from_user.id):
            return
        bot.send_message(msg.chat.id, "👑 *لوحة التحكم*", parse_mode="Markdown", reply_markup=admin_inline_menu())

    @bot.callback_query_handler(func=lambda c: c.data.startswith("a_"))
    def admin_callbacks(call):
        """معالجة أزرار الأدمن"""
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية")
            return
        
        bot.answer_callback_query(call.id)
        
        if call.data == "a_stats":
            handle_stats(bot, call)
        elif call.data == "a_users":
            handle_users(bot, call)
        elif call.data == "a_broadcast":
            bot.send_message(call.message.chat.id, "📢 أرسل نص الإذاعة:")
            bot.register_next_step_handler(call.message, lambda m: do_broadcast(bot, m))
        elif call.data == "a_ban":
            bot.send_message(call.message.chat.id, "🚫 أرسل ID المستخدم:")
            bot.register_next_step_handler(call.message, lambda m: do_ban(bot, m))
        elif call.data == "a_unban":
            bot.send_message(call.message.chat.id, "✅ أرسل ID المستخدم:")
            bot.register_next_step_handler(call.message, lambda m: do_unban(bot, m))
        elif call.data == "a_add_bal":
            bot.send_message(call.message.chat.id, "💰 أرسل: `ID المبلغ`\nمثال: `123456789 50`", parse_mode="Markdown")
            bot.register_next_step_handler(call.message, lambda m: do_add_balance(bot, m))
        elif call.data == "a_rem_bal":
            bot.send_message(call.message.chat.id, "➖ أرسل: `ID المبلغ`\nمثال: `123456789 10`", parse_mode="Markdown")
            bot.register_next_step_handler(call.message, lambda m: do_remove_balance(bot, m))
        elif call.data == "a_btn":
            handle_buttons_menu(bot, call)
        elif call.data == "a_social":
            bot.send_message(call.message.chat.id, "🌐 أرسل: `platform|url`\nمثال: `telegram|https://t.me/channel`", parse_mode="Markdown")
            bot.register_next_step_handler(call.message, lambda m: do_update_social(bot, m))
        elif call.data == "a_logs":
            handle_logs(bot, call)

    @bot.callback_query_handler(func=lambda c: c.data == "add_btn")
    def add_btn_callback(call):
        """إضافة زر"""
        if not is_admin(call.from_user.id):
            return
        bot.send_message(call.message.chat.id, "أرسل: `اسم|نوع|محتوى`\nمثال: `مساعدة|text|مرحباً!`", parse_mode="Markdown")
        bot.register_next_step_handler(call.message, lambda m: do_add_button(bot, m))

    @bot.callback_query_handler(func=lambda c: c.data == "del_btn_menu")
    def del_buttons_menu_callback(call):
        """قائمة حذف الأزرار"""
        if not is_admin(call.from_user.id):
            return
        buttons = get_custom_buttons()
        if not buttons:
            bot.send_message(call.message.chat.id, "لا توجد أزرار")
            return
        markup = types.InlineKeyboardMarkup()
        for btn in buttons:
            markup.add(types.InlineKeyboardButton(f"🗑️ {btn[1]}", callback_data=f"del_btn_{btn[0]}"))
        bot.send_message(call.message.chat.id, "اختر الزر:", reply_markup=markup)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("del_btn_"))
    def delete_button_callback(call):
        """حذف زر"""
        if not is_admin(call.from_user.id):
            return
        try:
            btn_id = int(call.data.split("_")[2])
            delete_custom_button(btn_id)
            bot.answer_callback_query(call.id, "✅ تم الحذف")
            bot.send_message(call.message.chat.id, "✅ تم حذف الزر")
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ خطأ: {e}", show_alert=True)

# ==================== دوال مساعدة ====================

def handle_stats(bot: TeleBot, call):
    """عرض الإحصائيات"""
    total_users, total_balance, total_tx, banned, total_dep, total_wd = get_stats()
    text = (
        f"📊 *الإحصائيات*\n\n"
        f"👥 المستخدمون: `{total_users}`\n"
        f"🚫 المحظورون: `{banned}`\n"
        f"💰 إجمالي الأرصدة: `{total_balance:.4f} USDT`\n"
        f"📈 إجمالي الإيداعات: `{total_dep:.4f} USDT`\n"
        f"📉 إجمالي السحوبات: `{total_wd:.4f} USDT`\n"
        f"📊 إجمالي العمليات: `{total_tx}`"
    )
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

def handle_users(bot: TeleBot, call):
    """عرض المستخدمين"""
    users = get_all_users()
    text = f"👥 *المستخدمون*\n\nالعدد: `{len(users)}`"
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

def handle_buttons_menu(bot: TeleBot, call):
    """قائمة إدارة الأزرار"""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ إضافة زر", callback_data="add_btn"))
    markup.add(types.InlineKeyboardButton("🗑️ حذف زر", callback_data="del_btn_menu"))
    bot.send_message(call.message.chat.id, "🔘 *إدارة الأزرار*", parse_mode="Markdown", reply_markup=markup)

def handle_logs(bot: TeleBot, call):
    """عرض السجل"""
    logs = get_all_transactions(limit=20)
    if not logs:
        bot.send_message(call.message.chat.id, "لا توجد عمليات")
        return
    
    text = "📋 *آخر 20 عملية*\n\n"
    for log in logs:
        txid_short = (log[4] or "—")[:12] + "..." if log[4] else "—"
        text += f"👤 `{log[0]}` | {log[1]}\n💰 `{log[2]:.4f}` | {log[3]}\n🔗 `{txid_short}`\n─────────────\n"
    
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

def do_broadcast(bot: TeleBot, msg):
    """إذاعة رسالة"""
    if not is_admin(msg.from_user.id):
        return
    
    users = get_all_users()
    success = failed = 0
    
    for user_id in users:
        try:
            bot.send_message(user_id, f"📢 *إذاعة*\n\n{msg.text}", parse_mode="Markdown")
            success += 1
            time.sleep(0.05)
        except Exception:
            failed += 1
    
    bot.send_message(msg.chat.id, f"✅ تم الإرسال لـ: `{success}`\n❌ فشل: `{failed}`", parse_mode="Markdown")

def do_ban(bot: TeleBot, msg):
    """حظر مستخدم"""
    if not is_admin(msg.from_user.id):
        return
    try:
        user_id = int(msg.text.strip())
        if user_id == ADMIN_ID:
            bot.send_message(msg.chat.id, "❌ لا يمكن حظر الأدمن")
            return
        ban_user(user_id)
        bot.send_message(msg.chat.id, f"✅ تم حظر `{user_id}`", parse_mode="Markdown")
        try:
            bot.send_message(user_id, "❌ تم حظر حسابك. تواصل مع الدعم.")
        except Exception:
            pass
    except ValueError:
        bot.send_message(msg.chat.id, "❌ ID غير صحيح")

def do_unban(bot: TeleBot, msg):
    """فك حظر"""
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

def do_add_balance(bot: TeleBot, msg):
    """إضافة رصيد"""
    if not is_admin(msg.from_user.id):
        return
    try:
        parts = msg.text.strip().split()
        user_id, amount = int(parts[0]), float(parts[1])
        
        if update_balance_atomic(user_id, amount, min_balance=0):
            add_transaction(user_id, "إضافة رصيد (أدمن)", amount, "مكتمل", transaction_type="admin_credit", transaction_status="completed")
            bot.send_message(msg.chat.id, f"✅ تم إضافة `{amount} USDT` للمستخدم `{user_id}`", parse_mode="Markdown")
            try:
                new_bal = get_balance(user_id)
                bot.send_message(user_id, f"💰 تم إضافة `{amount} USDT` لرصيدك!\n💳 الرصيد الجديد: `{new_bal:.4f} USDT`", parse_mode="Markdown")
            except Exception:
                pass
        else:
            bot.send_message(msg.chat.id, "❌ فشل الإضافة")
    except (ValueError, IndexError):
        bot.send_message(msg.chat.id, "❌ صيغة خاطئة. استخدم: `ID المبلغ`")

def do_remove_balance(bot: TeleBot, msg):
    """خصم رصيد"""
    if not is_admin(msg.from_user.id):
        return
    try:
        parts = msg.text.strip().split()
        user_id, amount = int(parts[0]), float(parts[1])
        
        bal = get_balance(user_id)
        if amount > bal:
            bot.send_message(msg.chat.id, f"❌ رصيد المستخدم `{bal:.4f}` أقل من `{amount}`", parse_mode="Markdown")
            return
        
        if update_balance_atomic(user_id, -amount, min_balance=0):
            add_transaction(user_id, "خصم رصيد (أدمن)", amount, "مكتمل", transaction_type="admin_debit", transaction_status="completed")
            bot.send_message(msg.chat.id, f"✅ تم خصم `{amount} USDT` من المستخدم `{user_id}`", parse_mode="Markdown")
        else:
            bot.send_message(msg.chat.id, "❌ فشل الخصم")
    except (ValueError, IndexError):
        bot.send_message(msg.chat.id, "❌ صيغة خاطئة. استخدم: `ID المبلغ`")

def do_add_button(bot: TeleBot, msg):
    """إضافة زر"""
    if not is_admin(msg.from_user.id):
        return
    try:
        parts = msg.text.strip().split("|")
        if len(parts) != 3:
            raise ValueError
        name, btn_type, content = parts[0].strip(), parts[1].strip(), parts[2].strip()
        if btn_type not in ["text", "url"]:
            bot.send_message(msg.chat.id, "❌ النوع يجب أن يكون: `text` أو `url`", parse_mode="Markdown")
            return
        add_custom_button(name, btn_type, content)
        bot.send_message(msg.chat.id, f"✅ تم إضافة الزر `{name}`", parse_mode="Markdown")
    except ValueError:
        bot.send_message(msg.chat.id, "❌ صيغة خاطئة. استخدم: `اسم|نوع|محتوى`")

def do_update_social(bot: TeleBot, msg):
    """تحديث الروابط"""
    if not is_admin(msg.from_user.id):
        return
    try:
        parts = msg.text.strip().split("|")
        if len(parts) == 2:
            platform, url = parts[0].strip().lower(), parts[1].strip()
            update_social_link(platform, url)
            bot.send_message(msg.chat.id, f"✅ تم تحديث `{platform}`", parse_mode="Markdown")
        else:
            raise ValueError
    except ValueError:
        bot.send_message(msg.chat.id, "❌ صيغة خاطئة. استخدم: `platform|url`")