/**
 * Sunum motorunun tipleri.
 *
 * Bir sahne üç parçadan oluşur:
 *   1. `kamera(d)`  — adıma göre kamera koreografisi (anında oturtma + uçuş zinciri + yörünge)
 *   2. `katmanlar(b)` — SAF fonksiyon; yalnız (plan, adım, t) girdilerinden deck.gl katmanları üretir
 *   3. `Katman`     — harita üstündeki HTML (manşet, kart, lejant…)
 *
 * `t` adım girişinden itibaren geçen saniyedir; adım değişince sıfırlanır.
 */
import type { ComponentType } from 'react';
import type { LayersList } from '@deck.gl/core';

import type { Boyut, HaritaApi } from '../../map/HaritaSahnesi';
import type { KameraDurumu } from '../../map/kamera';
import type { Meta, Plan } from '../../data/types';
import type { CagriNoktasi } from '../bilesen/Cagrilar';

/** Sahnenin gördüğü uygulama durumu (t hariç). */
export interface SahneDurumu {
  plan: Plan;
  meta: Meta;
  /** etkin plan N */
  n: number;
  /** 1 tabanlı adım */
  adim: number;
  adimSayisi: number;
  /** film (otomatik oynatma) açık mı */
  film: boolean;
  boyut: Boyut;
}

/** Katman üretimi için durum + sahne saati. */
export interface SahneBaglami extends SahneDurumu {
  /** adım girişinden beri geçen saniye */
  t: number;
}

/** Kamera hedefi: sabit değer ya da haritadan hesaplanan (fitBounds) değer. */
export type KameraDegeri = Partial<KameraDurumu> | ((y: KameraYardimi) => Partial<KameraDurumu>);

export interface KameraYardimi {
  api: HaritaApi;
  durum: SahneDurumu;
}

export interface KameraAdimi {
  durum: KameraDegeri;
  /** ms (varsayılan 2000) */
  sureMs?: number;
  tur?: 'fly' | 'linear';
  egri?: number;
}

export interface SahneKamerasi {
  /** adım girişinde anında oturtulacak kamera (kesme) */
  bas?: KameraDegeri;
  /** sırayla oynatılacak uçuşlar */
  adimlar?: KameraAdimi[];
  /** uçuşlar bittikten sonra yörünge hızı (derece/saniye); 0/undefined = yok */
  orbit?: number;
}

export interface SahneTanimi {
  /** kısa kimlik, ör. 'acilis' */
  id: string;
  /** sahne adı (ilerleme noktaları ipucu) */
  ad: string;
  /** adım sayısı (varsayılan 1) */
  adimSayisi?: (plan: Plan) => number;
  /** film modunda adımın ekranda kalma süresi (ms) */
  filmMs: (adim: number, plan: Plan) => number;
  /**
   * Giriş animasyonunun bitiş süresi (ms). QA `mesgul` bayrağı bu süre boyunca açık kalır,
   * böylece ekran görüntüsü sahne oturduktan sonra alınır.
   */
  girisMs?: number;
  kamera?: (d: SahneDurumu) => SahneKamerasi;
  katmanlar: (b: SahneBaglami) => LayersList;
  /** harita üstü HTML */
  Katman?: ComponentType<{ b: SahneBaglami }>;
  /** harita üstünde konumlanan HTML çağrı balonları (Sunum tek bir katmanda çizer) */
  cagrilar?: (d: SahneDurumu) => CagriNoktasi[];
  /** HTML katmanı sahne saatine (t) bağlı mı — bağlıysa 10 Hz'lik yavaş saat açılır */
  htmlSaati?: boolean;
  /** yavaş saatin duracağı saniye (boşuna render olmasın) */
  htmlSaatiBitis?: number;
}
