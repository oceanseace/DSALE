/**
 * Görev atama — "Trendyol Go'ya paket düşer gibi".
 *
 * Üç adım, tek ekran: kime → hangi binalar → ne zaman. Binalar üç yoldan seçilir:
 *   1. Algoritma seçsin  — öncelik formülünün en iyi N binası (önizleme, henüz gönderilmez)
 *   2. Mahalleden seç    — bir mahallenin uygun binaları
 *   3. Haritadan çiz     — haritada dikdörtgen çizilir, içindekiler seçilir
 * Her üçünde de yönetici listeyi tek tek düzenleyebilir; son sözü o söyler.
 *
 * Gönderilen liste satışçının telefonunda o günün listesi olarak belirir.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useBildirim } from '../../ortak/Bildirim';
import { Kapat, Onay, Uyari } from '../../ortak/Ikon';
import { mesafe, sayi } from '../../ortak/bicim';
import { binalar as binalarUcu, bugunMetni, gorevAta, gunEkle } from '../api';
import { satiscilar, useYonetim } from '../depo';
import {
  algoritmaSecimi,
  OFIS_VARSAYILAN,
  oncelikPuani,
  turaDiz,
  uygunMu,
  uygunsuzlukNedeni,
} from '../oncelik';
import { Icerik, YonUst, bolumeGit } from '../ortak/Kabuk';
import { HaritaTuval, type HaritaNoktasi } from '../ortak/HaritaTuval';
import { BasHarf, BosDurumKutusu, HataKutusu, Iskelet, Kart } from '../ortak/parcalar';
import { Cerceve, Kivilcim, Paket } from '../ortak/simgeler';
import type { BinaKart, SatisciGunu, YoneticiKullanici } from '../tipler';

/** Sunucu bir görevde en çok 60 bina kabul ediyor (ayarlar.EN_FAZLA_ADET). */
const EN_FAZLA = 60;
const VARSAYILAN_ADET = 25;
/** Bir günlük turun makul üst sınırı; üstünde yöneticiye uyarı gösterilir. */
const DAGINIK_ESIK_M = 25000;

type Yol = 'algoritma' | 'mahalle' | 'harita';

export function Atama({ baslangicKullanici }: { baslangicKullanici?: number | null }) {
  const { ekip, gun, ofis, gunTazele } = useYonetim();
  const { goster } = useBildirim();
  // Pasif hesaplara liste gönderilemez (geri alınan planın kapanan yer tutucuları
  // dahil); bölgesizler en sona: önce iş verilebilecek olanlar görünür.
  const ekipListesi = satiscilar(ekip)
    .filter((k) => k.aktif)
    .sort((a, b) => Number(!a.bolge) - Number(!b.bolge));

  const [kullaniciId, setKullaniciId] = useState<number | null>(baslangicKullanici ?? null);
  const [yol, setYol] = useState<Yol>('algoritma');
  const [mahalle, setMahalle] = useState('');
  const [adet, setAdet] = useState(VARSAYILAN_ADET);
  const [tarih, setTarih] = useState(bugunMetni());
  const [notu, setNotu] = useState('');
  const [secim, setSecim] = useState<string[]>([]);
  const [gonderiliyor, setGonderiliyor] = useState(false);
  const [sonuc, setSonuc] = useState<{ ad: string; adet: number; tarih: string } | null>(null);
  /** Haritayı elle odaklama anahtarı ("seçime yakınlaş" / "bölgeyi göster"). */
  const [odak, setOdak] = useState('');

  /* Bölgenin bütün binaları bir kez indirilir; seçim, önizleme ve harita ondan beslenir. */
  const [havuz, setHavuz] = useState<BinaKart[] | null>(null);
  const [havuzYukleniyor, setHavuzYukleniyor] = useState(false);
  const [havuzHatasi, setHavuzHatasi] = useState<string | null>(null);

  const kullanici = ekipListesi.find((k) => k.id === kullaniciId) ?? null;
  const bolge = kullanici?.bolge ?? null;

  useEffect(() => {
    if (baslangicKullanici) setKullaniciId(baslangicKullanici);
  }, [baslangicKullanici]);

  const havuzuGetir = useCallback(async (hedefBolge: number) => {
    setHavuzYukleniyor(true);
    setHavuzHatasi(null);
    try {
      const hepsi: BinaKart[] = [];
      let offset = 0;
      for (let tur = 0; tur < 8; tur++) {
        const yanit = await binalarUcu({ bolge: hedefBolge, limit: 1000, offset });
        hepsi.push(...yanit.binalar);
        offset += yanit.binalar.length;
        if (!yanit.binalar.length || hepsi.length >= yanit.toplam) break;
      }
      setHavuz(hepsi);
    } catch {
      setHavuzHatasi('Bölgenin binaları alınamadı. Bağlantıyı kontrol edip tekrar deneyin.');
      setHavuz(null);
    } finally {
      setHavuzYukleniyor(false);
    }
  }, []);

  useEffect(() => {
    setSecim([]);
    setMahalle('');
    setHavuz(null);
    if (bolge) void havuzuGetir(bolge);
  }, [bolge, havuzuGetir]);

  const bugun = useMemo(() => new Date(), []);
  const kartlar = useMemo(() => {
    const m = new Map<string, BinaKart>();
    (havuz ?? []).forEach((b) => m.set(b.bina_serial, b));
    return m;
  }, [havuz]);

  const mahalleler = useMemo(() => {
    const kume = new Map<string, number>();
    (havuz ?? []).forEach((b) => {
      if (!b.mahalle) return;
      if (uygunMu(b, bugun)) kume.set(b.mahalle, (kume.get(b.mahalle) ?? 0) + 1);
    });
    return Array.from(kume.entries()).sort((a, b) => a[0].localeCompare(b[0], 'tr'));
  }, [havuz, bugun]);

  const noktalar = useMemo<HaritaNoktasi[]>(
    () =>
      (havuz ?? []).map((b) => ({
        serial: b.bina_serial,
        konum: [b.lon, b.lat] as [number, number],
        durum: b.durum,
        firsat: b.firsat,
        bolge: b.bolge,
      })),
    [havuz],
  );

  const secimKumesi = useMemo(() => new Set(secim), [secim]);
  const secilenNoktalar = useMemo(
    () => noktalar.filter((n) => secimKumesi.has(n.serial)),
    [noktalar, secimKumesi],
  );
  /* Önizleme listesi gezilecek sıraya dizilir: yönetici günü olduğu gibi görür. */
  const baslangic = useMemo<[number, number]>(
    () => (ofis ? [ofis.lat, ofis.lon] : OFIS_VARSAYILAN),
    [ofis],
  );
  const secilenKartlar = useMemo(
    () =>
      turaDiz(
        secim.map((s) => kartlar.get(s)).filter((b): b is BinaKart => Boolean(b)),
        baslangic,
      ),
    [secim, kartlar, baslangic],
  );
  const toplamFirsat = secilenKartlar.reduce((t, b) => t + (b.firsat || 0), 0);
  const toplamMesafe = secilenKartlar.reduce((t, b) => t + (b.mesafe_m || 0), 0);

  /* ---------------- Seçim yolları ---------------- */

  const algoritmaSecsin = useCallback(() => {
    if (!havuz) return;
    const secilen = algoritmaSecimi(havuz, adet, bugun, baslangic);
    setSecim(secilen.map((b) => b.bina_serial));
    setYol('algoritma');
    setMahalle('');
    setOdak(`secim-${Date.now()}`);
    goster(`Algoritma ${secilen.length} bina seçti. İstemediğinizi listeden çıkarabilirsiniz.`, 'bilgi');
  }, [havuz, adet, bugun, baslangic, goster]);

  const mahalleSecildi = (ad: string) => {
    setMahalle(ad);
    setYol('mahalle');
    if (!havuz || !ad) {
      setSecim([]);
      return;
    }
    const secilen = algoritmaSecimi(
      havuz.filter((b) => b.mahalle === ad),
      adet,
      bugun,
      baslangic,
    );
    setSecim(secilen.map((b) => b.bina_serial));
    setOdak(`secim-${Date.now()}`);
    goster(`${ad}: ${secilen.length} bina seçildi.`, 'bilgi');
  };

  const haritadanSecildi = (seriler: string[]) => {
    const uygunlar: string[] = [];
    let elenen = 0;
    for (const s of seriler) {
      const kart = kartlar.get(s);
      if (!kart) continue;
      if (uygunMu(kart, bugun)) uygunlar.push(s);
      else elenen++;
    }
    if (!uygunlar.length) {
      goster(
        elenen
          ? `Çizdiğiniz alandaki ${elenen} binanın hepsi yakın zamanda gezilmiş.`
          : 'Çizdiğiniz alanda bina yok.',
        'uyari',
      );
      return;
    }
    const sirali = uygunlar
      .map((s) => kartlar.get(s) as BinaKart)
      .sort(
        (a, b) =>
          oncelikPuani(b, bugun) - oncelikPuani(a, bugun) ||
          a.bina_serial.localeCompare(b.bina_serial),
      )
      .slice(0, EN_FAZLA);
    setSecim(sirali.map((b) => b.bina_serial));
    goster(
      elenen
        ? `${sirali.length} bina seçildi · ${elenen} bina yakında gezildiği için alınmadı.`
        : `${sirali.length} bina seçildi.`,
      'basari',
    );
  };

  const cikar = (serial: string) => setSecim((o) => o.filter((s) => s !== serial));

  /* ---------------- Gönder ---------------- */

  const gonder = async () => {
    if (!kullanici || !secim.length) return;
    setGonderiliyor(true);
    try {
      const yanit = await gorevAta({
        kullanici_id: kullanici.id,
        tarih,
        bina_serial: secim.slice(0, EN_FAZLA),
        adet: Math.min(secim.length, EN_FAZLA),
        notu: notu.trim() || undefined,
      });
      setSonuc({ ad: yanit.kullanici.ad, adet: yanit.eklenen, tarih: yanit.tarih });
      setSecim([]);
      setNotu('');
      // Canlı durum ve sol menüdeki uyarı sayacı hemen doğruyu göstersin.
      gunTazele();
      if (bolge) void havuzuGetir(bolge);
    } catch (h) {
      goster(h instanceof Error ? h.message : 'Görev gönderilemedi.', 'uyari');
    } finally {
      setGonderiliyor(false);
    }
  };

  const gunOzetleri = useMemo(() => {
    const m = new Map<number, SatisciGunu>();
    (gun?.satiscilar ?? []).forEach((s) => m.set(s.kullanici_id, s));
    return m;
  }, [gun]);

  if (sonuc) {
    return (
      <>
        <YonUst baslik="Görev atama" />
        <Icerik>
          <Kart>
            <BosDurumKutusu
              simge="📦"
              baslik={`${sonuc.ad} kişisine ${sayi(sonuc.adet)} bina düştü`}
              aciklama={`${
                sonuc.tarih === bugunMetni() ? 'Bugünün' : 'Yarının'
              } listesi telefonunda hazır. Sonuçları işledikçe canlı durumda göreceksiniz.`}
            >
              <div className="yon-satir" style={{ justifyContent: 'center' }}>
                <button className="yd birincil buyuk" onClick={() => bolumeGit('canli')}>
                  Canlı duruma dön
                </button>
                <button className="yd buyuk" onClick={() => setSonuc(null)}>
                  Bir atama daha yap
                </button>
              </div>
            </BosDurumKutusu>
          </Kart>
        </Icerik>
      </>
    );
  }

  return (
    <>
      <YonUst
        baslik="Görev atama"
        altYazi="Satışçıyı seç, binaları seç, gönder. Liste anında telefonunda belirir."
      />

      <Icerik>
        {/* ---------- 1. Kime ---------- */}
        <Kart>
          <Adim no={1} baslik="Kime gidecek?" alt="Satışçı seçin; kendi bölgesi haritada açılır." />
          {ekipListesi.length ? (
            <div className="kisi-izgara">
              {ekipListesi.map((k) => (
                <KisiSecim
                  key={k.id}
                  k={k}
                  gunu={gunOzetleri.get(k.id)}
                  secili={k.id === kullaniciId}
                  sec={() => setKullaniciId(k.id)}
                />
              ))}
            </div>
          ) : (
            <BosDurumKutusu
              simge="👥"
              baslik="Önce ekip kurulmalı"
              aciklama="Ekip bölümünden satışçı ekleyin."
            />
          )}
        </Kart>

        {kullanici && !bolge ? (
          /* Bölge planı küçülünce bölgesi kalmayan satışçı (bolge = 0): hiçbir binaya
             gidemez, havuz boş gelir. Boş haritada beklemek yerine ne yapılacağı söylenir. */
          <Kart>
            <BosDurumKutusu
              simge="🧭"
              baslik={`${kullanici.ad} şu an bölgesiz`}
              aciklama="Bölge planı değişince bölgesi kalmadı. Önce Ekip ekranından bir bölge verin; sonra buradan liste gönderebilirsiniz."
            >
              <button className="yd birincil" onClick={() => bolumeGit('ekip')}>
                Ekip ekranına git
              </button>
            </BosDurumKutusu>
          </Kart>
        ) : kullanici ? (
          <>
            {/* ---------- 2. Hangi binalar ---------- */}
            <Kart>
              <Adim
                no={2}
                baslik="Hangi binalar?"
                alt={`${kullanici.ad} · ${bolge}. bölge${
                  havuz ? ` · ${sayi(havuz.length)} bina` : ''
                }`}
              />

              {havuzHatasi ? (
                <HataKutusu mesaj={havuzHatasi} yenile={() => bolge && havuzuGetir(bolge)} />
              ) : null}

              <div className="yol-secim" style={{ marginBottom: 16 }}>
                <button
                  className={`yol-kart${yol === 'algoritma' ? ' secili' : ''}`}
                  onClick={algoritmaSecsin}
                  disabled={!havuz}
                >
                  <span className="baslik">
                    <Kivilcim boyut={20} />
                    Algoritma seçsin
                  </span>
                  <span className="aciklama">
                    En yüksek potansiyelli {adet} binayı bulur: yeni açılan siteler, boş kapısı çok
                    olan binalar, sözü olan adresler öne gelir.
                  </span>
                </button>

                <div className={`yol-kart${yol === 'mahalle' ? ' secili' : ''}`}>
                  <span className="baslik">Mahalleden seç</span>
                  <span className="aciklama">Bir mahalleyi baştan sona tarayın.</span>
                  <select
                    className="yon-alan"
                    style={{ marginTop: 8 }}
                    value={mahalle}
                    onChange={(o) => mahalleSecildi(o.target.value)}
                    disabled={!havuz}
                    aria-label="Mahalle"
                  >
                    <option value="">Mahalle seçin…</option>
                    {mahalleler.map(([ad, kac]) => (
                      <option key={ad} value={ad}>
                        {ad} ({kac})
                      </option>
                    ))}
                  </select>
                </div>

                <button
                  className={`yol-kart${yol === 'harita' ? ' secili' : ''}`}
                  onClick={() => setYol('harita')}
                  disabled={!havuz}
                >
                  <span className="baslik">
                    <Cerceve boyut={20} />
                    Haritadan çiz
                  </span>
                  <span className="aciklama">
                    Haritada bir alanın üstüne dikdörtgen çizin; içindeki uygun binalar seçilir.
                  </span>
                </button>
              </div>

              <div className="yon-ikili">
                <div>
                  {havuzYukleniyor && !havuz ? (
                    <Iskelet yukseklik={420} />
                  ) : (
                    <HaritaTuval
                      noktalar={noktalar}
                      yukseklik={420}
                      secimKipi={yol === 'harita'}
                      secimBitti={haritadanSecildi}
                      vurgulanan={secimKumesi}
                      sigdirmaAnahtari={`${bolge}-${noktalar.length}`}
                      odakAnahtari={odak}
                      odakNoktalari={odak.startsWith('secim') ? secilenNoktalar : noktalar}
                      araclar={
                        <>
                          {yol === 'harita' ? (
                            <span className="durum-pil mavi">
                              <Cerceve boyut={14} /> Haritada dikdörtgen çizin
                            </span>
                          ) : null}
                          {secim.length ? (
                            <button
                              className="yd"
                              onClick={() => setOdak(`secim-${Date.now()}`)}
                              title="Görünümü seçili binalara sığdır"
                            >
                              Seçime yakınlaş
                            </button>
                          ) : null}
                          <button
                            className="yd"
                            onClick={() => setOdak(`bolge-${Date.now()}`)}
                            title="Görünümü bütün bölgeye sığdır"
                          >
                            Bölgeyi göster
                          </button>
                        </>
                      }
                    />
                  )}
                </div>

                <SecimListesi
                  binalar={secilenKartlar}
                  cikar={cikar}
                  temizle={() => setSecim([])}
                  toplamFirsat={toplamFirsat}
                  toplamMesafe={toplamMesafe}
                  bugun={bugun}
                />
              </div>
            </Kart>

            {/* ---------- 3. Ne zaman ---------- */}
            <Kart>
              <Adim no={3} baslik="Ne zaman?" alt="Liste bu tarihte telefonunda görünür." />
              <div className="yon-satir" style={{ gap: 18, alignItems: 'flex-end' }}>
                <div>
                  <span className="yon-etiket">Tarih</span>
                  <div className="yon-segment">
                    <button
                      className={tarih === bugunMetni() ? 'secili' : undefined}
                      onClick={() => setTarih(bugunMetni())}
                    >
                      Bugün
                    </button>
                    <button
                      className={tarih === gunEkle(bugunMetni(), 1) ? 'secili' : undefined}
                      onClick={() => setTarih(gunEkle(bugunMetni(), 1))}
                    >
                      Yarın
                    </button>
                  </div>
                </div>

                <div>
                  <span className="yon-etiket">Kaç bina (algoritma/mahalle seçiminde)</span>
                  <div className="yon-satir" style={{ gap: 6 }}>
                    {[15, 25, 40].map((d) => (
                      <button
                        key={d}
                        className={`yd${adet === d ? ' birincil' : ''}`}
                        onClick={() => setAdet(d)}
                      >
                        {d}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="yon-buyu" style={{ minWidth: 220 }}>
                  <span className="yon-etiket">Not (isteğe bağlı)</span>
                  <input
                    className="yon-alan"
                    value={notu}
                    maxLength={120}
                    placeholder="Örn. Önce site yönetimiyle görüş"
                    onChange={(o) => setNotu(o.target.value)}
                  />
                </div>
              </div>
            </Kart>

            {/* ---------- Gönder ---------- */}
            {/* Tarih burada da duruyor: yönetici göndermeden hemen önce
                "bugün mü yarın mı" sorusunu ekranı kaydırmadan görüp değiştirebilsin. */}
            <div className="gonder-serit">
              <Paket boyut={26} />
              <span className="ozet">
                {secim.length ? (
                  <>
                    <em>{kullanici.ad}</em> kişisine <em>{sayi(secim.length)} bina</em> ·{' '}
                    {sayi(toplamFirsat)} boş kapı
                  </>
                ) : (
                  'Henüz bina seçilmedi — yukarıdan bir yol seçin.'
                )}
              </span>
              <div className="yon-segment" role="group" aria-label="Görev tarihi">
                <button
                  className={tarih === bugunMetni() ? 'secili' : undefined}
                  onClick={() => setTarih(bugunMetni())}
                >
                  Bugün
                </button>
                <button
                  className={tarih === gunEkle(bugunMetni(), 1) ? 'secili' : undefined}
                  onClick={() => setTarih(gunEkle(bugunMetni(), 1))}
                >
                  Yarın
                </button>
              </div>
              <span style={{ marginLeft: 'auto' }}>
                <button
                  className="yd birincil buyuk"
                  onClick={gonder}
                  disabled={!secim.length || gonderiliyor}
                >
                  {gonderiliyor ? 'Gönderiliyor…' : 'Listeyi gönder'}
                </button>
              </span>
            </div>
          </>
        ) : null}
      </Icerik>
    </>
  );
}

/* ------------------------------ Parçalar ------------------------------ */

function Adim({ no, baslik, alt }: { no: number; baslik: string; alt?: string }) {
  return (
    <div className="yon-adim">
      <span className="no">{no}</span>
      <div>
        <h2>{baslik}</h2>
        {alt ? <div className="alt">{alt}</div> : null}
      </div>
    </div>
  );
}

function KisiSecim({
  k,
  gunu,
  secili,
  sec,
}: {
  k: YoneticiKullanici;
  gunu?: SatisciGunu;
  secili: boolean;
  sec: () => void;
}) {
  const listesiVar = Boolean(gunu?.gorev_id);
  return (
    <button className={`kisi-secim${secili ? ' secili' : ''}`} onClick={sec} aria-pressed={secili}>
      <BasHarf ad={k.ad} anahtar={k.id} />
      <span style={{ minWidth: 0, flex: 1 }}>
        <span className="ad" style={{ display: 'block' }} title={k.ad}>
          {k.ad}
        </span>
        <span className="alt" style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          {k.bolge ? `${k.bolge}. bölge` : 'Bölgesiz'}
          <span
            className={`yuk${listesiVar ? '' : ' bos'}`}
            title={listesiVar ? 'Bugün gezilen / listedeki bina' : 'Bugün için listesi yok'}
          >
            {listesiVar
              ? `${gunu?.ziyaret}/${(gunu?.ziyaret ?? 0) + (gunu?.kalan ?? 0)}`
              : 'liste yok'}
          </span>
        </span>
      </span>
      {secili ? <Onay boyut={18} /> : null}
    </button>
  );
}

function SecimListesi({
  binalar,
  cikar,
  temizle,
  toplamFirsat,
  toplamMesafe,
  bugun,
}: {
  binalar: Array<BinaKart & { mesafe_m?: number }>;
  cikar: (serial: string) => void;
  temizle: () => void;
  toplamFirsat: number;
  toplamMesafe: number;
  bugun: Date;
}) {
  if (!binalar.length) {
    return (
      <div className="yon-kart" style={{ background: 'var(--kart-bas)' }}>
        <BosDurumKutusu
          simge="🗺️"
          baslik="Seçilen bina yok"
          aciklama="“Algoritma seçsin” en iyi başlangıçtır; sonra listeden istediğinizi çıkarabilirsiniz."
        />
      </div>
    );
  }

  return (
    <div>
      <div className="yon-satir" style={{ marginBottom: 8 }}>
        <b style={{ fontSize: 15 }}>{sayi(binalar.length)} bina seçildi</b>
        <span className="durum-pil mavi">{sayi(toplamFirsat)} boş kapı</span>
        {toplamMesafe ? (
          <span className="durum-pil" title="Ofisten başlayan yaklaşık tur uzunluğu">
            ~{mesafe(toplamMesafe)}
          </span>
        ) : null}
        <button className="yd duz" style={{ marginLeft: 'auto' }} onClick={temizle}>
          Hepsini çıkar
        </button>
      </div>

      {binalar.length >= EN_FAZLA ? (
        <div className="yon-uyari" style={{ marginBottom: 8 }}>
          <Uyari boyut={18} />
          Bir güne en fazla {EN_FAZLA} bina gönderilebilir.
        </div>
      ) : null}

      {/* Öncelik formülünde mesafe yok: en potansiyelli binalar bölgenin iki
          ucuna dağılmış olabilir. Yönetici bunu göndermeden önce görmeli. */}
      {toplamMesafe > DAGINIK_ESIK_M ? (
        <div className="yon-uyari" style={{ marginBottom: 8 }}>
          <Uyari boyut={18} />
          Bu liste dağınık: turun tamamı ~{mesafe(toplamMesafe)}. Bir günde gezilmesi zor olabilir —
          “Mahalleden seç” ya da “Haritadan çiz” ile daraltın.
        </div>
      ) : null}

      <div className="secim-listesi">
        {binalar.map((b, i) => {
          const neden = uygunsuzlukNedeni(b, bugun);
          return (
            <div className="secim-satir" key={b.bina_serial}>
              <span className="sira">{i + 1}</span>
              <div className="govde">
                <div className="ad" title={b.baslik}>
                  {b.baslik}
                </div>
                <div className="alt">
                  {b.adres}
                  {b.firsat ? ` · ${sayi(b.firsat)} boş kapı` : ''}
                  {b.yeni_site ? ' · yeni site' : ''}
                  {neden ? ` · ${neden}` : ''}
                </div>
              </div>
              <button className="cikar" onClick={() => cikar(b.bina_serial)} aria-label="Listeden çıkar">
                <Kapat boyut={17} />
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
