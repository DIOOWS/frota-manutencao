(function () {
  'use strict';

  const app = document.getElementById('pf5App');
  if (!app) return;

  const panel = document.getElementById('pf5Panel');
  if (!panel) return;

  const mes = app.dataset.mes;
  const ano = app.dataset.ano;

  /*
   * QUANTIDADE DE CONTAS POR PÁGINA
   *
   * Se quiser voltar para 8 depois:
   * const PER_PAGE = 8;
   */
  const PER_PAGE = 6;

  let activeTab = 'aguardando';
  let selected = new Map();
  let currentPaymentId = null;
  let activePlanFilter = 'todos';

  /*
   * Evita que duas trocas rápidas de aba
   * acabem exibindo uma resposta antiga.
   */
  let tabRequestId = 0;

  const pages = {
    aguardando: 1,
    planejadas: 1
  };

  /*
   * CACHE DAS ABAS
   *
   * Aguardando já veio renderizado pelo Flask
   * junto com a página principal.
   */
  const tabCache = {
    aguardando: panel.innerHTML,
    planejadas: null
  };

  const money = (value) =>
    Number(value || 0).toLocaleString('pt-BR', {
      style: 'currency',
      currency: 'BRL'
    });

  /*
   * ============================================================
   * HELPERS
   * ============================================================
   */

  async function post(url, data) {
    const response = await fetch(url, {
      method: 'POST',
      body: data,
      headers: {
        'X-Requested-With': 'XMLHttpRequest'
      }
    });

    const json = await response
      .json()
      .catch(() => ({}));

    if (!response.ok || !json.ok) {
      throw new Error(
        json.message ||
        'Erro na operação.'
      );
    }

    return json;
  }

  function clearTabCache() {
    tabCache.aguardando = null;
    tabCache.planejadas = null;
  }

  function getSearchTerm() {
    return (
      document.getElementById('pf5Search')
        ?.value || ''
    )
      .trim()
      .toLowerCase();
  }

  function setTabActive(tab) {
    document
      .querySelectorAll('.pf5-tab')
      .forEach((button) => {
        const active =
          button.dataset.tab === tab;

        button.classList.toggle(
          'active',
          active
        );

        button.setAttribute(
          'aria-selected',
          active ? 'true' : 'false'
        );
      });
  }

  /*
   * ============================================================
   * PREFETCH
   *
   * Carrega a aba Vou pagar em segundo plano.
   * Assim, quando clicar nela pela primeira vez,
   * provavelmente já estará em memória.
   * ============================================================
   */

  async function prefetchTab(tab) {
    if (tabCache[tab]) {
      return;
    }

    try {
      const url =
        `/gestao/planejamento-financeiro/painel/${tab}` +
        `?mes=${encodeURIComponent(mes)}` +
        `&ano=${encodeURIComponent(ano)}`;

      const response = await fetch(url, {
        headers: {
          'X-Requested-With':
            'XMLHttpRequest'
        }
      });

      if (!response.ok) {
        return;
      }

      tabCache[tab] =
        await response.text();

    } catch (error) {
      /*
       * Prefetch é opcional.
       * Se falhar, a aba carrega normalmente
       * quando o usuário clicar.
       */
    }
  }

  /*
   * ============================================================
   * CARREGAR ABA
   * ============================================================
   */

  async function loadTab(
    tab,
    preservePage = true,
    forceReload = false
  ) {
    activeTab = tab;
    selected.clear();

    if (!preservePage) {
      pages[tab] = 1;
    }

    if (tab !== 'planejadas') {
      activePlanFilter = 'todos';
    }

    setTabActive(tab);

    /*
     * Se já temos a aba em memória,
     * não consulta Flask novamente.
     */
    if (
      tabCache[tab] &&
      !forceReload
    ) {
      panel.innerHTML =
        tabCache[tab];

      bindPanel();
      applyFilters(true);

      return;
    }

    const requestId =
      ++tabRequestId;

    panel.classList.add('loading');

    try {
      const url =
        `/gestao/planejamento-financeiro/painel/${tab}` +
        `?mes=${encodeURIComponent(mes)}` +
        `&ano=${encodeURIComponent(ano)}`;

      const response = await fetch(url, {
        headers: {
          'X-Requested-With':
            'XMLHttpRequest'
        }
      });

      if (!response.ok) {
        throw new Error(
          'Erro ao carregar painel.'
        );
      }

      const html =
        await response.text();

      /*
       * Uma aba mais nova já foi solicitada.
       * Ignora resposta atrasada.
       */
      if (
        requestId !==
        tabRequestId
      ) {
        return;
      }

      tabCache[tab] = html;

      panel.innerHTML = html;

      bindPanel();
      applyFilters(true);

    } finally {
      if (
        requestId ===
        tabRequestId
      ) {
        panel.classList.remove(
          'loading'
        );
      }
    }
  }

  /*
   * ============================================================
   * FILTROS
   * ============================================================
   */

  function applyFilters(
    preservePage = false
  ) {
    const searchTerm =
      getSearchTerm();

    panel
      .querySelectorAll('.pf5-row')
      .forEach((row) => {
        const searchText =
          (
            row.dataset.search || ''
          ).toLowerCase();

        const searchOk =
          !searchTerm ||
          searchText.includes(
            searchTerm
          );

        let planOk = true;

        if (
          activeTab ===
            'planejadas' &&
          activePlanFilter !==
            'todos'
        ) {
          planOk =
            row.dataset.planStatus ===
            activePlanFilter;
        }

        row.dataset.filtered =
          searchOk && planOk
            ? '1'
            : '0';
      });

    if (!preservePage) {
      pages[activeTab] = 1;
    }

    renderPagination();
    updateVisibleCount();
  }

  function updateVisibleCount() {
    const count =
      panel.querySelector(
        '.pf5-visible-count'
      );

    if (!count) {
      return;
    }

    const rows = [
      ...panel.querySelectorAll(
        '.pf5-row'
      )
    ].filter(
      (row) =>
        row.dataset.filtered !== '0'
    );

    count.textContent =
      rows.length;
  }

  /*
   * ============================================================
   * PAGINAÇÃO
   * ============================================================
   */

  function renderPagination() {
    const view =
      panel.querySelector(
        '.pf5-view'
      );

    if (!view) {
      return;
    }

    const allRows = [
      ...view.querySelectorAll(
        '.pf5-row'
      )
    ];

    const rows =
      allRows.filter(
        (row) =>
          row.dataset.filtered !== '0'
      );

    const footer =
      view.querySelector(
        '.pf5-footer'
      );

    if (!footer) {
      return;
    }

    const totalPages =
      Math.max(
        1,
        Math.ceil(
          rows.length /
          PER_PAGE
        )
      );

    if (
      pages[activeTab] >
      totalPages
    ) {
      pages[activeTab] =
        totalPages;
    }

    if (
      pages[activeTab] <
      1
    ) {
      pages[activeTab] = 1;
    }

    const page =
      pages[activeTab];

    const startIndex =
      (page - 1) *
      PER_PAGE;

    const endIndex =
      startIndex +
      PER_PAGE;

    /*
     * Primeiro esconde tudo.
     */
    allRows.forEach((row) => {
      row.style.display =
        'none';
    });

    /*
     * Depois mostra somente
     * as linhas da página atual.
     */
    rows.forEach(
      (row, index) => {
        if (
          index >= startIndex &&
          index < endIndex
        ) {
          row.style.display =
            '';
        }
      }
    );

    /*
     * Informação:
     * Mostrando 1 a 6 de 89 contas
     */
    const info =
      footer.querySelector(
        '.pf5-page-info'
      );

    if (info) {
      const start =
        rows.length
          ? startIndex + 1
          : 0;

      const end =
        Math.min(
          endIndex,
          rows.length
        );

      info.textContent =
        `Mostrando ${start} a ${end} de ${rows.length} contas`;
    }

    /*
     * Botões
     */
    const nav =
      footer.querySelector(
        '.pf5-pagination'
      );

    if (!nav) {
      return;
    }

    nav.innerHTML = '';

    const createButton = (
      label,
      targetPage,
      disabled = false,
      active = false
    ) => {
      const button =
        document.createElement(
          'button'
        );

      button.type = 'button';

      button.className =
        'pf5-page-btn' +
        (
          active
            ? ' active'
            : ''
        );

      button.textContent =
        label;

      button.disabled =
        disabled;

      /*
       * IMPORTANTE:
       *
       * Não tem window.scrollTo().
       *
       * Ao mudar de página,
       * a tela permanece exatamente
       * onde o usuário está.
       */
      button.addEventListener(
        'click',
        () => {
          pages[activeTab] =
            targetPage;

          renderPagination();
        }
      );

      nav.appendChild(
        button
      );
    };

    createButton(
      '«',
      1,
      page === 1
    );

    createButton(
      '‹',
      Math.max(
        1,
        page - 1
      ),
      page === 1
    );

    const pageList = [];

    if (totalPages <= 7) {
      for (
        let i = 1;
        i <= totalPages;
        i++
      ) {
        pageList.push(i);
      }

    } else {
      pageList.push(1);

      if (page > 4) {
        pageList.push('…');
      }

      const first =
        Math.max(
          2,
          page - 1
        );

      const last =
        Math.min(
          totalPages - 1,
          page + 1
        );

      for (
        let i = first;
        i <= last;
        i++
      ) {
        pageList.push(i);
      }

      if (
        page <
        totalPages - 3
      ) {
        pageList.push('…');
      }

      pageList.push(
        totalPages
      );
    }

    pageList.forEach(
      (item) => {
        if (
          item === '…'
        ) {
          const span =
            document.createElement(
              'span'
            );

          span.className =
            'pf5-page-ellipsis';

          span.textContent =
            '…';

          nav.appendChild(
            span
          );

          return;
        }

        createButton(
          String(item),
          item,
          false,
          item === page
        );
      }
    );

    createButton(
      '›',
      Math.min(
        totalPages,
        page + 1
      ),
      page === totalPages
    );

    createButton(
      '»',
      totalPages,
      page === totalPages
    );
  }

  /*
   * ============================================================
   * SELEÇÃO EM MASSA
   * ============================================================
   */

  function updateBulk() {
    const bar =
      document.getElementById(
        'pf5BulkBar'
      );

    if (!bar) {
      return;
    }

    let total = 0;

    selected.forEach(
      (value) => {
        total += Number(
          value || 0
        );
      }
    );

    const qty =
      document.getElementById(
        'pf5SelectedQty'
      );

    const totalEl =
      document.getElementById(
        'pf5SelectedTotal'
      );

    if (qty) {
      qty.textContent =
        selected.size;
    }

    if (totalEl) {
      totalEl.textContent =
        money(total);
    }

    const openButton =
      document.getElementById(
        'pf5OpenBulk'
      );

    const clearButton =
      document.getElementById(
        'pf5ClearSelection'
      );

    if (openButton) {
      openButton.disabled =
        selected.size === 0;
    }

    if (clearButton) {
      clearButton.disabled =
        selected.size === 0;
    }
  }

  /*
   * ============================================================
   * PLANEJAR UMA CONTA
   * ============================================================
   */

  async function planOne(
    id,
    date = '',
    observation = ''
  ) {
    const formData =
      new FormData();

    formData.set(
      'mes',
      mes
    );

    formData.set(
      'ano',
      ano
    );

    formData.set(
      'tipo_planejamento',
      'TOTAL'
    );

    /*
     * Data continua opcional.
     */
    if (date) {
      formData.set(
        'data_prevista',
        date
      );
    }

    if (observation) {
      formData.set(
        'observacao',
        observation
      );
    }

    return post(
      `/gestao/planejamento-financeiro/planejar/${id}`,
      formData
    );
  }

  /*
   * ============================================================
   * EVENTOS DO PAINEL
   *
   * Como o conteúdo do painel muda ao trocar
   * de aba, esses eventos precisam ser
   * vinculados novamente.
   * ============================================================
   */

  function bindPanel() {

    /*
     * CHECKBOXES
     */
    panel
      .querySelectorAll(
        '.pf5-row-check'
      )
      .forEach(
        (checkbox) => {
          checkbox.addEventListener(
            'change',
            () => {
              if (
                checkbox.checked
              ) {
                selected.set(
                  checkbox.value,
                  Number(
                    checkbox.dataset
                      .value || 0
                  )
                );

              } else {
                selected.delete(
                  checkbox.value
                );
              }

              updateBulk();
            }
          );
        }
      );

    /*
     * SELECIONAR VISÍVEIS
     */
    const selectAll =
      panel.querySelector(
        '#pf5SelectAll'
      );

    if (selectAll) {
      selectAll.addEventListener(
        'change',
        () => {
          panel
            .querySelectorAll(
              '.pf5-row-check'
            )
            .forEach(
              (checkbox) => {
                const row =
                  checkbox.closest(
                    '.pf5-row'
                  );

                /*
                 * Só seleciona as linhas
                 * visíveis da página atual.
                 */
                if (
                  !row ||
                  row.style.display ===
                    'none'
                ) {
                  return;
                }

                checkbox.checked =
                  selectAll.checked;

                if (
                  checkbox.checked
                ) {
                  selected.set(
                    checkbox.value,
                    Number(
                      checkbox.dataset
                        .value || 0
                    )
                  );

                } else {
                  selected.delete(
                    checkbox.value
                  );
                }
              }
            );

          updateBulk();
        }
      );
    }

    /*
     * LIMPAR SELEÇÃO
     */
    const clearButton =
      panel.querySelector(
        '#pf5ClearSelection'
      );

    if (clearButton) {
      clearButton.addEventListener(
        'click',
        () => {
          selected.clear();

          panel
            .querySelectorAll(
              '.pf5-row-check'
            )
            .forEach(
              (checkbox) => {
                checkbox.checked =
                  false;
              }
            );

          if (selectAll) {
            selectAll.checked =
              false;
          }

          updateBulk();
        }
      );
    }

    /*
     * ABRIR PLANEJAMENTO
     * EM MASSA
     */
    const openBulk =
      panel.querySelector(
        '#pf5OpenBulk'
      );

    if (openBulk) {
      openBulk.addEventListener(
        'click',
        () => {
          if (
            !selected.size
          ) {
            return;
          }

          let total = 0;

          selected.forEach(
            (value) => {
              total += Number(
                value || 0
              );
            }
          );

          const qty =
            document.getElementById(
              'pf5BulkQty'
            );

          const totalEl =
            document.getElementById(
              'pf5BulkTotal'
            );

          if (qty) {
            qty.textContent =
              selected.size;
          }

          if (totalEl) {
            totalEl.textContent =
              money(total);
          }

          const modal =
            document.getElementById(
              'pf5BulkModal'
            );

          if (modal) {
            modal.classList.add(
              'open'
            );

            modal.setAttribute(
              'aria-hidden',
              'false'
            );
          }
        }
      );
    }

    /*
     * ========================================================
     * VOU PAGAR
     * ========================================================
     */
    panel
      .querySelectorAll(
        '.pf5-plan-now'
      )
      .forEach(
        (button) => {
          button.addEventListener(
            'click',
            async () => {
              const originalText =
                button.textContent;

              button.disabled =
                true;

              button.textContent =
                'Planejando...';

              try {
                await planOne(
                  button.dataset.id
                );

                /*
                 * Dados mudaram.
                 * Cache antigo não pode continuar.
                 */
                clearTabCache();

                await loadTab(
                  'aguardando',
                  true,
                  true
                );

                /*
                 * Já começa a preparar
                 * a aba Vou pagar atualizada.
                 */
                prefetchTab(
                  'planejadas'
                );

              } catch (error) {
                alert(
                  error.message
                );

              } finally {
                button.disabled =
                  false;

                button.textContent =
                  originalText;
              }
            }
          );
        }
      );

    /*
     * ========================================================
     * ESCOLHER DATA INDIVIDUAL
     * ========================================================
     */
    panel
      .querySelectorAll(
        '.pf5-plan-date'
      )
      .forEach(
        (button) => {
          button.addEventListener(
            'click',
            () => {
              const modal =
                document.getElementById(
                  'pf5DateModal'
                );

              if (!modal) {
                return;
              }

              modal.dataset.id =
                button.dataset.id;

              const conta =
                document.getElementById(
                  'pf5DateConta'
                );

              if (conta) {
                conta.textContent =
                  button.dataset.name ||
                  '-';
              }

              const input =
                document.getElementById(
                  'pf5DateInput'
                );

              if (input) {
                input.value =
                  '';
              }

              modal.classList.add(
                'open'
              );

              modal.setAttribute(
                'aria-hidden',
                'false'
              );
            }
          );
        }
      );

    /*
     * ========================================================
     * KPIs
     * ========================================================
     */
    panel
      .querySelectorAll(
        '[data-plan-filter]'
      )
      .forEach(
        (button) => {

          const buttonFilter =
            button.dataset
              .planFilter ||
            'todos';

          button.classList.toggle(
            'active',
            buttonFilter ===
              activePlanFilter
          );

          button.addEventListener(
            'click',
            () => {
              activePlanFilter =
                button.dataset
                  .planFilter ||
                'todos';

              panel
                .querySelectorAll(
                  '[data-plan-filter]'
                )
                .forEach(
                  (item) => {
                    item.classList.toggle(
                      'active',
                      item === button
                    );
                  }
                );

              applyFilters(
                false
              );
            }
          );
        }
      );

    /*
     * ========================================================
     * REPROGRAMAR
     * ========================================================
     */
    panel
      .querySelectorAll(
        '.pf5-reprogram'
      )
      .forEach(
        (button) => {
          button.addEventListener(
            'click',
            () => {
              currentPaymentId =
                button.dataset
                  .paymentId;

              if (
                !currentPaymentId
              ) {
                alert(
                  'Pagamento não identificado.'
                );

                return;
              }

              const conta =
                document.getElementById(
                  'pf5ReprogramConta'
                );

              if (conta) {
                conta.textContent =
                  button.dataset.name ||
                  '-';
              }

              const input =
                document.getElementById(
                  'pf5ReprogramDate'
                );

              if (input) {
                input.value =
                  button.dataset.date ||
                  '';
              }

              const modal =
                document.getElementById(
                  'pf5ReprogramModal'
                );

              if (modal) {
                modal.classList.add(
                  'open'
                );

                modal.setAttribute(
                  'aria-hidden',
                  'false'
                );
              }
            }
          );
        }
      );

    /*
     * ========================================================
     * REMOVER DO PLANEJAMENTO
     * ========================================================
     */
    panel
      .querySelectorAll(
        '.pf5-remove-plan'
      )
      .forEach(
        (button) => {
          button.addEventListener(
            'click',
            async () => {

              if (
                !confirm(
                  'Remover esta conta do planejamento?'
                )
              ) {
                return;
              }

              const formData =
                new FormData();

              formData.set(
                'mes',
                mes
              );

              formData.set(
                'ano',
                ano
              );

              if (
                button.dataset
                  .paymentId
              ) {
                formData.set(
                  'pagamento_planejado_id',
                  button.dataset
                    .paymentId
                );
              }

              button.disabled =
                true;

              try {
                await post(
                  `/gestao/planejamento-financeiro/remover/${button.dataset.id}`,
                  formData
                );

                clearTabCache();

                await loadTab(
                  'planejadas',
                  true,
                  true
                );

                prefetchTab(
                  'aguardando'
                );

              } catch (error) {
                button.disabled =
                  false;

                alert(
                  error.message
                );
              }
            }
          );
        }
      );

    updateBulk();
  }

  /*
   * ============================================================
   * ABAS
   * ============================================================
   */

  document
    .querySelectorAll(
      '.pf5-tab'
    )
    .forEach(
      (button) => {
        button.addEventListener(
          'click',
          () => {
            const tab =
              button.dataset.tab;

            /*
             * Já está nessa aba.
             * Não faz nada.
             */
            if (
              tab === activeTab
            ) {
              return;
            }

            loadTab(
              tab,
              true,
              false
            ).catch(
              (error) => {
                alert(
                  error.message
                );
              }
            );
          }
        );
      }
    );

  /*
   * ============================================================
   * BUSCA
   * ============================================================
   */

  const search =
    document.getElementById(
      'pf5Search'
    );

  if (search) {
    search.addEventListener(
      'input',
      () => {
        applyFilters(
          false
        );
      }
    );
  }

  const searchClear =
    document.getElementById(
      'pf5SearchClear'
    );

  if (searchClear) {
    searchClear.addEventListener(
      'click',
      () => {
        if (search) {
          search.value = '';
        }

        applyFilters(
          false
        );
      }
    );
  }

  /*
   * ============================================================
   * MODAL - PLANEJAMENTO EM MASSA
   * ============================================================
   */

  document
    .querySelectorAll(
      '[data-close-bulk]'
    )
    .forEach(
      (element) => {
        element.addEventListener(
          'click',
          () => {
            const modal =
              document.getElementById(
                'pf5BulkModal'
              );

            if (modal) {
              modal.classList.remove(
                'open'
              );

              modal.setAttribute(
                'aria-hidden',
                'true'
              );
            }
          }
        );
      }
    );

  const bulkConfirm =
    document.getElementById(
      'pf5BulkConfirm'
    );

  if (bulkConfirm) {
    bulkConfirm.addEventListener(
      'click',
      async () => {

        if (
          !selected.size
        ) {
          return;
        }

        /*
         * Compatibilidade com HTML antigo
         * e com o novo pf5BulkDate.
         */
        const date =
          document
            .getElementById(
              'pf5BulkDate'
            )
            ?.value ||
          document
            .getElementById(
              'pf4BulkDate'
            )
            ?.value ||
          '';

        const observation =
          document
            .getElementById(
              'pf5BulkObs'
            )
            ?.value ||
          '';

        const originalText =
          bulkConfirm.textContent;

        bulkConfirm.disabled =
          true;

        bulkConfirm.textContent =
          'Planejando...';

        let ok = 0;
        const errors = [];

        for (
          const id of
          selected.keys()
        ) {
          try {
            await planOne(
              id,
              date,
              observation
            );

            ok++;

          } catch (error) {
            errors.push(
              `${id}: ${error.message}`
            );
          }
        }

        bulkConfirm.disabled =
          false;

        bulkConfirm.textContent =
          originalText;

        const modal =
          document.getElementById(
            'pf5BulkModal'
          );

        if (modal) {
          modal.classList.remove(
            'open'
          );

          modal.setAttribute(
            'aria-hidden',
            'true'
          );
        }

        const bulkDate =
          document.getElementById(
            'pf5BulkDate'
          ) ||
          document.getElementById(
            'pf4BulkDate'
          );

        if (bulkDate) {
          bulkDate.value = '';
        }

        const bulkObs =
          document.getElementById(
            'pf5BulkObs'
          );

        if (bulkObs) {
          bulkObs.value = '';
        }

        selected.clear();

        if (errors.length) {
          alert(
            `${ok} conta(s) planejada(s). ` +
            `${errors.length} falharam.`
          );
        }

        clearTabCache();

        await loadTab(
          'aguardando',
          true,
          true
        );

        prefetchTab(
          'planejadas'
        );
      }
    );
  }

  /*
   * ============================================================
   * MODAL - DATA INDIVIDUAL
   * ============================================================
   */

  document
    .querySelectorAll(
      '[data-close-date]'
    )
    .forEach(
      (element) => {
        element.addEventListener(
          'click',
          () => {
            const modal =
              document.getElementById(
                'pf5DateModal'
              );

            if (modal) {
              modal.classList.remove(
                'open'
              );

              modal.setAttribute(
                'aria-hidden',
                'true'
              );
            }
          }
        );
      }
    );

  const dateConfirm =
    document.getElementById(
      'pf5DateConfirm'
    );

  if (dateConfirm) {
    dateConfirm.addEventListener(
      'click',
      async () => {

        const modal =
          document.getElementById(
            'pf5DateModal'
          );

        const input =
          document.getElementById(
            'pf5DateInput'
          );

        if (
          !modal ||
          !input
        ) {
          return;
        }

        const date =
          input.value;

        if (!date) {
          alert(
            'Escolha a data.'
          );

          return;
        }

        dateConfirm.disabled =
          true;

        try {
          await planOne(
            modal.dataset.id,
            date
          );

          modal.classList.remove(
            'open'
          );

          modal.setAttribute(
            'aria-hidden',
            'true'
          );

          clearTabCache();

          await loadTab(
            'aguardando',
            true,
            true
          );

          prefetchTab(
            'planejadas'
          );

        } catch (error) {
          alert(
            error.message
          );

        } finally {
          dateConfirm.disabled =
            false;
        }
      }
    );
  }

  /*
   * ============================================================
   * MODAL - REPROGRAMAR
   * ============================================================
   */

  document
    .querySelectorAll(
      '[data-close-reprogram]'
    )
    .forEach(
      (element) => {
        element.addEventListener(
          'click',
          () => {
            const modal =
              document.getElementById(
                'pf5ReprogramModal'
              );

            if (modal) {
              modal.classList.remove(
                'open'
              );

              modal.setAttribute(
                'aria-hidden',
                'true'
              );
            }
          }
        );
      }
    );

  const reprogramConfirm =
    document.getElementById(
      'pf5ReprogramConfirm'
    );

  if (reprogramConfirm) {
    reprogramConfirm.addEventListener(
      'click',
      async () => {

        const input =
          document.getElementById(
            'pf5ReprogramDate'
          );

        if (!input) {
          return;
        }

        const date =
          input.value;

        if (!date) {
          alert(
            'Escolha a nova data.'
          );

          return;
        }

        if (
          !currentPaymentId
        ) {
          alert(
            'Pagamento não identificado.'
          );

          return;
        }

        const formData =
          new FormData();

        formData.set(
          'mes',
          mes
        );

        formData.set(
          'ano',
          ano
        );

        formData.set(
          'data_prevista',
          date
        );

        reprogramConfirm.disabled =
          true;

        try {
          await post(
            `/gestao/planejamento-financeiro/reprogramar/${currentPaymentId}`,
            formData
          );

          const modal =
            document.getElementById(
              'pf5ReprogramModal'
            );

          if (modal) {
            modal.classList.remove(
              'open'
            );

            modal.setAttribute(
              'aria-hidden',
              'true'
            );
          }

          clearTabCache();

          await loadTab(
            'planejadas',
            true,
            true
          );

          prefetchTab(
            'aguardando'
          );

        } catch (error) {
          alert(
            error.message
          );

        } finally {
          reprogramConfirm.disabled =
            false;
        }
      }
    );
  }

  /*
   * ============================================================
   * SINCRONIZAR RADAR
   * ============================================================
   */

  const syncForm =
    document.getElementById(
      'pf5SyncForm'
    );

  if (syncForm) {
    syncForm.addEventListener(
      'submit',
      async (event) => {

        /*
         * Impede navegador de abrir
         * o JSON da rota.
         */
        event.preventDefault();

        const button =
          syncForm.querySelector(
            'button'
          );

        if (
          !button ||
          button.disabled
        ) {
          return;
        }

        const originalText =
          button.innerHTML;

        button.disabled =
          true;

        button.innerHTML =
          '↻ Sincronizando...';

        try {
          await post(
            syncForm.action,
            new FormData(
              syncForm
            )
          );

          clearTabCache();

          await loadTab(
            activeTab,
            true,
            true
          );

          /*
           * Pré-carrega a outra aba.
           */
          const otherTab =
            activeTab ===
              'aguardando'
              ? 'planejadas'
              : 'aguardando';

          prefetchTab(
            otherTab
          );

        } catch (error) {
          alert(
            error.message
          );

        } finally {
          button.disabled =
            false;

          button.innerHTML =
            originalText;
        }
      }
    );
  }

  /*
   * ============================================================
   * PRIMEIRO CARREGAMENTO
   * ============================================================
   */

  bindPanel();
  applyFilters(true);

  /*
   * A página iniciou em Aguardando.
   * Guardamos novamente o HTML original.
   *
   * O painel atual já está disponível,
   * então não precisamos buscar Aguardando.
   */

  /*
   * Pré-carrega "Vou pagar"
   * sem bloquear a tela.
   */
  if (
    'requestIdleCallback' in window
  ) {
    window.requestIdleCallback(
      () => {
        prefetchTab(
          'planejadas'
        );
      },
      {
        timeout: 1500
      }
    );

  } else {
    setTimeout(
      () => {
        prefetchTab(
          'planejadas'
        );
      },
      250
    );
  }

})();