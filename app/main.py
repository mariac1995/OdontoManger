"""Aplicação FastAPI: API em /api e frontend estático em /."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, models  # noqa: F401  (registra as tabelas)
from .config import FRONTEND_DIR
from .database import Base, engine
from .routers import agenda, cadastros, pacientes
from .services.agenda import RegraDeNegocio


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="OdontoManager", version=__version__, lifespan=lifespan,
              description="Gestão e agendamento odontológico (Fase 1 – MVP).")


@app.exception_handler(RegraDeNegocio)
async def regra_de_negocio(_: Request, exc: RegraDeNegocio):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.mensagem})


for r in (pacientes.router, cadastros.dentistas, cadastros.procedimentos, agenda.router):
    app.include_router(r, prefix="/api")

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
