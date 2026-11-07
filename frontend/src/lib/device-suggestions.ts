import type { NodeDetail } from "@/api/types";
import type { Lang } from "@/i18n";

const SYMPTOMS: Record<Lang, Record<string, string>> = {
  en: {
    TRAFFIC_COUNTERS_ZERO: "Traffic counters zero", CELL_DOWN: "Cell down", CRC_ERRORS: "CRC errors",
    LINK_DOWN: "Link down", LINK_FLAPPING: "Link flapping", OPTICAL_LEVELS_LOW: "Low optical levels",
    MODULE_UNKNOWN: "Module shows as unknown", SFP_NOT_RECOGNISED: "SFP not recognised", HIGH_CPU: "High CPU",
    BATTERY_ALARM: "Battery alarm", FAN_ALARM: "Fan alarm", GPS_SYNC_LOST: "GPS sync lost",
    ALIGNMENT_LOST: "Antenna alignment lost", LINK_FADING: "Link fading", LACP_BUNDLE_DOWN: "LACP bundle down",
  },
  fi: {
    TRAFFIC_COUNTERS_ZERO: "Liikennelaskurit nollassa", CELL_DOWN: "Solu alhaalla", CRC_ERRORS: "CRC-virheitä",
    LINK_DOWN: "Linkki alhaalla", LINK_FLAPPING: "Linkki katkeilee", OPTICAL_LEVELS_LOW: "Matalat optiset tasot",
    MODULE_UNKNOWN: "Moduuli näkyy tuntemattomana", SFP_NOT_RECOGNISED: "SFP:tä ei tunnisteta", HIGH_CPU: "Korkea suoritinkuorma",
    BATTERY_ALARM: "Akkuhälytys", FAN_ALARM: "Tuuletinhälytys", GPS_SYNC_LOST: "GPS-synkronointi kadonnut",
    ALIGNMENT_LOST: "Antennin suuntaus kadonnut", LINK_FADING: "Linkki häipyy", LACP_BUNDLE_DOWN: "LACP-niputus alhaalla",
  },
};

/** Whole event phrases per language (Finnish needs the genitive). */
const EVENTS: Record<Lang, Record<string, string>> = {
  en: {
    SFP_REPLACEMENT: "after SFP replacement", PATCH_CABLE_CHANGE: "after a patch cable change",
    MODULE_HOT_SWAP: "after a module hot swap", FIRMWARE_UPGRADE: "after a firmware upgrade",
    POWER_OUTAGE: "after a power outage", STORM: "after a storm", HEAVY_SNOW_ICE: "in heavy snow or ice",
    COLD_WEATHER: "in hard frost", MAINTENANCE: "after maintenance",
  },
  fi: {
    SFP_REPLACEMENT: "SFP-vaihdon jälkeen", PATCH_CABLE_CHANGE: "patch-kaapelin vaihdon jälkeen",
    MODULE_HOT_SWAP: "moduulin kuumavaihdon jälkeen", FIRMWARE_UPGRADE: "ohjelmistopäivityksen jälkeen",
    POWER_OUTAGE: "sähkökatkon jälkeen", STORM: "myrskyn jälkeen", HEAVY_SNOW_ICE: "lumi- tai jääkuorman aikana",
    COLD_WEATHER: "kovalla pakkasella", MAINTENANCE: "huollon jälkeen",
  },
};

const normal = new Set(["INTERFACE_UP", "OPTICAL_LEVELS_NORMAL", "ALARMS_CLEARED"]);
const humanize = (code: string) => code.toLowerCase().replace(/[_-]+/g, " ");
const symptom = (code: string, lang: Lang) => SYMPTOMS[lang][code] ?? humanize(code);
const eventPhrase = (code: string, lang: Lang) =>
  EVENTS[lang][code] ?? (lang === "fi" ? `${humanize(code)} jälkeen` : `after ${humanize(code)}`);

const zone = "Europe/Helsinki";
const dateKey = (date: Date) => new Intl.DateTimeFormat("en-CA", { timeZone: zone, year: "numeric", month: "2-digit", day: "2-digit" }).format(date);

/** "08:15" / "8.15" today; "13 Feb 08:15" / "13.2. klo 8.15" otherwise. */
function alarmTime(date: Date, now: Date, lang: Lang): string {
  const time = new Intl.DateTimeFormat(lang === "fi" ? "fi-FI" : "en-GB", { timeZone: zone, hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(date);
  if (dateKey(date) === dateKey(now)) return time;
  if (lang === "fi") {
    return new Intl.DateTimeFormat("fi-FI", { timeZone: zone, day: "numeric", month: "numeric", hour: "numeric", minute: "2-digit", hourCycle: "h23" }).format(date);
  }
  const parts = new Intl.DateTimeFormat("en-GB", { timeZone: zone, day: "numeric", month: "short" }).formatToParts(date);
  return `${parts.find((p) => p.type === "day")?.value} ${parts.find((p) => p.type === "month")?.value} ${time}`;
}

/** Ordered device questions in the UI language; passing now makes Helsinki date handling deterministic in tests. */
export function deviceSuggestions(detail: NodeDetail, now = new Date(), lang: Lang = "en"): string[] {
  const questions: string[] = [];
  const events = (detail.events ?? []).filter((e) => e.detail && Number.isFinite(Date.parse(e.timestamp)));
  const raised = events.filter((e) => e.event_type === "alarm_raised").sort((a, b) => Date.parse(b.timestamp) - Date.parse(a.timestamp));
  const seen = new Set<string>();
  for (const alarm of raised) {
    const key = alarm.detail.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    if (events.some((e) => e.event_type === "alarm_cleared" && Date.parse(e.timestamp) > Date.parse(alarm.timestamp) && e.detail.toLowerCase().startsWith(key))) continue;
    const time = alarmTime(new Date(alarm.timestamp), now, lang);
    questions.push(lang === "fi" ? `${alarm.detail} ${time} alkaen: mitä teen?` : `${alarm.detail} since ${time}: what should I do?`);
    if (questions.length === 2) break;
  }
  const cards = (detail.knowledge ?? []).filter((c) => c.status !== "outdated" && c.status !== "superseded" && !c.scope_note?.startsWith("Not needed") && c.knowledge_type !== "access_info" && c.outcome !== "failed").sort((a, b) => b.confidence - a.confidence);
  let tips = 0;
  for (const card of cards) {
    const code = (card.symptoms ?? []).find((s) => s && !normal.has(s));
    if (!code) continue;
    const event = card.events?.[0];
    const question = event
      ? `${symptom(code, lang)} ${eventPhrase(event, lang)}?`
      : lang === "fi"
        ? `${symptom(code, lang)}: mitä teen?`
        : `${symptom(code, lang)}: what should I do?`;
    if (questions.includes(question)) continue;
    questions.push(question);
    if (++tips === 2) break;
  }
  const id = detail.node.node_id;
  if (detail.knowledge?.some((c) => c.knowledge_type === "access_info"))
    questions.push(lang === "fi" ? `Miten pääsen laitteen ${id} sijaintiin?` : `How do I get to the ${id} site?`);
  if (questions.length < 5)
    questions.push(lang === "fi" ? `Mitä tunnettuja vikoja laitteella ${id} on?` : `What are the known issues on ${id}?`);
  return questions.slice(0, 5);
}
