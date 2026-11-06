// Lector de PDFs del CENDOJ para ejecutar DENTRO de una página de www.poderjudicial.es abierta en el navegador
// (pestaña con cualquier documento "openDocument"). No carga código de fuera: solo usa el navegador.
// Uso: pegar el contenido con javascript_tool y después:
//   await window._cendoj([{id: "abc", url: "https://www.poderjudicial.es/search/AN/openDocument/<ref>/<fecha>"}, ...])
// Devuelve {id: extracto} con el encabezado, los hechos y el fallo de cada resolución (o "CAPTCHA"/"ERROR …").
window._inflate = async function (bytes) {
  const ds = new DecompressionStream('deflate'); const w = ds.writable.getWriter();
  w.write(bytes).catch(() => {}); w.close().catch(() => {});
  const r = ds.readable.getReader(); const chunks = []; let n = 0;
  try { while (true) { const { value, done } = await r.read(); if (done) break; chunks.push(value); n += value.length; } } catch (e) {}
  const out = new Uint8Array(n); let o = 0; for (const c of chunks) { out.set(c, o); o += c.length; } return out;
};
window._pdfTexto = async function (url) {
  const resp = await fetch(url);
  if (!(resp.headers.get('content-type') || '').includes('pdf')) return 'CAPTCHA';
  const u = new Uint8Array(await resp.arrayBuffer());
  const L = new TextDecoder('latin1').decode(u);
  const pos = {}; for (const m of L.matchAll(/(\d+) 0 obj/g)) pos[m[1]] = m.index;
  const obj = n => { const p = pos[n]; return p === undefined ? '' : L.slice(p, L.indexOf('endobj', p)); };
  const stream = async n => { const p = pos[n]; if (p === undefined) return ''; const s = L.indexOf('stream', p); let st = s + 6; if (L[st] === '\r') st++; if (L[st] === '\n') st++; const e = L.indexOf('endstream', st);
    const d = L.slice(p, s); const b = /FlateDecode/.test(d) ? await window._inflate(u.subarray(st, e)) : u.subarray(st, e); return new TextDecoder('latin1').decode(b); };
  const fontObjs = {}; for (const m of L.matchAll(/\/Font\s*<<([^>]*)>>/g)) for (const f of m[1].matchAll(/\/(\w+)\s+(\d+) 0 R/g)) fontObjs[f[1]] = f[2];
  const maps = {};
  for (const [name, n] of Object.entries(fontObjs)) {
    const tu = obj(n).match(/\/ToUnicode\s+(\d+) 0 R/); if (!tu) continue;
    const cm = await stream(tu[1]); const mp = {};
    for (const b of cm.matchAll(/beginbfchar([\s\S]*?)endbfchar/g)) for (const x of b[1].matchAll(/<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>/g)) mp[parseInt(x[1], 16)] = x[2];
    for (const b of cm.matchAll(/beginbfrange([\s\S]*?)endbfrange/g)) for (const x of b[1].matchAll(/<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>/g)) { const a = parseInt(x[1], 16), z = parseInt(x[2], 16), d = parseInt(x[3], 16); for (let k = a; k <= z; k++) mp[k] = (d + k - a).toString(16).padStart(4, '0'); }
    maps[name] = mp;
  }
  const hex2s = h => { let o = ''; for (let i = 0; i < h.length; i += 4) o += String.fromCharCode(parseInt(h.slice(i, i + 4), 16)); return o; };
  const pages = [...L.matchAll(/\/Type\s*\/Page[^s][\s\S]*?\/Contents\s+(\d+) 0 R/g)].map(m => m[1]);
  let out = '';
  for (const c of pages) {
    const t = await stream(c); let font = null, lastY = null;
    for (const m of t.matchAll(/\/(\w+)\s+[\d.]+\s+Tf|([-\d.]+)\s+([-\d.]+)\s+Tm|<([0-9A-Fa-f]+)>\s*Tj|\bBT\b/g)) {
      if (m[1]) font = m[1];
      else if (m[3] !== undefined) { const y = Math.round(Number(m[3])); if (lastY !== null && Math.abs(y - lastY) > 2) out += '\n'; lastY = y; }
      else if (m[4]) { const mp = maps[font] || {}; const h = m[4]; for (let i = 0; i < h.length; i += 4) { const g = parseInt(h.slice(i, i + 4), 16); out += mp[g] !== undefined ? hex2s(mp[g]) : ''; } }
    }
    out += '\n\n';
  }
  return out.replace(/[ \t]+/g, ' ').replace(/\n /g, '\n').replace(/\n{3,}/g, '\n\n');
};
window._extracto = function (t) {
  const p = t.search(/ha visto|ha examinado|ha deliberado|ANTECEDENTES/);
  const cab = t.slice(0, 350) + ' … ' + t.slice(Math.max(0, p - 100), p + 650);
  const h = t.search(/HECHOS PROBADOS|FUNDAMENTOS DE DERECHO/);
  const f = Math.max(t.lastIndexOf('FALLAMOS'), t.lastIndexOf('PARTE DISPOSITIVA'), t.lastIndexOf('ACUERDA'), t.search(/F\s?A\s?L\s?L\s?O\b(?![\s\S]*F\s?A\s?L\s?L\s?O\b)/));
  return (cab + ' […] ' + (h > 0 ? t.slice(h, h + 700) + ' […] ' : '') + (f > 0 ? t.slice(f, f + 700) : t.slice(-900))).replace(/\s+/g, ' ');
};
window._cendoj = async function (lista) {
  const res = {};
  for (const { id, url } of lista) {
    const m = url.match(/openDocument\/([0-9a-f]+)\/(\d{8})/);
    if (!m) { res[id] = 'ERROR enlace'; continue; }
    const pdf = `https://www.poderjudicial.es/search/contenidos.action?action=accessToPDF&publicinterface=true&tab=AN&reference=${m[1]}&encode=true&optimize=${m[2]}&databasematch=AN`;
    try { const t = await window._pdfTexto(pdf); res[id] = t === 'CAPTCHA' ? 'CAPTCHA' : window._extracto(t); }
    catch (e) { res[id] = 'ERROR ' + e.message; }
    if (res[id] === 'CAPTCHA') break;                      // el CENDOJ pide captcha: se para, no se intenta saltar
    await new Promise(r => setTimeout(r, 2500));           // con calma: una resolución cada pocos segundos
  }
  return res;
};
'ok';
