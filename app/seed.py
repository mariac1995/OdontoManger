"""Dados FICTÍCIOS para demonstração:  python -m app.seed   (use --reset para recriar o banco)."""
import sys
from datetime import date, datetime, time, timedelta

from . import models as m
from .database import Base, SessionLocal, engine
from .services.agenda import alterar_status, cancelar, criar_consulta
from .services.documentos import gerar_cpf

DENTISTAS = [("Dra. Helena Albuquerque", "CRO-RJ 41872", "Clínica geral", "08:00", "17:00"),
             ("Dr. Rafael Menezes", "CRO-RJ 38210", "Ortodontia", "09:00", "18:00")]
PROCEDIMENTOS = [("Avaliação", 30, 120), ("Limpeza (profilaxia)", 45, 180), ("Restauração", 60, 250),
                 ("Manutenção ortodôntica", 30, 150), ("Tratamento de canal", 90, 650), ("Clareamento", 60, 700)]
PACIENTES = ["Marcos Vinícius Pereira", "Juliana Carvalho Dias", "Tiago Nascimento Rocha", "Patrícia Lemos Barreto",
             "Eduardo Siqueira Neto", "Camila Ferreira Gomes", "Rodrigo Azevedo Pinto", "Larissa Monteiro Cruz",
             "Felipe Andrade Lopes", "Beatriz Cardoso Moura", "Gustavo Ribeiro Tavares", "Aline Souza Prado"]


def popular(db):
    dent = [m.Dentista(nome=n, cro=c, especialidade=e, hora_inicio=i, hora_fim=f) for n, c, e, i, f in DENTISTAS]
    proc = [m.Procedimento(nome=n, duracao_min=d, valor=v) for n, d, v in PROCEDIMENTOS]
    pac = [m.Paciente(nome=n, cpf=gerar_cpf(f"{(i + 3) * 7919 % 10**9:09d}"), telefone=f"2198{i:03d}{i * 7 % 10000:04d}",
                      data_nascimento=date(1970 + i * 3 % 35, 1 + i % 12, 1 + i * 2 % 28))
           for i, n in enumerate(PACIENTES)]
    db.add_all(dent + proc + pac)
    db.commit()

    hoje = date.today()
    plano = [  # (dia+, hora, dentista, paciente, procedimento, status final)
        (0, "08:30", 0, 0, 1, "confirmada"), (0, "09:30", 0, 1, 2, "agendada"), (0, "10:00", 1, 2, 3, "confirmada"),
        (0, "11:00", 1, 3, 0, "agendada"), (0, "14:00", 0, 4, 4, "confirmada"), (0, "15:30", 1, 5, 5, "agendada"),
        (1, "09:00", 0, 6, 0, "agendada"), (1, "10:00", 1, 7, 3, "confirmada"), (1, "14:00", 0, 8, 2, "agendada"),
        (2, "09:30", 1, 9, 3, "agendada"), (2, "11:00", 0, 10, 1, "agendada"),
        (-1, "09:00", 0, 11, 0, "concluida"), (-1, "10:00", 1, 0, 3, "concluida"), (-2, "14:00", 0, 2, 2, "faltou"),
        (-3, "09:00", 1, 4, 3, "concluida"), (-4, "15:00", 0, 6, 1, "cancelada")]
    for dia, hora, di, pi, pr, final in plano:
        inicio = datetime.combine(hoje + timedelta(days=dia), time.fromisoformat(hora))
        c = criar_consulta(db, paciente_id=pac[pi].id, dentista_id=dent[di].id, procedimento_id=proc[pr].id,
                           inicio=inicio, permitir_passado=True)
        if final == "cancelada":
            cancelar(db, c, "Paciente desmarcou")
        else:
            for etapa in {"confirmada": ["confirmada"], "faltou": ["faltou"],
                          "concluida": ["confirmada", "em_atendimento", "concluida"]}.get(final, []):
                alterar_status(db, c, etapa)
    almoco = datetime.combine(hoje, time(12, 0))
    for d in dent:
        db.add(m.Bloqueio(dentista_id=d.id, inicio=almoco, fim=almoco + timedelta(hours=1), motivo="Almoço"))
    db.commit()


if __name__ == "__main__":
    if "--reset" in sys.argv:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.query(m.Paciente).count():
            sys.exit("Banco já tem dados. Use --reset para recriar.")
        popular(db)
    print("Dados fictícios criados.")
