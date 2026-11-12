/* SGE PRO – Vistoria, Etapa 1: registrar problema num local.
   Problema -> causas e serviços (reparos). Marcar causas filtra os serviços,
   marcar serviços filtra as causas. Cada serviço marcado pede a quantidade na sua unidade. */
(function () {
  'use strict';

  var DADOS = JSON.parse(document.getElementById('dados-vistoria').textContent);
  var INICIAL = JSON.parse(document.getElementById('valores-iniciais').textContent);
  var REPAROS = DADOS.reparos;                       // {id: {codigo, nome, sigla, custo}}
  var POR_ID = {};
  DADOS.problemas.forEach(function (p) { POR_ID[p.id] = p; });

  var el = function (id) { return document.getElementById(id); };
  var brl = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
  function num(texto) {
    texto = String(texto || '').trim();
    if (!texto) return NaN;
    if (texto.indexOf(',') >= 0) texto = texto.replace(/\./g, '').replace(',', '.');
    return parseFloat(texto);
  }
  function esc(t) { var d = document.createElement('div'); d.textContent = t == null ? '' : t; return d.innerHTML; }
  function normal(t) { return String(t || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, ''); }

  // estado
  var problema = null;
  var causasSel = new Set((INICIAL.causas || []).map(String));
  var reparosSel = new Set(Object.keys(INICIAL.reparos || {}));
  var quantidades = Object.assign({}, INICIAL.reparos || {});

  // ---------------- 1. local: mostrar campos do novo local
  var selLocal = el('local');
  selLocal.addEventListener('change', function () { el('novoLocal').hidden = selLocal.value !== 'novo'; });

  // ---------------- 2. problema: busca e escolha
  var busca = el('buscaProblema');
  var lista = el('listaProblemas');

  function desenharProblemas() {
    var termo = normal(busca.value);
    var html = DADOS.problemas.filter(function (p) {
      if (!termo) return true;
      var texto = normal(p.codigo + ' ' + p.nome + ' ' + p.causas.map(function (c) { return c.descricao; }).join(' '));
      return termo.split(/\s+/).every(function (pedaco) { return texto.indexOf(pedaco) >= 0; });
    }).map(function (p) {
      var sel = problema && problema.id === p.id;
      return '<button type="button" role="option" aria-selected="' + sel + '" class="problema' + (sel ? ' problema--sel' : '') +
             '" data-id="' + p.id + '"><b>' + esc(p.codigo) + '</b> ' + esc(p.nome) +
             '<small>' + p.causas.length + ' causa' + (p.causas.length === 1 ? '' : 's') + '</small></button>';
    }).join('');
    lista.innerHTML = html || '<p class="filtro-info">Nenhum problema encontrado.</p>';
  }
  busca.addEventListener('input', desenharProblemas);
  lista.addEventListener('click', function (ev) {
    var b = ev.target.closest('button[data-id]');
    if (!b) return;
    var novo = POR_ID[b.dataset.id];
    if (problema && problema.id !== novo.id) { causasSel.clear(); reparosSel.clear(); }
    escolherProblema(novo);
  });

  function escolherProblema(p) {
    problema = p;
    el('problema').value = p ? p.id : '';
    el('problemaEscolhido').hidden = !p;
    if (p) el('problemaEscolhido').innerHTML = 'Problema: <b>' + esc(p.codigo + ' ' + p.nome) + '</b>';
    el('passoCausas').hidden = !p;
    desenharProblemas();
    desenharCausasReparos();
  }

  // ---------------- 3. causas e serviços com filtro cruzado
  function reparosDaCausa(c) { return c.reparos.map(function (r) { return String(r.id); }); }

  function desenharCausasReparos() {
    if (!problema) { atualizarTotal(); return; }
    var causas = problema.causas;

    // todos os serviços do problema, com as causas e o tipo (principal/complementar) de cada um
    var servicos = {};
    causas.forEach(function (c) {
      c.reparos.forEach(function (r) {
        var id = String(r.id);
        var s = servicos[id] || (servicos[id] = { id: id, causas: [], tipos: new Set(), rotulos: new Set() });
        if (s.causas.indexOf(c.codigo) < 0) s.causas.push(c.codigo);
        s.tipos.add(r.tipo + (r.condicao ? ': ' + r.condicao : ''));
        if (r.rotulo) s.rotulos.add(r.rotulo);
      });
    });

    // filtro: causas marcadas -> só os serviços delas; serviços marcados -> só as causas deles
    var visServ = new Set(Object.keys(servicos));
    if (causasSel.size) {
      visServ = new Set();
      causas.forEach(function (c) { if (causasSel.has(String(c.id))) reparosDaCausa(c).forEach(function (id) { visServ.add(id); }); });
    }
    reparosSel.forEach(function (id) { if (servicos[id]) visServ.add(id); });

    var visCausas = causas.filter(function (c) {
      if (causasSel.has(String(c.id))) return true;
      if (!reparosSel.size) return true;
      return reparosDaCausa(c).some(function (id) { return reparosSel.has(id); });
    });

    el('listaCausas').innerHTML = visCausas.map(function (c) {
      var id = String(c.id), marcado = causasSel.has(id);
      var qtdServ = new Set(reparosDaCausa(c)).size;
      return '<label class="marcar' + (marcado ? ' marcar--sel' : '') + '">' +
        '<input type="checkbox" name="causas" value="' + id + '"' + (marcado ? ' checked' : '') + '>' +
        '<span><b>' + esc(c.codigo) + '</b> ' + esc(c.descricao) +
        '<small>' + qtdServ + ' serviço' + (qtdServ === 1 ? '' : 's') + '</small></span></label>';
    }).join('') || '<p class="filtro-info">Este problema não tem causas cadastradas.</p>';

    var ids = Object.keys(servicos).filter(function (id) { return visServ.has(id); });
    ids.sort(function (a, b) { return (REPAROS[a].codigo || REPAROS[a].nome).localeCompare(REPAROS[b].codigo || REPAROS[b].nome, 'pt-BR'); });
    el('listaReparos').innerHTML = ids.map(function (id) {
      var r = REPAROS[id], s = servicos[id], marcado = reparosSel.has(id);
      var qtd = quantidades[id] || '';
      return '<div class="marcar marcar--reparo' + (marcado ? ' marcar--sel' : '') + '" data-reparo="' + id + '">' +
        '<label><input type="checkbox" name="reparos" value="' + id + '"' + (marcado ? ' checked' : '') + '>' +
        '<span>' + (r.codigo ? '<b>' + esc(r.codigo) + '</b> – ' : '') + esc(r.nome) +
        (s.rotulos.size ? ' <em>(' + esc(Array.from(s.rotulos).join(', ')) + ')</em>' : '') +
        '<small>' + esc(Array.from(s.tipos).join(' · ')) + ' · causas ' + esc(s.causas.join(', ')) +
        ' · ' + brl.format(parseFloat(r.custo)) + '/' + esc(r.sigla) + '</small></span></label>' +
        '<div class="qtd"' + (marcado ? '' : ' hidden') + '>' +
        '<input type="text" inputmode="decimal" name="qtd_' + id + '" value="' + esc(qtd) + '" placeholder="0,00" aria-label="Quantidade em ' + esc(r.sigla) + '">' +
        '<span class="qtd__unid">' + esc(r.sigla) + '</span>' +
        '<span class="qtd__custo" data-custo="' + id + '"></span></div></div>';
    }).join('') || '<p class="filtro-info">Nenhum serviço cadastrado para as causas escolhidas.</p>';

    var totalCausas = causas.length, totalServ = Object.keys(servicos).length;
    el('infoCausas').textContent = reparosSel.size && visCausas.length < totalCausas
      ? 'Mostrando ' + visCausas.length + ' de ' + totalCausas + ' (filtrado pelos serviços marcados)' : totalCausas + ' causas';
    el('infoReparos').textContent = causasSel.size && ids.length < totalServ
      ? 'Mostrando ' + ids.length + ' de ' + totalServ + ' (filtrado pelas causas marcadas)' : totalServ + ' serviços';

    atualizarTotal();
  }

  el('listaCausas').addEventListener('change', function (ev) {
    var cb = ev.target;
    if (cb.name !== 'causas') return;
    cb.checked ? causasSel.add(cb.value) : causasSel.delete(cb.value);
    desenharCausasReparos();
  });
  el('listaReparos').addEventListener('change', function (ev) {
    var cb = ev.target;
    if (cb.name !== 'reparos') return;
    cb.checked ? reparosSel.add(cb.value) : reparosSel.delete(cb.value);
    desenharCausasReparos();
    if (cb.checked) {
      var campo = document.querySelector('input[name="qtd_' + cb.value + '"]');
      if (campo) campo.focus();
    }
  });
  el('listaReparos').addEventListener('input', function (ev) {
    var m = /^qtd_(\d+)$/.exec(ev.target.name || '');
    if (m) { quantidades[m[1]] = ev.target.value; atualizarTotal(); }
  });
  document.querySelectorAll('[data-limpar]').forEach(function (b) {
    b.addEventListener('click', function () {
      (b.dataset.limpar === 'causas' ? causasSel : reparosSel).clear();
      desenharCausasReparos();
    });
  });

  function atualizarTotal() {
    var total = 0;
    reparosSel.forEach(function (id) {
      var r = REPAROS[id]; if (!r) return;
      var q = num(quantidades[id]);
      var custo = isNaN(q) ? 0 : Math.round(parseFloat(r.custo) * q * 100) / 100;
      total += custo;
      var cel = document.querySelector('[data-custo="' + id + '"]');
      if (cel) cel.textContent = isNaN(q) ? '' : '= ' + brl.format(custo);
    });
    el('totalOcorrencia').textContent = brl.format(total);
  }

  // ---------------- início (edição ou volta com erro)
  if (INICIAL.problema && POR_ID[INICIAL.problema]) escolherProblema(POR_ID[INICIAL.problema]);
  else desenharProblemas();
})();
