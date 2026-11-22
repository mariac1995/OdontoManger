"""Utilitários de documentos (CPF)."""
import re


def somente_digitos(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def _dv(base: str) -> str:
    soma = sum(int(d) * p for d, p in zip(base, range(len(base) + 1, 1, -1)))
    r = (soma * 10) % 11
    return str(0 if r == 10 else r)


def cpf_valido(cpf: str) -> bool:
    if len(cpf) != 11 or not cpf.isdigit() or cpf == cpf[0] * 11:
        return False
    d1 = _dv(cpf[:9])
    return cpf[9] == d1 and cpf[10] == _dv(cpf[:9] + d1)


def gerar_cpf(base9: str) -> str:
    """Completa 9 dígitos com os verificadores (usado só para dados fictícios)."""
    d1 = _dv(base9)
    return base9 + d1 + _dv(base9 + d1)
