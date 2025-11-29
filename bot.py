import asyncio
import os
import re 
from pyrogram import Client, filters
from pyrogram.errors import UserNotParticipant, FloodWait
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# =========================================================
## 🔑 إعداد البيانات (Configuration) 🔑
# =========================================================

API_ID = os.environ.get("32315282")       
API_HASH = os.environ.get("acdfe0167bd1ca0a8460f08829bc636d")  
BOT_TOKEN = os.environ.get("8552426997:AAFrhyosIgp8uekpZnjBCzd3Z9KmIMQA4I0")  

# متغيرات الجلسة والذاكرة المؤقتة
DOWNLOAD_DIR = "Temp_Cache_Cloud" 
# حفظ حالة المستخدم أثناء التسجيل {user_id: {"step": "phone", "phone_number": None, "sent_code": None}}
USER_STATES = {} 

# =========================================================

# تهيئة العميل كـ "بوت"
bot_app = Client(
    "BotSession",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ملاحظة: العميلuser_client سيتم إنشاؤه ديناميكياً لكل مستخدم عند التسجيل!
# لغرض التشغيل السحابي، يجب أن تكون جلسات المستخدمين موجودة في مجلد ما (مثل sessions/)

# =========================================================
## 🤖 أوامر البوت التفاعلية (Bot Commands) 🤖
# =========================================================

@bot_app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 تسجيل دخول (Login)", callback_data="login_step_1")],
        [InlineKeyboardButton("🚀 بدء عملية السحب", callback_data="start_scrape")]
    ])
    
    await message.reply_text(
        "مرحباً! اضغط على **تسجيل دخول** لبدء العملية، ثم ابدأ السحب.",
        reply_markup=keyboard
    )

@bot_app.on_callback_query(filters.regex("login_step_1"))
async def login_callback_handler(client, callback_query):
    user_id = callback_query.from_user.id
    
    # تهيئة الحالة
    USER_STATES[user_id] = {"step": "phone", "phone_number": None, "sent_code": None}
    
    await callback_query.edit_message_text(
        "📝 يرجى إرسال رقم هاتفك كاملاً مع رمز الدولة (مثال: +96277xxxxxxx).\n\n"
        "لن يتم تخزين رقمك إلا مؤقتاً لإتمام تسجيل الدخول.",
    )

@bot_app.on_message(filters.private & (filters.regex(r"^\+\d+") | filters.regex(r"^\d+")))
async def handle_login_input(client, message):
    user_id = message.from_user.id
    current_state = USER_STATES.get(user_id)

    if not current_state:
        return # ليس في مرحلة تسجيل الدخول

    if current_state["step"] == "phone":
        phone_number = message.text.strip()
        
        # 1. إنشاء عميل مؤقت للمستخدم
        temp_client = Client(
            f"sessions/{user_id}", # اسم الجلسة الخاصة بالمستخدم
            api_id=API_ID,
            api_hash=API_HASH
        )
        
        try:
            # 2. إرسال رمز التحقق
            await temp_client.connect()
            sent_code = await temp_client.send_code(phone_number)
            await temp_client.disconnect() # نفصل مؤقتاً

            # حفظ الحالة للانتقال إلى الخطوة التالية
            current_state["phone_number"] = phone_number
            current_state["sent_code"] = sent_code
            current_state["step"] = "code"
            
            await message.reply_text(
                "✅ تم إرسال رمز التحقق إلى تيليجرام الخاص بك. "
                "يرجى إرسال الرمز المكون من 5 أرقام الآن."
            )
            
        except Exception as e:
            await message.reply_text(f"❌ حدث خطأ عند إرسال الرمز: {e}")
            del USER_STATES[user_id]
            return

    elif current_state["step"] == "code":
        verification_code = message.text.strip()
        
        temp_client = Client(
            f"sessions/{user_id}",
            api_id=API_ID,
            api_hash=API_HASH
        )
        
        try:
            # 3. محاولة تسجيل الدخول باستخدام الرمز
            await temp_client.connect()
            await temp_client.sign_in(
                current_state["phone_number"],
                current_state["sent_code"].phone_code_hash,
                verification_code
            )
            
            # 4. تحقق من كلمة المرور (إذا كان التحقق بخطوتين مفعلاً)
            await temp_client.start() # محاولة التشغيل للتأكد
            await temp_client.stop()
            
            await message.reply_text("🎉 تم تسجيل دخول حسابك بنجاح! يمكنك الآن بدء السحب.")
            del USER_STATES[user_id] # إنهاء حالة التسجيل

        except FloodWait as e:
            await message.reply_text(f"⏳ يجب الانتظار {e.value} ثانية قبل إعادة المحاولة.")
        except Exception as e:
            if "Password" in str(e):
                current_state["step"] = "password"
                await message.reply_text("🔒 يرجى إرسال كلمة مرور التحقق بخطوتين (2FA) الآن.")
            else:
                await message.reply_text(f"❌ فشل تسجيل الدخول: {e}")
                del USER_STATES[user_id]

    elif current_state["step"] == "password":
        password = message.text.strip()
        
        temp_client = Client(
            f"sessions/{user_id}",
            api_id=API_ID,
            api_hash=API_HASH
        )
        
        try:
            # 5. تسجيل الدخول باستخدام كلمة المرور
            await temp_client.connect()
            await temp_client.start() # ستقوم هذه الخطوة بطلب كلمة المرور داخلياً
            await temp_client.check_password(password)
            await temp_client.stop()

            await message.reply_text("🎉 تم تسجيل دخول حسابك بنجاح! يمكنك الآن بدء السحب.")
            del USER_STATES[user_id]

        except Exception as e:
            await message.reply_text(f"❌ فشل تسجيل الدخول بكلمة المرور: {e}")
            del USER_STATES[user_id]


# (يجب إضافة بقية أوامر البوت مثل: logout و start_scrape و handle_scrape_request)
# (يجب استخدام client_user = Client(f"sessions/{message.from_user.id}", ...) في دالة السحب)


# =========================================================
## 🚀 دالة التشغيل الرئيسية (Main Function) 🚀
# =========================================================

async def main():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    os.makedirs("sessions", exist_ok=True) # مجلد لحفظ جلسات المستخدمين

    await bot_app.start()
    print("🤖 البوت يعمل وينتظر الأوامر...")
    
    from pyrogram import idle
    await idle()
    
    await bot_app.stop()

if __name__ == "__main__":
    asyncio.run(main())