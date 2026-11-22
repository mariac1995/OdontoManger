from app.services.documentos import cpf_valido, gerar_cpf

from .conftest import agendar


def test_cpf_validacao():
    assert cpf_valido(gerar_cpf("123456789"))
    assert not cpf_valido("12345678900") and not cpf_valido("11111111111") and not cpf_valido("123")


def test_cadastro_normaliza_cpf_e_telefone(client):
    r = client.post("/api/pacientes", json={"nome": "  Maria   Silva ", "cpf": "529.982.247-25",
                                             "telefone": "(21) 99999-0000", "email": "MARIA@Teste.com"})
    assert r.status_code == 201
    d = r.json()
    assert (d["nome"], d["cpf"], d["telefone"], d["email"]) == ("Maria Silva", "52998224725", "21999990000",
                                                                  "maria@teste.com")


def test_cpf_invalido_e_rejeitado(client):
    r = client.post("/api/pacientes", json={"nome": "Fulano", "cpf": "111.111.111-11", "telefone": "21999990000"})
    assert r.status_code == 422


def test_cpf_duplicado_e_rejeitado(client, base):
    r = client.post("/api/pacientes", json={"nome": "Outro Nome", "cpf": base["p1"]["cpf"], "telefone": "21999990000"})
    assert r.status_code == 409


def test_nome_e_nascimento_duplicados(client):
    dados = dict(nome="Carlos Alberto", cpf=gerar_cpf("111222333"), telefone="21999990000", data_nascimento="1990-05-10")
    assert client.post("/api/pacientes", json=dados).status_code == 201
    assert client.post("/api/pacientes", json={**dados, "cpf": gerar_cpf("444555666")}).status_code == 409


def test_busca_por_nome_ou_cpf(client, base):
    assert [p["nome"] for p in client.get("/api/pacientes", params={"q": "bruno"}).json()] == ["Bruno Lima"]
    assert [p["nome"] for p in client.get("/api/pacientes", params={"q": base["p1"]["cpf"][:6]}).json()] == ["Ana Souza"]


def test_paciente_com_historico_nao_pode_ser_excluido(client, base):
    agendar(client, base, "09:00")
    assert client.delete(f"/api/pacientes/{base['p1']['id']}").status_code == 409
    assert client.delete(f"/api/pacientes/{base['p2']['id']}").status_code == 204


def test_historico_do_paciente(client, base):
    agendar(client, base, "09:00")
    h = client.get(f"/api/pacientes/{base['p1']['id']}/consultas").json()
    assert len(h) == 1 and h[0]["procedimento"]["nome"] == "Avaliação"


def test_dentista_com_expediente_invalido(client):
    r = client.post("/api/dentistas", json={"nome": "Dr. X", "cro": "CRO-9", "hora_inicio": "18:00", "hora_fim": "08:00"})
    assert r.status_code == 422


def test_dashboard(client, base):
    agendar(client, base, "09:00")
    d = client.get("/api/dashboard").json()
    assert d["pacientes"] == 2 and d["consultas_futuras"] == 1 and d["taxa_faltas_mes"] is None
