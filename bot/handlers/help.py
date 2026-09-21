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

<b>3. O‘quvchilar javoblari</b>
📄 O‘quvchilar javoblari → PDF yoki rasmlar yuboring
Bot Gemini orqali faqat belgilangan javoblarni o‘qiydi.

<b>4. Natijalar</b>
📊 Natijalar → barcha o‘quvchilar natijasi
📥 Excel → yuklab olish

<b>5. Premium</b>
👑 Premium → kunlik PDF limitini oshirish

⚠️ <b>Muhim:</b>
Bot testni o‘zi yechmaydi.
Faqat rasm/PDF dagi belgilarni o‘qiydi va siz bergan kalit bilan solishtiradi.
"""


@router.message(F.text == "❓ Yordam")
async def help_handler(message: Message, user: User):
    await message.answer(HELP_TEXT, parse_mode="HTML")
