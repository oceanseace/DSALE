/**
 * "Excel'de aç": TASKS'ın o anki süzülmüş/sıralı satırları ve görünür sütunlarıyla gerçek .xlsx üretir
 * (cekirdek/ortak/xlsx.ts). Masaüstü kabuğunda (Turkcell.exe, `window.pywebview.api.excel_ac`) dosya gizli
 * tmp klasörüne yazılıp gerçek Excel'de açılır; tarayıcıda indirilir. Giriş: `excelAc(satirlar, sutunlar)`.
 * Kim: Isler.tsx. Köprünün Python tarafı: kod/masaustu/turkcell.py → KabukApi.excel_ac.
 */

import type { IsSatir } from '../../../cekirdek/is/tipler';
import { dosyaIndir, xlsxOlustur, type Hucre } from '../../../cekirdek/ortak/xlsx';
import { metinKalmali } from './pano';
import type { Sutun } from './sutunlar';

interface KabukApi {
  excel_ac?: (dosyaAdi: string, icerikB64: string) => Promise<{ ok: boolean; hata?: string } | null>;
}

function hucre(c: Sutun, s: IsSatir): Hucre {
  const v = c.deger(s);
  const n = c.sayi?.(s);
  if (n !== null && n !== undefined && !metinKalmali(c, v)) return n;
  return v;
}

/** "TASKS-2026-10-06-1712.xlsx" — dakikası olan ad: açık duran eski dosyanın üstüne yazmaya kalkmaz. */
function dosyaAdi(): string {
  const d = new Date();
  const iki = (n: number) => String(n).padStart(2, '0');
  return `TASKS-${d.getFullYear()}-${iki(d.getMonth() + 1)}-${iki(d.getDate())}-${iki(d.getHours())}${iki(d.getMinutes())}.xlsx`;
}

async function base64(blob: Blob): Promise<string> {
  const b = new Uint8Array(await blob.arrayBuffer());
  let s = '';
  for (let i = 0; i < b.length; i += 0x8000) s += String.fromCharCode(...b.subarray(i, i + 0x8000));
  return btoa(s);
}

/** Dosyayı Excel'de açar ya da indirir; hangisinin olduğunu döner. */
export async function excelAc(satirlar: IsSatir[], sutunlar: Sutun[]): Promise<'acildi' | 'indirildi'> {
  const blob = xlsxOlustur([
    {
      ad: 'TASKS',
      basliklar: sutunlar.map((c) => c.baslik),
      satirlar: satirlar.map((s) => sutunlar.map((c) => hucre(c, s))),
    },
  ]);
  const ad = dosyaAdi();
  const api = (window as unknown as { pywebview?: { api?: KabukApi } }).pywebview?.api;
  if (api?.excel_ac) {
    try {
      const y = await api.excel_ac(ad, await base64(blob));
      if (y?.ok) return 'acildi';
    } catch {
      /* köprü hata verdi: indirmeye düş */
    }
  }
  dosyaIndir(blob, ad);
  return 'indirildi';
}
