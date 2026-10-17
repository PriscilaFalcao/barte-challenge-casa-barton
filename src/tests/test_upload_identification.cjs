const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");

const source = readFileSync(path.join(__dirname, "..", "tarvo", "web", "app.js"), "utf8");
const functions = source.slice(source.indexOf("function normalizeHeader("), source.indexOf("function renderDownloads("));

function setup() {
  const errors = {
    hidden: true,
    items: [],
    replaceChildren() { this.items = []; },
    append(item) { this.items.push(item); },
  };
  const uploads = [];
  const context = vm.createContext({
    state: { closureId: "test" },
    notice: { hidden: false },
    document: {
      querySelector: () => errors,
      querySelectorAll: () => [],
      createElement: () => ({ textContent: "" }),
    },
    request: async (url, options) => {
      uploads.push({ url, name: decodeURIComponent(options.headers["X-Filename"]) });
      return { files: {} };
    },
    updateFileStatus() {},
  });
  vm.runInContext(functions, context);
  return { context, errors, uploads };
}

test("identifies renamed sources, accents, separators and case without reading content", () => {
  const { context } = setup();
  for (const [name, expected] of [
    ["01_orbe_relatorio_comissoes_set2026.csv", "orbe"],
    ["06_orbe_ajustes_tardios_out2026.csv", "orbe"],
    ["Comissão outubro.CSV", "orbe"],
    ["comissões-2026.csv", "orbe"],
    ["Novas TAXAS contratadas.xlsx", "taxas"],
    ["relatório câmbio.eml", "ponte"],
    ["remessas outubro.eml", "ponte"],
    ["plano-de-contas-2027.csv", "plano"],
    ["plano_contas.csv", "plano"],
    ["Fênix exportação.csv", "plano"],
    ["extrato_AURORA_2026.csv", "aurora"],
    ["Meridiano outubro.OFX", "meridiano"],
  ]) {
    assert.equal(context.identifyFile({ name }), expected, name);
  }
});

test("rejects unknown, ambiguous and incompatible names instead of guessing by extension", () => {
  const { context } = setup();
  for (const name of ["arquivo.csv", "arquivo.xlsx", "arquivo.eml", "arquivo.ofx", "aurora_orbe.csv", "taxas.csv", "minhaorbe.csv", "orbe.pdf"]) {
    assert.throws(() => context.identifyFile({ name }), /nome/, name);
  }
});

test("mixed batch uploads recognized files to their destination and lists every rejection", async () => {
  const { context, errors, uploads } = setup();
  await context.uploadBatch([{ name: "desconhecido.csv" }, { name: "aurora.csv" }, { name: "orbe_aurora.csv" }, { name: "taxas.xlsx" }]);
  assert.deepEqual(uploads.map(upload => upload.url), ["/api/closures/test/files/aurora", "/api/closures/test/files/taxas"]);
  assert.equal(errors.hidden, false);
  assert.equal(errors.items.length, 2);
  assert.match(errors.items[0].textContent, /desconhecido.csv/);
  assert.match(errors.items[1].textContent, /ambíguo/);
  await context.uploadBatch([{ name: "ponte.eml" }]);
  assert.equal(errors.hidden, true);
  assert.equal(errors.items.length, 0);
});
