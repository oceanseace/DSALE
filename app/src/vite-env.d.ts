/// <reference types="vite/client" />

/** JSON veri paketleri ?raw ile metin olarak gömülür (TS dev JSON'dan tip çıkarmasın). */
declare module '*.json?raw' {
  const icerik: string;
  export default icerik;
}
