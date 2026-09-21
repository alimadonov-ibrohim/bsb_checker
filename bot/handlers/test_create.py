from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User, Test
from bot.keyboards.main_kb import main_menu_kb, test_type_kb, cancel_kb

router = Router(name="test_create")


class CreateTestFSM(StatesGroup):
    subject = State()
    class_name = State()
    test_name = State()
    question_count = State()
    test_type = State()


@router.message(F.text == "➕ Yangi test")
async def start_create_test(message: Message, state: FSMContext, user: User):
    await state.clear()
    await state.set_state(CreateTestFSM.subject)
    await message.answer(
        "📚 Fan nomini yozing:\n\nMasalan: <b>Matematika</b>",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )


@router.message(F.text == "❌ Bekor qilish")
async def cancel_any(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Bekor qilindi.", reply_markup=main_menu_kb())


@router.message(CreateTestFSM.subject)
async def process_subject(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text or len(text) > 200:
        await message.answer("⚠️ Fan nomini to‘g‘ri kiriting (1–200 belgi).")
        return
    await state.update_data(subject=text)
    await state.set_state(CreateTestFSM.class_name)
    await message.answer("🏫 Sinfni yozing:\n\nMasalan: <b>9-A</b>", parse_mode="HTML")


@router.message(CreateTestFSM.class_name)
async def process_class(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text or len(text) > 50:
        await message.answer("⚠️ Sinfni to‘g‘ri kiriting.")
        return
    await state.update_data(class_name=text)
    await state.set_state(CreateTestFSM.test_name)
    await message.answer("📝 Test nomini yozing:\n\nMasalan: <b>1-BSB</b>", parse_mode="HTML")


@router.message(CreateTestFSM.test_name)
async def process_test_name(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text or len(text) > 200:
        await message.answer("⚠️ Test nomini to‘g‘ri kiriting.")
        return
    await state.update_data(test_name=text)
    await state.set_state(CreateTestFSM.question_count)
    await message.answer("🔢 Savollar sonini yozing:\n\nMasalan: <b>30</b>", parse_mode="HTML")


@router.message(CreateTestFSM.question_count)
async def process_question_count(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    try:
        count = int(text)
        if count < 1 or count > 200:
            raise ValueError()
    except ValueError:
        await message.answer("⚠️ Savollar soni 1 dan 200 gacha butun son bo‘lsin.")
        return
    await state.update_data(question_count=count)
    await state.set_state(CreateTestFSM.test_type)
    await message.answer(
        "📋 Test turini tanlang:",
        reply_markup=test_type_kb(),
    )


@router.callback_query(F.data.startswith("test_type:"), CreateTestFSM.test_type)
async def process_test_type(callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    test_type = callback.data.split(":")[1]
    data = await state.get_data()
    await state.clear()

    test = Test(
        user_id=user.id,
        subject=data["subject"],
        class_name=data["class_name"],
        test_name=data["test_name"],
        test_type=test_type,
        question_count=data["question_count"],
    )
    session.add(test)
    await session.flush()

    # Store current test id in user context via simple message
    await callback.message.edit_text(
        f"✅ <b>Test yaratildi!</b>\n\n"
        f"📚 Fan: {test.subject}\n"
        f"🏫 Sinf: {test.class_name}\n"
        f"📝 Nomi: {test.test_name}\n"
        f"🔢 Savollar: {test.question_count}\n"
        f"📋 Turi: {test.test_type}\n"
        f"🆔 Test ID: <code>{test.id}</code>\n\n"
        f"Endi <b>📋 Javoblar kaliti</b> ni yuboring.",
        parse_mode="HTML",
    )
    await callback.message.answer("Asosiy menyu:", reply_markup=main_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "cancel")
async def cancel_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Bekor qilindi.")
    await callback.message.answer("Asosiy menyu:", reply_markup=main_menu_kb())
    await callback.answer()
