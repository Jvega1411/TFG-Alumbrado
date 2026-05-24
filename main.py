from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.routes import init_engine, router
from config.settings import Config
from model.database import Base, create_db_engine

PROJECT_ROOT = Path(__file__).resolve().parent
WEB_DIR = PROJECT_ROOT / "web"
STATIC_DIR = WEB_DIR / "static"

Config.validate_api()
_engine = create_db_engine(Config.DB_ESTADOS_URL)
if Config.DB_AUTO_CREATE:
    Base.metadata.create_all(_engine)
init_engine(_engine)

app = FastAPI(
    title="alumbrado-gateway",
    description="API read-only y panel web para supervision de alumbrado.",
)
app.include_router(router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


if __name__ == "__main__":
    uvicorn.run("main:app", host=Config.API_HOST, port=Config.API_PORT, reload=False)
