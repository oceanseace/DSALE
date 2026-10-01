/**
 * Sahne sırası = sahne numarası. Dizi uzunluğu `sahneSayisi`dır ve 1–9/0 tuşları buna bakar.
 */
import type { SahneTanimi } from '../motor/tipler';
import s01Acilis from './s01Acilis';
import s02Guc from './s02Guc';
import s03Firsat from './s03Firsat';
import s04NasilBolduk from './s04NasilBolduk';
import s05SekizBolge from './s05SekizBolge';
import s06BolgeTuru from './s06BolgeTuru';
import s07Yalova from './s07Yalova';
import s08Denge from './s08Denge';
import s09Buyume from './s09Buyume';
import s10Kapanis from './s10Kapanis';

export const SAHNELER: SahneTanimi[] = [
  s01Acilis,
  s02Guc,
  s03Firsat,
  s04NasilBolduk,
  s05SekizBolge,
  s06BolgeTuru,
  s07Yalova,
  s08Denge,
  s09Buyume,
  s10Kapanis,
];

export default SAHNELER;
