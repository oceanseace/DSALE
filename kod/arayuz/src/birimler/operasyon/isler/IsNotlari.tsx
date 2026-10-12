/**
 * İş çekmecesi ▸ Not: yaz → "BOSS’a gönder" (POST /api/isler/{no}/not). Sunucu notu işin geçmişine yazar ve
 * BOSS işiyse BOSS'a yazma kuyruğuna koyar (akis.not_ekle → boss_yazma.kuyruga_ekle → eklenti).
 *
 * Her notun BOSS hâli `GET /api/isler/{no}/boss-yazma-onizleme` kayıtlarından (tur 'not') okunur; kayıt notla
 * metninden (govde.description) ve zamandan eşlenir: BOSS’a gidiyor · BOSS’ta ✓ · hata. Giden kayıt varken
 * birkaç saniyede bir yoklanır. Uç yoksa / izin yoksa (404/403) hâl yazılmaz, notlar yine görünür.
 */

import { useCallback, useEffect, useMemo, useState, type RefObject } from 'react';
import { bossYazmaOnizleme, hataMetni, notEkle, type BossYazmaOnizleme, type BossYazmaOnizlemeKaydi } from '../../../cekirdek/is/api';
import type { IsAyrinti, Olay } from '../../../cekirdek/is/tipler';
import { useBildirim } from '../../../cekirdek/ortak/Bildirim';
import { Hap } from '../../../cekirdek/ortak/Rozet';
import { bossHali, eylemAcik, GIDIYOR } from './BossYazmaHali';
import { sunucuZamani } from '../../../cekirdek/ortak/sure';
import { Bolum, kisaAd } from './parcalar';

const YOKLAMA_MS = 3000;
const YOKLAMA_EN_COK_MS = 3 * 60_000;
/** Kaydı henüz görünmeyen yeni not bu kadar süre "BOSS’a gidiyor" sayılır. */
const YENI_NOT_SN = 60;

const an = (z: string | null | undefined) => sunucuZamani(z)?.getTime() ?? 0;

function aciklama(k: BossYazmaOnizlemeKaydi): string | null {
  const g = Array.isArray(k.govde) ? k.govde[0] : k.govde;
  if (g && typeof g === 'object' && typeof (g as Record<string, unknown>).description === 'string') {
    return String((g as Record<string, unknown>).description).trim();
  }
  return null;
}

/** Notları yazma kayıtlarıyla eşle: önce aynı metin, sonra zamana en yakın; her kayıt bir kez. */
function eslestir(notlar: Olay[], kayitlar: BossYazmaOnizlemeKaydi[]): Map<number, BossYazmaOnizlemeKaydi> {
  const sonuc = new Map<number, BossYazmaOnizlemeKaydi>();
  const bos = new Set(kayitlar.map((k) => k.id));
  const enYakin = (n: Olay, aday: BossYazmaOnizlemeKaydi[]) =>
    aday
      .filter((k) => bos.has(k.id))
      .sort((x, y) => Math.abs(an(x.olusturma) - an(n.zaman)) - Math.abs(an(y.olusturma) - an(n.zaman)))[0];
  for (const n of notlar) {
    const metin = (n.notu ?? '').trim();
    const k = enYakin(n, kayitlar.filter((x) => aciklama(x) === metin));
    if (k) {
      sonuc.set(n.id, k);
      bos.delete(k.id);
    }
  }
  for (const n of notlar) {
    if (sonuc.has(n.id)) continue;
    const k = enYakin(n, kayitlar.filter((x) => aciklama(x) === null && Math.abs(an(x.olusturma) - an(n.zaman)) < 10_000));
    if (k) {
      sonuc.set(n.id, k);
      bos.delete(k.id);
    }
  }
  return sonuc;
}

function zamanMetni(z: string): string {
  const d = sunucuZamani(z);
  if (!d) return '';
  const iki = (n: number) => String(n).padStart(2, '0');
  const bugun = d.toDateString() === new Date().toDateString();
  return `${bugun ? '' : `${iki(d.getDate())}.${iki(d.getMonth() + 1)} `}${iki(d.getHours())}:${iki(d.getMinutes())}`;
}

export function IsNotlari({
  a,
  notRef,
  yenile,
}: {
  a: IsAyrinti;
  notRef: RefObject<HTMLTextAreaElement>;
  /** Not eklendikten sonra işi yeniden oku (geçmiş). */
  yenile: () => void;
}) {
  const bildirim = useBildirim();
  const [metin, setMetin] = useState('');
  const [gidiyor, setGidiyor] = useState(false);
  const [onizleme, setOnizleme] = useState<BossYazmaOnizleme | null>(null);
  const [yoklamaBas, setYoklamaBas] = useState(0);
  const bossIsi = Boolean(a.boss_task_no);

  const notlar = useMemo(() => a.olaylar.filter((o) => o.tur === 'not' && (o.notu ?? '').trim()), [a.olaylar]);

  const oku = useCallback(async () => {
    if (!bossIsi) return;
    try {
      setOnizleme(await bossYazmaOnizleme(a.is_no));
    } catch {
      setOnizleme(null); // uç yok / izin yok: hâl yazılmaz
    }
  }, [a.is_no, bossIsi]);

  /* İş ya da not sayısı değişince oku. */
  useEffect(() => {
    void oku();
  }, [oku, notlar.length]);

  const kayitlar = useMemo(() => (onizleme?.kayitlar ?? []).filter((k) => k.tur === 'not'), [onizleme]);
  const eslesme = useMemo(() => eslestir(notlar, kayitlar), [notlar, kayitlar]);
  const notAcik = eylemAcik(onizleme, 'not');
  const simdi = Date.now();
  const yeniMi = (n: Olay) => bossIsi && simdi - an(n.zaman) < YENI_NOT_SN * 1000;
  const yolda =
    bossIsi &&
    (kayitlar.some((k) => GIDIYOR.has(k.durum)) || notlar.some((n) => !eslesme.has(n.id) && yeniMi(n)));

  /* Giden kayıt varken yokla (en çok YOKLAMA_EN_COK_MS). */
  useEffect(() => {
    if (!yolda) return;
    const bas = yoklamaBas || Date.now();
    if (Date.now() - bas > YOKLAMA_EN_COK_MS) return;
    const t = window.setTimeout(() => void oku(), YOKLAMA_MS);
    return () => window.clearTimeout(t);
  }, [yolda, onizleme, oku, yoklamaBas]);

  const gonder = async () => {
    const m = metin.trim();
    if (!m || gidiyor) return;
    setGidiyor(true);
    try {
      await notEkle(a.is_no, m);
      setMetin('');
      setYoklamaBas(Date.now());
      bildirim.goster(bossIsi ? 'Not eklendi · BOSS’a gönderiliyor.' : 'Not eklendi.', 'basari');
      yenile();
      void oku();
    } catch (e) {
      bildirim.goster(hataMetni(e), 'uyari');
    } finally {
      setGidiyor(false);
    }
  };

  return (
    <Bolum baslik={notlar.length ? `Not (${notlar.length})` : 'Not'}>
      <div className="ip-not-yaz">
        <textarea
          ref={notRef}
          className="o-girdi"
          rows={2}
          value={metin}
          maxLength={1000}
          placeholder={bossIsi ? 'BOSS’a not yazın…' : 'Not yazın…'}
          aria-label="Not"
          onChange={(o) => setMetin(o.target.value)}
          onKeyDown={(o) => {
            if (o.key === 'Enter' && (o.ctrlKey || o.metaKey)) {
              o.preventDefault();
              void gonder();
            }
          }}
        />
        <div className="ip-not-alt">
          <span className="ip-kaynak">{metin.length > 900 ? `${metin.length}/1000 · ` : ''}Ctrl+Enter</span>
          <button type="button" className="o-dugme kucuk" disabled={!metin.trim() || gidiyor} onClick={() => void gonder()}>
            {gidiyor ? 'Gönderiliyor…' : bossIsi ? 'BOSS’a gönder' : 'Ekle'}
          </button>
        </div>
      </div>
      {notlar.length ? (
        <ol className="ip-notlar">
          {notlar.map((n) => {
            const h = bossIsi ? bossHali(eslesme.get(n.id), notAcik, yeniMi(n)) : null;
            return (
              <li key={n.id}>
                <p className="metin">{n.notu}</p>
                <div className="alt">
                  <span>
                    {n.kisi ? kisaAd(n.kisi) : 'Sistem'} · {zamanMetni(n.zaman)}
                  </span>
                  {h ? (
                    <Hap renk={h.renk} baslik={h.ipucu}>
                      {h.metin}
                    </Hap>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ol>
      ) : null}
    </Bolum>
  );
}
