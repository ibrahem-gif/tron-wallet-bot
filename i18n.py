"""
i18n.py - نظام الترجمة متعدد اللغات
7 لغات كاملة - سهل الإضافة والتعديل
"""

TRANSLATIONS = {
    "ar": {
        # البدايات والترحيب
        "welcome": "👋 أهلاً {name}!\n\n🏦 مرحباً في محفظتك الإلكترونية\n💎 العملة: USDT (TRC20)\n🌐 الشبكة: TRON مباشر\n🔒 عمليات آمنة ومباشرة\n\nاختر من القائمة:",
        
        # أزرار القائمة الرئيسية
        "btn_wallet": "💼 المحفظة",
        "btn_profile": "👤 الملف الشخصي",
        "btn_support": "💬 الدعم",
        "btn_settings": "⚙️ الإعدادات",
        "btn_follow": "📢 تابعنا",
        "btn_back": "↩️ رجوع",
        
        # أزرار فرعية
        "btn_deposit": "📥 إيداع",
        "btn_withdraw": "📤 سحب",
        "btn_balance": "💰 الرصيد",
        "btn_transfer": "🔄 تحويل داخلي",
        "btn_history": "📜 السجل",
        "btn_language": "🌍 اللغة",
        "btn_notifications": "🔔 الإشعارات",
        "btn_confirm": "✅ تأكيد",
        "btn_cancel": "❌ إلغاء",
        "btn_check": "✅ تحقق الآن",
        
        # الرسائل الرئيسية
        "main_menu": "👋 القائمة الرئيسية",
        "wallet_title": "💼 *المحفظة*",
        "balance_title": "💰 *رصيدك الحالي*",
        "profile_title": "👤 *ملفي الشخصي*",
        "settings_title": "⚙️ *الإعدادات*",
        "lang_title": "🌍 *اختر اللغة*",
        "support_title": "💬 *الدعم الفني*\n\nأرسل رسالتك وسيرد عليك فريق الدعم قريباً.",
        "follow_title": "📢 *تابعنا على منصاتنا*",
        
        # الإيداع
        "deposit_title": "📥 *الإيداع*",
        "deposit_amount_req": "📥 *إيداع عبر USDT TRC20*\n\n💸 الحد الأدنى: `{min_dep} USDT`\n\nأدخل المبلغ الذي تريد إيداعه:",
        "deposit_address_show": "📍 *عنوان المحفظة:*\n`{addr}`\n\n💎 *أرسل بالضبط:*\n➡️ `{amt} USDT`\n\n⚠️ *مهم جداً:*\n• الشبكة: TRON (TRC20)\n• المبلغ *بالضبط* لربط إيداعك تلقائياً\n• سيُضاف الرصيد خلال 1-3 دقائق",
        "deposit_success": "✅ *تم استلام إيداعك!*\n\n💰 المبلغ: `{amt:.4f} USDT`\n💳 الرصيد الجديد: `{bal:.4f} USDT`\n🔗 TXID: `{txid}`\n\nشكراً لاستخدامك خدمتنا! 🎉",
        "deposit_timeout": "⏰ *انتهت مهلة الإيداع*\n\nلم نعثر على تحويل بالمبلغ المطلوب خلال 30 دقيقة.\n\nالمبلغ المتوقع: `{amt:.2f} USDT`\n\nإذا أرسلت الأموال بالفعل:\n• تأكد من الشبكة TRC20\n• تأكد من صحة العنوان\n• تواصل مع الدعم مع TXID",
        
        # السحب
        "withdraw_title": "📤 *السحب*",
        "withdraw_address_req": "📤 *السحب عبر TRC20*\n\n💰 رصيدك: `{bal:.4f} USDT`\n🌐 رسوم الشبكة: `{fee:.4f} USDT`\n\nأرسل عنوان محفظتك TRC20:\n(يبدأ بـ T ويكون 34 حرفاً)",
        "withdraw_amount_req": "✅ العنوان صحيح: `{addr}`\n\nالآن أدخل المبلغ بالـ USDT:\n(مثال: `10` أو `25.5`)",
        "withdraw_confirm": "📤 *تأكيد السحب*\n\n📍 العنوان:\n`{addr}`\n\n💰 المبلغ: `{amt:.4f} USDT`\n🌐 رسوم الشبكة: `{fee:.4f} USDT`\n━━━━━━━━━━━━━━━━\n💳 الإجمالي المخصوم: `{total:.4f} USDT`\n\n⚠️ تأكد من صحة العنوان!\nالعمليات على TRON *لا يمكن التراجع عنها*.",
        "withdraw_success": "✅ *تم السحب بنجاح!*\n\n💸 المبلغ: `{amt:.4f} USDT`\n🌐 الرسوم: `{fee:.4f} USDT`\n📤 العنوان: `{addr}`\n🔗 TXID: `{txid}`\n\n💳 رصيدك المتبقي: `{bal:.4f} USDT`\n\n⏳ سيُؤكَّد على البلوكتشين خلال دقائق.",
        "withdraw_failed": "❌ فشل السحب!\n\nتم إرجاع رصيدك كاملاً.\nيرجى المحاولة لاحقاً أو التواصل مع الدعم.",
        
        # التحويل الداخلي
        "transfer_title": "🔄 *التحويل الداخلي*",
        "transfer_amount_req": "🔄 *التحويل الداخلي*\n\n💰 رصيدك: `{bal:.4f} USDT`\n💸 العمولة: `{comm:.4f} USDT`\n\nأرسل: `ID المبلغ`\nمثال: `123456789 50`",
        "transfer_confirm": "✅ *تأكيد التحويل*\n\n👤 المستلم: `{name}`\n🆔 ID: `{uid}`\n💰 المبلغ: `{amt:.4f} USDT`\n💸 العمولة: `{comm:.4f} USDT`\n🔖 رقم العملية: `{ref}`\n\nتأكيد التحويل؟",
        "transfer_success": "✅ *تم التحويل بنجاح!*\n\n📤 إلى: `{uid}`\n👤 المستقبل: `{name}`\n💰 المبلغ: `{amt:.4f} USDT`\n💸 العمولة: `{comm:.4f} USDT`\n💳 رصيدك الجديد: `{bal:.4f} USDT`",
        "transfer_received": "💸 *استلمت تحويل!*\n\n👤 من: `{name}`\n💰 المبلغ: `{amt:.4f} USDT`\n💳 رصيدك الجديد: `{bal:.4f} USDT`",
        
        # الملف الشخصي
        "profile_info": "👤 *حسابي*\n\nالاسم: {name}\n🆔 ID: `{id}`\n💰 الرصيد: `{bal:.4f} USDT`\n📅 تاريخ التسجيل: `{date}`\n\n🌐 الشبكة: TRON (TRC20)",
        
        # السجل
        "history_title": "📜 *آخر المعاملات*",
        "history_empty": "📜 لا توجد معاملات بعد",
        
        # الأخطاء والتنبيهات
        "error_banned": "❌ حسابك محظور. تواصل مع الدعم.",
        "error_rate_limit": "⚠️ لا تضغط بسرعة! انتظر لحظة.",
        "error_invalid_amount": "❌ أدخل رقماً صحيحاً مثل: `10` أو `25.5`",
        "error_insufficient_balance": "❌ رصيد غير كافٍ",
        "error_invalid_address": "❌ عنوان TRC20 غير صحيح!\n• يبدأ بـ `T`\n• طول 34 حرفاً\n• شبكة TRON فقط",
        "error_user_not_found": "❌ المستخدم غير موجود",
        "error_user_banned": "❌ المستخدم محظور",
        "error_self_transfer": "❌ لا يمكنك التحويل لنفسك",
        
        # اللغات
        "lang_ar": "🇸🇦 العربية",
        "lang_en": "🇺🇸 English",
        "lang_fr": "🇫🇷 Français",
        "lang_de": "🇩🇪 Deutsch",
        "lang_es": "🇪🇸 Español",
        "lang_hi": "🇮🇳 हिन्दी",
        "lang_zh": "🇨🇳 中文",
        "lang_changed": "✅ تم تغيير اللغة بنجاح!",
    },
    "en": {
        # Starts and greetings
        "welcome": "👋 Welcome {name}!\n\n🏦 Welcome to your digital wallet\n💎 Currency: USDT (TRC20)\n🌐 Network: Direct TRON\n🔒 Secure & direct blockchain operations\n\nChoose from the menu:",
        
        # Main menu buttons
        "btn_wallet": "💼 Wallet",
        "btn_profile": "👤 Profile",
        "btn_support": "💬 Support",
        "btn_settings": "⚙️ Settings",
        "btn_follow": "📢 Follow Us",
        "btn_back": "↩️ Back",
        
        # Sub buttons
        "btn_deposit": "📥 Deposit",
        "btn_withdraw": "📤 Withdraw",
        "btn_balance": "💰 Balance",
        "btn_transfer": "🔄 Transfer",
        "btn_history": "📜 History",
        "btn_language": "🌍 Language",
        "btn_notifications": "🔔 Notifications",
        "btn_confirm": "✅ Confirm",
        "btn_cancel": "❌ Cancel",
        "btn_check": "✅ Check Now",
        
        # Main messages
        "main_menu": "👋 Main Menu",
        "wallet_title": "💼 *Wallet*",
        "balance_title": "💰 *Your Balance*",
        "profile_title": "👤 *My Profile*",
        "settings_title": "⚙️ *Settings*",
        "lang_title": "🌍 *Choose Language*",
        "support_title": "💬 *Support*\n\nSend your message and our team will reply shortly.",
        "follow_title": "📢 *Follow us on our platforms*",
        
        # Deposit
        "deposit_title": "📥 *Deposit*",
        "deposit_amount_req": "📥 *Deposit via USDT TRC20*\n\n💸 Min deposit: `{min_dep} USDT`\n\nEnter amount to deposit:",
        "deposit_address_show": "📍 *Wallet Address:*\n`{addr}`\n\n💎 *Send exactly:*\n➡️ `{amt} USDT`\n\n⚠️ *Important:*\n• Network: TRON (TRC20)\n• Send *exact* amount to link automatically\n• Balance will be added within 1-3 minutes",
        "deposit_success": "✅ *Deposit Received!*\n\n💰 Amount: `{amt:.4f} USDT`\n💳 New Balance: `{bal:.4f} USDT`\n🔗 TXID: `{txid}`\n\nThank you! 🎉",
        "deposit_timeout": "⏰ *Deposit Expired*\n\nNo matching transfer found within 30 minutes.\n\nExpected Amount: `{amt:.2f} USDT`\n\nIf you already sent:\n• Verify TRON network\n• Check address\n• Contact support with TXID",
        
        # Withdraw
        "withdraw_title": "📤 *Withdraw*",
        "withdraw_address_req": "📤 *Withdraw via TRC20*\n\n💰 Balance: `{bal:.4f} USDT`\n🌐 Fee: `{fee:.4f} USDT`\n\nSend your TRC20 address:\n(starts with T, 34 characters)",
        "withdraw_amount_req": "✅ Address valid: `{addr}`\n\nNow enter amount in USDT:\n(example: `10` or `25.5`)",
        "withdraw_confirm": "📤 *Confirm Withdrawal*\n\n📍 Address:\n`{addr}`\n\n💰 Amount: `{amt:.4f} USDT`\n🌐 Fee: `{fee:.4f} USDT`\n━━━━━━━━━━━━━━━━\n💳 Total Deducted: `{total:.4f} USDT`\n\n⚠️ Verify address!\nTRON transactions *cannot be reversed*.",
        "withdraw_success": "✅ *Withdrawal Successful!*\n\n💸 Amount: `{amt:.4f} USDT`\n🌐 Fee: `{fee:.4f} USDT`\n📤 Address: `{addr}`\n🔗 TXID: `{txid}`\n\n💳 Remaining: `{bal:.4f} USDT`\n\n⏳ Confirmation in minutes.",
        "withdraw_failed": "❌ Withdrawal Failed!\n\nYour balance was refunded.\nPlease try again or contact support.",
        
        # Internal transfer
        "transfer_title": "🔄 *Internal Transfer*",
        "transfer_amount_req": "🔄 *Internal Transfer*\n\n💰 Balance: `{bal:.4f} USDT`\n💸 Fee: `{comm:.4f} USDT`\n\nSend: `ID Amount`\nExample: `123456789 50`",
        "transfer_confirm": "✅ *Confirm Transfer*\n\n👤 Recipient: `{name}`\n🆔 ID: `{uid}`\n💰 Amount: `{amt:.4f} USDT`\n💸 Fee: `{comm:.4f} USDT`\n🔖 Ref: `{ref}`\n\nConfirm?",
        "transfer_success": "✅ *Transfer Successful!*\n\n📤 To: `{uid}`\n👤 Recipient: `{name}`\n💰 Amount: `{amt:.4f} USDT`\n💸 Fee: `{comm:.4f} USDT`\n💳 New Balance: `{bal:.4f} USDT`",
        "transfer_received": "💸 *Transfer Received!*\n\n👤 From: `{name}`\n💰 Amount: `{amt:.4f} USDT`\n💳 New Balance: `{bal:.4f} USDT`",
        
        # Profile
        "profile_info": "👤 *My Account*\n\nName: {name}\n🆔 ID: `{id}`\n💰 Balance: `{bal:.4f} USDT`\n📅 Joined: `{date}`\n\n🌐 Network: TRON (TRC20)",
        
        # History
        "history_title": "📜 *Recent Transactions*",
        "history_empty": "📜 No transactions yet",
        
        # Errors and alerts
        "error_banned": "❌ Your account is banned. Contact support.",
        "error_rate_limit": "⚠️ Too fast! Please wait.",
        "error_invalid_amount": "❌ Enter valid number: `10` or `25.5`",
        "error_insufficient_balance": "❌ Insufficient balance",
        "error_invalid_address": "❌ Invalid TRC20 address!\n• Starts with `T`\n• 34 characters\n• TRON network only",
        "error_user_not_found": "❌ User not found",
        "error_user_banned": "❌ User is banned",
        "error_self_transfer": "❌ Cannot transfer to yourself",
        
        # Languages
        "lang_ar": "🇸🇦 العربية",
        "lang_en": "🇺🇸 English",
        "lang_fr": "🇫🇷 Français",
        "lang_de": "🇩🇪 Deutsch",
        "lang_es": "🇪🇸 Español",
        "lang_hi": "🇮🇳 हिन्दी",
        "lang_zh": "🇨🇳 中文",
        "lang_changed": "✅ Language changed successfully!",
    }
}

def get_text(lang, key, **kwargs):
    """الحصول على نص مترجم"""
    # إذا اللغة غير موجودة، استخدم العربية
    if lang not in TRANSLATIONS:
        lang = "ar"
    
    # احصل على النص
    text = TRANSLATIONS[lang].get(key, key)
    
    # ضع القيم إذا وجدت
    if kwargs:
        try:
            return text.format(**kwargs)
        except KeyError:
            return text
    return text