"""Modelo de dados (Fase 1): pacientes, dentistas, procedimentos, consultas e bloqueios."""
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

AGENDADA, CONFIRMADA, EM_ATENDIMENTO = "agendada", "confirmada", "em_atendimento"
CONCLUIDA, CANCELADA, FALTOU = "concluida", "cancelada", "faltou"

# Fluxo: Agendada -> Confirmada -> Em atendimento -> Concluída (cancelamento/falta nas etapas iniciais)
TRANSICOES = {
    AGENDADA: {CONFIRMADA, CANCELADA, FALTOU},
    CONFIRMADA: {EM_ATENDIMENTO, CANCELADA, FALTOU},
    EM_ATENDIMENTO: {CONCLUIDA},
    CONCLUIDA: set(),
    CANCELADA: set(),
    FALTOU: set(),
}
# Status que NÃO ocupam mais o horário da agenda
LIBERAM_HORARIO = (CANCELADA, FALTOU)


class Paciente(Base):
    __tablename__ = "pacientes"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), index=True)
    cpf: Mapped[str] = mapped_column(String(11), unique=True, index=True)
    telefone: Mapped[str] = mapped_column(String(11))
    data_nascimento: Mapped[date | None] = mapped_column(Date)
    email: Mapped[str | None] = mapped_column(String(120))
    endereco: Mapped[str | None] = mapped_column(String(255))
    observacoes: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    consultas: Mapped[list["Consulta"]] = relationship(back_populates="paciente")


class Dentista(Base):
    __tablename__ = "dentistas"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    cro: Mapped[str] = mapped_column(String(20))
    especialidade: Mapped[str | None] = mapped_column(String(80))
    hora_inicio: Mapped[str] = mapped_column(String(5), default="08:00")  # HH:MM
    hora_fim: Mapped[str] = mapped_column(String(5), default="18:00")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    consultas: Mapped[list["Consulta"]] = relationship(back_populates="dentista")


class Procedimento(Base):
    __tablename__ = "procedimentos"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True)
    duracao_min: Mapped[int] = mapped_column(Integer)
    valor: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class Consulta(Base):
    __tablename__ = "consultas"
    id: Mapped[int] = mapped_column(primary_key=True)
    paciente_id: Mapped[int] = mapped_column(ForeignKey("pacientes.id"), index=True)
    dentista_id: Mapped[int] = mapped_column(ForeignKey("dentistas.id"), index=True)
    procedimento_id: Mapped[int] = mapped_column(ForeignKey("procedimentos.id"))
    inicio: Mapped[datetime] = mapped_column(DateTime, index=True)
    fim: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default=AGENDADA, index=True)
    observacoes: Mapped[str | None] = mapped_column(Text)
    motivo_cancelamento: Mapped[str | None] = mapped_column(String(255))
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    paciente: Mapped[Paciente] = relationship(back_populates="consultas")
    dentista: Mapped[Dentista] = relationship(back_populates="consultas")
    procedimento: Mapped[Procedimento] = relationship()


class Bloqueio(Base):
    """Horário indisponível do dentista (almoço, reunião, férias)."""
    __tablename__ = "bloqueios"
    id: Mapped[int] = mapped_column(primary_key=True)
    dentista_id: Mapped[int] = mapped_column(ForeignKey("dentistas.id"), index=True)
    inicio: Mapped[datetime] = mapped_column(DateTime)
    fim: Mapped[datetime] = mapped_column(DateTime)
    motivo: Mapped[str] = mapped_column(String(120))
