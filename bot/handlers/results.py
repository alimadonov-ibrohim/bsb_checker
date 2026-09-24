import html as html_mod
import json
from pathlib import Path
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import User, Test, Student, Result, AnswerKey
from bot.keyboards.main_kb import main_menu_kb, cancel_kb, results_list_kb
from services.excel_service import ExcelService
from services.checker_service import normalize_points

router = Router(name="results")


def format_num(v) -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return str(int(f)) if f == int(f) else f"{f:g}"


class ResultsFSM(StatesGroup):
    select_test = State()


@router.message(F.text == "📊 Natijalar")
async def show_results_start(message: Message, state: FSMContext, session: AsyncSession, user: User):
    await state.clear()
    result = await session.execute(
        select(Test)
        .where(Test.user_id == user.id)
        .order_by(Test.created_at.desc())
        .limit(10)
    )
    tests = result.scalars().all()
    if not tests:
        await message.answer("⚠️ Hali test yo‘q.", reply_markup=main_menu_kb())
        return

    if len(tests) == 1:
        await send_results_for_test(message, session, tests[0])
        return

    lines = ["📊 Qaysi test natijasini ko‘rasiz?\n"]
    for t in tests:
        lines.append(f"• ID <code>{t.id}</code> — {t.subject} | {t.test_name}")
    lines.append("\nTest ID yozing:")
    await state.set_state(ResultsFSM.select_test)
    await message.answer("\n".join(lines), parse_mode="HTML", reply_markup=cancel_kb())


@router.message(ResultsFSM.select_test)
async def select_test_results(message: Message, state: FSMContext, session: AsyncSession, user: User):
    text = (message.text or "").strip()
    if text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=main_menu_kb())
        return
    if not text.isdigit():
        await message.answer("⚠️ Test ID kiriting.")
        return
    test_id = int(text)
    result = await session.execute(
        select(Test).where(Test.id == test_id, Test.user_id == user.id)
    )
    test = result.scalar_one_or_none()
    if not test:
        await message.answer("⚠️ Test topilmadi.")
        return
    await state.clear()
    await send_results_for_test(message, session, test)


async def send_results_for_test(message: Message, session: AsyncSession, test: Test):
    students_result = await session.execute(
        select(Student)
        .where(Student.test_id == test.id)
        .order_by(Student.id)
    )
    students = students_result.scalars().all()

    if not students:
        await message.answer(
            f"⚠️ <b>{test.test_name}</b> uchun hali o‘quvchi natijasi yo‘q.",
            parse_mode="HTML",
            reply_markup=main_menu_kb(),
        )
        return

    lines = [f"📊 <b>NATIJALAR</b>\n📚 {test.subject} | {test.test_name} | {test.class_name}\n"]
    percentages = []
    points = normalize_points(test.points_json)
    if points:
        total_balls = round(sum(points.get(str(i), 1.0) for i in range(1, test.question_count + 1)), 2)
    else:
        total_balls = float(test.question_count)

    for idx, st in enumerate(students, 1):
        res_q = await session.execute(select(Result).where(Result.student_id == st.id))
        res = res_q.scalar_one_or_none()
        if res:
            lines.append(
                f"{idx}. {st.name} — <b>{format_num(res.score)}</b>/{format_num(total_balls)} — {res.percentage}%"
            )
            percentages.append(res.percentage)
        else:
            lines.append(f"{idx}. {st.name} — natija yo‘q")

    if percentages:
        avg = round(sum(percentages) / len(percentages), 1)
        lines.append(
            f"\n📈 O‘rtacha: {avg}%\n"
            f"🏆 Eng yuqori: {max(percentages)}%\n"
            f"📉 Eng past: {min(percentages)}%\n"
            f"👨‍🎓 O‘quvchilar: {len(students)}\n"
            f"🔢 Umumiy ball: {format_num(total_balls)}"
        )

    await message.answer(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=results_list_kb(test.id),
    )


@router.callback_query(F.data.startswith("detail:"))
async def show_students_detail(callback: CallbackQuery, session: AsyncSession, user: User):
    test_id = int(callback.data.split(":")[1])
    result = await session.execute(
        select(Test).where(Test.id == test_id, Test.user_id == user.id)
    )
    test = result.scalar_one_or_none()
    if not test:
        await callback.answer("Test topilmadi", show_alert=True)
        return

    students_result = await session.execute(
        select(Student).where(Student.test_id == test.id).order_by(Student.id)
    )
    students = students_result.scalars().all()
    if not students:
        await callback.answer("O‘quvchi yo‘q", show_alert=True)
        return

    buttons = []
    for st in students:
        buttons.append([
            InlineKeyboardButton(
                text=html_mod.escape(st.name or f"O‘quvchi #{st.id}"),
                callback_data=f"student:{test.id}:{st.id}",
            )
        ])
    buttons.append([InlineKeyboardButton(text="◀️ Orqaga", callback_data=f"results:{test.id}")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    text = (
        f"🔍 <b>Javoblar</b>\n📚 {test.subject} | {test.test_name}\n"
        f"O‘quvchini tanlang — har bir savol uchun to‘g‘ri/noto‘g‘ri va javob ko‘rsatiladi:"
    )
    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("student:"))
async def show_student_detail(callback: CallbackQuery, session: AsyncSession, user: User):
    parts = callback.data.split(":")
    test_id = int(parts[1])
    student_id = int(parts[2])

    test_result = await session.execute(
        select(Test).where(Test.id == test_id, Test.user_id == user.id)
    )
    test = test_result.scalar_one_or_none()
    if not test:
        await callback.answer("Test topilmadi", show_alert=True)
        return

    st_result = await session.execute(
        select(Student).where(Student.id == student_id, Student.test_id == test.id)
    )
    st = st_result.scalar_one_or_none()
    if not st:
        await callback.answer("O‘quvchi topilmadi", show_alert=True)
        return

    res_result = await session.execute(select(Result).where(Result.student_id == st.id))
    res = res_result.scalar_one_or_none()
    if not res or not res.details_json:
        await callback.answer("Natija yo‘q", show_alert=True)
        return

    details = json.loads(res.details_json)
    if not isinstance(details, dict):
        details = {}

    points = normalize_points(test.points_json)
    total_balls = round(
        sum(points.get(str(i), 1.0) for i in range(1, test.question_count + 1)), 2
    )

    lines = [
        f"👨‍🎓 <b>{html_mod.escape(st.name)}</b> — {html_mod.escape(st.class_name or test.class_name)}",
        f"📊 Ball: <b>{format_num(res.score)}</b>/{format_num(total_balls)} — {res.percentage}%\n",
    ]
    sorted_q = sorted(details.keys(), key=lambda x: int(x) if str(x).isdigit() else 0)
    for q in sorted_q:
        d = details[q]
        status = d.get("status")
        student_ans = d.get("student")
        correct_ans = d.get("correct")
        try:
            q_point = float(points.get(str(q), d.get("points", 1.0)))
        except (TypeError, ValueError):
            q_point = 1.0
        if q_point <= 0:
            q_point = 1.0
        if status == "correct":
            icon = "✅"
        elif status == "incorrect":
            icon = "❌"
        else:
            icon = "⚠️"
        s_ans = html_mod.escape(student_ans) if student_ans else "javobsiz"
        line = f"{q}. {icon} <b>{s_ans}</b>"
        if status != "correct":
            c_ans = html_mod.escape(correct_ans) if correct_ans else "—"
            line += f" — {icon} to‘g‘ri: <b>{c_ans}</b>"
        line += f" — {format_num(q_point)} bal"
        lines.append(line)

    if len(lines) == 2:
        lines.append("Savollar bo‘yicha ma’lumot yo‘q.")

    texts = []
    current = []
    for line in lines:
        if sum(len(x) + 1 for x in current) + len(line) > 3500 and current:
            texts.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        texts.append("\n".join(current))

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ O‘quvchilar", callback_data=f"detail:{test.id}")],
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data=f"results:{test.id}")],
        ]
    )
    await callback.message.answer(texts[0], parse_mode="HTML", reply_markup=kb)
    for extra in texts[1:]:
        await callback.message.answer(extra, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("results:"))
async def show_results_again(callback: CallbackQuery, session: AsyncSession, user: User):
    test_id = int(callback.data.split(":")[1])
    result = await session.execute(
        select(Test).where(Test.id == test_id, Test.user_id == user.id)
    )
    test = result.scalar_one_or_none()
    if not test:
        await callback.answer("Test topilmadi", show_alert=True)
        return
    await send_results_for_test(callback.message, session, test)
    await callback.answer()


@router.callback_query(F.data.startswith("excel:"))
async def download_excel(callback: CallbackQuery, session: AsyncSession, user: User, bot: Bot):
    test_id = int(callback.data.split(":")[1])
    result = await session.execute(
        select(Test).where(Test.id == test_id, Test.user_id == user.id)
    )
    test = result.scalar_one_or_none()
    if not test:
        await callback.answer("Test topilmadi", show_alert=True)
        return

    students_result = await session.execute(
        select(Student).where(Student.test_id == test.id).order_by(Student.id)
    )
    students = students_result.scalars().all()
    if not students:
        await callback.answer("Natija yo‘q", show_alert=True)
        return

    points = normalize_points(test.points_json)
    max_balls = round(
        sum(points.get(str(i), 1.0) for i in range(1, test.question_count + 1)), 2
    )

    students_data = []
    for st in students:
        res_q = await session.execute(select(Result).where(Result.student_id == st.id))
        res = res_q.scalar_one_or_none()
        details = {}
        if res and res.details_json:
            details = json.loads(res.details_json)
        students_data.append({
            "name": st.name,
            "class_name": st.class_name,
            "correct_count": res.correct_count if res else 0,
            "incorrect_count": res.incorrect_count if res else 0,
            "uncertain_count": res.uncertain_count if res else 0,
            "percentage": res.percentage if res else 0,
            "score": res.score if res else 0,
            "max_score": max_balls,
            "total_questions": test.question_count,
            "details": details,
        })

    excel = ExcelService()
    path = excel.generate_results_excel(
        test_info={
            "id": test.id,
            "subject": test.subject,
            "class_name": test.class_name,
            "test_name": test.test_name,
            "test_type": test.test_type,
            "question_count": test.question_count,
        },
        students_data=students_data,
        filename=f"natija_{test.id}_{test.test_name}.xlsx".replace(" ", "_"),
    )

    await callback.message.answer_document(
        FSInputFile(path),
        caption=f"📥 {test.test_name} — natijalar",
    )
    await callback.answer()
    # Cleanup after send optional
    try:
        Path(path).unlink(missing_ok=True)
    except Exception:
        pass


@router.callback_query(F.data.startswith("stats:"))
async def show_stats(callback: CallbackQuery, session: AsyncSession, user: User):
    test_id = int(callback.data.split(":")[1])
    result = await session.execute(
        select(Test).where(Test.id == test_id, Test.user_id == user.id)
    )
    test = result.scalar_one_or_none()
    if not test:
        await callback.answer("Test topilmadi", show_alert=True)
        return

    students_result = await session.execute(
        select(Student).where(Student.test_id == test.id)
    )
    students = students_result.scalars().all()
    percentages = []
    for st in students:
        res_q = await session.execute(select(Result).where(Result.student_id == st.id))
        res = res_q.scalar_one_or_none()
        if res:
            percentages.append(res.percentage)

    if not percentages:
        await callback.answer("Statistika yo‘q", show_alert=True)
        return

    text = (
        f"📈 <b>STATISTIKA</b>\n\n"
        f"👨‍🎓 O‘quvchilar: {len(percentages)}\n"
        f"📈 O‘rtacha natija: {round(sum(percentages)/len(percentages), 1)}%\n"
        f"🏆 Eng yuqori: {max(percentages)}%\n"
        f"📉 Eng past: {min(percentages)}%"
    )
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


@router.message(F.text == "📥 Excel")
async def excel_shortcut(message: Message, state: FSMContext, session: AsyncSession, user: User):
    # Reuse results flow
    await show_results_start(message, state, session, user)


@router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Asosiy menyu:", reply_markup=main_menu_kb())
    await callback.answer()
