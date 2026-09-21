from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Statistika", callback_data="admin:stats"),
                InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="admin:users"),
            ],
            [
                InlineKeyboardButton(text="🎁 Premium berish", callback_data="admin:premium"),
                InlineKeyboardButton(text="🚫 Bloklash", callback_data="admin:ban"),
            ],
            [InlineKeyboardButton(text="❌ Yopish", callback_data="admin:close")],
        ]
    )