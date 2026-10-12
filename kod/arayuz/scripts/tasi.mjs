// Dosya taşır ve src içindeki bütün göreli içe aktarmaları yeni yere göre düzeltir.
//   node scripts/tasi.mjs <eski> <yeni>        (yollar src'ye göre, ör. birimler/saha/x.ts cekirdek/ortak/x.ts)
// Ardından: npm run typecheck ve npm run sinir
import { readFileSync, writeFileSync, mkdirSync, readdirSync, statSync, renameSync } from 'node:fs';
import { join, dirname, relative, posix } from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const SRC = join(dirname(fileURLToPath(import.meta.url)), '..', 'src');
const [eski, yeni] = process.argv.slice(2);
if (!eski || !yeni) {
  console.error('kullanım: node scripts/tasi.mjs <eski> <yeni>');
  process.exit(1);
}

const hepsi = (d) =>
  readdirSync(d).flatMap((a) => {
    const t = join(d, a);
    return statSync(t).isDirectory() ? hepsi(t) : [relative(SRC, t).replaceAll('\\', '/')];
  });
const dosyalar = hepsi(SRC);
if (!dosyalar.includes(eski)) {
  console.error('yok:', eski);
  process.exit(1);
}
const yer = (f) => (f === eski ? yeni : f);
const uzantisiz = (f) => f.replace(/\.(tsx?|jsx?)$/, '');
const goreli = (kimden, hedef) => {
  const r = posix.relative(posix.dirname(kimden), hedef);
  return r.startsWith('.') ? r : './' + r;
};
const UZANTI = ['', '.ts', '.tsx', '.js', '.css'];
const KALIP = /(from\s+|import\s*\(\s*|import\s+|@import\s+)(['"])(\.{1,2}\/[^'"]*)\2/g;

let degisen = 0;
for (const f of dosyalar.filter((d) => /\.(tsx?|jsx?|css)$/.test(d))) {
  const metin = readFileSync(join(SRC, f), 'utf8');
  const cikti = metin.replace(KALIP, (tum, on, t, spec) => {
    const taban = posix.normalize(posix.join(posix.dirname(f), spec));
    const u = UZANTI.find((x) => dosyalar.includes(taban + x));
    if (u === undefined) return tum;
    const hedef = taban + u;
    if (hedef !== eski && f !== eski) return tum;
    const yeniHedef = u ? (u === '.css' || u === '.js' && spec.endsWith('.js') ? yer(hedef) : uzantisiz(yer(hedef))) : yer(hedef);
    return `${on}${t}${goreli(yer(f), yeniHedef)}${t}`;
  });
  if (cikti !== metin) {
    writeFileSync(join(SRC, f), cikti);
    degisen++;
  }
}
mkdirSync(dirname(join(SRC, yeni)), { recursive: true });
try {
  execFileSync('git', ['mv', eski, yeni], { cwd: SRC, stdio: 'pipe' });
} catch {
  renameSync(join(SRC, eski), join(SRC, yeni));
}
console.log(`${eski} → ${yeni} · ${degisen} dosyada içe aktarma düzeltildi`);
