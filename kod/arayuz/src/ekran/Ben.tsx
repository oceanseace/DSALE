/**
 * Ben — satışçının kendi karnesi.
 * Bugün kaç bina, kaç satış, dönüşüm kaç; bölgede ne kadar kaldı.
 * Rakamlar büyük, cümleler kısa.
 */

import { useCallback, useEffect, useState } from 'react';
import { useBildirim } from '../ortak/Bildirim';
import { useOturum } from '../depo/oturum';
import { useSenkron } from '../depo/senkron';
import { useBugun } from '../depo/bugun';
import { DemoSeridi, DurumSeridi } from '../ortak/DurumSeridi';
import { Sayfa, SayfaGovde, Ust } from '../ortak/Sayfa';
import { Cekmece } from '../ortak/Cekmece';
import { Cikis } from '../ortak/Ikon';
import { sayi, telefonBicimle, yuzde } from '../ortak/bicim';
import { SAGLAYICI_ADLARI, kayitliSaglayici, saglayiciyiUnut } from '../ortak/yolTarifi';
import { saglik } from '../api/uclar';
import { Telefon } from '../ortak/Ikon';

export function Ben() {
  const { kullanici, ozet, ozetiTazele, cikisYap } = useOturum();
  const { goster } = useBildirim();
  const { gorev } = useBugun();
  const { bekleyen } = useSenkron();
  const [cikisSoruluyor, setCikisSoruluyor] = useState(false);

  useEffect(() => {
    void ozetiTazele();
  }, [ozetiTazele]);

  const bugun = ozet?.bugun;
  const ziyaret = bugun?.tamam ?? 0;
  const satis = bugun?.satis ?? 0;
  const satisBina = bugun?.satis_bina ?? 0;
  const toplam = bugun?.toplam ?? gorev?.binalar.length ?? 0;
  const kalan = Math.max(0, toplam - ziyaret);
  // DÖNÜŞÜM TEK TANIM: satışla biten bina / gezilen bina. Sunucu hesaplar,
  // istemci kendi bölmesini yapmaz. Eskiden bu ekran "abonelik/bina" diyordu
  // (yüzde 100'ü aşabiliyordu), yönetici ekranı "satış/ziyaret" diyordu; aynı
  // gün için iki farklı sayı çıkıyordu.
  const donusum = bugun?.donusum ?? (ziyaret > 0 ? satisBina / ziyaret : 0);
  const [haritaSaglayici, setHaritaSaglayici] = useState(() => kayitliSaglayici());
  const [yardim, setYardim] = useState<{ telefon?: string | null; ad?: string | null } | null>(null);

  useEffect(() => {
    let iptal = false;
    void saglik()
      .then((veri) => {
        if (!iptal && veri?.yardim_telefon) {
          setYardim({ telefon: veri.yardim_telefon, ad: veri.yardim_ad });
        }
      })
      .catch(() => undefined);
    return () => {
      iptal = true;
    };
  }, []);

  const hafta = ozet?.hafta;
  const bolge = ozet?.bolge;
  const bolgeOran = bolge && bolge.toplam > 0 ? bolge.dokunulan / bolge.toplam : null;

  const cikisOnayla = useCallback(() => {
    if (bekleyen > 0) return;
    saglayiciyiUnut();
    cikisYap();
  }, [bekleyen, cikisYap]);

  return (
    <Sayfa>
      <Ust baslik="Ben" altYazi={kullanici?.bolge_adi ?? null} />
      <SayfaGovde>
        <DemoSeridi />
        <DurumSeridi basariGoster />

        <div className="kart" style={{ marginTop: 14 }}>
          <div className="kart-ic" style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <span
              className="marka-isaret avatar"
              style={{ width: 52, height: 52, borderRadius: 16, fontSize: 22, flex: '0 0 auto' }}
              aria-hidden="true"
            >
              {(kullanici?.ad ?? '?').slice(0, 1).toUpperCase()}
            </span>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 19, fontWeight: 600, letterSpacing: '-0.02em' }}>
                {kullanici?.ad ?? '—'}
              </div>
              <div style={{ color: 'var(--metin-2)', fontSize: 15 }}>
                {kullanici?.telefon ? `0${telefonBicimle(kullanici.telefon)}` : ''}
                {kullanici?.bolge ? ` · ${kullanici.bolge}. bölge` : ''}
              </div>
            </div>
          </div>
        </div>

        <h2 className="bolum-baslik">Bugün</h2>
        <div className="bilgi-izgara">
          <div className="bilgi">
            <div className="etiket">Gezilen bina</div>
            <div className="deger">{sayi(ziyaret)}</div>
          </div>
          <div className="bilgi yesil-vurgu">
            <div className="etiket">Satılan abonelik</div>
            <div className="deger">{sayi(satis)}</div>
          </div>
          <div className="bilgi">
            <div className="etiket">Dönüşüm</div>
            <div className="deger">{ziyaret ? yuzde(donusum) : '—'}</div>
            {/* Payı da yaz: yanında "2 abonelik" dururken çıplak bir %17
                satışçıya yanlış hesap yaptırıyor (2/6 sanıyor). */}
            {ziyaret ? (
              <div className="alt-not">
                {sayi(satisBina)} / {sayi(ziyaret)} binada satış
              </div>
            ) : null}
          </div>
          <div className="bilgi">
            <div className="etiket">Listede kalan</div>
            <div className="deger">{sayi(kalan)}</div>
          </div>
        </div>

        {hafta ? (
          <>
            <h2 className="bolum-baslik">Bu hafta</h2>
            <div className="kart">
              <div className="satir">
                <span className="ad">Gezilen bina</span>
                <span className="deger">{sayi(hafta.ziyaret)}</span>
              </div>
              <div className="satir">
                <span className="ad">Satış yapılan bina</span>
                <span className="deger" style={{ color: 'var(--yesil)' }}>
                  {sayi(hafta.satis)}
                </span>
              </div>
              <div className="satir">
                <span className="ad">Satılan abonelik</span>
                <span className="deger" style={{ color: 'var(--yesil)' }}>
                  {sayi(hafta.satis_adedi ?? hafta.satis)}
                </span>
              </div>
              <div className="satir">
                <span className="ad">Randevu</span>
                <span className="deger">{sayi(hafta.randevu)}</span>
              </div>
              <div className="satir">
                <span className="ad">Dönüşüm</span>
                <span className="deger">
                  {hafta.ziyaret ? yuzde(hafta.donusum ?? hafta.satis / hafta.ziyaret) : '—'}
                </span>
              </div>
            </div>
          </>
        ) : null}

        {bolge && bolgeOran != null ? (
          <>
            <h2 className="bolum-baslik">Bölgem</h2>
            <div className="kart">
              <div
                className="kart-ic"
                style={{ display: 'flex', alignItems: 'center', gap: 18 }}
              >
                <Halka oran={bolgeOran} />
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 17, fontWeight: 600, marginBottom: 4 }}>
                    {sayi(bolge.dokunulan)} / {sayi(bolge.toplam)} bina
                  </div>
                  <div style={{ color: 'var(--metin-2)', fontSize: 15 }}>
                    {sayi(bolge.kalan)} binaya henüz gidilmedi
                    {bolge.kalan_firsat ? ` · ${sayi(bolge.kalan_firsat)} boş kapı` : ''}
                  </div>
                </div>
              </div>
            </div>
          </>
        ) : null}

        <h2 className="bolum-baslik">Ayarlar</h2>
        <div className="kart">
          <div className="satir">
            <span className="ad">Harita uygulaması</span>
            <span className="deger">
              {haritaSaglayici ? SAGLAYICI_ADLARI[haritaSaglayici] : 'Her seferinde sor'}
            </span>
          </div>
          {haritaSaglayici ? (
            <button
              className="satir"
              onClick={() => {
                saglayiciyiUnut();
                setHaritaSaglayici(null);
                goster('Bir dahaki yol tarifinde hangi harita olduğu sorulacak', 'bilgi');
              }}
            >
              <span className="ad" style={{ color: 'var(--birincil-yazi)' }}>
                Değiştir
              </span>
            </button>
          ) : null}
          {yardim?.telefon ? (
            <a className="satir" href={`tel:0${yardim.telefon}`}>
              <span className="ad">
                <Telefon boyut={17} /> {yardim.ad ? `${yardim.ad}'ı ara` : 'Yöneticini ara'}
              </span>
              <span className="deger">0{telefonBicimle(yardim.telefon)}</span>
            </a>
          ) : null}
        </div>

        <button
          className="dugme ikincil"
          style={{ marginTop: 26 }}
          onClick={() => setCikisSoruluyor(true)}
        >
          <Cikis boyut={20} />
          Çıkış yap
        </button>

        <p style={{ textAlign: 'center', color: 'var(--metin-2)', fontSize: 13, marginTop: 18 }}>
          Dehanet Ev Çözüm Merkezi · Saha Sistemi
        </p>
      </SayfaGovde>

      <Cekmece
        acik={cikisSoruluyor}
        kapat={() => setCikisSoruluyor(false)}
        baslik="Çıkış yapılsın mı?"
        altBaslik={
          bekleyen > 0
            ? `Önce ${sayi(bekleyen)} kaydın gönderilmesi gerekiyor.`
            : 'Tekrar girmek için telefon ve PIN gerekecek.'
        }
      >
        <div style={{ display: 'grid', gap: 10 }}>
          <button className="dugme birincil buyuk" onClick={cikisOnayla} disabled={bekleyen > 0}>
            {bekleyen > 0 ? 'Kayıtlar gönderilmeyi bekliyor' : 'Evet, çıkış yap'}
          </button>
          <button className="dugme sessiz" onClick={() => setCikisSoruluyor(false)}>
            Vazgeç
          </button>
        </div>
      </Cekmece>
    </Sayfa>
  );
}

/** Yüzdelik halka — bölge kapsaması için. */
function Halka({ oran }: { oran: number }) {
  const boyut = 86;
  const kalinlik = 10;
  const yaricap = (boyut - kalinlik) / 2;
  const cevre = 2 * Math.PI * yaricap;
  const dolu = Math.max(0, Math.min(1, oran)) * cevre;

  return (
    <div className="halka" style={{ width: boyut, height: boyut, flex: '0 0 auto' }}>
      <svg width={boyut} height={boyut} aria-hidden="true">
        <circle
          cx={boyut / 2}
          cy={boyut / 2}
          r={yaricap}
          fill="none"
          stroke="var(--gri-yumusak)"
          strokeWidth={kalinlik}
        />
        <circle
          cx={boyut / 2}
          cy={boyut / 2}
          r={yaricap}
          fill="none"
          stroke="var(--yesil)"
          strokeWidth={kalinlik}
          strokeLinecap="round"
          strokeDasharray={`${dolu} ${cevre - dolu}`}
          transform={`rotate(-90 ${boyut / 2} ${boyut / 2})`}
        />
      </svg>
      <span className="yuzde">{yuzde(oran)}</span>
    </div>
  );
}
