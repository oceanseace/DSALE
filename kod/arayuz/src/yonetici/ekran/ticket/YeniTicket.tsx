/**
 * Yeni ticket — bugünkü akışın aynısı, tek pencerede:
 *
 *   1. Bina (binadan açıldıysa hazır gelir; yoksa ad / Bina Serial / Location Id ile aranır)
 *   2. Konu + ekip telefonu → ticket metni sunucudan üretilir (kullanıcının
 *      OneDesk'e yazdığı metinle harfi harfine aynı) → "Metni kopyala"
 *   3. OneDesk'te ticket açılır → numarası buraya yazılır → "Kaydet"
 *
 * Aynı binada açık ticket varsa pencere bunu en üstte söyler: aynı sorun için
 * ikinci ticket açılmasın.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { SahaHatasi } from '../../../api/istemci';
import { binaAyrinti, ticketSablonu } from '../../../api/uclar';
import type { BinaAyrintisi, Ticket, TicketKonusu } from '../../../api/tipler';
import { Cekmece } from '../../../ortak/Cekmece';
import { useBildirim } from '../../../ortak/Bildirim';
import { DurumCipi } from '../../../ortak/BinaNotlari';
import { ekipTelefonunuKaydet, kayitliEkipTelefonu, kopyala, ticketMetni } from '../../../ortak/kimlik';
import { KONU_TURU, TICKET_KONULARI, acikGunMetni } from '../../../ortak/ticketBilgi';
import { Onay, Uyari } from '../../../ortak/Ikon';
import { binalar as binaAra, ticketKategorileri, ticketOlustur, type TicketKategorileri } from '../../api';
import { useYonetim } from '../../depo';
import { useOturum } from '../../../depo/oturum';
import '../faz2.css';

export const BILINEN_KANALLAR = ['DEHA', 'GLOBAL', 'ARIZA', 'TOPTAN'];

interface AramaSonucu {
  serial: string;
  ad: string;
  loc: string;
  bolge: number | null;
}

/** "00113680", "113680", "O25265408" — Location Id'yi sıfırsız ve büyük harfle karşılaştır. */
function kimlikSade(s: string): string {
  return s.toLocaleUpperCase('tr-TR').replace(/\s+/g, '').replace(/^0+(?=\d)/, '');
}

/** Sunucu `zorunlu_alanlar` göndermezse (eski sürüm) gösterilen yedek liste (EK-12.7). */
const YEDEK_ZORUNLU: Array<{ anahtar: string; etiket: string }> = [
  { anahtar: 'musteri_no', etiket: 'Müşteri no ve Hizmet ID' },
  { anahtar: 'seri_no', etiket: 'Seri no (cihaz değiştiyse eski ve yeni)' },
  { anahtar: 'port', etiket: 'SW ip/port ya da OLT ip/port' },
  { anahtar: 'kontroller', etiket: 'Yapılan kontroller' },
  { anahtar: 'aranma_saati', etiket: 'Müşterinin aranmak istediği saat (en geç 22:00)' },
  { anahtar: 'ekran_goruntusu', etiket: 'Tarih-saatli ekran görüntüsü (ek dosya)' },
];

export function YeniTicketPenceresi({
  acik,
  kapat,
  bina,
  kanallar = BILINEN_KANALLAR,
  kaydedildi,
}: {
  acik: boolean;
  kapat: () => void;
  /** Binadan açılınca dolu gelir; boşsa pencere bina sorar. */
  bina?: { bina_serial: string; baslik?: string | null } | null;
  kanallar?: string[];
  kaydedildi?: (t: Ticket) => void;
}) {
  const { goster } = useBildirim();
  const { noktalar, haritayiIste } = useYonetim();
  /*
   * Bina listesi araması (/api/bina) satış ucudur (satis.kendi; spec §2.3). Operasyon onu
   * açamaz ama her bina kartını görür (bina.oku): o yüzden Bina Serial'la birebir bulunur.
   */
  const { izinli } = useOturum();
  const listeArar = izinli('satis.kendi');

  const [serial, setSerial] = useState<string | null>(bina?.bina_serial ?? null);
  const [detay, setDetay] = useState<BinaAyrintisi | null>(null);
  const [detayHata, setDetayHata] = useState<string | null>(null);
  const [konu, setKonu] = useState<TicketKonusu>('SİNYAL');
  const [ekip, setEkip] = useState(kayitliEkipTelefonu);
  const [musteri, setMusteri] = useState('');
  const [kanal, setKanal] = useState('');
  const [aciklama, setAciklama] = useState('');
  const [metin, setMetin] = useState<string | null>(null);
  const [taslak, setTaslak] = useState(false);
  const [metinHata, setMetinHata] = useState<string | null>(null);
  /** Sunucu metni veremedi; aynı şablon burada (`ortak/kimlik.ts`) üretildi. */
  const [yerelMetin, setYerelMetin] = useState(false);
  const [kopyalandi, setKopyalandi] = useState(false);
  const [ticketNo, setTicketNo] = useState('');
  const [kaydediliyor, setKaydediliyor] = useState(false);
  const [hata, setHata] = useState<string | null>(null);

  const [arama, setArama] = useState('');
  const [sunucuSonuc, setSunucuSonuc] = useState<AramaSonucu[] | null>(null);
  const noInput = useRef<HTMLInputElement | null>(null);

  /* EK-5: OneDesk ekibi (varsayılan TEAM-TAS1BRS) + başlık. Liste sunucu ayarından. */
  const [kategoriler, setKategoriler] = useState<TicketKategorileri | null>(null);
  const [onedeskEkip, setOnedeskEkip] = useState('');
  const [kategori, setKategori] = useState('');

  /* Pencere her açılışta temiz başlar. */
  useEffect(() => {
    if (!acik) return;
    setSerial(bina?.bina_serial ?? null);
    setKonu('SİNYAL');
    setMusteri('');
    setKanal('');
    setAciklama('');
    setTicketNo('');
    setKopyalandi(false);
    setHata(null);
    setArama('');
    setEkip(kayitliEkipTelefonu());
    setKategori('');
    if (!bina) haritayiIste();
    let iptal = false;
    ticketKategorileri()
      .then((k) => {
        if (iptal) return;
        setKategoriler(k);
        setOnedeskEkip(k.varsayilan_ekip || k.ekipler[0] || '');
      })
      .catch(() => {
        // Eski sunucu: varsayılan ekip yine önerilir, başlık listesi boş kalır.
        if (!iptal) setOnedeskEkip('TEAM-TAS1BRS');
      });
    return () => {
      iptal = true;
    };
  }, [acik, bina, haritayiIste]);

  /** Başlık seçilince uygun metin şablonu önerilir ("SINYAL YOK" → Sinyal). */
  const kategoriSec = (ad: string) => {
    setKategori(ad);
    const oneri = kategoriler?.kategoriler.find((k) => k.ad === ad)?.konu_onerisi;
    if (oneri && TICKET_KONULARI.some((k) => k.konu === oneri)) setKonu(oneri as TicketKonusu);
  };

  /* Seçilen binanın ayrıntısı: açık ticket uyarısı ve kimlikler için. */
  useEffect(() => {
    if (!acik || !serial) {
      setDetay(null);
      return undefined;
    }
    let iptal = false;
    setDetay(null);
    setDetayHata(null);
    binaAyrinti(serial)
      .then((d) => !iptal && setDetay(d))
      .catch((h) => !iptal && setDetayHata(h instanceof SahaHatasi ? h.message : 'Bina bilgisi alınamadı.'));
    return () => {
      iptal = true;
    };
  }, [acik, serial]);

  /* Ticket metni: tek doğruluk kaynağı sunucu (saha/ticket.py). Sunucu metni
     veremezse (bağlantı koptu) SİNYAL ve EK SP için aynı şablon burada üretilir:
     `ortak/kimlik.ts → ticketMetni()` sunucudakiyle birebir aynıdır (sözleşme §7.4). */
  const detayRef = useRef<BinaAyrintisi | null>(null);
  detayRef.current = detay;
  useEffect(() => {
    if (!acik || !serial) {
      setMetin(null);
      return undefined;
    }
    let iptal = false;
    setKopyalandi(false);
    const sayac = window.setTimeout(() => {
      ticketSablonu(serial, konu, ekip)
        .then((s) => {
          if (iptal) return;
          setMetin(s.metin);
          setTaslak(s.sablon_taslak);
          setYerelMetin(false);
          setMetinHata(null);
        })
        .catch((h) => {
          if (iptal) return;
          const tur = KONU_TURU[konu];
          const b = detayRef.current?.bina;
          if (tur && b && b.bina_serial === serial) {
            setMetin(ticketMetni(b, tur, ekip));
            setTaslak(konu !== 'SİNYAL');
            setYerelMetin(true);
            setMetinHata(null);
            return;
          }
          setMetin(null);
          setMetinHata(h instanceof SahaHatasi ? h.message : 'Ticket metni üretilemedi.');
        });
    }, 250);
    return () => {
      iptal = true;
      window.clearTimeout(sayac);
    };
  }, [acik, serial, konu, ekip]);

  /* Bina arama: harita verisi indiyse ekranda (Location Id dahil), yoksa sunucuda. */
  const yerelSonuc = useMemo<AramaSonucu[] | null>(() => {
    const q = arama.trim();
    if (q.length < 2 || !noktalar) return null;
    const kucuk = q.toLocaleLowerCase('tr-TR');
    const sade = kimlikSade(q);
    const bulunan: Array<AramaSonucu & { puan: number }> = [];
    for (const n of noktalar) {
      const ad = (n.ad || '').toLocaleLowerCase('tr-TR');
      const loc = n.loc ? kimlikSade(n.loc) : '';
      const ser = n.serial.toLocaleUpperCase('tr-TR');
      let puan = 0;
      if (loc && loc === sade) puan = 100;
      else if (ser === q.toLocaleUpperCase('tr-TR')) puan = 90;
      else if (loc && sade.length >= 4 && loc.includes(sade)) puan = 50;
      else if (ser.includes(q.toLocaleUpperCase('tr-TR'))) puan = 40;
      else if (ad.includes(kucuk)) puan = ad.startsWith(kucuk) ? 30 : 20;
      if (puan) bulunan.push({ serial: n.serial, ad: n.ad || n.serial, loc: n.loc || '', bolge: n.bolge, puan });
    }
    return bulunan.sort((a, b) => b.puan - a.puan || a.ad.localeCompare(b.ad, 'tr')).slice(0, 8);
  }, [arama, noktalar]);

  useEffect(() => {
    const q = arama.trim();
    if (q.length < 2 || noktalar) {
      setSunucuSonuc(null);
      return undefined;
    }
    let iptal = false;
    const sayac = window.setTimeout(() => {
      if (!listeArar) {
        binaAyrinti(q.toLocaleUpperCase('tr-TR').replace(/\s+/g, ''))
          .then((d) => {
            if (iptal) return;
            const b = d.bina;
            setSunucuSonuc([
              { serial: b.bina_serial, ad: b.baslik || b.ad || b.bina_serial, loc: b.kimlik?.location_id ?? '', bolge: b.bolge ?? null },
            ]);
          })
          .catch(() => !iptal && setSunucuSonuc([]));
        return;
      }
      binaAra({ q, limit: 8 })
        .then((y) => {
          if (iptal) return;
          setSunucuSonuc(
            y.binalar.map((b) => ({ serial: b.bina_serial, ad: b.baslik, loc: '', bolge: b.bolge })),
          );
        })
        .catch(() => !iptal && setSunucuSonuc([]));
    }, 300);
    return () => {
      iptal = true;
      window.clearTimeout(sayac);
    };
  }, [arama, noktalar, listeArar]);

  const sonuclar = yerelSonuc ?? sunucuSonuc;
  const b = detay?.bina;
  const acikTicketlar = (detay?.ticketlar ?? []).filter((t) => t.acik);
  const ayniKonuAcik = acikTicketlar.some((t) => t.konu === konu);

  const metniKopyala = async () => {
    if (!metin) return;
    ekipTelefonunuKaydet(ekip);
    const ok = await kopyala(metin);
    setKopyalandi(ok);
    if (!ok) goster('Kopyalanamadı. Metni seçip Ctrl+C ile kopyalayın.', 'uyari');
    else window.setTimeout(() => noInput.current?.focus(), 50);
  };

  const kaydet = async () => {
    if (!serial) return;
    setKaydediliyor(true);
    setHata(null);
    try {
      ekipTelefonunuKaydet(ekip);
      const y = await ticketOlustur({
        konu,
        bina_serial: serial,
        ticket_no: ticketNo.trim() || null,
        musteri: musteri.trim() || null,
        kanal: kanal.trim() || null,
        detay: aciklama.trim() || null,
        ekip: ekip.trim() || null,
        metin: metin ?? null,
        onedesk_ekip: onedeskEkip || null,
        kategori: kategori || null,
      });
      goster(
        ticketNo.trim() ? `Ticket ${ticketNo.trim()} kaydedildi.` : 'Ticket kaydedildi — OneDesk numarasını sonra ekleyin.',
        'basari',
      );
      kaydedildi?.(y.ticket);
      kapat();
    } catch (h) {
      setHata(h instanceof SahaHatasi ? h.message : 'Ticket kaydedilemedi.');
    } finally {
      setKaydediliyor(false);
    }
  };

  return (
    <Cekmece
      acik={acik}
      kapat={kapat}
      kilitli={kaydediliyor}
      baslik="Yeni ticket"
      altBaslik="Metni kopyalayın, OneDesk'te ticket'ı açın, numarasını buraya yazın."
    >
      <div className="tk-yeni">
        {/* ---------------- 1. Bina ---------------- */}
        {!serial ? (
          <div className="tk-alan">
            <span className="yon-etiket">Hangi bina?</span>
            <input
              className="yon-alan"
              autoFocus
              value={arama}
              placeholder={listeArar ? 'Bina adı, Bina Serial ya da Location Id' : 'Bina Serial (bina kartındaki kimlik)'}
              onChange={(e) => setArama(e.target.value)}
            />
            {sonuclar ? (
              sonuclar.length ? (
                <ul className="tk-arama">
                  {sonuclar.map((s) => (
                    <li key={s.serial}>
                      <button type="button" onClick={() => setSerial(s.serial)}>
                        <b>{s.ad}</b>
                        <span>
                          {s.serial}
                          {s.loc ? ` · Location Id ${s.loc}` : ''}
                          {s.bolge ? ` · ${s.bolge}. bölge` : ''}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="tk-ipucu">
                  {listeArar
                    ? 'Bu aramayla bina bulunamadı.'
                    : 'Bu Bina Serial ile bina bulunamadı. Ticket’ı işin ya da binanın kartından da açabilirsiniz.'}
                </p>
              )
            ) : (
              <p className="tk-ipucu">
                {listeArar
                  ? 'En az iki harf yazın. Location Id sıfırlı ya da sıfırsız yazılabilir.'
                  : 'Bina Serial’ı tam yazın; ticket’ı işin ya da binanın kartından açmak daha kolaydır.'}
              </p>
            )}
          </div>
        ) : (
          <div className="tk-bina">
            <div style={{ minWidth: 0 }}>
              <b>{b?.baslik || b?.ad || bina?.baslik || serial}</b>
              <span>
                {serial}
                {b?.kimlik?.location_id ? ` · Location Id ${b.kimlik.location_id}` : ''}
                {b?.bolge ? ` · ${b.bolge}. bölge` : ''}
              </span>
            </div>
            {!bina ? (
              <button type="button" className="yd duz" onClick={() => setSerial(null)}>
                Değiştir
              </button>
            ) : null}
          </div>
        )}
        {detayHata ? <div className="yon-uyari kirmizi">{detayHata}</div> : null}

        {acikTicketlar.length ? (
          <div className={`tk-acik-uyari${ayniKonuAcik ? ' guclu' : ''}`}>
            <Uyari boyut={17} />
            <div>
              <b>
                {ayniKonuAcik
                  ? 'Bu binada aynı konuda açık ticket var — ikincisini açmayın.'
                  : 'Bu binada açık ticket var.'}
              </b>
              {acikTicketlar.slice(0, 3).map((t) => (
                <div key={t.id} className="tk-acik-satir">
                  <DurumCipi durum={t.durum} kucuk /> {t.konu_etiket}
                  {t.ticket_no ? ` · No ${t.ticket_no}` : ''}
                  {acikGunMetni(t.acik_gun) ? ` · ${acikGunMetni(t.acik_gun)}` : ''}
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {serial ? (
          <>
            {/* ---------------- OneDesk ekibi + başlık (EK-5) ---------------- */}
            <div className="tk-iki">
              <label className="tk-alan">
                <span className="yon-etiket">OneDesk ekibi</span>
                <select className="yon-alan" value={onedeskEkip} onChange={(e) => setOnedeskEkip(e.target.value)}>
                  {(kategoriler?.ekipler ?? ['TEAM-TAS1BRS']).map((e) => (
                    <option key={e} value={e}>
                      {e}
                    </option>
                  ))}
                </select>
              </label>
              <label className="tk-alan">
                <span className="yon-etiket">Başlık</span>
                <select
                  className="yon-alan"
                  value={kategori}
                  onChange={(e) => kategoriSec(e.target.value)}
                  disabled={!kategoriler?.kategoriler.length}
                >
                  <option value="">{kategoriler?.kategoriler.length ? 'Seçin…' : 'Liste yüklenemedi'}</option>
                  {(kategoriler?.kategoriler ?? []).map((k) => (
                    <option key={k.ad} value={k.ad}>
                      {k.ad}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            {/* ---------------- 2. Konu + metin ---------------- */}
            <div className="tk-alan">
              <span className="yon-etiket">Konu</span>
              <div className="tk-konular" role="radiogroup" aria-label="Konu">
                {TICKET_KONULARI.map((k) => (
                  <button
                    key={k.konu}
                    type="button"
                    role="radio"
                    aria-checked={konu === k.konu}
                    className={konu === k.konu ? 'secili' : undefined}
                    onClick={() => setKonu(k.konu)}
                  >
                    {k.etiket}
                  </button>
                ))}
              </div>
            </div>

            <div className="tk-iki">
              <label className="tk-alan">
                <span className="yon-etiket">Ekip telefonu (metnin sonuna yazılır)</span>
                <input
                  className="yon-alan"
                  inputMode="tel"
                  value={ekip}
                  placeholder="+90 5xx xxx xx xx"
                  onChange={(e) => setEkip(e.target.value)}
                />
              </label>
              <label className="tk-alan">
                <span className="yon-etiket">Müşteri / abone no (isteğe bağlı)</span>
                <input className="yon-alan" value={musteri} onChange={(e) => setMusteri(e.target.value)} />
              </label>
              <label className="tk-alan">
                <span className="yon-etiket">Kanal (isteğe bağlı)</span>
                <input
                  className="yon-alan"
                  list="tk-kanallar"
                  value={kanal}
                  placeholder="DEHA, GLOBAL, ARIZA…"
                  onChange={(e) => setKanal(e.target.value.toLocaleUpperCase('tr-TR'))}
                />
                <datalist id="tk-kanallar">
                  {kanallar.map((k) => (
                    <option key={k} value={k} />
                  ))}
                </datalist>
              </label>
              <label className="tk-alan">
                <span className="yon-etiket">Not (isteğe bağlı)</span>
                <input
                  className="yon-alan"
                  value={aciklama}
                  placeholder="Örn. WhatsApp'tan 3 görsel geldi"
                  onChange={(e) => setAciklama(e.target.value)}
                />
              </label>
            </div>

            <div className="tk-metin-kutu">
              <div className="tk-metin-bas">
                <span className="tk-adim-no">1</span>
                <b>Ticket metni</b>
                {taslak ? <span className="bp-rozet amber">taslak metin</span> : null}
              </div>
              {metinHata ? (
                <div className="yon-uyari kirmizi">{metinHata}</div>
              ) : (
                <pre className="tk-metin" aria-label="Ticket metni">
                  {metin ?? 'Metin hazırlanıyor…'}
                </pre>
              )}
              {yerelMetin ? (
                <p className="tk-ipucu">Sunucuya ulaşılamadı: metin bu bilgisayarda aynı şablonla üretildi.</p>
              ) : null}
              {taslak ? (
                <p className="tk-ipucu">
                  Bu konunun giriş cümlesi taslak; gerçek bir örnek metin gelince güncellenecek. Kimlik alanları doğru.
                </p>
              ) : null}
              <button
                type="button"
                className={`yd buyuk genis${kopyalandi ? ' yesil' : ' birincil'}`}
                onClick={metniKopyala}
                disabled={!metin}
              >
                {kopyalandi ? (
                  <>
                    <Onay boyut={18} /> Kopyalandı — OneDesk'e yapıştırın
                  </>
                ) : (
                  'Metni kopyala'
                )}
              </button>
              {kopyalandi ? (
                <p className="tk-ipucu">WhatsApp'tan gelen görselleri ekleyip ticket'ı OneDesk'te açın.</p>
              ) : null}
              {/* EK-12.7: BÇO'nun geri çevirmediği ticket'ta bulunması gerekenler.
                  Liste ayardan gelir (`ticket_zorunlu_alanlar`); eski sunucuda yedek liste. */}
              <details className="tk-kontrol">
                <summary>OneDesk'te eksiksiz olsun</summary>
                <ul>
                  {(kategoriler?.zorunlu_alanlar?.length ? kategoriler.zorunlu_alanlar : YEDEK_ZORUNLU).map((z) => (
                    <li key={z.anahtar}>{z.etiket}</li>
                  ))}
                </ul>
              </details>
            </div>

            {/* ---------------- 3. Numara + kaydet ---------------- */}
            <div className="tk-metin-kutu">
              <div className="tk-metin-bas">
                <span className="tk-adim-no">2</span>
                <b>OneDesk ticket numarası</b>
              </div>
              <input
                ref={noInput}
                className="yon-alan tk-no"
                inputMode="numeric"
                value={ticketNo}
                placeholder="Örn. 10133762171"
                onChange={(e) => setTicketNo(e.target.value.replace(/[^\dA-Za-z-]/g, ''))}
                onKeyDown={(e) => e.key === 'Enter' && !kaydediliyor && void kaydet()}
              />
              {!ticketNo.trim() ? (
                <p className="tk-ipucu">Numara henüz yoksa boş bırakıp kaydedin; defterde "numara yok" olarak durur.</p>
              ) : null}
            </div>

            {hata ? (
              <div className="yon-uyari kirmizi">
                <Uyari boyut={18} />
                {hata}
              </div>
            ) : null}

            <div className="bp-onay-dugmeler">
              <button className="yd" onClick={kapat} disabled={kaydediliyor}>
                Vazgeç
              </button>
              {/* Tek birincil eylem: metin kopyalanana kadar "Metni kopyala", sonra "Kaydet". */}
              <button
                className={`yd buyuk${kopyalandi || ticketNo.trim() ? ' birincil' : ''}`}
                onClick={() => void kaydet()}
                disabled={kaydediliyor || !metin}
              >
                {kaydediliyor
                  ? 'Kaydediliyor…'
                  : ayniKonuAcik
                    ? 'Yine de kaydet'
                    : ticketNo.trim()
                      ? 'Kaydet'
                      : 'Numarasız kaydet'}
              </button>
            </div>
          </>
        ) : null}
      </div>
    </Cekmece>
  );
}
