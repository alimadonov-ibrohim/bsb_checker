from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Yangi test"), KeyboardButton(text="📋 Javoblar kaliti")],
            [KeyboardButton(text="📄 O‘quvchilar javoblari"), KeyboardButton(text="📊 Natijalar")],
            [KeyboardButton(text="📥 Excel"), KeyboardButton(text="👑 Premium")],
            [KeyboardButton(text="👤 Profil"), KeyboardButton(text="❓ Yordam")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Menyudan tanlang...",
    )


def test_type_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="BSB", callback_data="test_type:BSB"),
                InlineKeyboardButton(text="CHSB", callback_data="test_type:CHSB"),
            ],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")],
        ]
    )


def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True,
    )


def premium_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Premium sotib olish", callback_data="buy_premium")],
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="back_main")],
        ]
    )


def results_list_kb(test_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📥 Excel yuklash", callback_data=f"excel:{test_id}"),
                InlineKeyboardButton(text="📈 Statistika", callback_data=f"stats:{test_id}"),
            ],
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="back_main")],
        ]
    )
