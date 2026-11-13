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

  // ---------------- estado
  // O que o engenheiro marcou: reparos avulsos e pacotes (soluções com "+").
  // Os reparos enviados são a união dos dois; a quantidade é uma por reparo.
  var problema = null;
  var causasSel = new Set((INICIAL.causas || []).map(String));
  var avulsosSel = new Set();
  var pacotesSel = new Set();
  var escolhaPacote = {};   // {chave do pacote: [reparo escolhido em cada grupo]}
  var quantidades = Object.assign({}, INICIAL.reparos || {});
  var restaurar = Object.keys(INICIAL.reparos || {});   // edição / volta com erro

  function reparosEscolhidos() {
    var todos = new Set(avulsosSel);
    pacotesSel.forEach(function (chave) { (escolhaPacote[chave] || []).forEach(function (id) { todos.add(id); }); });
    return todos;
  }

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
    if (problema && problema.id !== novo.id) {
      causasSel.clear(); avulsosSel.clear(); pacotesSel.clear(); escolhaPacote = {};
    }
    escolherProblema(novo);
  });

  function escolherProblema(p) {
    problema = p;
    el('problema').value = p ? p.id : '';
    el('problemaEscolhido').hidden = !p;
    if (p) el('problemaEscolhido').innerHTML = 'Problema: <b>' + esc(p.codigo + ' ' + p.nome) + '</b>';
    el('passoCausas').hidden = !p;
    if (p && restaurar.length) { restaurarEscolhas(); restaurar = []; }
    desenharProblemas();
    desenharCausasReparos();
  }

  // ---------------- 3. causas, serviços principais e complementares
  function reparosDaCausa(c) { return c.reparos.map(function (r) { return String(r.id); }); }

  // opções de cada coluna: pacotes (soluções com "+", sem repetir) e reparos avulsos
  function montarColunas(causasFiltro) {
    var colunas = { 'Principal': { avulsos: {}, pacotes: {}, total: new Set() },
                    'Complementar': { avulsos: {}, pacotes: {}, total: new Set() } };
    problema.causas.forEach(function (c) {
      var visivel = causasFiltro.indexOf(c) >= 0;
      (c.solucoes || []).forEach(function (sol) {
        var col = colunas[sol.tipo] || colunas['Principal'];
        var cond = sol.condicao || '';
        if (sol.grupos.length > 1) {
          var chave = sol.grupos.map(function (g) {
            return g.map(function (it) { return it.id; }).sort().join('_');
          }).join('-');
          col.total.add('p' + chave);
          var pk = col.pacotes[chave] || (col.pacotes[chave] = { chave: chave, grupos: sol.grupos, causas: [], conds: new Set(), visivel: false });
          if (pk.causas.indexOf(c.codigo) < 0) pk.causas.push(c.codigo);
          if (cond) pk.conds.add(cond);
          pk.visivel = pk.visivel || visivel;
        } else {
          sol.grupos.forEach(function (g) { g.forEach(function (it) {
            var id = String(it.id);
            col.total.add('r' + id);
            var s = col.avulsos[id] || (col.avulsos[id] = { id: id, causas: [], conds: new Set(), rotulos: new Set(), visivel: false });
            if (s.causas.indexOf(c.codigo) < 0) s.causas.push(c.codigo);
            if (cond) s.conds.add(cond);
            if (it.rotulo) s.rotulos.add(it.rotulo);
            s.visivel = s.visivel || visivel;
          }); });
        }
      });
    });
    return colunas;
  }

  // ao editar: reconstrói pacotes e avulsos a partir dos reparos salvos (pacotes maiores primeiro)
  function restaurarEscolhas() {
    var resto = new Set(restaurar.map(String));
    // considera só os pacotes das causas marcadas (se houver)
    var filtro = causasSel.size ? problema.causas.filter(function (c) { return causasSel.has(String(c.id)); }) : problema.causas;
    var colunas = montarColunas(filtro);
    var pacotes = [];
    ['Principal', 'Complementar'].forEach(function (t) {
      Object.keys(colunas[t].pacotes).forEach(function (k) {
        if (colunas[t].pacotes[k].visivel) pacotes.push(colunas[t].pacotes[k]);
      });
    });
    pacotes.sort(function (a, b) { return b.grupos.length - a.grupos.length; });
    pacotes.forEach(function (pk) {
      var escolha = pk.grupos.map(function (g) {
        var achado = g.filter(function (it) { return resto.has(String(it.id)); })[0];
        return achado ? String(achado.id) : null;
      });
      if (escolha.every(Boolean)) {
        pacotesSel.add(pk.chave);
        escolhaPacote[pk.chave] = escolha;
        escolha.forEach(function (id) { resto.delete(id); });
      }
    });
    resto.forEach(function (id) { avulsosSel.add(id); });
  }

  function desenharCausasReparos() {
    if (!problema) { atualizarTotal(); return; }
    var causas = problema.causas;
    var escolhidos = reparosEscolhidos();

    // causas: se há serviços marcados, mostra só as causas que eles resolvem
    var visCausas = causas.filter(function (c) {
      if (causasSel.has(String(c.id))) return true;
      if (!escolhidos.size) return true;
      return reparosDaCausa(c).some(function (id) { return escolhidos.has(id); });
    });
    el('listaCausas').innerHTML = visCausas.map(function (c) {
      var id = String(c.id), marcado = causasSel.has(id);
      var qtdServ = new Set(reparosDaCausa(c)).size;
      return '<label class="marcar' + (marcado ? ' marcar--sel' : '') + '">' +
        '<input type="checkbox" name="causas" value="' + id + '"' + (marcado ? ' checked' : '') + '>' +
        '<span><b>' + esc(c.codigo) + '</b> ' + esc(c.descricao) +
        '<small>' + qtdServ + ' serviço' + (qtdServ === 1 ? '' : 's') + '</small></span></label>';
    }).join('') || '<p class="filtro-info">Este problema não tem causas cadastradas.</p>';
    el('infoCausas').textContent = escolhidos.size && visCausas.length < causas.length
      ? 'Mostrando ' + visCausas.length + ' de ' + causas.length + ' (filtrado pelos serviços marcados)' : causas.length + ' causas';

    var causasFiltro = causasSel.size ? causas.filter(function (c) { return causasSel.has(String(c.id)); }) : causas;
    var colunas = montarColunas(causasFiltro);
    var comCampo = new Set();   // cada reparo tem um só campo de quantidade

    var rotuloReparo = function (id) {
      var r = REPAROS[id];
      return (r.codigo ? '<b>' + esc(r.codigo) + '</b> – ' : '') + esc(r.nome);
    };
    var campoQtd = function (id) {
      if (comCampo.has(id)) return '<p class="filtro-info">Quantidade informada em outra opção marcada.</p>';
      comCampo.add(id);
      var r = REPAROS[id];
      return '<div class="qtd">' +
        '<input type="text" inputmode="decimal" name="qtd_' + id + '" value="' + esc(quantidades[id] || '') +
        '" placeholder="0,00" aria-label="Quantidade em ' + esc(r.sigla) + '">' +
        '<span class="qtd__unid">' + esc(r.sigla) + '</span>' +
        '<span class="qtd__custo" data-custo="' + id + '"></span></div>';
    };
    var detalhe = function (conds, causasLista, custos) {
      return '<small>' + (conds.size ? esc(Array.from(conds).join(' · ')) + ' · ' : '') +
        'causas ' + esc(causasLista.join(', ')) + ' · ' + custos + '</small>';
    };

    function desenharColuna(tipo, idLista, idInfo) {
      var col = colunas[tipo];

      var htmlPacotes = Object.keys(col.pacotes).map(function (chave) {
        var pk = col.pacotes[chave], marcado = pacotesSel.has(chave);
        if (!pk.visivel && !marcado) return '';
        var escolha = escolhaPacote[chave] || (escolhaPacote[chave] = pk.grupos.map(function (g) { return String(g[0].id); }));
        var titulo = pk.grupos.map(function (g) {
          return g.map(function (it) { return rotuloReparo(String(it.id)) + (it.rotulo ? ' <em>(' + esc(it.rotulo) + ')</em>' : ''); })
                  .join(' <span class="ou">ou</span> ');
        }).join(' <span class="mais">+</span> ');
        var custos = pk.grupos.map(function (g, i) {
          var r = REPAROS[escolha[i]]; return brl.format(parseFloat(r.custo)) + '/' + esc(r.sigla);
        }).join(' + ');
        var corpo = !marcado ? '' : pk.grupos.map(function (g, i) {
          var radios = g.length > 1 ? '<div class="alternativas">' + g.map(function (it) {
            var id = String(it.id);
            return '<label><input type="radio" name="esc_' + chave + '_' + i + '" value="' + id + '" data-pacote="' + chave +
              '" data-grupo="' + i + '"' + (escolha[i] === id ? ' checked' : '') + '> ' +
              esc(it.rotulo || REPAROS[id].codigo || REPAROS[id].nome) + '</label>';
          }).join('') + '</div>' : '';
          var id = escolha[i];
          return '<div class="pacote__item">' + radios +
            '<p class="pacote__nome">' + rotuloReparo(id) + '</p>' +
            '<input type="hidden" name="reparos" value="' + id + '">' + campoQtd(id) + '</div>';
        }).join('');
        return '<div class="marcar marcar--reparo marcar--pacote' + (marcado ? ' marcar--sel' : '') + '">' +
          '<label><input type="checkbox" data-pacote-check="' + chave + '"' + (marcado ? ' checked' : '') + '>' +
          '<span><span class="pacote__selo">juntos</span> ' + titulo +
          detalhe(pk.conds, pk.causas, custos) + '</span></label>' + corpo + '</div>';
      }).filter(Boolean);

      var ids = Object.keys(col.avulsos).filter(function (id) { return col.avulsos[id].visivel || avulsosSel.has(id); });
      ids.sort(function (a, b) { return (REPAROS[a].codigo || REPAROS[a].nome).localeCompare(REPAROS[b].codigo || REPAROS[b].nome, 'pt-BR'); });
      var htmlAvulsos = ids.map(function (id) {
        var r = REPAROS[id], s = col.avulsos[id], marcado = avulsosSel.has(id);
        return '<div class="marcar marcar--reparo' + (marcado ? ' marcar--sel' : '') + '">' +
          '<label><input type="checkbox" name="reparos" value="' + id + '" data-avulso="1"' + (marcado ? ' checked' : '') + '>' +
          '<span>' + rotuloReparo(id) +
          (s.rotulos.size ? ' <em>(' + esc(Array.from(s.rotulos).join(', ')) + ')</em>' : '') +
          detalhe(s.conds, s.causas, brl.format(parseFloat(r.custo)) + '/' + esc(r.sigla)) +
          '</span></label>' + (marcado ? campoQtd(id) : '') + '</div>';
      });

      var vazio = tipo === 'Complementar' ? 'Nenhum complementar para as causas escolhidas.' : 'Nenhum serviço para as causas escolhidas.';
      el(idLista).innerHTML = htmlPacotes.concat(htmlAvulsos).join('') || '<p class="filtro-info">' + vazio + '</p>';
      var mostrados = htmlPacotes.length + htmlAvulsos.length, total = col.total.size;
      el(idInfo).textContent = causasSel.size && mostrados < total
        ? 'Mostrando ' + mostrados + ' de ' + total + ' (filtrado pelas causas)' : total + ' opç' + (total === 1 ? 'ão' : 'ões');
    }

    desenharColuna('Principal', 'listaReparos', 'infoReparos');
    desenharColuna('Complementar', 'listaComplementares', 'infoComplementares');
    atualizarTotal();
  }

  el('listaCausas').addEventListener('change', function (ev) {
    var cb = ev.target;
    if (cb.name !== 'causas') return;
    cb.checked ? causasSel.add(cb.value) : causasSel.delete(cb.value);
    desenharCausasReparos();
  });

  function focar(id) {
    var campo = document.querySelector('input[name="qtd_' + id + '"]');
    if (campo) campo.focus();
  }
  function aoMarcarServico(ev) {
    var cb = ev.target;
    if (cb.dataset.pacoteCheck) {                       // pacote inteiro
      var chave = cb.dataset.pacoteCheck;
      cb.checked ? pacotesSel.add(chave) : pacotesSel.delete(chave);
      desenharCausasReparos();
      if (cb.checked) focar((escolhaPacote[chave] || [])[0]);
      return;
    }
    if (cb.type === 'radio' && cb.dataset.pacote) {     // alternativa dentro do pacote
      escolhaPacote[cb.dataset.pacote][+cb.dataset.grupo] = cb.value;
      desenharCausasReparos();
      return;
    }
    if (!cb.dataset.avulso) return;                     // reparo avulso
    cb.checked ? avulsosSel.add(cb.value) : avulsosSel.delete(cb.value);
    desenharCausasReparos();
    if (cb.checked) focar(cb.value);
  }
  function aoDigitarQuantidade(ev) {
    var m = /^qtd_(\d+)$/.exec(ev.target.name || '');
    if (m) { quantidades[m[1]] = ev.target.value; atualizarTotal(); }
  }
  ['listaReparos', 'listaComplementares'].forEach(function (id) {
    el(id).addEventListener('change', aoMarcarServico);
    el(id).addEventListener('input', aoDigitarQuantidade);
  });

  // "limpar" de cada coluna
  document.querySelectorAll('[data-limpar]').forEach(function (b) {
    b.addEventListener('click', function () {
      if (b.dataset.limpar === 'causas') {
        causasSel.clear();
      } else {
        var lista = el(b.dataset.limpar === 'complementares' ? 'listaComplementares' : 'listaReparos');
        lista.querySelectorAll('[data-pacote-check]').forEach(function (i) { pacotesSel.delete(i.dataset.pacoteCheck); });
        lista.querySelectorAll('[data-avulso]').forEach(function (i) { avulsosSel.delete(i.value); });
      }
      desenharCausasReparos();
    });
  });

  function atualizarTotal() {
    var total = 0;
    reparosEscolhidos().forEach(function (id) {
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
