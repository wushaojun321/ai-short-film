from contextlib import asynccontextmanager
from fastapi import FastAPI
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
