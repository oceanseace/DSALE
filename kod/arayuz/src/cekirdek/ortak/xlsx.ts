/**
 * "Excel'e indir" (EK-9): kütüphanesiz, küçük ama GERÇEK .xlsx yazıcı.
 *
 * CSV Türkçe Excel'de ayraç (; mi , mi) ve kodlama yüzünden bozuk açılıyordu;
 * .xlsx her Excel'de aynı açılır. Dosya tarayıcıda üretilir, sunucuya hiçbir
 * şey gitmez. Başlık satırı kalın ve dondurulmuş, süzgeç (otomatik filtre)
 * açık, sayılar sayı olarak yazılır (toplanabilir), sütun genişliği içeriğe göre.
 *
 * Zip "store" (sıkıştırmasız) yazılır: birkaç bin satırda boyut sorun değil,
 * kod ise okunabilir kalır.
 */

export type Hucre = string | number | boolean | null | undefined | Date;

export interface XlsxSayfa {
  ad: string;
  basliklar: string[];
  satirlar: Hucre[][];
}

/* ------------------------------ CRC32 + zip ------------------------------ */

const CRC_TABLO = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();

function crc32(veri: Uint8Array): number {
  let c = 0xffffffff;
  for (let i = 0; i < veri.length; i++) c = CRC_TABLO[(c ^ veri[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function zip(dosyalar: Array<{ ad: string; veri: Uint8Array }>): Uint8Array<ArrayBuffer> {
  const kodla = new TextEncoder();
  const parcalar: Uint8Array[] = [];
  const merkez: Uint8Array[] = [];
  let ofset = 0;
  // Sabit tarih (1980-01-01): aynı veri → aynı dosya.
  const zaman = 0;
  const tarih = (0 << 9) | (1 << 5) | 1;
  for (const d of dosyalar) {
    const ad = kodla.encode(d.ad);
    const crc = crc32(d.veri);
    const yerel = new DataView(new ArrayBuffer(30));
    yerel.setUint32(0, 0x04034b50, true);
    yerel.setUint16(4, 20, true);
    yerel.setUint16(6, 0x0800, true); // UTF-8 ad
    yerel.setUint16(8, 0, true); // store
    yerel.setUint16(10, zaman, true);
    yerel.setUint16(12, tarih, true);
    yerel.setUint32(14, crc, true);
    yerel.setUint32(18, d.veri.length, true);
    yerel.setUint32(22, d.veri.length, true);
    yerel.setUint16(26, ad.length, true);
    yerel.setUint16(28, 0, true);
    parcalar.push(new Uint8Array(yerel.buffer), ad, d.veri);

    const m = new DataView(new ArrayBuffer(46));
    m.setUint32(0, 0x02014b50, true);
    m.setUint16(4, 20, true);
    m.setUint16(6, 20, true);
    m.setUint16(8, 0x0800, true);
    m.setUint16(10, 0, true);
    m.setUint16(12, zaman, true);
    m.setUint16(14, tarih, true);
    m.setUint32(16, crc, true);
    m.setUint32(20, d.veri.length, true);
    m.setUint32(24, d.veri.length, true);
    m.setUint16(28, ad.length, true);
    m.setUint32(42, ofset, true);
    merkez.push(new Uint8Array(m.buffer), ad);
    ofset += 30 + ad.length + d.veri.length;
  }
  const merkezBoyut = merkez.reduce((t, p) => t + p.length, 0);
  const son = new DataView(new ArrayBuffer(22));
  son.setUint32(0, 0x06054b50, true);
  son.setUint16(8, dosyalar.length, true);
  son.setUint16(10, dosyalar.length, true);
  son.setUint32(12, merkezBoyut, true);
  son.setUint32(16, ofset, true);
  const hepsi = [...parcalar, ...merkez, new Uint8Array(son.buffer)];
  const toplam = hepsi.reduce((t, p) => t + p.length, 0);
  const cikti = new Uint8Array(toplam);
  let i = 0;
  for (const p of hepsi) {
    cikti.set(p, i);
    i += p.length;
  }
  return cikti;
}

/* ------------------------------ XML ------------------------------ */

function kacir(metin: string): string {
  return metin
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    // XML 1.0'da izinsiz denetim karakterleri (Excel dosyayı "onarır" yoksa)
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, '');
}

function sutunAdi(i: number): string {
  let s = '';
  let n = i + 1;
  while (n > 0) {
    const k = (n - 1) % 26;
    s = String.fromCharCode(65 + k) + s;
    n = Math.floor((n - 1) / 26);
  }
  return s;
}

function sayfaAdi(ad: string, kullanilan: Set<string>): string {
  let temiz = ad.replace(/[[\]:*?/\\]/g, ' ').trim().slice(0, 31) || 'Sayfa';
  let n = 2;
  const kok = temiz;
  while (kullanilan.has(temiz.toLocaleLowerCase('tr-TR'))) temiz = `${kok.slice(0, 28)} ${n++}`;
  kullanilan.add(temiz.toLocaleLowerCase('tr-TR'));
  return temiz;
}

function hucreXml(deger: Hucre, ref: string, stil?: number): string {
  const s = stil ? ` s="${stil}"` : '';
  if (deger === null || deger === undefined || deger === '') return '';
  if (typeof deger === 'number') {
    return Number.isFinite(deger) ? `<c r="${ref}"${s}><v>${deger}</v></c>` : '';
  }
  if (typeof deger === 'boolean') return `<c r="${ref}" t="inlineStr"${s}><is><t>${deger ? 'Evet' : 'Hayır'}</t></is></c>`;
  const metin =
    deger instanceof Date
      ? deger.toLocaleString('tr-TR', { dateStyle: 'short', timeStyle: 'short' })
      : String(deger);
  return `<c r="${ref}" t="inlineStr"${s}><is><t xml:space="preserve">${kacir(metin)}</t></is></c>`;
}

function sayfaXml(sayfa: XlsxSayfa): string {
  const genislik = sayfa.basliklar.map((b, i) => {
    let en = b.length;
    for (let r = 0; r < Math.min(sayfa.satirlar.length, 400); r++) {
      const d = sayfa.satirlar[r][i];
      if (d !== null && d !== undefined) en = Math.max(en, String(d).length);
    }
    return Math.min(60, Math.max(8, en + 2));
  });
  const sutunlar = genislik.map((g, i) => `<col min="${i + 1}" max="${i + 1}" width="${g}" customWidth="1"/>`).join('');
  const satirlar: string[] = [];
  satirlar.push(
    `<row r="1">${sayfa.basliklar.map((b, i) => hucreXml(b, `${sutunAdi(i)}1`, 1)).join('')}</row>`,
  );
  sayfa.satirlar.forEach((satir, r) => {
    const no = r + 2;
    satirlar.push(`<row r="${no}">${satir.map((d, i) => hucreXml(d, `${sutunAdi(i)}${no}`)).join('')}</row>`);
  });
  const son = `${sutunAdi(Math.max(0, sayfa.basliklar.length - 1))}${sayfa.satirlar.length + 1}`;
  return (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
    '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">' +
    '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>' +
    `<cols>${sutunlar}</cols>` +
    `<sheetData>${satirlar.join('')}</sheetData>` +
    (sayfa.basliklar.length ? `<autoFilter ref="A1:${son}"/>` : '') +
    '</worksheet>'
  );
}

export function xlsxOlustur(sayfalar: XlsxSayfa[]): Blob {
  const kodla = new TextEncoder();
  const kullanilan = new Set<string>();
  const adlar = sayfalar.map((s) => sayfaAdi(s.ad, kullanilan));
  const dosyalar: Array<{ ad: string; veri: Uint8Array }> = [];
  const ekle = (ad: string, metin: string) => dosyalar.push({ ad, veri: kodla.encode(metin) });

  ekle(
    '[Content_Types].xml',
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
      '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">' +
      '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>' +
      '<Default Extension="xml" ContentType="application/xml"/>' +
      '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>' +
      '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>' +
      sayfalar
        .map(
          (_, i) =>
            `<Override PartName="/xl/worksheets/sheet${i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`,
        )
        .join('') +
      '</Types>',
  );
  ekle(
    '_rels/.rels',
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
      '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
      '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>' +
      '</Relationships>',
  );
  ekle(
    'xl/workbook.xml',
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
      '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">' +
      `<sheets>${adlar.map((ad, i) => `<sheet name="${kacir(ad)}" sheetId="${i + 1}" r:id="rId${i + 1}"/>`).join('')}</sheets>` +
      '<definedNames>' +
      sayfalar
        .map((s, i) =>
          s.basliklar.length
            ? `<definedName name="_xlnm._FilterDatabase" localSheetId="${i}" hidden="1">'${kacir(adlar[i]).replace(/'/g, "''")}'!$A$1:$${sutunAdi(s.basliklar.length - 1)}$${s.satirlar.length + 1}</definedName>`
            : '',
        )
        .join('') +
      '</definedNames>' +
      '</workbook>',
  );
  ekle(
    'xl/_rels/workbook.xml.rels',
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
      '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
      sayfalar
        .map(
          (_, i) =>
            `<Relationship Id="rId${i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${i + 1}.xml"/>`,
        )
        .join('') +
      `<Relationship Id="rId${sayfalar.length + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>` +
      '</Relationships>',
  );
  ekle(
    'xl/styles.xml',
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
      '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">' +
      '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>' +
      '<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>' +
      '<fill><patternFill patternType="solid"><fgColor rgb="FFEFF1F5"/><bgColor indexed="64"/></patternFill></fill></fills>' +
      '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>' +
      '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>' +
      '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>' +
      '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/></cellXfs>' +
      '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>' +
      '</styleSheet>',
  );
  sayfalar.forEach((s, i) => ekle(`xl/worksheets/sheet${i + 1}.xml`, sayfaXml(s)));

  const veri = zip(dosyalar);
  return new Blob([veri], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
}

/** Dosyayı indirir (tarayıcıda ve masaüstü kabuğunda aynı). */
export function dosyaIndir(blob: Blob, dosyaAdi: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = dosyaAdi;
  a.rel = 'noopener';
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 4000);
}

/** "Ticketlar-2026-09-30.xlsx" */
export function tarihliAd(kok: string): string {
  const d = new Date();
  const iki = (n: number) => String(n).padStart(2, '0');
  return `${kok}-${d.getFullYear()}-${iki(d.getMonth() + 1)}-${iki(d.getDate())}.xlsx`;
}
