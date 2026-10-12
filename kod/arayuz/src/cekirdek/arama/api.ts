/**
 * Arama ucu: GET /api/ara?q=&tur= — gruplu sonuç, izin süzgeci sunucuda.
 * Aynı sorgu kısa süre bellekte tutulur (geri silince anında döner); diske yazılmaz.
 */

import { istek } from '../api/istemci';

export type AramaTuru = 'bina' | 'is' | 'kisi' | 'mahalle' | 'obek';

export interface AramaSonucu {
  tur: AramaTuru;
  id: string | number;
  baslik: string;
  alt?: string;
  puan?: number;
  // bina
  serial?: string;
  location_id?: string | null;
  lat?: number | null;
  lon?: number | null;
  bolge?: number | null;
  pasif?: boolean;
  // iş
  is_no?: string;
  task_no?: string | null;
  durum?: string;
  acik?: boolean;
  musteri_no?: string | null;
  musteri_adi?: string | null;
  bina_serial?: string | null;
  // kişi
  rol?: string;
  aktif?: boolean;
}

export interface AramaGrubu {
  tur: AramaTuru;
  baslik: string;
  toplam: number;
  sonuclar: AramaSonucu[];
}

export interface AramaYaniti {
  q: string;
  gruplar: AramaGrubu[];
  toplam: number;
  sure_ms: number;
}

const bellek = new Map<string, { zaman: number; y: AramaYaniti }>();
const OMUR_MS = 20_000;

export async function ara(q: string, tur: AramaTuru | null, isaret?: AbortSignal): Promise<AramaYaniti> {
  const anahtar = `${tur ?? ''}|${q}`;
  const eski = bellek.get(anahtar);
  if (eski && Date.now() - eski.zaman < OMUR_MS) return eski.y;
  const y = await istek<AramaYaniti>(
    `/api/ara?q=${encodeURIComponent(q)}${tur ? `&tur=${tur}` : ''}`,
    { isaret, zamanAsimiMs: 10_000 },
  );
  bellek.set(anahtar, { zaman: Date.now(), y });
  if (bellek.size > 60) bellek.delete(bellek.keys().next().value as string);
  return y;
}
