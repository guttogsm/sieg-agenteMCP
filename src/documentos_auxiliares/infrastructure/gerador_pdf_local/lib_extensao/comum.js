/* =========================================================================
   comum.js — formatadores e utilitários compartilhados por DANFE e DACTE.
   ========================================================================= */
'use strict';

/* ---------------------------------------------------------------------
   1. FORMATADORES
   --------------------------------------------------------------------- */
const FMT = {
  money(v) {
    if (v === '' || v == null) return '';
    const n = Number(v);
    if (!isFinite(n)) return v;
    return n.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  },

  // Quantidade: a NF-e permite até 4 casas; corta zeros à direita mas mantém 2 no mínimo.
  qty(v) {
    if (v === '' || v == null) return '';
    const n = Number(v);
    if (!isFinite(n)) return v;
    return n.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 4 });
  },

  aliq(v) {
    if (v === '' || v == null) return '';
    const n = Number(v);
    if (!isFinite(n)) return v;
    return n.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  },

  peso(v) {
    if (v === '' || v == null) return '';
    const n = Number(v);
    if (!isFinite(n)) return v;
    return n.toLocaleString('pt-BR', { minimumFractionDigits: 3, maximumFractionDigits: 3 });
  },

  // dhEmi vem como 2026-01-16T09:18:12-03:00.
  // Fatiamos a string em vez de usar new Date() para NÃO converter fuso:
  // a data legal é a do emitente, não a do computador que imprime.
  date(v) {
    if (!v) return '';
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(v);
    return m ? `${m[3]}/${m[2]}/${m[1]}` : v;
  },

  time(v) {
    if (!v) return '';
    const m = /T(\d{2}):(\d{2}):(\d{2})/.exec(v);
    return m ? `${m[1]}:${m[2]}:${m[3]}` : '';
  },

  datetime(v) {
    const d = FMT.date(v), t = FMT.time(v);
    return t ? `${d} ${t}` : d;
  },

  cnpj(v) {
    const d = String(v || '').replace(/\D/g, '');
    if (d.length !== 14) return v || '';
    return d.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, '$1.$2.$3/$4-$5');
  },

  cpf(v) {
    const d = String(v || '').replace(/\D/g, '');
    if (d.length !== 11) return v || '';
    return d.replace(/^(\d{3})(\d{3})(\d{3})(\d{2})$/, '$1.$2.$3-$4');
  },

  doc(v) {
    const d = String(v || '').replace(/\D/g, '');
    if (d.length === 14) return FMT.cnpj(d);
    if (d.length === 11) return FMT.cpf(d);
    return v || '';
  },

  cep(v) {
    const d = String(v || '').replace(/\D/g, '');
    if (d.length !== 8) return v || '';
    return d.replace(/^(\d{5})(\d{3})$/, '$1-$2');
  },

  fone(v) {
    const d = String(v || '').replace(/\D/g, '');
    if (d.length === 11) return d.replace(/^(\d{2})(\d{5})(\d{4})$/, '($1) $2-$3');
    if (d.length === 10) return d.replace(/^(\d{2})(\d{4})(\d{4})$/, '($1) $2-$3');
    if (d.length === 9)  return d.replace(/^(\d{1})(\d{4})(\d{4})$/, '($1) $2-$3');
    if (d.length === 8)  return d.replace(/^(\d{4})(\d{4})$/, '$1-$2');
    return v || '';
  },

  // Nº da nota no DANFE sai zero-preenchido em 9 dígitos, com pontos.
  nnf(v) {
    const d = String(v || '').replace(/\D/g, '').padStart(9, '0');
    return d.replace(/^(\d{3})(\d{3})(\d{3})$/, '$1.$2.$3');
  },

  // Carga em CT-e vem com 4 casas (99.7200) e o DACTE imprime assim.
  carga(v) {
    if (v === '' || v == null) return '';
    const n = Number(v);
    if (!isFinite(n)) return v;
    return n.toLocaleString('pt-BR', { minimumFractionDigits: 4, maximumFractionDigits: 4 });
  },

  chave(v) {
    const d = String(v || '').replace(/\D/g, '');
    return d.replace(/(\d{4})(?=\d)/g, '$1 ').trim();
  }
};

/* Tabelas de decodificação */
const MOD_FRETE = {
  '0': '0 - Por conta do Emitente',
  '1': '1 - Por conta do Destinatário',
  '2': '2 - Por conta de Terceiros',
  '3': '3 - Transporte Próprio (Remetente)',
  '4': '4 - Transporte Próprio (Destinatário)',
  '9': '9 - Sem Frete'
};

/* ---------------------------------------------------------------------
   2. RESOLUÇÃO DE CAMINHOS NO XML

   Sintaxe do data-xml-path (mantida do projeto original):
     "emit.enderEmit.xLgr"  -> descendente:  emit enderEmit xLgr
     "infNFe@Id"            -> atributo Id do elemento infNFe

   ATENÇÃO ao escopo: querySelector busca no documento inteiro e devolve
   o PRIMEIRO nó que casar. Tags como <CNPJ>, <vBC>, <CST> e <IE> aparecem
   em vários blocos, então SEMPRE ancore o path a partir do pai
   ("dest.CNPJ", nunca "CNPJ").
   --------------------------------------------------------------------- */
function getValueFromPath(root, path) {
  if (!path) return '';
  const [rawSel, rawAttr] = path.split('@');
  const selector = rawSel.trim().replace(/\./g, ' ');
  const attr = rawAttr ? rawAttr.trim() : null;

  let node;
  try {
    node = selector ? root.querySelector(selector) : root;
  } catch (e) {
    console.warn('[DANFE] seletor inválido:', path, e);
    return '';
  }
  if (!node) return '';
  return attr ? (node.getAttribute(attr) || '') : (node.textContent || '').trim();
}

function txt(root, path) { return getValueFromPath(root, path); }

/* ---------------------------------------------------------------------
   3. CHAVE DE ACESSO
   --------------------------------------------------------------------- */
function extrairChave(xml) {
  // O Id vem prefixado: "NFe3526..." ou "CTe3126..." — o prefixo precisa sair.
  for (const p of ['infNFe@Id', 'infCte@Id']) {
    const id = txt(xml, p).replace(/\D/g, '');
    if (id.length === 44) return id;
  }
  // Fallback: protocolo de autorização.
  for (const p of ['infProt.chNFe', 'infProt.chCTe']) {
    const ch = txt(xml, p).replace(/\D/g, '');
    if (ch.length === 44) return ch;
  }
  return '';
}

/** Valida o DV da chave (módulo 11, pesos 2..9 da direita para a esquerda). */
function chaveValida(k) {
  if (!/^\d{44}$/.test(k)) return false;
  let soma = 0;
  for (let i = 0; i < 43; i++) soma += Number(k[i]) * (2 + ((42 - i) % 8));
  const resto = soma % 11;
  const dv = (resto === 0 || resto === 1) ? 0 : 11 - resto;
  return dv === Number(k[43]);
}


if (typeof module !== 'undefined' && module.exports) {
  module.exports = { FMT, MOD_FRETE, getValueFromPath, txt, extrairChave, chaveValida };
}
