/**
 * Işıklandırma ön ayarları (deck.gl LightingEffect) ve malzeme tanımları.
 */
import { AmbientLight, DirectionalLight, LightingEffect } from '@deck.gl/core';

export type IsikOnAyari = 'gece' | 'gunes' | 'golgeli';

/**
 * 'gece'   : koyu sahne için — yumuşak ortam + kuzeydoğudan sıcak anahtar ışık + güneybatıdan mavi dolgu
 * 'gunes'  : daha parlak, düz
 * 'golgeli': 'gece' + gölgeler (deneysel; büyük ölçekte performansı düşürebilir)
 */
export function isikEfekti(onAyar: IsikOnAyari = 'gece'): LightingEffect {
  const golge = onAyar === 'golgeli';
  const ortam = new AmbientLight({ color: [255, 255, 255], intensity: onAyar === 'gunes' ? 1.25 : 1.0 });
  const anahtar = new DirectionalLight({
    color: [255, 244, 225],
    intensity: onAyar === 'gunes' ? 2.2 : 1.9,
    direction: [-3, -9, -4],
    _shadow: golge,
  });
  const dolgu = new DirectionalLight({
    color: [120, 170, 255],
    intensity: 0.9,
    direction: [4, 6, -2],
  });
  const efekt = new LightingEffect({ ortam, anahtar, dolgu });
  if (golge) efekt.shadowColor = [0, 0, 0.05, 0.55];
  return efekt;
}

/** Bina malzemesi: hafif parlak, renkleri canlı tutar. */
export const BINA_MALZEMESI = {
  ambient: 0.42,
  diffuse: 0.62,
  shininess: 48,
  specularColor: [70, 76, 90] as [number, number, number],
};

/** Sütunlar için daha parlak/cam hissi */
export const SUTUN_MALZEMESI = {
  ambient: 0.55,
  diffuse: 0.55,
  shininess: 96,
  specularColor: [120, 130, 150] as [number, number, number],
};
