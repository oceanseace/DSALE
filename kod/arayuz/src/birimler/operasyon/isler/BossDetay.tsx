/**
 * İş çekmecesi ▸ BOSS sekmeleri (Ürünler, İletişim, … Adres Teyidi).
 *
 * Önce `GET /api/isler/{no}/boss-detay`: sunucuda saklı ayrıntı varsa HEMEN çizilir ve "BOSS · 14:32"
 * zamanı yazar. Ayrıntı TAZE_SN'den eskiyse (ya da kullanıcı yenile derse) arka planda
 * `POST …?yenile=true` ile eklentiden tazesi istenir; bu sırada içerik yerinde kalır, yalnız küçük bir
 * "güncelleniyor" işareti görünür (sunucu `yenileniyor` der). Hiç ayrıntı yoksa canlı çekim beklenir:
 * kaç saniyedir beklendiği ve eklentinin isteği alıp almadığı yazar; zaman aşımında neden + "Yeniden dene".
 * Uç yoksa (404) "Sunucu bu bilgiyi henüz vermiyor" yazar. Her öğe TEK SATIR (SekmeIcerigi): ürünler
 * "Marka Model · Seri · Ürün", kayıtlar "tarih · yazan" + metin, diğerleri "Etiket: değer · …"; iç içe kart yok.
 */

import { useEffect, useRef, useState } from 'react';
import { bossDetayGetir, bossDetayIste, hataMetni, type BossDetaySekme, type BossDetayYanit } from '../../../cekirdek/is/api';
import { sunucuZamani } from '../../../cekirdek/ortak/sure';
import { SimgeDugme } from '../../../cekirdek/ortak/Ilkel';
import { Yenile } from '../../../cekirdek/ortak/Ikon';
import { TelefonEylem } from './IsKimlik';

export const SEKMELER: Array<{ k: BossDetaySekme; ad: string }> = [
  { k: 'urunler', ad: 'Ürünler' },
  { k: 'iletisim', ad: 'İletişim' },
  { k: 'aciklama', ad: 'Açıklama' },
  { k: 'ariza_gecmisi', ad: 'Arıza Geçmişi' },
  { k: 'fotograflar', ad: 'Fotoğraflar' },
  { k: 'cihaz', ad: 'Cihaz' },
  { k: 'ariza_nedeni', ad: 'Arıza Nedeni' },
  { k: 'notlar', ad: 'Notlar' },
  { k: 'evraklar', ad: 'Evraklar' },
  { k: 'tarihce', ad: 'Tarihçe' },
  { k: 'adres_teyidi', ad: 'Adres Teyidi' },
];

/** Beklerken sık yokla: eklenti ayrıntıyı ~1–2 sn'de getirir (uzun yoklama + 9 sekme aynı anda). */
const YOKLAMA_MS = 500;
/** Sunucu zaman aşımı bildirmezse istemci en çok bu kadar bekler (sn). */
const VARSAYILAN_ASIM_SN = 90;
/** Saklı ayrıntı bundan yeniyse açılışta BOSS'a yeniden sorulmaz (sn). */
const TAZE_SN = 60;
const TAZE_ALINAMADI = 'BOSS’tan tazesi alınamadı; saklı ayrıntı gösteriliyor.';

type Hal =
  | { tur: 'yukleniyor'; sn: number; eklentiAldi: boolean | null }
  | { tur: 'uc_yok' }
  | { tur: 'hata'; metin: string }
  | { tur: 'veri'; y: BossDetayYanit };

const SEBEP: Record<string, string> = {
  zaman_asimi: 'BOSS Yardımcısı 90 sn içinde yanıt vermedi.',
};

function yasSn(zaman: string | null | undefined): number {
  const d = sunucuZamani(zaman);
  return d ? (Date.now() - d.getTime()) / 1000 : Infinity;
}

function saatMetni(zaman: string | null | undefined): string {
  const d = sunucuZamani(zaman);
  if (!d) return '';
  const iki = (n: number) => String(n).padStart(2, '0');
  const bugun = d.toDateString() === new Date().toDateString();
  return `${bugun ? '' : `${iki(d.getDate())}.${iki(d.getMonth() + 1)} `}${iki(d.getHours())}:${iki(d.getMinutes())}`;
}

export function BossDetay({ isNo, yedekTel }: { isNo: string; yedekTel?: string | null }) {
  const [hal, setHal] = useState<Hal>({ tur: 'yukleniyor', sn: 0, eklentiAldi: null });
  const [tazeleniyor, setTazeleniyor] = useState(false);
  const [tazeHata, setTazeHata] = useState<string | null>(null);
  const [sekme, setSekme] = useState<BossDetaySekme>('urunler');
  /** 0: açılış; >0: kullanıcı "yenile" dedi (saklı olsa da BOSS'a sorulur). */
  const [tur, setTur] = useState(0);
  const halRef = useRef(hal);
  halRef.current = hal;
  const sonIs = useRef<string | null>(null);

  useEffect(() => {
    let bitti = false;
    let zamanlayici = 0;
    const baslangic = Date.now();
    const zorla = tur > 0;
    /* Aynı işte yenileme: içerik yerinde kalır. Yeni iş: baştan. */
    let veriVar = false;
    if (sonIs.current !== isNo) {
      sonIs.current = isNo;
      setHal({ tur: 'yukleniyor', sn: 0, eklentiAldi: null });
    } else {
      const h = halRef.current;
      veriVar = h.tur === 'veri' && h.y.durum === 'hazir';
      if (!veriVar) setHal({ tur: 'yukleniyor', sn: 0, eklentiAldi: null });
    }
    setTazeleniyor(false);
    setTazeHata(null);

    const asildi = (y: BossDetayYanit | null) =>
      (Date.now() - baslangic) / 1000 > (y?.zaman_asimi_sn ?? VARSAYILAN_ASIM_SN) + 15;
    const tazeBitti = (hata: string | null = null) => {
      setTazeleniyor(false);
      setTazeHata(hata);
    };
    const hataGoster = (metin: string) => {
      if (veriVar) tazeBitti(metin);
      else setHal({ tur: 'hata', metin });
    };
    /** GET yanıtını işler; yoklama sürecekse true. */
    const isle = (y: BossDetayYanit | null): boolean => {
      if (!y) {
        if (!veriVar) setHal({ tur: 'uc_yok' });
        tazeBitti();
        return false;
      }
      if (y.durum === 'hazir') {
        veriVar = true;
        setHal({ tur: 'veri', y });
        if (y.yenileniyor && !asildi(y)) {
          setTazeleniyor(true);
          return true;
        }
        tazeBitti(y.yenileniyor ? TAZE_ALINAMADI : null);
        return false;
      }
      if (y.durum === 'bekliyor') {
        if (asildi(y)) {
          if (veriVar) tazeBitti(TAZE_ALINAMADI);
          else setHal({ tur: 'veri', y: { durum: 'yok', hata: 'zaman_asimi' } });
          return false;
        }
        if (veriVar) setTazeleniyor(true);
        else {
          const sn = typeof y.bekleme_sn === 'number' ? Math.round(y.bekleme_sn) : Math.round((Date.now() - baslangic) / 1000);
          setHal({ tur: 'yukleniyor', sn, eklentiAldi: typeof y.eklenti_aldi === 'boolean' ? y.eklenti_aldi : null });
        }
        return true;
      }
      /* yok: istek düştü ya da BOSS'ta ayrıntı yok */
      if (veriVar) tazeBitti(y.hata ? SEBEP[y.hata] ?? y.hata : TAZE_ALINAMADI);
      else setHal({ tur: 'veri', y });
      return false;
    };
    const yokla = async () => {
      if (bitti) return;
      try {
        const y = await bossDetayGetir(isNo);
        if (bitti) return;
        if (isle(y)) zamanlayici = window.setTimeout(() => void yokla(), YOKLAMA_MS);
      } catch (h) {
        if (!bitti) hataGoster(hataMetni(h));
      }
    };
    /** Eklentiden (tazesini) iste, sonra yokla. */
    const iste = async (yenile: boolean) => {
      if (veriVar) setTazeleniyor(true);
      try {
        const y = await bossDetayIste(isNo, yenile);
        if (bitti) return;
        if (!y) {
          if (!veriVar) setHal({ tur: 'uc_yok' });
          tazeBitti();
          return;
        }
        void yokla();
      } catch (h) {
        if (!bitti) hataGoster(hataMetni(h));
      }
    };

    void (async () => {
      /* 1) Saklı ayrıntı varsa hemen çiz. */
      let ilk: BossDetayYanit | null | undefined;
      try {
        ilk = await bossDetayGetir(isNo);
      } catch {
        ilk = undefined; // okunamadı: canlı istemeyi dene
      }
      if (bitti) return;
      if (ilk === null) {
        setHal({ tur: 'uc_yok' });
        return;
      }
      if (ilk?.durum === 'hazir') {
        veriVar = true;
        setHal({ tur: 'veri', y: ilk });
        if (ilk.yenileniyor) {
          setTazeleniyor(true);
          zamanlayici = window.setTimeout(() => void yokla(), YOKLAMA_MS);
        } else if (zorla || yasSn(ilk.zaman) > TAZE_SN) void iste(true);
        return;
      }
      if (ilk?.durum === 'bekliyor') {
        if (isle(ilk)) zamanlayici = window.setTimeout(() => void yokla(), YOKLAMA_MS);
        return;
      }
      /* 2) Saklı yok: canlı iste. */
      void iste(zorla);
    })();
    return () => {
      bitti = true;
      window.clearTimeout(zamanlayici);
    };
  }, [isNo, tur]);

  const sekmeler = hal.tur === 'veri' ? hal.y.sekmeler ?? {} : {};
  const icerik = sekmeler[sekme];
  const yenile = () => setTur((t) => t + 1);
  const yeniden = (
    <button type="button" className="o-dugme kucuk" onClick={yenile}>
      Yeniden dene
    </button>
  );

  return (
    <div className="bd-kok">
      <div className="bd-sekmeler" role="tablist" aria-label="BOSS ayrıntısı">
        {SEKMELER.map((s) => (
          <button
            key={s.k}
            type="button"
            role="tab"
            aria-selected={s.k === sekme}
            className={s.k === sekme ? 'secili' : undefined}
            onClick={() => setSekme(s.k)}
          >
            {s.ad}
            {hal.tur === 'veri' && !bosMu(sekmeler[s.k]) ? <i className="bd-dolu" aria-hidden="true" /> : null}
          </button>
        ))}
      </div>
      <div className="bd-govde" role="tabpanel">
        {hal.tur === 'yukleniyor' ? (
          <div className="bd-bekle" aria-live="polite">
            <div className="bd-yukleniyor">
              <span className="bd-donen" aria-hidden="true" /> BOSS’tan alınıyor…{hal.sn > 0 ? ` (${hal.sn} sn)` : ''}
            </div>
            {hal.eklentiAldi === false && hal.sn >= 10 ? (
              <p className="ip-uyari amber">BOSS Yardımcısı isteği henüz almadı — BOSS sekmesi açık ve eklenti bağlı mı?</p>
            ) : null}
          </div>
        ) : hal.tur === 'uc_yok' ? (
          <p className="ip-sessiz">Sunucu bu bilgiyi henüz vermiyor.</p>
        ) : hal.tur === 'hata' ? (
          <div className="ip-uyari amber bd-sebep">
            <span>{hal.metin}</span>
            {yeniden}
          </div>
        ) : hal.y.durum === 'yok' ? (
          hal.y.hata ? (
            <div className="ip-uyari amber bd-sebep">
              <span>{SEBEP[hal.y.hata] ?? hal.y.hata}</span>
              {yeniden}
            </div>
          ) : (
            <div className="bd-sebep">
              <span className="ip-sessiz">BOSS’ta bu iş için ayrıntı bulunamadı.</span>
              {yeniden}
            </div>
          )
        ) : (
          <>
            <div className="bd-durum">
              <span className="bd-zaman" aria-live="polite">
                {hal.y.zaman ? `BOSS · ${saatMetni(hal.y.zaman)}` : 'BOSS'}
                {tazeleniyor ? (
                  <span className="bd-guncel">
                    <span className="bd-nokta" aria-hidden="true" />
                    güncelleniyor
                  </span>
                ) : tazeHata ? (
                  <span className="bd-guncel hata" title={tazeHata}>
                    güncellenemedi
                  </span>
                ) : null}
              </span>
              <SimgeDugme etiket="BOSS’tan yeniden al" kucuk onClick={yenile} disabled={tazeleniyor}>
                <Yenile boyut={14} />
              </SimgeDugme>
            </div>
            {sekme === 'iletisim' ? <IletisimUstu deger={icerik} yedekTel={yedekTel} /> : null}
            {sekme === 'fotograflar' ? <Fotograflar deger={icerik} /> : null}
            {bosMu(icerik) ? <p className="ip-sessiz">Bu sekmede bilgi yok.</p> : <SekmeIcerigi sekme={sekme} d={jsonCoz(icerik)} />}
          </>
        )}
      </div>
    </div>
  );
}

function bosMu(d: unknown): boolean {
  if (d === null || d === undefined || d === '') return true;
  if (Array.isArray(d)) return d.length === 0;
  if (typeof d === 'object') return Object.keys(d as object).length === 0;
  return false;
}

/** Metin olarak gelen JSON'u ("{…}" / "[…]") nesneye çevirir; olmazsa olduğu gibi. */
function jsonCoz(d: unknown): unknown {
  if (typeof d !== 'string') return d;
  const t = d.trim();
  if (!/^[[{]/.test(t)) return d;
  try {
    return JSON.parse(t);
  } catch {
    return d;
  }
}

/* ------------------------------------------------------------------ sade görünüm (sekme başına satırlar)
   Her öğe tek satır: önemli değerler " · " ile; ayrıntılar küçük "Etiket: değer" satırları. İç içe kart yok;
   sunucunun "alan" kopyası (BOSS'un ham alanları) ayrı başlık olmadan aynı satıra katılır. */

type Nesne = Record<string, unknown>;

/** BOSS alan adı → Türkçe etiket (bilinmeyen ad olduğu gibi, okunur biçimde). */
const ETIKET: Record<string, string> = {
  campaignName: 'Kampanya', brandName: 'Marka', modelName: 'Model', offeringName: 'Ürün', serialNumber: 'Seri',
  productCode: 'Ürün kodu', productName: 'Ürün', deviceReturned: 'İade', documentName: 'Evrak', barcodeCode: 'Barkod',
  description: 'Açıklama', createDate: 'Tarih', createdDate: 'Tarih', status: 'Durum', name: 'Ad', type: 'Tür',
  ad: 'Ad', kod: 'Kod', durum: 'Durum', tur: 'Tür', tarih: 'Tarih', yazan: 'Yazan', olay: 'Olay', aciklama: 'Açıklama',
  metin: 'Metin', neden: 'Neden', eposta: 'E-posta', deger: 'Değer',
};
/** Gösterilmeyen teknik alanlar (BOSS yanıt zarfı, kimlikler). */
const GIZLI = /^(returnCode|returnMessage|isPaginated|page|size|total|id|uuid|.*Id)$/;

function etiket(a: string): string {
  const son = a.split('.').pop() ?? a;
  if (ETIKET[son]) return ETIKET[son];
  const m = son.replace(/_/g, ' ').replace(/([a-zçğıöşü])([A-Z])/g, '$1 $2');
  return m.charAt(0).toLocaleUpperCase('tr-TR') + m.slice(1).toLocaleLowerCase('tr-TR');
}

function yazi(v: unknown): string {
  if (v === null || v === undefined || v === '') return '';
  if (typeof v === 'boolean') return v ? 'Evet' : 'Hayır';
  if (Array.isArray(v)) return v.map(yazi).filter(Boolean).join(', ');
  if (typeof v === 'object') return '';
  return String(v).trim();
}

/** Nesneyi tek düzeye indirir ("alan" altındakiler üst düzeye; iç nesneler "a.b"). */
function duzle(o: Nesne, onek = '', cikti: Nesne = {}, derinlik = 0): Nesne {
  for (const [a, v0] of Object.entries(o)) {
    const v = jsonCoz(v0);
    const ad = a === 'alan' ? onek : onek ? `${onek}.${a}` : a;
    if (v && typeof v === 'object' && !Array.isArray(v) && derinlik < 3) duzle(v as Nesne, ad, cikti, derinlik + 1);
    else if (!(ad in cikti) || cikti[ad] === '' || cikti[ad] == null) cikti[ad] = v;
  }
  return cikti;
}

/** "Etiket: değer" çiftleri (boş ve gizli alanlar düşer; aynı değer iki kez yazılmaz). */
function ciftler(o: Nesne, haric: Set<string> = new Set()): Array<[string, string]> {
  const out: Array<[string, string]> = [];
  const gorulen = new Set<string>();
  for (const [a, v] of Object.entries(duzle(o))) {
    const son = a.split('.').pop() ?? a;
    if (haric.has(son) || GIZLI.test(son)) continue;
    const m = yazi(v);
    if (!m || gorulen.has(`${etiket(a)}|${m}`)) continue;
    gorulen.add(`${etiket(a)}|${m}`);
    out.push([etiket(a), m]);
  }
  return out;
}

const YER_TUTUCU = /^(tt)?\w*(marka|model)$/i;   // BOSS'un sahte marka/model adları (ör. "TTONTMarka")

/** Ürün satırı: "Marka Model · Seri · Ürün" (ör. "HUAWEI HG8010Hv6-10 · 48575443BF0BCDB3 · ONT Modem"). */
function urunSatiri(o: Nesne): { ana: string; kod: string } {
  const d = duzle(o);
  const al = (...adlar: string[]) => {
    for (const a of adlar) {
      const v = yazi(d[a]);
      if (v) return v;
    }
    return '';
  };
  let marka = al('brandName');
  let model = al('modelName');
  if (YER_TUTUCU.test(marka)) marka = '';
  if (YER_TUTUCU.test(model)) model = '';
  if (marka && model.toLocaleUpperCase('tr-TR').startsWith(marka.toLocaleUpperCase('tr-TR'))) {
    model = model.slice(marka.length).replace(/^[\s_-]+/, '');
  }
  model = model.replace(/_/g, ' ');
  const cihaz = [marka, model].filter(Boolean).join(' ');
  const seri = al('serialNumber', 'serialNo', 'seri');
  const urun = al('offeringName', 'productName', 'ad', 'name');
  const parca = [cihaz, seri, urun].filter(Boolean);
  return { ana: parca.join(' · ') || al('kod', 'productCode') || '—', kod: al('productCode', 'kod') };
}

function Urunler({ liste }: { liste: Nesne[] }) {
  const kampanyalar = [...new Set(liste.map((x) => yazi(duzle(x).campaignName)).filter(Boolean))];
  return (
    <>
      {kampanyalar.length ? <p className="bd-ust">Kampanya: {kampanyalar.join(' · ')}</p> : null}
      <ul className="bd-satirlar">
        {liste.map((x, i) => {
          const s = urunSatiri(x);
          return (
            <li key={i} title={s.kod || undefined}>
              {s.ana}
            </li>
          );
        })}
      </ul>
    </>
  );
}

/** Kayıt satırı: üstte metin (varsa), altında "tarih · olay · yazan" ve kalan alanlar tek satırda. */
function KayitSatirlari({ liste, ana, ust }: { liste: Nesne[]; ana: string[]; ust: string[] }) {
  return (
    <ul className="bd-satirlar">
      {liste.map((x, i) => {
        const d = duzle(x);
        const metin = ana.map((a) => yazi(d[a])).filter(Boolean).join(' · ');
        const ustSatir = ust.map((a) => yazi(d[a])).filter(Boolean);
        const kalan = ciftler(x, new Set([...ana, ...ust]));
        return (
          <li key={i}>
            {ustSatir.length ? <span className="bd-meta">{ustSatir.join(' · ')}</span> : null}
            {metin ? <span className="bd-satir-metin">{metin}</span> : null}
            {kalan.length ? <span className="bd-meta">{kalan.map(([e, v]) => `${e}: ${v}`).join(' · ')}</span> : null}
          </li>
        );
      })}
    </ul>
  );
}

/** Genel: her öğe tek satır "Etiket: değer · Etiket: değer". */
function GenelSatirlar({ liste }: { liste: unknown[] }) {
  return (
    <ul className="bd-satirlar">
      {liste.map((x0, i) => {
        const x = jsonCoz(x0);
        if (x && typeof x === 'object' && !Array.isArray(x)) {
          const c = ciftler(x as Nesne);
          return <li key={i}>{c.length ? c.map(([e, v]) => `${e}: ${v}`).join(' · ') : '—'}</li>;
        }
        return <li key={i}>{yazi(x) || '—'}</li>;
      })}
    </ul>
  );
}

function SekmeIcerigi({ sekme, d }: { sekme: BossDetaySekme; d: unknown }) {
  const nesneler = (Array.isArray(d) ? d : [d]).map(jsonCoz);
  const hepsiNesne = nesneler.every((x) => x && typeof x === 'object' && !Array.isArray(x));
  if (!hepsiNesne) return <GenelSatirlar liste={nesneler} />;
  const liste = nesneler as Nesne[];
  switch (sekme) {
    case 'urunler':
      return <Urunler liste={liste} />;
    case 'iletisim':
      return <KayitSatirlari liste={liste} ana={['ad', 'tur', 'telefonlar', 'eposta']} ust={[]} />;
    case 'aciklama':
    case 'notlar':
      return <KayitSatirlari liste={liste} ana={['metin']} ust={['tarih', 'yazan', 'tur']} />;
    case 'tarihce':
    case 'ariza_gecmisi':
      return <KayitSatirlari liste={liste} ana={['olay', 'aciklama']} ust={['tarih', 'yazan']} />;
    case 'fotograflar':
      return <KayitSatirlari liste={liste.map((x) => ({ ...x, url: undefined }))} ana={['ad']} ust={['tarih', 'tur']} />;
    case 'ariza_nedeni': {
      const dolu = liste.filter((x) => yazi(x.neden) || ciftler(x, new Set(['kod'])).length);
      if (!dolu.length) return <p className="ip-sessiz">Arıza nedeni girilmemiş.</p>;
      return <KayitSatirlari liste={dolu} ana={['neden']} ust={[]} />;
    }
    default:
      return <GenelSatirlar liste={liste} />;
  }
}

/** İletişim sekmesindeki telefonları bul (tel, telefon, gsm, cep…). */
function telefonlar(d: unknown, yedek?: string | null): string[] {
  const bulunan = new Set<string>();
  const gez = (x: unknown, anahtar = '') => {
    if (Array.isArray(x)) x.forEach((y) => gez(y, anahtar));
    else if (x && typeof x === 'object') Object.entries(x as Record<string, unknown>).forEach(([a, v]) => gez(v, a));
    else if ((typeof x === 'string' || typeof x === 'number') && /tel|gsm|cep|phone|numara/i.test(anahtar)) {
      const s = String(x).replace(/[^\d+]/g, '');
      if (s.replace(/\D/g, '').length >= 10) bulunan.add(s);
    }
  };
  gez(d);
  if (yedek) {
    const s = yedek.replace(/[^\d+]/g, '');
    if (s.replace(/\D/g, '').length >= 10) bulunan.add(s);
  }
  return [...bulunan];
}

function IletisimUstu({ deger, yedekTel }: { deger: unknown; yedekTel?: string | null }) {
  const liste = telefonlar(deger, yedekTel);
  if (!liste.length) return null;
  return (
    <div className="bd-telefonlar">
      {liste.map((t) => (
        <TelefonEylem key={t} tel={t} />
      ))}
    </div>
  );
}

function Fotograflar({ deger }: { deger: unknown }) {
  const adresler: string[] = [];
  const gez = (x: unknown) => {
    if (Array.isArray(x)) x.forEach(gez);
    else if (x && typeof x === 'object') Object.values(x as Record<string, unknown>).forEach(gez);
    else if (typeof x === 'string' && /^(https?:|data:image\/|\/)/.test(x) && /(\.(jpe?g|png|webp|gif)|data:image|foto|image|resim)/i.test(x)) adresler.push(x);
  };
  gez(deger);
  if (!adresler.length) return null;
  return (
    <div className="bd-fotolar">
      {adresler.map((u) => (
        <a key={u} href={u} target="_blank" rel="noreferrer noopener">
          <img src={u} alt="" loading="lazy" />
        </a>
      ))}
    </div>
  );
}
