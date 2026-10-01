/**
 * Yalnız kabuğun KENDİ yerel ekranlarına (file://) küçük bir köprü açar.
 * Sunucudan yüklenen yönetici arayüzü (http://127.0.0.1) bu köprüyü GÖRMEZ.
 */
'use strict';
const { contextBridge, ipcRenderer } = require('electron');

if (window.location.protocol === 'file:') {
  contextBridge.exposeInMainWorld('dehanet', {
    durum: () => ipcRenderer.invoke('dehanet:durum'),
    ayarlar: () => ipcRenderer.invoke('dehanet:ayarlar'),
    telefon: () => ipcRenderer.invoke('dehanet:telefon'),
    eylem: (ad, veri) => ipcRenderer.invoke('dehanet:eylem', ad, veri),
    dinle: (geriCagir) => {
      const f = (_olay, d) => geriCagir(d);
      ipcRenderer.on('dehanet:durum', f);
      return () => ipcRenderer.removeListener('dehanet:durum', f);
    },
  });
}
