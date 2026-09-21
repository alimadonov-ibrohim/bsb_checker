import os
import json
import aiofiles
from pathlib import Path
from aiogram import Router, F, Bot
from aiogram.types import Message, ContentType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import User, Test, AnswerKey
from bot.keyboards.main_kb import main_menu_kb, cancel_kb
from services.gemini_service import GeminiService

router = Router(name="answer_key")

ALLOWED_EXT = {".txt", ".pdf", ".jpg", ".jpeg", ".png"}
TEMP = Path(os.getenv("TEMP_DIR", "temp"))


class AnswerKeyFSM(StatesGroup):
    waiting_file = State()
    select_test = State()


@router.message(F.text == "📋 Javoblar kaliti")
async def start_answer_key(message: Message, state: FSMContext, session: AsyncSession, user: User):
    # Get user's recent tests without answer key
    result = await session.execute(
        select(Test)
        .where(Test.user_id == user.id)
        .order_by(Test.created_at.desc())
        .limit(10)
    )
    tests = result.scalars().all()

    if not tests:
        await message.answer(
            "⚠️ Avval <b>➕ Yangi test</b> yarating.",
            parse_mode="HTML",
            reply_markup=main_menu_kb(),
        )
        return

    # If only one test — use it
    if len(tests) == 1:
        await state.update_data(test_id=tests[0].id)
        await state.set_state(AnswerKeyFSM.waiting_file)
        await message.answer(
            f"📋 <b>{tests[0].test_name}</b> uchun javoblar kalitini yuboring.\n\n"
            f"Qabul qilinadi: TXT, PDF, JPG, PNG\n"
            f"Format misoli:\n<code>1-A\n2-C\n3-B</code>",
            parse_mode="HTML",
            reply_markup=cancel_kb(),
        )
        return

    # Multiple tests — ask to choose
    lines = ["📋 Qaysi test uchun kalit yuborasiz?\n"]
    for t in tests:
        lines.append(f"• ID <code>{t.id}</code> — {t.subject} | {t.test_name} ({t.question_count} savol)")
    lines.append("\nTest ID raqamini yozing:")
    await state.set_state(AnswerKeyFSM.select_test)
    await message.answer("\n".join(lines), parse_mode="HTML", reply_markup=cancel_kb())


@router.message(AnswerKeyFSM.select_test)
async def select_test_for_key(message: Message, state: FSMContext, session: AsyncSession, user: User):
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("⚠️ Test ID raqamini kiriting.")
        return
    test_id = int(text)
    result = await session.execute(
        select(Test).where(Test.id == test_id, Test.user_id == user.id)
    )
    test = result.scalar_one_or_none()
    if not test:
        await message.answer("⚠️ Test topilmadi yoki sizniki emas.")
        return
    await state.update_data(test_id=test.id)
    await state.set_state(AnswerKeyFSM.waiting_file)
    await message.answer(
        f"📋 <b>{test.test_name}</b> uchun javoblar kalitini yuboring.\n"
        f"TXT / PDF / rasm yuboring.",
        parse_mode="HTML",
    )


@router.message(AnswerKeyFSM.waiting_file, F.content_type.in_({
    ContentType.DOCUMENT, ContentType.PHOTO, ContentType.TEXT
}))
async def receive_answer_key(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    bot: Bot,
):
    data = await state.get_data()
    test_id = data.get("test_id")
    if not test_id:
        await state.clear()
        await message.answer("⚠️ Test tanlanmagan. Qaytadan boshlang.", reply_markup=main_menu_kb())
        return

    result = await session.execute(
        select(Test).where(Test.id == test_id, Test.user_id == user.id)
    )
    test = result.scalar_one_or_none()
    if not test:
        await state.clear()
        await message.answer("⚠️ Test topilmadi.", reply_markup=main_menu_kb())
        return

    file_paths = []
    TEMP.mkdir(parents=True, exist_ok=True)

    try:
        if message.document:
            doc = message.document
            ext = Path(doc.file_name or "").suffix.lower()
            if ext not in ALLOWED_EXT:
                await message.answer("⚠️ Faqat TXT, PDF, JPG, PNG qabul qilinadi.")
                return
            dest = TEMP / f"akey_{user.telegram_id}_{doc.file_id}{ext}"
            await bot.download(doc, destination=dest)
            file_paths.append(str(dest))
        elif message.photo:
            photo = message.photo[-1]
            dest = TEMP / f"akey_{user.telegram_id}_{photo.file_id}.jpg"
            await bot.download(photo, destination=dest)
            file_paths.append(str(dest))
        elif message.text:
            # Plain text answer key
            text_content = message.text.strip()
            dest = TEMP / f"akey_{user.telegram_id}_text.txt"
            async with aiofiles.open(dest, "w", encoding="utf-8") as f:
                await f.write(text_content)
            file_paths.append(str(dest))
        else:
            await message.answer("⚠️ Fayl yoki matn yuboring.")
            return

        await message.answer("🔄 Javoblar kaliti o‘qilmoqda...")

        gemini = GeminiService()
        if file_paths[0].endswith(".txt") and len(file_paths) == 1:
            async with aiofiles.open(file_paths[0], "r", encoding="utf-8") as f:
                content = await f.read()
            answers = await gemini.extract_from_text(content)
        else:
            answers = await gemini.extract_answer_key(file_paths)

        if not answers:
            await message.answer(
                "⚠️ Javoblar kalitidan hech narsa o‘qib bo‘lmadi.\n"
                "Formatni tekshiring: 1-A, 2-C, 3-B ...",
                reply_markup=main_menu_kb(),
            )
            await state.clear()
            return

        # Save / update AnswerKey
        existing = await session.execute(
            select(AnswerKey).where(AnswerKey.test_id == test.id)
        )
        ak = existing.scalar_one_or_none()
        answers_json = json.dumps(answers, ensure_ascii=False)

        if ak:
            ak.answers_json = answers_json
        else:
            ak = AnswerKey(test_id=test.id, answers_json=answers_json)
            session.add(ak)

        await session.flush()
        await state.clear()

        count = len([v for v in answers.values() if v is not None])
        await message.answer(
            f"✅ <b>Javoblar kaliti saqlandi.</b>\n"
            f"Jami o‘qilgan savollar: <b>{count}</b>\n"
            f"Test: {test.test_name} ({test.question_count} savol)\n\n"
            f"Endi <b>📄 O‘quvchilar javoblari</b> ni yuborishingiz mumkin.",
            parse_mode="HTML",
            reply_markup=main_menu_kb(),
        )
    except Exception as e:
        await message.answer(
            f"❌ Xatolik: {str(e)[:200]}\nQaytadan urinib ko‘ring.",
            reply_markup=main_menu_kb(),
        )
        await state.clear()
    finally:
        for fp in file_paths:
            try:
                Path(fp).unlink(missing_ok=True)
            except Exception:
                pass
