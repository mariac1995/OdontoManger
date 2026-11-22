"""Schemas Pydantic: validação de entrada e formato das respostas."""
import re
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .services.documentos import cpf_valido, somente_digitos


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Pacientes ----------
class PacienteIn(BaseModel):
    nome: str = Field(min_length=3, max_length=120)
    cpf: str
    telefone: str
    data_nascimento: date | None = None
    email: str | None = Field(default=None, max_length=120)
    endereco: str | None = Field(default=None, max_length=255)
    observacoes: str | None = None

    @field_validator("nome")
    @classmethod
    def _nome(cls, v):
        return " ".join(v.split())

    @field_validator("cpf")
    @classmethod
    def _cpf(cls, v):
        d = somente_digitos(v)
        if not cpf_valido(d):
            raise ValueError("CPF inválido")
        return d

    @field_validator("telefone")
    @classmethod
    def _tel(cls, v):
        d = somente_digitos(v)
        if len(d) not in (10, 11):
            raise ValueError("Telefone deve ter DDD + 8 ou 9 dígitos")
        return d

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        if v in (None, ""):
            return None
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v):
            raise ValueError("E-mail inválido")
        return v.lower()

    @field_validator("data_nascimento")
    @classmethod
    def _nasc(cls, v):
        if v and v > date.today():
            raise ValueError("Data de nascimento no futuro")
        return v


class PacienteOut(Out):
    id: int
    nome: str
    cpf: str
    telefone: str
    data_nascimento: date | None
    email: str | None
    endereco: str | None
    observacoes: str | None


class PacienteResumo(Out):
    id: int
    nome: str
    telefone: str


# ---------- Dentistas ----------
class DentistaIn(BaseModel):
    nome: str = Field(min_length=3, max_length=120)
    cro: str = Field(min_length=3, max_length=20)
    especialidade: str | None = Field(default=None, max_length=80)
    hora_inicio: str = "08:00"
    hora_fim: str = "18:00"
    ativo: bool = True

    @field_validator("hora_inicio", "hora_fim")
    @classmethod
    def _hora(cls, v):
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v):
            raise ValueError("Use o formato HH:MM")
        return v

    @model_validator(mode="after")
    def _ordem(self):
        if self.hora_inicio >= self.hora_fim:
            raise ValueError("hora_inicio deve ser anterior a hora_fim")
        return self


class DentistaOut(Out):
    id: int
    nome: str
    cro: str
    especialidade: str | None
    hora_inicio: str
    hora_fim: str
    ativo: bool


# ---------- Procedimentos ----------
class ProcedimentoIn(BaseModel):
    nome: str = Field(min_length=3, max_length=120)
    duracao_min: int = Field(gt=0, le=480)
    valor: float = Field(ge=0)
    ativo: bool = True


class ProcedimentoOut(Out):
    id: int
    nome: str
    duracao_min: int
    valor: float
    ativo: bool


# ---------- Consultas ----------
class ConsultaIn(BaseModel):
    paciente_id: int
    dentista_id: int
    procedimento_id: int
    inicio: datetime
    observacoes: str | None = None


class ReagendarIn(BaseModel):
    inicio: datetime
    dentista_id: int | None = None


class StatusIn(BaseModel):
    status: str


class CancelarIn(BaseModel):
    motivo: str = Field(min_length=3, max_length=255)


class ConsultaOut(Out):
    id: int
    inicio: datetime
    fim: datetime
    status: str
    observacoes: str | None
    motivo_cancelamento: str | None
    paciente: PacienteResumo
    dentista: DentistaOut
    procedimento: ProcedimentoOut


# ---------- Bloqueios ----------
class BloqueioIn(BaseModel):
    dentista_id: int
    inicio: datetime
    fim: datetime
    motivo: str = Field(min_length=3, max_length=120)

    @model_validator(mode="after")
    def _ordem(self):
        if self.inicio >= self.fim:
            raise ValueError("inicio deve ser anterior a fim")
        return self


class BloqueioOut(Out):
    id: int
    dentista_id: int
    inicio: datetime
    fim: datetime
    motivo: str
