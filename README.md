# OdontoManager

Sistema web de gestão e agendamento odontológico. Esta versão implementa a **Fase 1 (MVP)**:
cadastro de pacientes e dentistas, agenda com verificação de conflitos e banco de dados.

> Use apenas **dados fictícios**. Prontuários e dados de saúde são sensíveis (LGPD).

## Como rodar

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements-dev.txt

python -m app.seed                # (opcional) dados fictícios de demonstração
uvicorn app.main:app --reload     # abre em http://localhost:8000
```

- Interface: http://localhost:8000
- Documentação interativa da API: http://localhost:8000/docs
- Testes: `pytest`
- Recriar os dados de demonstração: `python -m app.seed --reset`

## Estrutura

```
odontomanager/
├── app/
│   ├── main.py              # FastAPI: monta rotas em /api e serve o frontend
│   ├── config.py            # configurações (banco, passo da agenda)
│   ├── database.py          # engine/sessão SQLAlchemy
│   ├── models.py            # tabelas e fluxo de status
│   ├── schemas.py           # validação (Pydantic)
│   ├── seed.py              # dados fictícios
│   ├── routers/             # camada HTTP (pacientes, cadastros, agenda)
│   └── services/
│       ├── agenda.py        # REGRAS DE NEGÓCIO (sem HTTP)
│       └── documentos.py    # validação de CPF
├── frontend/                # HTML + CSS + JavaScript puro
├── tests/                   # pytest (regras de agenda e cadastros)
└── requirements*.txt
```

As regras ficam em `services/`, separadas das rotas: dá para testá-las sem HTTP e reaproveitá-las depois (lembretes, relatórios).

## Regras de negócio implementadas

| Regra | Comportamento |
|---|---|
| Conflito de horários | Não permite duas consultas sobrepostas do mesmo dentista |
| Duração | O fim da consulta é calculado pela duração do procedimento |
| Paciente | Não pode ter duas consultas ao mesmo tempo; CPF validado e único; nome + nascimento também não duplica |
| Expediente | Só agenda dentro do horário do dentista e nunca no passado |
| Bloqueios | Almoço, reunião ou férias impedem agendamento; não bloqueia período que já tem consulta |
| Cancelamento | Exige motivo e libera o horário |
| Faltas | Status "faltou" libera o horário e entra na taxa de faltas |
| Status | Agendada → Confirmada → Em atendimento → Concluída (não pula etapas) |
| Reagendamento | Revalida conflitos e volta para "Agendada" |
| Histórico | Consultas não podem ser excluídas (só canceladas); paciente com histórico não é excluído |

## Roteiro

- [x] **Fase 1 – MVP:** pacientes, dentistas, agenda, agendar/cancelar/reagendar, conflitos, banco, dashboard básico
- [ ] **Fase 2 – Gestão:** prontuário e odontograma, tratamentos, financeiro
- [ ] **Fase 3 – Automação:** lembretes, WhatsApp, relatórios
- [ ] **Fase 4 – Avançado:** login JWT e perfis (admin/dentista/recepção), auditoria, backup, deploy

## Limitações conhecidas

- Sem autenticação: não exponha na internet antes da Fase 4.
- Sem dias da semana de atendimento (domingo aparece como dia útil); o expediente é o mesmo todos os dias.
- Sem migrações (Alembic): ao mudar o modelo, recrie o banco (`--reset`) ou adote migrações.
- A fonte Manrope vem do Google Fonts; sem internet, o navegador usa uma fonte do sistema.
