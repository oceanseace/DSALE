/**
 * İş ekranlarının küçük ortak parçaları (WP-C): kısa ad, dilim metni, kopyala
 * düğmesi, teknisyen ve öbek seçicileri. Metinler §6.15 sözlüğündendir.
 */

import { useMemo, useState, type ReactNode } from 'react';
import type { IsSatir, Kisi, Obek, TeknikOzet } from '../../is/tipler';
import { kopyala } from '../../ortak/kimlik';
import { KisiSecici, type SecilecekKisi } from '../../ortak/KisiSecici';
import { eslesir } from '../../ortak/ara';
import { sunucuZamani } from '../../ortak/sure';
import { useBildirim } from '../../ortak/Bildirim';

/** "Ali Kaya" → "Ali K." (ekranda teknisyen adı böyle; tam ad ipucunda). */
export function kisaAd(ad: string | null | undefined): string {
  const p = String(ad ?? '').trim().split(/\s+/).filter(Boolean);
  if (!p.length) return '—';
  if (p.length === 1) return p[0];
  return `${p.slice(0, -1).join(' ')} ${p[p.length - 1].charAt(0).toLocaleUpperCase('tr-TR')}.`;
}

const iki = (n: number) => String(n).padStart(2, '0');

export function gunAnahtari(d: Date): string {
  return `${d.getFullYear()}-${iki(d.getMonth() + 1)}-${iki(d.getDate())}`;
}

/** "11:00–13:00" (bugün) · "Yarın 11:00–13:00" · "02.10 11:00–13:00". */
export function dilimMetni(bas: string | null | undefined, bit: string | null | undefined, simdi = new Date()): string {
  const b = sunucuZamani(bas);
  if (!b) return '';
  const s = sunucuZamani(bit);
  const saat = (d: Date) => `${iki(d.getHours())}:${iki(d.getMinutes())}`;
  const bugun = gunAnahtari(simdi);
  const yarin = gunAnahtari(new Date(simdi.getFullYear(), simdi.getMonth(), simdi.getDate() + 1));
  const g = gunAnahtari(b);
  const gun = g === bugun ? '' : g === yarin ? 'Yarın ' : `${iki(b.getDate())}.${iki(b.getMonth() + 1)} `;
  return `${gun}${saat(b)}${s ? `–${saat(s)}` : ''}`;
}

/** "30.09.2026 11:00" — BOSS'a yazılacak biçim. */
export function tarihSaatMetni(metin: string | null | undefined): string {
  const d = sunucuZamani(metin);
  if (!d) return '';
  return `${iki(d.getDate())}.${iki(d.getMonth() + 1)}.${d.getFullYear()} ${iki(d.getHours())}:${iki(d.getMinutes())}`;
}

export function saatMetni(metin: string | null | undefined): string {
  const d = sunucuZamani(metin);
  return d ? `${iki(d.getHours())}:${iki(d.getMinutes())}` : '—';
}

/** Atanmamış işin bekleme rengi (§3.5): 10 dk amber, 15 dk kırmızı. */
export function beklemeRengi(dk: number | null | undefined): 'kirmizi' | 'amber' | null {
  if (dk === null || dk === undefined) return null;
  if (dk >= 15) return 'kirmizi';
  if (dk >= 10) return 'amber';
  return null;
}

export function obekSinifi(renk: number | null | undefined): string {
  return `r${((renk ?? 0) % 8 + 8) % 8}`;
}

export function ObekNoktasi({ renk }: { renk: number | null | undefined }) {
  return <span className={`o-obek-nokta ${obekSinifi(renk)}`} aria-hidden="true" />;
}

/** Küçük "Kopyala" düğmesi: basınca "Kopyalandı ✓" olur. */
export function KopyalaDugmesi({
  metin,
  etiket = 'Kopyala',
  sonra,
  bildirim,
}: {
  metin: string;
  etiket?: string;
  /** Kopyalandıktan sonra (erişim kaydı gibi). */
  sonra?: () => void;
  /** Kopyalandı bildirimi ("Task No kopyalandı, BOSS'ta arayın"). */
  bildirim?: string;
}) {
  const [oldu, setOldu] = useState(false);
  const { goster } = useBildirim();
  return (
    <button
      type="button"
      className="o-dugme kucuk metin ip-kopyala"
      onClick={async (o) => {
        o.stopPropagation();
        const tamam = await kopyala(metin);
        if (tamam) {
          setOldu(true);
          window.setTimeout(() => setOldu(false), 1600);
          if (bildirim) goster(bildirim, 'basari');
          sonra?.();
        } else goster('Kopyalanamadı. Metni seçip Ctrl+C ile kopyalayın.', 'uyari');
      }}
    >
      {oldu ? 'Kopyalandı ✓' : etiket}
    </button>
  );
}

/* ------------------------------ Teknisyen seçici ------------------------------ */

/** "öbeğin · bugün 9/15" satırları; önce öbeğin ev teknisyeni, sonra yükü az olan. */
export function teknikSecenekleri(teknikler: TeknikOzet[], obekId: number | null | undefined, onerilen?: number | null): SecilecekKisi[] {
  const sirali = [...teknikler].sort((a, b) => {
    const ea = a.obekler.some((o) => o.id === obekId) ? 0 : 1;
    const eb = b.obekler.some((o) => o.id === obekId) ? 0 : 1;
    if (ea !== eb) return ea - eb;
    if (a.bugun_yok !== b.bugun_yok) return a.bugun_yok ? 1 : -1;
    return a.bugun.atanan / Math.max(1, a.kapasite) - b.bugun.atanan / Math.max(1, b.kapasite);
  });
  return sirali.map((t) => {
    const obeginde = obekId ? t.obekler.some((o) => o.id === obekId) : false;
    const parca = [
      obeginde ? 'öbeğin' : t.obekler.length ? t.obekler.map((o) => o.ad).slice(0, 2).join(', ') : null,
      `bugün ${t.bugun.atanan}/${t.kapasite}`,
      t.bugun_yok ? 'bugün yok' : null,
    ].filter(Boolean);
    return {
      id: t.id,
      ad: t.ad,
      bilgi: parca.join(' · '),
      rozet:
        onerilen === t.id ? (
          <span className="o-rozet mavi">Önerilen</span>
        ) : t.giris_var === false ? (
          <span className="o-rozet" title="Telefonu yok; işini BOSS Mobil ile yapar">
            BOSS Mobil
          </span>
        ) : undefined,
      anahtar: `${t.boss_ekip ?? ''} ${t.obekler.map((o) => o.ad).join(' ')} ${t.unvan ?? ''}`,
      kapali: false,
    };
  });
}

export function TeknikSecici({
  teknikler,
  deger,
  degisti,
  obekId,
  onerilen,
}: {
  teknikler: TeknikOzet[];
  deger: number | null;
  degisti: (id: number) => void;
  obekId?: number | null;
  onerilen?: number | null;
}) {
  const kisiler = useMemo(() => teknikSecenekleri(teknikler, obekId, onerilen), [teknikler, obekId, onerilen]);
  if (!teknikler.length) {
    return <p className="ip-sessiz">Henüz teknik görevli yok. Ekip ekranından Teknik görevli kişi ekleyin.</p>;
  }
  return (
    <KisiSecici
      kisiler={kisiler}
      deger={deger}
      degisti={degisti}
      yerTutucu="Teknisyen adı, öbek ya da BOSS ekibi…"
      bosMetin="Bu adla teknisyen yok."
      enCok={6}
    />
  );
}

/* ------------------------------ Öbek seçici ------------------------------ */

export function ObekSecici({
  obekler,
  deger,
  sec,
  bos = 'Öbek bulunamadı.',
}: {
  obekler: Obek[];
  deger?: number | null;
  sec: (o: Obek) => void;
  bos?: string;
}) {
  const [sorgu, setSorgu] = useState('');
  const liste = obekler.filter((o) => eslesir(`${o.ad} ${o.mahalleler.map((m) => `${m.ilce} ${m.mahalle}`).join(' ')}`, sorgu));
  return (
    <div className="ip-obek-secici">
      <input
        className="o-girdi"
        type="search"
        value={sorgu}
        placeholder="Öbek ya da mahalle adı…"
        onChange={(o) => setSorgu(o.target.value)}
        aria-label="Öbek ara"
        autoFocus
      />
      <div className="ip-secim-liste" role="listbox" aria-label="Öbekler">
        {liste.length ? (
          liste.map((o) => (
            <button
              key={o.id}
              type="button"
              role="option"
              aria-selected={o.id === deger}
              className={o.id === deger ? 'secili' : undefined}
              onClick={() => sec(o)}
            >
              <ObekNoktasi renk={o.renk} />
              <span className="ad">{o.ad}</span>
              <span className="bilgi">
                {o.mahalleler.length ? `${o.mahalleler.length} mahalle` : 'mahalle yok'}
                {o.sahip ? ` · ${kisaAd(o.sahip.ad)}` : ''}
              </span>
            </button>
          ))
        ) : (
          <p className="o-kisi-bos">{bos}</p>
        )}
      </div>
    </div>
  );
}

/* ------------------------------ küçükler ------------------------------ */

export function Bolum({ baslik, children, sag }: { baslik: ReactNode; children: ReactNode; sag?: ReactNode }) {
  return (
    <section className="ip-bolum">
      <header>
        <h3>{baslik}</h3>
        {sag}
      </header>
      {children}
    </section>
  );
}

export function kisiAdi(k: Kisi | null | undefined): string {
  return k ? kisaAd(k.ad) : '—';
}

/** İşin satır başlığı için yer metni: "Görükle · Çınar Sitesi" (ya da ilçe · mahalle). */
export function yerMetni(s: IsSatir): string {
  if (s.kisa_adres) return s.kisa_adres;
  return [s.mahalle, s.ilce].filter(Boolean).join(' · ') || 'Yer bilinmiyor';
}
