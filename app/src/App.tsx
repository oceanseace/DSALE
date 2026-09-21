/**
 * Uygulama kabuğu: mod seçimi (Sunum ↔ Keşif) ve global tuşlar.
 *
 *  K  → mod değiştirir (sunum ↔ keşif)
 *  F  → tam ekran
 *  O  → dosyadan plan açar (Dosya › Plan Aç… ile aynı)
 * Sahne tuşları (→ ← 1..0 F film) ilgili modun içinde ele alınır.
 */
import { useEffect } from 'react';

import { useUygulama } from './core/uygulama';
import { kontratGuncelle } from './core/kontrat';
import { tamEkranDegistir } from './core/platform';
import Sunum from './sunum/Sunum';
import Kesif from './kesif/Kesif';
import { renk, u, boy, yazi } from './ui/tema';

export default function App() {
  const { mod, setMod, planAc, bildirim } = useUygulama();

  useEffect(() => {
    const tus = (e: KeyboardEvent) => {
      const hedef = e.target as HTMLElement | null;
      if (hedef && /^(INPUT|TEXTAREA|SELECT)$/.test(hedef.tagName)) return;
      if (e.ctrlKey || e.altKey || e.metaKey) return;
      const k = e.key.toLocaleLowerCase('tr-TR');
      if (k === 'k') {
        e.preventDefault();
        setMod(mod === 'sunum' ? 'kesif' : 'sunum');
      } else if (k === 'f') {
        // F: sunumda "film" tuşudur; tam ekran Shift+F ile
        if (e.shiftKey) {
          e.preventDefault();
          tamEkranDegistir();
        }
      } else if (k === 'o') {
        e.preventDefault();
        void planAc();
      }
    };
    window.addEventListener('keydown', tus);
    return () => window.removeEventListener('keydown', tus);
  }, [mod, setMod, planAc]);

  useEffect(() => {
    kontratGuncelle({ mod });
  }, [mod]);

  return (
    <>
      {mod === 'kesif' ? <Kesif /> : <Sunum />}
      {bildirim && (
        <div
          key={bildirim.no}
          className="dsale-belir"
          style={{
            position: 'fixed',
            left: '50%',
            transform: 'translateX(-50%)',
            bottom: u(48),
            padding: `${u(14)} ${u(28)}`,
            borderRadius: u(999),
            background: 'rgba(3,7,16,0.92)',
            border: `1px solid ${bildirim.tur === 'hata' ? renk.tehlike : renk.cizgi}`,
            color: bildirim.tur === 'hata' ? renk.tehlike : renk.metin,
            fontFamily: yazi.govde,
            fontSize: u(boy.govde),
            zIndex: 50,
            pointerEvents: 'none',
          }}
        >
          {bildirim.metin}
        </div>
      )}
    </>
  );
}
