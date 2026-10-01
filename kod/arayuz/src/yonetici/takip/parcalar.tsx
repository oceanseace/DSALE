/** Takip panelinin küçük parçaları: eğri (sparkline), Türkçe ek, zaman metinleri. */

const AYLAR = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'];
const GUNLER = ['Pazar', 'Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi'];
const iki = (n: number) => String(n).padStart(2, '0');

function oku(metin: string | null | undefined): Date | null {
  if (!metin) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?/.exec(metin);
  if (!m) return null;
  return new Date(+m[1], +m[2] - 1, +m[3], +(m[4] ?? 0), +(m[5] ?? 0));
}

/** "30 Eylül Salı" (sunucu saatiyle; yoksa cihaz). */
export function uzunTarih(sunucuZamani?: string | null): string {
  const d = oku(sunucuZamani) ?? new Date();
  return `${d.getDate()} ${AYLAR[d.getMonth()]} ${GUNLER[d.getDay()]}`;
}

/** "14:05" */
export function saatMetni(metin: string | null | undefined): string {
  const d = oku(metin);
  return d ? `${iki(d.getHours())}:${iki(d.getMinutes())}` : '—';
}

/** Bugünse "14:05", değilse "29.09 14:05". */
export function tarihSaatMetni(metin: string | null | undefined): string {
  const d = oku(metin);
  if (!d) return '—';
  const bugun = new Date();
  const ayni = d.toDateString() === bugun.toDateString();
  return ayni ? `bugün ${saatMetni(metin)}` : `${iki(d.getDate())}.${iki(d.getMonth() + 1)} ${saatMetni(metin)}`;
}

/**
 * Sayının 3. tekil iyelik eki (ses uyumu, sayının okunuşunun son sözcüğüne
 * göre): 62 → "'si", 40 → "'ı", 9 → "'u", 100 → "'ü", 6 → "'sı", 0 → "'ı".
 * "%62'si sözünde bitti" gibi cümleler için.
 */
export function iyelik(n: number): string {
  const birler = ['', 'bir', 'iki', 'üç', 'dört', 'beş', 'altı', 'yedi', 'sekiz', 'dokuz'];
  const onlar = ['', 'on', 'yirmi', 'otuz', 'kırk', 'elli', 'altmış', 'yetmiş', 'seksen', 'doksan'];
  const m = Math.abs(Math.round(n));
  const son =
    m === 0 ? 'sıfır' : m % 10 ? birler[m % 10] : m % 100 ? onlar[Math.floor(m / 10) % 10] : m % 1000 ? 'yüz' : 'bin';
  const unluler = [...son].filter((h) => 'aeıioöuü'.includes(h));
  const u = unluler[unluler.length - 1] ?? 'e';
  const uyum: Record<string, string> = { a: 'ı', ı: 'ı', e: 'i', i: 'i', o: 'u', u: 'u', ö: 'ü', ü: 'ü' };
  const ek = uyum[u] ?? 'i';
  return `'${'aeıioöuü'.includes(son[son.length - 1]) ? 's' : ''}${ek}`;
}

/**
 * Küçük eğri (sparkline): yalnız yön gösterir, değer yazıyla verilir (renk ve
 * çizgi bilgi TAŞIMAZ). En az iki nokta; tek renk (--metin-2), eksen yok.
 */
export function Egri({ degerler, etiket, genis = false }: { degerler: number[]; etiket: string; genis?: boolean }) {
  if (degerler.length < 2) return null;
  const G = genis ? 240 : 120;
  const Y = genis ? 36 : 28;
  const en = Math.min(...degerler);
  const bo = Math.max(...degerler);
  const aralik = bo - en || 1;
  const noktalar = degerler.map((d, i) => {
    const x = (i / (degerler.length - 1)) * (G - 4) + 2;
    const y = Y - 3 - ((d - en) / aralik) * (Y - 6);
    return [x, y] as const;
  });
  const yol = noktalar.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
  const [sx, sy] = noktalar[noktalar.length - 1];
  return (
    <svg className={`tp-egri${genis ? ' genis' : ''}`} viewBox={`0 0 ${G} ${Y}`} role="img" aria-label={etiket} preserveAspectRatio="none">
      <path d={yol} fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
      <circle cx={sx} cy={sy} r="2.6" fill="currentColor" />
    </svg>
  );
}
