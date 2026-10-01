/**
 * Takip — yönetici paneli (OPERASYON_V2_SPEC §6.11; F11, F15, F17; EK-3, EK-6).
 *
 * Dört kutu, dört soru — tek bakışta:
 *   Sözümüzü tutuyor muyuz?   biten işlerin 24 saat (işin kendi hedefi) içinde biten payı
 *   Hızlı mıyız?              atama medyanı, ≤ 15 dk payı (yalnız sistem çalışırken doğan işler)
 *   BTK'yı kaçırıyor muyuz?   48 saati aşan açık BTK; TV 6 s / Bağlantı 12 s hedefte payı
 *   Yetiyor muyuz?            bugünkü talep / kapasite (§3.6), sahadaki teknik [− +]
 * Altında: hız hattı (BOSS → sistem → atama → gördü → BOSS'a işlendi → yol → saha),
 * birikim, BTK (askıda duran saat dahil), öbekler, teknik, hijyen; yöneticide satış
 * bölümü ve sistem kayıtları. Operasyon satış ve sistem bölümlerini görmez.
 *
 * Renk yalnız hedef aşılınca girer; kutular varsayılan nötr. Her sayı tıklanınca
 * İşler'i o süzgeçle açar: `#/yonetici/isler/suz/<kod>` (kodlar: `SUZ` sabiti) ve
 * öbek için `#/yonetici/isler/obek/<id>` (§6.0). Veri yoksa "kayıt yok" yazılır,
 * sıfır çubuk çizilmez. Telefonda kutular alt alta satır olur, değer sağa yaslı;
 * tablolar satır kartına döner (§7.4).
 */

import { useCallback, useMemo, useState } from 'react';
import { useOturum } from '../../depo/oturum';
import { git } from '../../yol/rota';
import { YonUst, Icerik } from '../ortak/Kabuk';
import { useVeri } from '../ortak/parcalar';
import { Segment } from '../../ortak/Segment';
import { Hikaye, type HikayeTonu } from '../../ortak/Hikaye';
import { HataKutusu, Iskelet } from '../../ortak/Bos';
import { Panel } from '../../ortak/Panel';
import { useBildirim } from '../../ortak/Bildirim';
import { sayi, yuzde } from '../../ortak/bicim';
import { sureMetni } from '../../ortak/sure';
import { yerelOku, yerelYaz } from '../../ortak/yerel';
import { SahaHatasi } from '../../api/istemci';
import type { HizAdimi, TakipYanit } from '../../is/tipler';
import { kapasiteYaz, takipErisim, takipGetir, takipYonetim, type YonetimKaydi } from './api';
import { SatisBolumu } from './SatisBolumu';
import { Egri, iyelik, saatMetni, tarihSaatMetni, uzunTarih } from './parcalar';
import './takip.css';

/** İşler süzgeç kodları (WP-C `#/yonetici/isler/suz/<kod>` ile okur). */
export const SUZ = {
  asan24: 'asan24',
  atanmamis: 'atanmamis',
  btk48: 'btk48',
  kontrol: 'kontrol',
  bossIslenecek: 'boss_islenecek',
  bossAcik: 'boss_acik',
  askidaUyanmasiz: 'askida_uyanmasiz',
  askidaBtkDurdu: 'askida_btk_durdu',
  btkAlarm: 'btk_alarm',
  genelAriza: 'genel_ariza',
  oncelikli: 'oncelikli',
  teknik: (id: number) => `teknik-${id}`,
} as const;

const GUN_ANAHTARI = 'saha.takip.gun';
const GUNLER = [
  { deger: '1', etiket: 'Bugün' },
  { deger: '7', etiket: '7 gün' },
  { deger: '30', etiket: '30 gün' },
] as const;
type GunSecimi = (typeof GUNLER)[number]['deger'];

/** Hız hattı adımlarının ekrandaki adı (§5.3.6). Sunucunun bilmediğimiz adımı adıyla yazılır. */
const ADIM_ADI: Record<string, string> = {
  boss_sistem: 'BOSS → sistem',
  atama: 'Atama',
  teknik_gordu: 'Teknisyen gördü',
  boss_islendi: "BOSS'a işlendi",
  yola_cikis: 'Yola çıkış',
  yol: 'Yol',
  saha: 'Sahada',
  kapanis_dogrulama: 'Kapanış doğrulama',
  uctan_uca: 'Uçtan uca',
};
const ADIM_ACIKLAMA: Record<string, string> = {
  boss_sistem: 'BOSS’ta açılıştan raporla sisteme gelişe',
  atama: 'Sisteme gelişten ilk atamaya (15 dk ölçüsü)',
  teknik_gordu: 'Atamadan teknisyenin telefonda görmesine',
  boss_islendi: 'Atamadan BOSS’a işlenmesine',
  yola_cikis: 'Atamadan yola çıkışa',
  yol: 'Yola çıkıştan sahaya varışa',
  saha: 'Sahada işe başlamadan çözüme',
  kapanis_dogrulama: 'Çözümden BOSS’ta kapanışın görülmesine',
  uctan_uca: 'BOSS’ta açılıştan çözüme',
};

function gunOku(): GunSecimi {
  const ham = yerelOku(GUN_ANAHTARI);
  return ham === '1' || ham === '30' ? ham : '7';
}

export function Takip() {
  const { izinli } = useOturum();
  const tam = izinli('takip.tam');
  const kapasiteYazabilir = izinli('kapasite.yaz');
  const islereGider = izinli('is.ata', 'is.liste');
  const [gunSecim, setGunSecim] = useState<GunSecimi>(gunOku);
  const gun = Number(gunSecim);
  const v = useVeri(() => takipGetir(gun), [gun], 60_000);
  const t = v.veri;

  const suz = useCallback(
    (kod: string) => {
      if (islereGider) git(`/yonetici/isler/suz/${encodeURIComponent(kod)}`);
    },
    [islereGider],
  );

  const gunDegisti = (g: GunSecimi) => {
    yerelYaz(GUN_ANAHTARI, g);
    setGunSecim(g);
  };

  return (
    <>
      <YonUst baslik="Takip" />
      <Icerik>
        <div className="tp">
          <div className="tp-ust">
            <div className="tp-ust-sol">
              <span className="tp-tarih">{uzunTarih(t?.sunucu_zamani)}</span>
              {t ? <RaporTazeligi t={t} /> : null}
            </div>
            <Segment<GunSecimi>
              etiket="Dönem"
              kucuk
              deger={gunSecim}
              degisti={gunDegisti}
              secenekler={GUNLER.map((g) => ({ deger: g.deger, etiket: g.etiket }))}
            />
          </div>

          {v.hata && !t ? <HataKutusu mesaj={v.hata} tekrar={v.yenile} /> : null}
          {!t ? (
            v.hata ? null : <Iskelet satir={6} yukseklik={96} />
          ) : (
            <>
              <TakipHikayesi t={t} gun={gun} />
              <DortKutu t={t} gun={gun} suz={islereGider ? suz : null} kapasiteYazabilir={kapasiteYazabilir} yenile={v.yenile} />
              <HizHatti adimlar={t.hiz_hatti} gun={gun} />
              <div className="tp-ikili">
                <Birikim t={t} gun={gun} suz={islereGider ? suz : null} />
                <BtkBolumu t={t} suz={islereGider ? suz : null} />
              </div>
              <Hijyen t={t} suz={islereGider ? suz : null} />
              <ObekTablosu t={t} tikla={islereGider ? (id) => git(`/yonetici/isler/obek/${id}`) : null} />
              <TeknikTablosu t={t} tikla={islereGider ? (id) => suz(SUZ.teknik(id)) : null} />
              {tam ? <SatisBolumu gun={gun} /> : null}
              {tam ? <SistemBolumu t={t} /> : null}
              {v.sonGuncelleme ? (
                <p className="tp-dipnot">
                  Güncellendi {v.sonGuncelleme.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })} · her
                  dakika kendiliğinden yenilenir.
                </p>
              ) : null}
            </>
          )}
        </div>
      </Icerik>
    </>
  );
}

/* ------------------------------ Üst şerit ------------------------------ */

function RaporTazeligi({ t }: { t: TakipYanit }) {
  const yas = t.hijyen.rapor_yas_dk;
  if (!t.sistem.son_rapor) return <span className="tp-hap">Henüz rapor yok</span>;
  const renk = yas == null ? '' : yas >= 60 ? ' kirmizi' : yas >= 30 ? ' amber' : '';
  return (
    <span className={`tp-hap${renk}`} title="BOSS'tan gelen son Teknik Task Detay Raporu">
      Son rapor {saatMetni(t.sistem.son_rapor)}
      {yas != null ? ` · ${yas < 1 ? 'az önce' : `${sureMetni(yas)} önce`}` : ''}
    </span>
  );
}

/* ------------------------------ Hikâye (EK-6) ------------------------------ */

function TakipHikayesi({ t, gun }: { t: TakipYanit; gun: number }) {
  const atama = t.hiz_hatti.find((a) => a.adim === 'atama');
  const donem = gun === 1 ? 'Son 24 saatte' : `Son ${gun} günde`;
  const parca1 =
    t.uyum24.oran == null
      ? `${donem} biten iş kaydı yok`
      : `${donem} biten işlerin ${yuzde(t.uyum24.oran)}${iyelik(Math.round(t.uyum24.oran * 100))} sözünde bitti`;
  const parca2 = atama?.medyan_dk != null ? `; atama medyanı ${sureMetni(atama.medyan_dk)}.` : '.';
  const btk = t.manset.btk48 ? `48 saati aşan ${sayi(t.manset.btk48)} BTK işi var` : '48 saati aşan BTK işi yok';
  const ekip = t.kapasite.mesaj
    ? 'ekipte teknik görevli yok'
    : t.kapasite.mod === 'asiri_yuk'
      ? `ekip bugün yetmiyor${t.kapasite.esnek_oneri ? ` — ${t.kapasite.esnek_oneri} esnek teknisyen önerilir` : ''}`
      : 'ekip bugün yetiyor';
  const cumle = `${parca1}${parca2} ${btk}; ${ekip}.`;
  const ton: HikayeTonu =
    t.manset.btk48 > 0 || t.kapasite.mod === 'asiri_yuk'
      ? 'acil'
      : (atama?.medyan_dk ?? 0) > (atama?.hedef_dk ?? 15)
        ? 'dikkat'
        : t.uyum24.oran != null
          ? 'iyi'
          : 'sakin';
  return <Hikaye cumle={cumle} ton={ton} />;
}

/* ------------------------------ Dört kutu ------------------------------ */

function DortKutu({
  t,
  gun,
  suz,
  kapasiteYazabilir,
  yenile,
}: {
  t: TakipYanit;
  gun: number;
  suz: ((kod: string) => void) | null;
  kapasiteYazabilir: boolean;
  yenile: () => void;
}) {
  const atama = t.hiz_hatti.find((a) => a.adim === 'atama');
  const atamaGec = atama?.medyan_dk != null && atama.medyan_dk > atama.hedef_dk;
  const egim = t.uyum24.egim.filter((e) => e.oran != null).map((e) => e.oran as number);
  const donem = gun === 1 ? 'son 24 saatte' : `son ${gun} günde`;
  return (
    <section className="tp-kutular" aria-label="Dört soru">
      <Kutu
        soru="Sözümüzü tutuyor muyuz?"
        deger={t.uyum24.oran == null ? '—' : yuzde(t.uyum24.oran)}
        ek={
          t.uyum24.n ? (
            <>
              {donem} biten {sayi(t.uyum24.n)} iş
              {t.uyum24.yaklasik ? ' · yaklaşık' : ''}
            </>
          ) : (
            'Bu dönemde biten iş kaydı yok'
          )
        }
        alt={egim.length >= 2 ? <Egri degerler={egim} etiket="Günlük söz tutma payı" /> : null}
        baslik={
          t.uyum24.yaklasik
            ? 'Bir kısmı raporda görünmeyince kapandı; kapanış anı kesin değil.'
            : 'İşin kendi hedefinde (24 saat) çözülen ya da kapanan payı'
        }
        tikla={suz ? () => suz(SUZ.asan24) : undefined}
        tiklaEtiket="24 saati aşan açık işleri göster"
      />
      <Kutu
        soru="Hızlı mıyız?"
        deger={atama?.medyan_dk == null ? '—' : sureMetni(atama.medyan_dk)}
        renk={atamaGec ? 'kirmizi' : undefined}
        ek={
          atama?.n ? (
            <>
              atama medyanı · {yuzde(atama.hedefte_oran)} ≤ {atama.hedef_dk} dk
            </>
          ) : (
            'Atama kaydı yok'
          )
        }
        alt={
          <span className={t.manset.en_eski_atanmamis_dk != null && t.manset.en_eski_atanmamis_dk >= 15 ? 'tp-uyari-yazi' : undefined}>
            {t.manset.atanmamis
              ? `Şu an ${sayi(t.manset.atanmamis)} iş bekliyor${
                  t.manset.en_eski_atanmamis_dk != null ? ` · en eskisi ${sureMetni(t.manset.en_eski_atanmamis_dk)}` : ''
                }`
              : 'Atanmamış iş yok'}
          </span>
        }
        tikla={suz ? () => suz(SUZ.atanmamis) : undefined}
        tiklaEtiket="Atanmamış işleri göster"
      />
      <Kutu
        soru="BTK'yı kaçırıyor muyuz?"
        deger={sayi(t.manset.btk48)}
        renk={t.manset.btk48 > 0 ? 'kirmizi' : undefined}
        ek={t.manset.btk48 ? '48 saati aşan açık BTK' : '48 saati aşan BTK yok'}
        alt={
          <>
            {t.manset.en_yasli_btk_s != null ? `En yaşlı açık BTK ${sayi(t.manset.en_yasli_btk_s)} s` : 'Açık BTK yok'}
          </>
        }
        tikla={suz ? () => suz(SUZ.btk48) : undefined}
        tiklaEtiket="48 saati aşan BTK işlerini göster"
      />
      <KapasiteKutusu t={t} yazabilir={kapasiteYazabilir} yenile={yenile} />
    </section>
  );
}

function Kutu({
  soru,
  deger,
  ek,
  alt,
  renk,
  baslik,
  tikla,
  tiklaEtiket,
}: {
  soru: string;
  deger: React.ReactNode;
  ek?: React.ReactNode;
  alt?: React.ReactNode;
  renk?: 'kirmizi' | 'amber';
  baslik?: string;
  tikla?: () => void;
  tiklaEtiket?: string;
}) {
  const ic = (
    <>
      <span className="tp-soru">{soru}</span>
      <span className={`tp-deger${renk ? ' ' + renk : ''}`}>{deger}</span>
      {ek ? <span className="tp-ek">{ek}</span> : null}
      {alt ? <span className="tp-alt">{alt}</span> : null}
    </>
  );
  return tikla ? (
    <button type="button" className="tp-kutu tiklanir" onClick={tikla} title={baslik} aria-label={`${soru} ${tiklaEtiket ?? ''}`}>
      {ic}
    </button>
  ) : (
    <div className="tp-kutu" title={baslik}>
      {ic}
    </div>
  );
}

function KapasiteKutusu({ t, yazabilir, yenile }: { t: TakipYanit; yazabilir: boolean; yenile: () => void }) {
  const { goster } = useBildirim();
  const [yerel, setYerel] = useState<TakipYanit['kapasite'] | null>(null);
  const [yaziyor, setYaziyor] = useState(false);
  const k = yerel && yerel.talep === t.kapasite.talep ? yerel : t.kapasite;
  const oran = k.kapasite > 0 ? k.talep / k.kapasite : null;
  const asiri = k.mod === 'asiri_yuk';

  const yaz = async (aktif: number | null) => {
    if (yaziyor) return;
    setYaziyor(true);
    try {
      const bugun = t.sunucu_zamani.slice(0, 10);
      const y = await kapasiteYaz(bugun, aktif);
      setYerel({ ...t.kapasite, ...y });
      yenile();
    } catch (h) {
      goster(h instanceof SahaHatasi ? h.message : 'Kaydedilemedi.', 'uyari');
    } finally {
      setYaziyor(false);
    }
  };

  return (
    <div className="tp-kutu tp-kapasite">
      <span className="tp-soru">Yetiyor muyuz?</span>
      <span className={`tp-deger${asiri ? ' amber' : ''}`}>
        {sayi(k.talep)} <small>/ {sayi(k.kapasite)}</small>
      </span>
      <span className="tp-ek">
        {k.mesaj ?? (asiri ? `Aşırı yük${k.esnek_oneri ? ` · +${k.esnek_oneri} esnek önerilir` : ''}` : 'Bugünkü talep kapasitenin içinde')}
      </span>
      {oran != null ? (
        <span
          className={`tp-olcer${asiri ? ' asiri' : ''}`}
          role="meter"
          aria-valuemin={0}
          aria-valuemax={k.kapasite}
          aria-valuenow={Math.min(k.talep, k.kapasite)}
          aria-label={`Talep ${k.talep}, kapasite ${k.kapasite}`}
        >
          <span style={{ width: `${Math.min(100, Math.round(oran * 100))}%` }} />
        </span>
      ) : null}
      <span className="tp-alt tp-sahada">
        <span>
          Sahada teknik <strong>{sayi(k.aktif)}</strong>
          {k.elle ? ' · elle' : ''}
        </span>
        {yazabilir ? (
          <span className="tp-adimci">
            <button type="button" onClick={() => void yaz(Math.max(0, k.aktif - 1))} disabled={yaziyor || k.aktif <= 0} aria-label="Sahadaki teknik sayısını azalt">
              −
            </button>
            <button type="button" onClick={() => void yaz(k.aktif + 1)} disabled={yaziyor} aria-label="Sahadaki teknik sayısını artır">
              +
            </button>
          </span>
        ) : null}
      </span>
      {yazabilir && k.elle ? (
        <button type="button" className="o-bag tp-otomatik" onClick={() => void yaz(null)} disabled={yaziyor}>
          Atamalardan hesapla
        </button>
      ) : null}
    </div>
  );
}

/* ------------------------------ Hız hattı ------------------------------ */

function HizHatti({ adimlar, gun }: { adimlar: HizAdimi[]; gun: number }) {
  const sirali = useMemo(() => {
    const sira = Object.keys(ADIM_ADI);
    const yer = (adim: string) => {
      const i = sira.indexOf(adim);
      return i < 0 ? sira.length : i;
    };
    return [...adimlar].sort((a, b) => yer(a.adim) - yer(b.adim));
  }, [adimlar]);
  return (
    <section className="tp-bolum" aria-labelledby="tp-hiz">
      <div className="tp-bolum-bas">
        <h2 id="tp-hiz">Hız hattı</h2>
        <span className="tp-bolum-alt">{gun === 1 ? 'son 24 saat' : `son ${gun} gün`} · medyan · hedefte</span>
      </div>
      <ol className="tp-hat">
        {sirali.map((a) => {
          const gec = a.medyan_dk != null && a.medyan_dk > a.hedef_dk;
          return (
            <li key={a.adim} className={`tp-adim${gec ? ' gec' : ''}${a.n ? '' : ' bos'}`} title={ADIM_ACIKLAMA[a.adim] ?? a.adim}>
              <span className="ad">{ADIM_ADI[a.adim] ?? a.adim}</span>
              <span className="deger">{a.medyan_dk == null ? '—' : sureMetni(a.medyan_dk)}</span>
              <span className="ek">
                {a.n
                  ? `${a.hedefte_oran == null ? '' : `${yuzde(a.hedefte_oran)} · `}hedef ${sureMetni(a.hedef_dk)}`
                  : 'kayıt yok'}
              </span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

/* ------------------------------ Birikim ve BTK ------------------------------ */

function Birikim({ t, gun, suz }: { t: TakipYanit; gun: number; suz: ((kod: string) => void) | null }) {
  const seri = t.birikim.seri.map((s) => s.asan24);
  const egim = t.birikim.egim_gun;
  return (
    <section className="tp-bolum">
      <div className="tp-bolum-bas">
        <h2>Birikim</h2>
        <span className="tp-bolum-alt">24 saati aşan açık iş</span>
      </div>
      <div className="tp-satir-buyuk">
        <button type="button" className="tp-buyuk-sayi" onClick={suz ? () => suz(SUZ.asan24) : undefined} disabled={!suz}>
          {sayi(t.birikim.asan24)}
        </button>
        <span className={`tp-egim${egim != null && egim > 0 ? ' kotu' : egim != null && egim < 0 ? ' iyi' : ''}`}>
          {egim == null
            ? 'Eğim için en az yarım günlük kayıt gerekir'
            : `${egim > 0 ? '↗ +' : egim < 0 ? '↘ ' : '→ '}${sayi(egim).replace('-', '−')}/gün (${gun === 1 ? '24 saat' : `${gun} gün`})`}
        </span>
      </div>
      {seri.length >= 2 ? <Egri degerler={seri} etiket="24 saati aşan açık iş sayısının seyri" genis /> : null}
    </section>
  );
}

function BtkBolumu({ t, suz }: { t: TakipYanit; suz: ((kod: string) => void) | null }) {
  const satirlar: Array<{ etiket: string; deger: string; kod?: string; uyari?: boolean }> = [
    { etiket: 'TV hedefi 6 s içinde', deger: yuzde(t.btk.tv6) },
    { etiket: 'Bağlantı hedefi 12 s içinde', deger: yuzde(t.btk.baglanti12) },
    { etiket: 'Teşhis araması ≤ 45 dk', deger: yuzde(t.btk.teshis45) },
    { etiket: 'Askıda (BTK saati durdu)', deger: sayi(t.hijyen.askida_btk_durdu), kod: SUZ.askidaBtkDurdu },
    { etiket: 'Şikâyeti alarm gününde', deger: sayi(t.hijyen.btk_alarm), kod: SUZ.btkAlarm, uyari: t.hijyen.btk_alarm > 0 },
  ];
  return (
    <section className="tp-bolum">
      <div className="tp-bolum-bas">
        <h2>BTK</h2>
        <span className="tp-bolum-alt">hedefte çözülen payı · abone kaynaklı askıda saat durur</span>
      </div>
      <ul className="tp-liste">
        {satirlar.map((s) => (
          <SayiSatiri key={s.etiket} {...s} suz={suz} />
        ))}
      </ul>
    </section>
  );
}

function SayiSatiri({
  etiket,
  deger,
  kod,
  uyari,
  suz,
  soluk,
}: {
  etiket: string;
  deger: string;
  kod?: string;
  uyari?: boolean;
  suz: ((kod: string) => void) | null;
  soluk?: boolean;
}) {
  const ic = (
    <>
      <span className="etiket">{etiket}</span>
      <span className={`deger${uyari ? ' uyari' : ''}`}>{deger}</span>
    </>
  );
  return (
    <li className={soluk ? 'soluk' : undefined}>
      {kod && suz ? (
        <button type="button" onClick={() => suz(kod)}>
          {ic}
        </button>
      ) : (
        <span className="tp-liste-ic">{ic}</span>
      )}
    </li>
  );
}

/* ------------------------------ Hijyen ------------------------------ */

function Hijyen({ t, suz }: { t: TakipYanit; suz: ((kod: string) => void) | null }) {
  const h = t.hijyen;
  const satirlar = [
    { etiket: 'Çözüldü ama BOSS’ta açık', n: h.cozuldu_boss_acik, kod: SUZ.bossAcik },
    { etiket: 'Askıda, uyanma yok', n: h.askida_uyanmasiz, kod: SUZ.askidaUyanmasiz },
    { etiket: 'BOSS’a işlenecek', n: h.boss_islenecek, kod: SUZ.bossIslenecek },
    { etiket: 'Kanal şikâyeti (öncelikli)', n: h.oncelikli, kod: SUZ.oncelikli },
    { etiket: 'Genel arıza — sevk edilmiyor', n: h.genel_ariza, kod: SUZ.genelAriza },
    { etiket: 'Kontrol gerekli', n: t.manset.kontrol, kod: SUZ.kontrol },
  ];
  const temiz = satirlar.every((s) => !s.n);
  return (
    <section className="tp-bolum">
      <div className="tp-bolum-bas">
        <h2>Hijyen</h2>
        <span className="tp-bolum-alt">{temiz ? 'Hepsi temiz ✓' : 'elle toparlanacaklar'}</span>
      </div>
      <ul className="tp-liste iki-sutun">
        {satirlar.map((s) => (
          <SayiSatiri key={s.etiket} etiket={s.etiket} deger={sayi(s.n)} kod={s.n ? s.kod : undefined} uyari={s.n > 0} soluk={!s.n} suz={suz} />
        ))}
      </ul>
    </section>
  );
}

/* ------------------------------ Tablolar ------------------------------ */

function ObekTablosu({ t, tikla }: { t: TakipYanit; tikla: ((id: number) => void) | null }) {
  const satirlar = useMemo(
    () => [...t.obekler].sort((a, b) => b.atanmamis - a.atanmamis || b.geciken - a.geciken || b.acik - a.acik || a.ad.localeCompare(b.ad, 'tr')),
    [t.obekler],
  );
  return (
    <section className="tp-bolum">
      <div className="tp-bolum-bas">
        <h2>Öbekler</h2>
        <span className="tp-bolum-alt">{sayi(satirlar.length)} öbek · atanmamışı olan önce</span>
      </div>
      {satirlar.length ? (
        <div className="yon-tablo-sarmal">
          <table className="yon-tablo satirlasir tp-tablo">
            <thead>
              <tr>
                <th>Öbek</th>
                <th className="sayi">Açık</th>
                <th className="sayi">Geciken</th>
                <th className="sayi">BTK</th>
                <th className="sayi">Atanmamış</th>
                <th>Ev teknisyeni</th>
              </tr>
            </thead>
            <tbody>
              {satirlar.map((o) => (
                <tr
                  key={o.id}
                  className={`${tikla ? 'tiklanir' : ''}${o.acik ? '' : ' soluk'}`}
                  onClick={tikla ? () => tikla(o.id) : undefined}
                  onKeyDown={tikla ? (e) => (e.key === 'Enter' ? tikla(o.id) : undefined) : undefined}
                  tabIndex={tikla ? 0 : undefined}
                >
                  <td className="ad-hucre">{o.ad}</td>
                  <td className="sayi" data-etiket="Açık">{sayi(o.acik)}</td>
                  <td className={`sayi${o.geciken ? ' kirmizi' : ''}`} data-etiket="Geciken">{sayi(o.geciken)}</td>
                  <td className="sayi" data-etiket="BTK">{sayi(o.btk)}</td>
                  <td className={`sayi${o.atanmamis ? ' mavi' : ''}`} data-etiket="Atanmamış">{sayi(o.atanmamis)}</td>
                  <td className="tam" data-etiket="Ev teknisyeni">{o.sahip?.ad ?? 'Teknisyeni yok'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="tp-bos">Henüz öbek yok. Öbekler ekranından ekleyin.</p>
      )}
    </section>
  );
}

function TeknikTablosu({ t, tikla }: { t: TakipYanit; tikla: ((id: number) => void) | null }) {
  const satirlar = t.teknikler;
  return (
    <section className="tp-bolum">
      <div className="tp-bolum-bas">
        <h2>Teknik</h2>
        <span className="tp-bolum-alt">bugün</span>
      </div>
      {satirlar.length ? (
        <div className="yon-tablo-sarmal">
          <table className="yon-tablo satirlasir tp-tablo">
            <thead>
              <tr>
                <th>Kişi</th>
                <th className="sayi">Atanan</th>
                <th className="sayi">Biten</th>
                <th className="sayi">Evde yok</th>
                <th className="sayi">Yolda / sahada</th>
                <th>İlk iş</th>
              </tr>
            </thead>
            <tbody>
              {satirlar.map((k) => (
                <tr
                  key={k.id}
                  className={`${tikla ? 'tiklanir' : ''}${k.atanan || k.biten ? '' : ' soluk'}`}
                  onClick={tikla ? () => tikla(k.id) : undefined}
                  onKeyDown={tikla ? (e) => (e.key === 'Enter' ? tikla(k.id) : undefined) : undefined}
                  tabIndex={tikla ? 0 : undefined}
                >
                  <td className="ad-hucre">{k.ad}</td>
                  <td className="sayi" data-etiket="Atanan">{sayi(k.atanan)}</td>
                  <td className="sayi" data-etiket="Biten">{sayi(k.biten)}</td>
                  <td className="sayi" data-etiket="Evde yok">{sayi(k.evde_yok)}</td>
                  <td className="sayi" data-etiket="Yolda / sahada">{sayi(k.yolda_sahada)}</td>
                  <td data-etiket="İlk iş">{k.ilk_is ? saatMetni(k.ilk_is) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="tp-bos">Ekip'te teknik görevli kişi yok. Ekip ekranından ekleyin.</p>
      )}
    </section>
  );
}

/* ------------------------------ Sistem (yalnız yönetici) ------------------------------ */

function SistemBolumu({ t }: { t: TakipYanit }) {
  const [panel, setPanel] = useState<'yonetim' | 'erisim' | null>(null);
  const erisim = useVeri(() => takipErisim(1), [], 0);
  const bugun = t.sunucu_zamani.slice(0, 10);
  const bugunErisim = (erisim.veri?.gunler ?? []).filter((g) => g.gun === bugun).reduce((a, g) => a + (g.adet || 0), 0);
  return (
    <section className="tp-bolum">
      <div className="tp-bolum-bas">
        <h2>Sistem</h2>
      </div>
      <ul className="tp-liste iki-sutun">
        <SayiSatiri etiket="Son yedek" deger={t.sistem.son_yedek ? tarihSaatMetni(t.sistem.son_yedek) : 'yok'} suz={null} uyari={!t.sistem.son_yedek} />
        <SayiSatiri etiket="Son güncelleme" deger={t.sistem.son_goc ? tarihSaatMetni(t.sistem.son_goc) : '—'} suz={null} />
        <li>
          <button type="button" onClick={() => setPanel('erisim')}>
            <span className="etiket">Müşteri bilgisi erişimi (bugün)</span>
            <span className="deger">{erisim.veri ? sayi(bugunErisim) : '—'}</span>
          </button>
        </li>
        <li>
          <button type="button" onClick={() => setPanel('yonetim')}>
            <span className="etiket">Yönetim kaydı</span>
            <span className="deger bag">Aç ›</span>
          </button>
        </li>
      </ul>
      <p className="tp-dipnot">{t.sistem.saklama_metni}</p>
      <YonetimPaneli acik={panel === 'yonetim'} kapat={() => setPanel(null)} />
      <ErisimPaneli acik={panel === 'erisim'} kapat={() => setPanel(null)} />
    </section>
  );
}

function eylemAdi(e: string): string {
  const s = e.replace(/[_.]/g, ' ').trim();
  return s ? s[0].toLocaleUpperCase('tr-TR') + s.slice(1) : e;
}

function YonetimPaneli({ acik, kapat }: { acik: boolean; kapat: () => void }) {
  return (
    <Panel acik={acik} kapat={kapat} baslik="Yönetim kaydı" altBaslik="Ekip, ayar ve veri değişiklikleri (son 100)">
      {acik ? <YonetimListesi /> : null}
    </Panel>
  );
}

function YonetimListesi() {
  const v = useVeri<YonetimKaydi[]>(() => takipYonetim(100), [], 0);
  if (v.hata) return <HataKutusu mesaj={v.hata} tekrar={v.yenile} />;
  if (!v.veri) return <Iskelet satir={6} yukseklik={44} />;
  if (!v.veri.length) return <p className="tp-bos">Kayıt yok.</p>;
  return (
    <ol className="tp-kayitlar">
      {v.veri.map((r) => (
        <li key={r.id}>
          <span className="zaman">{tarihSaatMetni(r.zaman)}</span>
          <span className="metin">
            <strong>{eylemAdi(r.eylem)}</strong>
            {r.hedef ? ` · ${r.hedef}` : ''}
            <span className="kisi">{r.kullanici_ad ?? 'Sistem'}</span>
          </span>
        </li>
      ))}
    </ol>
  );
}

function ErisimPaneli({ acik, kapat }: { acik: boolean; kapat: () => void }) {
  return (
    <Panel acik={acik} kapat={kapat} baslik="Müşteri bilgisi erişimi" altBaslik="Son 7 gün · kim, hangi ekranda, kaç kez (müşteri adı tutulmaz)">
      {acik ? <ErisimListesi /> : null}
    </Panel>
  );
}

const ERISIM_ADI: Record<string, string> = {
  is_liste: 'İş listesi',
  is_ayrinti: 'İş ayrıntısı',
  excel: 'Excel',
  kopya_musteri_no: 'Müşteri no kopyası',
  tel_goster: 'Telefon',
};

function ErisimListesi() {
  const v = useVeri(() => takipErisim(7), [], 0);
  if (v.hata) return <HataKutusu mesaj={v.hata} tekrar={v.yenile} />;
  if (!v.veri) return <Iskelet satir={6} yukseklik={44} />;
  if (!v.veri.gunler.length) return <p className="tp-bos">Bu hafta kayıt yok.</p>;
  return (
    <ol className="tp-kayitlar">
      {v.veri.gunler.map((g, i) => (
        <li key={`${g.gun}-${g.kisi}-${g.eylem}-${i}`}>
          <span className="zaman">{g.gun.split('-').reverse().join('.')}</span>
          <span className="metin">
            <strong>{g.kisi ?? '—'}</strong> · {ERISIM_ADI[g.eylem] ?? eylemAdi(g.eylem)}
          </span>
          <span className="adet">{sayi(g.adet)}</span>
        </li>
      ))}
    </ol>
  );
}
