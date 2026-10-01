/**
 * "Yol tarifi" — telefonun kendi harita uygulamasına derin bağlantı.
 * Uygulama içinde navigasyon yapmıyoruz; satışçı zaten alıştığı haritayı
 * kullanıyor. Seçimi hatırlanır, bir dahaki sefere tek dokunuş yeter.
 */

export type HaritaSaglayici = 'google' | 'yandex' | 'apple';

const ANAHTAR = 'saha.harita';

export const SAGLAYICI_ADLARI: Record<HaritaSaglayici, string> = {
  google: 'Google Haritalar',
  yandex: 'Yandex Navi',
  apple: 'Apple Haritalar',
};

export function baglanti(saglayici: HaritaSaglayici, lat: number, lon: number): string {
  const nokta = `${lat.toFixed(6)},${lon.toFixed(6)}`;
  switch (saglayici) {
    case 'yandex':
      return `https://yandex.com.tr/harita/?rtext=~${nokta}&rtt=auto`;
    case 'apple':
      return `https://maps.apple.com/?daddr=${nokta}&dirflg=d`;
    default:
      return `https://www.google.com/maps/dir/?api=1&destination=${nokta}&travelmode=driving`;
  }
}

export function kayitliSaglayici(): HaritaSaglayici | null {
  try {
    const deger = localStorage.getItem(ANAHTAR);
    if (deger === 'google' || deger === 'yandex' || deger === 'apple') return deger;
  } catch {
    /* depolama kapalıysa her seferinde sorulur */
  }
  return null;
}

export function saglayiciyiKaydet(saglayici: HaritaSaglayici) {
  try {
    localStorage.setItem(ANAHTAR, saglayici);
  } catch {
    /* yok sayılır */
  }
}

export function saglayiciyiUnut() {
  try {
    localStorage.removeItem(ANAHTAR);
  } catch {
    /* yok sayılır */
  }
}

/**
 * Telefonda GERÇEKTEN açılabilecek seçenekler.
 *
 * Android'de "Apple Haritalar" satırı gösterilmez: seçilse bile açılmaz ve
 * "bu uygulama bozuk" izlenimi bırakır. iPhone'da Apple Haritalar başa gelir.
 */
export function saglayiciSirasi(): HaritaSaglayici[] {
  const kunye = navigator.userAgent || '';
  const iOS =
    /iPad|iPhone|iPod/.test(kunye) ||
    (navigator.platform === 'MacIntel' && (navigator.maxTouchPoints ?? 0) > 1);
  if (iOS) return ['apple', 'google', 'yandex'];
  return ['google', 'yandex'];
}

export function haritayiAc(saglayici: HaritaSaglayici, lat: number, lon: number) {
  window.open(baglanti(saglayici, lat, lon), '_blank', 'noopener,noreferrer');
}
