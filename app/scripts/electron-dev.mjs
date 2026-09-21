#!/usr/bin/env node
/**
 * Geliştirme kabuğu: Vite sunucusunu başlatır ve Electron'u o adrese bağlar.
 * Electron kapanınca sunucu da kapanır.  Kullanım:  npm run electron:dev
 */
import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';

const APP = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

const sunucu = await createServer({ configFile: path.join(APP, 'vite.config.ts'), root: APP, server: { port: 5178 } });
await sunucu.listen();
const adres = sunucu.resolvedUrls?.local?.[0] ?? `http://localhost:${sunucu.config.server.port}/`;
sunucu.printUrls();

const electron = (await import('electron')).default;
const cocuk = spawn(String(electron), [APP, ...process.argv.slice(2)], {
  stdio: 'inherit',
  env: { ...process.env, DSALE_DEV_URL: adres },
});

cocuk.on('close', async (kod) => {
  await sunucu.close();
  process.exit(kod ?? 0);
});
