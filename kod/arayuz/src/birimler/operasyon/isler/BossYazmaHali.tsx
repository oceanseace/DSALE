/**
 * BOSS'a yazma kaydının uygulamadaki hâli (not ve atama için ortak): BOSS’a gidiyor · BOSS’ta ✓ · hata (mesajıyla) ·
 * yazma kapalı. Kayıtlar `GET /api/isler/{no}/boss-yazma-onizleme`'den; `eylemler[tur]` o eylemin BOSS'a gerçekten
 * gidip gitmediğini söyler (eylemin kendi anahtarı + doğrulanmış şablon).
 *
 * `BossAtamaDurumu`: iş çekmecesinde (Planla) atamanın + randevunun BOSS hâli. Uygulamada teknisyen ve saat seçilince
 * sunucu kaydı kuyruğa koyar (akis.ata → boss_yazma), eklenti BOSS'a yazar; burada sonucu görünür. Giden kayıt
 * varken birkaç saniyede bir yoklanır.
 */

import { useCallback, useEffect, useState } from 'react';
import { bossYazmaOnizleme, type BossYazmaOnizleme, type BossYazmaOnizlemeKaydi } from '../../../cekirdek/is/api';
import type { IsAyrinti } from '../../../cekirdek/is/tipler';
import { Hap } from '../../../cekirdek/ortak/Rozet';
import { git } from '../../../cekirdek/yol/rota';
import { useOturum } from '../../../cekirdek/yerel/oturum';
import { dilimMetni } from './parcalar';

export type HalRengi = 'mor' | 'amber' | 'kirmizi' | 'gri' | 'mavi' | 'yesil';
export interface BossHali {
  metin: string;
  renk: HalRengi;
  ipucu?: string;
  /** Hata satırında gösterilecek BOSS/eklenti mesajı. */
  hata?: string;
}

export const GIDIYOR = new Set(['bekliyor', 'gonderiliyor']);

/** Önizlemede bu eylem BOSS'a gerçekten gider mi (eski sunucu `eylemler` vermez: genel anahtara bakılır). */
export function eylemAcik(o: BossYazmaOnizleme | null, tur: string): boolean {
  return (o?.eylemler?.[tur] ?? o?.yazma) === 'acik';
}

export function bossHali(k: BossYazmaOnizlemeKaydi | undefined, acik: boolean, yeni: boolean): BossHali | null {
  if (!k) return yeni ? { metin: 'BOSS’a gidiyor', renk: 'mavi' } : null;
  const e = k.eklenti;
  switch (k.durum) {
    case 'bekliyor':
      return acik
        ? { metin: 'BOSS’a gidiyor', renk: 'mavi', ipucu: 'BOSS sekmesi açıkken birkaç saniyede yazılır.' }
        : { metin: 'BOSS’a yazma kapalı', renk: 'gri', ipucu: 'Yönetici BOSS’a yazmayı açınca gönderilir.' };
    case 'gonderiliyor':
      return { metin: 'BOSS’a gidiyor', renk: 'mavi' };
    case 'onizleme':
      return { metin: 'Gönderilmedi · yazma kapalı', renk: 'gri', ipucu: 'BOSS’a yazma kapalıyken yalnız önizlenir.' };
    case 'gonderildi': {
      const rc = e?.return_kodu;
      if (rc === null || rc === undefined || String(rc) === '0') return { metin: 'BOSS’ta ✓', renk: 'yesil' };
      const m = e?.return_mesaji || `returnCode ${rc}`;
      return { metin: 'BOSS hata', renk: 'kirmizi', ipucu: m, hata: m };
    }
    case 'eksik': {
      const m = k.eksik?.length ? `Eksik: ${k.eksik.join(', ')}` : 'Eksik bilgi';
      return { metin: 'Bekliyor · eksik bilgi', renk: 'amber', ipucu: m, hata: m };
    }
    case 'hata':
    case 'zaman_asimi': {
      const m =
        e?.return_mesaji ||
        (e?.belirsiz ? 'Sonuç gelmedi; BOSS’ta bakın.' : e?.hata) ||
        (k.durum === 'zaman_asimi' ? 'Zaman aşımı' : 'BOSS’a yazılamadı');
      return { metin: 'Hata', renk: 'kirmizi', ipucu: m, hata: m };
    }
    case 'yerine_yeni':
      return null;
    default:
      return { metin: k.durum, renk: 'gri' };
  }
}

/** Atama kaydındaki eksik alan adları → kullanıcı dili. */
const EKSIK_ADI: Record<string, string> = {
  resourceId: 'teknisyenin BOSS ekibi yok (Kişiler’de BOSS ekibi eşleyin)',
  taskId: 'işin BOSS kimliği henüz gelmedi (eşitlemeyi bekleyin)',
  autoId: 'BOSS task no 9 haneli değil',
  start: 'randevu saati yok',
  end: 'randevu saati yok',
  customerFullName: 'müşteri adı yok',
  customerNo: 'müşteri no yok',
};

function atamaDilimi(k: BossYazmaOnizlemeKaydi): string {
  const g = (Array.isArray(k.govde) ? k.govde[0] : k.govde) as Record<string, unknown> | null;
  const bas = typeof g?.start === 'string' ? g.start : null;
  const bit = typeof g?.end === 'string' ? g.end : null;
  return bas ? dilimMetni(bas, bit) : '';
}

const YOKLAMA_MS = 3000;
const YOKLAMA_EN_COK_MS = 5 * 60_000;

/** `yeniden`: hata hâlinde "Yeniden dene" düğmesi (atama: POST /api/boss/atama-yeniden). */
export function BossAtamaDurumu({ a, yeniden }: { a: IsAyrinti; yeniden?: () => void }) {
  return <BossKayitDurumu a={a} tur="atama" yeniden={yeniden} />;
}

/** Askının BOSS hâli (task/suspend): tek iş ve toplu askı aynı kuyruğu kullanır. */
export function BossAskiDurumu({ a, yeniden }: { a: IsAyrinti; yeniden?: () => void }) {
  return <BossKayitDurumu a={a} tur="aski" yeniden={yeniden} />;
}

const ASKI_EKSIK: Record<string, string> = {
  taskId: 'işin BOSS kimliği henüz gelmedi (eşitlemeyi bekleyin)',
  suspendReasonId: 'BOSS askı nedeni listesi okunuyor (BOSS sekmesi açık olmalı)',
  suspendSubReasonId: 'BOSS alt neden listesi bekleniyor',
  suspendStatusEndDate: 'bitiş zamanı yok',
};

function askiBitisi(k: BossYazmaOnizlemeKaydi): string {
  const g = (Array.isArray(k.govde) ? k.govde[0] : k.govde) as Record<string, unknown> | null;
  return typeof g?.suspendStatusEndDate === 'string' ? `bitiş ${g.suspendStatusEndDate}` : '';
}

function BossKayitDurumu({ a, tur, yeniden }: { a: IsAyrinti; tur: 'atama' | 'aski'; yeniden?: () => void }) {
  const { izinli } = useOturum();
  const [onizleme, setOnizleme] = useState<BossYazmaOnizleme | null>(null);
  const [bas, setBas] = useState(() => Date.now());
  const bossIsi = Boolean(a.boss_task_no);

  const oku = useCallback(async () => {
    if (!bossIsi) return;
    try {
      setOnizleme(await bossYazmaOnizleme(a.is_no));
    } catch {
      setOnizleme(null); // uç yok / izin yok: hâl yazılmaz
    }
  }, [a.is_no, bossIsi]);

  /* İş değişince (atama / randevu yapıldı: sürüm artar) yeniden oku ve yoklamayı tazele. */
  useEffect(() => {
    setBas(Date.now());
    void oku();
  }, [oku, a.surum]);

  const son = (onizleme?.kayitlar ?? []).find((k) => k.tur === tur && k.durum !== 'yerine_yeni');
  const gidiyor = Boolean(son && GIDIYOR.has(son.durum));
  useEffect(() => {
    if (!gidiyor || Date.now() - bas > YOKLAMA_EN_COK_MS) return;
    const t = window.setTimeout(() => void oku(), YOKLAMA_MS);
    return () => window.clearTimeout(t);
  }, [gidiyor, onizleme, oku, bas]);

  if (!bossIsi || !son) return null;
  const h = bossHali(son, eylemAcik(onizleme, tur), false);
  if (!h) return null;
  const dilim = tur === 'atama' ? atamaDilimi(son) : askiBitisi(son);
  const adlar = tur === 'atama' ? EKSIK_ADI : ASKI_EKSIK;
  const eksik = son.durum === 'bekliyor' && son.eksik?.length ? son.eksik.map((x) => adlar[x] ?? x) : [];
  return (
    <div className="ip-boss-yazma" aria-live="polite">
      <span className="ip-kaynak">{tur === 'atama' ? 'BOSS randevusu' : 'BOSS askısı'}{dilim ? ` · ${dilim}` : ''}{son.kisi ? ` · ${son.kisi}` : ''}</span>
      <Hap renk={eksik.length ? 'amber' : h.renk} baslik={h.ipucu}>
        {eksik.length ? 'Bekliyor · eksik bilgi' : h.metin}
      </Hap>
      {eksik.length ? <p className="ip-uyari amber">{[...new Set(eksik)].join(' · ')}</p> : null}
      {izinli('is.ata') && a.boss_task_no ? (
        <button
          type="button"
          className="o-bag ip-ic-bag"
          onClick={() => git(`/yonetici/boss/kuyruk?ara=${encodeURIComponent(a.boss_task_no!)}`)}
        >
          BOSS kuyruğunda gör
        </button>
      ) : null}
      {!eksik.length && h.hata ? (
        <p className="ip-uyari kirmizi">
          <span>BOSS: {h.hata}</span>
          {yeniden && h.renk === 'kirmizi' ? (
            <button type="button" className="o-dugme kucuk" onClick={yeniden}>
              Yeniden dene
            </button>
          ) : null}
        </p>
      ) : null}
    </div>
  );
}
