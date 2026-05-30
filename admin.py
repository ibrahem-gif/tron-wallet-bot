"""
admin.py - نظام إدارة متطور واحترافي
"""

import os
import time
from telebot import TeleBot, types
from database import (
    get_stats, get_advanced_stats, get_all_users, get_all_users_paginated,
    ban_user, unban_user, get_balance, update_balance_atomic, 
    add_transaction, get_user, get_user_details, get_custom_buttons, 
    add_custom_button, delete_custom_button, get_all_transactions,
    update_social_link, get_all_social_links, get_user_language,
    search_users, delete_user_completely, reset_user_balance,
    get_recent_deposits, get_recent_withdrawals, get_recent_users,
    get_user_transactions_detailed
)

ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

def is_admin(telegram_id):
    """التحقق من صلاحيات الأدمن"""
    return telegram_id == ADMIN_ID

def admin_inline_menu():
    """القائمة الرئيسية للأدمن"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 الإحصائيات", callback_data="adm_stats"),
        types.InlineKeyboardButton("👥 المستخدمين", callback_data="adm_users_1")
    )
    markup.add(
        types.InlineKeyboardButton("🔍 بحث", callback_data="adm_search"),
        types.InlineKeyboardButton("📢 بث جماعي", callback_data="adm_broadcast")
    )
    markup.add(
        types.InlineKeyboardButton("📈 المراقبة", callback_data="adm_monitor"),
        types.InlineKeyboardButton("💰 إدارة الأرصدة", callback_data="adm_balance")
    )
    markup.add(
        types.InlineKeyboardButton("🔘 الأزرار", callback_data="adm_buttons"),
        types.InlineKeyboardButton("🌐 الروابط", callback_data="adm_links")
    )
    markup.add(
        types.InlineKeyboardButton("📋 السجلات", callback_data="adm_logs")
    )
    return markup

def users_list_menu(page=1):
    """قائمة المستخدمين مع الصفحات"""
    try:
        users, total_pages = get_all_users_paginated(page, per_page=10)
    except Exception:
        return types.InlineKeyboardMarkup()
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    for user in users:
        uid, username = user
        display = "@{0}".format(username) if username else "ID: {0}".format(uid)
        markup.add(types.InlineKeyboardButton(display, callback_data="user_{0}".format(uid)))
    
    nav_buttons = []
    if page > 1:
        nav_buttons.append(types.InlineKeyboardButton("⬅️ السابق", callback_data="adm_users_{0}".format(page-1)))
    
    nav_buttons.append(types.InlineKeyboardButton("{0}/{1}".format(page, total_pages), callback_data="ignore"))
    
    if page < total_pages:
        nav_buttons.append(types.InlineKeyboardButton("➡️ التالي", callback_data="adm_users_{0}".format(page+1)))
    
    if nav_buttons:
        markup.row(*nav_buttons)
    
    markup.add(types.InlineKeyboardButton("🏠 الرئيسية", callback_data="adm_home"))
    
    return markup

def user_detail_menu(telegram_id):
    """قائمة تفاصيل المستخدم"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    markup.add(
        types.InlineKeyboardButton("➕ إضافة رصيد", callback_data="uact_add_{0}".format(telegram_id)),
        types.InlineKeyboardButton("➖ خصم رصيد", callback_data="uact_rem_{0}".format(telegram_id))
    )
    markup.add(
        types.InlineKeyboardButton("🔄 تصفير الرصيد", callback_data="uact_reset_{0}".format(telegram_id)),
        types.InlineKeyboardButton("📩 إرسال إشعار", callback_data="uact_notify_{0}".format(telegram_id))
    )
    markup.add(
        types.InlineKeyboardButton("🚫 حظر", callback_data="uact_ban_{0}".format(telegram_id)),
        types.InlineKeyboardButton("✅ فك الحظر", callback_data="uact_unban_{0}".format(telegram_id))
    )
    markup.add(
        types.InlineKeyboardButton("📜 السجل", callback_data="uact_log_{0}".format(telegram_id)),
        types.InlineKeyboardButton("🗑️ حذف", callback_data="uact_del_{0}".format(telegram_id))
    )
    markup.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="adm_users_1"))
    
    return markup

def register_admin_handlers(bot):
    """تسجيل جميع معالجات الأدمن"""

    @bot.message_handler(commands=["admin"])
    def admin_panel(msg):
        if not is_admin(msg.from_user.id):
            return
        
        text = "👑 *لوحة التحكم المتقدمة*\n\nمرحباً بك في نظام الإدارة الشامل\nاختر الإجراء المطلوب:"
        
        bot.send_message(msg.chat.id, text, parse_mode="Markdown", reply_markup=admin_inline_menu())
    
    @bot.callback_query_handler(func=lambda c: c.data == "adm_stats")
    def show_advanced_stats(call):
        if not is_admin(call.from_user.id):
            return
        
        try:
            stats = get_advanced_stats()
            
            text = (
                "📊 *الإحصائيات الشاملة*\n\n"
                "👥 *المستخدمون:*\n"
                "• الإجمالي: `{0}`\n"
                "• النشطون: `{1}`\n"
                "• جدد اليوم: `{2}`\n"
                "• جدد الأسبوع: `{3}`\n"
                "• جدد الشهر: `{4}`\n"
                "• المحظورون: `{5}`\n\n"
                "💰 *المالية:*\n"
                "• إجمالي الأرصدة: `{6:.4f} USDT`\n"
                "• إجمالي الإيداعات: `{7:.4f} USDT`\n"
                "• إجمالي السحوبات: `{8:.4f} USDT`\n\n"
                "📈 *العمليات:*\n"
                "• إيداعات ناجحة: `{9}`\n"
                "• سحوبات ناجحة: `{10}`\n"
                "• سحوبات معلقة: `{11}`"
            ).format(
                stats['total_users'],
                stats['active_users'],
                stats['new_today'],
                stats['new_week'],
                stats['new_month'],
                stats['banned_count'],
                stats['total_balance'],
                stats['total_deposits'],
                stats['total_withdrawals'],
                stats['deposit_count'],
                stats['withdrawal_count'],
                stats['pending_withdrawals']
            )
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔄 تحديث", callback_data="adm_stats"))
            markup.add(types.InlineKeyboardButton("🏠 الرئيسية", callback_data="adm_home"))
            
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
        except Exception as e:
            bot.answer_callback_query(call.id, "❌ خطأ: {0}".format(str(e)), show_alert=True)
    
    @bot.callback_query_handler(func=lambda c: c.data.startswith("adm_users_"))
    def show_users_list(call):
        if not is_admin(call.from_user.id):
            return
        
        try:
            page = int(call.data.split("_")[2])
            text = "👥 *المستخدمون المسجلون*\n\nالصفحة {0}".format(page)
            
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=users_list_menu(page))
        except Exception as e:
            bot.answer_callback_query(call.id, "❌ خطأ: {0}".format(str(e)), show_alert=True)
    
    @bot.callback_query_handler(func=lambda c: c.data.startswith("user_"))
    def show_user_details(call):
        if not is_admin(call.from_user.id):
            return
        
        try:
            user_id = int(call.data.split("_")[1])
            details = get_user_details(user_id)
            
            if not details:
                bot.answer_callback_query(call.id, "❌ المستخدم غير موجود", show_alert=True)
                return
            
            status = "🚫 محظور" if details['is_banned'] else "✅ مفعل"
            
            text = (
                "👤 *معلومات المستخدم*\n\n"
                "🆔 ID: `{0}`\n"
                "📱 اليوزر: @{1}\n"
                "📅 التسجيل: `{2}`\n"
                "🌍 اللغة: `{3}`\n"
                "📊 الحالة: {4}\n\n"
                "💰 *المالية:*\n"
                "• الرصيد: `{5:.4f} USDT`\n"
                "• إجمالي الإيداعات: `{6:.4f} USDT`\n"
                "• عدد الإيداعات: `{7}`\n"
                "• إجمالي السحوبات: `{8:.4f} USDT`\n"
                "• عدد السحوبات: `{9}`\n\n"
                "⏱️ آخر نشاط: `{10}`"
            ).format(
                details['telegram_id'],
                details['username'],
                details['created_at'],
                details['language'],
                status,
                details['balance'],
                details['deposit_total'],
                details['deposit_count'],
                details['withdrawal_total'],
                details['withdrawal_count'],
                details['last_activity']
            )
            
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=user_detail_menu(user_id))
        except Exception as e:
            bot.answer_callback_query(call.id, "❌ خطأ: {0}".format(str(e)), show_alert=True)
    
    @bot.callback_query_handler(func=lambda c: c.data.startswith("uact_add_"))
    def user_add_balance(call):
        if not is_admin(call.from_user.id):
            return
        
        user_id = int(call.data.split("_")[2])
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "💰 أرسل المبلغ لإضافته للمستخدم `{0}`:".format(user_id), parse_mode="Markdown")
        bot.register_next_step_handler(call.message, lambda m: process_add_balance(bot, m, user_id))
    
    @bot.callback_query_handler(func=lambda c: c.data.startswith("uact_rem_"))
    def user_remove_balance(call):
        if not is_admin(call.from_user.id):
            return
        
        user_id = int(call.data.split("_")[2])
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "➖ أرسل المبلغ لخصمه من المستخدم `{0}`:".format(user_id), parse_mode="Markdown")
        bot.register_next_step_handler(call.message, lambda m: process_remove_balance(bot, m, user_id))
    
    @bot.callback_query_handler(func=lambda c: c.data.startswith("uact_reset_"))
    def user_reset_balance(call):
        if not is_admin(call.from_user.id):
            return
        
        user_id = int(call.data.split("_")[2])
        
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ نعم، صفّر", callback_data="confirm_reset_{0}".format(user_id)),
            types.InlineKeyboardButton("❌ إلغاء", callback_data="user_{0}".format(user_id))
        )
        
        bot.edit_message_text(
            "⚠️ *تأكيد تصفير الرصيد*\n\nهل أنت متأكد من تصفير رصيد المستخدم `{0}`؟".format(user_id),
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=markup
        )
    
    @bot.callback_query_handler(func=lambda c: c.data.startswith("confirm_reset_"))
    def confirm_reset_balance(call):
        if not is_admin(call.from_user.id):
            return
        
        user_id = int(call.data.split("_")[2])
        reset_user_balance(user_id)
        add_transaction(user_id, "تصفير رصيد (أدمن)", 0, "مكتمل", transaction_type="admin_reset")
        
        bot.answer_callback_query(call.id, "✅ تم تصفير الرصيد", show_alert=True)
        
        # العودة لصفحة المستخدم
        details = get_user_details(user_id)
        if details:
            status = "🚫 محظور" if details['is_banned'] else "✅ مفعل"
            
            text = (
                "👤 *معلومات المستخدم*\n\n"
                "🆔 ID: `{0}`\n"
                "📱 اليوزر: @{1}\n"
                "📅 التسجيل: `{2}`\n"
                "🌍 اللغة: `{3}`\n"
                "📊 الحالة: {4}\n\n"
                "💰 *المالية:*\n"
                "• الرصيد: `{5:.4f} USDT`\n"
                "• إجمالي الإيداعات: `{6:.4f} USDT`\n"
                "• عدد الإيداعات: `{7}`\n"
                "• إجمالي السحوبات: `{8:.4f} USDT`\n"
                "• عدد السحوبات: `{9}`\n\n"
                "⏱️ آخر نشاط: `{10}`"
            ).format(
                details['telegram_id'],
                details['username'],
                details['created_at'],
                details['language'],
                status,
                details['balance'],
                details['deposit_total'],
                details['deposit_count'],
                details['withdrawal_total'],
                details['withdrawal_count'],
                details['last_activity']
            )
            
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=user_detail_menu(user_id))
    
    @bot.callback_query_handler(func=lambda c: c.data.startswith("uact_notify_"))
    def user_notify(call):
        if not is_admin(call.from_user.id):
            return
        
        user_id = int(call.data.split("_")[2])
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "📩 أرسل الإشعار للمستخدم `{0}`:".format(user_id), parse_mode="Markdown")
        bot.register_next_step_handler(call.message, lambda m: process_notify(bot, m, user_id))
    
    @bot.callback_query_handler(func=lambda c: c.data.startswith("uact_ban_"))
    def user_ban(call):
        if not is_admin(call.from_user.id):
            return
        
        user_id = int(call.data.split("_")[2])
        ban_user(user_id)
        
        bot.answer_callback_query(call.id, "🚫 تم حظر المستخدم", show_alert=True)
        
        try:
            bot.send_message(user_id, "❌ تم حظر حسابك. تواصل مع الدعم.")
        except:
            pass
        
        details = get_user_details(user_id)
        if details:
            status = "🚫 محظور" if details['is_banned'] else "✅ مفعل"
            text = (
                "👤 *معلومات المستخدم*\n\n"
                "🆔 ID: `{0}`\n"
                "📱 اليوزر: @{1}\n"
                "📅 التسجيل: `{2}`\n"
                "🌍 اللغة: `{3}`\n"
                "📊 الحالة: {4}\n\n"
                "💰 *المالية:*\n"
                "• الرصيد: `{5:.4f} USDT`\n"
                "• إجمالي الإيداعات: `{6:.4f} USDT`\n"
                "• عدد الإيداعات: `{7}`\n"
                "• إجمالي السحوبات: `{8:.4f} USDT`\n"
                "• عدد السحوبات: `{9}`\n\n"
                "⏱️ آخر نشاط: `{10}`"
            ).format(
                details['telegram_id'],
                details['username'],
                details['created_at'],
                details['language'],
                status,
                details['balance'],
                details['deposit_total'],
                details['deposit_count'],
                details['withdrawal_total'],
                details['withdrawal_count'],
                details['last_activity']
            )
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=user_detail_menu(user_id))
    
    @bot.callback_query_handler(func=lambda c: c.data.startswith("uact_unban_"))
    def user_unban(call):
        if not is_admin(call.from_user.id):
            return
        
        user_id = int(call.data.split("_")[2])
        unban_user(user_id)
        
        bot.answer_callback_query(call.id, "✅ تم فك الحظر", show_alert=True)
        
        try:
            bot.send_message(user_id, "✅ تم فك حظر حسابك. أهلاً بعودتك!")
        except:
            pass
        
        details = get_user_details(user_id)
        if details:
            status = "🚫 محظور" if details['is_banned'] else "✅ مفعل"
            text = (
                "👤 *معلومات المستخدم*\n\n"
                "🆔 ID: `{0}`\n"
                "📱 اليوزر: @{1}\n"
                "📅 التسجيل: `{2}`\n"
                "🌍 اللغة: `{3}`\n"
                "📊 الحالة: {4}\n\n"
                "💰 *المالية:*\n"
                "• الرصيد: `{5:.4f} USDT`\n"
                "• إجمالي الإيداعات: `{6:.4f} USDT`\n"
                "• عدد الإيداعات: `{7}`\n"
                "• إجمالي السحوبات: `{8:.4f} USDT`\n"
                "• عدد السحوبات: `{9}`\n\n"
                "⏱️ آخر نشاط: `{10}`"
            ).format(
                details['telegram_id'],
                details['username'],
                details['created_at'],
                details['language'],
                status,
                details['balance'],
                details['deposit_total'],
                details['deposit_count'],
                details['withdrawal_total'],
                details['withdrawal_count'],
                details['last_activity']
            )
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=user_detail_menu(user_id))
    
    @bot.callback_query_handler(func=lambda c: c.data.startswith("uact_log_"))
    def user_log(call):
        if not is_admin(call.from_user.id):
            return
        
        user_id = int(call.data.split("_")[2])
        transactions = get_user_transactions_detailed(user_id, limit=10)
        
        if not transactions:
            bot.answer_callback_query(call.id, "لا توجد عمليات", show_alert=True)
            return
        
        text = "📜 *سجل عمليات المستخدم {0}*\n\n".format(user_id)
        
        for tx in transactions:
            tx_type, amount, status, txid, wallet, fee, created = tx
            txid_short = (txid or "—")[:10] + "..." if txid else "—"
            text += "• `{0}` - `{1:.4f} USDT`\n  {2} | {3}\n  🔗 {4}\n\n".format(tx_type, amount, status, created, txid_short)
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="user_{0}".format(user_id)))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
    
    @bot.callback_query_handler(func=lambda c: c.data.startswith("uact_del_"))
    def user_delete(call):
        if not is_admin(call.from_user.id):
            return
        
        user_id = int(call.data.split("_")[2])
        
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("⚠️ نعم، احذف نهائياً", callback_data="confirm_del_{0}".format(user_id)),
            types.InlineKeyboardButton("❌ إلغاء", callback_data="user_{0}".format(user_id))
        )
        
        bot.edit_message_text(
            "⚠️ *تحذير: حذف نهائي!*\n\nهل أنت متأكد من حذف المستخدم `{0}` نهائياً؟\n\nسيتم حذف جميع بياناته ومعاملاته!".format(user_id),
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=markup
        )
    
    @bot.callback_query_handler(func=lambda c: c.data.startswith("confirm_del_"))
    def confirm_delete_user(call):
        if not is_admin(call.from_user.id):
            return
        
        user_id = int(call.data.split("_")[2])
        
        if delete_user_completely(user_id):
            bot.answer_callback_query(call.id, "✅ تم الحذف نهائياً", show_alert=True)
            bot.edit_message_text(
                "✅ تم حذف المستخدم `{0}` نهائياً".format(user_id),
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown",
                reply_markup=types.InlineKeyboardMarkup().add(
                    types.InlineKeyboardButton("🏠 الرئيسية", callback_data="adm_home")
                )
            )
        else:
            bot.answer_callback_query(call.id, "❌ فشل الحذف", show_alert=True)
    
    @bot.callback_query_handler(func=lambda c: c.data == "adm_search")
    def admin_search(call):
        if not is_admin(call.from_user.id):
            return
        
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "🔍 *البحث عن مستخدم*\n\nأرسل:\n• ID المستخدم\n• اليوزرنيم\n• جزء من الاسم", parse_mode="Markdown")
        bot.register_next_step_handler(call.message, lambda m: process_search(bot, m))
    
    @bot.callback_query_handler(func=lambda c: c.data == "adm_broadcast")
    def admin_broadcast(call):
        if not is_admin(call.from_user.id):
            return
        
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "📢 *البث الجماعي*\n\nأرسل الرسالة التي تريد إرسالها لجميع المستخدمين:", parse_mode="Markdown")
        bot.register_next_step_handler(call.message, lambda m: process_broadcast(bot, m))
    
    @bot.callback_query_handler(func=lambda c: c.data == "adm_monitor")
    def admin_monitor(call):
        if not is_admin(call.from_user.id):
            return
        
        try:
            deposits = get_recent_deposits(5)
            withdrawals = get_recent_withdrawals(5)
            users = get_recent_users(5)
            
            dep_text = ""
            for dep in deposits:
                dep_text += "• `{0}` - `{1:.4f} USDT` ({2})\n".format(dep[0], dep[1], dep[2])
            
            wd_text = ""
            for wd in withdrawals:
                wd_text += "• `{0}` - `{1:.4f} USDT` ({2})\n".format(wd[0], wd[1], wd[2])
            
            usr_text = ""
            for usr in users:
                usr_text += "• `{0}` - @{1} ({2})\n".format(usr[0], usr[1] or "بدون", usr[2])
            
            text = (
                "📈 *لوحة المراقبة*\n\n"
                "📥 *آخر الإيداعات:*\n{0}\n\n"
                "📤 *آخر السحوبات:*\n{1}\n\n"
                "👥 *آخر المستخدمين:*\n{2}"
            ).format(dep_text or "لا يوجد", wd_text or "لا يوجد", usr_text or "لا يوجد")
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔄 تحديث", callback_data="adm_monitor"))
            markup.add(types.InlineKeyboardButton("🏠 الرئيسية", callback_data="adm_home"))
            
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
        except Exception as e:
            bot.answer_callback_query(call.id, "❌ خطأ: {0}".format(str(e)), show_alert=True)
    
    @bot.callback_query_handler(func=lambda c: c.data == "adm_home")
    def admin_home(call):
        if not is_admin(call.from_user.id):
            return
        
        text = "👑 *لوحة التحكم المتقدمة*\n\nاختر الإجراء:"
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=admin_inline_menu())


def process_add_balance(bot, msg, user_id):
    """معالجة إضافة الرصيد"""
    if not is_admin(msg.from_user.id):
        return
    
    try:
        amount = float(msg.text.strip())
        
        if amount <= 0:
            bot.send_message(msg.chat.id, "❌ المبلغ يجب أن يكون أكبر من صفر")
            return
        
        if update_balance_atomic(user_id, amount):
            add_transaction(user_id, "إضافة رصيد (أدمن)", amount, "مكتمل", transaction_type="admin_credit")
            bot.send_message(msg.chat.id, "✅ تم إضافة `{0:.4f} USDT` للمستخدم `{1}`".format(amount, user_id), parse_mode="Markdown")
            
            try:
                bot.send_message(user_id, "💰 تم إضافة `{0:.4f} USDT` لرصيدك من الإدارة".format(amount), parse_mode="Markdown")
            except:
                pass
        else:
            bot.send_message(msg.chat.id, "❌ فشلت العملية")
    except ValueError:
        bot.send_message(msg.chat.id, "❌ أدخل رقماً صحيحاً")


def process_remove_balance(bot, msg, user_id):
    """معالجة خصم الرصيد"""
    if not is_admin(msg.from_user.id):
        return
    
    try:
        amount = float(msg.text.strip())
        
        if amount <= 0:
            bot.send_message(msg.chat.id, "❌ المبلغ يجب أن يكون أكبر من صفر")
            return
        
        if update_balance_atomic(user_id, -amount, min_balance=0):
            add_transaction(user_id, "خصم رصيد (أدمن)", amount, "مكتمل", transaction_type="admin_debit")
            bot.send_message(msg.chat.id, "✅ تم خصم `{0:.4f} USDT` من المستخدم `{1}`".format(amount, user_id), parse_mode="Markdown")
        else:
            bot.send_message(msg.chat.id, "❌ رصيد غير كافٍ أو فشلت العملية")
    except ValueError:
        bot.send_message(msg.chat.id, "❌ أدخل رقماً صحيحاً")


def process_notify(bot, msg, user_id):
    """معالجة إرسال الإشعار"""
    if not is_admin(msg.from_user.id):
        return
    
    try:
        bot.send_message(user_id, "📩 *إشعار من الإدارة:*\n\n{0}".format(msg.text), parse_mode="Markdown")
        bot.send_message(msg.chat.id, "✅ تم إرسال الإشعار للمستخدم `{0}`".format(user_id), parse_mode="Markdown")
    except Exception as e:
        bot.send_message(msg.chat.id, "❌ فشل الإرسال: {0}".format(str(e)))


def process_search(bot, msg):
    """معالجة البحث عن مستخدم"""
    if not is_admin(msg.from_user.id):
        return
    
    query = msg.text.strip()
    results = search_users(query)
    
    if not results:
        bot.send_message(msg.chat.id, "❌ لم يتم العثور على نتائج")
        return
    
    text = "🔍 *نتائج البحث عن: {0}*\n\n".format(query)
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    for user in results:
        uid, username = user
        display = "@{0}".format(username) if username else "ID: {0}".format(uid)
        text += "• {0}\n".format(display)
        markup.add(types.InlineKeyboardButton(display, callback_data="user_{0}".format(uid)))
    
    markup.add(types.InlineKeyboardButton("🏠 الرئيسية", callback_data="adm_home"))
    
    bot.send_message(msg.chat.id, text, parse_mode="Markdown", reply_markup=markup)


def process_broadcast(bot, msg):
    """معالجة البث الجماعي"""
    if not is_admin(msg.from_user.id):
        return
    
    users = get_all_users()
    total = len(users)
    success = 0
    failed = 0
    
    progress_msg = bot.send_message(msg.chat.id, "📢 جاري الإرسال...\n\n0 / {0}".format(total))
    
    for idx, user in enumerate(users, 1):
        try:
            bot.send_message(user[0], "📢 *إذاعة:*\n\n{0}".format(msg.text), parse_mode="Markdown")
            success += 1
        except Exception:
            failed += 1
        
        if idx % 10 == 0:
            try:
                bot.edit_message_text(
                    "📢 جاري الإرسال...\n\n{0} / {1}\n✅ نجح: {2}\n❌ فشل: {3}".format(idx, total, success, failed),
                    msg.chat.id,
                    progress_msg.message_id
                )
            except:
                pass
        
        time.sleep(0.05)
    
    bot.edit_message_text(
      
      "✅ *اكتمل البث الجماع"
    )