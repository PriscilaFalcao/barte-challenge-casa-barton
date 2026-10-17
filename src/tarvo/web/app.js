const state = {
  closureId: null,
  month: null,
  files: {},
  table: "comissoes",
  rows: [],
  lastFocus: null,
};

const labels = {
  comissoes: { title: "Comissões", columns: ["lojista", "linha_negocio", "comissao_brl"] },
  divergencias: { title: "Divergências", columns: ["cnpj", "linha_negocio", "ref_origem", "diferenca_brl"] },
  notas: { title: "Notas", columns: ["tomador", "linha_negocio", "valor_brl"] },
  pendencias: { title: "Pendências", columns: ["tipo", "ref_origem", "quem_decide", "valor_brl"] },
};
const columnLabels = {
  lojista: "Lojista", linha_negocio: "Linha", comissao_brl: "Comissão", cnpj: "CNPJ",
  ref_origem: "Referência", diferenca_brl: "Diferença", tomador: "Tomador",
  valor_brl: "Valor", tipo: "Tipo", quem_decide: "Responsável",
};

const emptyState = document.querySelector("#empty-state");
const closureView = document.querySelector("#closure-view");
const uploadPanel = document.querySelector("#upload-panel");
const validationPanel = document.querySelector("#validation-panel");
const resultsPanel = document.querySelector("#results-panel");
const notice = document.querySelector("#notice");
const dialog = document.querySelector("#month-dialog");
const drawer = document.querySelector("#detail-drawer");

function showNotice(message, isError = true) {
  notice.textContent = message;
  notice.classList.toggle("notice-success", !isError);
  notice.hidden = false;
  notice.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function request(url, options = {}) {
  const response = await fetch(url, options);
  const contentType = response.headers.get("Content-Type") || "";
  const body = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) throw new Error(body?.error || "Não foi possível concluir a solicitação.");
  return body;
}

function setWorkflow(step) {
  const order = ["files", "review", "run", "validation", "outputs", "close"];
  const activeIndex = order.indexOf(step);
  document.querySelectorAll(".workflow-step").forEach((element, index) => {
    element.classList.toggle("current", index === activeIndex);
    element.classList.toggle("done", index < activeIndex);
  });
}

function formatMonth(month) {
  const [year, number] = month.split("-");
  return `${number}/${year}`;
}

function renderSummary(target, summary) {
  const cards = [
    ["Comissão de checkout", summary.checkout, "Processamento da Orbe", true],
    ["Comissão de remessa", summary.remessa, "Operações da Ponte", false],
    ["Divergências", summary.divergences_total, `${summary.divergences_count} itens encontrados`, false],
    ["Notas a emitir", summary.notes_total, `${summary.notes_count} notas no período`, false],
    ["Pendências abertas", summary.pending_count.toLocaleString("pt-BR"), Object.entries(summary.pending_by_decider).map(([name, count]) => `${name}: ${count}`).join(" · ") || "Nenhuma pendência", false],
    ["Conferência do rastro", summary.reconciles ? "Tudo reconcilia" : "Revisar valores", summary.reconciles ? "Valores conciliados com as origens" : "Há valores sem reconciliação", summary.reconciles],
  ];
  target.replaceChildren(...cards.map(([title, value, detail, accent]) => {
    const card = document.createElement("article");
    card.className = `summary-card${accent ? " accent" : ""}`;
    const label = document.createElement("p");
    label.className = "summary-label";
    label.textContent = title;
    const amount = document.createElement("p");
    amount.className = "summary-value";
    amount.textContent = value;
    const meta = document.createElement("p");
    meta.className = "summary-meta";
    meta.textContent = detail;
    card.append(label, amount, meta);
    return card;
  }));
}

function formatValue(column, value) {
  if (["comissao_brl", "diferenca_brl", "valor_brl", "valor"].includes(column)) {
    const amount = Number(value);
    if (Number.isFinite(amount)) return amount.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  }
  return value || "—";
}

function renderTable() {
  const config = labels[state.table];
  const head = document.querySelector("#table-head");
  const body = document.querySelector("#table-body");
  const query = document.querySelector("#table-search").value.trim().toLocaleLowerCase("pt-BR");
  const filtered = state.rows.filter(row => Object.values(row).some(value => String(value).toLocaleLowerCase("pt-BR").includes(query)));

  const headerRow = document.createElement("tr");
  for (const column of config.columns) {
    const cell = document.createElement("th");
    cell.scope = "col";
    cell.textContent = columnLabels[column] || column;
    headerRow.append(cell);
  }
  head.replaceChildren(headerRow);

  const visible = filtered.slice(0, 100);
  if (!visible.length) {
    const row = document.createElement("tr");
    row.className = "empty-row";
    const cell = document.createElement("td");
    cell.colSpan = config.columns.length;
    cell.textContent = query ? "Nenhum resultado para esta busca." : "Não há linhas nesta saída.";
    row.append(cell);
    body.replaceChildren(row);
  } else {
    body.replaceChildren(...visible.map(record => {
      const row = document.createElement("tr");
      row.tabIndex = 0;
      row.setAttribute("aria-label", `Abrir detalhe ${record.lojista || record.tomador || record.ref_origem || record.id_saida}`);
      for (const column of config.columns) {
        const cell = document.createElement("td");
        cell.textContent = formatValue(column, record[column]);
        if (["comissao_brl", "diferenca_brl", "valor_brl"].includes(column)) cell.className = "amount";
        row.append(cell);
      }
      row.addEventListener("click", () => openDetails(record));
      row.addEventListener("keydown", event => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          openDetails(record);
        }
      });
      return row;
    }));
  }
  document.querySelector("#table-footer").textContent =
    `${filtered.length.toLocaleString("pt-BR")} registro(s)${filtered.length > 100 ? " · exibindo os 100 primeiros" : ""}`;
}

async function selectTable(table) {
  state.table = table;
  document.querySelectorAll(".tab").forEach(tab => {
    const active = tab.dataset.table === table;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
  });
  document.querySelector("#table-search").value = "";
  try {
    const result = await request(`/api/closures/${state.closureId}/tables/${table}`);
    state.rows = result.rows;
    renderTable();
  } catch (error) {
    showNotice(error.message);
  }
}

function displayValue(label, value) {
  const item = document.createElement("div");
  item.className = "detail-record";
  const key = document.createElement("span");
  key.className = "detail-label";
  key.textContent = label;
  const val = document.createElement("span");
  val.className = "detail-value";
  val.textContent = value || "—";
  item.append(key, val);
  return item;
}

async function openDetails(record) {
  state.lastFocus = document.activeElement;
  drawer.hidden = false;
  const content = document.querySelector("#drawer-content");
  content.replaceChildren();
  const details = [
    ["Identificador", record.id_saida],
    ["Lojista / tomador", record.lojista || record.tomador],
    ["Linha de negócio", record.linha_negocio],
    ["Valor", formatValue("comissao_brl", record.comissao_brl || record.valor_brl || record.diferenca_brl)],
    ["Tipo", record.tipo],
    ["Responsável", record.quem_decide],
  ].filter(([, value]) => value);
  for (const [label, value] of details) content.append(displayValue(label, value));

  const title = document.createElement("h3");
  title.className = "trace-title";
  title.textContent = "Rastro de origem";
  content.append(title);
  try {
    const result = await request(`/api/closures/${state.closureId}/trace?id_saida=${encodeURIComponent(record.id_saida)}`);
    if (!result.rows.length) {
      const empty = document.createElement("p");
      empty.className = "helper-text";
      empty.textContent = "Não há linhas de rastro associadas a este registro.";
      content.append(empty);
    }
    for (const trace of result.rows) {
      const item = document.createElement("article");
      item.className = "trace-item";
      const heading = document.createElement("strong");
      heading.textContent = `${trace.arquivo_origem} · ${trace.ref_origem}`;
      item.append(heading);
      const metadata = [
        ["Valor de origem", formatValue("valor", trace.valor)],
        ["Componente", trace.componente],
        ["Regra aplicada", trace.regra_id],
      ].filter(([, value]) => value);
      for (const [label, value] of metadata) {
        const line = document.createElement("span");
        line.textContent = `${label}: ${value}`;
        item.append(line);
      }
      content.append(item);
    }
  } catch (error) {
    content.append(displayValue("Rastro", error.message));
  }
  document.querySelector("#drawer-backdrop").hidden = false;
  drawer.setAttribute("aria-hidden", "false");
  drawer.classList.add("open");
  document.querySelector("#close-drawer").focus();
}

function closeDrawer() {
  drawer.classList.remove("open");
  drawer.setAttribute("aria-hidden", "true");
  document.querySelector("#drawer-backdrop").hidden = true;
  setTimeout(() => {
    if (!drawer.classList.contains("open")) drawer.hidden = true;
  }, 230);
  if (state.lastFocus instanceof HTMLElement) state.lastFocus.focus();
}

function updateFileStatus() {
  const cards = [...document.querySelectorAll(".file-card")];
  const complete = cards.every(card => state.files[card.dataset.slot]);
  cards.forEach(card => {
    const filename = state.files[card.dataset.slot];
    card.classList.toggle("has-file", Boolean(filename));
    card.querySelector(".file-name").textContent = filename || "Escolher arquivo";
  });
  document.querySelector("#upload-status").textContent = complete
    ? "3 de 3 arquivos enviados. Pronto para conferir."
    : `${Object.keys(state.files).length} de 3 arquivos enviados.`;
  document.querySelector("#validate-files").disabled = !complete;
}

async function createClosure() {
  const month = document.querySelector("#month-input").value;
  if (!month) return;
  try {
    const result = await request("/api/closures", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ month }),
    });
    state.closureId = result.id;
    state.month = result.month;
    state.files = {};
    emptyState.hidden = true;
    closureView.hidden = false;
    uploadPanel.hidden = false;
    validationPanel.hidden = true;
    resultsPanel.hidden = true;
    document.querySelector("#month-label").textContent = formatMonth(result.month);
    document.querySelector("#table-search").value = "";
    notice.hidden = true;
    updateFileStatus();
    setWorkflow("files");
    dialog.close();
    document.querySelector("#new-closure").focus();
  } catch (error) {
    showNotice(error.message);
  }
}

document.querySelectorAll("#new-closure, [data-create]").forEach(button => {
  button.addEventListener("click", () => dialog.showModal());
});
document.querySelector("#create-confirm").addEventListener("click", event => {
  event.preventDefault();
  createClosure();
});
document.querySelector("#month-form").addEventListener("submit", event => {
  event.preventDefault();
  createClosure();
});
document.querySelectorAll(".file-card input").forEach(input => {
  input.addEventListener("change", async () => {
    const file = input.files[0];
    const slot = input.closest(".file-card").dataset.slot;
    if (!file) return;
    try {
      const result = await request(`/api/closures/${state.closureId}/files/${slot}`, {
        method: "POST",
        headers: { "Content-Type": "application/octet-stream", "X-Filename": encodeURIComponent(file.name) },
        body: file,
      });
      state.files = result.files;
      updateFileStatus();
      notice.hidden = true;
    } catch (error) {
      showNotice(error.message);
      input.value = "";
    }
  });
});
document.querySelector("#validate-files").addEventListener("click", async event => {
  const button = event.currentTarget;
  button.disabled = true;
  button.textContent = "Conferindo arquivos…";
  setWorkflow("review");
  try {
    const result = await request(`/api/closures/${state.closureId}/validate`, { method: "POST" });
    uploadPanel.hidden = true;
    validationPanel.hidden = false;
    renderSummary(document.querySelector("#preview-summary"), result.summary);
    setWorkflow("run");
    notice.hidden = true;
  } catch (error) {
    showNotice(error.message);
    setWorkflow("files");
  } finally {
    button.innerHTML = 'Conferir arquivos <span aria-hidden="true">→</span>';
    button.disabled = false;
    updateFileStatus();
  }
});
document.querySelector("#run-closure").addEventListener("click", async event => {
  const button = event.currentTarget;
  button.disabled = true;
  button.textContent = "Executando motor…";
  setWorkflow("run");
  try {
    const result = await request(`/api/closures/${state.closureId}/run`, { method: "POST" });
    validationPanel.hidden = true;
    resultsPanel.hidden = false;
    document.querySelector("#results-month").textContent = formatMonth(result.month);
    document.querySelector("#download-all").href = `/api/closures/${state.closureId}/download/todos.zip`;
    renderSummary(document.querySelector("#results-summary"), result.summary);
    await selectTable("comissoes");
    setWorkflow("outputs");
    notice.hidden = true;
  } catch (error) {
    showNotice(error.message);
    setWorkflow("run");
  } finally {
    button.disabled = false;
    button.innerHTML = 'Executar fechamento <span aria-hidden="true">→</span>';
  }
});
document.querySelectorAll(".tab").forEach(tab => tab.addEventListener("click", () => selectTable(tab.dataset.table)));
document.querySelector("#table-search").addEventListener("input", renderTable);
document.querySelector("#close-drawer").addEventListener("click", closeDrawer);
document.querySelector("#drawer-backdrop").addEventListener("click", closeDrawer);
document.querySelectorAll("[data-notice]").forEach(link => link.addEventListener("click", event => {
  event.preventDefault();
  showNotice(link.dataset.notice, false);
}));
document.addEventListener("keydown", event => {
  if (event.key === "Escape" && drawer.classList.contains("open")) closeDrawer();
  if (event.key === "Tab" && drawer.classList.contains("open")) {
    const focusable = [...drawer.querySelectorAll('button:not([disabled]), a[href], input:not([disabled]), [tabindex]:not([tabindex="-1"])')];
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
});
