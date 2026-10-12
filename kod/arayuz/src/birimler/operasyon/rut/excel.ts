/**
 * "Excel'e aktar": ekiplere gönderilen günlük rut dosyasının AYNI biçimi — önce ÖZET sayfası, sonra ekip başına bir
 * sayfa (sayfa adı = ekip şefi), sütunlar Excel'deki sırayla. Masaüstü kabuğunda (Turkcell.exe) gerçek Excel'de
 * açılır, tarayıcıda indirilir.
 */

import { dosyaIndir, xlsxOlustur, type Hucre, type XlsxSayfa } from '../../../cekirdek/ortak/xlsx';
import type { RutGun, RutOzet } from './api';

interface KabukApi {
  excel_ac?: (dosyaAdi: string, icerikB64: string) => Promise<{ ok: boolean; hata?: string } | null>;
}

async function base64(blob: Blob): Promise<string> {
  const b = new Uint8Array(await blob.arrayBuffer());
  let s = '';
  for (let i = 0; i < b.length; i += 0x8000) s += String.fromCharCode(...b.subarray(i, i + 0x8000));
  return btoa(s);
}

function hucre(v: unknown): Hucre {
  if (v === null || v === undefined) return null;
  if (typeof v === 'number' || typeof v === 'string' || typeof v === 'boolean') return v;
  return String(v);
}

export function rutSayfalari(gun: RutGun): XlsxSayfa[] {
  const ozetSutun = gun.ozet_sutunlari;
  const toplam = (a: keyof RutOzet) => gun.ozet.reduce((t, o) => t + (Number(o[a]) || 0), 0);
  const ozet: XlsxSayfa = {
    ad: 'ÖZET',
    basliklar: ozetSutun.map((c) => c.baslik),
    satirlar: [
      ...gun.ozet.map((o) => ozetSutun.map((c) => hucre(o[c.id]))),
      ozetSutun.map((c) =>
        c.id === 'sef'
          ? 'TOPLAM'
          : ['mesai_ici', 'iptal_erteleme', 'mesai_disi', 'yan_is', 'mesai_dk'].includes(c.id)
            ? toplam(c.id)
            : null,
      ),
    ],
  };
  const ekipler: XlsxSayfa[] = gun.ekipler.map((e) => ({
    ad: e.ad,
    basliklar: gun.sutunlar.map((c) => c.baslik),
    satirlar: e.satirlar.map((s) => gun.sutunlar.map((c) => hucre(s[c.id]))),
  }));
  return [ozet, ...ekipler];
}

export async function rutExcel(gun: RutGun): Promise<'acildi' | 'indirildi'> {
  const blob = xlsxOlustur(rutSayfalari(gun));
  const [y, a, g] = gun.tarih.split('-');
  const ad = `RUT ${g}.${a}.${y}.xlsx`;
  const api = (window as unknown as { pywebview?: { api?: KabukApi } }).pywebview?.api;
  if (api?.excel_ac) {
    try {
      const sonuc = await api.excel_ac(ad, await base64(blob));
      if (sonuc?.ok) return 'acildi';
    } catch {
      /* köprü hata verdi: indirmeye düş */
    }
  }
  dosyaIndir(blob, ad);
  return 'indirildi';
}
