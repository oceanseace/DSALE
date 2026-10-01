/**
 * Tur raporu yükle — Superonline'ın yeni bina listesi (data.xlsx) gelince.
 *
 *   1. Dosyayı bırak → sunucu okur, FARKI gösterir, hiçbir şeyi değiştirmez.
 *   2. Farka bak (yeni bina · çıkan bina · sayısı değişen · önce/sonra) → "Uygula".
 *      Çıkan bina silinmez, pasif olur; bölgeler ve ziyaret geçmişi değişmez.
 *   3. Yeni binaların koordinatı yoktur: OneMap'ten alınır. Adımlar burada tek
 *      tek yazılı; OneMap'in indirdiği onemap_yeni.json buraya bırakılınca binalar
 *      haritaya ve en yakın bölgeye girer.
 *
 * Aynı işlemler komut satırından da yapılır (`python -m saha.veri_araci tur …`);
 * sonuç aynıdır (sözleşme §7.3).
 */

import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent, type ReactNode } from 'react';
import { SahaHatasi } from '../../api/istemci';
import { Cekmece } from '../../ortak/Cekmece';
import { useBildirim } from '../../ortak/Bildirim';
import { kopyala } from '../../ortak/kimlik';
import { sayi, yuzde } from '../../ortak/bicim';
import { Onay, Uyari } from '../../ortak/Ikon';
import {
  bekleyenBinalar,
  bekleyenKimlikleriIndir,
  oneMapAraciIndir,
  oneMapAraciMetni,
  oneMapYukle,
  turRaporlari,
  turRaporu,
  turRaporuUygula,
  turRaporuYukle,
} from '../api';
import { useYonetim } from '../depo';
import { Icerik, YonUst } from '../ortak/Kabuk';
import { HataKutusu, Iskelet, Kart, Segment, useVeri } from '../ortak/parcalar';
import { Indir } from '../ortak/simgeler';
import type {
  BekleyenBina,
  OneMapYaniti,
  TurFarki,
  TurOnizlemesi,
  TurToplami,
  TurUygulamaYaniti,
} from '../tipler';
import './faz2.css';

const ONEMAP_ADRESI = 'https://arcgis.turkcell.com.tr/arcgis/rest/services/ONEMAP/BINA/MapServer/0';

function hataMetni(h: unknown, yedek = 'İşlem yapılamadı.') {
  return h instanceof SahaHatasi ? h.message : yedek;
}

function zamanMetni(z: string | null | undefined) {
  if (!z) return '—';
  const m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/.exec(z);
  return m ? `${m[3]}.${m[2]}.${m[1]} ${m[4]}:${m[5]}` : z;
}

function farkMetni(fark: number) {
  if (!fark) return '0';
  return `${fark > 0 ? '+' : '−'}${sayi(Math.abs(fark))}`;
}

const ALAN_ADI: Record<string, string> = {
  res_hp: 'RES HP',
  aktif_res: 'Aktif abone',
  firsat: 'Boş kapı',
  toplam_hp: 'Toplam HP',
  soho_hp: 'SOHO HP',
};

const DURUM_ADI: Record<string, string> = {
  onizleme: 'Önizleme — uygulanmadı',
  uygulandi: 'Uygulandı',
  eskidi: 'Eskidi (daha yenisi uygulandı)',
};

export function TurRaporu() {
  const { haritayiTazele } = useYonetim();
  const { goster } = useBildirim();
  const [surum, setSurum] = useState(0);
  const liste = useVeri(turRaporlari, [surum]);
  const bekleyen = useVeri(() => bekleyenBinalar('konum_bekliyor'), [surum]);

  const [onizleme, setOnizleme] = useState<TurOnizlemesi | null>(null);
  const [yukleniyor, setYukleniyor] = useState<string | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [onayAcik, setOnayAcik] = useState(false);
  const [sonuc, setSonuc] = useState<TurUygulamaYaniti | null>(null);
  const [pasifOnay, setPasifOnay] = useState(false);
  const [ekIller, setEkIller] = useState<Set<string>>(new Set());
  const adimRef = useRef<HTMLDivElement | null>(null);

  const dosyaSecildi = async (dosya: File | null | undefined) => {
    if (!dosya) return;
    if (!/\.xlsx$/i.test(dosya.name)) {
      setHata(`"${dosya.name}" bir Excel (.xlsx) dosyası değil. Tur raporunu (data.xlsx) seçin.`);
      return;
    }
    setHata(null);
    setSonuc(null);
    setOnizleme(null);
    setPasifOnay(false);
    setEkIller(new Set());
    setYukleniyor(dosya.name);
    try {
      const y = await turRaporuYukle(dosya);
      setOnizleme(y);
      setSurum((s) => s + 1);
    } catch (h) {
      setHata(hataMetni(h, 'Rapor okunamadı.'));
    } finally {
      setYukleniyor(null);
    }
  };

  const eskiRaporuAc = async (turId: number) => {
    setHata(null);
    setSonuc(null);
    try {
      setOnizleme(await turRaporu(turId));
      setPasifOnay(false);
      setEkIller(new Set());
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (h) {
      setHata(hataMetni(h, 'Rapor kaydı açılamadı.'));
    }
  };

  const uygulandi = (y: TurUygulamaYaniti) => {
    setOnayAcik(false);
    setSonuc(y);
    setOnizleme(null);
    setSurum((s) => s + 1);
    haritayiTazele();
    goster(y.zaten_uygulandi ? 'Bu rapor zaten uygulanmıştı.' : 'Tur raporu uygulandı.', 'basari');
    window.setTimeout(() => adimRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 200);
  };

  const adim = onizleme ? 2 : (bekleyen.veri?.toplam ?? 0) > 0 || sonuc ? 3 : 1;
  const sonUygulanan = liste.veri?.son_uygulanan;

  return (
    <>
      <YonUst
        baslik="Tur raporu yükle"
        altYazi="Yeni bina listesi (data.xlsx) gelince: yükle → farka bak → uygula. Bölgeler ve ziyaret geçmişi değişmez."
      />

      <Icerik>
        <ol className="tr-adimlar" aria-label="Adımlar">
          <AdimBasi no={1} etkin={adim === 1} bitti={adim > 1} baslik="Raporu yükleyin" />
          <AdimBasi no={2} etkin={adim === 2} bitti={Boolean(sonuc)} baslik="Farka bakıp uygulayın" />
          <AdimBasi no={3} etkin={adim === 3} bitti={false} baslik="Yeni binaların konumu (OneMap)" />
        </ol>

        <DosyaAlani
          kabul=".xlsx"
          ince={Boolean(onizleme) || adim === 3}
          calisiyor={yukleniyor}
          secildi={dosyaSecildi}
          baslik="Tur raporunu (data.xlsx) buraya sürükleyin"
          alt="ya da tıklayıp seçin · ORIGN sayfası okunur · en çok 80 MB"
          inceMetin="Başka bir rapor yüklemek için dosyayı buraya bırakın ya da tıklayın"
          calisiyorMetni={(ad) => `${ad} okunuyor… 19.706 bina karşılaştırılıyor (yaklaşık 5 saniye)`}
        />

        {!onizleme && !yukleniyor && sonUygulanan ? (
          <div className="tr-bilgi">
            Son uygulanan rapor: <b>{zamanMetni(sonUygulanan.zaman)}</b> (kayıt {sonUygulanan.tur_id}). Yeni rapor
            gelene kadar sistem bu sayılarla çalışır.
          </div>
        ) : null}

        {hata ? <HataKutusu mesaj={hata} /> : null}

        {sonuc ? (
          <div className="yon-uyari yesil" role="status">
            <Onay boyut={18} />
            <span>{sonuc.mesaj}</span>
          </div>
        ) : null}

        {onizleme ? (
          <FarkGorunumu
            o={onizleme}
            pasifOnay={pasifOnay}
            setPasifOnay={setPasifOnay}
            ekIller={ekIller}
            setEkIller={setEkIller}
            vazgec={() => setOnizleme(null)}
            uygula={() => setOnayAcik(true)}
          />
        ) : null}

        <div ref={adimRef}>
          <OneMapAdimi
            bekleyen={bekleyen.veri?.binalar ?? null}
            toplam={bekleyen.veri?.toplam ?? 0}
            yukleniyor={bekleyen.yukleniyor && !bekleyen.veri}
            yenile={() => setSurum((s) => s + 1)}
            eklendi={() => {
              setSurum((s) => s + 1);
              haritayiTazele();
            }}
          />
        </div>

        <Kart
          baslik="Yüklenen raporlar"
          altYazi="Her yükleme saklanır. Uygulanmamış bir önizlemeyi yeniden açmak için satıra tıklayın."
          sikis
        >
          {liste.yukleniyor && !liste.veri ? (
            <div style={{ padding: 16 }}>
              <Iskelet yukseklik={90} />
            </div>
          ) : liste.veri?.raporlar.length ? (
            <div className="yon-tablo-sarmal">
              <table className="yon-tablo">
                <thead>
                  <tr>
                    <th>Yükleme</th>
                    <th>Dosya</th>
                    <th>Durum</th>
                    <th className="sayi">Yeni</th>
                    <th className="sayi">Çıkan</th>
                    <th className="sayi">Değişen</th>
                    <th>Yükleyen</th>
                  </tr>
                </thead>
                <tbody>
                  {liste.veri.raporlar.map((r) => (
                    <tr
                      key={r.tur_id}
                      className={`tiklanir${onizleme?.tur_id === r.tur_id ? ' secili' : ''}`}
                      onClick={() => void eskiRaporuAc(r.tur_id)}
                    >
                      <td>{zamanMetni(r.yukleme)}</td>
                      <td className="tr-dosya">{r.dosya}</td>
                      <td>
                        <span className={`bp-rozet ${r.durum === 'uygulandi' ? 'yesil' : r.durum === 'onizleme' ? 'mavi' : 'gri'}`}>
                          {DURUM_ADI[r.durum] ?? r.durum}
                        </span>
                      </td>
                      <td className="sayi">{sayi(r.yeni_bina ?? 0)}</td>
                      <td className="sayi">{sayi(r.cikan_bina ?? 0)}</td>
                      <td className="sayi">{sayi(r.degisen_bina ?? 0)}</td>
                      <td>{r.yukleyen ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="tr-bos">Henüz rapor yüklenmedi.</p>
          )}
        </Kart>
      </Icerik>

      {onizleme ? (
        <UygulaCekmecesi
          acik={onayAcik}
          kapat={() => setOnayAcik(false)}
          o={onizleme}
          pasifOnay={pasifOnay}
          ekIller={ekIller}
          uygulandi={uygulandi}
        />
      ) : null}
    </>
  );
}

/* ------------------------------ Adım başlığı ------------------------------ */

function AdimBasi({ no, etkin, bitti, baslik }: { no: number; etkin: boolean; bitti: boolean; baslik: string }) {
  return (
    <li className={`tr-adim${etkin ? ' etkin' : ''}${bitti ? ' bitti' : ''}`} aria-current={etkin ? 'step' : undefined}>
      <span className="tr-adim-no">{bitti ? <Onay boyut={15} /> : no}</span>
      <span>{baslik}</span>
    </li>
  );
}

/* ------------------------------ Dosya bırakma alanı ------------------------------ */

export function DosyaAlani({
  kabul,
  ince = false,
  calisiyor,
  secildi,
  baslik,
  alt,
  inceMetin,
  calisiyorMetni,
}: {
  kabul: string;
  ince?: boolean;
  calisiyor: string | null;
  secildi: (d: File | null | undefined) => void;
  baslik: string;
  alt: string;
  inceMetin?: string;
  calisiyorMetni: (ad: string) => string;
}) {
  const [uzerinde, setUzerinde] = useState(false);
  const girdi = useRef<HTMLInputElement | null>(null);
  const birak = (o: DragEvent<HTMLDivElement>) => {
    o.preventDefault();
    setUzerinde(false);
    if (!calisiyor) secildi(o.dataTransfer.files?.[0]);
  };
  return (
    <div
      className={`tr-birak${uzerinde ? ' uzerinde' : ''}${ince ? ' ince' : ''}${calisiyor ? ' calisiyor' : ''}`}
      onDragOver={(o) => {
        o.preventDefault();
        setUzerinde(true);
      }}
      onDragLeave={() => setUzerinde(false)}
      onDrop={birak}
      onClick={() => !calisiyor && girdi.current?.click()}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if ((e.key === 'Enter' || e.key === ' ') && !calisiyor) girdi.current?.click();
      }}
    >
      <input
        ref={girdi}
        type="file"
        accept={kabul}
        hidden
        onChange={(e) => {
          secildi(e.target.files?.[0]);
          e.target.value = '';
        }}
      />
      {calisiyor ? (
        <div className="tr-birak-ic">
          <span className="tr-donen" aria-hidden="true" />
          <b>{calisiyorMetni(calisiyor)}</b>
        </div>
      ) : ince ? (
        <div className="tr-birak-ic yatay">
          <Indir boyut={18} />
          <span>{inceMetin ?? baslik}</span>
        </div>
      ) : (
        <div className="tr-birak-ic">
          <span className="tr-birak-simge" aria-hidden="true">
            <Indir boyut={26} />
          </span>
          <b>{baslik}</b>
          <span>{alt}</span>
        </div>
      )}
    </div>
  );
}

/* ------------------------------ Fark ------------------------------ */

type OrnekSekme = 'degisen' | 'yeni' | 'cikan' | 'geri_donen';

function FarkGorunumu({
  o,
  pasifOnay,
  setPasifOnay,
  ekIller,
  setEkIller,
  vazgec,
  uygula,
}: {
  o: TurOnizlemesi;
  pasifOnay: boolean;
  setPasifOnay: (v: boolean) => void;
  ekIller: Set<string>;
  setEkIller: (s: Set<string>) => void;
  vazgec: () => void;
  uygula: () => void;
}) {
  const f = o.fark;
  const farkYok = !f.yeni_bina && !f.cikan_bina && !f.degisen_bina && !f.geri_donen_bina;
  const ilkSekme: OrnekSekme = f.degisen_bina ? 'degisen' : f.yeni_bina ? 'yeni' : f.cikan_bina ? 'cikan' : 'geri_donen';
  const [sekme, setSekme] = useState<OrnekSekme>(ilkSekme);
  useEffect(() => setSekme(ilkSekme), [o.tur_id]); // eslint-disable-line react-hooks/exhaustive-deps

  const uygulanabilir = o.durum === undefined || o.durum === 'onizleme';
  const onayEksik = f.pasif_onay_gerekli && !pasifOnay;
  const ilDisi = Object.entries(f.il_disi_dagilim ?? {}).sort((a, b) => b[1] - a[1]);

  return (
    <section className="yon-kart tr-fark" aria-label="Rapor farkı">
      <div className="tr-fark-ust">
        <div style={{ minWidth: 0 }}>
          <div className="tr-fark-baslik">
            {o.dosya_adi || o.dosya} · {o.okuma.sayfa} sayfası · <b>{sayi(o.okuma.tekil_bina)} bina</b> okundu
          </div>
          <div className="tr-fark-alt">
            {o.durum === 'uygulandi'
              ? `Bu rapor uygulandı (${zamanMetni(o.uygulama)}).`
              : o.durum === 'eskidi'
                ? 'Bu önizleme eskidi: ondan sonra yüklenen bir rapor uygulandı.'
                : 'Önizleme — henüz hiçbir şey değişmedi.'}
            {o.ayni_dosya_daha_once
              ? ` Aynı dosya daha önce de yüklenmişti (${zamanMetni(o.ayni_dosya_daha_once.yukleme)}).`
              : ''}
            {o.okuma.tekrar ? ` Raporda ${sayi(o.okuma.tekrar)} bina iki kez geçiyor (büyük HP'li satır alındı).` : ''}
            {o.okuma.bozuk_tellcordia
              ? ` ${sayi(o.okuma.bozuk_tellcordia)} Tellcordia ID bilimsel sayıya dönmüştü, düzeltildi.`
              : ''}
          </div>
        </div>
      </div>

      {farkYok ? (
        <div className="tr-ayni">
          <Onay boyut={22} />
          <div>
            <b>Rapor sistemdeki verilerle birebir aynı.</b>
            <span>Yeni, çıkan ya da sayısı değişen bina yok. Uygulamak yalnız "son tur raporu" tarihini yeniler.</span>
          </div>
        </div>
      ) : (
        <div className="tr-kutular">
          <FarkKutusu renk="mavi" deger={f.yeni_bina} etiket="Yeni bina" alt="OneMap'ten konum alınıp haritaya eklenecek" />
          <FarkKutusu
            renk={f.cikan_bina ? 'amber' : undefined}
            deger={f.cikan_bina}
            etiket="Rapordan çıkan"
            alt={`Pasife alınacak, silinmez · bugünkü binaların ${yuzde(f.cikan_oran, f.cikan_oran < 0.01 ? 2 : 1)} kadarı`}
          />
          <FarkKutusu deger={f.degisen_bina} etiket="Sayısı değişen" alt="HP, abone ya da boş kapı güncellenecek" />
          <FarkKutusu
            renk={f.geri_donen_bina ? 'yesil' : undefined}
            deger={f.geri_donen_bina}
            etiket="Geri dönen"
            alt="Önceden pasifti, yeniden etkinleşecek"
          />
        </div>
      )}

      <OnceSonra once={f.once} sonra={f.sonra} />

      {f.uyarilar.length ? (
        <div className="bp-dikkat">
          {f.uyarilar.map((u) => (
            <div key={u}>
              <Uyari boyut={16} /> {u}
            </div>
          ))}
        </div>
      ) : null}

      {!farkYok ? <OrnekTablosu f={f} sekme={sekme} setSekme={setSekme} /> : null}

      {uygulanabilir && ilDisi.length ? (
        <div className="tr-iller">
          <div className="tr-iller-baslik">
            Hizmet verilen iller ({f.hizmet_illeri.join(', ')}) dışındaki yeni binalar varsayılan olarak eklenmez.
            Eklemek istediğiniz ili işaretleyin:
          </div>
          <div className="tr-iller-liste">
            {ilDisi.map(([il, adet]) => (
              <label key={il} className="tr-il">
                <input
                  type="checkbox"
                  checked={ekIller.has(il)}
                  onChange={(e) => {
                    const y = new Set(ekIller);
                    if (e.target.checked) y.add(il);
                    else y.delete(il);
                    setEkIller(y);
                  }}
                />
                {il} <b>{sayi(adet)}</b>
              </label>
            ))}
          </div>
        </div>
      ) : null}

      {uygulanabilir && f.pasif_onay_gerekli ? (
        <label className="bp-onay-kutu kirmizi">
          <input type="checkbox" checked={pasifOnay} onChange={(e) => setPasifOnay(e.target.checked)} />
          <span>
            <b>Rapor tam, eksik değil.</b> Bugünkü {sayi(f.cikan_bina)} bina (oran {yuzde(f.cikan_oran)}) bu raporda
            yok; pasife alınmalarını onaylıyorum. (Tek ilçelik ya da yarım bir dosya yüklendiyse işaretlemeyin.)
          </span>
        </label>
      ) : null}

      <div className="tr-fark-dugmeler">
        <button className="yd" onClick={vazgec}>
          {uygulanabilir ? 'Vazgeç' : 'Kapat'}
        </button>
        {uygulanabilir ? (
          <button
            className={`yd buyuk${farkYok ? '' : ' birincil'}`}
            onClick={uygula}
            disabled={onayEksik}
            title={onayEksik ? 'Önce pasife alma onayını işaretleyin' : undefined}
          >
            <Onay boyut={18} />
            {farkYok ? 'Yine de uygula' : 'Uygula'}
          </button>
        ) : null}
      </div>
    </section>
  );
}

function FarkKutusu({
  deger,
  etiket,
  alt,
  renk,
}: {
  deger: number;
  etiket: string;
  alt: string;
  renk?: 'mavi' | 'amber' | 'yesil';
}) {
  return (
    <div className={`tr-kutu${renk && deger ? ' ' + renk : ''}${deger ? '' : ' sifir'}`}>
      <div className="etiket">{etiket}</div>
      <div className="deger">{sayi(deger)}</div>
      <div className="alt">{alt}</div>
    </div>
  );
}

function OnceSonra({ once, sonra }: { once: TurToplami; sonra: TurToplami }) {
  const satirlar: Array<[keyof TurToplami, string]> = [
    ['bina', 'Bina'],
    ['res_hp', 'RES HP'],
    ['aktif_res', 'Aktif abone'],
    ['firsat', 'Boş kapı'],
    ['toplam_hp', 'Toplam HP'],
  ];
  return (
    <div className="yon-tablo-sarmal tr-once-sonra">
      <table className="yon-tablo">
        <thead>
          <tr>
            <th>Toplamlar</th>
            <th className="sayi">Şimdi</th>
            <th className="sayi">Uygulanınca</th>
            <th className="sayi">Fark</th>
          </tr>
        </thead>
        <tbody>
          {satirlar.map(([alan, ad]) => {
            const fark = (sonra[alan] ?? 0) - (once[alan] ?? 0);
            return (
              <tr key={alan}>
                <td>{ad}</td>
                <td className="sayi">{sayi(once[alan])}</td>
                <td className="sayi">{sayi(sonra[alan])}</td>
                <td className={`sayi tr-fark-hucre${fark > 0 ? ' arti' : fark < 0 ? ' eksi' : ''}`}>{farkMetni(fark)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function OrnekTablosu({
  f,
  sekme,
  setSekme,
}: {
  f: TurFarki;
  sekme: OrnekSekme;
  setSekme: (s: OrnekSekme) => void;
}) {
  const sayilar: Record<OrnekSekme, number> = {
    degisen: f.degisen_bina,
    yeni: f.yeni_bina,
    cikan: f.cikan_bina,
    geri_donen: f.geri_donen_bina,
  };
  const secenekler = (
    [
      { deger: 'degisen', etiket: `Sayısı değişen (${sayi(f.degisen_bina)})` },
      { deger: 'yeni', etiket: `Yeni (${sayi(f.yeni_bina)})` },
      { deger: 'cikan', etiket: `Çıkan (${sayi(f.cikan_bina)})` },
      { deger: 'geri_donen', etiket: `Geri dönen (${sayi(f.geri_donen_bina)})` },
    ] as Array<{ deger: OrnekSekme; etiket: string }>
  ).filter((s) => sayilar[s.deger] > 0 || s.deger === sekme);

  let govde: ReactNode = null;
  let gosterilen = 0;
  if (sekme === 'degisen') {
    gosterilen = f.ornek.degisen.length;
    govde = (
      <table className="yon-tablo">
        <thead>
          <tr>
            <th>Bina</th>
            <th>Bölge</th>
            <th>Ne değişiyor</th>
            <th className="sayi">Boş kapı farkı</th>
          </tr>
        </thead>
        <tbody>
          {f.ornek.degisen.map((b) => (
            <tr key={b.bina_serial}>
              <td className="tr-bina">
                <b>{b.ad || b.bina_serial}</b>
                <span>
                  {b.bina_serial}
                  {b.ilce ? ` · ${b.ilce}` : ''}
                </span>
              </td>
              <td>{b.bolge ? `${b.bolge}. bölge` : '—'}</td>
              <td className="tr-degisim">
                {Object.entries(b.degisim).map(([alan, [eski, yeni]]) => (
                  <span key={alan}>
                    {ALAN_ADI[alan] ?? alan} {sayi(eski)} → <b>{sayi(yeni)}</b>
                  </span>
                ))}
              </td>
              <td className={`sayi tr-fark-hucre${b.firsat_fark > 0 ? ' arti' : b.firsat_fark < 0 ? ' eksi' : ''}`}>
                {farkMetni(b.firsat_fark)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  } else if (sekme === 'yeni') {
    gosterilen = f.ornek.yeni.length;
    govde = (
      <table className="yon-tablo">
        <thead>
          <tr>
            <th>Bina</th>
            <th>İl / ilçe</th>
            <th className="sayi">RES HP</th>
            <th className="sayi">Aktif abone</th>
            <th className="sayi">Boş kapı</th>
          </tr>
        </thead>
        <tbody>
          {f.ornek.yeni.map((b) => (
            <tr key={b.bina_serial}>
              <td className="tr-bina">
                <b>{b.ad || b.site_adi_crm || b.bina_serial}</b>
                <span>{b.bina_serial}</span>
              </td>
              <td>{[b.il, b.ilce_crm].filter(Boolean).join(' / ') || '—'}</td>
              <td className="sayi">{sayi(b.res_hp)}</td>
              <td className="sayi">{sayi(b.aktif_res)}</td>
              <td className="sayi">{sayi(b.firsat)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  } else if (sekme === 'cikan') {
    gosterilen = f.ornek.cikan.length;
    govde = (
      <table className="yon-tablo">
        <thead>
          <tr>
            <th>Bina</th>
            <th>Bölge</th>
            <th className="sayi">RES HP</th>
            <th className="sayi">Boş kapı</th>
          </tr>
        </thead>
        <tbody>
          {f.ornek.cikan.map((b) => (
            <tr key={b.bina_serial}>
              <td className="tr-bina">
                <b>{b.ad || b.site_adi || b.bina_serial}</b>
                <span>
                  {b.bina_serial}
                  {b.ilce ? ` · ${b.ilce}` : ''}
                </span>
              </td>
              <td>{b.bolge ? `${b.bolge}. bölge` : '—'}</td>
              <td className="sayi">{sayi(b.res_hp)}</td>
              <td className="sayi">{sayi(b.firsat)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  } else {
    gosterilen = f.ornek.geri_donen.length;
    govde = (
      <table className="yon-tablo">
        <thead>
          <tr>
            <th>Bina</th>
            <th>Bölge</th>
          </tr>
        </thead>
        <tbody>
          {f.ornek.geri_donen.map((b) => (
            <tr key={b.bina_serial}>
              <td className="tr-bina">
                <b>{b.ad || b.bina_serial}</b>
                <span>
                  {b.bina_serial}
                  {b.ilce ? ` · ${b.ilce}` : ''}
                </span>
              </td>
              <td>{b.bolge ? `${b.bolge}. bölge` : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  return (
    <div className="tr-ornek">
      <div className="tr-ornek-ust">
        <Segment<OrnekSekme> etiket="Örnek listesi" deger={sekme} degisti={setSekme} secenekler={secenekler} />
        {sayilar[sekme] > gosterilen ? (
          <span className="tr-ornek-not">
            İlk {sayi(gosterilen)} örnek gösteriliyor (toplam {sayi(sayilar[sekme])})
          </span>
        ) : null}
      </div>
      <div className="yon-tablo-sarmal tr-ornek-tablo">{govde}</div>
    </div>
  );
}

/* ------------------------------ Uygula onayı ------------------------------ */

function UygulaCekmecesi({
  acik,
  kapat,
  o,
  pasifOnay,
  ekIller,
  uygulandi,
}: {
  acik: boolean;
  kapat: () => void;
  o: TurOnizlemesi;
  pasifOnay: boolean;
  ekIller: Set<string>;
  uygulandi: (y: TurUygulamaYaniti) => void;
}) {
  const [calisiyor, setCalisiyor] = useState(false);
  const [hata, setHata] = useState<string | null>(null);
  const f = o.fark;
  useEffect(() => {
    if (acik) setHata(null);
  }, [acik]);

  const uygula = async () => {
    setCalisiyor(true);
    setHata(null);
    try {
      const iller = ekIller.size ? [...f.hizmet_illeri, ...ekIller] : null;
      uygulandi(await turRaporuUygula({ tur_id: o.tur_id, pasif_onay: pasifOnay, iller }));
    } catch (h) {
      setHata(hataMetni(h, 'Rapor uygulanamadı. Hiçbir şey değişmedi.'));
    } finally {
      setCalisiyor(false);
    }
  };

  const ekYeni = [...ekIller].reduce((t, il) => t + (f.il_disi_dagilim[il] ?? 0), 0);
  return (
    <Cekmece
      acik={acik}
      kapat={kapat}
      kilitli={calisiyor}
      baslik="Tur raporu uygulansın mı?"
      altBaslik="Tek seferde yapılır: ya hepsi olur ya hiçbiri. Her değişiklik binanın geçmişine yazılır."
    >
      <ul className="bp-onay-liste">
        <li>
          <b>{sayi(f.degisen_bina)} binanın</b> RES HP, abone ve boş kapı sayıları güncellenir.
        </li>
        {f.cikan_bina ? (
          <li>
            <b>{sayi(f.cikan_bina)} bina pasife alınır</b> — silinmez; listelere girmez, geçmişi durur. Rapora geri
            dönerse kendiliğinden etkinleşir.
          </li>
        ) : null}
        {f.geri_donen_bina ? (
          <li>
            <b>{sayi(f.geri_donen_bina)} bina</b> yeniden etkinleşir.
          </li>
        ) : null}
        {f.yeni_bina + ekYeni ? (
          <li>
            <b>{sayi(f.yeni_bina + ekYeni)} yeni bina</b> OneMap konumu bekleyenler listesine girer (sonraki adım).
          </li>
        ) : null}
        <li>
          <b>Bölgeler, ziyaret geçmişi ve bugünkü listeler değişmez.</b>
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
        <button className="yd birincil buyuk" onClick={uygula} disabled={calisiyor}>
          {calisiyor ? 'Uygulanıyor…' : 'Evet, uygula'}
        </button>
      </div>
    </Cekmece>
  );
}

/* ------------------------------ OneMap adımı ------------------------------ */

function OneMapAdimi({
  bekleyen,
  toplam,
  yukleniyor,
  yenile,
  eklendi,
}: {
  bekleyen: BekleyenBina[] | null;
  toplam: number;
  yukleniyor: boolean;
  yenile: () => void;
  eklendi: () => void;
}) {
  const { goster } = useBildirim();
  const [gonderiliyor, setGonderiliyor] = useState<string | null>(null);
  const [sonuc, setSonuc] = useState<OneMapYaniti | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [talimatAcik, setTalimatAcik] = useState(false);
  const bekliyor = toplam > 0;
  const talimatGorunur = bekliyor || talimatAcik;

  const bildir = useCallback(
    async (is: () => Promise<unknown>, basari: string) => {
      try {
        await is();
        goster(basari, 'basari');
      } catch (h) {
        goster(hataMetni(h), 'uyari');
      }
    },
    [goster],
  );

  const araciKopyala = async () => {
    try {
      const metin = await oneMapAraciMetni();
      const ok = await kopyala(metin);
      goster(ok ? 'OneMap aracı kopyalandı — Brave konsoluna yapıştırın.' : 'Kopyalanamadı; "indir"i kullanın.', ok ? 'basari' : 'uyari');
    } catch (h) {
      goster(hataMetni(h, 'Araç alınamadı.'), 'uyari');
    }
  };

  const jsonSecildi = async (dosya: File | null | undefined) => {
    if (!dosya) return;
    if (!/\.json$/i.test(dosya.name)) {
      setHata(`"${dosya.name}" bir JSON dosyası değil. OneMap aracının indirdiği onemap_yeni.json seçilmeli.`);
      return;
    }
    setHata(null);
    setSonuc(null);
    setGonderiliyor(dosya.name);
    try {
      const y = await oneMapYukle(dosya);
      setSonuc(y);
      eklendi();
    } catch (h) {
      setHata(hataMetni(h, 'Dosya işlenemedi.'));
    } finally {
      setGonderiliyor(null);
    }
  };

  const eklenenBolgeler = useMemo(() => {
    const m = new Map<number, number>();
    (sonuc?.binalar ?? []).forEach((b) => b.bolge && m.set(b.bolge, (m.get(b.bolge) ?? 0) + 1));
    return [...m.entries()].sort((a, b) => a[0] - b[0]);
  }, [sonuc]);

  return (
    <Kart
      baslik="Yeni binaların konumu (OneMap)"
      altYazi={
        yukleniyor
          ? 'Konum bekleyen binalar getiriliyor…'
          : bekliyor
            ? `${sayi(toplam)} yeni bina haritaya girmek için koordinat bekliyor.`
            : 'Konum bekleyen bina yok. Yeni tur raporunda yeni bina çıkarsa burada listelenir.'
      }
      sag={
        <span className="yon-satir" style={{ gap: 8 }}>
          {!bekliyor ? (
            <button className="yd duz" onClick={() => setTalimatAcik((a) => !a)}>
              {talimatAcik ? 'Adımları gizle' : 'Adımları göster'}
            </button>
          ) : null}
          <button className="yd duz" onClick={yenile}>
            Yenile
          </button>
        </span>
      }
    >
      {sonuc ? (
        <div className={`yon-uyari ${sonuc.eklenen ? 'yesil' : ''}`} style={{ marginBottom: 14 }} role="status">
          <Onay boyut={18} />
          <span>
            {sonuc.mesaj}
            {eklenenBolgeler.length
              ? ` Bölgelere dağılım: ${eklenenBolgeler.map(([b, a]) => `${b}. bölge ${a}`).join(', ')}.`
              : ''}
          </span>
        </div>
      ) : null}

      {bekliyor && bekleyen ? (
        <div className="yon-tablo-sarmal tr-bekleyen">
          <table className="yon-tablo">
            <thead>
              <tr>
                <th>Bina</th>
                <th>Tellcordia ID</th>
                <th>Location Id</th>
                <th>İl / ilçe</th>
                <th className="sayi">RES HP</th>
                <th className="sayi">Boş kapı</th>
              </tr>
            </thead>
            <tbody>
              {bekleyen.slice(0, 50).map((b) => (
                <tr key={b.bina_serial}>
                  <td className="tr-bina">
                    <b>{b.ad || b.site_adi || b.bina_serial}</b>
                    <span>{b.bina_serial}</span>
                  </td>
                  <td className="tr-kod">{b.tellcordia_id || '—'}</td>
                  <td className="tr-kod">{b.location_id || '—'}</td>
                  <td>{[b.il, b.ilce].filter(Boolean).join(' / ') || '—'}</td>
                  <td className="sayi">{sayi(b.res_hp ?? 0)}</td>
                  <td className="sayi">{sayi(b.firsat ?? 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {bekleyen.length > 50 ? <p className="tr-ornek-not">İlk 50 bina gösteriliyor (toplam {sayi(toplam)}).</p> : null}
        </div>
      ) : null}

      {talimatGorunur ? (
        <ol className="tr-talimat">
          <li>
            <span className="tr-talimat-no">1</span>
            <div>
              <b>Kimlik dosyasını indirin.</b> Her satırda konumu bekleyen bir binanın kimliği var.
              <div className="tr-talimat-dugmeler">
                <button
                  className="yd"
                  disabled={!bekliyor}
                  onClick={() => void bildir(bekleyenKimlikleriIndir, 'bekleyen_idler.txt indirildi.')}
                >
                  <Indir boyut={17} />
                  bekleyen_idler.txt indir
                </button>
              </div>
            </div>
          </li>
          <li>
            <span className="tr-talimat-no">2</span>
            <div>
              <b>Brave'i açın</b> (OneMap oturumunuz açık olmalı) ve şu adrese gidin:
              <div className="tr-adres">
                <code>{ONEMAP_ADRESI}</code>
                <button
                  className="yd"
                  onClick={async () =>
                    goster((await kopyala(ONEMAP_ADRESI)) ? 'Adres kopyalandı — Brave\'e yapıştırın.' : 'Kopyalanamadı.', 'bilgi')
                  }
                >
                  Adresi kopyala
                </button>
              </div>
            </div>
          </li>
          <li>
            <span className="tr-talimat-no">3</span>
            <div>
              Klavyede <kbd>F12</kbd> tuşuna basın → üstten <b>Console</b> (Konsol) sekmesini seçin.
            </div>
          </li>
          <li>
            <span className="tr-talimat-no">4</span>
            <div>
              <b>OneMap aracını kopyalayıp konsola yapıştırın</b>, <kbd>Enter</kbd> tuşuna basın. Tarayıcı "yapıştırmaya
              izin ver" derse <code>allow pasting</code> yazıp Enter tuşuna basın, sonra tekrar yapıştırın.
              <div className="tr-talimat-dugmeler">
                <button className="yd birincil" onClick={() => void araciKopyala()}>
                  Aracı kopyala
                </button>
                <button className="yd duz" onClick={() => void bildir(oneMapAraciIndir, 'onemap_cek.js indirildi.')}>
                  ya da dosya olarak indir
                </button>
              </div>
            </div>
          </li>
          <li>
            <span className="tr-talimat-no">5</span>
            <div>
              Sağ üstte <b>mavi çerçeveli bir kutu</b> açılır. <b>bekleyen_idler.txt</b> dosyasını seçin. İş bitince{' '}
              <b>onemap_yeni.json</b> İndirilenler klasörüne iner.
            </div>
          </li>
          <li>
            <span className="tr-talimat-no">6</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <b>onemap_yeni.json dosyasını buraya bırakın.</b> Binalar haritaya eklenir: aynı sitenin binaları varsa
              onların bölgesine, yoksa en yakın binanın bölgesine.
              <div style={{ marginTop: 10 }}>
                <DosyaAlani
                  kabul=".json,application/json"
                  calisiyor={gonderiliyor}
                  secildi={jsonSecildi}
                  baslik="onemap_yeni.json dosyasını buraya sürükleyin"
                  alt="ya da tıklayıp seçin (İndirilenler klasörü)"
                  calisiyorMetni={(ad) => `${ad} işleniyor…`}
                />
              </div>
              {hata ? (
                <div className="yon-uyari kirmizi" style={{ marginTop: 10 }}>
                  <Uyari boyut={18} />
                  {hata}
                </div>
              ) : null}
            </div>
          </li>
        </ol>
      ) : null}

      {talimatGorunur ? (
        <p className="tr-guvence">
          Araç yalnız OneMap'e sorgu atar ve sonucu <b>sizin bilgisayarınıza</b> indirir. Şifre sormaz, oturum bilgisine
          dokunmaz, başka hiçbir yere veri göndermez. OneMap'te henüz olmayan binalar "bulunamadı" sayılır, bir sonraki
          turda yeniden denenir.
        </p>
      ) : null}
    </Kart>
  );
}
