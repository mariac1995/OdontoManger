"""Regras de negócio da agenda. Não conhece HTTP: levanta exceções de domínio."""
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import PASSO_AGENDA_MIN


class RegraDeNegocio(Exception):
    status_code = 422

    def __init__(self, mensagem: str):
        super().__init__(mensagem)
        self.mensagem = mensagem


class NaoEncontrado(RegraDeNegocio):
    status_code = 404


class Conflito(RegraDeNegocio):
    status_code = 409


def obter(db: Session, modelo, id_: int):
    obj = db.get(modelo, id_)
    if not obj:
        raise NaoEncontrado(f"{modelo.__name__} {id_} não encontrado(a).")
    return obj


def _hora(txt: str) -> time:
    return time.fromisoformat(txt)


def motivo_indisponivel(db: Session, dentista: m.Dentista, inicio: datetime, fim: datetime, *,
                        paciente_id: int | None = None, ignorar_id: int | None = None,
                        permitir_passado: bool = False) -> str | None:
    """Devolve o motivo pelo qual o intervalo NÃO pode ser agendado, ou None se está livre."""
    if not dentista.ativo:
        return "Dentista inativo."
    if inicio.date() != fim.date():
        return "O atendimento não pode atravessar a meia-noite."
    if inicio.time() < _hora(dentista.hora_inicio) or fim.time() > _hora(dentista.hora_fim):
        return f"Fora do expediente do dentista ({dentista.hora_inicio}–{dentista.hora_fim})."
    if not permitir_passado and inicio < datetime.now():
        return "Não é possível agendar no passado."

    def sobrepoe():
        q = select(m.Consulta).where(m.Consulta.inicio < fim, m.Consulta.fim > inicio,
                                     m.Consulta.status.not_in(m.LIBERAM_HORARIO))
        if ignorar_id:
            q = q.where(m.Consulta.id != ignorar_id)
        return q

    if db.scalars(sobrepoe().where(m.Consulta.dentista_id == dentista.id)).first():
        return "O dentista já tem consulta nesse horário."
    if paciente_id and db.scalars(sobrepoe().where(m.Consulta.paciente_id == paciente_id)).first():
        return "O paciente já tem outra consulta nesse horário."
    bloqueio = db.scalars(select(m.Bloqueio).where(m.Bloqueio.dentista_id == dentista.id,
                                                   m.Bloqueio.inicio < fim, m.Bloqueio.fim > inicio)).first()
    if bloqueio:
        return f"Horário bloqueado: {bloqueio.motivo}."
    return None


def _exigir_livre(db, dentista, inicio, fim, **kw):
    motivo = motivo_indisponivel(db, dentista, inicio, fim, **kw)
    if motivo:
        raise Conflito(motivo)


def horarios_livres(db: Session, dentista: m.Dentista, dia: date, duracao_min: int, *,
                    paciente_id: int | None = None, ignorar_id: int | None = None) -> list[str]:
    livres, atual = [], datetime.combine(dia, _hora(dentista.hora_inicio))
    limite = datetime.combine(dia, _hora(dentista.hora_fim))
    dur = timedelta(minutes=duracao_min)
    while atual + dur <= limite:
        if not motivo_indisponivel(db, dentista, atual, atual + dur,
                                   paciente_id=paciente_id, ignorar_id=ignorar_id):
            livres.append(atual.strftime("%H:%M"))
        atual += timedelta(minutes=PASSO_AGENDA_MIN)
    return livres


def criar_consulta(db: Session, *, paciente_id, dentista_id, procedimento_id, inicio, observacoes=None,
                   permitir_passado=False) -> m.Consulta:
    paciente = obter(db, m.Paciente, paciente_id)
    dentista = obter(db, m.Dentista, dentista_id)
    proc = obter(db, m.Procedimento, procedimento_id)
    if not proc.ativo:
        raise RegraDeNegocio("Procedimento inativo.")
    fim = inicio + timedelta(minutes=proc.duracao_min)
    _exigir_livre(db, dentista, inicio, fim, paciente_id=paciente.id, permitir_passado=permitir_passado)
    c = m.Consulta(paciente=paciente, dentista=dentista, procedimento=proc, inicio=inicio, fim=fim,
                   observacoes=observacoes)
    db.add(c)
    db.commit()
    return c


def reagendar(db: Session, c: m.Consulta, novo_inicio: datetime, novo_dentista_id: int | None = None):
    if c.status not in (m.AGENDADA, m.CONFIRMADA):
        raise RegraDeNegocio(f"Consulta {c.status} não pode ser reagendada.")
    dentista = obter(db, m.Dentista, novo_dentista_id) if novo_dentista_id else c.dentista
    fim = novo_inicio + timedelta(minutes=c.procedimento.duracao_min)
    _exigir_livre(db, dentista, novo_inicio, fim, paciente_id=c.paciente_id, ignorar_id=c.id)
    c.dentista, c.inicio, c.fim = dentista, novo_inicio, fim
    c.status = m.AGENDADA  # novo horário precisa ser confirmado de novo
    db.commit()
    return c


def alterar_status(db: Session, c: m.Consulta, novo: str):
    if novo not in m.TRANSICOES:
        raise RegraDeNegocio(f"Status desconhecido: {novo}.")
    if novo == m.CANCELADA:
        raise RegraDeNegocio("Para cancelar, informe o motivo em /cancelar.")
    if novo not in m.TRANSICOES[c.status]:
        raise Conflito(f"Transição inválida: {c.status} → {novo}.")
    c.status = novo
    db.commit()
    return c


def cancelar(db: Session, c: m.Consulta, motivo: str):
    if m.CANCELADA not in m.TRANSICOES[c.status]:
        raise Conflito(f"Consulta {c.status} não pode ser cancelada.")
    c.status, c.motivo_cancelamento = m.CANCELADA, motivo
    db.commit()
    return c


def resumo_dashboard(db: Session, agora: datetime | None = None) -> dict:
    agora = agora or datetime.now()
    ini_dia = datetime.combine(agora.date(), time.min)
    fim_dia = ini_dia + timedelta(days=1)
    ini_mes = ini_dia.replace(day=1)
    C = m.Consulta

    def conta(*filtros):
        return db.scalar(select(func.count()).select_from(C).where(*filtros)) or 0

    hoje = (C.inicio >= ini_dia, C.inicio < fim_dia)
    ativos_hoje = conta(*hoje, C.status.not_in(m.LIBERAM_HORARIO))
    concluidas_mes = conta(C.inicio >= ini_mes, C.status == m.CONCLUIDA)
    faltas_mes = conta(C.inicio >= ini_mes, C.status == m.FALTOU)
    base_faltas = concluidas_mes + faltas_mes
    top = db.execute(select(m.Procedimento.nome, func.count(C.id)).join(C)
                     .where(C.status == m.CONCLUIDA).group_by(m.Procedimento.id)
                     .order_by(func.count(C.id).desc()).limit(5)).all()
    return {
        "pacientes": db.scalar(select(func.count()).select_from(m.Paciente)) or 0,
        "consultas_hoje": ativos_hoje,
        "confirmadas_hoje": conta(*hoje, C.status == m.CONFIRMADA),
        "aguardando_confirmacao": conta(*hoje, C.status == m.AGENDADA),
        "cancelamentos_mes": conta(C.inicio >= ini_mes, C.status == m.CANCELADA),
        "consultas_futuras": conta(C.inicio >= agora, C.status.in_((m.AGENDADA, m.CONFIRMADA))),
        "taxa_faltas_mes": round(100 * faltas_mes / base_faltas, 1) if base_faltas else None,
        "procedimentos_mais_realizados": [{"nome": n, "total": t} for n, t in top],
    }
