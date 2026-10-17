// Renderizador de texto da aba "Contestações": monta DOM com textContent, sem innerHTML.
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");

const source = readFileSync(path.join(__dirname, "..", "tarvo", "web", "app.js"), "utf8");
const trecho = source.slice(source.indexOf("function appendInline("), source.indexOf("function renderDocument("));

class No {
  constructor(tag) { this.tag = tag; this.children = []; this.textContent = ""; }
  append(...itens) { this.children.push(...itens); }
}
const documentoFalso = {
  createElement: tag => new No(tag),
  createTextNode: texto => ({ tag: "#text", textContent: texto }),
  createDocumentFragment: () => new No("#fragment"),
};
const contexto = vm.createContext({ document: documentoFalso });
vm.runInContext(`${trecho}; globalThis.renderMarkdown = renderMarkdown;`, contexto);

const texto = [
  "# Título", "", "> **Rascunho**, não enviado.", "", "## Ponte", "",
  "**Para:** Backoffice", "**De:** Financeiro", "",
  "| Natureza | Valor |", "|---|---|", "| Excesso | R$ 1.418,85 |", "| Duplicidade | R$ 410,94 |", "",
  "- item `a`", "- item b", "", "<script>alert(1)</script>",
].join("\n");

const tags = no => [no.tag, ...(no.children || []).flatMap(tags)];

test("monta título, citação, tabela e lista", () => {
  const raiz = contexto.renderMarkdown(texto);
  const todas = tags(raiz);
  for (const esperado of ["h1", "blockquote", "h2", "table", "thead", "tbody", "ul", "li", "strong", "code", "br"]) {
    assert.ok(todas.includes(esperado), `faltou ${esperado}`);
  }
  assert.equal(todas.filter(t => t === "td").length, 4);
});

test("conteúdo vira texto, nunca HTML", () => {
  const raiz = contexto.renderMarkdown(texto);
  const todas = tags(raiz);
  assert.ok(!todas.includes("script"));
  const textos = [];
  const colher = no => { if (no.tag === "#text") textos.push(no.textContent); no.children?.forEach(colher); };
  colher(raiz);
  assert.ok(textos.includes("<script>alert(1)</script>"));
});
