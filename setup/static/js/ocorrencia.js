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
  var escolhaPacote = {};   // {solucao_id: [reparo escolhido em cada grupo]}

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

    // causas: se há serviços marcados, mostra só as causas que eles resolvem
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

    // serviços do problema: soluções com "+" viram um PACOTE (escolhidos juntos);
    // as demais aparecem reparo a reparo
    var causasVisiveisServ = causasSel.size ? causas.filter(function (c) { return causasSel.has(String(c.id)); }) : causas;
    var individuais = {}, pacotes = {}, todosIds = new Set();
    causas.forEach(function (c) {
      var visivel = causasVisiveisServ.indexOf(c) >= 0;
      (c.solucoes || []).forEach(function (sol) {
        var tipo = sol.tipo + (sol.condicao ? ': ' + sol.condicao : '');
        if (sol.grupos.length > 1) {
          todosIds.add('p' + sol.id);
          var pk = pacotes[sol.id] || (pacotes[sol.id] = { sol: sol, tipo: tipo, causas: [], visivel: false });
          if (pk.causas.indexOf(c.codigo) < 0) pk.causas.push(c.codigo);
          pk.visivel = pk.visivel || visivel;
        } else {
          sol.grupos.forEach(function (g) { g.forEach(function (it) {
            var id = String(it.id);
            todosIds.add('r' + id);
            var s = individuais[id] || (individuais[id] = { id: id, causas: [], tipos: new Set(), rotulos: new Set(), visivel: false });
            if (s.causas.indexOf(c.codigo) < 0) s.causas.push(c.codigo);
            s.tipos.add(tipo);
            if (it.rotulo) s.rotulos.add(it.rotulo);
            s.visivel = s.visivel || visivel;
          }); });
        }
      });
    });

    // escolha dentro de cada grupo do pacote (quando o grupo tem alternativas)
    Object.keys(pacotes).forEach(function (sid) {
      var esc = escolhaPacote[sid] || (escolhaPacote[sid] = []);
      pacotes[sid].sol.grupos.forEach(function (g, i) {
        var marcado = g.filter(function (it) { return reparosSel.has(String(it.id)); })[0];
        if (marcado) esc[i] = String(marcado.id);
        else if (!esc[i]) esc[i] = String(g[0].id);
      });
      pacotes[sid].marcado = esc.every(function (id) { return reparosSel.has(id); });
      if (pacotes[sid].marcado) pacotes[sid].visivel = true;
    });
    Object.keys(individuais).forEach(function (id) { if (reparosSel.has(id)) individuais[id].visivel = true; });

    var rotuloReparo = function (id) {
      var r = REPAROS[id];
      return (r.codigo ? '<b>' + esc(r.codigo) + '</b> – ' : '') + esc(r.nome);
    };
    var jaComQtd = new Set();
    var campoQtd = function (id) {
      var r = REPAROS[id];
      jaComQtd.add(id);
      return '<div class="qtd">' +
        '<input type="text" inputmode="decimal" name="qtd_' + id + '" value="' + esc(quantidades[id] || '') +
        '" placeholder="0,00" aria-label="Quantidade em ' + esc(r.sigla) + '">' +
        '<span class="qtd__unid">' + esc(r.sigla) + '</span>' +
        '<span class="qtd__custo" data-custo="' + id + '"></span></div>';
    };

    var htmlPacotes = Object.keys(pacotes).filter(function (sid) { return pacotes[sid].visivel; }).map(function (sid) {
      var pk = pacotes[sid], sol = pk.sol, escolha = escolhaPacote[sid];
      var titulo = sol.grupos.map(function (g) {
        return g.map(function (it) { return rotuloReparo(String(it.id)) + (it.rotulo ? ' <em>(' + esc(it.rotulo) + ')</em>' : ''); })
                .join(' <span class="ou">ou</span> ');
      }).join(' <span class="mais">+</span> ');
      var custos = sol.grupos.map(function (g, i) {
        var r = REPAROS[escolha[i]]; return brl.format(parseFloat(r.custo)) + '/' + esc(r.sigla);
      }).join(' + ');
      var corpo = '';
      if (pk.marcado) {
        corpo = sol.grupos.map(function (g, i) {
          var radios = g.length > 1 ? '<div class="alternativas">' + g.map(function (it) {
            var id = String(it.id);
            return '<label><input type="radio" name="esc_' + sid + '_' + i + '" value="' + id + '" data-pacote="' + sid +
              '" data-grupo="' + i + '"' + (escolha[i] === id ? ' checked' : '') + '> ' +
              esc(it.rotulo || REPAROS[id].codigo || REPAROS[id].nome) + '</label>';
          }).join('') + '</div>' : '';
          var id = escolha[i];
          return '<div class="pacote__item">' + radios +
            '<p class="pacote__nome">' + rotuloReparo(id) + '</p>' +
            '<input type="hidden" name="reparos" value="' + id + '">' +
            (jaComQtd.has(id) ? '' : campoQtd(id)) + '</div>';
        }).join('');
      }
      return '<div class="marcar marcar--reparo marcar--pacote' + (pk.marcado ? ' marcar--sel' : '') + '">' +
        '<label><input type="checkbox" data-pacote-check="' + sid + '"' + (pk.marcado ? ' checked' : '') + '>' +
        '<span><span class="pacote__selo">juntos</span> ' + titulo +
        '<small>' + esc(pk.tipo) + ' · causas ' + esc(pk.causas.join(', ')) + ' · ' + custos + '</small></span></label>' +
        corpo + '</div>';
    });

    var ids = Object.keys(individuais).filter(function (id) { return individuais[id].visivel; });
    ids.sort(function (a, b) { return (REPAROS[a].codigo || REPAROS[a].nome).localeCompare(REPAROS[b].codigo || REPAROS[b].nome, 'pt-BR'); });
    var htmlIndividuais = ids.map(function (id) {
      var r = REPAROS[id], s = individuais[id], marcado = reparosSel.has(id);
      var qtd = '';
      if (marcado) qtd = jaComQtd.has(id) ? '<p class="filtro-info">Quantidade informada no pacote.</p>' : campoQtd(id);
      return '<div class="marcar marcar--reparo' + (marcado ? ' marcar--sel' : '') + '">' +
        '<label><input type="checkbox" name="reparos" value="' + id + '"' + (marcado ? ' checked' : '') + '>' +
        '<span>' + rotuloReparo(id) +
        (s.rotulos.size ? ' <em>(' + esc(Array.from(s.rotulos).join(', ')) + ')</em>' : '') +
        '<small>' + esc(Array.from(s.tipos).join(' · ')) + ' · causas ' + esc(s.causas.join(', ')) +
        ' · ' + brl.format(parseFloat(r.custo)) + '/' + esc(r.sigla) + '</small></span></label>' + qtd + '</div>';
    });

    // pacotes primeiro (os campos de quantidade deles têm prioridade)
    el('listaReparos').innerHTML = htmlPacotes.concat(htmlIndividuais).join('') ||
      '<p class="filtro-info">Nenhum serviço cadastrado para as causas escolhidas.</p>';

    var mostrados = htmlPacotes.length + htmlIndividuais.length, totalServ = todosIds.size;
    var totalCausas = causas.length;
    el('infoCausas').textContent = reparosSel.size && visCausas.length < totalCausas
      ? 'Mostrando ' + visCausas.length + ' de ' + totalCausas + ' (filtrado pelos serviços marcados)' : totalCausas + ' causas';
    el('infoReparos').textContent = causasSel.size && mostrados < totalServ
      ? 'Mostrando ' + mostrados + ' de ' + totalServ + ' (filtrado pelas causas marcadas)' : totalServ + ' opções';

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
    if (cb.dataset.pacoteCheck) {                       // marca/desmarca o pacote inteiro
      var escolha = escolhaPacote[cb.dataset.pacoteCheck] || [];
      escolha.forEach(function (id) { cb.checked ? reparosSel.add(id) : reparosSel.delete(id); });
      desenharCausasReparos();
      if (cb.checked) {
        var primeiro = document.querySelector('input[name="qtd_' + escolha[0] + '"]');
        if (primeiro) primeiro.focus();
      }
      return;
    }
    if (cb.type === 'radio' && cb.dataset.pacote) {     // troca a alternativa dentro do pacote
      var lista = escolhaPacote[cb.dataset.pacote], i = +cb.dataset.grupo;
      reparosSel.delete(lista[i]);
      lista[i] = cb.value;
      reparosSel.add(cb.value);
      desenharCausasReparos();
      return;
    }
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
