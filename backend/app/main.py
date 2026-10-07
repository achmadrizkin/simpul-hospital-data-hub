import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import seed
from .api import router
from .db import DB_PATH, init_db
from .live import scheduler_loop
from .pipeline import register_sources

FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if not DB_PATH.exists() or not seed.STATE_FILE.exists():
        await asyncio.to_thread(seed.run)
    else:
        init_db()
        register_sources()
    task = asyncio.create_task(scheduler_loop())
    yield
    task.cancel()


app = FastAPI(title="Simpul — Hospital Data Hub", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/api/health")
def health():
    return {"ok": True}


# Serve the built dashboard from the same port when it exists (single-command demo).
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        file = FRONTEND_DIST / path
        if path and file.is_file():
            return FileResponse(file)
        return FileResponse(FRONTEND_DIST / "index.html")
