/**
 * Araç çubuğundaki "Sütunlar ▾": bütün sütunlar (temel + BOSS listesindeki her alan, Türkçe adıyla)
 * işaretle göster / kaldır gizle; arama; "Varsayılana dön". Seçim kişi başına saklanır (sutunDuzeni.ts).
 * SIRA burada değişir: üstteki "Sıra" listesinde sütunu yukarı/aşağı sürükle ya da ↑/↓ (düzende saklanır).
 * Tablo başlığında sürüklemek sütun TAŞIMAZ, Excel gibi sütun aralığı seçer. Genişlik başlığın kenarından.
 * Giriş: <SutunSecici …/>. Kim: Isler.tsx.
 */

import { useCallback, useMemo, useRef, useState } from 'react';
import { eslesir } from '../../../cekirdek/ortak/ara';
import { useDisariKapat, useEkranaSigdir } from './acilir';
import type { SutunDuzeni } from './sutunDuzeni';
import type { Sutun } from './sutunlar';

export function SutunSecici({ sutunlar, duzen }: { sutunlar: Sutun[]; duzen: SutunDuzeni }) {
  const [acik, setAcik] = useState(false);
  const [ara, setAra] = useState('');
  const kok = useRef<HTMLDivElement>(null);
  const kapat = useCallback(() => setAcik(false), []);
  useDisariKapat(kok, kapat, acik);
  const acilirRef = useRef<HTMLDivElement>(null);
  useEkranaSigdir(acilirRef, acik);

  const gorunur = useMemo(() => new Set(duzen.gorunenIdler), [duzen.gorunenIdler]);
  const uyan = sutunlar.filter((c) => eslesir(c.baslik, ara));
  const temel = uyan.filter((c) => c.grup === 'temel');
  const boss = uyan.filter((c) => c.grup === 'boss');
  const bossToplam = sutunlar.filter((c) => c.grup === 'boss').length;

  /* Sıra listesi: görünen sütunlar ekrandaki sırayla. Konumlar düzenin kimlik listesine (gorunenIdler) göre. */
  const [surukle, setSurukle] = useState<string | null>(null);
  const [hedef, setHedef] = useState<{ id: string; alt: boolean } | null>(null);
  const idler = duzen.gorunenIdler;
  const konum = (id: string) => idler.indexOf(id);
  const sira = duzen.gorunen;
  const tasi = (id: string, h: number) => duzen.siraYaz(id, h);
  const birak = () => {
    if (surukle && hedef) tasi(surukle, konum(hedef.id) + (hedef.alt ? 1 : 0));
    setSurukle(null);
    setHedef(null);
  };

  const kutu = (c: Sutun) => (
    <label key={c.id} className="xg-sutun-sec">
      <input type="checkbox" checked={gorunur.has(c.id)} onChange={(o) => duzen.goster(c.id, o.target.checked)} />
      <span>{c.baslik}</span>
    </label>
  );

  return (
    <div className="xg-bolunmus" ref={kok}>
      <button type="button" className="xg-arac-dugme" aria-expanded={acik} onClick={() => setAcik((a) => !a)}>
        Sütunlar ({duzen.gorunen.length}/{sutunlar.length}) ▾
      </button>
      {acik ? (
        <div ref={acilirRef} className="xg-acilir xg-sutunlar" role="dialog" aria-label="Sütunlar">
          <input className="o-girdi kucuk" type="search" value={ara} autoFocus placeholder="Sütun ara…" onChange={(o) => setAra(o.target.value)} />
          {!ara.trim() && sira.length > 1 ? (
            <>
              <div className="xg-menu-etiket">Sıra — sürükleyin ya da ↑ ↓</div>
              <div className="xg-sira-liste" role="list" aria-label="Sütun sırası">
                {sira.map((c, i) => (
                  <div
                    key={c.id}
                    role="listitem"
                    className={`xg-sira${surukle === c.id ? ' surukleniyor' : ''}${hedef?.id === c.id && surukle !== c.id ? (hedef.alt ? ' hedef-alt' : ' hedef-ust') : ''}`}
                    draggable
                    onDragStart={(o) => {
                      o.dataTransfer.effectAllowed = 'move';
                      o.dataTransfer.setData('text/plain', c.id);
                      setSurukle(c.id);
                    }}
                    onDragOver={(o) => {
                      if (!surukle) return;
                      o.preventDefault();
                      const k = o.currentTarget.getBoundingClientRect();
                      const alt = o.clientY > k.top + k.height / 2;
                      if (hedef?.id !== c.id || hedef.alt !== alt) setHedef({ id: c.id, alt });
                    }}
                    onDrop={(o) => {
                      o.preventDefault();
                      birak();
                    }}
                    onDragEnd={() => {
                      setSurukle(null);
                      setHedef(null);
                    }}
                  >
                    <span className="xg-sira-tutamak" aria-hidden="true">
                      ⠿
                    </span>
                    <span className="xg-sira-ad">{c.baslik}</span>
                    <button
                      type="button"
                      className="xg-sira-dugme"
                      disabled={i === 0}
                      aria-label={`${c.baslik} yukarı`}
                      title="Yukarı (sola)"
                      onClick={() => tasi(c.id, konum(sira[i - 1].id))}
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      className="xg-sira-dugme"
                      disabled={i === sira.length - 1}
                      aria-label={`${c.baslik} aşağı`}
                      title="Aşağı (sağa)"
                      onClick={() => tasi(c.id, konum(sira[i + 1].id) + 1)}
                    >
                      ↓
                    </button>
                  </div>
                ))}
              </div>
            </>
          ) : null}
          <div className="xg-sutun-liste">
            {temel.length ? <div className="xg-menu-etiket">Temel sütunlar</div> : null}
            {temel.map(kutu)}
            <div className="xg-menu-etiket">BOSS alanları{bossToplam ? ` (${bossToplam})` : ''}</div>
            {boss.map(kutu)}
            {!bossToplam ? <div className="xg-not">BOSS alanları henüz gelmedi; liste tazelenince burada görünür.</div> : null}
          </div>
          <div className="xg-menu-alt">
            <span className="xg-bosluk" />
            <button type="button" className="o-dugme kucuk" onClick={duzen.varsayilan}>
              Varsayılana dön
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
