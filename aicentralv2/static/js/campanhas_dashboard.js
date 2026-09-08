(function () {
  "use strict";

  const root = document.getElementById("campaignDashboard");
  if (!root) return;

  const dataElement = document.getElementById("campaignDashboardData");
  let dashboardData = {};
  try {
    dashboardData = JSON.parse(dataElement ? dataElement.textContent : "{}");
  } catch (error) {
    console.error("Dados do painel de campanhas inválidos.", error);
  }

  function notify(message, type) {
    const status = document.getElementById("campaignActionStatus");
    if (status) {
      status.textContent = message || "";
      status.dataset.type = type || "info";
    }
    if (typeof window.showToast === "function" && message) {
      window.showToast(message, type || "info");
    }
  }

  function parseMoney(value) {
    if (value == null || value === "") return 0;
    if (typeof value === "number" && Number.isFinite(value)) return value;
    let raw = String(value).replace(/R\$\s*/gi, "").replace(/\s/g, "");
    if (raw.includes(",")) raw = raw.replace(/\./g, "").replace(",", ".");
    else if ((raw.match(/\./g) || []).length > 1) raw = raw.replace(/\./g, "");
    const parsed = Number.parseFloat(raw);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function formatMoneyInput(value) {
    if (value == null || value === "") return "";
    return parseMoney(value).toLocaleString("pt-BR", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }

  function formatDateInput(value) {
    if (!value) return "";
    return String(value).slice(0, 10);
  }

  function setField(id, value) {
    const field = document.getElementById(id);
    if (field) field.value = value == null ? "" : value;
  }

  function initializeFilters() {
    const form = document.getElementById("campaignFilters");
    if (!form) return;
    ["campaignReference", "campaignOwner", "campaignPlatform"].forEach(function (id) {
      const field = document.getElementById(id);
      if (field) field.addEventListener("change", function () { form.submit(); });
    });

    const search = document.getElementById("campaignSearch");
    const visibleCount = document.getElementById("campaignVisibleCount");
    const empty = document.getElementById("campaignSearchEmpty");
    if (!search) return;
    search.addEventListener("input", function () {
      const term = search.value.trim().toLocaleLowerCase("pt-BR");
      const rows = Array.from(root.querySelectorAll("[data-campaign-row]"));
      let visible = 0;
      rows.forEach(function (row) {
        const matches = !term || (row.dataset.search || "").includes(term);
        row.hidden = !matches;
        if (matches) visible += 1;
      });
      if (visibleCount) visibleCount.textContent = visible + (visible === 1 ? " ativa" : " ativas");
      if (empty) empty.hidden = visible > 0 || !rows.length;
    });
  }

  function initializeRows() {
    root.querySelectorAll("[data-campaign-row]").forEach(function (row) {
      function openDetail(event) {
        if (event.target.closest("a, button")) return;
        window.location.href = row.dataset.detailUrl;
      }
      row.addEventListener("click", openDetail);
      row.addEventListener("keydown", function (event) {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        openDetail(event);
      });
    });
  }

  function initializeQuickEdit() {
    const dialog = document.getElementById("campaignQuickEdit");
    const form = document.getElementById("campaignQuickEditForm");
    const status = document.getElementById("campaignQuickEditStatus");
    const fullEdit = document.getElementById("campaignFullEditLink");
    if (!dialog || !form) return;

    function setStatus(message, type) {
      if (!status) return;
      status.textContent = message || "";
      status.dataset.type = type || "info";
      status.hidden = !message;
    }

    function openEditor(campaign) {
      const editTemplate = form.dataset.editUrlTemplate;
      form.action = editTemplate.replace("/0/", "/" + campaign.id_campanha + "/");
      setField("quick_id_pi", campaign.id_pi);
      setField("quick_id_cliente", campaign.id_cliente);
      setField("quick_id_cliente_hidden", campaign.id_cliente);
      setField("quick_mes_ref", formatDateInput(campaign.mes_ref));
      setField("quick_mes_ref_comp", campaign.mes_ref_comp);
      setField("quick_nome_campanha", campaign.nome_campanha);
      setField("quick_obj_contratados", campaign.obj_contratados);
      setField("quick_valor_plataforma", formatMoneyInput(campaign.valor_plataforma));
      setField("quick_custo_midia_orcado", formatMoneyInput(campaign.custo_midia_orcado));
      setField("quick_id_status", campaign.id_status);
      setField("quick_periodo_inicio", formatDateInput(campaign.periodo_inicio));
      setField("quick_periodo_fim", formatDateInput(campaign.periodo_fim));
      setField("quick_id_plataforma", campaign.id_plataforma);
      setField("quick_id_objetivos_campanha", campaign.id_objetivos_campanha);
      setField("quick_totalizador_atingido", campaign.totalizador_atingido);
      setField("quick_totalizador_gasto", formatMoneyInput(campaign.totalizador_gasto));
      setField("quick_link_dash", campaign.link_dash);
      ["perc_margem_cc", "perc_tech_fee", "perc_com_vendas", "perc_pl_incentivos", "perc_impostos"].forEach(function (field) {
        setField("quick_" + field, campaign[field]);
      });
      ["val_margem_cc", "val_tech_fee", "val_com_vendas", "val_pl_incentivos", "val_impostos"].forEach(function (field) {
        setField("quick_" + field, formatMoneyInput(campaign[field]));
      });
      const under = document.getElementById("quick_under");
      if (under) under.checked = Boolean(campaign.under);
      if (fullEdit) fullEdit.href = "/campanhas-pi/" + campaign.id_campanha;
      setStatus("", "info");
      dialog.showModal();
    }

    const financialPairs = [
      ["perc_margem_cc", "val_margem_cc"],
      ["perc_tech_fee", "val_tech_fee"],
      ["perc_com_vendas", "val_com_vendas"],
      ["perc_pl_incentivos", "val_pl_incentivos"],
      ["perc_impostos", "val_impostos"],
    ];
    function recalculateFinancialComposition() {
      const baseField = document.getElementById("quick_valor_plataforma");
      const base = parseMoney(baseField ? baseField.value : 0);
      financialPairs.forEach(function (pair) {
        const percentage = document.getElementById("quick_" + pair[0]);
        setField(
          "quick_" + pair[1],
          formatMoneyInput(base * parseMoney(percentage ? percentage.value : 0) / 100)
        );
      });
    }
    financialPairs.forEach(function (pair) {
      const percentage = document.getElementById("quick_" + pair[0]);
      if (percentage) percentage.addEventListener("input", recalculateFinancialComposition);
    });
    const platformValue = document.getElementById("quick_valor_plataforma");
    if (platformValue) platformValue.addEventListener("input", recalculateFinancialComposition);

    root.querySelectorAll("[data-edit-campaign]").forEach(function (button) {
      button.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        try {
          openEditor(JSON.parse(button.dataset.editCampaign));
        } catch (error) {
          console.error("Não foi possível abrir a edição rápida.", error);
          notify("Não foi possível abrir a edição desta campanha.", "error");
        }
      });
    });

    root.querySelectorAll("[data-close-dialog]").forEach(function (button) {
      button.addEventListener("click", function () { dialog.close(); });
    });

    dialog.addEventListener("click", function (event) {
      if (event.target === dialog) dialog.close();
    });

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      const submit = form.querySelector("[type='submit']");
      if (submit) submit.disabled = true;
      setStatus("Salvando alterações…", "info");
      fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          "X-Campanhas-Retorno": "dashboard",
        },
      })
        .then(function (response) {
          return response.json().then(function (payload) {
            return { ok: response.ok, payload: payload };
          });
        })
        .then(function (result) {
          if (!result.ok || !result.payload.success) {
            throw new Error(result.payload.error || "Não foi possível salvar a campanha.");
          }
          setStatus("Alterações salvas.", "success");
          notify(result.payload.message || "Campanha atualizada.", "success");
          window.setTimeout(function () { window.location.reload(); }, 450);
        })
        .catch(function (error) {
          setStatus(error.message || "Não foi possível salvar a campanha.", "error");
          if (submit) submit.disabled = false;
        });
    });
  }

  function initializeCharts() {
    if (typeof window.ApexCharts !== "function") {
      notify("Os gráficos não puderam ser carregados.", "error");
      return;
    }
    const colors = {
      teal: "#1e4d4f",
      green: "#24705b",
      amber: "#a55d08",
      red: "#a93535",
      muted: "#8ca0a3",
      grid: "#e4ebec",
    };
    const paceElement = document.getElementById("campaignPaceChart");
    const paceRows = ((dashboardData.pace || {}).campanhas || []);
    if (paceElement && paceRows.length) {
      const paceChart = new window.ApexCharts(paceElement, {
        chart: { type: "scatter", height: 330, toolbar: { show: false }, animations: { enabled: false } },
        series: [{
          name: "Campanhas",
          data: paceRows.map(function (row) {
            return { x: Number(row.tempo) || 0, y: Number(row.entrega) || 0, meta: row };
          }),
        }],
        colors: [colors.teal],
        markers: {
          size: 6,
          strokeWidth: 1,
          strokeColors: "#ffffff",
          discrete: paceRows.map(function (row, index) {
            return {
              seriesIndex: 0,
              dataPointIndex: index,
              fillColor: row.severidade === "critical" ? colors.red : row.severidade === "attention" ? colors.amber : colors.green,
              size: 7,
            };
          }),
        },
        annotations: {
          yaxis: [{ y: 50, borderColor: colors.grid, strokeDashArray: 4 }],
          xaxis: [{ x: 50, borderColor: colors.grid, strokeDashArray: 4 }],
        },
        xaxis: { min: 0, max: 100, tickAmount: 4, title: { text: "Tempo decorrido (%)" }, labels: { formatter: function (value) { return Math.round(value) + "%"; } } },
        yaxis: { min: 0, max: 110, tickAmount: 5, title: { text: "Entrega (%)" }, labels: { formatter: function (value) { return Math.round(value) + "%"; } } },
        grid: { borderColor: colors.grid },
        legend: { show: false },
        tooltip: {
          custom: function (context) {
            const point = paceRows[context.dataPointIndex] || {};
            const wrapper = document.createElement("div");
            wrapper.className = "campaign-chart-tooltip";
            const title = document.createElement("strong");
            title.textContent = point.nome || "Campanha";
            const text = document.createElement("span");
            text.textContent = (point.cliente || "") + " · tempo " + Math.round(point.tempo || 0) + "% · entrega " + Math.round(point.entrega || 0) + "%";
            wrapper.append(title, text);
            return wrapper.outerHTML;
          },
        },
      });
      paceChart.render();
    } else if (paceElement) {
      paceElement.textContent = "Sem campanhas com dados de ritmo.";
      paceElement.classList.add("campaign-empty");
    }

    const platformElement = document.getElementById("campaignPlatformChart");
    const platforms = dashboardData.platforms || {};
    if (platformElement && (platforms.labels || []).length) {
      const platformChart = new window.ApexCharts(platformElement, {
        chart: { type: "bar", height: 255, toolbar: { show: false }, animations: { enabled: false } },
        series: [
          { name: dashboardData.reference || "Atual", data: platforms.atual || [] },
          { name: dashboardData.previousReference || "Anterior", data: platforms.anterior || [] },
        ],
        colors: [colors.teal, colors.muted],
        plotOptions: { bar: { borderRadius: 2, columnWidth: "58%" } },
        xaxis: { categories: platforms.labels || [], labels: { rotate: -35 } },
        yaxis: { labels: { formatter: function (value) { return "R$ " + Math.round(value / 1000) + " mil"; } } },
        grid: { borderColor: colors.grid },
        legend: { position: "top", horizontalAlign: "left" },
        tooltip: { y: { formatter: function (value) { return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" }); } } },
      });
      platformChart.render();
    } else if (platformElement) {
      platformElement.textContent = "Sem investimento registrado nesta comparação.";
      platformElement.classList.add("campaign-empty");
    }
  }

  initializeFilters();
  initializeRows();
  initializeQuickEdit();
  initializeCharts();
})();
