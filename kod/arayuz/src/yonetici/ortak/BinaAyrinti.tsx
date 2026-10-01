/**
 * Haritada seçilen binanın ayrıntı penceresi (yönetici).
 *
 * Kartta seri numarası değil bina adı görünür; "Ayrıntılar" bu pencereyi açar:
 * adres, kapasite, son ziyaretler ve bina kimlikleri (Location Id, Tellcordia ID,
 * UAVT). Kimlikler tek dokunuşla kopyalanır — BOSS/OneMap/ticket ekranlarına
 * yapıştırmak için.
 *
 * Faz 2: binanın ticket'ları (sayı + son durum, "Ticket aç"), veri notları
 * (sistemin bu kayıtta bulduğu tutarsızlıklar) ve künye değişiklik geçmişi
 * (tur raporuyla değişen HP/abone, pasife alma, OneMap'ten ekleme).
 */

import { useCallback, useEffect, useState } from 'react';
import { binaAyrinti } from '../../api/uclar';
import type { BinaAyrintisi } from '../../api/tipler';
import { sayi, tarihSaat, yuzde } from '../../ortak/bicim';
import { BinaKimlik } from '../../ortak/BinaKimlik';
import { KaliteNotlari, TicketOzeti } from '../../ortak/BinaNotlari';
import { tarihKisa } from '../../ortak/ticketBilgi';
import { git } from '../../yol/rota';
import { binaDegisimleri } from '../api';
import type { BinaDegisimleri } from '../tipler';
import { YeniTicketPenceresi } from '../ekran/ticket/YeniTicket';

const DURUM_METNI: Record<string, string> = {
  bekliyor: 'Hiç gidilmedi',
  planli: 'Bugünkü listede',
  ziyaret_edildi: 'Dokunuldu',
  tekrar_gel: 'Tekrar gidilecek',
  girilemedi: 'Binaya girilemedi',
  altyapi_sorunu: 'Altyapı sorunu',
};

const DEGISIM_ALANI: Record<string, string> = {
  res_hp: 'RES HP',
  aktif_res: 'Aktif abone',
  firsat: 'Boş kapı',
  toplam_hp: 'Toplam HP',
  soho_hp: 'SOHO HP',
  pasif: 'Durum',
  bolge: 'Bölge',
};

function Deger({ etiket, deger }: { etiket: string; deger: string }) {
  // Uzun kimlik (öbek "BRS-KAYAPA_TOKI2") dar kutuda harf harf kırılmasın: yazı küçülür.
  return (
    <div className="ayr-deger">
      <div className="etiket">{etiket}</div>
      <div className={`deger${deger.length > 12 && !deger.includes(' ') ? ' uzun' : ''}`}>{deger}</div>
    </div>
  );
}

export function BinaAyrintiPenceresi({ serial, kapat }: { serial: string; kapat: () => void }) {
  const [veri, setVeri] = useState<BinaAyrintisi | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [ticketAcik, setTicketAcik] = useState(false);
  const [surum, setSurum] = useState(0);

  useEffect(() => {
    let iptal = false;
    if (surum === 0) setVeri(null);
    setHata(null);
    binaAyrinti(serial)
      .then((v) => !iptal && setVeri(v))
      .catch((e) => !iptal && setHata(e?.message || 'Bina bilgisi alınamadı.'));
    return () => {
      iptal = true;
    };
  }, [serial, surum]);

  useEffect(() => {
    // Yeni ticket penceresi açıkken Esc önce onu kapatır (Cekmece kendi dinler).
    const tus = (e: KeyboardEvent) => e.key === 'Escape' && !ticketAcik && kapat();
    window.addEventListener('keydown', tus);
    return () => window.removeEventListener('keydown', tus);
  }, [kapat, ticketAcik]);

  const ticketeGit = useCallback(
    (yol: string) => {
      kapat();
      git(yol);
    },
    [kapat],
  );

  const b = veri?.bina;

  return (
    <div className="ayr-perde" onClick={kapat} role="presentation">
      <div
        className="ayr-pencere"
        role="dialog"
        aria-modal="true"
        aria-label="Bina ayrıntıları"
        onClick={(e) => e.stopPropagation()}
      >
        <button type="button" className="ayr-kapat" onClick={kapat} aria-label="Kapat">
          ×
        </button>

        {hata ? (
          <div className="ayr-hata">{hata}</div>
        ) : !b ? (
          <div className="ayr-yukleniyor">Bina bilgileri getiriliyor…</div>
        ) : (
          <>
            <div className="ayr-baslik">{b.baslik || b.ad || serial}</div>
            <div className="ayr-adres">
              {[b.adres, b.il].filter(Boolean).join(' · ')}
              {b.blok_adi ? ` · Blok ${b.blok_adi}` : ''}
            </div>
            <div className="ayr-rozetler">
              {b.pasif ? (
                <span className="ayr-rozet pasif" title="Son tur raporunda yok: listelere girmez, geçmişi durur">
                  Pasif · son tur raporunda yok
                </span>
              ) : null}
              <span className={`ayr-rozet durum-${b.durum ?? 'bekliyor'}`}>
                {DURUM_METNI[b.durum ?? 'bekliyor'] ?? b.durum_etiket}
              </span>
              {b.bolge ? <span className="ayr-rozet">{b.bolge}. bölge</span> : null}
              {b.yeni_site ? <span className="ayr-rozet yeni">Yeni site</span> : null}
              {b.altyapi ? <span className="ayr-rozet">{b.altyapi}</span> : null}
            </div>

            <div className="ayr-izgara">
              <Deger etiket="Kat / daire" deger={`${b.kat || '–'} kat · ${sayi(b.daire ?? 0)} daire`} />
              <Deger etiket="RES HP" deger={sayi(b.res_hp ?? 0)} />
              <Deger etiket="Aktif abone" deger={sayi(b.aktif_res ?? 0)} />
              <Deger etiket="Boş kapı" deger={sayi(b.firsat ?? 0)} />
              <Deger
                etiket="Doluluk"
                deger={b.penetrasyon == null ? 'veri yok' : yuzde(b.penetrasyon)}
              />
              <Deger etiket="Satış" deger={`${sayi(b.toplam_satis ?? 0)} abonelik`} />
              <Deger etiket="Satış öbeği" deger={b.obek || '–'} />
              <Deger etiket="Satışa hazır" deger={b.sales_ready ? tarihKisa(b.sales_ready) : '–'} />
            </div>

            {/* Sayıların hemen altında: neden öyle göründükleri ("abone HP'den fazla → boş kapı 0"). */}
            <KaliteNotlari notlar={b.kalite} />

            <TicketOzeti
              ticketlar={veri!.ticketlar ?? []}
              ticketAc={() => setTicketAcik(true)}
              ticketSecildi={(t) => ticketeGit(`/yonetici/ticketlar/${t.id}`)}
              tumunuGor={() => ticketeGit(`/yonetici/ticketlar/${encodeURIComponent(serial)}`)}
            />

            {/* Ticket metni artık "Ticket aç" penceresinde üretilir (konu seçilir,
                kopyalanır, OneDesk numarası kaydedilir); burada yalnız kimlikler. */}
            <BinaKimlik bina={b} ticket={false} />

            <div className="ayr-bolum">Son ziyaretler</div>
            {veri!.ziyaretler.length ? (
              <ul className="ayr-ziyaretler">
                {veri!.ziyaretler.slice(0, 5).map((z, i) => (
                  <li key={z.id ?? i}>
                    <span className="zaman">{tarihSaat(z.zaman)}</span>
                    <span className="sonuc">{z.sonuc_etiket ?? z.sonuc}</span>
                    {'kullanici' in z && (z as { kullanici?: string }).kullanici ? (
                      <span className="kim">{(z as { kullanici?: string }).kullanici}</span>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : (
              <div className="ayr-bos">Bu binaya henüz gidilmedi.</div>
            )}

            <DegisimGecmisi serial={serial} />

            <YeniTicketPenceresi
              acik={ticketAcik}
              kapat={() => setTicketAcik(false)}
              bina={{ bina_serial: serial, baslik: b.baslik || b.ad }}
              kaydedildi={() => setSurum((s) => s + 1)}
            />
          </>
        )}
      </div>
    </div>
  );
}

/** Künye geçmişi — yalnız istenince indirilir (çoğu binada boş). */
function DegisimGecmisi({ serial }: { serial: string }) {
  const [acik, setAcik] = useState(false);
  const [veri, setVeri] = useState<BinaDegisimleri | null>(null);
  const [hata, setHata] = useState<string | null>(null);

  useEffect(() => {
    if (!acik || veri) return;
    binaDegisimleri(serial)
      .then(setVeri)
      .catch((e) => setHata(e?.message || 'Geçmiş alınamadı.'));
  }, [acik, veri, serial]);

  if (!acik) {
    return (
      <button type="button" className="ayr-gecmis-ac" onClick={() => setAcik(true)}>
        Değişiklik geçmişini göster (tur raporu, OneMap)
      </button>
    );
  }
  return (
    <>
      <div className="ayr-bolum">Değişiklik geçmişi</div>
      {hata ? (
        <div className="ayr-hata">{hata}</div>
      ) : !veri ? (
        <div className="ayr-yukleniyor">Getiriliyor…</div>
      ) : veri.degisimler.length ? (
        <ul className="ayr-ziyaretler">
          {veri.degisimler.slice(0, 30).map((d, i) => (
            <li key={i}>
              <span className="zaman">{tarihSaat(d.zaman)}</span>
              <span className="sonuc">
                {d.alan === 'pasif'
                  ? d.yeni === '1'
                    ? 'Pasife alındı'
                    : 'Yeniden etkin'
                  : `${DEGISIM_ALANI[d.alan] ?? d.alan}: ${d.eski ?? '—'} → ${d.yeni ?? '—'}`}
              </span>
              <span className="kim">{d.kaynak.startsWith('tur:') ? 'Tur raporu' : d.kaynak === 'onemap' ? 'OneMap' : d.kaynak}</span>
            </li>
          ))}
        </ul>
      ) : (
        <div className="ayr-bos">Bu binanın künyesi ilk kurulumdan beri değişmedi.</div>
      )}
    </>
  );
}
