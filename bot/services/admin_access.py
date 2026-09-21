import os

ADMIN_TELEGRAM_IDS = sorted(
    {
        int(x.strip())
        for x in os.getenv("ADMIN_TELEGRAM_IDS", "").split(",")
        if x.strip().lstrip("+-").isdigit()
    }
)


def is_bot_admin(telegram_id: int) -> bool:
    return telegram_id in ADMIN_TELEGRAM_IDS


def admin_ids() -> list[int]:
    return ADMIN_TELEGRAM_IDS