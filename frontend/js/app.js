/* OdontoManager – frontend (JS puro). Fala com a API em /api. */
const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const brl = v => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v);
const iso = d => d.toLocaleDateString('sv-SE');
const parseDia = s => { const [y, m, d] = s.split('-').map(Number); return new Date(y, m - 1, d); };
const hhmm = s => s.slice(11, 16);
const minutos = t => { const [h, m] = t.split(':').map(Number); return h * 60 + m; };
const fmtCpf = c => c.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, '$1.$2.$3-$4');
const fmtTel = t => t.length === 11 ? t.replace(/(\d{2})(\d{5})(\d{4})/, '($1) $2-$3') : t.replace(/(\d{2})(\d{4})(\d{4})/, '($1) $2-$3');
const fmtData = s => s ? s.split('-').reverse().join('/') : '—';
const ROTULO = { agendada: 'Agendada', confirmada: 'Confirmada', em_atendimento: 'Em atendimento', concluida: 'Concluída', cancelada: 'Cancelada', faltou: 'Faltou' };
const HPX = 72;

const estado = { dia: iso(new Date()), dentistas: [], procs: [] };

/* ---------- infraestrutura ---------- */
function erroTexto(d) {
  if (Array.isArray(d)) return d.map(e => `${(e.loc || []).slice(1).join('.')}: ${String(e.msg).replace('Value error, ', '')}`).join('\n');
  return d || 'Erro inesperado.';
}
async function api(caminho, { method = 'GET', body, params } = {}) {
  const url = new URL('/api' + caminho, location.origin);
  Object.entries(params || {}).forEach(([k, v]) => { if (v != null && v !== '') url.searchParams.set(k, v); });
  const r = await fetch(url, { method, headers: body ? { 'Content-Type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined });
  if (r.status === 204) return null;
  const dados = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(erroTexto(dados.detail));
  return dados;
}
function aviso(msg, erro = false) {
  const el = document.createElement('div');
  if (erro) el.className = 'erro';
  el.textContent = msg;
  $('#aviso').append(el);
  setTimeout(() => el.remove(), erro ? 6000 : 3000);
}
const dlg = $('#dlg');
function abrir(titulo, corpo, rodape = '', largo = false) {
  dlg.className = largo ? 'largo' : '';
  dlg.innerHTML = `<div class="dlg-cab"><h2>${esc(titulo)}</h2><button class="fechar" type="button" aria-label="Fechar" data-fechar>×</button></div>
    <div class="dlg-corpo">${corpo}</div>${rodape ? `<div class="dlg-rodape">${rodape}</div>` : ''}`;
  dlg.querySelectorAll('[data-fechar]').forEach(b => b.onclick = () => dlg.close());
  if (!dlg.open) dlg.showModal();
}
const aberto = () => dlg.open;

/* Formulário genérico: campos = [{n, rot, tipo, opcoes, req, cheio, ph, step}] */
function formulario({ titulo, campos, valores = {}, enviar, rotuloEnviar = 'Salvar', extra = '' }) {
  const campo = c => {
    const v = valores[c.n] ?? c.padrao ?? '';
    const id = 'f_' + c.n;
    const attrs = `id="${id}" name="${c.n}" ${c.req ? 'required' : ''} ${c.ph ? `placeholder="${esc(c.ph)}"` : ''} ${c.step ? `step="${c.step}"` : ''}`;
    let ctl;
    if (c.tipo === 'select') ctl = `<select ${attrs}>${c.opcoes.map(([val, rot]) => `<option value="${esc(val)}" ${String(val) === String(v) ? 'selected' : ''}>${esc(rot)}</option>`).join('')}</select>`;
    else if (c.tipo === 'textarea') ctl = `<textarea ${attrs}>${esc(v)}</textarea>`;
    else if (c.tipo === 'checkbox') return `<div class="campo check"><input type="checkbox" ${attrs} ${v ? 'checked' : ''}><label for="${id}">${esc(c.rot)}</label></div>`;
    else ctl = `<input type="${c.tipo || 'text'}" ${attrs} value="${esc(v)}">`;
    return `<div class="campo ${c.cheio ? 'cheio' : ''}"><label for="${id}">${esc(c.rot)}</label>${ctl}</div>`;
  };
  abrir(titulo, `<form id="form" novalidate><div class="campos">${campos.map(campo).join('')}</div>${extra}<p class="erro-form" id="erro" role="alert"></p></form>`,
    `<button class="btn" type="button" data-fechar>Cancelar</button><button class="btn principal" type="submit" form="form">${rotuloEnviar}</button>`);
  const f = $('#form');
  f.onsubmit = async ev => {
    ev.preventDefault();
    if (!f.reportValidity()) return;
    const out = {};
    for (const c of campos) {
      const el = f.elements[c.n];
      if (c.tipo === 'checkbox') out[c.n] = el.checked;
      else if (c.tipo === 'number') out[c.n] = el.value === '' ? null : Number(el.value);
      else out[c.n] = el.value.trim() === '' && !c.req ? null : el.value.trim();
    }
    try { await enviar(out); dlg.close(); } catch (e) { $('#erro').textContent = e.message; }
  };
}

/* ---------- referências ---------- */
async function carregarRefs() {
  [estado.dentistas, estado.procs] = await Promise.all([api('/dentistas'), api('/procedimentos')]);
}
const ativos = l => l.filter(x => x.ativo);

/* ---------- AGENDA ---------- */
async function viewAgenda() {
  const dia = estado.dia, dd = parseDia(dia), ehHoje = dia === iso(new Date());
  const [consultas, bloqueios, dash] = await Promise.all([api('/consultas', { params: { data: dia } }), api('/bloqueios', { params: { data: dia } }), api('/dashboard')]);
  const dentistas = ativos(estado.dentistas);
  const ocupam = consultas.filter(c => !['cancelada', 'faltou'].includes(c.status));
  const liberadas = consultas.filter(c => ['cancelada', 'faltou'].includes(c.status));
  const ini = Math.min(...dentistas.map(d => Math.floor(minutos(d.hora_inicio) / 60)), 8);
  const fim = Math.max(...dentistas.map(d => Math.ceil(minutos(d.hora_fim) / 60)), 18);
  const alt = (fim - ini) * HPX, top = min => (min - ini * 60) / 60 * HPX;
  const horas = Array.from({ length: fim - ini + 1 }, (_, i) => `<span style="top:${i * HPX}px">${String(ini + i).padStart(2, '0')}:00</span>`).join('');
  const agora = new Date(), minAgora = agora.getHours() * 60 + agora.getMinutes();

  const colunas = dentistas.map(d => {
    const evts = ocupam.filter(c => c.dentista.id === d.id).map(c => {
      const a = minutos(hhmm(c.inicio)), b = minutos(hhmm(c.fim)), h = (b - a) / 60 * HPX - 2;
      return `<button class="evt st-${c.status} ${h < 50 ? 'curta' : ''}" style="top:${top(a)}px;height:${h}px" data-consulta="${c.id}" title="${esc(c.paciente.nome)} — ${esc(c.procedimento.nome)}">
        <b>${hhmm(c.inicio)}</b><span class="nome">${esc(c.paciente.nome)}</span><small>${esc(c.procedimento.nome)}</small></button>`;
    }).join('');
    const blks = bloqueios.filter(b => b.dentista_id === d.id).map(b => {
      const a = Math.max(minutos(hhmm(b.inicio)), ini * 60), z = Math.min(minutos(hhmm(b.fim)), fim * 60);
      return `<div class="blk" style="top:${top(a)}px;height:${(z - a) / 60 * HPX - 2}px" data-bloqueio="${b.id}" title="Clique para remover o bloqueio">${esc(b.motivo)}</div>`;
    }).join('');
    const linha = ehHoje && minAgora >= ini * 60 && minAgora <= fim * 60 ? `<div class="agora" style="top:${top(minAgora)}px"></div>` : '';
    const n = ocupam.filter(c => c.dentista.id === d.id).length;
    return { cab: `<div class="cab"><b>${esc(d.nome)}</b><span>${esc(d.especialidade || '')}${d.especialidade ? ' – ' : ''}${n} consulta${n === 1 ? '' : 's'}</span></div>`,
      col: `<div class="col" data-dentista="${d.id}">${blks}${evts}${linha}</div>` };
  });
  const stat = (v, r) => `<div><b>${v}</b><span>${r}</span></div>`;
  $('#app').innerHTML = `
    <div class="barra">
      <h1>${dd.toLocaleDateString('pt-BR', { weekday: 'long' }).replace(/^./, c => c.toUpperCase())}<small>${dd.toLocaleDateString('pt-BR', { day: 'numeric', month: 'long', year: 'numeric' })}</small></h1>
      <button class="btn" data-dia="-1" aria-label="Dia anterior">‹</button>
      <button class="btn" data-dia="hoje">Hoje</button>
      <button class="btn" data-dia="1" aria-label="Próximo dia">›</button>
      <input type="date" id="irpara" value="${dia}" aria-label="Ir para a data">
      <button class="btn" id="bloquear">Bloquear horário</button>
      <button class="btn principal" id="novo">Novo agendamento</button>
    </div>
    <div class="resumo" aria-label="Resumo de hoje">
      ${stat(dash.consultas_hoje, 'consultas hoje')}${stat(dash.confirmadas_hoje, 'confirmadas')}${stat(dash.aguardando_confirmacao, 'aguardando confirmação')}
      ${stat(dash.consultas_futuras, 'consultas futuras')}${stat(dash.cancelamentos_mes, 'cancelamentos no mês')}${stat(dash.taxa_faltas_mes == null ? '—' : dash.taxa_faltas_mes + '%', 'faltas no mês')}${stat(dash.pacientes, 'pacientes')}
    </div>
    ${dentistas.length ? `<div class="agenda"><div class="agenda-grade" style="--alt:${alt}px;--hpx:${HPX}px;grid-template-columns:56px repeat(${dentistas.length},minmax(220px,1fr))">
      <div class="cab vazio"></div>${colunas.map(c => c.cab).join('')}
      <div class="horas">${horas}</div>${colunas.map(c => c.col).join('')}</div></div>` : '<div class="painel vazio-msg">Cadastre um dentista em “Cadastros” para usar a agenda.</div>'}
    <div class="legenda">${['agendada', 'confirmada', 'em_atendimento', 'concluida'].map(s => `<span><i style="--c:var(--${s === 'em_atendimento' ? 'atendimento' : s})"></i>${ROTULO[s]}</span>`).join('')}</div>
    ${liberadas.length ? `<p class="fora-agenda">Fora da agenda (horário liberado): ${liberadas.map(c => `${hhmm(c.inicio)} ${esc(c.paciente.nome)} – ${ROTULO[c.status].toLowerCase()}`).join('; ')}.</p>` : ''}`;

  const app = $('#app');
  app.querySelectorAll('[data-dia]').forEach(b => b.onclick = () => { const v = b.dataset.dia; const n = v === 'hoje' ? new Date() : new Date(dd.getTime() + (+v) * 864e5 + 36e5); estado.dia = iso(n); viewAgenda(); });
  $('#irpara').onchange = e => { if (e.target.value) { estado.dia = e.target.value; viewAgenda(); } };
  $('#novo').onclick = () => agendamento({});
  $('#bloquear').onclick = () => bloquear();
  app.querySelectorAll('[data-consulta]').forEach(b => b.onclick = e => { e.stopPropagation(); detalheConsulta(consultas.find(c => c.id === +b.dataset.consulta)); });
  app.querySelectorAll('[data-bloqueio]').forEach(b => b.onclick = async e => {
    e.stopPropagation();
    if (confirm(`Remover o bloqueio “${b.textContent}”?`)) { await api('/bloqueios/' + b.dataset.bloqueio, { method: 'DELETE' }); aviso('Bloqueio removido.'); viewAgenda(); }
  });
  app.querySelectorAll('.col').forEach(col => col.onclick = e => {
    if (e.target !== col) return;
    const min = Math.floor((e.offsetY / HPX * 60 + ini * 60) / 15) * 15;
    agendamento({ dentista_id: +col.dataset.dentista, hora: `${String(Math.floor(min / 60)).padStart(2, '0')}:${String(min % 60).padStart(2, '0')}` });
  });
}

function detalheConsulta(c) {
  const f = { agendada: ['confirmada', 'Confirmar'], confirmada: ['em_atendimento', 'Iniciar atendimento'], em_atendimento: ['concluida', 'Concluir'] }[c.status];
  const pode = ['agendada', 'confirmada'].includes(c.status);
  abrir('Consulta', `<div class="detalhe"><dl>
      <dt>Paciente</dt><dd>${esc(c.paciente.nome)} (${fmtTel(c.paciente.telefone)})</dd>
      <dt>Procedimento</dt><dd>${esc(c.procedimento.nome)} – ${c.procedimento.duracao_min} min – ${brl(c.procedimento.valor)}</dd>
      <dt>Dentista</dt><dd>${esc(c.dentista.nome)}</dd>
      <dt>Horário</dt><dd>${fmtData(c.inicio.slice(0, 10))}, ${hhmm(c.inicio)} às ${hhmm(c.fim)}</dd>
      <dt>Situação</dt><dd><span class="etiqueta st-${c.status}">${ROTULO[c.status]}</span></dd>
      ${c.observacoes ? `<dt>Observações</dt><dd>${esc(c.observacoes)}</dd>` : ''}
      ${c.motivo_cancelamento ? `<dt>Motivo do cancelamento</dt><dd>${esc(c.motivo_cancelamento)}</dd>` : ''}</dl></div>`,
    `${pode ? '<button class="btn perigo" id="a-cancelar">Cancelar consulta</button><button class="btn" id="a-faltou">Marcar falta</button><button class="btn" id="a-reag">Reagendar</button>' : ''}
     ${f ? `<button class="btn principal" id="a-avancar">${f[1]}</button>` : ''}`);
  const mudar = async novo => { try { await api(`/consultas/${c.id}/status`, { method: 'POST', body: { status: novo } }); dlg.close(); aviso('Situação atualizada.'); viewAgenda(); } catch (e) { aviso(e.message, true); } };
  if (f) $('#a-avancar').onclick = () => mudar(f[0]);
  if (pode) {
    $('#a-faltou').onclick = () => mudar('faltou');
    $('#a-reag').onclick = () => agendamento({ consulta: c });
    $('#a-cancelar').onclick = () => formulario({ titulo: 'Cancelar consulta', rotuloEnviar: 'Cancelar consulta',
      campos: [{ n: 'motivo', rot: 'Motivo do cancelamento', tipo: 'textarea', req: true, cheio: true }],
      enviar: async v => { await api(`/consultas/${c.id}/cancelar`, { method: 'POST', body: v }); aviso('Consulta cancelada; horário liberado.'); viewAgenda(); } });
  }
}

/* Novo agendamento / reagendamento (mesmo formulário) */
async function agendamento({ dentista_id, hora, consulta, paciente_id }) {
  const edit = !!consulta;
  const pacientes = edit ? [] : await api('/pacientes');
  const rotuloPac = p => `${p.nome} (${fmtCpf(p.cpf)})`;
  const dsel = consulta?.dentista.id ?? dentista_id ?? ativos(estado.dentistas)[0]?.id;
  const dia = edit ? consulta.inicio.slice(0, 10) : estado.dia;
  const prePac = pacientes.find(p => p.id === paciente_id);
  abrir(edit ? 'Reagendar consulta' : 'Novo agendamento', `<form id="form" novalidate><div class="campos">
    <div class="campo cheio"><label for="f_pac">Paciente</label>
      ${edit ? `<input id="f_pac" value="${esc(consulta.paciente.nome)}" disabled>` : `<div style="display:flex;gap:.5rem"><input id="f_pac" list="lista-pac" autocomplete="off" placeholder="Digite o nome ou CPF" value="${prePac ? esc(rotuloPac(prePac)) : ''}" required><button class="btn" type="button" id="novo-pac">Novo</button></div>
      <datalist id="lista-pac">${pacientes.map(p => `<option value="${esc(rotuloPac(p))}"></option>`).join('')}</datalist>`}</div>
    <div class="campo"><label for="f_proc">Procedimento</label><select id="f_proc" ${edit ? 'disabled' : ''}>${(edit ? estado.procs : ativos(estado.procs)).map(p => `<option value="${p.id}" ${edit && p.id === consulta.procedimento.id ? 'selected' : ''}>${esc(p.nome)} (${p.duracao_min} min)</option>`).join('')}</select></div>
    <div class="campo"><label for="f_dent">Dentista</label><select id="f_dent">${ativos(estado.dentistas).map(d => `<option value="${d.id}" ${d.id === dsel ? 'selected' : ''}>${esc(d.nome)}</option>`).join('')}</select></div>
    <div class="campo"><label for="f_data">Data</label><input type="date" id="f_data" value="${dia}" min="${iso(new Date())}" required></div>
    <div class="campo cheio"><label>Horários livres</label><div class="horarios" id="slots" role="group" aria-label="Horários livres"></div></div>
    ${edit ? '' : '<div class="campo cheio"><label for="f_obs">Observações</label><textarea id="f_obs"></textarea></div>'}
    </div><p class="erro-form" id="erro" role="alert"></p></form>`,
    `<button class="btn" type="button" data-fechar>Cancelar</button><button class="btn principal" id="salvar" type="submit" form="form" disabled>${edit ? 'Reagendar' : 'Agendar'}</button>`);

  let escolhido = hora || (edit ? hhmm(consulta.inicio) : null);
  const pacId = () => edit ? consulta.paciente.id : pacientes.find(p => rotuloPac(p) === $('#f_pac').value)?.id;
  async function slots() {
    const box = $('#slots'); $('#salvar').disabled = true;
    if (!$('#f_dent').value || !$('#f_proc').value || !$('#f_data').value) { box.innerHTML = '<p>Preencha procedimento, dentista e data.</p>'; return; }
    try {
      const livres = await api('/agenda/horarios-livres', { params: { dentista_id: $('#f_dent').value, procedimento_id: $('#f_proc').value, data: $('#f_data').value, paciente_id: pacId(), ignorar_consulta_id: consulta?.id } });
      if (!livres.includes(escolhido)) escolhido = null;
      box.innerHTML = livres.length ? livres.map(h => `<button type="button" aria-pressed="${h === escolhido}" data-h="${h}">${h}</button>`).join('') : '<p>Nenhum horário livre neste dia.</p>';
      box.querySelectorAll('button').forEach(b => b.onclick = () => { escolhido = b.dataset.h; box.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', x === b)); $('#salvar').disabled = !(edit || pacId()); });
      $('#salvar').disabled = !(escolhido && (edit || pacId()));
    } catch (e) { box.innerHTML = `<p>${esc(e.message)}</p>`; }
  }
  ['f_dent', 'f_proc', 'f_data'].forEach(id => $('#' + id).onchange = slots);
  if (!edit) {
    $('#f_pac').oninput = () => { $('#salvar').disabled = !(escolhido && pacId()); };
    $('#f_pac').onchange = slots;
    $('#novo-pac').onclick = () => formPaciente(null, p => agendamento({ dentista_id: +$('#f_dent')?.value || dsel, hora: escolhido, paciente_id: p.id }));
  }
  $('#form').onsubmit = async ev => {
    ev.preventDefault();
    const inicio = `${$('#f_data').value}T${escolhido}:00`;
    try {
      if (edit) await api(`/consultas/${consulta.id}/reagendar`, { method: 'PATCH', body: { inicio, dentista_id: +$('#f_dent').value } });
      else await api('/consultas', { method: 'POST', body: { paciente_id: pacId(), dentista_id: +$('#f_dent').value, procedimento_id: +$('#f_proc').value, inicio, observacoes: $('#f_obs').value.trim() || null } });
      dlg.close(); aviso(edit ? 'Consulta reagendada.' : 'Consulta agendada.'); estado.dia = $('#f_data').value; viewAgenda();
    } catch (e) { $('#erro').textContent = e.message; slots(); }
  };
  slots();
}

function bloquear() {
  formulario({ titulo: 'Bloquear horário', rotuloEnviar: 'Bloquear',
    campos: [{ n: 'dentista_id', rot: 'Dentista', tipo: 'select', opcoes: ativos(estado.dentistas).map(d => [d.id, d.nome]), cheio: true },
      { n: 'data', rot: 'Data', tipo: 'date', req: true, padrao: estado.dia, cheio: true },
      { n: 'ini', rot: 'Das', tipo: 'time', req: true, padrao: '12:00' }, { n: 'fim', rot: 'Às', tipo: 'time', req: true, padrao: '13:00' },
      { n: 'motivo', rot: 'Motivo', req: true, ph: 'Almoço, reunião, férias…', cheio: true }],
    enviar: async v => { await api('/bloqueios', { method: 'POST', body: { dentista_id: +v.dentista_id, inicio: `${v.data}T${v.ini}:00`, fim: `${v.data}T${v.fim}:00`, motivo: v.motivo } }); aviso('Horário bloqueado.'); estado.dia = v.data; viewAgenda(); } });
}

/* ---------- PACIENTES ---------- */
function formPaciente(p, aoSalvar) {
  formulario({ titulo: p ? 'Editar paciente' : 'Novo paciente', valores: p ? { ...p, cpf: fmtCpf(p.cpf), telefone: fmtTel(p.telefone) } : {},
    campos: [{ n: 'nome', rot: 'Nome completo', req: true, cheio: true }, { n: 'cpf', rot: 'CPF', req: true, ph: '000.000.000-00' }, { n: 'telefone', rot: 'Telefone', req: true, ph: '(21) 99999-0000' },
      { n: 'data_nascimento', rot: 'Data de nascimento', tipo: 'date' }, { n: 'email', rot: 'E-mail', tipo: 'email' },
      { n: 'endereco', rot: 'Endereço', cheio: true }, { n: 'observacoes', rot: 'Observações', tipo: 'textarea', cheio: true }],
    enviar: async v => { const r = await api(p ? '/pacientes/' + p.id : '/pacientes', { method: p ? 'PUT' : 'POST', body: v }); aviso('Paciente salvo.'); aoSalvar ? aoSalvar(r) : viewPacientes(); } });
}
async function historico(p) {
  const h = await api(`/pacientes/${p.id}/consultas`);
  abrir(`Histórico – ${p.nome}`, h.length ? `<div class="painel"><table><thead><tr><th>Data</th><th>Procedimento</th><th>Dentista</th><th>Situação</th></tr></thead><tbody>
    ${h.map(c => `<tr><td>${fmtData(c.inicio.slice(0, 10))} ${hhmm(c.inicio)}</td><td>${esc(c.procedimento.nome)}</td><td>${esc(c.dentista.nome)}</td><td><span class="etiqueta st-${c.status}">${ROTULO[c.status]}</span></td></tr>`).join('')}</tbody></table></div>` : '<p class="vazio-msg">Sem consultas registradas.</p>',
    `<button class="btn principal" data-fechar>Fechar</button>`, true);
}
async function viewPacientes(q = '') {
  const lista = await api('/pacientes', { params: { q } });
  $('#app').innerHTML = `<div class="barra"><h1>Pacientes<small>${lista.length} ${q ? 'encontrado(s)' : 'cadastrado(s)'}</small></h1>
    <input type="search" id="busca" class="btn" style="font-weight:500;cursor:text;min-width:260px" placeholder="Buscar por nome ou CPF" value="${esc(q)}" aria-label="Buscar paciente">
    <button class="btn principal" id="novo">Novo paciente</button></div>
    <div class="painel">${lista.length ? `<table><thead><tr><th>Nome</th><th>CPF</th><th>Telefone</th><th>Nascimento</th><th></th></tr></thead><tbody>
    ${lista.map(p => `<tr><td><b>${esc(p.nome)}</b></td><td>${fmtCpf(p.cpf)}</td><td>${fmtTel(p.telefone)}</td><td>${fmtData(p.data_nascimento)}</td>
      <td class="acoes"><button class="btn mini" data-hist="${p.id}">Histórico</button> <button class="btn mini" data-edit="${p.id}">Editar</button> <button class="btn mini" data-ag="${p.id}">Agendar</button></td></tr>`).join('')}</tbody></table>` : '<div class="vazio-msg">Nenhum paciente encontrado.</div>'}</div>`;
  let t; const b = $('#busca'); b.oninput = () => { clearTimeout(t); t = setTimeout(() => viewPacientes(b.value).then(() => { const n = $('#busca'); n.focus(); n.setSelectionRange(n.value.length, n.value.length); }), 300); };
  $('#novo').onclick = () => formPaciente(null);
  const por = id => lista.find(p => p.id === +id);
  $('#app').querySelectorAll('[data-hist]').forEach(x => x.onclick = () => historico(por(x.dataset.hist)));
  $('#app').querySelectorAll('[data-edit]').forEach(x => x.onclick = () => formPaciente(por(x.dataset.edit)));
  $('#app').querySelectorAll('[data-ag]').forEach(x => x.onclick = () => agendamento({ paciente_id: +x.dataset.ag }));
}

/* ---------- CADASTROS ---------- */
function formDentista(d) {
  formulario({ titulo: d ? 'Editar dentista' : 'Novo dentista', valores: d || {},
    campos: [{ n: 'nome', rot: 'Nome', req: true, cheio: true }, { n: 'cro', rot: 'CRO', req: true, ph: 'CRO-UF 00000' }, { n: 'especialidade', rot: 'Especialidade' },
      { n: 'hora_inicio', rot: 'Início do expediente', tipo: 'time', req: true, padrao: '08:00' }, { n: 'hora_fim', rot: 'Fim do expediente', tipo: 'time', req: true, padrao: '18:00' },
      { n: 'ativo', rot: 'Ativo (aparece na agenda)', tipo: 'checkbox', padrao: true }],
    enviar: async v => { await api(d ? '/dentistas/' + d.id : '/dentistas', { method: d ? 'PUT' : 'POST', body: v }); aviso('Dentista salvo.'); await carregarRefs(); viewCadastros(); } });
}
function formProc(p) {
  formulario({ titulo: p ? 'Editar procedimento' : 'Novo procedimento', valores: p || {},
    campos: [{ n: 'nome', rot: 'Nome', req: true, cheio: true }, { n: 'duracao_min', rot: 'Duração (minutos)', tipo: 'number', req: true, step: 5, padrao: 30 },
      { n: 'valor', rot: 'Valor (R$)', tipo: 'number', req: true, step: '0.01', padrao: 0 }, { n: 'ativo', rot: 'Ativo', tipo: 'checkbox', padrao: true }],
    enviar: async v => { await api(p ? '/procedimentos/' + p.id : '/procedimentos', { method: p ? 'PUT' : 'POST', body: v }); aviso('Procedimento salvo.'); await carregarRefs(); viewCadastros(); } });
}
function viewCadastros() {
  const { dentistas, procs } = estado;
  $('#app').innerHTML = `<div class="barra"><h1>Cadastros<small>Dentistas e procedimentos</small></h1></div><div class="dupla">
    <section><div class="titulo-sec"><h2>Dentistas</h2><button class="btn principal" id="nd">Novo dentista</button></div><div class="painel"><table><thead><tr><th>Nome</th><th>Expediente</th><th></th></tr></thead><tbody>
    ${dentistas.map(d => `<tr class="${d.ativo ? '' : 'inativo'}"><td><b>${esc(d.nome)}</b><br><small>${esc(d.cro)}${d.especialidade ? ' – ' + esc(d.especialidade) : ''}${d.ativo ? '' : ' – inativo'}</small></td><td>${d.hora_inicio}–${d.hora_fim}</td><td class="acoes"><button class="btn mini" data-d="${d.id}">Editar</button></td></tr>`).join('') || '<tr><td colspan="3" class="vazio-msg">Nenhum dentista.</td></tr>'}</tbody></table></div></section>
    <section><div class="titulo-sec"><h2>Procedimentos</h2><button class="btn principal" id="np">Novo procedimento</button></div><div class="painel"><table><thead><tr><th>Nome</th><th>Duração</th><th>Valor</th><th></th></tr></thead><tbody>
    ${procs.map(p => `<tr class="${p.ativo ? '' : 'inativo'}"><td><b>${esc(p.nome)}</b></td><td>${p.duracao_min} min</td><td>${brl(p.valor)}</td><td class="acoes"><button class="btn mini" data-p="${p.id}">Editar</button></td></tr>`).join('') || '<tr><td colspan="4" class="vazio-msg">Nenhum procedimento.</td></tr>'}</tbody></table></div></section></div>`;
  $('#nd').onclick = () => formDentista(null); $('#np').onclick = () => formProc(null);
  $('#app').querySelectorAll('[data-d]').forEach(b => b.onclick = () => formDentista(dentistas.find(d => d.id === +b.dataset.d)));
  $('#app').querySelectorAll('[data-p]').forEach(b => b.onclick = () => formProc(procs.find(p => p.id === +b.dataset.p)));
}

/* ---------- roteamento ---------- */
async function rotear() {
  const aba = (location.hash || '#agenda').slice(1);
  document.querySelectorAll('.abas a').forEach(a => a.removeAttribute('aria-current'));
  document.querySelectorAll('.abas a').forEach(a => { if (a.dataset.aba === aba) a.setAttribute('aria-current', 'page'); });
  try {
    await carregarRefs();
    await ({ agenda: viewAgenda, pacientes: () => viewPacientes(), cadastros: viewCadastros }[aba] || viewAgenda)();
  } catch (e) { $('#app').innerHTML = `<div class="painel vazio-msg">Não foi possível carregar os dados.<br>${esc(e.message)}</div>`; }
}
addEventListener('hashchange', rotear);
addEventListener('focus', () => { if (!aberto() && (location.hash || '#agenda') === '#agenda') viewAgenda().catch(() => { }); });
rotear();
