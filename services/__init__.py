from .form.main import router as form_router
from .bot.main import router as bot_router
from .llm.main import router as llm_router
from .parser.main import router as parser_router
from .scoring.main import router as scoring_router
from .dashboard.main import router as dashboard_router


# This file makes the "services" directory a Python package
# and allows for better imports of services.


__all__ = ["form_router", "bot_router", "llm_router", "parser_router", "scoring_router", "dashboard_router"]