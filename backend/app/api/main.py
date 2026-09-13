from fastapi import APIRouter

from app.api.routes import (
    backtest,
    configs,
    exports,
    global_preview,
    google_sheets,
    items,
    login,
    logs,
    meta,
    model_summary,
    navigation,
    performance_analysis,
    private,
    scheduled_tasks,
    stocks,
    task_results,
    task_templates,
    tasks,
    users,
    utils,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(items.router)

# google_sheet_task migration domain
api_router.include_router(tasks.router)
api_router.include_router(task_results.router)
api_router.include_router(global_preview.router)
api_router.include_router(backtest.router)
api_router.include_router(model_summary.router)
api_router.include_router(exports.router)
api_router.include_router(performance_analysis.router)
api_router.include_router(google_sheets.sheets_router)
api_router.include_router(google_sheets.tokens_router)
api_router.include_router(scheduled_tasks.router)
api_router.include_router(task_templates.router)
api_router.include_router(stocks.router)
api_router.include_router(configs.router)
api_router.include_router(navigation.router)
api_router.include_router(logs.router)
api_router.include_router(meta.router)


if settings.FASTAPI_ENV == "development":
    api_router.include_router(private.router)
