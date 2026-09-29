/* =========================================================================
   nfce-dados.js — extrai do XML de NFC-e (modelo 65) os dados do cupom.
   Depende de: comum.js
   ========================================================================= */
'use strict';

(function (root, factory) {
  if (typeof module !== 'undefined' && module.exports) module.exports = factory(require('./comum.js'));
  else root.NfceDados = factory({ FMT: FMT, getValueFromPath: getValueFromPath, extrairChave: extrairChave });
})(typeof window !== 'undefined' ? window : this, function (C) {

  const FMT = C.FMT;
  const g = C.getValueFromPath;

  /* Formas de pagamento — tabela tPag do MOC da NF-e. */
  const T_PAG = {
    '01': 'Dinheiro', '02': 'Cheque', '03': 'Cartão de Crédito', '04': 'Cartão de Débito',
    '05': 'Crédito Loja', '10': 'Vale Alimentação', '11': 'Vale Refeição', '12': 'Vale Presente',
    '13': 'Vale Combustível', '14': 'Duplicata Mercantil', '15': 'Boleto Bancário',
    '16': 'Depósito Bancário', '17': 'PIX Dinâmico', '18': 'Transferência Bancária',
    '19': 'Programa de Fidelidade', '20': 'PIX Estático', '21': 'Crédito em Loja',
    '22': 'Pagamento Eletrônico não informado', '90': 'Sem Pagamento', '99': 'Outros'
  };

  function extrair(xml) {
    const chave = C.extrairChave(xml);

    const emitEnd = [
      g(xml, 'emit.enderEmit.xLgr'),
      g(xml, 'emit.enderEmit.nro')
    ].filter(Boolean).join(', ');

    // Consumidor é opcional na NFC-e; ausente = "não identificado".
    const destCNPJ = g(xml, 'dest.CNPJ');
    const destCPF  = g(xml, 'dest.CPF');
    const destNome = g(xml, 'dest.xNome');
    const temDest  = !!(destCNPJ || destCPF || destNome);

    const itens = Array.from(xml.querySelectorAll('det')).map(det => {
      const p = det.querySelector('prod');
      if (!p) return null;
      return {
        codigo: g(p, 'cProd'),
        desc:   g(p, 'xProd'),
        qtd:    FMT.qty(g(p, 'qCom')),
        un:     g(p, 'uCom'),
        unit:   FMT.money(g(p, 'vUnCom')),
        total:  FMT.money(g(p, 'vProd'))
      };
    }).filter(Boolean);

    const pagamentos = Array.from(xml.querySelectorAll('pag > detPag')).map(d => ({
      forma: T_PAG[g(d, 'tPag')] || g(d, 'tPag'),
      valor: FMT.money(g(d, 'vPag'))
    }));

    return {
      chave,
      chaveFmt: FMT.chave(chave),
      // Na NFC-e o QR é obrigatório e vem pronto no XML (com o hash já calculado).
      qrCode:   (g(xml, 'infNFeSupl.qrCode') || '').trim(),
      urlChave: (g(xml, 'infNFeSupl.urlChave') || '').trim(),

      emitNome: g(xml, 'emit.xNome'),
      emitDoc:  FMT.doc(g(xml, 'emit.CNPJ') || g(xml, 'emit.CPF')),
      emitIE:   g(xml, 'emit.IE'),
      emitEnd,
      emitBairro: g(xml, 'emit.enderEmit.xBairro'),
      emitMunUF: [g(xml, 'emit.enderEmit.xMun'), g(xml, 'emit.enderEmit.UF')].filter(Boolean).join('-'),

      temDest,
      destNome,
      destDoc: FMT.doc(destCNPJ || destCPF),

      itens,
      qtdItens: String(itens.length),

      vProd:  FMT.money(g(xml, 'total.ICMSTot.vProd')),
      vDesc:  FMT.money(g(xml, 'total.ICMSTot.vDesc')),
      vFrete: FMT.money(g(xml, 'total.ICMSTot.vFrete')),
      vOutro: FMT.money(g(xml, 'total.ICMSTot.vOutro')),
      vNF:    FMT.money(g(xml, 'total.ICMSTot.vNF')),
      vTotTrib: FMT.money(g(xml, 'total.ICMSTot.vTotTrib')),

      pagamentos,
      troco: FMT.money(g(xml, 'pag.vTroco') || '0'),

      numero: FMT.nnf(g(xml, 'ide.nNF')),
      numeroSimples: g(xml, 'ide.nNF'),
      serie:  String(g(xml, 'ide.serie')).padStart(3, '0'),
      dhEmi:  `${FMT.date(g(xml, 'ide.dhEmi'))} ${FMT.time(g(xml, 'ide.dhEmi'))}`.trim(),

      nProt:  g(xml, 'infProt.nProt'),
      dhProt: `${FMT.date(g(xml, 'infProt.dhRecbto'))} ${FMT.time(g(xml, 'infProt.dhRecbto'))}`.trim(),

      // Emissão em contingência precisa ser destacada no cupom.
      contingencia: !['1', '4'].includes(g(xml, 'ide.tpEmis')),
      homologacao:  g(xml, 'ide.tpAmb') === '2',

      infCpl: g(xml, 'infAdic.infCpl')
    };
  }

  function nomeArquivo(d) {
    const num = String(d.numeroSimples || '').replace(/\D/g, '').padStart(9, '0');
    return `NFCe_${num}_${d.chave}.pdf`;
  }

  return { extrair, nomeArquivo, T_PAG };
});
