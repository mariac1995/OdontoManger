from datetime import date, timedelta

from .conftest import agendar, amanha_as


def test_agenda_consulta_calcula_fim_pela_duracao(client, base):
    r = agendar(client, base, "09:00", proc="longo")
    assert r.status_code == 201
    assert r.json()["fim"].endswith("10:00:00") and r.json()["status"] == "agendada"


def test_bloqueia_sobreposicao_do_mesmo_dentista(client, base):
    assert agendar(client, base, "09:00", proc="longo").status_code == 201
    r = agendar(client, base, "09:30", paciente="p2")  # cai no meio da consulta de 1h
    assert r.status_code == 409 and "dentista" in r.json()["detail"]


def test_horarios_adjacentes_sao_permitidos(client, base):
    assert agendar(client, base, "09:00").status_code == 201          # 09:00–09:30
    assert agendar(client, base, "09:30", paciente="p2").status_code == 201


def test_consulta_longa_nao_cabe_em_buraco_curto(client, base):
    agendar(client, base, "10:00")                                      # ocupa 10:00–10:30
    r = agendar(client, base, "09:30", paciente="p2", proc="longo")     # 09:30–10:30 invade
    assert r.status_code == 409


def test_cancelar_libera_o_horario(client, base):
    cid = agendar(client, base, "09:00").json()["id"]
    assert client.post(f"/api/consultas/{cid}/cancelar", json={"motivo": "Paciente desmarcou"}).status_code == 200
    assert agendar(client, base, "09:00", paciente="p2").status_code == 201


def test_paciente_nao_pode_ter_duas_consultas_no_mesmo_horario(client, base):
    agendar(client, base, "09:00")
    r = agendar(client, base, "09:00", dentista="d2")
    assert r.status_code == 409 and "paciente" in r.json()["detail"]


def test_fora_do_expediente(client, base):
    assert agendar(client, base, "07:30").status_code == 409
    assert agendar(client, base, "17:45").status_code == 409  # termina 18:15


def test_nao_agenda_no_passado(client, base):
    ontem = (date.today() - timedelta(days=1)).isoformat() + "T09:00:00"
    r = client.post("/api/consultas", json={"paciente_id": base["p1"]["id"], "dentista_id": base["d"]["id"],
                                            "procedimento_id": base["curto"]["id"], "inicio": ontem})
    assert r.status_code == 409


def test_bloqueio_impede_agendamento_e_aparece_fora_dos_horarios_livres(client, base):
    amanha = date.today() + timedelta(days=1)
    r = client.post("/api/bloqueios", json={"dentista_id": base["d"]["id"], "inicio": amanha_as("12:00"),
                                           "fim": amanha_as("13:00"), "motivo": "Almoço"})
    assert r.status_code == 201
    assert agendar(client, base, "12:15").status_code == 409
    livres = client.get("/api/agenda/horarios-livres", params=dict(
        dentista_id=base["d"]["id"], data=amanha.isoformat(), procedimento_id=base["curto"]["id"])).json()
    assert "11:30" in livres and "12:00" not in livres and "12:30" not in livres and "13:00" in livres


def test_nao_bloqueia_periodo_com_consulta(client, base):
    agendar(client, base, "09:00")
    r = client.post("/api/bloqueios", json={"dentista_id": base["d"]["id"], "inicio": amanha_as("08:30"),
                                           "fim": amanha_as("09:30"), "motivo": "Reunião"})
    assert r.status_code == 409


def test_reagendar_respeita_conflito_e_volta_para_agendada(client, base):
    agendar(client, base, "09:00", paciente="p2")
    cid = agendar(client, base, "10:00").json()["id"]
    client.post(f"/api/consultas/{cid}/status", json={"status": "confirmada"})
    assert client.patch(f"/api/consultas/{cid}/reagendar", json={"inicio": amanha_as("09:15")}).status_code == 409
    r = client.patch(f"/api/consultas/{cid}/reagendar", json={"inicio": amanha_as("11:00")})
    assert r.status_code == 200 and r.json()["status"] == "agendada"


def test_reagendar_ignora_a_propria_consulta(client, base):
    cid = agendar(client, base, "09:00", proc="longo").json()["id"]
    assert client.patch(f"/api/consultas/{cid}/reagendar", json={"inicio": amanha_as("09:30")}).status_code == 200


def test_fluxo_de_status_valido_e_invalido(client, base):
    cid = agendar(client, base, "09:00").json()["id"]
    st = lambda s: client.post(f"/api/consultas/{cid}/status", json={"status": s})
    assert st("concluida").status_code == 409                # não pode pular etapas
    assert [st(x).status_code for x in ("confirmada", "em_atendimento", "concluida")] == [200, 200, 200]
    assert st("confirmada").status_code == 409               # concluída é final
    assert client.post(f"/api/consultas/{cid}/cancelar", json={"motivo": "tarde demais"}).status_code == 409


def test_falta_libera_horario_e_conta_no_dashboard(client, base):
    cid = agendar(client, base, "09:00").json()["id"]
    client.post(f"/api/consultas/{cid}/status", json={"status": "faltou"})
    assert agendar(client, base, "09:00", paciente="p2").status_code == 201


def test_consultas_nao_podem_ser_excluidas(client, base):
    cid = agendar(client, base, "09:00").json()["id"]
    assert client.delete(f"/api/consultas/{cid}").status_code == 405


def test_horarios_livres_para_dia_vazio(client, base):
    amanha = (date.today() + timedelta(days=1)).isoformat()
    livres = client.get("/api/agenda/horarios-livres", params=dict(
        dentista_id=base["d"]["id"], data=amanha, procedimento_id=base["longo"]["id"])).json()
    assert livres[0] == "08:00" and livres[-1] == "17:00" and len(livres) == 37
