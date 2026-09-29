/* =========================================================================
   nfce-pdf.js — DANFE NFC-e (modelo 65), formato cupom.

   Diferente do DANFE de NF-e: não é A4 com blocos fixos, e sim uma bobina
   de 80 mm com altura variável conforme a quantidade de itens.

   Como a altura precisa ser conhecida ANTES de criar o documento, o desenho
   roda em duas passagens: a primeira só mede (não pinta nada), a segunda
   desenha de verdade num documento já dimensionado.

   Depende de: qrcode (lib/qrcode.js)
   ========================================================================= */
'use strict';

(function (root, factory) {
  if (typeof module !== 'undefined' && module.exports) module.exports = factory();
  else root.NfcePDF = factory();
})(typeof window !== 'undefined' ? window : this, function () {

  const LARGURA = 80;      // mm — bobina padrão
  const M       = 3;       // margem
  const X0      = M;
  const X1      = LARGURA - M;
  const W       = X1 - X0; // 74

  const QR_LADO = 40;

  /* =====================================================================
     Contexto de desenho: em modo "medir" apenas avança o y.
     ===================================================================== */
  function criarCtx(doc, medir) {
    let y = M;

    function fonte(tam, negrito) {
      doc.setFont('helvetica', negrito ? 'bold' : 'normal');
      doc.setFontSize(tam);
    }

    /** Escreve uma ou mais linhas (com quebra automática) e avança o y. */
    function texto(t, o) {
      o = o || {};
      fonte(o.fs || 7, o.b);
      const largura = o.w || W;
      const linhas = doc.splitTextToSize(String(t == null ? '' : t), largura);
      const alt = (o.lh || (o.fs || 7) * 0.42);

      for (const ln of linhas) {
        if (!medir) {
          if (o.align === 'center')     doc.text(ln, LARGURA / 2, y, { align: 'center' });
          else if (o.align === 'right') doc.text(ln, X1, y, { align: 'right' });
          else                          doc.text(ln, o.x != null ? o.x : X0, y);
        }
        y += alt;
      }
      return linhas.length;
    }

    /** Par rótulo/valor na mesma linha: rótulo à esquerda, valor à direita. */
    function par(rot, val, o) {
      o = o || {};
      fonte(o.fs || 7, o.b);
      if (!medir) {
        doc.text(String(rot), X0, y);
        doc.text(String(val), X1, y, { align: 'right' });
      }
      y += (o.fs || 7) * 0.42;
    }

    function tracejado(gap) {
      y += (gap == null ? 1.2 : gap);
      if (!medir) {
        doc.setLineWidth(0.1);
        doc.setLineDashPattern([0.6, 0.6], 0);
        doc.line(X0, y, X1, y);
        doc.setLineDashPattern([], 0);
      }
      y += (gap == null ? 1.8 : gap);
    }

    function espaco(n) { y += n; }

    return {
      texto, par, tracejado, espaco,
      get y() { return y; },
      set y(v) { y = v; },
      doc, medir
    };
  }

  /* =====================================================================
     QR Code
     ===================================================================== */
  function qr(doc, texto, x, y, lado) {
    if (!texto) return;
    let q;
    try {
      q = qrcode(0, 'M');
      q.addData(texto);
      q.make();
    } catch (e) {
      console.warn('[NFCe] falha no QR:', e);
      return;
    }
    const n = q.getModuleCount();
    const p = lado / (n + 2);
    doc.setFillColor(0);
    for (let r = 0; r < n; r++) {
      for (let c = 0; c < n; c++) {
        if (q.isDark(r, c)) doc.rect(x + (c + 1) * p, y + (r + 1) * p, p, p, 'F');
      }
    }
  }

  /* =====================================================================
     Desenho do cupom
     ===================================================================== */
  function montar(ctx, d) {
    const doc = ctx.doc;

    if (d.homologacao) {
      ctx.texto('AMBIENTE DE HOMOLOGAÇÃO - SEM VALOR FISCAL', { fs: 7, b: true, align: 'center' });
      ctx.espaco(1);
    }

    /* ---- Emitente ---- */
    ctx.texto(d.emitNome, { fs: 8, b: true, align: 'center' });
    ctx.texto(`CNPJ: ${d.emitDoc}  IE: ${d.emitIE}`, { fs: 6.4, align: 'center' });
    ctx.texto(d.emitEnd, { fs: 6.4, align: 'center' });
    if (d.emitBairro) ctx.texto(d.emitBairro, { fs: 6.4, align: 'center' });
    ctx.texto(d.emitMunUF, { fs: 6.4, align: 'center' });

    ctx.tracejado();

    ctx.texto('Documento Auxiliar da Nota Fiscal de Consumidor Eletrônica',
              { fs: 6.4, align: 'center' });
    ctx.texto('Não permite aproveitamento de crédito de ICMS',
              { fs: 6.4, align: 'center' });

    ctx.tracejado();

    /* ---- Itens ---- */
    // Colunas: código+descrição à esquerda; qtde, un, unit, total à direita.
    // Grid do cupom, em mm a partir da margem. GUTTER garante que a descrição
  // nunca encoste na coluna Qtde — foi exatamente onde colidia antes.
  const X_DESC = X0 + 7;
  const cQtd = X0 + 35, cUn = X0 + 44, cUnit = X0 + 58, cTot = X1;
  const GUTTER = 5;
  const W_DESC = (cQtd - GUTTER) - X_DESC;

    ctx.doc.setFont('helvetica', 'normal');
    ctx.doc.setFontSize(6);
    if (!ctx.medir) {
      doc.text('Código', X0, ctx.y);
      doc.text('Descrição', X_DESC, ctx.y);
      doc.text('Qtde', cQtd, ctx.y, { align: 'right' });
      doc.text('UN', cUn, ctx.y, { align: 'right' });
      doc.text('Vl Unit', cUnit, ctx.y, { align: 'right' });
      doc.text('Vl Total', cTot, ctx.y, { align: 'right' });
    }
    ctx.y += 3;

    for (const it of d.itens) {
      // Mede a largura REAL do texto em vez de confiar num limite em mm:
      // splitTextToSize usa as unidades internas do jsPDF e estava deixando
      // a descrição invadir a coluna Qtde.
      const linhasDesc = doc.splitTextToSize(it.desc, W_DESC);
      if (!ctx.medir) {
        doc.setFont('helvetica', 'normal');
        doc.setFontSize(6);
        doc.text(it.codigo, X0, ctx.y);
        doc.text(linhasDesc[0] || '', X_DESC, ctx.y);
        doc.text(it.qtd,   cQtd,  ctx.y, { align: 'right' });
        doc.text(it.un,    cUn,   ctx.y, { align: 'right' });
        doc.text(it.unit,  cUnit, ctx.y, { align: 'right' });
        doc.text(it.total, cTot,  ctx.y, { align: 'right' });
      }
      ctx.y += 2.7;

      // Descrição longa continua nas linhas seguintes, recuada.
      for (let i = 1; i < linhasDesc.length; i++) {
        if (!ctx.medir) doc.text(linhasDesc[i], X_DESC, ctx.y);
        ctx.y += 2.5;
      }
    }

    ctx.tracejado();

    /* ---- Totais ---- */
    ctx.par('Qtde total de itens', d.qtdItens, { fs: 7 });
    ctx.par('Valor Total R$', d.vProd, { fs: 7 });
    if (d.vDesc && d.vDesc !== '0,00')  ctx.par('Desconto R$', d.vDesc, { fs: 7 });
    if (d.vFrete && d.vFrete !== '0,00') ctx.par('Frete R$', d.vFrete, { fs: 7 });
    if (d.vOutro && d.vOutro !== '0,00') ctx.par('Outras despesas R$', d.vOutro, { fs: 7 });
    ctx.espaco(0.8);
    ctx.par('Valor a Pagar R$', d.vNF, { fs: 9, b: true });

    ctx.espaco(1);
    ctx.par('FORMA PAGAMENTO', 'VALOR PAGO R$', { fs: 6.4 });
    for (const p of d.pagamentos) ctx.par(p.forma, p.valor, { fs: 7 });
    ctx.par('Troco R$', d.troco, { fs: 7 });

    ctx.tracejado();

    /* ---- Chave e consulta ---- */
    ctx.texto('Consulte pela Chave de Acesso em:', { fs: 7, b: true, align: 'center' });
    ctx.texto(d.urlChave || 'www.nfe.fazenda.gov.br/portal', { fs: 6.4, align: 'center' });
    ctx.espaco(0.6);
    ctx.texto(d.chaveFmt, { fs: 6.6, align: 'center' });

    ctx.espaco(1.2);
    ctx.texto(d.temDest
      ? `CONSUMIDOR: ${d.destNome || ''} ${d.destDoc || ''}`.trim()
      : 'CONSUMIDOR NÃO IDENTIFICADO', { fs: 6.6, align: 'center' });

    ctx.texto(`NFC-e nº ${d.numero}  Série ${d.serie}  ${d.dhEmi}`,
              { fs: 7, b: true, align: 'center' });

    if (d.nProt) {
      ctx.texto(`Protocolo de Autorização: ${d.nProt}`, { fs: 6.4, align: 'center' });
      ctx.texto(`Data de Autorização: ${d.dhProt}`, { fs: 6.4, align: 'center' });
    }

    if (d.contingencia) {
      ctx.espaco(0.8);
      ctx.texto('EMITIDA EM CONTINGÊNCIA', { fs: 7, b: true, align: 'center' });
      ctx.texto('Pendente de autorização', { fs: 6.4, align: 'center' });
    }

    ctx.tracejado();

    /* ---- QR Code ---- */
    ctx.espaco(1);
    if (!ctx.medir) qr(doc, d.qrCode, (LARGURA - QR_LADO) / 2, ctx.y, QR_LADO);
    ctx.y += QR_LADO + 2;

    /* ---- Rodapé ---- */
    if (d.vTotTrib && d.vTotTrib !== '0,00') {
      ctx.texto(`Tributos totais incidentes (Lei Federal 12.741/2012): R$ ${d.vTotTrib}`,
                { fs: 6, align: 'center' });
    }
    if (d.infCpl) ctx.texto(d.infCpl, { fs: 6, align: 'center' });

    ctx.espaco(2);
  }

  /* =====================================================================
     API pública
     ===================================================================== */
  function gerar(dados, jsPDFCtor) {
    // Passagem 1: mede a altura num documento descartável de mesma largura.
    const provisorio = new jsPDFCtor({ unit: 'mm', format: [LARGURA, 1000] });
    const medida = criarCtx(provisorio, true);
    montar(medida, dados);
    const altura = Math.max(60, Math.ceil(medida.y) + M);

    // Passagem 2: desenha no documento já com a altura certa.
    const doc = new jsPDFCtor({ unit: 'mm', format: [LARGURA, altura], compress: true });
    montar(criarCtx(doc, false), dados);

    doc.setProperties({
      title: `DANFE NFC-e ${dados.numero}`,
      subject: dados.chave,
      creator: 'Extensão DANFE/DACTE'
    });
    return doc;
  }

  return { gerar, LARGURA };
});
