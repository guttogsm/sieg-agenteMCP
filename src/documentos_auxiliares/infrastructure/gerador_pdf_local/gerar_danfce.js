#!/usr/bin/env node
'use strict';
/* =========================================================================
   gerar_danfce.js — gera a DANFCE (NFC-e, modelo 65) localmente a partir do
   XML, sem depender da API SIEG.

   CONTEXTO (25/09/2026): a API SIEG tem rotas de geração de PDF só pra
   Danfe (NF-e), Dacte (CT-e) e Danfse (NFS-e) — /api/v1/gerarDanfeVia*,
   gerarDacteVia*, gerarDanfseVia* — confirmado no Swagger "engine" real, e
   NÃO existe rota equivalente pra NFC-e nem CF-e. Antes deste script, um
   pedido de PDF de NFC-e era bloqueado com uma mensagem explicando essa
   limitação (ver ExecutorFerramentasSieg._validar_chave_para_pdf).

   Este script fecha a lacuna reaproveitando, SEM ALTERAÇÃO NA LÓGICA, o
   motor de renderização já testado e em uso na extensão Chrome "Documentos
   Fiscais" do próprio Guto (nfce-dados.js extrai os campos do XML,
   nfce-pdf.js desenha o cupom com jsPDF) — arquivos vendorizados em
   lib_extensao/ exatamente como estavam no .zip da extensão (v6.6.4),
   trocando só o DOMParser do browser por `linkedom` (equivalente em Node,
   com o mesmo querySelector/querySelectorAll/getAttribute/textContent que
   esse código já espera).

   Uso: node gerar_danfce.js <caminho_xml_entrada> <caminho_pdf_saida>

   Saída:
     sucesso   -> exit(0), stdout com JSON {"ok":true,"bytes":N,"chave":"...","numero":"..."}
     tipo != NFC-e (mod != 65) -> exit(2), stderr com JSON
         {"ok":false,"erro":"tipo_incompativel","modDetectado":"55"|"57"|...|null}
     qualquer outro erro -> exit(1), stderr com JSON {"ok":false,"erro":"<mensagem>"}

   Depende de (package.json nesta mesma pasta): linkedom.
   ========================================================================= */

const fs = require('fs');
const path = require('path');

let DOMParser;
try {
  ({ DOMParser } = require('linkedom'));
} catch (e) {
  process.stderr.write(JSON.stringify({
    ok: false,
    erro: "dependência 'linkedom' não instalada — rode 'npm install' dentro de " +
          "documentos_auxiliares/infrastructure/gerador_pdf_local/ uma vez.",
  }) + '\n');
  process.exit(1);
}

const LIB = path.join(__dirname, 'lib_extensao');
const { jsPDF } = require(path.join(LIB, 'lib', 'jspdf.umd.min.js'));

// nfce-pdf.js chama qrcode() como referência global — herdado do ambiente
// de extensão, onde lib/qrcode.js roda solto na página e todo script
// enxerga o mesmo `window`. Em Node, cada require() tem seu próprio escopo
// de módulo, então a única forma de manter nfce-pdf.js SEM MODIFICAÇÃO é
// publicar essa dependência em `global` antes dele rodar.
global.qrcode = require(path.join(LIB, 'lib', 'qrcode.js'));

const NfceDados = require(path.join(LIB, 'nfce-dados.js'));
const NfcePDF = require(path.join(LIB, 'nfce-pdf.js'));

function falhar(codigo, obj) {
  process.stderr.write(JSON.stringify(obj) + '\n');
  process.exit(codigo);
}

const [, , caminhoXml, caminhoPdf] = process.argv;
if (!caminhoXml || !caminhoPdf) {
  falhar(1, { ok: false, erro: 'uso: node gerar_danfce.js <xml_entrada> <pdf_saida>' });
}

let texto;
try {
  texto = fs.readFileSync(caminhoXml, 'utf-8');
} catch (e) {
  falhar(1, { ok: false, erro: `falha ao ler XML de entrada: ${e.message}` });
}

let xml;
try {
  xml = new DOMParser().parseFromString(texto, 'text/xml');
} catch (e) {
  falhar(1, { ok: false, erro: `XML malformado: ${e.message}` });
}

const infNFe = xml.querySelector('infNFe');
if (!infNFe) {
  falhar(1, { ok: false, erro: 'não é um XML de NF-e/NFC-e reconhecido (sem <infNFe>).' });
}

// Mesma verificação que o Python já faz a partir da chave (posições 21-22
// do dígito verificador), só que aqui direto do campo <ide><mod> do XML —
// mais uma camada de garantia, na fonte de dados mais confiável possível
// (o próprio conteúdo do documento, não uma leitura de string da chave).
const mod = ((xml.querySelector('ide > mod') || {}).textContent || '').trim();
if (mod !== '65') {
  falhar(2, { ok: false, erro: 'tipo_incompativel', modDetectado: mod || null });
}

let dados;
let doc;
try {
  dados = NfceDados.extrair(xml);
  doc = NfcePDF.gerar(dados, jsPDF);
} catch (e) {
  falhar(1, { ok: false, erro: `falha ao gerar PDF: ${e.message}` });
}

let buf;
try {
  buf = Buffer.from(doc.output('arraybuffer'));
  fs.writeFileSync(caminhoPdf, buf);
} catch (e) {
  falhar(1, { ok: false, erro: `falha ao salvar PDF: ${e.message}` });
}

process.stdout.write(JSON.stringify({
  ok: true,
  bytes: buf.length,
  chave: dados.chave,
  numero: dados.numeroSimples,
}) + '\n');
