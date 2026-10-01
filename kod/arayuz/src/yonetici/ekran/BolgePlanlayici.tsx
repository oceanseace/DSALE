/**
 * Bölge planlayıcı — "8 ekipten 14 ekibe çıkınca bölgeler dinamik bölünsün".
 *
 * Üç adım, hepsi bu ekranda:
 *   1. Kaç satışçı? (2…50) → "Önizle": yeni sınırlar haritada, bölge başına
 *      sayılar tabloda, üstte tek cümle: "9.171 bina el değiştirir, geçmiş
 *      ziyaretler korunur".
 *   2. "Uygula": onay penceresi ne olacağını madde madde söyler. Yeni bölgeler
 *      için açılan hesapların davet kodları hemen ekranda.
 *   3. "Geri al": bir önceki plana döner (binalar ve satışçılar eski yerine).
 *
 * Hazır plan yoksa (ya da güncel veriyle yeniden hesap istenirse) sunucu arka
 * planda hesaplar; ekran ilerlemeyi gösterir ve bitince önizlemeyi kendisi açar.
 * Ziyaret, görev ve satış kayıtlarına hiçbir adımda dokunulmaz (sözleşme §7.2).
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { SahaHatasi } from '../../api/istemci';
import { Cekmece } from '../../ortak/Cekmece';
import { useBildirim } from '../../ortak/Bildirim';
import { kopyala } from '../../ortak/kimlik';
import { sayi, yuzde } from '../../ortak/bicim';
import { GeriAl, Onay, Uyari, Yenile } from '../../ortak/Ikon';
import {
  bolgelemeDurumu,
  bolgelemeOnizle,
  hesapIsi,
  planExceliIndir,
  planGeriAl,
  planUygula,
} from '../api';
import { useYonetim } from '../depo';
import { Icerik, YonUst, bolumeGit } from '../ortak/Kabuk';
import { HataKutusu, Iskelet, Kart, OranCubugu, useVeri } from '../ortak/parcalar';
import { Indir } from '../ortak/simgeler';
import type {
  BolgelemeDurumu,
  HesapIsi,
  PlanBolgesi,
  PlanGecmisi,
  PlanOlcusu,
  PlanOnizlemesi,
  PlanUygulamaYaniti,
} from '../tipler';
import { BolgeHaritasi, yaziRengi } from './bolge/BolgeHaritasi';
import { bolgeSayisiniTazele } from './bolge/bolgeSayisi';
import './faz2.css';

const EN_AZ = 2;
const EN_COK = 50;

const OLCULER: Array<{ deger: PlanOlcusu; etiket: string; aciklama: string }> = [
  { deger: 'res_hp', etiket: 'RES HP (önerilen)', aciklama: 'Her bölgede eşit sayıda satılabilir kapı' },
  { deger: 'firsat', etiket: 'Boş kapı', aciklama: 'Her bölgede eşit sayıda hâlâ satılmamış kapı' },
  { deger: 'toplam_hp', etiket: 'Toplam HP', aciklama: 'SOHO dahil bütün kapılar' },
  { deger: 'bina', etiket: 'Bina sayısı', aciklama: 'Her bölgede eşit sayıda bina' },
];

const KAYNAK_ADI: Record<string, string> = {
  baslangic: 'Başlangıç (ilk kurulum)',
  hazir: 'Hazır plan',
  onbellek: 'Hazır plan',
  hesap: 'Güncel veriyle hesaplandı',
};

function hataMetni(h: unknown, yedek = 'İşlem yapılamadı.') {
  return h instanceof SahaHatasi ? h.message : yedek;
}

/** 0,0006 → "+%0,06" · -0,0001 → "−%0,01" (işaret yüzde işaretinin önünde) */
function sapmaMetni(s: number, isaretli = true) {
  const y = Math.abs(s * 100).toLocaleString('tr-TR', { maximumFractionDigits: 2, minimumFractionDigits: 1 });
  const isaret = !isaretli || !s ? '' : s > 0 ? '+' : '−';
  return `${isaret}%${y}`;
}

function zamanMetni(z: string | null | undefined) {
  if (!z) return '—';
  const m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/.exec(z);
  return m ? `${m[3]}.${m[2]}.${m[1]} ${m[4]}:${m[5]}` : z;
}

export function BolgePlanlayici() {
  const { noktalar, haritayiIste, haritayiTazele, haritaHatasi, ekipTazele } = useYonetim();
  const { goster } = useBildirim();
  const [surum, setSurum] = useState(0);
  const durum = useVeri(bolgelemeDurumu, [surum]);
  const d = durum.veri;

  const [n, setN] = useState<number | null>(null);
  const [olcu, setOlcu] = useState<PlanOlcusu>('res_hp');
  const [onizleme, setOnizleme] = useState<PlanOnizlemesi | null>(null);
  const [is, setIs] = useState<HesapIsi | null>(null);
  const [isteniyor, setIsteniyor] = useState(false);
  const [hata, setHata] = useState<string | null>(null);
  const [odak, setOdak] = useState<number | null>(null);
  const [onayAcik, setOnayAcik] = useState(false);
  const [geriAlAcik, setGeriAlAcik] = useState(false);
  const [sonuc, setSonuc] = useState<PlanUygulamaYaniti | null>(null);
  const [excelSuruyor, setExcelSuruyor] = useState(false);
  const yenidenIstendi = useRef(false);

  useEffect(() => {
    haritayiIste();
  }, [haritayiIste]);

  /* İlk açılışta seçici bugünkü sayıda durur. */
  useEffect(() => {
    if (d && n == null) {
      setN(d.n);
      setOlcu(d.olcu ?? 'res_hp');
    }
  }, [d, n]);

  /* Sunucuda süren bir hesap varsa (başka sekmeden başlatılmış) ilerlemesi gösterilir. */
  useEffect(() => {
    if (d?.calisan_is && !is) setIs(d.calisan_is);
  }, [d?.calisan_is, is]);

  const onizle = useCallback(
    async (hedefN: number, hedefOlcu: PlanOlcusu, hesapla = false) => {
      setIsteniyor(true);
      setHata(null);
      setOdak(null);
      try {
        const y = await bolgelemeOnizle(hedefN, hedefOlcu, hesapla);
        if (y.hazir) {
          setOnizleme(y);
          setIs(null);
        } else {
          setOnizleme(null);
          setIs(y.is);
        }
      } catch (h) {
        setHata(hataMetni(h, 'Önizleme alınamadı.'));
      } finally {
        setIsteniyor(false);
      }
    },
    [],
  );

  /* Arka plan hesabını izle: bitince önizlemeyi kendisi açar. */
  useEffect(() => {
    if (!is || is.durum === 'bitti' || is.durum === 'hata') return undefined;
    let iptal = false;
    const sayac = window.setInterval(async () => {
      try {
        const yeni = await hesapIsi(is.is_id);
        if (iptal) return;
        setIs(yeni);
        if (yeni.durum === 'bitti') {
          window.clearInterval(sayac);
          void onizle(yeni.n, (yeni.olcu as PlanOlcusu) ?? 'res_hp');
        } else if (yeni.durum === 'hata') {
          window.clearInterval(sayac);
          setHata(yeni.mesaj || 'Plan hesaplanamadı.');
        }
      } catch (h) {
        if (iptal) return;
        window.clearInterval(sayac);
        setIs(null);
        setHata(
          h instanceof SahaHatasi && h.durum === 404
            ? 'Sunucu yeniden başladığı için hesap yarıda kaldı. "Önizle"ye tekrar basın.'
            : hataMetni(h, 'Hesabın durumu alınamadı.'),
        );
      }
    }, 1500);
    return () => {
      iptal = true;
      window.clearInterval(sayac);
    };
  }, [is, onizle]);

  /* Önizleme dizisi haritadaki noktalarla aynı sırada olmalı. Değilse (tur raporu
     sonrası haritanın eski kopyası) harita bir kez tazelenir. */
  const diziUyumlu = Boolean(onizleme && noktalar && onizleme.bina_bolge.length === noktalar.length);
  useEffect(() => {
    if (onizleme && noktalar && !diziUyumlu && !yenidenIstendi.current) {
      yenidenIstendi.current = true;
      haritayiTazele();
    }
  }, [onizleme, noktalar, diziUyumlu, haritayiTazele]);

  const vazgec = () => {
    setOnizleme(null);
    setIs(null);
    setOdak(null);
    setHata(null);
  };

  const tazeleHepsi = useCallback(
    (yeniN?: number) => {
      setSurum((s) => s + 1);
      haritayiTazele();
      ekipTazele();
      bolgeSayisiniTazele(yeniN);
    },
    [haritayiTazele, ekipTazele],
  );

  const excelIndir = async () => {
    if (!d) return;
    setExcelSuruyor(true);
    try {
      const ad = await planExceliIndir(d.n, d.plan?.id ?? null);
      goster(`${ad} indirildi.`, 'basari');
    } catch (h) {
      goster(hataMetni(h, 'Excel hazırlanamadı.'), 'uyari');
    } finally {
      setExcelSuruyor(false);
    }
  };

  const seciliN = n ?? d?.n ?? 8;
  const hazirMi = d ? d.hazir_nler.includes(seciliN) && olcu === 'res_hp' : true;
  const onizlemeModu = Boolean(onizleme);
  const gosterilenBolgeler: PlanBolgesi[] = onizleme?.bolgeler ?? d?.bolgeler ?? [];

  const haritaBolgeleri = useMemo(
    () =>
      gosterilenBolgeler.map((b) => ({
        bolge: b.bolge,
        ad: b.ad,
        renk: b.renk,
        poligon: b.poligon,
        etiket: b.etiket ?? null,
      })),
    [gosterilenBolgeler],
  );

  const aktifPlanGecmisi = d?.gecmis.find((g) => Boolean(g.aktif));
  const oncekiPlan = aktifPlanGecmisi?.onceki_id
    ? d?.gecmis.find((g) => g.id === aktifPlanGecmisi.onceki_id)
    : null;

  return (
    <>
      <YonUst
        baslik="Bölge planlayıcı"
        altYazi="Ekip büyüyünce ya da küçülünce bölgeleri yeniden böl: önce önizle, sonra uygula. İstersen geri al."
      >
        {d?.geri_alinabilir ? (
          <button className="yd" onClick={() => setGeriAlAcik(true)} disabled={isteniyor}>
            <GeriAl boyut={18} />
            Geri al
          </button>
        ) : null}
        <button className="yd" onClick={excelIndir} disabled={!d || excelSuruyor}>
          <Indir boyut={18} />
          {excelSuruyor ? 'Excel hazırlanıyor…' : 'Excel indir'}
        </button>
      </YonUst>

      <Icerik>
        {durum.hata ? <HataKutusu mesaj={durum.hata} yenile={durum.yenile} /> : null}
        {haritaHatasi ? <HataKutusu mesaj={haritaHatasi} yenile={haritayiTazele} /> : null}

        {!d ? (
          <Iskelet yukseklik={180} />
        ) : (
          <>
            <BugunSeridi d={d} />

            {d.bolgesiz_satiscilar.length ? (
              <div className="yon-uyari">
                <Uyari boyut={18} />
                <span>
                  {d.bolgesiz_satiscilar.length} satışçı bölgesiz:{' '}
                  <b>{d.bolgesiz_satiscilar.map((s) => s.ad).join(', ')}</b>. Hiçbir binaya gidemezler;
                  Ekip ekranından bölge verin.
                </span>
                <span className="sag">
                  <button className="yd" onClick={() => bolumeGit('ekip')}>
                    Ekip ekranına git
                  </button>
                </span>
              </div>
            ) : null}

            <Secici
              d={d}
              n={seciliN}
              setN={(yeni) => {
                setN(yeni);
                if (onizleme && onizleme.n !== yeni) setOnizleme(null);
              }}
              olcu={olcu}
              setOlcu={(o) => {
                setOlcu(o);
                if (onizleme && onizleme.olcu !== o) setOnizleme(null);
              }}
              hazirMi={hazirMi}
              onizlendi={Boolean(onizleme && onizleme.n === seciliN && onizleme.olcu === olcu)}
              calisiyor={isteniyor || Boolean(is && (is.durum === 'bekliyor' || is.durum === 'calisiyor'))}
              onizle={() => void onizle(seciliN, olcu)}
            />

            {hata ? <HataKutusu mesaj={hata} /> : null}

            {is && (is.durum === 'bekliyor' || is.durum === 'calisiyor') ? <Ilerleme is={is} /> : null}

            {onizleme ? (
              <FarkKarti
                o={onizleme}
                vazgec={vazgec}
                uygula={() => setOnayAcik(true)}
                yenidenHesapla={() => void onizle(onizleme.n, onizleme.olcu, true)}
                calisiyor={isteniyor}
              />
            ) : null}

            <Kart
              baslik={
                onizlemeModu
                  ? `Önizleme: ${onizleme!.n} bölge`
                  : `Bugünkü bölgeler (${d.n})`
              }
              altYazi={
                onizlemeModu
                  ? 'Renkler yeni bölgeler. Bir bölgeye tıklayın: harita oraya odaklanır, tabloda işaretlenir.'
                  : 'Her nokta bir bina, rengi bölgesi. Bir bölgeye tıklayın: harita oraya odaklanır.'
              }
              sikis
            >
              <div style={{ padding: '0 14px 14px' }}>
                {noktalar && onizlemeModu && !diziUyumlu ? (
                  <div className="yon-uyari" style={{ marginBottom: 10 }}>
                    Harita verisi planla aynı değil (binalar yeni güncellenmiş olabilir); harita tazeleniyor…
                  </div>
                ) : null}
                <BolgeHaritasi
                  noktalar={noktalar ?? []}
                  bolgeDizisi={onizlemeModu && diziUyumlu ? onizleme!.bina_bolge : null}
                  bolgeler={haritaBolgeleri}
                  yukseklik={540}
                  odakBolge={odak}
                  bolgeSecildi={setOdak}
                  sigdirmaAnahtari={onizleme ? `on-${onizleme.plan_ref}` : `bugun-${d.n}`}
                />
              </div>
            </Kart>

            {onizlemeModu ? (
              <BolgeTablosu bolgeler={onizleme!.bolgeler} odak={odak} setOdak={setOdak} onizleme />
            ) : (
              <BolgeKartlari bolgeler={d.bolgeler} odak={odak} setOdak={setOdak} />
            )}

            {d.gecmis.length ? <PlanGecmisTablosu gecmis={d.gecmis} /> : null}
          </>
        )}
      </Icerik>

      {onizleme ? (
        <UygulaCekmecesi
          acik={onayAcik}
          kapat={() => setOnayAcik(false)}
          o={onizleme}
          uygulandi={(y) => {
            setOnayAcik(false);
            setSonuc(y);
            setOnizleme(null);
            setOdak(null);
            tazeleHepsi(y.n);
            goster(`${y.n} bölgelik plan uygulandı.`, 'basari');
          }}
        />
      ) : null}

      <GeriAlCekmecesi
        acik={geriAlAcik}
        kapat={() => setGeriAlAcik(false)}
        d={d}
        oncekiPlan={oncekiPlan ?? null}
        geriAlindi={(mesaj, yeniN) => {
          setGeriAlAcik(false);
          setOnizleme(null);
          setN(yeniN);
          tazeleHepsi(yeniN);
          goster(mesaj, 'basari');
        }}
      />

      <SonucCekmecesi sonuc={sonuc} kapat={() => setSonuc(null)} />
    </>
  );
}

/* ------------------------------ Bugün şeridi ------------------------------ */

function BugunSeridi({ d }: { d: BolgelemeDurumu }) {
  const satisciSayisi = d.bolgeler.reduce((t, b) => t + b.satiscilar.filter((s) => s.aktif).length, 0);
  return (
    <div className="bp-bugun">
      <div className="bp-bugun-ana">
        <div className="bp-bugun-etiket">Bugün</div>
        <div className="bp-bugun-cumle">
          <b>{d.n} bölge</b> · {satisciSayisi} satışçı · {sayi(d.toplam.bina)} bina
        </div>
        <div className="bp-bugun-alt">
          {d.plan
            ? `${d.plan.n} bölgelik plan · ${KAYNAK_ADI[d.plan.kaynak] ?? d.plan.kaynak} · uygulama: ${zamanMetni(d.plan.zaman)}`
            : 'İlk kurulumdaki bölgeler (henüz planlayıcıyla değiştirilmedi)'}
        </div>
      </div>
      <div className="bp-bugun-sayi">
        <div className="deger">{sayi(d.toplam.res_hp)}</div>
        <div className="etiket">RES HP</div>
      </div>
      <div className="bp-bugun-sayi">
        <div className="deger">{sayi(d.toplam.kalan_firsat)}</div>
        <div className="etiket">Satılmamış boş kapı</div>
      </div>
      <div className="bp-bugun-sayi">
        <div className="deger">{yuzde(d.toplam.dokunulan_oran, 1)}</div>
        <div className="etiket">Binaların dokunulan kısmı</div>
      </div>
    </div>
  );
}

/* ------------------------------ N seçici ------------------------------ */

function Secici({
  d,
  n,
  setN,
  olcu,
  setOlcu,
  hazirMi,
  onizlendi,
  calisiyor,
  onizle,
}: {
  d: BolgelemeDurumu;
  /** Seçili sayı için önizleme şu an ekranda. */
  onizlendi: boolean;
  n: number;
  setN: (n: number) => void;
  olcu: PlanOlcusu;
  setOlcu: (o: PlanOlcusu) => void;
  hazirMi: boolean;
  calisiyor: boolean;
  onizle: () => void;
}) {
  const sinirla = (x: number) => Math.max(EN_AZ, Math.min(EN_COK, Math.round(x)));
  const konum = (x: number) => ((x - EN_AZ) / (EN_COK - EN_AZ)) * 100;
  const fark = n - d.n;

  return (
    <section className="yon-kart bp-secici" aria-label="Bölge sayısı">
      <div className="bp-secici-sol">
        <div className="bp-soru">Kaç satışçıyla çalışacaksınız?</div>
        <div className="bp-adim">
          <button
            type="button"
            className="bp-adim-dugme"
            onClick={() => setN(sinirla(n - 1))}
            disabled={n <= EN_AZ}
            aria-label="Bir azalt"
          >
            −
          </button>
          <label className="bp-adim-deger">
            <input
              type="number"
              min={EN_AZ}
              max={EN_COK}
              value={n}
              onChange={(o) => {
                const v = Number(o.target.value);
                if (Number.isFinite(v) && v > 0) setN(sinirla(v));
              }}
              aria-label="Bölge sayısı"
            />
            <span>bölge</span>
          </label>
          <button
            type="button"
            className="bp-adim-dugme"
            onClick={() => setN(sinirla(n + 1))}
            disabled={n >= EN_COK}
            aria-label="Bir artır"
          >
            +
          </button>
        </div>
        <div className={`bp-ipucu${hazirMi || onizlendi ? ' hazir' : ''}`}>
          {onizlendi
            ? 'Önizleme aşağıda. Başka bir sayı da deneyebilirsiniz.'
            : n === d.n && olcu === d.olcu
            ? 'Bugünkü sayı. Artırın ya da azaltın, sonra önizleyin.'
            : hazirMi
              ? `Hazır plan · anında açılır${fark ? ` · bugüne göre ${fark > 0 ? '+' : ''}${fark} satışçı` : ''}`
              : 'Bu sayı için hazır plan yok · güncel veriyle hesaplanır (10 sn – 2 dk)'}
        </div>
      </div>

      <div className="bp-secici-orta">
        <div className="bp-kaydirac">
          <input
            type="range"
            min={EN_AZ}
            max={EN_COK}
            step={1}
            value={n}
            onChange={(o) => setN(sinirla(Number(o.target.value)))}
            aria-label="Bölge sayısı kaydıracı"
            style={{ ['--dolu' as string]: `${konum(n)}%` }}
          />
          <span className="bp-bugun-isaret" style={{ left: `${konum(d.n)}%` }} aria-hidden="true">
            <span className="cubuk" />
            <span className="yazi">bugün {d.n}</span>
          </span>
          <div className="bp-olcek" aria-hidden="true">
            {[2, 10, 20, 30, 40, 50].map((x) => (
              <span key={x} style={{ left: `${konum(x)}%` }}>
                {x}
              </span>
            ))}
          </div>
        </div>
        <label className="bp-olcu">
          <span>Eşit bölünecek:</span>
          <select className="yon-alan" value={olcu} onChange={(o) => setOlcu(o.target.value as PlanOlcusu)}>
            {OLCULER.map((o) => (
              <option key={o.deger} value={o.deger}>
                {o.etiket}
              </option>
            ))}
          </select>
          <span className="bp-olcu-aciklama">{OLCULER.find((o) => o.deger === olcu)?.aciklama}</span>
        </label>
      </div>

      <div className="bp-secici-sag">
        <button className="yd birincil buyuk" onClick={onizle} disabled={calisiyor}>
          {calisiyor ? 'Hazırlanıyor…' : `${n} bölgeyi önizle`}
        </button>
        <div className="bp-guvence">Önizleme hiçbir şeyi değiştirmez.</div>
      </div>
    </section>
  );
}

/* ------------------------------ Hesap ilerlemesi ------------------------------ */

function Ilerleme({ is }: { is: HesapIsi }) {
  const [gecen, setGecen] = useState(0);
  useEffect(() => {
    const bas = is.baslangic ? new Date(is.baslangic.replace(' ', 'T')).getTime() : Date.now();
    const t = () => setGecen(Math.max(0, Math.round((Date.now() - bas) / 1000)));
    t();
    const s = window.setInterval(t, 1000);
    return () => window.clearInterval(s);
  }, [is.baslangic]);
  const kalan = Math.max(0, (is.tahmini_sn || 0) - gecen);
  const oran = Math.max(0.03, Math.min(1, is.ilerleme || 0));
  return (
    <div className="bp-ilerleme" role="status" aria-live="polite">
      <div className="bp-ilerleme-ust">
        <b>{is.n} bölgelik plan güncel veriyle hesaplanıyor</b>
        <span>
          {is.asama || 'Hazırlanıyor'} · {Math.round(oran * 100)}%
          {kalan > 0 ? ` · yaklaşık ${kalan} sn kaldı` : ''}
        </span>
      </div>
      <div className="bp-ilerleme-yol">
        <span style={{ width: `${oran * 100}%` }} />
      </div>
      <div className="bp-ilerleme-alt">
        Bu pencereden çıkabilirsiniz; hesap sunucuda sürer. Bitince önizleme kendiliğinden açılır.
      </div>
    </div>
  );
}

/* ------------------------------ Fark (sade dille) ------------------------------ */

function FarkKarti({
  o,
  vazgec,
  uygula,
  yenidenHesapla,
  calisiyor,
}: {
  o: PlanOnizlemesi;
  vazgec: () => void;
  uygula: () => void;
  yenidenHesapla: () => void;
  calisiyor: boolean;
}) {
  const f = o.fark;
  const yeni = f.yeni_satisci_acilacak_bolgeler;
  const ayni = f.el_degistiren_bina === 0 && f.numarasi_degisen_bina === 0;
  const sapma = Math.max(Math.abs(o.denge.sapma_min), Math.abs(o.denge.sapma_maks));
  // Aşağıdaki maddelerde zaten söylenen uyarılar tekrar yazılmaz.
  const ekUyarilar = o.uyarilar.filter(
    (u) => !/yer tutucu satışçı hesabı/.test(u) && !/bölgesi kalmıyor/.test(u),
  );

  return (
    <section className="yon-kart bp-fark" aria-label="Plan farkı">
      <div className="bp-fark-ust">
        <div>
          <div className="bp-fark-baslik">
            {o.mevcut_n} bölgeden {o.n} bölgeye geçerseniz
          </div>
          <div className="bp-fark-cumle">
            {ayni ? (
              'Bu plan bugünkü bölgelerle aynı; uygulamak hiçbir şeyi değiştirmez.'
            ) : (
              <>
                <em>{sayi(f.el_degistiren_bina)} bina</em> ({yuzde(f.el_degistiren_oran)}) başka satışçıya
                geçer, geçmiş ziyaretler korunur.
              </>
            )}
          </div>
        </div>
        <div className="bp-fark-dugmeler">
          <button className="yd" onClick={vazgec}>
            Vazgeç
          </button>
          <button className="yd birincil buyuk" onClick={uygula} disabled={calisiyor || ayni}>
            <Onay boyut={18} />
            Uygula
          </button>
        </div>
      </div>

      <ul className="bp-maddeler">
        <li className="iyi">
          <Onay boyut={16} />
          <span>
            <b>Hiçbir kayıt silinmez.</b> El değiştiren binalardaki {sayi(f.el_degistiren_ziyaret)} ziyaret,
            bugünkü listeler ve satışlar olduğu gibi kalır.
          </span>
        </li>
        {f.satisci_hareketleri.length ? (
          <li>
            <Uyari boyut={16} />
            <span>
              Numarası değişen satışçı:{' '}
              {f.satisci_hareketleri.map((s) => `${s.ad} (${s.eski_bolge} → ${s.yeni_bolge})`).join(', ')}.
            </span>
          </li>
        ) : (
          <li className="iyi">
            <Onay boyut={16} />
            <span>Bugünkü satışçıların hepsi kendi bölge numarasında kalır.</span>
          </li>
        )}
        {yeni.length ? (
          <li>
            <span className="bp-madde-arti" aria-hidden="true">
              +
            </span>
            <span>
              <b>{yeni.length} yeni bölge</b> ({yeni.join(', ')}) için satışçı hesabı ve 6 haneli davet kodu açılır.
              Sonra Ekip ekranından ad ve telefonu düzeltin.
            </span>
          </li>
        ) : null}
        {f.bolgesiz_kalacak_satiscilar.length ? (
          <li className="dikkat">
            <Uyari boyut={16} />
            <span>
              <b>{f.bolgesiz_kalacak_satiscilar.length} satışçının bölgesi kalmaz</b> (
              {f.bolgesiz_kalacak_satiscilar.map((s) => s.ad).join(', ')}): "bölgesiz" olurlar, hesapları açık
              kalır. Uygularken pasife almayı seçebilirsiniz.
            </span>
          </li>
        ) : null}
        <li className="iyi">
          <Onay boyut={16} />
          <span>
            Denge: her bölge ortalamadan en çok <b>{sapmaMetni(sapma, false)}</b> sapıyor (
            {OLCULER.find((x) => x.deger === o.olcu)?.etiket.replace(' (önerilen)', '') ?? o.olcu}).
          </span>
        </li>
      </ul>

      {ekUyarilar.length ? (
        <div className="bp-dikkat">
          {ekUyarilar.map((u) => (
            <div key={u}>
              <Uyari boyut={16} /> {u}
            </div>
          ))}
        </div>
      ) : null}

      <div className="bp-kaynak">
        <span>
          {o.kaynak === 'hesap'
            ? 'Plan bugünkü veriyle sunucuda hesaplandı.'
            : 'Plan sunumdaki hazır bölünmeden geldi (anında açıldı).'}
        </span>
        <button className="yd duz" onClick={yenidenHesapla} disabled={calisiyor}>
          <Yenile boyut={16} />
          Güncel veriyle yeniden hesapla
        </button>
      </div>
    </section>
  );
}

/* ------------------------------ Bugünkü bölgeler: kartlar ------------------------------ */

function BolgeKartlari({
  bolgeler,
  odak,
  setOdak,
}: {
  bolgeler: PlanBolgesi[];
  odak: number | null;
  setOdak: (b: number | null) => void;
}) {
  return (
    <div className="bp-kartlar">
      {bolgeler.map((b) => {
        const kisiler = b.satiscilar.filter((s) => s.aktif);
        return (
          <button
            key={b.bolge}
            type="button"
            className={`bp-kart${odak === b.bolge ? ' secili' : ''}`}
            onClick={() => setOdak(odak === b.bolge ? null : b.bolge)}
            aria-pressed={odak === b.bolge}
          >
            <span className="bp-kart-renk" style={{ background: b.renk }} />
            <span className="bp-kart-bas">
              <span className="bp-no" style={{ background: b.renk, color: yaziRengi(b.renk) }}>
                {b.bolge}
              </span>
              <span className="bp-kart-ad" title={b.ad}>
                {b.ad}
              </span>
            </span>
            <span className={`bp-kart-kisi${kisiler.length ? '' : ' bp-kisisiz'}`}>
              {kisiler.length ? kisiler.map((s) => s.ad).join(', ') : 'Satışçı yok'}
              {kisiler.length && kisiler.every((s) => !s.pin_var) ? (
                <span className="bp-rozet amber" title="Davet koduyla PIN belirlemedi">
                  henüz giriş yapmadı
                </span>
              ) : null}
            </span>
            <span className="bp-kart-sayilar">
              <span>
                <b>{sayi(b.bina)}</b> bina
              </span>
              <span>
                <b>{sayi(b.res_hp)}</b> RES HP
              </span>
              <span>
                <b>{sayi(b.kalan_firsat)}</b> boş kapı
              </span>
            </span>
            <span className="bp-kart-oran">
              <OranCubugu oran={b.dokunulan_oran} />
              <span className="bp-kart-oran-yazi">
                {sayi(b.dokunulan)} / {sayi(b.bina)} bina dokunuldu
              </span>
            </span>
          </button>
        );
      })}
    </div>
  );
}

/* ------------------------------ Önizleme: KPI tablosu ------------------------------ */

function BolgeTablosu({
  bolgeler,
  odak,
  setOdak,
  onizleme = false,
}: {
  bolgeler: PlanBolgesi[];
  odak: number | null;
  setOdak: (b: number | null) => void;
  onizleme?: boolean;
}) {
  const toplam = bolgeler.reduce(
    (t, b) => ({
      bina: t.bina + b.bina,
      res_hp: t.res_hp + b.res_hp,
      kalan_firsat: t.kalan_firsat + b.kalan_firsat,
      dokunulan: t.dokunulan + b.dokunulan,
    }),
    { bina: 0, res_hp: 0, kalan_firsat: 0, dokunulan: 0 },
  );
  return (
    <Kart
      baslik="Bölge başına sayılar"
      altYazi="Satıra tıklayın: haritada o bölge öne çıkar. Denge sütunu ortalamadan sapmayı gösterir."
      sikis
    >
      <div className="yon-tablo-sarmal">
        {/* Telefonda satır kartı (§7.4): hücreler etiketini (data-etiket) önüne yazar. */}
        <table className="yon-tablo bp-tablo satirlasir">
          <thead>
            <tr>
              <th>Bölge</th>
              <th>Satışçı</th>
              <th className="sayi">Bina</th>
              <th className="sayi">RES HP</th>
              <th className="sayi">Boş kapı</th>
              <th style={{ minWidth: 120 }}>Dokunulan</th>
              <th className="sayi">Denge</th>
              {onizleme ? <th className="bp-genis">Binalar nereden geliyor</th> : null}
            </tr>
          </thead>
          <tbody>
            {bolgeler.map((b) => {
              const kisiler = b.satiscilar.filter((s) => s.aktif);
              return (
                <tr
                  key={b.bolge}
                  className={`tiklanir${odak === b.bolge ? ' secili' : ''}`}
                  onClick={() => setOdak(odak === b.bolge ? null : b.bolge)}
                >
                  <td className="ad-hucre">
                    <span className="bp-hucre-bolge">
                      <span className="bp-no" style={{ background: b.renk, color: yaziRengi(b.renk) }}>
                        {b.bolge}
                      </span>
                      <span className="bp-hucre-ad" title={b.ad}>
                        {b.ad}
                      </span>
                    </span>
                  </td>
                  <td data-etiket="Satışçı">
                    {b.yeni_satisci_acilacak ? (
                      <span className="bp-rozet mavi" title="Uygulanınca yer tutucu hesap ve davet kodu açılır">
                        Yeni satışçı
                      </span>
                    ) : kisiler.length ? (
                      kisiler.map((s) => s.ad).join(', ')
                    ) : (
                      <span className="bp-rozet amber">Satışçı yok</span>
                    )}
                  </td>
                  <td className="sayi" data-etiket="Bina">{sayi(b.bina)}</td>
                  <td className="sayi" data-etiket="RES HP">{sayi(b.res_hp)}</td>
                  <td className="sayi" data-etiket="Boş kapı">{sayi(b.kalan_firsat)}</td>
                  <td className="tam">
                    <OranCubugu oran={b.dokunulan_oran} />
                  </td>
                  <td className={`sayi bp-sapma${Math.abs(b.sapma) > 0.05 ? ' kotu' : ''}`} data-etiket="Denge">
                    {sapmaMetni(b.sapma)}
                  </td>
                  {onizleme ? (
                    <td className="bp-nereden tam">
                      {(b.nereden ?? [])
                        .filter((x) => x.bina > 0)
                        .slice(0, 2)
                        .map((x) =>
                          x.bolge ? `${x.bolge}. bölgeden ${sayi(x.bina)}` : `bölgesizden ${sayi(x.bina)}`,
                        )
                        .join(' · ')}
                    </td>
                  ) : null}
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr>
              <td className="ad-hucre">Toplam</td>
              <td />
              <td className="sayi" data-etiket="Bina">{sayi(toplam.bina)}</td>
              <td className="sayi" data-etiket="RES HP">{sayi(toplam.res_hp)}</td>
              <td className="sayi" data-etiket="Boş kapı">{sayi(toplam.kalan_firsat)}</td>
              <td data-etiket="Dokunulan">{toplam.bina ? yuzde(toplam.dokunulan / toplam.bina, 1) : '—'}</td>
              <td />
              {onizleme ? <td /> : null}
            </tr>
          </tfoot>
        </table>
      </div>
    </Kart>
  );
}

/* ------------------------------ Plan geçmişi ------------------------------ */

function PlanGecmisTablosu({ gecmis }: { gecmis: PlanGecmisi[] }) {
  return (
    <Kart baslik="Plan geçmişi" altYazi="Her uygulama ve geri alma burada durur; hiçbir plan silinmez." sikis>
      <div className="yon-tablo-sarmal">
        <table className="yon-tablo satirlasir">
          <thead>
            <tr>
              <th>Zaman</th>
              <th className="sayi">Bölge</th>
              <th>Kaynak</th>
              <th>Kim</th>
              <th>Durum</th>
              <th>Not</th>
            </tr>
          </thead>
          <tbody>
            {gecmis.map((g) => (
              <tr key={g.id}>
                <td className="ad-hucre">{zamanMetni(g.zaman)}</td>
                <td className="sayi" data-etiket="Bölge">{g.n}</td>
                <td data-etiket="Kaynak">{KAYNAK_ADI[g.kaynak] ?? g.kaynak}</td>
                <td data-etiket="Kim">{g.olusturan ?? '—'}</td>
                <td>
                  {g.aktif ? (
                    <span className="bp-rozet yesil">Şu an geçerli</span>
                  ) : g.geri_alindi ? (
                    <span className="bp-rozet gri">Geri alındı</span>
                  ) : (
                    <span className="bp-rozet gri">Önceki</span>
                  )}
                </td>
                <td className="tam" data-etiket="Not">{g.notu || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Kart>
  );
}

/* ------------------------------ Uygula onayı ------------------------------ */

function UygulaCekmecesi({
  acik,
  kapat,
  o,
  uygulandi,
}: {
  acik: boolean;
  kapat: () => void;
  o: PlanOnizlemesi;
  uygulandi: (y: PlanUygulamaYaniti) => void;
}) {
  const [pasiflestir, setPasiflestir] = useState(false);
  const [notu, setNotu] = useState('');
  const [calisiyor, setCalisiyor] = useState(false);
  const [hata, setHata] = useState<string | null>(null);
  const f = o.fark;

  useEffect(() => {
    if (acik) {
      setHata(null);
      setPasiflestir(false);
    }
  }, [acik]);

  const uygula = async () => {
    setCalisiyor(true);
    setHata(null);
    try {
      const y = await planUygula({ n: o.n, plan_ref: o.plan_ref, pasiflestir, notu: notu.trim() || undefined });
      uygulandi(y);
    } catch (h) {
      setHata(
        h instanceof SahaHatasi && h.kod === 'plan_degisti'
          ? 'Önizlemeden sonra binalar değişti. Kapatıp "Önizle"ye yeniden basın.'
          : hataMetni(h, 'Plan uygulanamadı. Hiçbir şey değişmedi.'),
      );
    } finally {
      setCalisiyor(false);
    }
  };

  return (
    <Cekmece
      acik={acik}
      kapat={kapat}
      kilitli={calisiyor}
      baslik={`${o.n} bölgelik planı uygula?`}
      altBaslik="Tek seferde yapılır: ya hepsi olur ya hiçbiri. İstediğiniz an geri alabilirsiniz."
    >
      <ul className="bp-onay-liste">
        <li>
          <b>{sayi(f.el_degistiren_bina)} bina</b> yeni bölgesine geçer.
        </li>
        <li>
          <b>Ziyaret geçmişi, bugünkü listeler ve satışlar</b> olduğu gibi kalır.
        </li>
        {f.yeni_satisci_acilacak_bolgeler.length ? (
          <li>
            <b>{f.yeni_satisci_acilacak_bolgeler.length} yeni satışçı hesabı</b> açılır (bölge{' '}
            {f.yeni_satisci_acilacak_bolgeler.join(', ')}); davet kodları bir sonraki ekranda.
          </li>
        ) : null}
        {f.bugun_listede_el_degistiren ? (
          <li>
            Bugünkü listelerde <b>{sayi(f.bugun_listede_el_degistiren)} bina</b> el değiştiriyor: bugün eski
            satışçısı gezebilir. En temizi planı akşam uygulamak.
          </li>
        ) : null}
      </ul>

      {f.bolgesiz_kalacak_satiscilar.length ? (
        <label className="bp-onay-kutu">
          <input type="checkbox" checked={pasiflestir} onChange={(e) => setPasiflestir(e.target.checked)} />
          <span>
            Bölgesi kalmayan {f.bolgesiz_kalacak_satiscilar.length} satışçıyı pasife al (
            {f.bolgesiz_kalacak_satiscilar.map((s) => s.ad).join(', ')}). Seçmezseniz "bölgesiz" kalırlar;
            hesap hiçbir durumda silinmez.
          </span>
        </label>
      ) : null}

      <label style={{ display: 'block', marginTop: 12 }}>
        <span className="yon-etiket">Not (isteğe bağlı)</span>
        <input
          className="yon-alan"
          value={notu}
          maxLength={200}
          placeholder="Örn. Ekim'de 6 yeni satışçı başlıyor"
          onChange={(e) => setNotu(e.target.value)}
        />
      </label>

      {hata ? (
        <div className="yon-uyari kirmizi" style={{ marginTop: 12 }}>
          <Uyari boyut={18} />
          {hata}
        </div>
      ) : null}

      <div className="bp-onay-dugmeler">
        <button className="yd" onClick={kapat} disabled={calisiyor}>
          Vazgeç
        </button>
        <button className="yd birincil buyuk" onClick={uygula} disabled={calisiyor}>
          {calisiyor ? 'Uygulanıyor…' : `Evet, ${o.n} bölgeyi uygula`}
        </button>
      </div>
    </Cekmece>
  );
}

/* ------------------------------ Geri al ------------------------------ */

function GeriAlCekmecesi({
  acik,
  kapat,
  d,
  oncekiPlan,
  geriAlindi,
}: {
  acik: boolean;
  kapat: () => void;
  d: BolgelemeDurumu | null;
  oncekiPlan: PlanGecmisi | null;
  geriAlindi: (mesaj: string, n: number) => void;
}) {
  const [calisiyor, setCalisiyor] = useState(false);
  const [hata, setHata] = useState<string | null>(null);
  useEffect(() => {
    if (acik) setHata(null);
  }, [acik]);

  const geriAl = async () => {
    setCalisiyor(true);
    setHata(null);
    try {
      const y = await planGeriAl();
      const kapanan = y.kapatilan_yer_tutucular.length
        ? ` ${y.kapatilan_yer_tutucular.length} yer tutucu hesap kapatıldı (silinmedi).`
        : '';
      geriAlindi(y.mesaj + kapanan, y.n);
    } catch (h) {
      setHata(hataMetni(h, 'Geri alınamadı. Hiçbir şey değişmedi.'));
    } finally {
      setCalisiyor(false);
    }
  };

  const hedefN = oncekiPlan?.n;
  return (
    <Cekmece
      acik={acik}
      kapat={kapat}
      kilitli={calisiyor}
      baslik={hedefN ? `${hedefN} bölgelik önceki plana dönülsün mü?` : 'Önceki plana dönülsün mü?'}
      altBaslik={d ? `Şu an ${d.n} bölge var.` : undefined}
    >
      <ul className="bp-onay-liste">
        <li>Binalar ve satışçılar planı uygulamadan önceki bölgelerine döner.</li>
        <li>Bu plan için açılan yer tutucu hesaplar kapanır (silinmez; gerekirse yeniden açılır).</li>
        <li>
          <b>Ziyaret, liste ve satış kayıtlarına dokunulmaz.</b>
        </li>
      </ul>
      {hata ? (
        <div className="yon-uyari kirmizi" style={{ marginTop: 12 }}>
          <Uyari boyut={18} />
          {hata}
        </div>
      ) : null}
      <div className="bp-onay-dugmeler">
        <button className="yd" onClick={kapat} disabled={calisiyor}>
          Vazgeç
        </button>
        <button className="yd birincil buyuk" onClick={geriAl} disabled={calisiyor}>
          <GeriAl boyut={18} />
          {calisiyor ? 'Geri alınıyor…' : 'Evet, geri al'}
        </button>
      </div>
    </Cekmece>
  );
}

/* ------------------------------ Uygulandı: davet kodları ------------------------------ */

function SonucCekmecesi({ sonuc, kapat }: { sonuc: PlanUygulamaYaniti | null; kapat: () => void }) {
  const { goster } = useBildirim();
  if (!sonuc) return null;
  const kodlar = sonuc.yeni_satiscilar;
  return (
    <Cekmece acik kapat={kapat} baslik={`${sonuc.n} bölgelik plan uygulandı`} altBaslik={sonuc.mesaj}>
      {kodlar.length ? (
        <>
          <div className="bp-kod-baslik">
            Yeni bölgeler için açılan hesaplar — kodu satışçıya verin, ilk girişte kendi PIN'ini belirlesin:
          </div>
          <div className="bp-kodlar">
            {kodlar.map((k) => (
              <div key={k.id} className="bp-kod">
                <span className="bp-kod-bolge">{k.bolge}. bölge</span>
                <span className="bp-kod-ad">{k.ad}</span>
                <button
                  type="button"
                  className="bp-kod-deger"
                  title="Kopyala"
                  onClick={async () =>
                    goster((await kopyala(k.davet_kodu)) ? 'Davet kodu kopyalandı.' : 'Kopyalanamadı.', 'bilgi')
                  }
                >
                  {k.davet_kodu}
                </button>
              </div>
            ))}
          </div>
          <div className="yon-uyari" style={{ marginTop: 12 }}>
            <Uyari boyut={18} />
            Bu hesapların telefonu geçici (50000000NN). Ekip ekranından gerçek ad ve telefonu yazın.
          </div>
        </>
      ) : null}
      <div className="bp-onay-dugmeler">
        <button className="yd" onClick={kapat}>
          Kapat
        </button>
        {kodlar.length ? (
          <button
            className="yd birincil buyuk"
            onClick={() => {
              kapat();
              bolumeGit('ekip');
            }}
          >
            Ekip ekranına git
          </button>
        ) : null}
      </div>
    </Cekmece>
  );
}
