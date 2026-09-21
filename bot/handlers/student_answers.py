import os
import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timezone
from aiogram import Router, F, Bot
from aiogram.types import Message, ContentType, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import (
    User, Test, AnswerKey, Student, StudentAnswer, Result, ProcessingJob
)
from database.models.setting import Setting
from bot.keyboards.main_kb import main_menu_kb, cancel_kb
from services.gemini_service import GeminiService
from services.pdf_service import PDFService
from services.checker_service import CheckerService
from services.paths import temp_dir

router = Router(name="student_answers")

logger = logging.getLogger(__name__)

TEMP = temp_dir()
MAX_FILE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
STUDENT_BATCH_SIZE = int(os.getenv("STUDENT_BATCH_SIZE", "4"))
STUDENT_CONCURRENCY = int(os.getenv("STUDENT_CONCURRENCY", "2"))


class StudentAnswersFSM(StatesGroup):
    select_test = State()
    waiting_file = State()


async def get_setting(session: AsyncSession, key: str, default: str) -> str:
    r = await session.execute(select(Setting).where(Setting.key == key))
    s = r.scalar_one_or_none()
    return s.value if s else default


@router.message(F.text == "📄 O‘quvchilar javoblari")
async def start_student_answers(message: Message, state: FSMContext, session: AsyncSession, user: User):
    result = await session.execute(
        select(Test)
        .where(Test.user_id == user.id)
        .order_by(Test.created_at.desc())
        .limit(10)
    )
    tests = result.scalars().all()
    if not tests:
        await message.answer("⚠️ Avval test yarating va javoblar kalitini yuklang.", reply_markup=main_menu_kb())
        return

    # Check answer key exists for at least one
    tests_with_key = []
    for t in tests:
        ak = await session.execute(select(AnswerKey).where(AnswerKey.test_id == t.id))
        if ak.scalar_one_or_none():
            tests_with_key.append(t)

    if not tests_with_key:
        await message.answer(
            "⚠️ Avval <b>📋 Javoblar kaliti</b> ni yuklang.",
            parse_mode="HTML",
            reply_markup=main_menu_kb(),
        )
        return

    if len(tests_with_key) == 1:
        await state.update_data(test_id=tests_with_key[0].id)
        await state.set_state(StudentAnswersFSM.waiting_file)
        await message.answer(
            f"📄 <b>{tests_with_key[0].test_name}</b> uchun o‘quvchilar javoblarini yuboring.\n\n"
            f"Qabul qilinadi: PDF yoki rasmlar (JPG/PNG)\n"
            f"Bir nechta sahifa bo‘lishi mumkin.",
            parse_mode="HTML",
            reply_markup=cancel_kb(),
        )
        return

    lines = ["📄 Qaysi test uchun o‘quvchi javoblarini yuborasiz?\n"]
    for t in tests_with_key:
        lines.append(f"• ID <code>{t.id}</code> — {t.subject} | {t.test_name}")
    lines.append("\nTest ID raqamini yozing:")
    await state.set_state(StudentAnswersFSM.select_test)
    await message.answer("\n".join(lines), parse_mode="HTML", reply_markup=cancel_kb())


@router.message(StudentAnswersFSM.select_test)
async def select_test_for_students(message: Message, state: FSMContext, session: AsyncSession, user: User):
    text = (message.text or "").strip()
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
    ak = await session.execute(select(AnswerKey).where(AnswerKey.test_id == test.id))
    if not ak.scalar_one_or_none():
        await message.answer("⚠️ Bu testda javoblar kaliti yo‘q.")
        return
    await state.update_data(test_id=test.id)
    await state.set_state(StudentAnswersFSM.waiting_file)
    await message.answer(
        f"📄 <b>{test.test_name}</b> uchun PDF yoki rasmlarni yuboring.",
        parse_mode="HTML",
    )


@router.message(StudentAnswersFSM.waiting_file, F.content_type.in_({
    ContentType.DOCUMENT, ContentType.PHOTO
}))
async def receive_student_files(
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
        await message.answer("⚠️ Test tanlanmagan.", reply_markup=main_menu_kb())
        return

    # Daily limit check
    free_limit = int(await get_setting(session, "free_daily_pdf_limit", os.getenv("FREE_DAILY_PDF_LIMIT", "3")))
    prem_limit = int(await get_setting(session, "premium_daily_pdf_limit", os.getenv("PREMIUM_DAILY_PDF_LIMIT", "6")))
    user.reset_daily_limit_if_needed()

    if not user.can_upload_pdf(free_limit, prem_limit):
        limit = user.get_daily_limit(free_limit, prem_limit)
        await message.answer(
            f"⚠️ Bugungi limitingiz tugadi ({limit} PDF/kun).\n"
            f"👑 Premium bilan kuniga {prem_limit} ta PDF yuborishingiz mumkin.",
            reply_markup=main_menu_kb(),
        )
        await state.clear()
        return

    result = await session.execute(
        select(Test).where(Test.id == test_id, Test.user_id == user.id)
    )
    test = result.scalar_one_or_none()
    if not test:
        await state.clear()
        await message.answer("⚠️ Test topilmadi.", reply_markup=main_menu_kb())
        return

    ak_result = await session.execute(select(AnswerKey).where(AnswerKey.test_id == test.id))
    ak = ak_result.scalar_one_or_none()
    if not ak:
        await message.answer("⚠️ Javoblar kaliti topilmadi.", reply_markup=main_menu_kb())
        await state.clear()
        return

    answer_key = json.loads(ak.answers_json)
    TEMP.mkdir(parents=True, exist_ok=True)

    file_path = None
    is_pdf = False
    try:
        if message.document:
            doc = message.document
            ext = Path(doc.file_name or "").suffix.lower()
            if ext not in {".pdf", ".jpg", ".jpeg", ".png"}:
                await message.answer("⚠️ Faqat PDF yoki rasm (JPG/PNG) qabul qilinadi.")
                return
            if doc.file_size and doc.file_size > MAX_FILE_MB * 1024 * 1024:
                await message.answer(f"⚠️ Fayl hajmi {MAX_FILE_MB} MB dan oshmasligi kerak.")
                return
            file_path = TEMP / f"student_{user.telegram_id}_{doc.file_id}{ext}"
            await bot.download(doc, destination=file_path)
            is_pdf = ext == ".pdf"
            file_name = doc.file_name or file_path.name
        elif message.photo:
            photo = message.photo[-1]
            file_path = TEMP / f"student_{user.telegram_id}_{photo.file_id}.jpg"
            await bot.download(photo, destination=file_path)
            is_pdf = False
            file_name = file_path.name
        else:
            await message.answer("⚠️ Fayl yuboring.")
            return

        # Create processing job
        job = ProcessingJob(
            user_id=user.id,
            test_id=test.id,
            file_name=file_name,
            status="pending",
        )
        session.add(job)
        await session.flush()

        # Increment daily usage
        user.daily_pdf_used += 1
        await session.flush()

        status_msg = await message.answer("🔄 Fayl qabul qilindi. Tekshirish boshlandi...")

        # Process in background-ish (same event loop but with progress updates)
        await process_student_file(
            bot=bot,
            chat_id=message.chat.id,
            status_msg_id=status_msg.message_id,
            session=session,
            user=user,
            test=test,
            answer_key=answer_key,
            file_path=str(file_path),
            is_pdf=is_pdf,
            job=job,
        )
        await state.clear()

    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)[:300]}", reply_markup=main_menu_kb())
        await state.clear()
        if file_path:
            try:
                Path(file_path).unlink(missing_ok=True)
            except Exception:
                pass


async def process_student_file(
    bot: Bot,
    chat_id: int,
    status_msg_id: int,
    session: AsyncSession,
    user: User,
    test: Test,
    answer_key: dict,
    file_path: str,
    is_pdf: bool,
    job: ProcessingJob,
):
    pdf_service = PDFService(temp_dir=str(TEMP))
    gemini = GeminiService()
    checker = CheckerService()
    image_paths = []

    try:
        job.status = "processing"
        await session.flush()

        if is_pdf:
            if not pdf_service.is_valid_pdf(file_path):
                raise ValueError("PDF buzilgan yoki ochib bo‘lmadi.")
            total_pages = pdf_service.get_page_count(file_path)
            job.total_pages = total_pages
            await session.flush()

            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_msg_id,
                text=f"🔄 PDF ochildi. Jami sahifalar: {total_pages}\nSahifalar tayyorlanmoqda...",
            )
            image_paths = pdf_service.split_pdf_to_images(file_path, job.id)
        else:
            image_paths = [file_path]
            job.total_pages = 1
            await session.flush()

        page_results = [None] * total
        sem = asyncio.Semaphore(STUDENT_CONCURRENCY)
        lock = asyncio.Lock()
        done = [0]

        def progress_bar(count):
            bar_len = 20
            filled = int(bar_len * count / total)
            return "█" * filled + "░" * (bar_len - filled)

        def empty_result():
            return {"name": None, "class_name": None, "answers": {}}

        async def process_batch(idx_paths):
            async with sem:
                paths = [p for _, p in idx_paths]
                results = None
                try:
                    results = await gemini.extract_student_answers_batch(paths)
                except Exception as e:
                    logger.error(f"Batch extraction failed, falling back per-page: {e}")
                if not isinstance(results, list) or len(results) != len(idx_paths):
                    results = []
                    for p in paths:
                        try:
                            results.append(await gemini.extract_student_answers(p))
                        except Exception as e:
                            logger.error(f"Page extraction failed: {e}")
                            results.append(empty_result())
                for j, (idx, _) in enumerate(idx_paths):
                    page_results[idx] = (
                        results[j] if j < len(results) else empty_result()
                    )
                async with lock:
                    done[0] += len(idx_paths)
                    job.processed_pages = done[0]
                    await session.flush()
                    if done[0] == total or done[0] % (STUDENT_BATCH_SIZE * 4) == 0:
                        try:
                            await bot.edit_message_text(
                                chat_id=chat_id,
                                message_id=status_msg_id,
                                text=(
                                    f"🔄 Tekshirilmoqda...\n"
                                    f"{done[0]} / {total} sahifa\n"
                                    f"{progress_bar(done[0])}"
                                ),
                            )
                        except Exception:
                            pass

        batches = []
        for i in range(0, total, STUDENT_BATCH_SIZE):
            batches.append(list(enumerate(image_paths[i : i + STUDENT_BATCH_SIZE])))

        await asyncio.gather(*(process_batch(b) for b in batches))

        # Group pages into students.
        # Simple strategy: each page is one student unless name matches previous.
        # For multi-page same student: merge consecutive pages with same/empty name.
        students_raw = []
        current = None

        for page in page_results:
            name = page.get("name")
            if current is None:
                current = {
                    "name": name,
                    "class_name": page.get("class_name"),
                    "pages": [page],
                }
            elif name and current["name"] and name.strip().lower() != current["name"].strip().lower():
                # New student
                students_raw.append(current)
                current = {
                    "name": name,
                    "class_name": page.get("class_name"),
                    "pages": [page],
                }
            else:
                # Same student (or name empty) — append page
                if name and not current["name"]:
                    current["name"] = name
                if page.get("class_name") and not current["class_name"]:
                    current["class_name"] = page.get("class_name")
                current["pages"].append(page)

        if current:
            students_raw.append(current)

        # If no names found at all — treat each page as separate student
        if len(students_raw) == 1 and not students_raw[0]["name"] and len(page_results) > 1:
            # Could be multi-page single student OR many unnamed — warn
            students_raw = [
                {
                    "name": None,
                    "class_name": None,
                    "pages": [p],
                }
                for p in page_results
            ]
            warn_multi = True
        else:
            warn_multi = False

        saved_count = 0
        for idx, sraw in enumerate(students_raw, 1):
            merged = checker.merge_student_pages(sraw["pages"])
            name = merged["name"] or f"O‘quvchi #{idx}"
            class_name = merged["class_name"] or test.class_name

            student = Student(
                test_id=test.id,
                name=name,
                class_name=class_name,
            )
            session.add(student)
            await session.flush()

            sa = StudentAnswer(
                student_id=student.id,
                answers_json=json.dumps(merged["answers"], ensure_ascii=False),
            )
            session.add(sa)

            comparison = checker.compare(
                answer_key=answer_key,
                student_answers=merged["answers"],
                question_count=test.question_count,
            )

            result_obj = Result(
                student_id=student.id,
                correct_count=comparison["correct_count"],
                incorrect_count=comparison["incorrect_count"],
                uncertain_count=comparison["uncertain_count"],
                percentage=comparison["percentage"],
                score=comparison["score"],
                details_json=json.dumps(comparison["details"], ensure_ascii=False),
            )
            session.add(result_obj)
            saved_count += 1

        job.status = "completed"
        job.finished_at = datetime.now(timezone.utc)
        await session.flush()

        summary = (
            f"✅ <b>Tekshirish yakunlandi!</b>\n\n"
            f"📄 Fayl: {job.file_name}\n"
            f"📑 Sahifalar: {job.total_pages}\n"
            f"👨‍🎓 O‘quvchilar: {saved_count}\n"
            f"📚 Test: {test.test_name}\n\n"
            f"Natijalarni ko‘rish: <b>📊 Natijalar</b>\n"
            f"Excel: <b>📥 Excel</b>"
        )
        if warn_multi:
            summary += (
                "\n\n⚠️ Ba’zi sahifalarda ism topilmadi. "
                "Har bir sahifa alohida o‘quvchi sifatida saqlandi. "
                "Kerak bo‘lsa qo‘lda tuzating."
            )

        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg_id,
            text=summary,
            parse_mode="HTML",
        )
        await bot.send_message(chat_id, "Asosiy menyu:", reply_markup=main_menu_kb())

    except Exception as e:
        job.status = "failed"
        job.error = str(e)[:1000]
        job.finished_at = datetime.now(timezone.utc)
        await session.flush()
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_msg_id,
                text=f"❌ Tekshirishda xatolik:\n{str(e)[:300]}",
            )
        except Exception:
            pass
    finally:
        # Cleanup
        try:
            Path(file_path).unlink(missing_ok=True)
        except Exception:
            pass
        pdf_service.cleanup_job(job.id)
