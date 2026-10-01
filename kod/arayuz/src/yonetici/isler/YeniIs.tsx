/**
 * Yeni iş (§6.8, F16): bayinin kendi açtığı iş. Tek sütun çekmece:
 * Müşteri No (aynı müşterinin açık işi varsa söylenir) · Müşteri adı · İş tipi
 * (bilinen task adlarından) · Bina (bina ile ara → mahalle ve öbek kendiliğinden)
 * ya da Adres + mahalle (sözlük seçici) · Açıklama. Birincil: "İşi aç".
 * Sonuç: "B-260930-001 açıldı · Atanmadı listesinde." İş "Bayi" rozetiyle öneriyle düşer.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { hataMetni, istemciKimligi, yeniIs } from '../../is/api';
import type { MahalleKaydi } from '../../is/tipler';
import { binaAyrinti } from '../../api/uclar';
import { binalar as binaAra } from '../api';
import { Panel } from '../../ortak/Panel';
import { Segment } from '../../ortak/Segment';
import { useBildirim } from '../../ortak/Bildirim';
import { useOturum } from '../../depo/oturum';
import { MahalleSecici } from '../obekler/MahalleSecici';
import { useIsler } from './depo';

interface BinaSecimi {
  serial: string;
  ad: string;
  yer: string;
}

const SIK_ISLER = ['Bağlantı Problemi', 'Arama Problemi', 'TV+ Arıza', 'Modem Değişikliği', 'STB Cihaz Değişikliği'];

export function YeniIsPaneli({ acik, kapat, acildi }: { acik: boolean; kapat: () => void; acildi: (isNo: string) => void }) {
  const depo = useIsler();
  const { izinli } = useOturum();
  const bildirim = useBildirim();
  const [musteriNo, setMusteriNo] = useState('');
  const [musteriAdi, setMusteriAdi] = useState('');
  const [task, setTask] = useState('');
  const [yerKipi, setYerKipi] = useState<'bina' | 'adres'>('bina');
  const [binaSorgu, setBinaSorgu] = useState('');
  const [binaSonuc, setBinaSonuc] = useState<BinaSecimi[] | null>(null);
  const [bina, setBina] = useState<BinaSecimi | null>(null);
  const [adres, setAdres] = useState('');
  const [mahalle, setMahalle] = useState<MahalleKaydi | null>(null);
  const [mahalleSec, setMahalleSec] = useState(false);
  const [aciklama, setAciklama] = useState('');
  const [bekliyor, setBekliyor] = useState(false);
  const kimlik = useRef(istemciKimligi());
  const listeArar = izinli('satis.kendi');

  useEffect(() => {
    if (!acik) return;
    kimlik.current = istemciKimligi();
    setMusteriNo('');
    setMusteriAdi('');
    setTask('');
    setBina(null);
    setBinaSorgu('');
    setBinaSonuc(null);
    setAdres('');
    setMahalle(null);
    setAciklama('');
  }, [acik]);

  const tasklar = useMemo(() => {
    const s = new Map<string, number>();
    depo.isler.forEach((x) => s.set(x.task_adi, (s.get(x.task_adi) ?? 0) + 1));
    SIK_ISLER.forEach((t) => s.set(t, s.get(t) ?? 0));
    return [...s.entries()].sort((a, b) => b[1] - a[1]).map(([t]) => t);
  }, [depo.isler]);

  const ayniMusteri = useMemo(() => {
    const n = musteriNo.trim();
    if (n.length < 5) return [];
    return depo.isler.filter((x) => x.musteri_no && x.musteri_no === n);
  }, [depo.isler, musteriNo]);

  /* Bina arama: yöneticide bina listesinde (ad / Location Id), operasyonda Bina Serial ile birebir. */
  useEffect(() => {
    const q = binaSorgu.trim();
    if (q.length < 3 || bina) {
      setBinaSonuc(null);
      return;
    }
    let iptal = false;
    const t = window.setTimeout(() => {
      const bitti = (l: BinaSecimi[]) => !iptal && setBinaSonuc(l);
      if (listeArar) {
        binaAra({ q, limit: 8 })
          .then((y) => bitti(y.binalar.map((b) => ({ serial: b.bina_serial, ad: b.baslik, yer: [b.mahalle, b.ilce].filter(Boolean).join(' · ') }))))
          .catch(() => bitti([]));
      } else {
        binaAyrinti(q.toLocaleUpperCase('tr-TR').replace(/\s+/g, ''))
          .then((d) =>
            bitti([
              {
                serial: d.bina.bina_serial,
                ad: d.bina.baslik || d.bina.ad || d.bina.bina_serial,
                yer: [d.bina.mahalle, d.bina.ilce].filter(Boolean).join(' · '),
              },
            ]),
          )
          .catch(() => bitti([]));
      }
    }, 300);
    return () => {
      iptal = true;
      window.clearTimeout(t);
    };
  }, [binaSorgu, bina, listeArar]);

  const hazir = task.trim() && (yerKipi === 'bina' ? Boolean(bina) : Boolean(adres.trim() && mahalle));

  const ac = async () => {
    if (!hazir) return;
    setBekliyor(true);
    try {
      const y = await yeniIs({
        task_adi: task.trim(),
        bina_serial: yerKipi === 'bina' ? bina?.serial : null,
        adres: yerKipi === 'adres' ? adres.trim() : null,
        mahalle_id: yerKipi === 'adres' ? mahalle?.id ?? null : null,
        musteri_adi: musteriAdi.trim() || null,
        musteri_no: musteriNo.trim() || null,
        aciklama: aciklama.trim() || null,
        istemci_id: kimlik.current,
      });
      depo.isYaz(y.is);
      bildirim.goster(`${y.is_no} açıldı · Atanmadı listesinde.`, 'basari', { sureMs: 6000 });
      kapat();
      acildi(y.is_no);
    } catch (e) {
      bildirim.goster(hataMetni(e), 'uyari');
    } finally {
      setBekliyor(false);
    }
  };

  return (
    <Panel
      acik={acik}
      kapat={kapat}
      kilitli={bekliyor}
      baslik={mahalleSec ? 'Mahalleyi seçin' : 'Yeni iş'}
      altBaslik={mahalleSec ? undefined : 'Bayinin açtığı iş; 24 saat açılış anından başlar.'}
      alt={
        mahalleSec ? undefined : (
          <>
            <button type="button" className="o-dugme" onClick={kapat} disabled={bekliyor}>
              Vazgeç
            </button>
            <button type="button" className="o-dugme birincil" onClick={() => void ac()} disabled={!hazir || bekliyor}>
              {bekliyor ? 'Açılıyor…' : 'İşi aç'}
            </button>
          </>
        )
      }
    >
      {mahalleSec ? (
        <>
          <button type="button" className="o-dugme kucuk metin" onClick={() => setMahalleSec(false)}>
            ‹ Geri
          </button>
          <MahalleSecici
            tek
            tekSec={(m) => {
              setMahalle(m);
              setMahalleSec(false);
            }}
          />
        </>
      ) : (
        <div className="ip-form">
          <label className="o-alan">
            <span className="etiket">Müşteri No (isteğe bağlı)</span>
            <input className="o-girdi" inputMode="numeric" value={musteriNo} maxLength={40} onChange={(o) => setMusteriNo(o.target.value)} />
            {ayniMusteri.length ? (
              <span className="aciklama ip-uyari-yazi">
                Bu müşterinin açık işi var: {ayniMusteri.map((x) => `${x.task_adi} (${x.boss_task_no ?? x.is_no})`).join(', ')}
              </span>
            ) : null}
          </label>
          <label className="o-alan">
            <span className="etiket">Müşteri adı (isteğe bağlı)</span>
            <input className="o-girdi" value={musteriAdi} maxLength={200} onChange={(o) => setMusteriAdi(o.target.value)} />
          </label>
          <label className="o-alan">
            <span className="etiket">İş tipi</span>
            <input className="o-girdi" list="ip-tasklar" value={task} maxLength={120} placeholder="Bağlantı Problemi…" onChange={(o) => setTask(o.target.value)} />
            <datalist id="ip-tasklar">
              {tasklar.map((t) => (
                <option key={t} value={t} />
              ))}
            </datalist>
          </label>

          <div className="o-alan">
            <span className="etiket">Yer</span>
            <Segment<'bina' | 'adres'>
              etiket="Yer"
              tam
              deger={yerKipi}
              degisti={setYerKipi}
              secenekler={[
                { deger: 'bina', etiket: 'Bina ile' },
                { deger: 'adres', etiket: 'Adres ile' },
              ]}
            />
          </div>

          {yerKipi === 'bina' ? (
            bina ? (
              <div className="ip-secilen">
                <span>
                  <b>{bina.ad}</b>
                  <span className="ip-kaynak"> · {bina.yer || bina.serial}</span>
                </span>
                <button type="button" className="o-dugme kucuk metin" onClick={() => setBina(null)}>
                  Değiştir
                </button>
              </div>
            ) : (
              <label className="o-alan">
                <span className="etiket">{listeArar ? 'Bina adı, Location Id ya da Bina Serial' : 'Bina Serial'}</span>
                <input className="o-girdi" type="search" value={binaSorgu} onChange={(o) => setBinaSorgu(o.target.value)} />
                {binaSonuc && binaSonuc.length ? (
                  <div className="ip-secim-liste" role="listbox" aria-label="Binalar">
                    {binaSonuc.map((b) => (
                      <button key={b.serial} type="button" role="option" aria-selected={false} onClick={() => setBina(b)}>
                        <span className="ad">{b.ad}</span>
                        <span className="bilgi">{b.yer || b.serial}</span>
                      </button>
                    ))}
                  </div>
                ) : null}
                {binaSonuc && !binaSonuc.length ? (
                  <span className="aciklama">
                    {listeArar ? 'Bu aramayla bina bulunamadı.' : 'Bu Bina Serial ile bina yok. Bina Serial’ı tam yazın ya da “Adres ile” seçin.'}
                  </span>
                ) : null}
              </label>
            )
          ) : (
            <>
              <label className="o-alan">
                <span className="etiket">Adres</span>
                <textarea value={adres} maxLength={500} onChange={(o) => setAdres(o.target.value)} style={{ minHeight: 72 }} />
              </label>
              <div className="o-alan">
                <span className="etiket">Mahalle</span>
                {mahalle ? (
                  <div className="ip-secilen">
                    <span>
                      <b>{mahalle.ad}</b>
                      <span className="ip-kaynak">
                        {' '}
                        · {mahalle.ilce}
                        {mahalle.obek ? ` · ${mahalle.obek.ad} öbeğine düşer` : ' · öbeği yok (Kontrol’e düşer)'}
                      </span>
                    </span>
                    <button type="button" className="o-dugme kucuk metin" onClick={() => setMahalleSec(true)}>
                      Değiştir
                    </button>
                  </div>
                ) : (
                  <button type="button" className="o-dugme" onClick={() => setMahalleSec(true)}>
                    Mahalle seçin…
                  </button>
                )}
              </div>
            </>
          )}

          <label className="o-alan">
            <span className="etiket">Açıklama (isteğe bağlı)</span>
            <textarea value={aciklama} maxLength={1000} onChange={(o) => setAciklama(o.target.value)} style={{ minHeight: 72 }} />
          </label>
        </div>
      )}
    </Panel>
  );
}
