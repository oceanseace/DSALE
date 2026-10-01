/**
 * Preload — yalnız `window.dsaleMasaustu` köprüsünü açar (contextIsolation açık).
 * Uygulama tarafı: src/core/platform.ts
 */
const { contextBridge, ipcRenderer } = require('electron');

function abone(kanal, cb) {
  const sarmal = (_olay, veri) => cb(veri);
  ipcRenderer.on(kanal, sarmal);
  return () => ipcRenderer.removeListener(kanal, sarmal);
}

contextBridge.exposeInMainWorld('dsaleMasaustu', {
  surum: process.versions.electron,
  planAc: () => ipcRenderer.invoke('dsale:planAc'),
  onPlanYuklendi: (cb) => abone('dsale:plan', cb),
  onModDegistir: (cb) => abone('dsale:mod', cb),
  tamEkranDegistir: () => ipcRenderer.invoke('dsale:tamEkran'),
  tamEkranMi: () => ipcRenderer.invoke('dsale:tamEkranMi'),
});
