"""Consultas, horários livres, bloqueios e dashboard.
Não há DELETE de consulta: o histórico é preservado (use /cancelar)."""
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m, schemas as s
from ..database import get_db
from ..services import agenda as svc

router = APIRouter(tags=["Agenda"])


@router.get("/consultas", response_model=list[s.ConsultaOut])
def listar_consultas(data: date | None = None, dentista_id: int | None = None, status: str | None = None,
                     db: Session = Depends(get_db)):
    q = select(m.Consulta).order_by(m.Consulta.inicio)
    if data:
        ini = datetime.combine(data, time.min)
        q = q.where(m.Consulta.inicio >= ini, m.Consulta.inicio < ini + timedelta(days=1))
    if dentista_id:
        q = q.where(m.Consulta.dentista_id == dentista_id)
    if status:
        q = q.where(m.Consulta.status == status)
    return db.scalars(q).all()


@router.post("/consultas", response_model=s.ConsultaOut, status_code=201)
def agendar(dados: s.ConsultaIn, db: Session = Depends(get_db)):
    return svc.criar_consulta(db, **dados.model_dump())


@router.get("/consultas/{id}", response_model=s.ConsultaOut)
def detalhar(id: int, db: Session = Depends(get_db)):
    return svc.obter(db, m.Consulta, id)


@router.patch("/consultas/{id}/reagendar", response_model=s.ConsultaOut)
def reagendar(id: int, dados: s.ReagendarIn, db: Session = Depends(get_db)):
    return svc.reagendar(db, svc.obter(db, m.Consulta, id), dados.inicio, dados.dentista_id)


@router.post("/consultas/{id}/status", response_model=s.ConsultaOut)
def mudar_status(id: int, dados: s.StatusIn, db: Session = Depends(get_db)):
    return svc.alterar_status(db, svc.obter(db, m.Consulta, id), dados.status)


@router.post("/consultas/{id}/cancelar", response_model=s.ConsultaOut)
def cancelar(id: int, dados: s.CancelarIn, db: Session = Depends(get_db)):
    return svc.cancelar(db, svc.obter(db, m.Consulta, id), dados.motivo)


@router.get("/agenda/horarios-livres", response_model=list[str])
def horarios_livres(dentista_id: int, data: date, procedimento_id: int, paciente_id: int | None = None,
                    ignorar_consulta_id: int | None = None, db: Session = Depends(get_db)):
    d = svc.obter(db, m.Dentista, dentista_id)
    p = svc.obter(db, m.Procedimento, procedimento_id)
    return svc.horarios_livres(db, d, data, p.duracao_min, paciente_id=paciente_id, ignorar_id=ignorar_consulta_id)


@router.get("/bloqueios", response_model=list[s.BloqueioOut])
def listar_bloqueios(data: date, db: Session = Depends(get_db)):
    ini = datetime.combine(data, time.min)
    return db.scalars(select(m.Bloqueio).where(m.Bloqueio.inicio < ini + timedelta(days=1),
                                               m.Bloqueio.fim > ini).order_by(m.Bloqueio.inicio)).all()


@router.post("/bloqueios", response_model=s.BloqueioOut, status_code=201)
def criar_bloqueio(dados: s.BloqueioIn, db: Session = Depends(get_db)):
    svc.obter(db, m.Dentista, dados.dentista_id)
    choque = db.scalars(select(m.Consulta).where(
        m.Consulta.dentista_id == dados.dentista_id, m.Consulta.inicio < dados.fim,
        m.Consulta.fim > dados.inicio, m.Consulta.status.not_in(m.LIBERAM_HORARIO))).first()
    if choque:
        raise svc.Conflito("Já existe consulta nesse período; reagende ou cancele antes de bloquear.")
    b = m.Bloqueio(**dados.model_dump())
    db.add(b)
    db.commit()
    return b


@router.delete("/bloqueios/{id}", status_code=204)
def remover_bloqueio(id: int, db: Session = Depends(get_db)):
    db.delete(svc.obter(db, m.Bloqueio, id))
    db.commit()
    return Response(status_code=204)


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    return svc.resumo_dashboard(db)
