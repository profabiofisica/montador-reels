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
const d = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const lhr = d.lhr || d;
let n = 0;
const anda = (o) => { if (Array.isArray(o)) return o.forEach(anda); if (o && typeof o === 'object') for (const k of Object.keys(o)) { const v = o[k]; if (typeof v === 'string' && dic.has(v)) { o[k] = dic.get(v); n++; } else anda(v); } };
anda(lhr.categories); anda(lhr.audits); anda(lhr.categoryGroups); if (lhr.i18n) anda(lhr.i18n.rendererFormattedStrings);
const rf = {};
for (const [id, v] of Object.entries(pt)) { const m = id.match(/^report\/renderer\/[a-z-]+\.js \| (\w+)$/); if (m) rf[m[1]] = v.message; }
lhr.i18n = lhr.i18n || {}; lhr.i18n.rendererFormattedStrings = Object.assign(lhr.i18n.rendererFormattedStrings || {}, rf);
lhr.configSettings.locale = 'pt-BR';
fs.writeFileSync(process.argv[3], ReportGenerator.generateReportHtml(lhr));
console.log('ok', n, 'textos em português;', lhr.categories.performance.title);
