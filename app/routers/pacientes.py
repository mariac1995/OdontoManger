from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import models as m, schemas as s
from ..database import get_db
from ..services.agenda import Conflito, obter
from ..services.documentos import somente_digitos

router = APIRouter(prefix="/pacientes", tags=["Pacientes"])


def _checar_duplicidade(db: Session, dados: s.PacienteIn, ignorar_id: int | None = None):
    q = select(m.Paciente).where(m.Paciente.cpf == dados.cpf)
    outro = db.scalars(q).first()
    if outro and outro.id != ignorar_id:
        raise Conflito(f"Já existe paciente com este CPF: {outro.nome}.")
    if dados.data_nascimento:
        q = select(m.Paciente).where(m.Paciente.nome == dados.nome,
                                     m.Paciente.data_nascimento == dados.data_nascimento)
        outro = db.scalars(q).first()
        if outro and outro.id != ignorar_id:
            raise Conflito("Já existe paciente com mesmo nome e data de nascimento.")


@router.get("", response_model=list[s.PacienteOut])
def listar(q: str | None = Query(None, description="Busca por nome ou CPF"), limite: int = 500,
           db: Session = Depends(get_db)):
    stmt = select(m.Paciente).order_by(m.Paciente.nome).limit(limite)
    if q:
        digitos = somente_digitos(q)
        cond = [m.Paciente.nome.ilike(f"%{q.strip()}%")]
        if digitos:
            cond.append(m.Paciente.cpf.like(f"%{digitos}%"))
        stmt = stmt.where(or_(*cond))
    return db.scalars(stmt).all()


@router.post("", response_model=s.PacienteOut, status_code=201)
def criar(dados: s.PacienteIn, db: Session = Depends(get_db)):
    _checar_duplicidade(db, dados)
    p = m.Paciente(**dados.model_dump())
    db.add(p)
    db.commit()
    return p


@router.get("/{id}", response_model=s.PacienteOut)
def detalhar(id: int, db: Session = Depends(get_db)):
    return obter(db, m.Paciente, id)


@router.put("/{id}", response_model=s.PacienteOut)
def atualizar(id: int, dados: s.PacienteIn, db: Session = Depends(get_db)):
    p = obter(db, m.Paciente, id)
    _checar_duplicidade(db, dados, ignorar_id=id)
    for k, v in dados.model_dump().items():
        setattr(p, k, v)
    db.commit()
    return p


@router.get("/{id}/consultas", response_model=list[s.ConsultaOut])
def historico(id: int, db: Session = Depends(get_db)):
    obter(db, m.Paciente, id)
    return db.scalars(select(m.Consulta).where(m.Consulta.paciente_id == id)
                      .order_by(m.Consulta.inicio.desc())).all()


@router.delete("/{id}", status_code=204)
def excluir(id: int, db: Session = Depends(get_db)):
    """Só exclui paciente sem histórico: registros anteriores são preservados."""
    p = obter(db, m.Paciente, id)
    if p.consultas:
        raise Conflito("Paciente possui histórico de consultas e não pode ser excluído.")
    db.delete(p)
    db.commit()
    return Response(status_code=204)
