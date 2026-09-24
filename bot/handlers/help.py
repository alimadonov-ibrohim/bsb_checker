from aiogram import Router, F
from aiogram.types import Message
from database.models import User

router = Router(name="help")

HELP_TEXT = """
❓ <b>YORDAM</b>

<b>1. Yangi test yaratish</b>
➕ Yangi test → Fan, sinf, test nomi, savollar soni, BSB/CHSB

<b>2. Javoblar kaliti</b>
📋 Javoblar kaliti → TXT, PDF yoki rasm yuboring
Format: 1-A, 2-C, 3-B ...

<b>3. Ballar</b>
⭐ Ballar → har bir savolga necha ball berilishini kiritish/ozgartirish.
Format: faqat son (2), ro‘yxat (2,2,1,1) yoki diapazon (1-10:2, 11:1).

<b>4. O‘quvchilar javoblari</b>
📄 O‘quvchilar javoblari → PDF, rasm (JPG/PNG) yoki Excel (.xlsx/.csv) yuboring
Bot faqat belgilangan javoblarni o‘qiydi va kalit bilan solishtiradi.

<b>5. Natijalar</b>
📊 Natijalar → barcha o‘quvchilar natijasi
🔍 Javoblar → har bir savol uchun to‘g‘ri/noto‘g‘ri va to‘g‘ri javob
📥 Excel → yuklab olish

<b>6. Premium</b>
👑 Premium → kunlik PDF limitini oshirish

⚠️ <b>Muhim:</b>
Bot testni o‘zi yechmaydi.
Faqat rasm/PDF dagi belgilarni o‘qiydi va siz bergan kalit bilan solishtiradi.
"""


@router.message(F.text == "❓ Yordam")
async def help_handler(message: Message, user: User):
    await message.answer(HELP_TEXT, parse_mode="HTML")
