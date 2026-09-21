from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from bot.keyboards.main_kb import main_menu_kb
from database.models import User

router = Router(name="start")

WELCOME = (
    "Assalomu alaykum! 👋\n\n"
    "Men BSB/CHSB testlarini avtomatik tekshiruvchi botman.\n\n"
    "📋 Javoblar kalitini yuboring\n"
    "📄 O‘quvchilar javoblarini yuboring\n"
    "🤖 Men javoblarni solishtiraman\n"
    "📊 Natijalarni hisoblayman\n"
    "📥 Excel fayl tayyorlayman."
)


@router.message(CommandStart())
async def cmd_start(message: Message, user: User):
    await message.answer(WELCOME, reply_markup=main_menu_kb())
