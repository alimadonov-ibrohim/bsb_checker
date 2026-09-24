"""
Ball (points) handler — har bir savolga necha ball berilishini kiritish/ozgartirish.
Ball saqlangach, bor natijalarning balli qayta hisoblanadi.
"""
import json
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import User, Test, Student, Result
from bot.keyboards.main_kb import main_menu_kb, cancel_kb
from services.checker_service import parse_points_input, normalize_points, format_points_line

router = Router(name="points")


class PointsFSM(StatesGroup):
    select_test = State()
    waiting_points = State()


def quick_points_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1 bal", callback_data="qpoints:1"),
                InlineKeyboardButton(text="1.5 bal", callback_data="qpoints:1.5"),
                InlineKeyboardButton(text="2 bal", callback_data="qpoints:2"),
            ],
            [
                InlineKeyboardButton(text="3 bal", callback_data="qpoints:3"),
                InlineKeyboardButton(text="5 bal", callback_data="qpoints:5"),
                InlineKeyboardButton(text="10 bal", callback_data="qpoints:10"),
            ],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="qpoints:cancel")],
        ]
    )


def points_help_text(question_count: int) -> str:
    return (
        f"⭐ Har bir savolga necha ball beriladi?\n"
        f"Savollar soni: <b>{question_count}</b>\n\n"
        f"<b>Variantlar:</b>\n"
        f"• Barchasiga bir xil — <code>2</code>\n"
        f"• Ro‘yxat — <code>2, 2, 1, 1, 3, ...</code> (vergul bilan, soni savollarga teng)\n"
        f"• Diapazon/baholash — <code>1:2, 11-20:1, 21:3</code>\n"
        f"• Ko‘rsatilmagan savollar <b>1 bal</b> bo‘ladi\n\n"
        f"Yuklab tugmalardan ham tanlashingiz mumkin:"
    )


async def ask_points(message: Message, state: FSMContext, test: Test):
    await state.update_data(test_id=test.id)
    pts = normalize_points(test.points_json)
    lines = [f"⭐ <b>{test.test_name}</b> uchun joriy ballar:\n"]
    if pts:
        lines.append(format_points_line(pts, test.question_count))
    else:
        lines.append("Hali ball belgilanmagan (barcha savollarda 1 bal).")
    lines.append("\n" + points_help_text(test.question_count))
    await state.set_state(PointsFSM.waiting_points)
    await message.answer(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=quick_points_kb(),
    )


@router.message(F.text == "⭐ Ballar")
async def start_points(message: Message, state: FSMContext, session: AsyncSession, user: User):
    await state.clear()
    result = await session.execute(
        select(Test)
        .where(Test.user_id == user.id)
        .order_by(Test.created_at.desc())
        .limit(10)
    )
    tests = result.scalars().all()
    if not tests:
        await message.answer("⚠️ Avval <b>➕ Yangi test</b> yarating.", parse_mode="HTML", reply_markup=main_menu_kb())
        return

    if len(tests) == 1:
        await ask_points(message, state, tests[0])
        return

    lines = ["⭐ Qaysi testga ball belgilaysiz?\n"]
    for t in tests:
        pts = normalize_points(t.points_json)
        line = f"• ID <code>{t.id}</code> — {t.subject} | {t.test_name}"
        if pts:
            line += f" — «{t.question_count} savol»"
        lines.append(line)
    lines.append("\nTest ID raqamini yozing:")
    await state.set_state(PointsFSM.select_test)
    await message.answer("\n".join(lines), parse_mode="HTML", reply_markup=cancel_kb())


@router.message(PointsFSM.select_test)
async def select_test_for_points(message: Message, state: FSMContext, session: AsyncSession, user: User):
    text = (message.text or "").strip()
    if text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=main_menu_kb())
        return
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
    await ask_points(message, state, test)


@router.message(PointsFSM.waiting_points)
async def receive_points(message: Message, state: FSMContext, session: AsyncSession, user: User):
    text = (message.text or "").strip()
    if text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=main_menu_kb())
        return

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

    try:
        points = parse_points_input(text, test.question_count)
    except ValueError as e:
        await message.answer(str(e))
        return

    test.points_json = json.dumps(points, ensure_ascii=False)
    await session.flush()

    # Recompute all existing scores with the new points
    recomputed = await _recompute_scores(session, test.id, points)

    await state.clear()
    await message.answer(
        f"✅ <b>Ballar saqlandi!</b>\n\n"
        f"📚 Test: {test.test_name}\n"
        f"{format_points_line(points, test.question_count)}\n"
        f"🔢 Umumiy ball: <b>{round(sum(points.values()), 2)}</b>\n"
        f"{f'📝 Natijalar yangilandi (o‘quvchilar: {recomputed})' if recomputed else '📝 O‘quvchi natijalari hali yo‘q — tekshirganda yangi ball bo‘yicha hisoblanadi.'}",
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
    )


@router.callback_query(F.data.startswith("points:"))
async def points_from_results(callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    test_id = int(callback.data.split(":")[1])
    result = await session.execute(
        select(Test).where(Test.id == test_id, Test.user_id == user.id)
    )
    test = result.scalar_one_or_none()
    if not test:
        await callback.answer("Test topilmadi", show_alert=True)
        return
    await state.clear()
    await ask_points(callback.message, state, test)
    await callback.answer()


@router.callback_query(F.data.startswith("qpoints:"))
async def quick_points(callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    value = callback.data.split(":", 1)[1]
    if value == "cancel":
        await state.clear()
        await callback.message.edit_text("❌ Bekor qilindi.")
        await callback.message.answer("Asosiy menyu:", reply_markup=main_menu_kb())
        await callback.answer()
        return

    data = await state.get_data()
    test_id = data.get("test_id")
    if not test_id:
        await state.clear()
        await callback.message.edit_text("⚠️ Test tanlanmagan.")
        await callback.answer()
        return

    result = await session.execute(
        select(Test).where(Test.id == test_id, Test.user_id == user.id)
    )
    test = result.scalar_one_or_none()
    if not test:
        await state.clear()
        await callback.message.edit_text("⚠️ Test topilmadi.")
        await callback.answer()
        return

    points = {str(i): round(float(value), 2) for i in range(1, test.question_count + 1)}
    test.points_json = json.dumps(points, ensure_ascii=False)
    await session.flush()

    recomputed = await _recompute_scores(session, test.id, points)
    await state.clear()

    await callback.message.edit_text(
        f"✅ <b>Ballar saqlandi!</b>\n\n"
        f"📚 Test: {test.test_name}\n"
        f"Barcha savollar: <b>{round(float(value), 2)} bal</b>\n"
        f"🔢 Umumiy ball: <b>{round(sum(points.values()), 2)}</b>\n"
        f"{f'📝 Natijalar yangilandi (o‘quvchilar: {recomputed})' if recomputed else '📝 O‘quvchi natijalari hali yo‘q.'}",
        parse_mode="HTML",
    )
    await callback.message.answer("Asosiy menyu:", reply_markup=main_menu_kb())
    await callback.answer()


async def _recompute_scores(session: AsyncSession, test_id: int, points: dict) -> int:
    """Yangi ballar bo‘yicha har bir o‘quvchining Result.score ini qayta hisoblaydi."""
    students_result = await session.execute(
        select(Student).where(Student.test_id == test_id)
    )
    students = students_result.scalars().all()
    updated = 0
    for st in students:
        r = await session.execute(select(Result).where(Result.student_id == st.id))
        res = r.scalar_one_or_none()
        if not res or not res.details_json:
            continue
        try:
            details = json.loads(res.details_json)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(details, dict):
            continue
        earned = 0.0
        for q, d in details.items():
            p = points.get(str(q))
            if p is None:
                try:
                    p = float(d.get("points", 1.0))
                except (TypeError, ValueError):
                    p = 1.0
            if not isinstance(p, (int, float)) or p <= 0:
                p = 1.0
            if d.get("status") == "correct":
                earned += p
        res.score = round(earned, 2)
        updated += 1
    if updated:
        await session.flush()
    return updated