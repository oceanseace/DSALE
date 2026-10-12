// Birim sınırı denetimi. Kural:
//   cekirdek/  hiçbir birimi içe aktaramaz
//   birimler/X yalnız cekirdek'i ve kendi klasörünü içe aktarır (başka birimi değil)
//   App.tsx ve Konsol.tsx birimleri birbirine bağlayan tek yerdir
//   + odak kuralı: odak taşıyan useEffect her çizimde değişen geri çağrıya (kapat, cevap …) bağlı olmaz
//   node scripts/sinir.mjs
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, dirname, relative, posix } from 'node:path';
import { fileURLToPath } from 'node:url';

const SRC = join(dirname(fileURLToPath(import.meta.url)), '..', 'src');
const hepsi = (d) =>
  readdirSync(d).flatMap((a) => {
    const t = join(d, a);
    return statSync(t).isDirectory() ? hepsi(t) : [relative(SRC, t).replaceAll('\\', '/')];
  });
const KALIP = /(?:from\s+|import\s*\(\s*|import\s+|@import\s+)['"](\.{1,2}\/[^'"]+)['"]/g;

const ihlaller = [];
for (const f of hepsi(SRC).filter((d) => /\.(tsx?|css)$/.test(d))) {
  const [kok, birim] = f.split('/');
  for (const [, spec] of readFileSync(join(SRC, f), 'utf8').matchAll(KALIP)) {
    const [hKok, hBirim] = posix.normalize(posix.join(posix.dirname(f), spec)).split('/');
    if (kok === 'cekirdek' && hKok === 'birimler') ihlaller.push(`${f} → birimler/${hBirim} (çekirdek birim tanımaz)`);
    if (kok === 'birimler' && hKok === 'birimler' && birim !== hBirim) ihlaller.push(`${f} → birimler/${hBirim}`);
  }
}
// Odak kuralı (08.10 "Yeni kişi" hatası): odak taşıyan bir useEffect, her çizimde değişen geri çağrıya (kapat,
// cevap …) bağlı OLMAZ — yoksa her tuş vuruşunda etki yeniden kurulur ve yazılan alanın odağı kaçar. Geri çağrıyı
// useRef'te tutun (örnek: cekirdek/ortak/Panel.tsx).
const ODAK_YASAK = /\b(kapat|cevap|bitti|degisti|onClose|onChange|kaydet)\b/;
const odakIhlalleri = [];
for (const f of hepsi(SRC).filter((d) => /\.tsx?$/.test(d))) {
  const k = readFileSync(join(SRC, f), 'utf8').replace(/\r/g, '');
  let i = 0;
  while ((i = k.indexOf('useEffect(', i)) >= 0) {
    const son = /\n\s*\}, \[([^\]]*)\]\);/g;
    son.lastIndex = i;
    const m = son.exec(k);
    if (!m) break;
    const govde = k.slice(i, m.index);
    if (/\.focus\(/.test(govde) && ODAK_YASAK.test(m[1])) {
      odakIhlalleri.push(`${f}:${k.slice(0, i).split('\n').length} odak taşıyan useEffect [${m[1].trim()}]'e bağlı`);
    }
    i = i + 1;
  }
}
if (odakIhlalleri.length) {
  console.error('Odak kuralı ihlali (geri çağrıyı useRef ile tutun; bkz. cekirdek/ortak/Panel.tsx):\n  ' + odakIhlalleri.join('\n  '));
  process.exit(1);
}

if (ihlaller.length) {
  console.error('Birim sınırı ihlali:\n  ' + ihlaller.join('\n  '));
  console.error('Ortak olan parçayı cekirdek/ altına taşıyın: node scripts/tasi.mjs <eski> <yeni>');
  process.exit(1);
}
console.log('birim sınırları temiz · odak kuralı temiz');
