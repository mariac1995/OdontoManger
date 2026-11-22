from datetime import date, datetime, time, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.services.documentos import gerar_cpf


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Sessao = sessionmaker(bind=engine, autoflush=False)

    def _db():
        with Sessao() as db:
            yield db

    app.dependency_overrides[get_db] = _db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def amanha_as(hhmm: str) -> str:
    return datetime.combine(date.today() + timedelta(days=1), time.fromisoformat(hhmm)).isoformat()


@pytest.fixture()
def base(client):
    """Um dentista (08–18), dois pacientes e dois procedimentos (30 e 60 min)."""
    d = client.post("/api/dentistas", json={"nome": "Dra. Teste", "cro": "CRO-1234"}).json()
    d2 = client.post("/api/dentistas", json={"nome": "Dr. Outro", "cro": "CRO-5678"}).json()
    p1 = client.post("/api/pacientes", json={"nome": "Ana Souza", "cpf": gerar_cpf("123456789"),
                                              "telefone": "21999990000"}).json()
    p2 = client.post("/api/pacientes", json={"nome": "Bruno Lima", "cpf": gerar_cpf("987654321"),
                                              "telefone": "21988880000"}).json()
    curto = client.post("/api/procedimentos", json={"nome": "Avaliação", "duracao_min": 30, "valor": 100}).json()
    longo = client.post("/api/procedimentos", json={"nome": "Restauração", "duracao_min": 60, "valor": 250}).json()
    return dict(d=d, d2=d2, p1=p1, p2=p2, curto=curto, longo=longo)


def agendar(client, base, hhmm, paciente="p1", proc="curto", dentista="d"):
    return client.post("/api/consultas", json={
        "paciente_id": base[paciente]["id"], "dentista_id": base[dentista]["id"],
        "procedimento_id": base[proc]["id"], "inicio": amanha_as(hhmm)})
