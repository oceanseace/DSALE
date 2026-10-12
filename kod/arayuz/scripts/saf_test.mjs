/** Saf-fonksiyon testlerini (test/saf.test.ts) esbuild ile paketleyip node'da koşar. `npm run build` önce bunu çalıştırır. */
import { build } from 'esbuild';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';

const kok = fileURLToPath(new URL('..', import.meta.url));
const dir = mkdtempSync(join(tmpdir(), 'saf-test-'));
const cikti = join(dir, 'saf.test.mjs');
try {
  await build({
    entryPoints: [join(kok, 'test', 'saf.test.ts')],
    bundle: true,
    platform: 'node',
    format: 'esm',
    outfile: cikti,
    logLevel: 'error',
    loader: { '.css': 'empty', '.svg': 'empty', '.png': 'empty' },
    define: { 'import.meta.env': '{"DEV":false}' },
    jsx: 'automatic',
  });
  await import(pathToFileURL(cikti).href);
} catch (e) {
  console.error(e);
  process.exitCode = 1;
} finally {
  rmSync(dir, { recursive: true, force: true });
}
