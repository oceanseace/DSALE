/**
 * Ticket ayrıntısı — sağdan açılan çekmece.
 *
 * Üstte ne olduğu (durum · konu · kaç gündür açık · bina), ortada "Durum
 * güncelle" (mail geldi → Çözüldü / Transfer …, notuyla), altta geçmiş.
 * OneDesk numarası yoksa en üstte onu sorar. "İşler" bölümü: ticket'ın Task No'ları (seçilenler + kurulum engeliyle
 * bağlananlar) ve "+ abone ekle" (aynı iş seçicisi, IsSecici.tsx). Sil: KALICI silme (onaylı; ticket, geçmişi ve
 * fotoğrafları iz bırakmadan silinir, bağlı işler yalnız ayrılır — `POST /api/ticket/{id}/sil`).
 */

import { lazy, Suspense, useCallback, useEffect, useState } from 'react';
import { useOnay } from '../../../cekirdek/ortak/Onay';
import {
  isSecenekleri,
  ticketIsCikar,
  ticketIsEkle,
  ticketSil,
  type IsSecenekleri,
  type TicketSatiri,
} from '../../../cekirdek/ticket/api';
import { benzerMetni, cozulduMetni } from './bildirim';
import { IsSecici } from './IsSecici';
import { SahaHatasi } from '../../../cekirdek/api/istemci';
import type { Ticket, TicketDurumu, TicketKonusu } from '../../../cekirdek/api/tipler';
import { useBildirim } from '../../../cekirdek/ortak/Bildirim';
import { DurumCipi } from '../../../cekirdek/ortak/BinaNotlari';
import { kopyala } from '../../../cekirdek/ortak/kimlik';
import { tarihSaat } from '../../../cekirdek/ortak/bicim';
import {
  TICKET_DURUMLARI,
  TICKET_KONULARI,
  acikGunMetni,
  durumBilgisi,
  konuEtiketi,
  tarihKisa,
} from '../../../cekirdek/ortak/ticketBilgi';
import { Kalem, Onay } from '../../../cekirdek/ortak/Ikon';
import { ticketAyrintisi, ticketGuncelle } from '../../../cekirdek/api/yonetim';
import { BinaAyrintiPenceresi } from '../../../cekirdek/konsol/BinaAyrinti';
import { Iskelet } from '../../../cekirdek/konsol/parcalar';
import type { TicketAyrintisi, TicketGecmisSatiri, TicketGuncelleme } from '../../../cekirdek/api/yonetimTipleri';
import { BILINEN_KANALLAR } from './kanallar';
import '../../../cekirdek/konsol/ekran.css';

/** Ticket fotoğrafları (EK-8): telefondan çekilenler ve yüklenenler. */
const TicketFotolari = lazy(() => import('./TicketFotolari').then((m) => ({ default: m.TicketFotolari })));

function FotoYeri({ ticketId }: { ticketId: number }) {
  return (
    <Suspense fallback={<Iskelet yukseklik={72} />}>
      <TicketFotolari ticketId={ticketId} />
    </Suspense>
  );
}

const ALAN_ADI: Record<string, string> = {
  onedesk_ekip: 'OneDesk ekibi',
  kategori: 'Başlık',
  ticket_no: 'OneDesk no',
  acilis: 'Açılış',
  konu: 'Konu',
  musteri: 'Müşteri',
  kanal: 'Kanal',
  detay: 'Detay',
  site: 'Site',
  location_id: 'Location Id',
};

function hataMetni(h: unknown, yedek: string) {
  return h instanceof SahaHatasi ? h.message : yedek;
}

export function TicketCekmecesi({
  id,
  kapat,
  degisti,
  hatirlatmaSaat = 24,
  silindi,
  yazabilir = true,
}: {
  id: number;
  kapat: () => void;
  /** Kayıt değişince listeyi güncellemek için. */
  degisti?: (t: Ticket) => void;
  /** EK-12.7: BÇO'da bu kadar saati geçen açık ticket için TL'ye mail hatırlatması (ayar). */
  hatirlatmaSaat?: number;
  /** Ticket kalıcı silindi: listeden çıkarmak için. */
  silindi?: (id: number) => void;
  /** ticket.defter: düzenleme denetimleri (no, durum, alanlar, Sil, "+ abone ekle"); yoksa salt okunur. */
  yazabilir?: boolean;
}) {
  const { goster } = useBildirim();
  const [onayPenceresi, sor] = useOnay();
  const [veri, setVeri] = useState<TicketAyrintisi | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [yeniDurum, setYeniDurum] = useState<TicketDurumu | null>(null);
  const [notu, setNotu] = useState('');
  const [no, setNo] = useState('');
  const [noDuzenle, setNoDuzenle] = useState(false);
  const [duzenle, setDuzenle] = useState(false);
  const [taslak, setTaslak] = useState<TicketGuncelleme>({});
  const [kaydediliyor, setKaydediliyor] = useState(false);
  const [binaAcik, setBinaAcik] = useState(false);

  const getir = useCallback(async () => {
    setHata(null);
    try {
      const v = await ticketAyrintisi(id);
      setVeri(v);
      setNo(v.ticket.ticket_no);
    } catch (h) {
      setHata(hataMetni(h, 'Ticket açılamadı.'));
    }
  }, [id]);

  useEffect(() => {
    setVeri(null);
    setYeniDurum(null);
    setNotu('');
    setNoDuzenle(false);
    setDuzenle(false);
    void getir();
  }, [getir]);

  useEffect(() => {
    const tus = (e: KeyboardEvent) => e.key === 'Escape' && !binaAcik && !kaydediliyor && kapat();
    window.addEventListener('keydown', tus);
    return () => window.removeEventListener('keydown', tus);
  }, [kapat, binaAcik, kaydediliyor]);

  const gonder = async (govde: TicketGuncelleme, basari: string) => {
    setKaydediliyor(true);
    try {
      const y = await ticketGuncelle(id, govde);
      setVeri({ ticket: y.ticket, gecmis: y.gecmis });
      setNo(y.ticket.ticket_no);
      degisti?.(y.ticket);
      const donen = y as { donen_tasklar?: string[]; bekliyora_donen_is?: number };
      const cozuldu = cozulduMetni(donen.donen_tasklar, donen.bekliyora_donen_is);
      goster(y.degisti === false ? 'Değişiklik yoktu.' : cozuldu ? `${basari} ${cozuldu}` : basari, 'basari');
      return true;
    } catch (h) {
      goster(hataMetni(h, 'Kaydedilemedi.'), 'uyari');
      return false;
    } finally {
      setKaydediliyor(false);
    }
  };

  const durumKaydet = async () => {
    if (!yeniDurum && !notu.trim()) return;
    const ok = await gonder(
      { ...(yeniDurum ? { durum: yeniDurum } : {}), ...(notu.trim() ? { notu: notu.trim() } : {}) },
      yeniDurum ? `Durum: ${durumBilgisi(yeniDurum).etiket}.` : 'Not eklendi.',
    );
    if (ok) {
      setYeniDurum(null);
      setNotu('');
    }
  };

  const noKaydet = async () => {
    const ok = await gonder({ ticket_no: no.trim() }, 'OneDesk numarası kaydedildi.');
    if (ok) setNoDuzenle(false);
  };

  const alanlariKaydet = async () => {
    const ok = await gonder(taslak, 'Ticket güncellendi.');
    if (ok) {
      setDuzenle(false);
      setTaslak({});
    }
  };

  const t = veri?.ticket;
  const yas = t?.acik ? acikGunMetni(t.acik_gun) : null;

  const isGuncelle = (yeni: TicketSatiri) => {
    setVeri((v) => (v ? { ...v, ticket: yeni } : v));
    degisti?.(yeni);
  };

  const sil = async () => {
    if (!t) return;
    const evet = await sor({
      baslik: 'Ticket silinsin mi?',
      metin: 'Bu ticket kalıcı olarak silinir.',
      onay: 'Sil',
      yikici: true,
    });
    if (!evet) return;
    try {
      const y = await ticketSil(t.id);
      goster(y.ayrilan_is ? `Ticket silindi; ${y.ayrilan_is} iş ayrıldı.` : 'Ticket silindi.', 'basari');
      silindi?.(t.id);
      kapat();
    } catch (h) {
      goster(hataMetni(h, 'Silinemedi.'), 'uyari');
    }
  };

  return (
    <>
      <div className="yan-perde" onClick={() => !kaydediliyor && kapat()} aria-hidden="true" />
      <aside className="yan-cekmece tk-cekmece" role="dialog" aria-modal="true" aria-label="Ticket ayrıntısı">
        <div className="yan-cekmece-bas">
          <div style={{ minWidth: 0 }}>
            <div className="tk-ust-satir">
              {t ? <DurumCipi durum={t.durum} /> : null}
              {t ? <span className="tk-konu-etiket">{t.konu_etiket}</span> : null}
              {yas ? <span className={`tk-yas${(t?.acik_gun ?? 0) >= 2 ? ' gec' : ''}`}>{yas}</span> : null}
            </div>
            <h2>{t ? (t.ticket_no ? `Ticket ${t.ticket_no}` : 'OneDesk numarası yok') : 'Ticket'}</h2>
          </div>
          <button type="button" className="yan-kapat" onClick={kapat} aria-label="Kapat">
            ×
          </button>
        </div>

        <div className="yan-cekmece-govde">
          {hata ? <div className="yon-uyari kirmizi">{hata}</div> : null}
          {!t ? (
            !hata ? <Iskelet yukseklik={320} /> : null
          ) : (
            <>
              {/* ---------------- OneDesk numarası ---------------- */}
              {yazabilir && (!t.ticket_no || noDuzenle) ? (
                <div className="tk-no-kutu">
                  <span className="yon-etiket">
                    {t.ticket_no ? 'OneDesk numarasını düzeltin' : "OneDesk'te açtığınız ticket'ın numarası"}
                  </span>
                  <div className="yon-satir" style={{ gap: 8, flexWrap: 'nowrap' }}>
                    <input
                      className="yon-alan tk-no"
                      value={no}
                      inputMode="numeric"
                      placeholder="Örn. 10133762171"
                      onChange={(e) => setNo(e.target.value.replace(/[^\dA-Za-z-]/g, ''))}
                      onKeyDown={(e) => e.key === 'Enter' && no.trim() && void noKaydet()}
                    />
                    <button className="yd birincil" onClick={noKaydet} disabled={!no.trim() || kaydediliyor}>
                      Kaydet
                    </button>
                    {noDuzenle ? (
                      <button className="yd duz" onClick={() => setNoDuzenle(false)}>
                        Vazgeç
                      </button>
                    ) : null}
                  </div>
                </div>
              ) : null}

              {/* ---------------- TL'ye mail hatırlatması (EK-12.7) ---------------- */}
              {t.acik && (t.acik_gun ?? 0) * 24 >= Math.max(1, hatirlatmaSaat) ? (
                <div className="yon-uyari tk-tl-hatirlat">
                  <span>
                    <b>{hatirlatmaSaat.toLocaleString('tr-TR')} saati geçti.</b> Takım liderine OneDesk no ve müşteri no
                    ile mail atın.
                  </span>
                  <span className="sag">
                    <button
                      type="button"
                      className="yd"
                      onClick={async () =>
                        goster(
                          (await kopyala(
                            [
                              `OneDesk ID: ${t.ticket_no || '—'}`,
                              `Müşteri no: ${t.musteri || '—'}`,
                              `Bina: ${t.bina?.ad || t.site || t.bina_serial || '—'}`,
                              `Açık: ${(t.acik_gun ?? 0).toLocaleString('tr-TR')} gün`,
                            ].join('\n'),
                          ))
                            ? 'Mail metni kopyalandı.'
                            : 'Kopyalanamadı.',
                          'bilgi',
                        )
                      }
                    >
                      Mail metnini kopyala
                    </button>
                  </span>
                </div>
              ) : null}

              {/* ---------------- Durum güncelle — en sık yapılan iş, en üstte ---------------- */}
              {yazabilir ? (
              <div className="tk-durum-kutu">
                <div className="tk-bolum-baslik">Durum güncelle</div>
                <p className="tk-ipucu" style={{ marginTop: 0 }}>
                  Mail geldiğinde (çözüldü / transfer) buradan işleyin. Her değişiklik notuyla geçmişe yazılır.
                </p>
                <div className="tk-durumlar" role="radiogroup" aria-label="Yeni durum">
                  {TICKET_DURUMLARI.map((d) => {
                    const simdiki = d.durum === t.durum;
                    const secili = yeniDurum === d.durum;
                    return (
                      <button
                        key={d.durum}
                        type="button"
                        role="radio"
                        aria-checked={secili}
                        disabled={simdiki}
                        className={`tk-durum tk-d-${d.renk}${secili ? ' secili' : ''}${simdiki ? ' simdiki' : ''}`}
                        onClick={() => setYeniDurum(secili ? null : d.durum)}
                        title={d.anlam}
                      >
                        <b>
                          {secili ? <Onay boyut={14} /> : null}
                          {d.etiket}
                        </b>
                        <span>{simdiki ? 'şu anki durum' : d.anlam}</span>
                      </button>
                    );
                  })}
                </div>
                <label className="tk-alan" style={{ marginTop: 10 }}>
                  <span className="yon-etiket">Not (isteğe bağlı)</span>
                  <input
                    className="yon-alan"
                    value={notu}
                    maxLength={2000}
                    placeholder={
                      yeniDurum === 'ÇÖZÜLDÜ'
                        ? 'Örn. 29.09 mail: sinyal düzeltildi'
                        : yeniDurum === 'TRANSFER'
                          ? 'Örn. Saha ekibine transfer edildi'
                          : 'Örn. Müşteri arandı, sorun sürüyor'
                    }
                    onChange={(e) => setNotu(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && (yeniDurum || notu.trim()) && void durumKaydet()}
                  />
                </label>
                <button
                  className="yd birincil genis buyuk"
                  style={{ marginTop: 10 }}
                  onClick={durumKaydet}
                  disabled={(!yeniDurum && !notu.trim()) || kaydediliyor}
                >
                  {kaydediliyor
                    ? 'Kaydediliyor…'
                    : yeniDurum
                      ? `Durumu "${durumBilgisi(yeniDurum).etiket}" yap`
                      : notu.trim()
                        ? 'Notu ekle'
                        : 'Yeni durumu seçin'}
                </button>
              </div>
              ) : null}

              {/* ---------------- Bina ---------------- */}
              <div className="tk-bina">
                <div style={{ minWidth: 0 }}>
                  <b>{t.bina?.ad || t.site || 'Binaya bağlı değil'}</b>
                  <span>
                    {[
                      t.bina_serial,
                      t.location_id ? `Location Id ${t.location_id}` : null,
                      t.bina?.bolge ? `${t.bina.bolge}. bölge` : null,
                      [t.bina?.ilce, t.bina?.mahalle].filter(Boolean).join(' / ') || null,
                    ]
                      .filter(Boolean)
                      .join(' · ')}
                  </span>
                </div>
                {t.bina_serial ? (
                  <button type="button" className="yd" onClick={() => setBinaAcik(true)}>
                    Binayı aç
                  </button>
                ) : null}
              </div>

              <TicketIsleri t={t as TicketSatiri} guncelle={isGuncelle} yazabilir={yazabilir} />

              <div className="tk-bilgiler">
                <Bilgi etiket="Açılış" deger={tarihKisa(t.acilis)} />
                {t.onedesk_ekip ? <Bilgi etiket="OneDesk ekibi" deger={t.onedesk_ekip} /> : null}
                {t.kategori ? <Bilgi etiket="Başlık" deger={t.kategori} genis /> : null}
                <Bilgi etiket="Satış kanalı" deger={(t as TicketSatiri).satis_kanali || t.kanal || '—'} />
                <Bilgi etiket="Müşteri" deger={t.musteri || '—'} kopya />
                <Bilgi etiket="Kaynak" deger={t.kaynak === 'excel' ? "Excel'den aktarıldı" : 'Uygulamada açıldı'} />
                {t.detay ? <Bilgi etiket="Detay" deger={t.detay} genis /> : null}
                {t.kapanis ? <Bilgi etiket="Kapanış" deger={tarihSaat(t.kapanis)} /> : null}
              </div>

              {yazabilir ? (
              <div className="tk-arac-satiri">
                {t.ticket_no && !noDuzenle ? (
                  <button className="yd duz" onClick={() => setNoDuzenle(true)}>
                    <Kalem boyut={15} /> Numarayı düzelt
                  </button>
                ) : null}
                <button
                  className="yd duz"
                  onClick={() => {
                    setDuzenle((d) => !d);
                    setTaslak({});
                  }}
                >
                  <Kalem boyut={15} /> {duzenle ? 'Düzenlemeyi kapat' : 'Diğer alanları düzenle'}
                </button>
                <button className="yd duz tk-sil" onClick={() => void sil()}>
                  Sil
                </button>
              </div>
              ) : null}

              {yazabilir && duzenle ? (
                <div className="tk-duzenle">
                  <label className="tk-alan">
                    <span className="yon-etiket">Konu</span>
                    <select
                      className="yon-alan"
                      value={taslak.konu ?? t.konu}
                      onChange={(e) => setTaslak({ ...taslak, konu: e.target.value as TicketKonusu })}
                    >
                      {TICKET_KONULARI.map((k) => (
                        <option key={k.konu} value={k.konu}>
                          {k.etiket}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="tk-alan">
                    <span className="yon-etiket">Açılış tarihi</span>
                    <input
                      className="yon-alan"
                      type="date"
                      value={taslak.acilis ?? t.acilis ?? ''}
                      onChange={(e) => setTaslak({ ...taslak, acilis: e.target.value })}
                    />
                  </label>
                  <label className="tk-alan">
                    <span className="yon-etiket">Kanal</span>
                    <input
                      className="yon-alan"
                      list="tk-kanallar-duzenle"
                      value={taslak.kanal ?? t.kanal}
                      onChange={(e) => setTaslak({ ...taslak, kanal: e.target.value.toLocaleUpperCase('tr-TR') })}
                    />
                    <datalist id="tk-kanallar-duzenle">
                      {BILINEN_KANALLAR.map((k) => (
                        <option key={k} value={k} />
                      ))}
                    </datalist>
                  </label>
                  <label className="tk-alan">
                    <span className="yon-etiket">Müşteri</span>
                    <input
                      className="yon-alan"
                      value={taslak.musteri ?? t.musteri}
                      onChange={(e) => setTaslak({ ...taslak, musteri: e.target.value })}
                    />
                  </label>
                  <label className="tk-alan genis">
                    <span className="yon-etiket">Detay</span>
                    <textarea
                      className="yon-alan"
                      value={taslak.detay ?? t.detay}
                      onChange={(e) => setTaslak({ ...taslak, detay: e.target.value })}
                    />
                  </label>
                  <div className="bp-onay-dugmeler genis" style={{ marginTop: 0 }}>
                    <button
                      className="yd birincil"
                      onClick={alanlariKaydet}
                      disabled={!Object.keys(taslak).length || kaydediliyor}
                    >
                      Değişiklikleri kaydet
                    </button>
                  </div>
                </div>
              ) : null}

              {/* ---------------- Metin ---------------- */}
              {t.metin ? (
                <div className="tk-metin-kutu">
                  <div className="tk-metin-bas">
                    <b>Ticket metni</b>
                    <button
                      className="yd duz"
                      style={{ marginLeft: 'auto' }}
                      onClick={async () => goster((await kopyala(t.metin)) ? 'Metin kopyalandı.' : 'Kopyalanamadı.', 'bilgi')}
                    >
                      Kopyala
                    </button>
                  </div>
                  <pre className="tk-metin">{t.metin}</pre>
                </div>
              ) : null}

              {/* ---------------- Fotoğraflar (EK-8) ---------------- */}
              <div className="tk-bolum-baslik">Fotoğraflar</div>
              <FotoYeri ticketId={t.id} />

              {/* ---------------- Geçmiş ---------------- */}
              <div className="tk-bolum-baslik">Geçmiş</div>
              <ol className="tk-gecmis">
                {[...(veri?.gecmis ?? [])].reverse().map((g) => (
                  <GecmisSatiri key={g.id} g={g} />
                ))}
              </ol>
            </>
          )}
        </div>
      </aside>
      {onayPenceresi}
      {binaAcik && t?.bina_serial ? (
        <BinaAyrintiPenceresi serial={t.bina_serial} kapat={() => setBinaAcik(false)} />
      ) : null}
    </>
  );
}

/** Ticket'ın işleri (Task No · Task adı · satış kanalı · müşteri) + "+ abone ekle" (aynı iş seçicisi). */
function TicketIsleri({
  t,
  guncelle,
  yazabilir = true,
}: {
  t: TicketSatiri;
  guncelle: (t: TicketSatiri) => void;
  yazabilir?: boolean;
}) {
  const { goster } = useBildirim();
  const isler = t.isler ?? [];
  const [ekle, setEkle] = useState(false);
  const [arama, setArama] = useState(t.location_id || '');
  const [secenek, setSecenek] = useState<IsSecenekleri | null>(null);
  const [secili, setSecili] = useState<Set<string>>(new Set());
  const [bekliyor, setBekliyor] = useState(false);
  const mevcut = new Set(isler.map((x) => x.task_no));

  const getir = async () => {
    const q = arama.trim();
    if (!q) return;
    setBekliyor(true);
    try {
      /* Yalnız rakam/virgül: müşteri no; değilse Loc ID. */
      const v = await isSecenekleri(/^[\d\s,;]+$/.test(q) ? { musteri: q, haric: t.id } : { loc: q, haric: t.id });
      setSecenek(v);
      setSecili(new Set());
    } catch (h) {
      goster(hataMetni(h, 'İşler getirilemedi.'), 'uyari');
    } finally {
      setBekliyor(false);
    }
  };

  const kaydet = async () => {
    if (!secili.size) return;
    setBekliyor(true);
    try {
      const y = await ticketIsEkle(t.id, [...secili]);
      guncelle(y.ticket);
      goster(`${y.eklenen.length.toLocaleString('tr-TR')} iş eklendi.`, 'basari');
      setEkle(false);
      setSecenek(null);
    } catch (h) {
      goster(hataMetni(h, 'Eklenemedi.'), 'uyari');
    } finally {
      setBekliyor(false);
    }
  };

  const cikar = async (no: string) => {
    try {
      guncelle((await ticketIsCikar(t.id, [no])).ticket);
    } catch (h) {
      goster(hataMetni(h, 'Çıkarılamadı.'), 'uyari');
    }
  };

  return (
    <div className="tk-isler">
      <div className="tk-bolum-baslik tk-isler-bas">
        <span>İşler{isler.length ? ` (${isler.length.toLocaleString('tr-TR')})` : ''}</span>
        {yazabilir ? (
          <button type="button" className="yd duz" onClick={() => setEkle((e) => !e)}>
            {ekle ? 'Kapat' : '+ abone ekle'}
          </button>
        ) : null}
      </div>
      {isler.length ? (
        <ul className="tk-is-satirlari">
          {isler.map((x) => (
            <li key={x.task_no} className={x.acik ? '' : 'kapali'}>
              <span className="no">{x.task_no}</span>
              <span className="ad" title={x.uyari || undefined}>
                {x.uyari ? <span className="tk-uyari">⚠ </span> : null}
                {x.task_adi || '—'}
              </span>
              <span className="kanal">{x.satis_kanali}</span>
              <span className="no">{x.musteri_no}</span>
              {x.bagli ? (
                <span className="tk-is-etiket" title="Kurulum engeliyle bağlı (TASKS Bizim durum)">
                  engel
                </span>
              ) : null}
              {x.secildi && yazabilir ? (
                <button
                  type="button"
                  className="tk-is-cikar"
                  aria-label={`Task ${x.task_no} çıkar`}
                  title="Ticket'tan çıkar"
                  onClick={() => void cikar(x.task_no)}
                >
                  ×
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="tk-ipucu">Bu ticket'a iş seçilmemiş.</p>
      )}
      <BossNotlari t={t} />
      <BossAskilari t={t} />
      {yazabilir && ekle ? (
        <div className="tk-is-ekle">
          <div className="yon-satir" style={{ gap: 8, flexWrap: 'nowrap' }}>
            <input
              className="yon-alan"
              value={arama}
              placeholder="Müşteri No (virgülle çok) ya da Loc ID"
              onChange={(o) => setArama(o.target.value)}
              onKeyDown={(o) => o.key === 'Enter' && void getir()}
            />
            <button className="yd" onClick={() => void getir()} disabled={!arama.trim() || bekliyor}>
              İşleri getir
            </button>
          </div>
          {secenek ? (
            <>
              {secenek.benzer.length ? <p className="tk-yeni-not uyari">⚠ {benzerMetni(secenek.benzer)}</p> : null}
              <IsSecici isler={secenek.isler} secili={secili} degistir={setSecili} fazla={secenek.fazla} devreDisi={mevcut} />
              <button className="yd birincil" style={{ marginTop: 8 }} onClick={() => void kaydet()} disabled={!secili.size || bekliyor}>
                {secili.size ? `${secili.size.toLocaleString('tr-TR')} işi ekle` : 'İş seçin'}
              </button>
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

/** Ticket numarası girilince işlere kendiliğinden düşülen BOSS notu (sunucu: saha/ticket_boss_not.py). */
type BossNotu = {
  task_no: string;
  task_adi: string;
  metin: string;
  durum: 'gonderiliyor' | 'gonderildi' | 'hata' | 'kapali';
  hata?: string;
};
const BOSS_NOT_ETIKET: Record<BossNotu['durum'], string> = {
  gonderiliyor: 'gidiyor',
  gonderildi: '✓',
  hata: 'hata',
  kapali: 'kapalı',
};

function BossNotlari({ t }: { t: TicketSatiri }) {
  const notlar = (t as TicketSatiri & { boss_notlari?: BossNotu[] }).boss_notlari ?? [];
  if (!notlar.length) return null;
  return (
    <div className="tk-boss-notlari">
      <div className="tk-bolum-baslik">BOSS notu</div>
      <ul className="tk-is-satirlari">
        {notlar.map((x) => (
          <li key={x.task_no} title={x.metin}>
            <span className="no">{x.task_no}</span>
            <span className="ad">{x.task_adi || '—'}</span>
            <span
              className={`tk-boss-not ${x.durum}`}
              title={x.durum === 'hata' && x.hata ? `${x.metin}
${x.hata}` : x.metin}
            >
              BOSS notu: {BOSS_NOT_ETIKET[x.durum] ?? x.durum}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Ticket'a bağlı işlerin otomatik BOSS askısı ve çözümde önceki ekibe geri ataması (sunucu: saha/ticket_boss_aski.py). */
type BossAskisi = {
  task_no: string;
  task_adi: string;
  durum: 'askida' | 'atandi' | 'ekipsiz' | 'atanamadi' | 'birakildi';
  onceki_ekip: string | null;
  bitis: string | null;
  atama_bas: string | null;
  hata?: string;
  /** Önceki ekip anlık görüntüsü ve son bilinen ekip yok: "Önceki ekip bilinmiyor — elle atayın". */
  uyari?: string;
  boss?: 'gidiyor' | 'tamam' | 'hata' | 'kapali' | 'alt_neden_bekleniyor';
  boss_hata?: string;
};
const BOSS_ASKI_ETIKET: Record<NonNullable<BossAskisi['boss']>, string> = {
  gidiyor: 'gidiyor',
  tamam: '✓',
  hata: 'hata',
  kapali: 'kapalı',
  alt_neden_bekleniyor: 'alt neden bekleniyor',
};
const gunSaat = (t: string | null) => (t ? `${t.slice(8, 10)}.${t.slice(5, 7)} ${t.slice(11, 16)}` : '');

function askiMetni(x: BossAskisi): { metin: string; sinif: string } {
  if (x.durum === 'atandi') return { metin: `Önceki ekibe atandı${x.onceki_ekip ? ` (${x.onceki_ekip})` : ''} · ${gunSaat(x.atama_bas)}`, sinif: 'gonderildi' };
  if (x.durum === 'ekipsiz') return { metin: `Çözüldü · ${x.uyari ?? 'Önceki ekip bilinmiyor — elle atayın'}`, sinif: 'hata' };
  if (x.durum === 'atanamadi') return { metin: `Çözüldü · atanamadı${x.hata ? `: ${x.hata}` : ''}`, sinif: 'hata' };
  if (x.durum === 'birakildi') return { metin: 'Askı bırakıldı', sinif: 'kapali' };
  const b = x.boss ?? 'gidiyor';
  return {
    metin: `BOSS askı: ${BOSS_ASKI_ETIKET[b] ?? b}${x.bitis ? ` · ${gunSaat(x.bitis)}’e dek` : ''}${x.uyari ? ` · ${x.uyari}` : ''}`,
    sinif: b === 'tamam' ? 'gonderildi' : b === 'hata' ? 'hata' : b === 'gidiyor' ? 'gonderiliyor' : 'kapali',
  };
}

function BossAskilari({ t }: { t: TicketSatiri }) {
  const askilar = (t as TicketSatiri & { boss_askilar?: BossAskisi[] }).boss_askilar ?? [];
  if (!askilar.length) return null;
  return (
    <div className="tk-boss-notlari">
      <div className="tk-bolum-baslik">BOSS askısı</div>
      <ul className="tk-is-satirlari">
        {askilar.map((x) => {
          const m = askiMetni(x);
          return (
            <li key={x.task_no} title={x.boss_hata || (x.onceki_ekip ? `Önceki ekip: ${x.onceki_ekip}` : undefined)}>
              <span className="no">{x.task_no}</span>
              <span className="ad">{x.task_adi || '—'}</span>
              <span className={`tk-boss-not ${m.sinif}`}>{m.metin}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function Bilgi({
  etiket,
  deger,
  genis = false,
  kopya = false,
}: {
  etiket: string;
  deger: string;
  genis?: boolean;
  kopya?: boolean;
}) {
  const { goster } = useBildirim();
  return (
    <div className={`tk-bilgi${genis ? ' genis' : ''}`}>
      <span className="etiket">{etiket}</span>
      {kopya && deger !== '—' ? (
        <button
          type="button"
          className="deger kopya"
          title="Kopyala"
          onClick={async () => goster((await kopyala(deger)) ? `${etiket} kopyalandı.` : 'Kopyalanamadı.', 'bilgi')}
        >
          {deger}
        </button>
      ) : (
        <span className="deger">{deger}</span>
      )}
    </div>
  );
}

function GecmisSatiri({ g }: { g: TicketGecmisSatiri }) {
  const durumDegisti = g.eski_durum !== g.yeni_durum;
  const alanlar = Object.entries(g.alanlar ?? {});
  return (
    <li className="tk-gecmis-satir">
      <span className="tk-gecmis-nokta" aria-hidden="true">
        {g.eski_durum == null ? <Onay boyut={12} /> : durumDegisti ? null : <Kalem boyut={11} />}
      </span>
      <div>
        <div className="tk-gecmis-ust">
          <span>{tarihSaat(g.zaman)}</span>
          {g.kullanici ? <span>· {g.kullanici}</span> : null}
        </div>
        <div className="tk-gecmis-ne">
          {g.eski_durum == null ? (
            <>
              Oluşturuldu {g.yeni_durum ? <DurumCipi durum={g.yeni_durum} kucuk /> : null}
            </>
          ) : durumDegisti ? (
            <>
              <DurumCipi durum={g.eski_durum} kucuk /> → <DurumCipi durum={g.yeni_durum ?? ''} kucuk />
            </>
          ) : alanlar.length ? (
            'Bilgi güncellendi'
          ) : (
            'Not eklendi'
          )}
        </div>
        {alanlar.length ? (
          <div className="tk-gecmis-alanlar">
            {alanlar.map(([a, [eski, yeni]]) => (
              <span key={a}>
                {ALAN_ADI[a] ?? a}: <s>{a === 'konu' ? konuEtiketi(eski ?? '') : eski || '—'}</s> →{' '}
                <b>{a === 'konu' ? konuEtiketi(yeni ?? '') : yeni || '—'}</b>
              </span>
            ))}
          </div>
        ) : null}
        {g.notu ? <div className="tk-gecmis-not">{g.notu}</div> : null}
      </div>
    </li>
  );
}

