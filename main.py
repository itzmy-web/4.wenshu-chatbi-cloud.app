# 导入FastAPI核心类
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routers.auth_router import auth_router
from app.api.routers.connect_router import connect_router
from app.api.routers.dictionary_router import dictionary_router
from app.api.routers.query_router import query_router
from app.api.routers.report_router import daily_report_scheduler, report_router
from app.api.routers.suggest_router import suggest_router
from app.api.routers.upload_router import upload_router
from app.core.context import request_id_ctx_var
from app.core.lifespan import lifespan

# 创建FastAPI应用实例
app = FastAPI(lifespan=lifespan)

# 每日 09:00 自动刷新报告的后台任务
import asyncio

_scheduler_task = None


@app.on_event("startup")
async def _start_report_scheduler():
    global _scheduler_task
    _scheduler_task = asyncio.create_task(daily_report_scheduler())

# 注册路由
app.include_router(auth_router)
app.include_router(query_router)
app.include_router(suggest_router)
app.include_router(upload_router)
app.include_router(dictionary_router)
app.include_router(connect_router)
app.include_router(report_router)

# 首页聊天 UI
INDEX_HTML = Path(__file__).parent / "static" / "index.html"

# 页面禁缓存：每次打开都拿最新版，避免改版后浏览器还显示旧页面
NO_CACHE = {"Cache-Control": "no-cache, must-revalidate"}

# 静态资源（echarts.min.js 等）
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


@app.get("/")
async def index():
    return FileResponse(INDEX_HTML, headers=NO_CACHE)


# 数据大屏
DASHBOARD_HTML = Path(__file__).parent / "static" / "dashboard.html"


@app.get("/dashboard.html")
async def dashboard():
    return FileResponse(DASHBOARD_HTML, headers=NO_CACHE)


# 数据字典页
@app.get("/dictionary.html")
async def dictionary_page():
    return FileResponse(Path(__file__).parent / "static" / "dictionary.html", headers=NO_CACHE)


# 每日报告页
@app.get("/report.html")
async def report_page():
    return FileResponse(Path(__file__).parent / "static" / "report.html", headers=NO_CACHE)


# 查询记录 页（独立）
@app.get("/records.html")
async def records_page():
    return FileResponse(Path(__file__).parent / "static" / "records.html", headers=NO_CACHE)


# 收藏问法 页（独立）
@app.get("/favorites.html")
async def favorites_page():
    return FileResponse(Path(__file__).parent / "static" / "favorites.html", headers=NO_CACHE)


# 上传数据 页（独立）
@app.get("/upload.html")
async def upload_page():
    return FileResponse(Path(__file__).parent / "static" / "upload.html", headers=NO_CACHE)


# 构建标记（2026-10-14 新增）：用于判断线上进程是否已加载最新代码。
# 背景：部署复用沙箱时，若旧 uvicorn 进程未重启，磁盘新代码不会生效（stale process）。
# 用法：curl <host>/api/_build —— 值应与仓库最新提交说明一致。
BUILD_MARK = "2026-10-14-empty-result-guard"


@app.get("/api/_build")
async def build_mark():
    return {"build": BUILD_MARK}


# 整合中间件->设置异步协程上下文变量
@app.middleware("http")
async def add_request_cxt_var(request: Request, call_next):
    # 设置异步协程上下文变量
    request_id_ctx_var.set(uuid.uuid4())
    return await call_next(request)


if __name__ == "__main__":
    import uvicorn

    # 沙箱通过 PORT 环境变量注入端口，本地默认 8000
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
