/**
 * Revisora Editorial RCA — pré-auditoria automatizada.
 * IMPORTANTE: não faz fact-checking semântico e NUNCA aprova publicação.
 * Cada alegação material exige fonte conferida pela Social, seguida de aprovação da direção.
 */
import fs from 'node:fs';
import crypto from 'node:crypto';

const URL_PADRAO = 'https://agenciarca.com.br/blog/pane-microsoft-phishing-golpes-email/';
const url = process.env.ARTIGO_URL || URL_PADRAO;
const BASE = new URL('https://agenciarca.com.br');
const normaliza = s => s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
const limpar = s => s.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, ' ')
  .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, ' ')
  .replace(/<[^>]*>/g, ' ').replace(/&[^;\s]{2,8};/g, ' ').replace(/\s+/g, ' ').trim();
const achados = [];
const apontar = (nivel, descricao) => achados.push({nivel,descricao});
function aprovadaURL(s) {
  try {
    const u = new URL(s);
    if (!['https:', 'http:'].includes(u.protocol)) return false;
    const h = u.hostname.toLowerCase();
    return h !== 'localhost' && !h.endsWith('.local') && !/^127\.|^10\.|^192\.168\.|^169\.254\.|^172\.(1[6-9]|2[0-9]|3[01])\./.test(h);
  } catch { return false; }
}
async function buscar(u, timeoutMs=14000) {
  if (!aprovadaURL(u)) throw new Error('endereço não público ou inválido');
  const r = await fetch(u, {headers: {'user-agent':'RCA-RevisoraEditorial/1.0'}, signal: AbortSignal.timeout(timeoutMs), redirect:'follow'});
  if (!r.ok) throw new Error('HTTP '+r.status);
  const type=r.headers.get('content-type')||'';
  if (!/html|text|json|pdf/i.test(type)) throw new Error('tipo de resposta inesperado: '+type);
  const texto=await r.text();
  if (texto.length>2_000_000) throw new Error('resposta acima de 2 MB');
  return {texto, final:r.url, status:r.status};
}
const rel = {
  url_artigo:url, analisado_em_utc:new Date().toISOString(), executado:'GitHub Actions',
  motor:'pré-auditoria técnica; NÃO é fact-checking semântico',
  resultado:'BLOQUEADO — aguarda checagem individual das afirmações pela Social e aprovação da direção',
  aprovado_pela_revisora:false, autorizacao_publicacao:false,
  versao_sha256:null, titulos:[], links:[], achados, fontes_semanticamente_conferidas:0
};
try {
  const u=new URL(url);
  if (u.protocol !== 'https:' || !['agenciarca.com.br','www.agenciarca.com.br'].includes(u.hostname))
    throw new Error('A URL do artigo deve ser HTTPS e pertencer à RCA');
  const {texto}=await buscar(url);
  rel.versao_sha256=crypto.createHash('sha256').update(texto).digest('hex');
  rel.titulos=[...texto.matchAll(/<(h[1-3])\b[^>]*>([\s\S]*?)<\/\1>/gi)]
    .map(m=>({nivel:m[1].toLowerCase(),texto:limpar(m[2])}));
  const corpo=normaliza(limpar(texto));
  const descr=texto.match(/<meta\s+[^>]*name=["']description["'][^>]*content=["']([^"']+)/i);
  if (!rel.titulos.some(h=>h.nivel==='h1')) apontar('MAIOR','Nenhum H1 encontrado');
  if (rel.titulos.filter(h=>h.nivel==='h1').length>1) apontar('MAIOR','H1 múltiplos');
  if (rel.titulos.filter(h=>h.nivel==='h2').length<2) apontar('MAIOR','Menos de dois H2');
  if (!descr) apontar('MAIOR','Meta description não encontrada na página HTML');
  else if (descr[1].length>160) apontar('MENOR','Meta description muito longa');
  for (const clich of ['no mundo digital de hoje','mais do que nunca','e fundamental destacar',
  'vale ressaltar','neste cenario','a pergunta que fica e','em um mundo cada vez mais']) {
    if (corpo.includes(clich)) apontar('MAIOR','Frase genérica: '+clich);
  }
  const hrefs=[...texto.matchAll(/<a\s[^>]*href=["']([^"']+)["']/gi)].map(m=>m[1]);
  const links=[...new Set(hrefs.map(h=>{try{return new URL(h,url).href}catch{return null}}).filter(Boolean))];
  const externas=links.filter(l=>new URL(l).hostname!==BASE.hostname && new URL(l).hostname!=='www.agenciarca.com.br');
  rel.links=links.map(l=>({url:l,verificado:false}));
  if (!externas.length) apontar('BLOQUEANTE','Nenhuma fonte externa localizada no artigo');
  const consultar=links.slice(0,25);
  for (const link of consultar) {
    const registro=rel.links.find(x=>x.url===link);
    try { const v=await buscar(link,8000); registro.verificado=true; registro.http=v.status; }
    catch(e){registro.erro=String(e.message||e).slice(0,160); apontar('MAIOR','Link requer conferência: '+link);}
  }
  if (links.length>25) apontar('MENOR','Mais de 25 links: validação dos demais exige conferência manual');
  apontar('BLOQUEANTE','Mesmo com links válidos, a Social deve provar que cada fonte sustenta a afirmação específica');
  apontar('BLOQUEANTE','Requer análise editorial de linguagem, SEO e promessas comerciais conforme SKILL.md');
} catch(e) {
  apontar('BLOQUEANTE','Não foi possível auditar a versão publicada: '+String(e.message||e));
}
fs.mkdirSync('relatorios',{recursive:true});
fs.writeFileSync('relatorios/auditoria-editorial.json',JSON.stringify(rel,null,2)+'\n');
const md=[
  '# Revisora Editorial RCA — pré-auditoria',
  '',
  '- Artigo: '+rel.url_artigo,
  '- Data UTC: '+rel.analisado_em_utc,
  '- Versão SHA256 HTML: '+(rel.versao_sha256||'não obtida'),
  '- Resultado: **'+rel.resultado+'**',
  '- **A revisão factual semântica NÃO foi executada automaticamente**',
  '- Para aprovação: Social deve conferir alegações, citar trechos exatos das fontes e registrar relatório da skill; depois Fábio/Fabi devem aprovar',
  '',
  '## Achados',
  ...achados.map(x=>'- **'+x.nivel+'** — '+x.descricao),
  '',
  '## Links testados',
  ...rel.links.map(x=>'- '+(x.verificado?'OK':'PENDENTE')+' — '+x.url+(x.erro?' — '+x.erro:'')),
  '',
  '## Próxima etapa',
  'Aplicar skills/revisora-editorial-rca/SKILL.md e EXEMPLO-RELATORIO.md com fontes abertas; publicar apenas com aprovação expressa da direção.',
].join('\n');
fs.writeFileSync('relatorios/auditoria-editorial.md',md+'\n');
console.log(md);
if (!rel.versao_sha256) process.exitCode=2; // falha técnica de acesso; demais bloqueios editoriais constam no relatório, não como sucesso de aprovação
