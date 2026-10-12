/**
 * "Askıya al…" (TASKS'ta seçili satırlar, MAP'te seçili noktalar): BOSS ana neden + alt neden + bitiş (en çok 7 gün
 * ileri) + açıklama → seçili işlerin hepsi askıya alınır (`POST /api/isler/toplu-aski`; her iş kendi işleminde) ve her
 * iş için BOSS'a task/suspend kaydı düşer (kimlikler işin kendi kataloğundan). Nedenler seçili işlerin BOSS
 * kataloglarının birleşimidir (`POST /api/isler/toplu-aski/nedenler`); katalog ya da alt neden listesi henüz
 * okunmadıysa birkaç saniyede bir yeniden sorulur. Önceden seçili çift (kullanıcı kararı 09.10; bütün askılar):
 * Abone Kaynaklı (ABONE) > Ulaşılamadı — sunucunun `varsayilan`ı; katalog okunmadan da hazırdır. Alt neden kimliği
 * her iş için kendi kategorisinin listesinden çözülür (sunucu; liste gelene dek BOSS kaydı bekler).
 * Giriş: <TopluAskiPaneli acik kapat satirlar bitti/>. Çağıranlar: Isler.tsx, IsHaritasiEkrani.tsx.
 * TEK iş askısı (İş çekmecesi) de AYNI yolu kullanır: `useAskiFormu` (form + gönderim) → `POST /api/isler/toplu-aski`
 * tek iş numarasıyla. Hızlı seçimler: 2 saat · Yarın 10:00 · 2 gün · 3 gün · 1 hafta (en çok 7 gün).
 */

import { useEffect, useMemo, useState, type ReactNode } from 'react';
import type { IsSatir } from '../../../cekirdek/is/tipler';
import { hataMetni, topluAski, topluAskiNedenleri, type TopluAskiNedenleri } from '../../../cekirdek/is/api';
import { Dugme } from '../../../cekirdek/ortak/Ilkel';
import { Cip, CipSirasi } from '../../../cekirdek/ortak/Suz';
import { Panel } from '../../../cekirdek/ortak/Panel';
import { useIsler } from './durum';
import { yerelKatYaz } from './map/noktalar';
import { useIliskili } from './IliskiliSecim';

const KAPALI = new Set(['cozuldu', 'kapandi']);
const EN_COK_GUN = 7;
const YOKLAMA_MS = 3000;
const YOKLAMA_EN_COK = 20;

const sayi = (n: number) => n.toLocaleString('tr-TR');
const iki = (n: number) => String(n).padStart(2, '0');
const gunMetni = (d: Date) => `${d.getFullYear()}-${iki(d.getMonth() + 1)}-${iki(d.getDate())}`;
const saatMetni = (d: Date) => `${iki(d.getHours())}:${iki(d.getMinutes())}`;

type AskiSatiri = Pick<IsSatir, 'is_no' | 'boss_task_no' | 'durum' | 'boss_durum'>;

/** Bütün askıların önceden seçili BOSS nedeni (sunucu yanıtı gelmeden de; eşi boss_yazma.VARSAYILAN_ASKI). */
export const VARSAYILAN_CIFT = { neden: 'ABONE', alt: 'Ulaşılamadı' } as const;

/** Hızlı bitiş seçimleri (tek ve toplu askıda aynı). "1 hafta sonra" 7 gün sınırını aşmaz. */
export function askiHizliSecimler(simdi: Date): Array<{ etiket: string; an: Date }> {
  const yarin10 = new Date(simdi.getFullYear(), simdi.getMonth(), simdi.getDate() + 1, 10, 0, 0);
  const hafta = new Date(simdi.getTime() + EN_COK_GUN * 86400_000 - 5 * 60_000);
  hafta.setSeconds(0, 0);
  const ikiSaat = new Date(simdi.getTime() + 2 * 3600e3);
  ikiSaat.setSeconds(0, 0);
  return [
    { etiket: '2 saat sonra', an: ikiSaat },
    { etiket: 'Yarın 10:00', an: yarin10 },
    { etiket: '2 gün sonra', an: new Date(yarin10.getTime() + 86400_000) },
    { etiket: '3 gün sonra', an: new Date(yarin10.getTime() + 2 * 86400_000) },
    { etiket: '1 hafta sonra', an: hafta },
  ];
}

interface Sonuc {
  atanan: string[];
  hatalar: Array<{ no: string; neden: string }>;
  boss: { gonderilir: boolean; aciklama: string | null };
}

export interface AskiFormu {
  /** Form alanları (neden, alt neden, bitiş, açıklama) ya da bitti özeti. */
  govde: ReactNode;
  hazir: boolean;
  asama: 'sec' | 'gidiyor' | 'bitti';
  /** Gönderir; dönüş askıya alınan iş numaraları (hata olursa null, metin formda görünür). */
  uygula: () => Promise<string[] | null>;
  acikSayi: number;
}

/** Askı formu: TopluAskiPaneli ve İş çekmecesinin tek iş askısı ortak kullanır. */
export function useAskiFormu({
  acik,
  satirlar,
  bitti,
  tek = false,
}: {
  acik: boolean;
  satirlar: AskiSatiri[];
  bitti?: () => void;
  /** Tek iş (çekmece): bitti özeti gösterilmez, çağıran kapatır. */
  tek?: boolean;
}): AskiFormu {
  const depo = useIsler();
  const acikSatirlar = useMemo(() => satirlar.filter((s) => !KAPALI.has(s.durum)), [satirlar]);
  const seciliNolar = useMemo(() => acikSatirlar.map((s) => s.is_no), [acikSatirlar]);
  const [asama, setAsama] = useState<'sec' | 'gidiyor' | 'bitti'>('sec');
  /* İlişkili işler (aynı müşterinin öbür açık işleri; varsayılan dahil): seçimle birlikte askıya alınır. */
  const iliskili = useIliskili(acik && asama === 'sec', seciliNolar);
  const nolar = useMemo(() => [...seciliNolar, ...iliskili.ekler.map((x) => x.is_no)], [seciliNolar, iliskili.ekler]);
  const taskNo = useMemo(() => {
    const m = new Map(satirlar.map((s) => [s.is_no, s.boss_task_no || s.is_no]));
    iliskili.hepsi.forEach((x) => m.set(x.is_no, x.task_no));
    return (no: string) => m.get(no) ?? no;
  }, [satirlar, iliskili.hepsi]);
  const simdi = new Date(Date.now() + depo.sunucuFarkMs);
  const enGec = new Date(simdi.getTime() + EN_COK_GUN * 86400_000);

  const [katalog, setKatalog] = useState<TopluAskiNedenleri | null>(null);
  const [katalogHata, setKatalogHata] = useState<string | null>(null);
  const [yoklama, setYoklama] = useState(0);
  const [neden, setNeden] = useState('');
  const [alt, setAlt] = useState('');
  const [gun, setGun] = useState(() => gunMetni(new Date(simdi.getTime() + 86400_000)));
  const [saat, setSaat] = useState('18:00');
  const [aciklama, setAciklama] = useState('');
  const [sonuc, setSonuc] = useState<Sonuc | null>(null);
  const [hata, setHata] = useState<string | null>(null);

  useEffect(() => {
    if (!acik) return;
    setAsama('sec');
    setSonuc(null);
    setHata(null);
    setKatalog(null);
    setYoklama(0);
  }, [acik]);

  /* Nedenler: açılışta ve katalog / alt neden listesi beklenirken birkaç saniyede bir. */
  useEffect(() => {
    if (!acik || !seciliNolar.length || asama !== 'sec') return undefined;
    let iptal = false;
    const t = window.setTimeout(
      () => {
        topluAskiNedenleri(seciliNolar)
          .then((y) => {
            if (iptal) return;
            setKatalog(y);
            setKatalogHata(null);
            const bekliyor = y.bekleniyor || y.katalogsuz > 0 || !y.alt_biliniyor;
            if (bekliyor && yoklama < YOKLAMA_EN_COK) setYoklama((n) => n + 1);
          })
          .catch((h) => !iptal && setKatalogHata(hataMetni(h)));
      },
      yoklama ? YOKLAMA_MS : 0,
    );
    return () => {
      iptal = true;
      window.clearTimeout(t);
    };
  }, [acik, seciliNolar, asama, yoklama]);

  /* Varsayılan ana neden: Abone kaynaklı (ABONE) — sunucunun önerdiği çift. */
  const vars = katalog?.varsayilan ?? VARSAYILAN_CIFT;
  useEffect(() => {
    if (!katalog?.nedenler.length || neden) return;
    const v = katalog.nedenler.find((n) => n.kod === vars.neden) ?? katalog.nedenler[0];
    setNeden(v.kod || v.ad || '');
  }, [katalog, neden, vars.neden]);
  const secili = katalog?.nedenler.find((n) => (n.kod || n.ad) === neden) ?? null;
  const altlar = secili?.alt ?? [];
  const altImza = altlar.join('|');
  useEffect(() => {
    // önceden seçili: varsayılan alt neden ("Ulaşılamadı"); kullanıcının seçimi listede kaldıkça korunur
    const onerilen = secili?.kod === vars.neden ? vars.alt : '';
    if (altlar.length) setAlt((a) => (altlar.includes(a) ? a : altlar.includes(onerilen) ? onerilen : ''));
    else setAlt((a) => a || onerilen);
    // altImza: liste içeriği değişince
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [altImza, secili?.kod, vars.alt, vars.neden]);

  const hizliSec = (d: Date) => {
    setGun(gunMetni(d));
    setSaat(saatMetni(d));
  };
  const bitis = `${gun} ${saat}:00`;
  const bitisTarih = new Date(`${gun}T${saat}:00`);
  const bitisGecerli = !Number.isNaN(bitisTarih.getTime()) && bitisTarih > simdi && bitisTarih <= enGec;
  const hazir = Boolean(secili) && bitisGecerli && Boolean(alt.trim()) && acikSatirlar.length > 0;

  const uygula = async (): Promise<string[] | null> => {
    if (!hazir || !secili) return null;
    setAsama('gidiyor');
    setHata(null);
    try {
      const y = await topluAski({
        is_nolar: nolar,
        neden: secili.kod || secili.ad || '',
        alt: alt.trim() || null,
        bitis,
        aciklama: aciklama.trim() || null,
      });
      setSonuc({
        atanan: y.atanan,
        hatalar: y.atlanan.map((a) => ({ no: a.is_no, neden: a.hata || a.kod })),
        boss: y.boss,
      });
      const askiya = new Set(y.atanan);
      yerelKatYaz([...satirlar, ...iliskili.ekler].filter((s) => askiya.has(s.is_no)), 'askiya_alindi'); // MAP: BOSS eşitlemesini beklemeden
      void depo.tazele();
      if (tek && !y.atanan.length) {
        setHata(y.atlanan[0]?.hata || y.atlanan[0]?.kod || 'Askıya alınamadı.');
        setAsama('sec');
        return null;
      }
      setAsama(tek ? 'sec' : 'bitti');
      if (y.atanan.length) bitti?.();
      return y.atanan;
    } catch (h) {
      setHata(hataMetni(h));
      setAsama('sec');
      return null;
    }
  };

  const govde = (
      <div className="ta-kok">
        {asama === 'bitti' && sonuc ? (
          <div className="ta-ozet" aria-live="polite">
            <p className="ta-baslik">
              {secili?.ad ?? neden}
              {alt ? ` · ${alt}` : ''} · {gun.split('-').reverse().join('.')} {saat}
            </p>
            <div className="ta-sayilar">
              <span className="ta-sayi yesil">
                <b>{sayi(sonuc.atanan.length)}</b> ✓ askıya alındı
              </span>
              {sonuc.hatalar.length ? (
                <span className="ta-sayi kirmizi">
                  <b>{sayi(sonuc.hatalar.length)}</b> hata
                </span>
              ) : null}
            </div>
            <p className="ta-not">
              {sonuc.boss.gonderilir
                ? 'BOSS’a her iş için askı isteği gidiyor (BOSS sekmesi açık olmalı); sonucu iş çekmecesinde görünür.'
                : sonuc.boss.aciklama || 'BOSS’a askı yazma henüz kapalı: kayıtlar önizlemede bekler.'}
            </p>
            {sonuc.hatalar.length ? (
              <ul className="ta-hatalar">
                {sonuc.hatalar.map((h) => (
                  <li key={h.no}>
                    <b>{taskNo(h.no)}</b> {h.neden}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : (
          <>
            {katalogHata ? <p className="ip-uyari kirmizi">{katalogHata}</p> : null}
            {!katalog && !katalogHata ? <p className="ta-not">BOSS askı nedenleri okunuyor…</p> : null}
            {katalog && !katalog.nedenler.length ? (
              <p className="ip-uyari">
                BOSS askı nedenleri henüz okunmadı{katalog.katalogsuz ? ' (eklenti okuyor; BOSS sekmesi açık olmalı)' : ''}.
              </p>
            ) : null}
            {katalog?.nedenler.length ? (
              <>
                <label className="ta-alan">
                  <span>Ana neden</span>
                  <select className="o-girdi" value={neden} onChange={(o) => setNeden(o.target.value)}>
                    {katalog.nedenler.map((n) => (
                      <option key={n.kod || n.ad || ''} value={n.kod || n.ad || ''}>
                        {n.ad}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="ta-alan">
                  <span>Alt neden</span>
                  {altlar.length ? (
                    <select className="o-girdi" value={alt} onChange={(o) => setAlt(o.target.value)}>
                      <option value="">Seçin…</option>
                      {altlar.map((a) => (
                        <option key={a} value={a}>
                          {a}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <>
                      <input
                        className="o-girdi"
                        value={alt}
                        maxLength={160}
                        placeholder="Alt neden adı (BOSS’taki gibi)"
                        onChange={(o) => setAlt(o.target.value)}
                      />
                      <span className="ip-uyari" role="status">
                        Alt neden listesi bekleniyor — BOSS’ta bir işi elle askıya alırken bu ana nedeni seçin; eklenti
                        listeyi getirir. Şimdi askıya alınırsa BOSS kaydı liste gelene dek bekler, sonra bu adla gider.
                      </span>
                    </>
                  )}
                </label>
              </>
            ) : null}
            <div className="ta-alan">
              <span>Bitiş (en çok {EN_COK_GUN} gün)</span>
            <CipSirasi etiket="Hızlı bitiş">
              {askiHizliSecimler(simdi).map((u) => (
                <Cip key={u.etiket} secili={gun === gunMetni(u.an) && saat === saatMetni(u.an)} onClick={() => hizliSec(u.an)}>
                  {u.etiket}
                </Cip>
              ))}
            </CipSirasi>
              <div className="o-arac">
                <input
                  className="o-girdi"
                  type="date"
                  value={gun}
                  min={gunMetni(simdi)}
                  max={gunMetni(enGec)}
                  onChange={(o) => setGun(o.target.value)}
                  aria-label="Bitiş günü"
                />
                <input
                  className="o-girdi"
                  type="time"
                  step={900}
                  value={saat}
                  onChange={(o) => setSaat(o.target.value)}
                  aria-label="Bitiş saati"
                />
              </div>
              {!bitisGecerli ? <span className="ip-uyari kirmizi">Bitiş ileride ve en çok {EN_COK_GUN} gün sonra olmalı.</span> : null}
            </div>
            {iliskili.govde}
            <label className="ta-alan">
              <span>Açıklama</span>
              <textarea
                className="o-girdi"
                rows={3}
                maxLength={500}
                value={aciklama}
                placeholder="Boşsa BOSS’a: Teknik ekibe iletildi"
                onChange={(o) => setAciklama(o.target.value)}
              />
            </label>
            {hata ? <p className="ip-uyari kirmizi">{hata}</p> : null}
            <p className="ta-not">
              {katalog && !katalog.gonderilir
                ? 'BOSS’a askı yazma alt neden listesi gelene dek önizlemede bekler.'
                : tek
                ? 'İş BOSS’ta da askıya alınır (BOSS sekmesi açık olmalı); sonucu çekmecede görünür.'
                : 'Her iş BOSS’ta da askıya alınır (BOSS sekmesi açık olmalı).'}
            </p>
          </>
        )}
      </div>
  );

  return { govde, hazir, asama, uygula, acikSayi: nolar.length };
}

export function TopluAskiPaneli({
  acik,
  kapat,
  satirlar,
  bitti,
}: {
  acik: boolean;
  kapat: () => void;
  satirlar: IsSatir[];
  /** İşlem bitince (seçimi temizlemek için). */
  bitti?: () => void;
}) {
  const f = useAskiFormu({ acik, satirlar, bitti });
  const kapaliSayi = satirlar.length - f.acikSayi;
  const altBolum =
    f.asama === 'bitti' ? (
      <Dugme tur="birincil" genis onClick={kapat}>
        Kapat
      </Dugme>
    ) : (
      <>
        <Dugme tur="metin" onClick={kapat} disabled={f.asama === 'gidiyor'}>
          Vazgeç
        </Dugme>
        <Dugme tur="birincil" disabled={!f.hazir || f.asama === 'gidiyor'} onClick={() => void f.uygula()}>
          {f.asama === 'gidiyor' ? 'Askıya alınıyor…' : `${sayi(f.acikSayi)} işi askıya al`}
        </Dugme>
      </>
    );
  return (
    <Panel
      acik={acik}
      kapat={kapat}
      kilitli={f.asama === 'gidiyor'}
      baslik="Askıya al"
      altBaslik={`${sayi(f.acikSayi)} iş seçili${kapaliSayi ? ` · ${sayi(kapaliSayi)} kapalı iş atlanır` : ''}`}
      alt={altBolum}
    >
      {f.govde}
    </Panel>
  );
}
