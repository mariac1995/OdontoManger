"""Dentistas e procedimentos (cadastros de apoio)."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m, schemas as s
from ..database import get_db
from ..services.agenda import Conflito, obter

dentistas = APIRouter(prefix="/dentistas", tags=["Dentistas"])
procedimentos = APIRouter(prefix="/procedimentos", tags=["Procedimentos"])


@dentistas.get("", response_model=list[s.DentistaOut])
def listar_dentistas(apenas_ativos: bool = False, db: Session = Depends(get_db)):
    q = select(m.Dentista).order_by(m.Dentista.nome)
    if apenas_ativos:
        q = q.where(m.Dentista.ativo)
    return db.scalars(q).all()


@dentistas.post("", response_model=s.DentistaOut, status_code=201)
def criar_dentista(dados: s.DentistaIn, db: Session = Depends(get_db)):
    d = m.Dentista(**dados.model_dump())
    db.add(d)
    db.commit()
    return d


@dentistas.put("/{id}", response_model=s.DentistaOut)
def atualizar_dentista(id: int, dados: s.DentistaIn, db: Session = Depends(get_db)):
    d = obter(db, m.Dentista, id)
    for k, v in dados.model_dump().items():
        setattr(d, k, v)
    db.commit()
    return d


@procedimentos.get("", response_model=list[s.ProcedimentoOut])
def listar_procedimentos(apenas_ativos: bool = False, db: Session = Depends(get_db)):
    q = select(m.Procedimento).order_by(m.Procedimento.nome)
    if apenas_ativos:
        q = q.where(m.Procedimento.ativo)
    return db.scalars(q).all()


def _nome_livre(db, nome, ignorar_id=None):
    outro = db.scalars(select(m.Procedimento).where(m.Procedimento.nome == nome)).first()
    if outro and outro.id != ignorar_id:
        raise Conflito("Já existe um procedimento com esse nome.")


@procedimentos.post("", response_model=s.ProcedimentoOut, status_code=201)
def criar_procedimento(dados: s.ProcedimentoIn, db: Session = Depends(get_db)):
    _nome_livre(db, dados.nome)
    p = m.Procedimento(**dados.model_dump())
    db.add(p)
    db.commit()
    return p


@procedimentos.put("/{id}", response_model=s.ProcedimentoOut)
def atualizar_procedimento(id: int, dados: s.ProcedimentoIn, db: Session = Depends(get_db)):
    p = obter(db, m.Procedimento, id)
    _nome_livre(db, dados.nome, id)
    for k, v in dados.model_dump().items():
        setattr(p, k, v)
    db.commit()
    return p
