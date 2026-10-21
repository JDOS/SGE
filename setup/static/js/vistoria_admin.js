/* Agrupa os critérios da vistoria por categoria (linha de título) e esconde a coluna repetida */
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.inline-group .tabular table').forEach(function (tabela) {
    var linhas = tabela.querySelectorAll('tbody tr.form-row, tbody tr.has_original');
    if (!linhas.length || !tabela.querySelector('td.field-categoria')) return;

    var th = tabela.querySelectorAll('thead th');
    var colunas = th.length;
    th.forEach(function (h) { if (/categoria/i.test(h.textContent)) h.classList.add('vistoria-oculta'); });

    var anterior = null, numero = 0;
    linhas.forEach(function (tr) {
      var cel = tr.querySelector('td.field-categoria');
      if (!cel) return;
      var cat = cel.textContent.trim();
      cel.classList.add('vistoria-oculta');
      if (cat !== anterior) {
        var cab = document.createElement('tr');
        cab.className = 'vistoria-cat';
        cab.innerHTML = '<td colspan="' + colunas + '"></td>';
        cab.firstChild.textContent = cat;
        tr.parentNode.insertBefore(cab, tr);
        anterior = cat;
      }
      numero += 1;
      var nome = tr.querySelector('td.field-criterio_nome p');
      if (nome) nome.textContent = numero + '. ' + nome.textContent;
    });
  });
});


/* Reparo e valor: aparecem só quando a resposta é N; a unidade acompanha o reparo escolhido */
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.inline-group .tabular tr.has_original').forEach(function (tr) {
    var select = tr.querySelector('select.reparo-select');
    var valor = tr.querySelector('input.valor-input');
    if (!select || !valor) return;

    var unidade = document.createElement('span');
    unidade.className = 'valor-unidade';
    valor.insertAdjacentElement('afterend', unidade);

    function atualizarUnidade() {
      var op = select.options[select.selectedIndex];
      unidade.textContent = (op && op.dataset.sigla) || '';
    }
    function atualizarVisibilidade() {
      var marcado = tr.querySelector('.radio-sna input:checked');
      tr.classList.toggle('sem-reparo', !marcado || marcado.value !== 'N');
    }

    select.addEventListener('change', atualizarUnidade);
    tr.querySelectorAll('.radio-sna input').forEach(function (r) {
      r.addEventListener('change', atualizarVisibilidade);
    });
    atualizarUnidade();
    atualizarVisibilidade();
  });
});