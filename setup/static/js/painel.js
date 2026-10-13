/* SGE PRO – Painel de análise integrada (dados simulados) */
(function () {
  'use strict';

  var DADOS = JSON.parse(document.getElementById('dados-painel').textContent);
  var ESCOLAS = DADOS.escolas;
  var NCS = DADOS.ncs;
  var CATEGORIAS = DADOS.categorias;
  var POR_ID = {};
  ESCOLAS.forEach(function (e) { POR_ID[e.id] = e; });

  // posição fixa no ranking de prioridade (rede toda)
  ESCOLAS.slice().sort(function (a, b) { return b.prioridade - a.prioridade; })
    .forEach(function (e, i) { e.pos = i + 1; });

  var COR = {
    'Mínimo': '#c0392b', 'Médio': '#e0a030', 'Elevado': '#2e8b57',
    'Alta': '#c0392b', 'Média': '#e8772e', 'Baixa': '#e8c547',
    'Aberta': '#e8772e', 'Em andamento': '#6b7a8f', 'Resolvida': '#2e8b57',
    base: '#3b4a5e', destaque: '#e8772e', claro: '#c9d1dc'
  };

  var estado = { escola: '', categoria: '', bairro: '', faixa: '', statusNc: 'abertas', ordem: 'prioridade', asc: false };

  // ---------- formatação ----------
  var fmtInt = new Intl.NumberFormat('pt-BR');
  var fmtDec = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 3, maximumFractionDigits: 3 });
  var fmtBRL = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
  function brlCurto(v) {
    if (v >= 1e6) return 'R$ ' + (v / 1e6).toLocaleString('pt-BR', { maximumFractionDigits: 1, minimumFractionDigits: 1 }) + ' mi';
    if (v >= 1e3) return 'R$ ' + Math.round(v / 1e3).toLocaleString('pt-BR') + ' mil';
    return fmtBRL.format(v);
  }
  function esc(t) { var d = document.createElement('div'); d.textContent = t == null ? '' : t; return d.innerHTML; }
  function contar(lista, chave) {
    var r = {}; lista.forEach(function (x) { r[x[chave]] = (r[x[chave]] || 0) + 1; }); return r;
  }
  function somar(lista, chave, campo) {
    var r = {}; lista.forEach(function (x) { r[x[chave]] = (r[x[chave]] || 0) + x[campo]; }); return r;
  }
  function el(id) { return document.getElementById(id); }

  // ---------- recortes conforme os filtros ----------
  function escolasFiltradas() {
    return ESCOLAS.filter(function (e) {
      return (!estado.escola || e.id === estado.escola) &&
             (!estado.bairro || e.bairro === estado.bairro) &&
             (!estado.faixa || e.faixa === estado.faixa);
    });
  }
  function ncsDe(escolas, usarCategoria) {
    var ids = {}; escolas.forEach(function (e) { ids[e.id] = true; });
    return NCS.filter(function (n) {
      return ids[n.escola] && (!usarCategoria || !estado.categoria || n.categoria === estado.categoria);
    });
  }
  function abertas(lista) { return lista.filter(function (n) { return n.status !== 'Resolvida'; }); }

  // ---------- filtros (preenchimento) ----------
  var selEscola = el('fEscola'), selCat = el('fCategoria'), selBairro = el('fBairro');
  ESCOLAS.slice().sort(function (a, b) { return a.nome.localeCompare(b.nome, 'pt-BR'); }).forEach(function (e) {
    selEscola.add(new Option(e.nome + ' – ' + e.bairro, e.id));
  });
  CATEGORIAS.forEach(function (c) { selCat.add(new Option(c, c)); });
  Object.keys(contar(ESCOLAS, 'bairro')).sort(function (a, b) { return a.localeCompare(b, 'pt-BR'); })
    .forEach(function (b) { selBairro.add(new Option(b, b)); });

  selEscola.addEventListener('change', function () { definir({ escola: selEscola.value }); });
  selCat.addEventListener('change', function () { definir({ categoria: selCat.value }); });
  selBairro.addEventListener('change', function () { definir({ bairro: selBairro.value }); });
  el('fFaixa').addEventListener('click', function (ev) {
    var b = ev.target.closest('button'); if (b) definir({ faixa: b.dataset.faixa });
  });
  el('fStatus').addEventListener('click', function (ev) {
    var b = ev.target.closest('button'); if (b) { estado.statusNc = b.dataset.status; desenharFicha(); }
  });
  el('limpar').addEventListener('click', function () { definir({ escola: '', categoria: '', bairro: '', faixa: '' }); });
  el('voltarRede').addEventListener('click', function () { definir({ escola: '' }); });

  function definir(mudancas) {
    Object.keys(mudancas).forEach(function (k) { estado[k] = mudancas[k]; });
    // ao escolher uma escola, os filtros de bairro/faixa não podem escondê-la
    if (mudancas.escola) { estado.bairro = ''; estado.faixa = ''; }
    atualizarUrl();
    desenhar();
    if (mudancas.escola) el('ficha').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function atualizarUrl() {
    var p = new URLSearchParams();
    ['escola', 'categoria', 'bairro', 'faixa'].forEach(function (k) { if (estado[k]) p.set(k, estado[k]); });
    var q = p.toString();
    history.replaceState(null, '', location.pathname + (q ? '?' + q : ''));
  }
  (function lerUrl() {
    var p = new URLSearchParams(location.search);
    if (POR_ID[p.get('escola')]) estado.escola = p.get('escola');
    if (CATEGORIAS.indexOf(p.get('categoria')) >= 0) estado.categoria = p.get('categoria');
    if (p.get('bairro')) estado.bairro = p.get('bairro');
    if (['Mínimo', 'Médio', 'Elevado'].indexOf(p.get('faixa')) >= 0) estado.faixa = p.get('faixa');
  })();

  // ---------- gráficos ----------
  Chart.defaults.font.family = '"Barlow", "Segoe UI", Arial, sans-serif';
  Chart.defaults.color = '#5b6472';
  Chart.defaults.plugins.legend.display = false;
  Chart.defaults.animation.duration = 350;

  var rotuloFim = {
    id: 'rotuloFim',
    afterDatasetsDraw: function (chart, args, opts) {
      if (!opts || !opts.formato) return;
      var ctx = chart.ctx; ctx.save();
      ctx.font = '600 11px ' + Chart.defaults.font.family; ctx.fillStyle = '#3b4a5e'; ctx.textBaseline = 'middle';
      chart.getDatasetMeta(0).data.forEach(function (bar, i) {
        var v = chart.data.datasets[0].data[i];
        if (v) ctx.fillText(opts.formato(v), bar.x + 5, bar.y);
      });
      ctx.restore();
    }
  };
  var centroRosca = {
    id: 'centroRosca',
    afterDraw: function (chart, args, opts) {
      if (!opts || opts.texto == null) return;
      var a = chart.chartArea, ctx = chart.ctx; ctx.save();
      ctx.font = '700 16px ' + Chart.defaults.font.family; ctx.fillStyle = '#262c35';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(opts.texto, (a.left + a.right) / 2, (a.top + a.bottom) / 2);
      ctx.restore();
    }
  };

  function barrasH(id, formato, aoClicar) {
    return new Chart(el(id), {
      type: 'bar',
      data: { labels: [], datasets: [{ data: [], backgroundColor: [], borderRadius: 2, barPercentage: 0.75, categoryPercentage: 0.9, maxBarThickness: 22 }] },
      options: {
        indexAxis: 'y', maintainAspectRatio: false,
        layout: { padding: { right: 64 } },
        scales: {
          x: { display: false, beginAtZero: true, grace: '4%' },
          y: { grid: { display: false }, ticks: { autoSkip: false, font: { size: 11 } } }
        },
        plugins: {
          rotuloFim: { formato: formato },
          tooltip: { callbacks: { label: function (c) { return ' ' + formato(c.raw); } } }
        },
        onClick: function (ev, itens, chart) { if (itens.length) aoClicar(chart.data.labels[itens[0].index], itens[0].index); },
        onHover: function (ev, itens) { ev.native.target.style.cursor = itens.length ? 'pointer' : 'default'; }
      },
      plugins: [rotuloFim]
    });
  }
  function rosca(id) {
    return new Chart(el(id), {
      type: 'doughnut',
      data: { labels: [], datasets: [{ data: [], backgroundColor: [], borderWidth: 2, borderColor: '#fff' }] },
      options: { maintainAspectRatio: false, cutout: '62%', plugins: { centroRosca: {}, tooltip: { enabled: true } } },
      plugins: [centroRosca]
    });
  }

  var gCategorias = barrasH('gCategorias', function (v) { return fmtInt.format(v); }, function (cat) {
    definir({ categoria: estado.categoria === cat ? '' : cat });
  });
  var topIds = [];
  var gTop = barrasH('gTop', function (v) { return fmtInt.format(v); }, function (rotulo, i) {
    if (!estado.escola && topIds[i]) definir({ escola: topIds[i] });
  });
  var gCusto = barrasH('gCusto', brlCurto, function (cat) {
    definir({ categoria: estado.categoria === cat ? '' : cat });
  });
  var gFaixa = rosca('gFaixa'), gGravidade = rosca('gGravidade'), gStatus = rosca('gStatus');

  function corCategoria(cat) {
    if (estado.categoria) return cat === estado.categoria ? COR.destaque : COR.claro;
    return cat === 'Acessibilidade' ? COR.destaque : COR.base;
  }

  // ---------- mapa ----------
  var mapa = L.map('mapa', { scrollWheelZoom: false, zoomControl: true });
  L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 16, attribution: 'Base &copy; Esri'
  }).addTo(mapa);
  var circulos = {};
  ESCOLAS.forEach(function (e) {
    var c = L.circleMarker([e.lat, e.lng], { color: '#fff', weight: 1.5, fillColor: COR[e.faixa], fillOpacity: 0.85, radius: 8 })
      .addTo(mapa)
      .on('click', function () { definir({ escola: estado.escola === e.id ? '' : e.id }); });
    circulos[e.id] = c;
  });
  var limitesRede = L.latLngBounds(ESCOLAS.map(function (e) { return [e.lat, e.lng]; }));
  function enquadrarRede() { mapa.invalidateSize(); mapa.fitBounds(limitesRede, { padding: [16, 16] }); }
  mapa.fitBounds(limitesRede, { padding: [16, 16] });
  window.addEventListener('load', function () { if (!estado.escola) enquadrarRede(); });
  document.getElementById('menuBtn') && document.getElementById('menuBtn').addEventListener('click', function () {
    setTimeout(function () { mapa.invalidateSize(); }, 300);
  });

  var mapaFocado = false;

  // ---------- desenho ----------
  function desenhar() {
    var escolas = escolasFiltradas();
    var todasNcs = ncsDe(escolas, true);        // respeita categoria
    var ab = abertas(todasNcs);
    var abSemCat = abertas(ncsDe(escolas, false));
    var uma = estado.escola ? POR_ID[estado.escola] : null;

    // controles
    selEscola.value = estado.escola; selCat.value = estado.categoria; selBairro.value = estado.bairro;
    document.querySelectorAll('#fFaixa button').forEach(function (b) {
      b.setAttribute('aria-pressed', String(b.dataset.faixa === estado.faixa));
    });
    el('limpar').hidden = !(estado.escola || estado.categoria || estado.bairro || estado.faixa);

    // indicadores
    var custo = ab.reduce(function (s, n) { return s + n.custo; }, 0);
    var acess = abSemCat.filter(function (n) { return n.categoria === 'Acessibilidade'; });
    var custoAcess = acess.reduce(function (s, n) { return s + n.custo; }, 0);
    var mediaInd = escolas.length ? escolas.reduce(function (s, e) { return s + e.indice; }, 0) / escolas.length : 0;
    var nTese = escolas.filter(function (e) { return e.tese; }).length;

    el('kEscolas').textContent = fmtInt.format(escolas.length);
    el('kEscolasSub').textContent = nTese ? nTese + ' com índice real da tese' : 'dados simulados';
    el('kNc').textContent = fmtInt.format(ab.length);
    el('kNcSub').textContent = estado.categoria ? 'abertas ou em andamento · ' + estado.categoria : 'abertas ou em andamento';
    el('kAcess').textContent = fmtInt.format(acess.length);
    el('kIndiceRot').textContent = uma ? 'Índice da escola' : 'Índice médio';
    el('kIndice').textContent = escolas.length ? fmtDec.format(mediaInd) : '—';
    el('kIndiceSub').textContent = uma ? 'faixa ' + uma.faixa.toLowerCase() : '0 a 1 · médio de 0,50 a 0,74';
    el('kCusto').textContent = fmtBRL.format(custo);
    el('kCustoSub').textContent = estado.categoria ? 'NC abertas de ' + estado.categoria.toLowerCase() : 'soma das NC abertas';

    // frase-resumo
    var r;
    if (!escolas.length) {
      r = 'Nenhuma escola atende a esses filtros.';
    } else if (uma) {
      var altas = ab.filter(function (n) { return n.gravidade === 'Alta'; }).length;
      r = '<b>' + esc(uma.nome) + '</b> está na faixa <b>' + uma.faixa.toLowerCase() + '</b> (índice ' + fmtDec.format(uma.indice) +
          ') e é a <b>' + uma.pos + 'ª</b> no ranking de prioridade. Tem ' + ab.length + ' NC abertas' +
          (estado.categoria ? ' de ' + esc(estado.categoria.toLowerCase()) : '') + ', ' + altas +
          ' de gravidade alta; corrigir custaria <b>' + brlCurto(custo) + '</b>.';
    } else {
      var nMin = escolas.filter(function (e) { return e.faixa === 'Mínimo'; }).length;
      r = (nMin === 1 ? '1 escola está' : nMin + ' escolas estão') + ' na faixa mínima de desempenho. ' +
          'Corrigir as não conformidades abertas' + (estado.categoria ? ' de ' + esc(estado.categoria.toLowerCase()) : '') +
          ' custaria <b>' + brlCurto(custo) + '</b>' +
          (estado.categoria ? '.' : ', dos quais <b>' + brlCurto(custoAcess) + '</b> em acessibilidade.');
    }
    el('resumo').innerHTML = r;

    // tipo de NC (sempre todas as categorias; a escolhida fica em destaque)
    var porCat = contar(abSemCat, 'categoria');
    var cats = CATEGORIAS.slice().sort(function (a, b) { return (porCat[b] || 0) - (porCat[a] || 0); });
    gCategorias.data.labels = cats;
    gCategorias.data.datasets[0].data = cats.map(function (c) { return porCat[c] || 0; });
    gCategorias.data.datasets[0].backgroundColor = cats.map(corCategoria);
    gCategorias.update();

    // custo por categoria
    var custoCat = somar(abSemCat, 'categoria', 'custo');
    var catsC = CATEGORIAS.slice().sort(function (a, b) { return (custoCat[b] || 0) - (custoCat[a] || 0); });
    gCusto.data.labels = catsC;
    gCusto.data.datasets[0].data = catsC.map(function (c) { return Math.round(custoCat[c] || 0); });
    gCusto.data.datasets[0].backgroundColor = catsC.map(function (c) {
      return estado.categoria ? corCategoria(c) : (c === 'Acessibilidade' ? COR.destaque : '#6b7a8f');
    });
    gCusto.update();

    // top 10 escolas, ou NC por local quando há uma escola escolhida
    if (uma) {
      var porLocal = contar(ab, 'local');
      var locais = Object.keys(porLocal).sort(function (a, b) { return porLocal[b] - porLocal[a]; }).slice(0, 10);
      el('tTop').textContent = 'NC abertas por local da escola';
      el('tTopSub').textContent = 'Ambientes com mais problemas' + (estado.categoria ? ' · ' + estado.categoria : '');
      topIds = [];
      gTop.data.labels = locais;
      gTop.data.datasets[0].data = locais.map(function (l) { return porLocal[l]; });
      gTop.data.datasets[0].backgroundColor = COR.base;
    } else {
      var porEscola = contar(ab, 'escola');
      var top = escolas.slice().sort(function (a, b) { return (porEscola[b.id] || 0) - (porEscola[a.id] || 0); }).slice(0, 10);
      el('tTop').textContent = 'NC abertas por escola (top 10)';
      el('tTopSub').textContent = 'Onde estão mais problemas acumulados · clique para ver a escola';
      topIds = top.map(function (e) { return e.id; });
      gTop.data.labels = top.map(function (e) { return e.curto; });
      gTop.data.datasets[0].data = top.map(function (e) { return porEscola[e.id] || 0; });
      gTop.data.datasets[0].backgroundColor = top.map(function (e) { return COR[e.faixa]; });
    }
    gTop.update();

    // roscas
    preencherRosca(gFaixa, 'lFaixa', ['Mínimo', 'Médio', 'Elevado'], contar(escolas, 'faixa'));
    preencherRosca(gGravidade, 'lGravidade', ['Alta', 'Média', 'Baixa'], contar(ab, 'gravidade'));
    preencherRosca(gStatus, 'lStatus', ['Aberta', 'Em andamento', 'Resolvida'], contar(todasNcs, 'status'));

    // mapa
    var porEscolaMapa = contar(ab, 'escola');
    var visiveis = {}; escolas.forEach(function (e) { visiveis[e.id] = true; });
    ESCOLAS.forEach(function (e) {
      var c = circulos[e.id], n = porEscolaMapa[e.id] || 0, ativo = !!visiveis[e.id], sel = e.id === estado.escola;
      c.setRadius(ativo ? 4 + Math.sqrt(n) * 1.5 : 4);
      c.setStyle({
        fillOpacity: ativo ? 0.85 : 0.15, opacity: ativo ? 1 : 0.3,
        color: sel ? '#262c35' : '#fff', weight: sel ? 3 : 1.5
      });
      if (sel) c.bringToFront();
      c.bindTooltip('<div class="mapa-tip"><b>' + esc(e.nome) + '</b>' + esc(e.bairro) + ' · índice ' +
        fmtDec.format(e.indice) + '<br>' + (ativo ? n + ' NC abertas' : 'fora do filtro') + '</div>');
    });
    if (uma) mapa.setView([uma.lat, uma.lng], Math.max(mapa.getZoom(), 14));
    else if (mapaFocado) enquadrarRede();
    mapaFocado = !!uma;

    desenharRanking(escolas, ab);
    desenharFicha();
  }

  function preencherRosca(graf, idLeg, chaves, contagem) {
    var valores = chaves.map(function (k) { return contagem[k] || 0; });
    var total = valores.reduce(function (s, v) { return s + v; }, 0);
    graf.data.labels = chaves;
    graf.data.datasets[0].data = valores;
    graf.data.datasets[0].backgroundColor = chaves.map(function (k) { return COR[k]; });
    graf.options.plugins.centroRosca.texto = fmtInt.format(total);
    graf.update();
    el(idLeg).innerHTML = chaves.map(function (k, i) {
      return '<li><i style="background:' + COR[k] + '"></i>' + k + '<b>' + fmtInt.format(valores[i]) + '</b></li>';
    }).join('');
  }

  // ---------- ranking ----------
  function desenharRanking(escolas, ab) {
    var nc = contar(ab, 'escola'), custo = somar(ab, 'escola', 'custo');
    var acess = contar(ab.filter(function (n) { return n.categoria === 'Acessibilidade'; }), 'escola');
    var linhas = escolas.map(function (e) {
      return { e: e, pos: e.pos, id: e.id, nome: e.nome, bairro: e.bairro, indice: e.indice,
               nc: nc[e.id] || 0, acess: acess[e.id] || 0, alunos: e.alunos, prioridade: e.prioridade, custo: custo[e.id] || 0 };
    });
    var k = estado.ordem, dir = estado.asc ? 1 : -1;
    linhas.sort(function (a, b) {
      var va = a[k], vb = b[k];
      if (typeof va === 'string') return dir * va.localeCompare(vb, 'pt-BR');
      return dir * (va - vb);
    });
    document.querySelectorAll('#tRanking th').forEach(function (th) {
      var b = th.querySelector('button');
      if (b && b.dataset.ordem === k && b.textContent !== 'Faixa') th.setAttribute('aria-sort', estado.asc ? 'ascending' : 'descending');
      else th.removeAttribute('aria-sort');
    });
    var corpo = el('tRanking').querySelector('tbody');
    if (!linhas.length) { corpo.innerHTML = '<tr><td colspan="11" class="vazio-tabela">Nenhuma escola atende a esses filtros.</td></tr>'; return; }
    corpo.innerHTML = linhas.map(function (l) {
      return '<tr data-id="' + l.id + '"' + (l.id === estado.escola ? ' class="sel"' : '') + '>' +
        '<td>' + l.pos + '</td><td>' + l.id + '</td>' +
        '<td><button type="button" data-id="' + l.id + '">' + esc(l.nome) + '</button></td>' +
        '<td>' + esc(l.bairro) + '</td>' +
        '<td class="num">' + fmtDec.format(l.indice) + '</td>' +
        '<td><span class="pilula pilula--' + l.e.faixa + '">' + l.e.faixa + '</span></td>' +
        '<td class="num">' + l.nc + '</td><td class="num">' + l.acess + '</td>' +
        '<td class="num">' + fmtInt.format(l.alunos) + '</td>' +
        '<td class="num">' + fmtDec.format(l.prioridade) + '</td>' +
        '<td class="num">' + fmtBRL.format(l.custo) + '</td></tr>';
    }).join('');
  }
  el('tRanking').querySelector('thead').addEventListener('click', function (ev) {
    var b = ev.target.closest('button'); if (!b) return;
    var k = b.dataset.ordem;
    if (estado.ordem === k) estado.asc = !estado.asc;
    else { estado.ordem = k; estado.asc = ['pos', 'id', 'nome', 'bairro', 'indice'].indexOf(k) >= 0; }
    desenharRanking(escolasFiltradas(), abertas(ncsDe(escolasFiltradas(), true)));
  });
  el('tRanking').querySelector('tbody').addEventListener('click', function (ev) {
    var tr = ev.target.closest('tr[data-id]'); if (!tr) return;
    definir({ escola: estado.escola === tr.dataset.id ? '' : tr.dataset.id });
  });

  // ---------- ficha da escola ----------
  var ORDEM_GRAV = { 'Alta': 0, 'Média': 1, 'Baixa': 2 };
  function desenharFicha() {
    var uma = estado.escola ? POR_ID[estado.escola] : null;
    el('ficha').hidden = !uma;
    if (!uma) return;

    var todas = ncsDe([uma], true);
    var ab = abertas(todas);
    var altas = ab.filter(function (n) { return n.gravidade === 'Alta'; }).length;
    var custo = ab.reduce(function (s, n) { return s + n.custo; }, 0);

    el('fNome').textContent = uma.nome;
    el('fSub').textContent = uma.id + ' · ' + uma.bairro + (uma.tese ? ' · índice real da tese InfraEs' : ' · dados simulados');
    el('fIndice').textContent = fmtDec.format(uma.indice);
    el('fIndice').style.color = COR[uma.faixa];
    el('fMarca').style.left = (uma.indice * 100) + '%';

    var itens = [
      ['Faixa', '<span class="pilula pilula--' + uma.faixa + '">' + uma.faixa + '</span>'],
      ['Ranking de prioridade', uma.pos + 'º de ' + ESCOLAS.length],
      ['Índice de prioridade', fmtDec.format(uma.prioridade)],
      ['Alunos', fmtInt.format(uma.alunos)],
      ['Alunos com deficiência', fmtInt.format(uma.deficiencia)],
      ['NC abertas' + (estado.categoria ? ' (' + estado.categoria + ')' : ''), fmtInt.format(ab.length)],
      ['NC de gravidade alta', fmtInt.format(altas)],
      ['Custo de recuperação', fmtBRL.format(custo)]
    ];
    el('fLista').innerHTML = itens.map(function (i) { return '<div><dt>' + i[0] + '</dt><dd>' + i[1] + '</dd></div>'; }).join('');

    document.querySelectorAll('#fStatus button').forEach(function (b) {
      b.setAttribute('aria-pressed', String(b.dataset.status === estado.statusNc));
    });
    var lista = todas.filter(function (n) {
      if (estado.statusNc === 'abertas') return n.status !== 'Resolvida';
      return !estado.statusNc || n.status === estado.statusNc;
    }).sort(function (a, b) { return ORDEM_GRAV[a.gravidade] - ORDEM_GRAV[b.gravidade] || b.custo - a.custo; });

    var corpo = el('tNcs').querySelector('tbody');
    if (!lista.length) { corpo.innerHTML = '<tr><td colspan="8" class="vazio-tabela">Nenhuma não conformidade com esse filtro.</td></tr>'; return; }
    corpo.innerHTML = lista.map(function (n) {
      return '<tr><td>' + n.id + '</td><td>' + esc(n.categoria) + '</td><td>' + esc(n.servico) + '</td>' +
        '<td>' + esc(n.local) + '</td>' +
        '<td><span class="pilula pilula--' + n.gravidade + '">' + n.gravidade + '</span></td>' +
        '<td><span class="pilula pilula--' + n.status.replace(' ', '-') + '">' + n.status + '</span></td>' +
        '<td>' + n.data.split('-').reverse().join('/') + '</td>' +
        '<td class="num">' + (n.status === 'Resolvida' ? '—' : fmtBRL.format(n.custo)) + '</td></tr>';
    }).join('');
  }

  desenhar();
})();
