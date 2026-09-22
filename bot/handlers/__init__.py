from aiogram import Router
from .start import router as start_router
from .test_create import router as test_create_router
from .answer_key import router as answer_key_router
from .student_answers import router as student_answers_router
from .results import router as results_router
from .premium import router as premium_router
from .profile import router as profile_router
from .help import router as help_router
from .admin import router as admin_router
from .fallback import router as fallback_router


def get_all_routers() -> list[Router]:
    return [
        start_router,
        test_create_router,
        answer_key_router,
        student_answers_router,
        results_router,
        premium_router,
        profile_router,
        help_router,
        admin_router,
        fallback_router,
    ]
