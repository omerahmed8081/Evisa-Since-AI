import type { KnowledgeAction } from "@/api/types";
import type { Lang } from "@/i18n";

/**
 * Finnish translations of backend vocabulary codes. Cards show the backend's
 * actions_text/avoid_text in English; in Finnish these per-code translations win,
 * falling back to the backend text for unknown codes.
 */
const STEPS_FI: Record<string, string> = {
  CHECK_TRAFFIC_COUNTERS: "Tarkista, että liikennelaskurit kasvavat",
  BOUNCE_INTERFACE: "Ota portti alas ja nosta se takaisin ylös",
  REBOOT_UNIT: "Käynnistä koko laite uudelleen",
  REPLACE_SFP: "Vaihda SFP",
  CLEAN_CONNECTOR: "Puhdista liitin",
  CLEAR_ICE_RADOME: "Poista jää antennin suojakuvusta",
  REPLACE_PSU: "Vaihda virtalähde",
  READD_PORT_CHANNEL_MEMBER: "Poista portti port-channelista ja lisää se takaisin",
  CHECK_TEMP_SENSOR: "Tarkista lämpötila-anturi",
  CHECK_CHASSIS_TEMP: "Tarkista kotelon lämpötila",
  CHECK_MOUNT_BOLTS: "Tarkista antennin kiinnityspultit",
  REALIGN_ANTENNA: "Suuntaa antenni uudelleen",
  REPLACE_FUSE: "Vaihda sulake",
  USE_APPROVED_PART: "Käytä vain hyväksyttyä osaa",
  SET_CONSOLE_BAUD_9600: "Aseta konsolin nopeudeksi 9600 baudia",
  REPLACE_PATCH_CABLE: "Vaihda patch-kaapeli",
  REPLACE_LINE_CARD: "Vaihda linjakortti",
  COLD_RESTART_BASEBAND: "Tee baseband-yksikölle kylmäkäynnistys",
  WARM_REBOOT: "Tee lämmin uudelleenkäynnistys",
  ENABLE_ATPC: "Ota ATPC (automaattinen lähetystehon säätö) käyttöön",
  WAIT_INVENTORY_REFRESH: "Odota, että inventaario päivittyy",
  RESEAT_MODULE: "Irrota moduuli ja asenna se uudelleen",
  NO_DISPATCH_NEEDED: "Paikalle ei tarvitse lähteä",
};

/** Finnish negatives are not "Älä + step", so these are written out per code. */
const AVOID_FI: Record<string, string> = {
  REPLACE_SFP: "Älä vaihda SFP:tä",
  REBOOT_UNIT: "Älä käynnistä koko laitetta uudelleen",
  REPLACE_LINE_CARD: "Älä vaihda linjakorttia",
  WARM_REBOOT: "Älä tee lämmintä uudelleenkäynnistystä",
  RESEAT_MODULE: "Älä irrota moduulia",
  REPLACE_PSU: "Älä vaihda virtalähdettä",
};

/** Step text for a card action in the active language. */
export function actionText(a: KnowledgeAction, lang: Lang): string {
  if (lang === "fi") return STEPS_FI[a.code] ?? a.text;
  return a.text;
}

/** Avoid text for a card action; unknown codes become "Vältä: <step>" in Finnish. */
export function avoidText(a: KnowledgeAction, lang: Lang): string {
  if (lang !== "fi") return a.text;
  const step = STEPS_FI[a.code];
  return AVOID_FI[a.code] ?? (step ? `Vältä: ${step}` : a.text);
}
