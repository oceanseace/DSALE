/**
 * "Sunucuya ulaşılamıyor" ince şeridi (§6.13) — yönetim kabuğu ve teknik.
 *
 * Tarayıcının "çevrimdışı" demesi yetmez: ofiste Wi-Fi açıkken sunucu
 * bilgisayarı kapalı olabilir. Bu yüzden şerit, sekme görünürken 30 sn'de bir
 * `/api/saglik`'a küçük bir yoklama yapar; iki üst üste başarısızlıkta çıkar,
 * ilk başarıda kaybolur. Ekrandaki bilgi silinmez; yalnız ne kadar eski olduğu
 * söylenir ("son güncelleme 14:05").
 *
 * Hiçbir şeye tıklamak gerekmez; iş akışını bekletmez.
 */

import { useEffect, useRef, useState } from 'react';
import { Uyari } from './Ikon';
import './bilesen.css';

const ARALIK_MS = 30_000;
const ZAMAN_ASIMI_MS = 6_000;

function saatMetni(t: Date): string {
  return t.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
}

async function yokla(): Promise<boolean> {
  const d = new AbortController();
  const sayac = window.setTimeout(() => d.abort(), ZAMAN_ASIMI_MS);
  try {
    const y = await fetch('/api/saglik', { cache: 'no-store', signal: d.signal });
    return y.ok;
  } catch {
    return false;
  } finally {
    window.clearTimeout(sayac);
  }
}

export function BaglantiSeridi({ ek }: { ek?: string }) {
  const [kopuk, setKopuk] = useState(false);
  const sonBasari = useRef<Date>(new Date());
  const hata = useRef(0);

  useEffect(() => {
    let iptal = false;
    const dene = async () => {
      if (document.visibilityState !== 'visible') return;
      const tamam = await yokla();
      if (iptal) return;
      if (tamam) {
        sonBasari.current = new Date();
        hata.current = 0;
        setKopuk(false);
      } else {
        hata.current += 1;
        // Tek bir düşen istek şerit çıkarmaz (Wi-Fi geçişi); ikincisi çıkarır.
        if (hata.current >= 2 || !navigator.onLine) setKopuk(true);
      }
    };
    const sayac = window.setInterval(() => void dene(), ARALIK_MS);
    const cevrimdisi = () => {
      hata.current = 2;
      setKopuk(true);
    };
    const cevrimici = () => void dene();
    const gorunur = () => void dene();
    window.addEventListener('offline', cevrimdisi);
    window.addEventListener('online', cevrimici);
    document.addEventListener('visibilitychange', gorunur);
    return () => {
      iptal = true;
      window.clearInterval(sayac);
      window.removeEventListener('offline', cevrimdisi);
      window.removeEventListener('online', cevrimici);
      document.removeEventListener('visibilitychange', gorunur);
    };
  }, []);

  if (!kopuk) return null;
  return (
    <div className="o-baglanti-seridi" role="status" aria-live="polite">
      <Uyari boyut={16} />
      <span>
        Sunucuya ulaşılamıyor · son güncelleme {saatMetni(sonBasari.current)}
        {ek ? ` · ${ek}` : ''}
      </span>
    </div>
  );
}
