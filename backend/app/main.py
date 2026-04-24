from contextlib import asynccontextmanager
import json
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.utils.seed_data import seed_prompt_configs
from app.routers import projects, episodes, shots, assets, tasks
from app.routers.admin import prompt_configs as admin_prompt_configs
from app.routers import generation
from app.routers import conversations
from app.routers import sts


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed_prompt_configs()
    yield


def _normalize_ids(obj):
    """递归将 JSON 对象中的 _id 字段改为 id，使后端输出与前端期望一致。"""
    if isinstance(obj, list):
        return [_normalize_ids(item) for item in obj]
    if isinstance(obj, dict):
        return {("id" if k == "_id" else k): _normalize_ids(v) for k, v in obj.items()}
    return obj


app = FastAPI(
    title="AI Short Film API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def normalize_id_middleware(request: Request, call_next):
    """将所有 JSON 响应中的 _id 字段统一重命名为 id。"""
    response = await call_next(request)
    content_type = response.headers.get("content-type", "")
    if "application/json" not in content_type:
        return response

    body = b""
    async for chunk in response.body_iterator:
        body += chunk

    try:
        data = json.loads(body)
        normalized = _normalize_ids(data)
        new_body = json.dumps(normalized, ensure_ascii=False).encode("utf-8")
        return Response(
            content=new_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type="application/json",
        )
    except (json.JSONDecodeError, Exception):
        return Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )

API_PREFIX = "/api/v1"

app.include_router(projects.router, prefix=API_PREFIX)
app.include_router(episodes.router, prefix=API_PREFIX)
app.include_router(shots.router, prefix=API_PREFIX)
app.include_router(assets.router, prefix=API_PREFIX)
app.include_router(tasks.router, prefix=API_PREFIX)
app.include_router(generation.router, prefix=API_PREFIX)
app.include_router(conversations.router, prefix=API_PREFIX)
app.include_router(admin_prompt_configs.router, prefix=API_PREFIX)
app.include_router(sts.router, prefix=API_PREFIX)


@app.get("/health")
async def health():
    return {"status": "ok"}
