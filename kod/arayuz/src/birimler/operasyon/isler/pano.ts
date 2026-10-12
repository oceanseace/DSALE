/**
 * Ctrl+C: seçili alanı panoya — düz metin sekmeyle ayrılmış (TSV), yanında HTML tablo.
 * Excel önce HTML'i okur: Task No / Müşteri No / telefon METİN biçimiyle gider, 05… ve 12+ hane bozulmaz;
 * Not Defteri gibi yerlere TSV düşer. Giriş: `alaniKopyala(satirlar, sutunlar, alan)`. Kim: Tablo.tsx.
 */

import type { IsSatir } from '../../../cekirdek/is/tipler';
import type { Alan } from './secim';
import type { Sutun } from './sutunlar';

const kacir = (m: string) => m.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

/** Excel'in sayıya ya da bilimsel gösterime çevireceği numara mı. */
export function metinKalmali(c: Sutun, v: string): boolean {
  return Boolean(c.numara) || /^0\d/.test(v) || /^\d{12,}$/.test(v);
}

function hucreMetni(c: Sutun, s: IsSatir): string {
  const n = c.sayi?.(s);
  // Türkçe Excel ondalığı virgülle okur.
  if (n !== null && n !== undefined) return String(n).replace('.', ',');
  return c.deger(s).replace(/[\t\r\n]+/g, ' ');
}

export function alanMetni(satirlar: IsSatir[], sutunlar: Sutun[], alan: Alan): { duz: string; html: string } {
  const duz: string[] = [];
  const html: string[] = [];
  for (let r = alan.r1; r <= alan.r2; r++) {
    const s = satirlar[r];
    if (!s) continue;
    const d: string[] = [];
    const h: string[] = [];
    for (let c = alan.c1; c <= alan.c2; c++) {
      const k = sutunlar[c];
      if (!k) continue;
      const v = hucreMetni(k, s);
      d.push(v);
      h.push(metinKalmali(k, v) ? `<td style='mso-number-format:"\\@"'>${kacir(v)}</td>` : `<td>${kacir(v)}</td>`);
    }
    duz.push(d.join('\t'));
    html.push(`<tr>${h.join('')}</tr>`);
  }
  return {
    duz: duz.join('\r\n'),
    html: `<meta charset="utf-8"><table>${html.join('')}</table>`,
  };
}

/** Panoya iki biçimle yazar; olmazsa yalnız düz metin. Başarıyı döner. */
export async function panoyaYaz(duz: string, html: string): Promise<boolean> {
  let tamam = false;
  const dinle = (o: ClipboardEvent) => {
    if (!o.clipboardData) return;
    o.clipboardData.setData('text/plain', duz);
    o.clipboardData.setData('text/html', html);
    o.preventDefault();
    tamam = true;
  };
  document.addEventListener('copy', dinle, true);
  try {
    // Kullanıcı tuşuna basarken çağrılır: HTTP (ofis ağı) üzerinde de çalışır.
    document.execCommand('copy');
  } catch {
    /* aşağıdaki yola düş */
  } finally {
    document.removeEventListener('copy', dinle, true);
  }
  if (tamam) return true;
  try {
    await navigator.clipboard.writeText(duz);
    return true;
  } catch {
    return false;
  }
}
