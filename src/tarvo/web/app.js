const state = {
  closureId: null,
  month: null,
  files: {},
  table: "comissoes",
  rows: [],
  lastFocus: null,
  accounts: [],
  eventSource: null,
  closed: false,
  blockingCount: 0,
};

const labels = {
  comissoes: { title: "Comissões", columns: ["lojista", "linha_negocio", "comissao_brl"], download: "comissoes_por_lojista.csv" },
  divergencias: { title: "Divergências", columns: ["cnpj", "linha_negocio", "ref_origem", "diferenca_brl"], download: "divergencias_taxa.csv" },
  notas: { title: "Notas", columns: ["tomador", "linha_negocio", "valor_brl"], download: "notas_a_emitir.csv" },
  lancamentos: { title: "Extratos classificados", columns: ["banco", "data", "descricao", "valor", "conta_codigo", "metodo"], download: "lancamentos_classificados.csv" },
  pendencias: { title: "Pendências", columns: ["tipo", "ref_origem", "quem_decide", "valor_brl"], download: "pendencias.csv" },
  rastro: { title: "Rastro", columns: ["arquivo_origem", "ref_origem", "valor", "componente", "regra_id"], download: "rastro.csv" },
};
const columnLabels = {
  lojista: "Lojista", linha_negocio: "Linha", comissao_brl: "Comissão", cnpj: "CNPJ",
  ref_origem: "Referência", diferenca_brl: "Diferença", tomador: "Tomador",
  valor_brl: "Valor", tipo: "Tipo", quem_decide: "Responsável",
  banco: "Banco", data: "Data", descricao: "Descrição", valor: "Valor",
  conta_codigo: "Conta contábil", metodo: "Método", arquivo_origem: "Arquivo de origem",
  componente: "Componente", regra_id: "Regra",
};
const downloadNames = {
  "comissoes_por_lojista.csv": "Comissões",
  "divergencias_taxa.csv": "Divergências",
  "notas_a_emitir.csv": "Notas",
  "lancamentos_classificados.csv": "Extratos classificados",
  "pendencias.csv": "Pendências",
  "rastro.csv": "Rastro",
  "resumo.md": "Resumo",
  "execucao.log": "Log da execução",
};

const emptyState = document.querySelector("#empty-state");
const closureView = document.querySelector("#closure-view");
const uploadPanel = document.querySelector("#upload-panel");
const validationPanel = document.querySelector("#validation-panel");
const resultsPanel = document.querySelector("#results-panel");
const notice = document.querySelector("#notice");
const dialog = document.querySelector("#month-dialog");
const drawer = document.querySelector("#detail-drawer");

function setProcessing(message) {
  const busy = Boolean(message);
  document.querySelector("#processing-message").textContent = message || "";
  document.querySelector("#processing-status").hidden = !busy;
  closureView.setAttribute("aria-busy", String(busy));
  document.querySelectorAll("#new-closure, [data-create], .file-card input").forEach(element => {
    element.disabled = busy;
  });
}

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
    ["Lançamentos classificados", summary.bank_entries_count.toLocaleString("pt-BR"), "Extratos Aurora e Meridiano", false],
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
      const sourceButton = document.createElement("button");
      sourceButton.className = "source-row-button";
      sourceButton.type = "button";
      sourceButton.textContent = "Ver linha original";
      sourceButton.addEventListener("click", async () => {
        sourceButton.disabled = true;
        try {
          const params = new URLSearchParams({ arquivo: trace.arquivo_origem, ref_origem: trace.ref_origem });
          const sourceResult = await request(`/api/closures/${state.closureId}/source?${params}`);
          const sourceDetails = document.createElement("details");
          sourceDetails.className = "source-row-details";
          sourceDetails.open = true;
          const summary = document.createElement("summary");
          summary.textContent = "Linha como recebida";
          sourceDetails.append(summary);
          for (const [name, value] of Object.entries(sourceResult.linha)) {
            sourceDetails.append(displayValue(name, value));
          }
          item.append(sourceDetails);
          sourceButton.remove();
        } catch (error) {
          showNotice(error.message);
        } finally {
          sourceButton.disabled = false;
        }
      });
      item.append(sourceButton);
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
  const filesOf = card => state.files[card.dataset.slot] || [];
  const complete = cards.every(card => filesOf(card).length > 0);
  const total = cards.reduce((sum, card) => sum + filesOf(card).length, 0);
  cards.forEach(card => {
    const names = filesOf(card);
    card.classList.toggle("has-file", names.length > 0);
    card.querySelector(".file-name").textContent = names.length ? names.join(", ") : "Escolher arquivo(s)";
    card.querySelector(".file-clear").hidden = names.length === 0;
  });
  const missing = cards.filter(card => !filesOf(card).length).length;
  document.querySelector("#upload-status").textContent = complete
    ? `${total} arquivo${total === 1 ? "" : "s"} enviado${total === 1 ? "" : "s"}. Pronto para conferir.`
    : `${total} arquivo${total === 1 ? "" : "s"} enviado${total === 1 ? "" : "s"}; falta${missing === 1 ? "" : "m"} ${missing} tipo${missing === 1 ? "" : "s"} de arquivo.`;
  document.querySelector("#validate-files").disabled = !complete;
}

function normalizeHeader(text) {
  return text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/^\uFEFF/, "").toUpperCase();
}

function identifyFile(file) {
  const name = normalizeHeader(file.name);
  const extension = name.slice(name.lastIndexOf("."));
  const stem = name.slice(0, name.lastIndexOf("."));
  const patterns = [
    ["orbe", ".CSV", /(?:^|[^A-Z0-9])(?:ORBE|COMISS(?:AO|OES))(?:[^A-Z0-9]|$)/],
    ["taxas", ".XLSX", /(?:^|[^A-Z0-9])TAXAS?(?:[^A-Z0-9]|$)/],
    ["ponte", ".EML", /(?:^|[^A-Z0-9])(?:PONTE|CAMBIO|REMESSAS?)(?:[^A-Z0-9]|$)/],
    ["plano", ".CSV", /(?:^|[^A-Z0-9])(?:PLANO[\s_-]+(?:DE[\s_-]+)?CONTAS|FENIX)(?:[^A-Z0-9]|$)/],
    ["aurora", ".CSV", /(?:^|[^A-Z0-9])AURORA(?:[^A-Z0-9]|$)/],
    ["meridiano", ".OFX", /(?:^|[^A-Z0-9])MERIDIANO(?:[^A-Z0-9]|$)/],
  ];
  const matches = patterns.filter(([, expected, pattern]) => extension === expected && pattern.test(stem));
  if (matches.length !== 1) {
    throw new Error(`${file.name}: ${matches.length ? "nome ambíguo" : "tipo não identificado pelo nome"}. Use Orbe/comissões, taxas, Ponte/câmbio/remessas, plano de contas/Fênix, Aurora ou Meridiano no nome, com a extensão correspondente.`);
  }
  return matches[0][0];
}

async function uploadFile(file, slot) {
  const result = await request(`/api/closures/${state.closureId}/files/${slot}`, {
    method: "POST",
    headers: { "Content-Type": "application/octet-stream", "X-Filename": encodeURIComponent(file.name) },
    body: file,
  });
  state.files = result.files;
  updateFileStatus();
}

async function uploadBatch(fileList) {
  const errors = document.querySelector("#unidentified-files");
  errors.replaceChildren();
  errors.hidden = true;
  document.querySelectorAll(".file-card").forEach(card => card.classList.remove("unidentified"));
  notice.hidden = true;
  for (const file of fileList) {
    let slot;
    try {
      slot = identifyFile(file);
    } catch (error) {
      const item = document.createElement("li");
      item.textContent = error.message;
      errors.append(item);
      errors.hidden = false;
      continue;
    }
    await uploadFile(file, slot);
  }
}

function renderDownloads() {
  const root = document.querySelector("#download-links");
  root.replaceChildren(...Object.entries(downloadNames).map(([fileName, label]) => {
    const link = document.createElement("a");
    link.className = "download-link";
    link.href = `/api/closures/${state.closureId}/download/${fileName}`;
    link.download = fileName;
    link.textContent = `↓ ${label}`;
    return link;
  }));
}

function createField(labelText, control, wide = false) {
  const wrapper = document.createElement("label");
  wrapper.className = `field-label${wide ? " wide" : ""}`;
  wrapper.append(document.createTextNode(labelText), control);
  return wrapper;
}

function createControl(tag, options = {}) {
  const control = document.createElement(tag);
  control.className = tag === "select" ? "" : "text-input";
  control.required = Boolean(options.required);
  control.name = options.name;
  if (tag === "textarea") control.rows = 2;
  if (options.placeholder) control.placeholder = options.placeholder;
  if (tag === "input") control.type = options.type || "text";
  return control;
}

const agentLabels = {
  classificador: "Classificador",
  interprete_taxas: "Intérprete de taxas",
  investigador: "Investigador",
};

function renderAgentWorking(activity) {
  const events = activity.events || [];
  const last = events.at(-1);
  const active = activity.status === "running" && activity.execution?.status === "EXECUTANDO";
  const working = active && last?.etapa === "agente" && last.status === "iniciada";
  const indicator = document.querySelector("#agent-working");
  indicator.hidden = !working;
  document.querySelector(".agent-activity").setAttribute("aria-busy", String(Boolean(working)));
  if (working) {
    const name = agentLabels[last.detalhe.agente] || last.detalhe.agente;
    document.querySelector("#agent-working-name").textContent = `${name} trabalhando…`;
    document.querySelector("#agent-working-detail").textContent = `Analisando o item ${last.detalhe.id_saida}. Aguarde a resposta do agente.`;
  }
}

function renderAgentCalls(calls, running = false) {
  const root = document.querySelector("#agent-calls");
  if (!calls.length) {
    const empty = document.createElement("p");
    empty.className = "helper-text";
    empty.textContent = running ? "Aguardando a conclusão das chamadas dos agentes…" : "Nenhuma chamada de agente registrada nesta execução.";
    root.replaceChildren(empty);
    return;
  }
  root.replaceChildren(...calls.map(call => {
    const item = document.createElement("div");
    item.className = "agent-call";
    const name = document.createElement("strong");
    name.textContent = `${agentLabels[call.agente] || call.agente} · ${call.id_saida}`;
    const details = document.createElement("span");
    details.className = "agent-call-meta";
    details.textContent = `${call.origem} · ${call.resultado}${call.detalhe ? ` · ${call.detalhe}` : ""}`;
    item.append(name, details);
    return item;
  }));
}

function renderExecutionEvents(events) {
  const root = document.querySelector("#execution-events");
  const labelsByStage = {
    ingestao: "Leitura dos arquivos",
    checkout: "Conciliação Orbe",
    divergencias: "Apuração de divergências",
    remessa: "Conciliação de remessas",
    notas: "Notas a emitir",
    bancos: "Classificação bancária",
    agentes: "Revisão assistida",
    consolidacao: "Validação e consolidação",
  };
  root.replaceChildren(...events.filter(event => event.etapa !== "agente").map(event => {
    const item = document.createElement("li");
    item.className = "event-item";
    const name = document.createElement("strong");
    name.textContent = labelsByStage[event.etapa] || event.etapa;
    const detail = document.createElement("span");
    detail.className = "event-detail";
    detail.textContent = Object.entries(event.detalhe || {}).map(([key, value]) => `${key}: ${value}`).join(" · ") || "Etapa registrada pelo motor";
    const status = document.createElement("span");
    status.className = "event-status";
    status.textContent = event.status === "executada" ? "Concluída" : event.status;
    item.append(name, detail, status);
    return item;
  }));
}

async function loadActivity() {
  const activity = await request(`/api/closures/${state.closureId}/activity`);
  const stageLabels = {
    EXECUTANDO: "Execução em andamento",
    CONCLUIDA: "Execução concluída",
    ERRO: "Execução com erro",
  };
  document.querySelector("#execution-title").textContent =
    stageLabels[activity.execution?.status] || "Acompanhamento do motor";
  document.querySelector("#execution-status").textContent = activity.error ||
    (activity.execution?.terminada_em ? `Finalizada em ${activity.execution.terminada_em}` : "Preparando etapas e checkpoints…");
  const badge = document.querySelector("#execution-badge");
  badge.textContent = stageLabels[activity.execution?.status] || activity.status;
  badge.className = `badge ${activity.status === "running" ? "badge-running" : activity.status === "failed" ? "badge-blocked" : "badge-success"}`;
  renderExecutionEvents(activity.events || []);
  renderAgentWorking(activity);
  renderAgentCalls(activity.agent_calls || [], activity.status === "running");
}

function renderDecisionFields(container, decisionType, scope, item) {
  container.replaceChildren();
  if (decisionType === "NOTA") {
    const note = createControl("textarea", { name: "texto", required: true, placeholder: "Descreva a decisão para este caso." });
    container.append(createField("Decisão registrada", note, true));
    return;
  }
  if (decisionType === "CONTA") {
    const account = document.createElement("select");
    account.name = "conta";
    account.required = true;
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "Selecione uma conta analítica";
    account.append(placeholder);
    for (const entry of state.accounts) {
      const option = document.createElement("option");
      option.value = entry.codigo;
      option.textContent = `${entry.codigo} · ${entry.descricao}`;
      account.append(option);
    }
    container.append(createField("Conta contábil", account, true));
    if (scope === "regra") {
      const bank = document.createElement("select");
      bank.name = "banco";
      bank.required = true;
      for (const [value, label] of [["AURORA", "Banco Aurora"], ["MERIDIANO", "Banco Meridiano"]]) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = label;
        bank.append(option);
      }
      const pattern = createControl("input", { name: "padrao", required: true, placeholder: "Regex aplicada à descrição" });
      container.append(createField("Banco", bank), createField("Padrão (regex)", pattern));
    }
    return;
  }
  if (decisionType === "EC_LOJISTA") {
    const ec = createControl("input", { name: "ec", required: true, placeholder: "Código EC" });
    const cnpj = createControl("input", { name: "cnpj", required: true, placeholder: "CNPJ do lojista" });
    container.append(createField("EC", ec), createField("CNPJ", cnpj));
  }
}

function renderQueue(items) {
  const root = document.querySelector("#queue-items");
  const empty = document.querySelector("#queue-empty");
  const badge = document.querySelector("#queue-count");
  badge.textContent = `${items.length} ${items.length === 1 ? "pendência" : "pendências"} · ${state.blockingCount} bloqueante(s)`;
  empty.hidden = items.length !== 0;
  root.hidden = items.length === 0;
  root.replaceChildren(...items.map(item => {
    const card = document.createElement("article");
    card.className = "queue-item";
    const header = document.createElement("div");
    header.className = "queue-item-heading";
    const headingBlock = document.createElement("div");
    const title = document.createElement("h3");
    title.textContent = `${item.tipo} · ${item.id_saida}`;
    const metadata = document.createElement("p");
    metadata.className = "queue-metadata";
    metadata.textContent = `${item.ref_origem} · ${formatValue("valor_brl", item.valor_brl)} · Responsável: ${item.quem_decide}`;
    headingBlock.append(title, metadata);
    const status = document.createElement("span");
    status.className = `badge ${item.bloqueante === "S" ? "badge-blocked" : "badge-running"}`;
    status.textContent = item.bloqueante === "S" ? "Bloqueante" : item.estado;
    header.append(headingBlock, status);
    const reason = document.createElement("p");
    reason.textContent = item.motivo;
    card.append(header, reason);
    if (item.proposta) {
      const proposal = document.createElement("p");
      proposal.textContent = `Proposta do agente: ${typeof item.proposta === "string" ? item.proposta : JSON.stringify(item.proposta)}`;
      card.append(proposal);
    }

    const form = document.createElement("form");
    form.className = "decision-form";
    const type = document.createElement("select");
    type.name = "tipo_decisao";
    for (const [value, label] of [
      ["NOTA", "Registrar observação"],
      ["CONTA", "Atribuir conta contábil"],
      ["EC_LOJISTA", "Vincular EC a lojista"],
    ]) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      type.append(option);
    }
    const scope = document.createElement("select");
    scope.name = "escopo";
    for (const [value, label] of [["caso", "Somente este caso"], ["regra", "Promover como regra"]]) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      scope.append(option);
    }
    const dynamicFields = document.createElement("div");
    dynamicFields.className = "decision-fields wide";
    const author = createControl("input", { name: "autor", required: true, placeholder: "Nome de quem decide" });
    author.value = "Financeiro";
    const reasonInput = createControl("input", { name: "motivo", required: true, placeholder: "Justificativa da decisão" });
    const submit = document.createElement("button");
    submit.className = "button button-primary wide";
    submit.type = "submit";
    submit.textContent = "Registrar decisão e reexecutar";
    const scopeField = createField("Aplicação", scope);
    form.append(createField("Tipo de decisão", type), scopeField, dynamicFields,
      createField("Responsável", author), createField("Motivo", reasonInput), submit);
    const updateFields = () => {
      scopeField.hidden = type.value !== "CONTA";
      if (type.value === "EC_LOJISTA") scope.value = "regra";
      else if (type.value === "NOTA") scope.value = "caso";
      scope.disabled = type.value !== "CONTA";
      renderDecisionFields(dynamicFields, type.value, scope.value, item);
    };
    type.addEventListener("change", updateFields);
    scope.addEventListener("change", updateFields);
    updateFields();
    form.addEventListener("submit", async event => {
      event.preventDefault();
      submit.disabled = true;
      const data = Object.fromEntries(new FormData(form));
      data.id_saida = item.id_saida;
      try {
        await request(`/api/closures/${state.closureId}/decisions`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        });
        document.querySelector("#execution-panel").hidden = false;
        await monitorExecution();
        showNotice("Decisão registrada. O motor está reexecutando as etapas afetadas.", false);
      } catch (error) {
        showNotice(error.message);
        submit.disabled = false;
      }
    });
    card.append(form);
    return card;
  }));
}

async function loadQueue() {
  const queue = await request(`/api/closures/${state.closureId}/queue`);
  if (!state.closed) {
    const accountResult = await request(`/api/closures/${state.closureId}/accounts`);
    state.accounts = accountResult.accounts;
  }
  state.blockingCount = queue.blocking_count;
  renderQueue(queue.items);
  document.querySelector("#validation-queue").hidden = false;
  updateClosePanel();
}

function updateClosePanel() {
  const panel = document.querySelector("#close-panel");
  panel.hidden = false;
  const closedRecord = state.closureRecord;
  const form = document.querySelector("#close-form");
  const message = document.querySelector("#close-message");
  const button = document.querySelector("#close-confirm");
  if (state.closed && closedRecord) {
    document.querySelector("#close-title").textContent = "Competência fechada";
    message.textContent = `Fechada por ${closedRecord.closed_by} em ${closedRecord.closed_at}. Snapshot SHA-256 registrado para cada arquivo de saída.`;
    form.hidden = true;
    return;
  }
  document.querySelector("#close-title").textContent = "Revisão final";
  form.hidden = false;
  button.disabled = state.blockingCount > 0;
  message.textContent = state.blockingCount > 0
    ? `Resolva as ${state.blockingCount} pendência(s) bloqueante(s) e reexecute antes de fechar.`
    : "Sem pendências bloqueantes. Registre o responsável e a justificativa para fechar.";
}

async function showCompletedClosure(result) {
  state.month = result.month;
  state.closed = result.closed;
  state.closureRecord = result.closure_record;
  uploadPanel.hidden = true;
  validationPanel.hidden = true;
  document.querySelector("#execution-panel").hidden = false;
  resultsPanel.hidden = false;
  document.querySelector("#results-month").textContent = formatMonth(result.month);
  document.querySelector("#download-all").href = `/api/closures/${state.closureId}/download/todos.zip`;
  renderSummary(document.querySelector("#results-summary"), result.summary);
  renderDownloads();
  await Promise.all([loadActivity(), loadQueue()]);
  await selectTable(state.table || "comissoes");
  setWorkflow(state.closed ? "close" : state.blockingCount ? "validation" : "outputs");
}

async function monitorExecution() {
  if (state.eventSource) state.eventSource.close();
  const panel = document.querySelector("#execution-panel");
  const runButton = document.querySelector("#run-closure");
  runButton.disabled = true;
  runButton.textContent = "Executando motor…";
  document.querySelectorAll(".decision-form button").forEach(button => { button.disabled = true; });
  document.querySelector("#close-confirm").disabled = true;
  panel.hidden = false;
  document.querySelector("#execution-title").textContent = "Execução em andamento";
  document.querySelector("#execution-status").textContent = "Acompanhando as etapas do motor em tempo real…";
  document.querySelector("#execution-badge").textContent = "Executando";
  document.querySelector("#execution-badge").className = "badge badge-running";
  document.querySelector("#execution-events").replaceChildren();
  document.querySelector("#agent-calls").replaceChildren();
  document.querySelector("#agent-working").hidden = true;
  setWorkflow("run");
  await loadActivity();
  const source = new EventSource(`/api/closures/${state.closureId}/events`);
  state.eventSource = source;
  source.addEventListener("progress", () => {
    loadActivity().catch(error => showNotice(error.message));
  });
  source.addEventListener("complete", async event => {
    source.close();
    state.eventSource = null;
    document.querySelector("#agent-working").hidden = true;
    document.querySelector(".agent-activity").setAttribute("aria-busy", "false");
    const result = JSON.parse(event.data);
    if (result.status === "completed" || result.status === "closed") {
      await showCompletedClosure(result);
      showNotice("Execução concluída. Confira as saídas e a fila de validações.", false);
    } else {
      document.querySelector("#execution-title").textContent = "Execução com erro";
      document.querySelector("#execution-status").textContent = result.error || "O motor não concluiu esta execução.";
      document.querySelector("#execution-badge").textContent = "Erro";
      document.querySelector("#execution-badge").className = "badge badge-blocked";
      showNotice(result.error || "O motor não concluiu esta execução.");
      setWorkflow("run");
      document.querySelectorAll(".decision-form button").forEach(button => { button.disabled = false; });
    }
    runButton.disabled = false;
    runButton.innerHTML = 'Executar fechamento <span aria-hidden="true">→</span>';
  });
}

async function startRun() {
  await request(`/api/closures/${state.closureId}/run`, { method: "POST" });
  validationPanel.hidden = true;
  resultsPanel.hidden = true;
  await monitorExecution();
}

async function restoreSavedClosure() {
  const closureId = localStorage.getItem("tarvo.closureId");
  if (!closureId) return;
  try {
    const result = await request(`/api/closures/${closureId}`);
    state.closureId = result.id;
    state.month = result.month;
    state.files = result.files;
    state.closed = result.closed;
    state.closureRecord = result.closure_record;
    emptyState.hidden = true;
    closureView.hidden = false;
    document.querySelector("#month-label").textContent = formatMonth(result.month);
    updateFileStatus();
    if (result.status === "uploading") {
      uploadPanel.hidden = false;
      validationPanel.hidden = true;
      resultsPanel.hidden = true;
      setWorkflow("files");
    } else if (result.status === "validated" || result.status === "failed") {
      uploadPanel.hidden = true;
      validationPanel.hidden = false;
      resultsPanel.hidden = true;
      if (result.summary) renderSummary(document.querySelector("#preview-summary"), result.summary);
      document.querySelector("#run-closure").textContent = result.status === "failed" ? "Tentar novamente →" : "Executar fechamento →";
      setWorkflow("run");
      if (result.status === "failed") {
        document.querySelector("#execution-panel").hidden = false;
        await loadActivity();
      }
    } else if (result.status === "running") {
      uploadPanel.hidden = true;
      validationPanel.hidden = true;
      await monitorExecution();
    } else if (result.status === "completed" || result.status === "closed") {
      await showCompletedClosure(result);
    }
  } catch (error) {
    showNotice(`Não foi possível restaurar o fechamento salvo: ${error.message}`);
  }
}

async function createClosure() {
  const month = document.querySelector("#month-input").value;
  if (!month) return;
  try {
    if (state.eventSource) state.eventSource.close();
    state.eventSource = null;
    const result = await request("/api/closures", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ month }),
    });
    state.closureId = result.id;
    localStorage.setItem("tarvo.closureId", result.id);
    state.month = result.month;
    state.files = {};
    state.table = "comissoes";
    state.rows = [];
    emptyState.hidden = true;
    closureView.hidden = false;
    uploadPanel.hidden = false;
    validationPanel.hidden = true;
    resultsPanel.hidden = true;
    document.querySelector("#execution-panel").hidden = true;
    document.querySelector("#validation-queue").hidden = true;
    document.querySelector("#close-panel").hidden = true;
    state.closed = false;
    state.closureRecord = null;
    state.accounts = [];
    state.blockingCount = 0;
    document.querySelector("#month-label").textContent = formatMonth(result.month);
    document.querySelector("#table-search").value = "";
    document.querySelector("#batch-files").value = "";
    document.querySelectorAll(".file-card input").forEach(input => { input.value = ""; });
    document.querySelector("#unidentified-files").replaceChildren();
    document.querySelector("#unidentified-files").hidden = true;
    document.querySelectorAll(".file-card").forEach(card => card.classList.remove("unidentified"));
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
    const files = [...input.files];
    if (!files.length) return;
    try {
      await uploadBatch(files);
      input.closest(".file-card").classList.toggle("unidentified", !document.querySelector("#unidentified-files").hidden);
    } catch (error) {
      showNotice(error.message);
      input.value = "";
    }
  });
});
document.querySelectorAll(".file-clear").forEach(button => {
  button.addEventListener("click", async event => {
    event.preventDefault();
    event.stopPropagation();
    const slot = button.closest(".file-card").dataset.slot;
    try {
      const result = await request(`/api/closures/${state.closureId}/files/${slot}`, { method: "DELETE" });
      state.files = result.files;
      button.closest(".file-card").querySelector("input").value = "";
      updateFileStatus();
      notice.hidden = true;
    } catch (error) {
      showNotice(error.message);
    }
  });
});
const batchDropzone = document.querySelector("#batch-dropzone");
const batchInput = document.querySelector("#batch-files");
batchInput.addEventListener("change", async () => {
  if (!batchInput.files.length) return;
  try {
    await uploadBatch(batchInput.files);
  } catch (error) {
    showNotice(error.message);
  } finally {
    batchInput.value = "";
  }
});
batchDropzone.addEventListener("dragover", event => {
  event.preventDefault();
  batchDropzone.classList.add("drag-over");
});
batchDropzone.addEventListener("dragleave", event => {
  if (!batchDropzone.contains(event.relatedTarget)) batchDropzone.classList.remove("drag-over");
});
batchDropzone.addEventListener("drop", async event => {
  event.preventDefault();
  batchDropzone.classList.remove("drag-over");
  try {
    await uploadBatch(event.dataTransfer.files);
  } catch (error) {
    showNotice(error.message);
  }
});
batchDropzone.addEventListener("keydown", event => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    batchInput.click();
  }
});
document.querySelector("#validate-files").addEventListener("click", async event => {
  const button = event.currentTarget;
  button.disabled = true;
  button.textContent = "Conferindo arquivos…";
  setProcessing("Conferindo os arquivos do fechamento…");
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
    setProcessing(null);
    button.innerHTML = 'Conferir arquivos <span aria-hidden="true">→</span>';
    button.disabled = false;
    updateFileStatus();
  }
});
document.querySelector("#run-closure").addEventListener("click", async event => {
  const button = event.currentTarget;
  button.disabled = true;
  button.textContent = "Executando motor…";
  try {
    await startRun();
    notice.hidden = true;
  } catch (error) {
    showNotice(error.message);
    setWorkflow("run");
  } finally {
    if (!state.eventSource) {
      button.disabled = false;
      button.innerHTML = 'Executar fechamento <span aria-hidden="true">→</span>';
    }
  }
});
document.querySelector("#close-form").addEventListener("submit", async event => {
  event.preventDefault();
  const button = document.querySelector("#close-confirm");
  button.disabled = true;
  try {
    const result = await request(`/api/closures/${state.closureId}/close`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        autor: document.querySelector("#close-author").value,
        motivo: document.querySelector("#close-reason").value,
      }),
    });
    state.closed = result.closed;
    state.closureRecord = result.closure_record;
    await showCompletedClosure(result);
    showNotice("Competência fechada e snapshot das saídas registrado.", false);
  } catch (error) {
    showNotice(error.message);
  } finally {
    button.disabled = state.blockingCount > 0 || state.closed;
  }
});
document.querySelectorAll(".tab").forEach(tab => tab.addEventListener("click", () => selectTable(tab.dataset.table)));
document.querySelector("#table-search").addEventListener("input", renderTable);
document.querySelector("#close-drawer").addEventListener("click", closeDrawer);
document.querySelector("#drawer-backdrop").addEventListener("click", closeDrawer);
const navLinks = [...document.querySelectorAll(".main-nav .nav-link")];
function setActiveNav(link) {
  navLinks.forEach(item => {
    const active = item === link;
    item.classList.toggle("active", active);
    if (active) item.setAttribute("aria-current", "page");
    else item.removeAttribute("aria-current");
  });
}
const navLinkFor = id => navLinks.find(item => item.dataset.section === id);
let navLockUntil = 0;
function syncNavWithScroll() {
  if (Date.now() < navLockUntil) return;
  const line = window.innerHeight * 0.4;
  const atBottom = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4;
  let current = "fechamentos";
  for (const id of ["validation-queue", "downloads"]) {
    const section = document.querySelector(`#${id}`);
    if (!section || !section.offsetParent) continue;
    if (section.getBoundingClientRect().top <= line) current = id;
  }
  if (atBottom && document.querySelector("#downloads").offsetParent && window.scrollY > 0) current = "downloads";
  setActiveNav(navLinkFor(current));
}
window.addEventListener("scroll", syncNavWithScroll, { passive: true });
window.addEventListener("resize", syncNavWithScroll);
navLinks.forEach(link => link.addEventListener("click", event => {
  event.preventDefault();
  const id = link.dataset.section;
  if (id === "fechamentos") {
    notice.hidden = true;
    setActiveNav(link);
    navLockUntil = Date.now() + 800;
    window.scrollTo({ top: 0, behavior: "smooth" });
    return;
  }
  const section = document.querySelector(`#${id}`);
  if (closureView.hidden || !section || !section.offsetParent) {
    showNotice("Abra ou conclua um fechamento para acessar esta seção.", false);
    return;
  }
  notice.hidden = true;
  setActiveNav(link);
  navLockUntil = Date.now() + 800;
  if (id === "downloads") window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "smooth" });
  else section.scrollIntoView({ behavior: "smooth", block: "start" });
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
restoreSavedClosure();
