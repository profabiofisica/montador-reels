// Relatório oficial do Lighthouse (o mesmo motor do pagespeed.web.dev) a partir do resultado real da API, em português.
import fs from 'fs';
import {createRequire} from 'module';
import {ReportGenerator} from 'lighthouse/report/generator/report-generator.js';
const req = createRequire(import.meta.url);
const base = req.resolve('lighthouse/package.json').replace(/package\.json$/, '') + 'shared/localization/locales/';
const en = JSON.parse(fs.readFileSync(base + 'en-US.json', 'utf8'));
const pt = JSON.parse(fs.readFileSync(base + 'pt.json', 'utf8'));
const dic = new Map();
for (const [id, v] of Object.entries(en)) if (pt[id] && !/[{}]/.test(v.message)) dic.set(v.message, pt[id].message);
// 05/11/2026: textos com valor no meio ("Est savings of 720 ms", "4 long tasks found") ficavam em inglês
const re = [];
const esc = (s) => s.replace(/[.*+?^$()|[\]\\]/g, '\\$&');
for (const [id, v] of Object.entries(en)) {
  const m = v.message, p2 = pt[id] && pt[id].message;
  if (!p2 || !/\{\w+\}/.test(m) || /\{\w+,/.test(m) || /\{\w+,/.test(p2)) continue;
  const nomes = [...m.matchAll(/\{(\w+)\}/g)].map((x) => x[1]);
  const fonte = '^' + m.split(/\{\w+\}/).map(esc).join('(.+?)') + '$';
  try { re.push([new RegExp(fonte), nomes, p2]); } catch (e) { }
}
// títulos mais novos do PageSpeed que ainda não estão no pacote de tradução
const extra = new Map([['Render-blocking requests', 'Solicitações que bloqueiam a renderização'], ['Network dependency tree', 'Árvore de dependência da rede'],
  ['Improve image delivery', 'Melhorar a entrega de imagens'], ['Forced reflow', 'Reflow forçado'], ['LCP breakdown', 'Detalhamento da LCP'], ['3rd parties', 'Terceiros'],
  ['Optimize DOM size', 'Otimizar o tamanho do DOM'], ['Use efficient cache lifetimes', 'Use ciclos de vida eficientes de cache'], ['Legacy JavaScript', 'JavaScript legado'],
  ['Document request latency', 'Latência de solicitação de documentos'], ['Font display', 'Exibição de fontes'], ['Duplicated JavaScript', 'JavaScript duplicado'],
  ['HTML5 landmark elements are used to improve navigation', 'Elementos de ponto de referência do HTML5 são usados para melhorar a navegação'],
  ['Offscreen content is hidden from assistive technology', 'O conteúdo fora da tela fica oculto para a tecnologia assistiva'],
  ['Custom controls have associated labels', 'Os controles personalizados têm rótulos associados'], ['Custom controls have ARIA roles', 'Os controles personalizados têm funções ARIA'],
  ['Interactive controls are keyboard focusable', 'Os controles interativos podem ser focados pelo teclado'], ['Interactive elements indicate their purpose and state', 'Os elementos interativos indicam a finalidade e o estado'],
  ['The page has a logical tab order', 'A página tem uma ordem lógica de tabulação'], ['Visual order on the page follows DOM order', 'A ordem visual da página segue a ordem do DOM'],
  ['User focus is not accidentally trapped in a region', 'O foco do usuário não fica preso por acidente em uma região'], ["The user's focus is directed to new content added to the page", 'O foco do usuário vai para o conteúdo novo adicionado à página'],
  ['HTML5 landmark elements are used to improve navigation.', 'Elementos de ponto de referência do HTML5 são usados para melhorar a navegação.']]);
const traduz = (v) => {
  if (dic.has(v)) return dic.get(v);
  if (extra.has(v)) return extra.get(v);
  if (v.length > 200) return null;
  for (const [r, nomes, p2] of re) { const m = v.match(r); if (m) { let s = p2; nomes.forEach((nm, i) => { s = s.split('{' + nm + '}').join(m[i + 1]); }); return s; } }
  const sv = v.match(/^Est savings of (.+)$/); if (sv) return 'Economia estimada de ' + sv[1];
  const lt = v.match(/^(\d+) long tasks? found$/); if (lt) return lt[1] + (lt[1] === '1' ? ' tarefa longa encontrada' : ' tarefas longas encontradas');
  return null;
};
const d = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const lhr = d.lhr || d;
let n = 0;
const anda = (o) => { if (Array.isArray(o)) return o.forEach(anda); if (o && typeof o === 'object') for (const k of Object.keys(o)) { const v = o[k]; if (typeof v === 'string') { const x = traduz(v); if (x !== null) { o[k] = x; n++; } } else anda(v); } };
anda(lhr.categories); anda(lhr.audits); anda(lhr.categoryGroups); if (lhr.i18n) anda(lhr.i18n.rendererFormattedStrings);
const rf = {};
for (const [id, v] of Object.entries(pt)) { const m = id.match(/^report\/renderer\/[a-z-]+\.js \| (\w+)$/); if (m) rf[m[1]] = v.message; }
lhr.i18n = lhr.i18n || {}; lhr.i18n.rendererFormattedStrings = Object.assign(lhr.i18n.rendererFormattedStrings || {}, rf);
lhr.configSettings.locale = 'pt-BR';
fs.writeFileSync(process.argv[3], ReportGenerator.generateReportHtml(lhr));
console.log('ok', n, 'textos em português;', lhr.categories.performance.title);
