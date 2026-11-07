import type { KnowledgeCard, Node, NodeDetail, NodeEvent, Stats } from "./types";

const n = (
  node_id: string,
  type: Node["type"],
  install_date: string,
  firmware: string,
  location: string,
): Node => ({ node_id, type, install_date, firmware, location, status: "in_service" });

export const MOCK_NODES: Node[] = [
  n("TRN-042", "transmission", "2019-05-14", "3.2.4", "Kolari"),
  n("TRN-077", "transmission", "2018-09-03", "3.4.0", "Muonio"),
  n("TRN-015", "transmission", "2017-04-21", "3.4.0", "Kittilä"),
  n("TRN-031", "transmission", "2019-08-30", "3.3.0", "Sodankylä"),
  n("TRN-101", "transmission", "2022-11-10", "5.1.0", "Oulu"),
  n("TRN-112", "transmission", "2023-06-05", "5.2.1", "Rovaniemi"),
  n("TRN-118", "transmission", "2024-02-19", "5.2.3", "Kajaani"),
  n("TRN-023", "transmission", "2018-03-12", "3.3.1", "Rovaniemi"),
  n("TRN-056", "transmission", "2016-10-05", "3.1.4", "Kemijärvi"),
  n("TRN-125", "transmission", "2025-03-03", "5.2.3", "Tampere"),
  n("AGG-003", "aggregation_router", "2020-02-17", "7.3.2", "Oulu"),
  n("AGG-007", "aggregation_router", "2022-05-11", "7.4.0", "Rovaniemi"),
  n("AGG-012", "aggregation_router", "2019-03-08", "7.2.0", "Kajaani"),
  n("AGG-015", "aggregation_router", "2023-09-20", "7.3.5", "Tampere"),
  n("BTS-210", "base_station", "2018-07-25", "2.6.0", "Muonio"),
  n("BTS-233", "base_station", "2019-10-12", "2.4.1", "Kolari"),
  n("BTS-250", "base_station", "2022-09-14", "2.6.0", "Tampere"),
  n("BTS-261", "base_station", "2023-01-30", "2.6.2", "Kittilä"),
  n("BTS-205", "base_station", "2017-11-08", "2.3.4", "Kemijärvi"),
  n("BTS-244", "base_station", "2019-04-17", "2.5.0", "Pello"),
  n("BTS-272", "base_station", "2024-05-22", "2.6.2", "Oulu"),
  n("MW-401", "microwave_link", "2017-06-02", "1.4.0", "Sodankylä"),
  n("MW-405", "microwave_link", "2018-01-30", "1.4.0", "Kittilä"),
  n("MW-412", "microwave_link", "2021-08-16", "1.4.0", "Rovaniemi"),
  n("MW-418", "microwave_link", "2019-05-28", "1.4.0", "Pello"),
];

export const MOCK_STATS: Stats = {
  assertions: 29,
  valid_assertions: 28,
  devices: 25,
  sources: 33,
  terms: 60,
  feedback: 0,
};

const base = {
  actions: [],
  avoid: [],
  observed_on: [],
  sources: [],
} satisfies Partial<KnowledgeCard>;

const trn031Main: KnowledgeCard = {
  assertion_id: "T001-1",
  knowledge_ids: ["T001-1", "E001-1", "T002-1", "E006-1"],
  knowledge_type: "troubleshooting_rule",
  status: "confirmed",
  outcome: "worked",
  confidence: 0.95,
  summary:
    "On older transmission nodes, after SFP replacement the interface can be UP with normal optics but zero traffic; this is a forwarding-state issue, fixed by disabling and re-enabling the interface.",
  actions: [
    { code: "CHECK_TRAFFIC_COUNTERS", text: "Check that the traffic counters are increasing" },
    { code: "BOUNCE_INTERFACE", text: "Disable and re-enable the interface" },
  ],
  avoid: [
    { code: "REBOOT_UNIT", text: "Don't reboot the whole unit" },
    { code: "REPLACE_SFP", text: "Don't replace the SFP" },
  ],
  scope: { device_type: "transmission", installed_before: "2020-01-01", firmware_below: "3.4" },
  scope_text: "Transmission nodes installed before 2020, firmware below 3.4",
  observed_on: ["TRN-031", "TRN-042", "TRN-077"],
  valid_from: "2025-03-12T09:25:00+02:00",
  how_it_applies: "observed on this device",
  sources: [
    {
      source_id: "T001",
      source_type: "teams",
      author: "Erkki Expert",
      timestamp: "2025-03-12T09:14:00+02:00",
      excerpt:
        "Don't trust the green link status on those. Sometimes after changing the SFP the interface comes up normally, but the forwarding state doesn't recover correctly. … Check whether the traffic counters are actually increasing.",
    },
    {
      source_id: "E001",
      source_type: "email",
      author: "Erkki Expert",
      timestamp: "2025-03-12T14:02:00+02:00",
      excerpt:
        "Before replacing the SFP again or rebooting the unit, check the traffic counters. If the interface is UP but the counters remain at zero, try disabling and enabling the interface once.",
    },
    {
      source_id: "T002",
      source_type: "teams",
      author: "Erkki Expert",
      timestamp: "2025-09-04T10:05:00+03:00",
      excerpt: "Ota portti alas, odota hetki ja nosta takaisin. Älä buuttaa koko laitetta.",
    },
    {
      source_id: "E006",
      source_type: "email",
      author: "Erkki Expert",
      timestamp: "2026-02-16T10:20:00+02:00",
      excerpt:
        "Portin disablointi ja enablointi korjasi tilanteen heti. SFP:tä ei tarvinnut vaihtaa eikä laitetta buutata.",
    },
  ],
  related_failed: [
    {
      assertion_id: "T015-1",
      summary:
        "Replacing the SFP again does not fix zero traffic on an older transmission node when the port is up with normal optics.",
      author: "Tiina Tuominen",
      source_type: "teams",
      date: "2025-07-15",
    },
    {
      assertion_id: "T014-1",
      summary:
        "Rebooting the whole older transmission node does not fix zero traffic after SFP replacement and causes a ~20 minute site outage.",
      author: "Mikko Mäkelä",
      source_type: "teams",
      date: "2025-06-30",
    },
  ],
};

const trn031Fw: KnowledgeCard = {
  ...base,
  assertion_id: "E007-1",
  knowledge_ids: ["E007-1"],
  knowledge_type: "troubleshooting_rule",
  status: "confirmed",
  outcome: "worked",
  confidence: 0.7,
  summary:
    "Firmware 3.4 fixes the forwarding-state problem after SFP replacement on older transmission nodes; the interface disable/enable workaround is only needed below 3.4.",
  scope: { device_type: "transmission", firmware_at_least: "3.4" },
  scope_note: "Not yet on TRN-031: only applies from firmware 3.4 upward, device has 3.3.0",
  details: "Fixed in firmware 3.4; TRN-042 and TRN-031 still below 3.4.",
  observed_on: ["TRN-015", "TRN-077"],
  sources: [
    { source_id: "E007", source_type: "email", author: "Erkki Expert", timestamp: "2026-04-08T10:15:00+03:00" },
  ],
};

const bts233Main: KnowledgeCard = {
  assertion_id: "T004-1",
  knowledge_ids: ["T004-1", "C001-1"],
  knowledge_type: "troubleshooting_rule",
  status: "confirmed",
  outcome: "worked",
  confidence: 0.8,
  summary:
    "On older base stations the cell can stay down after a power outage; a normal (warm) reboot does not help, a cold restart of the baseband unit does.",
  actions: [{ code: "COLD_RESTART_BASEBAND", text: "Cold-restart the baseband unit" }],
  avoid: [{ code: "WARM_REBOOT", text: "Don't do a warm reboot" }],
  scope: { device_type: "base_station", installed_before: "2020-01-01", firmware_below: "2.6" },
  scope_text: "Base stations installed before 2020, firmware below 2.6",
  observed_on: ["BTS-210", "BTS-233"],
  sources: [
    { source_id: "T004", source_type: "teams", author: "Sanna Siirto", timestamp: "2024-06-03T08:44:00+03:00" },
    {
      source_id: "C001",
      source_type: "call",
      author: "Sanna Siirto",
      timestamp: "2025-12-10T02:47:00+02:00",
      note: "Night call-out",
    },
  ],
};

const bts233Fw: KnowledgeCard = {
  ...base,
  assertion_id: "T016-1",
  knowledge_ids: ["T016-1"],
  knowledge_type: "troubleshooting_rule",
  status: "confirmed",
  outcome: "worked",
  confidence: 0.7,
  summary:
    "Base station firmware 2.6 fixes the baseband not recovering after a power outage; the cold-restart workaround is only needed below 2.6.",
  scope: { device_type: "base_station", firmware_at_least: "2.6" },
  scope_note: "Not yet on BTS-233: only applies from firmware 2.6 upward, device has 2.4.1",
  observed_on: ["BTS-233"],
  sources: [{ source_id: "T016", source_type: "teams", author: "Sanna Siirto", timestamp: "2026-03-02" }],
};

const accessCard: KnowledgeCard = {
  ...base,
  assertion_id: "E008-1",
  knowledge_ids: ["E008-1"],
  knowledge_type: "access_info",
  status: "unconfirmed",
  outcome: "unknown",
  confidence: 0.5,
  summary:
    "The private road to the TRN-042 / BTS-233 site near Kolari has a locked barrier; the key is in a lockbox at the neighbouring farm (red house before the barrier), code 2580.",
  details: "Lockbox code 2580; red house right before the barrier; return the key.",
  scope: {},
  scope_text: "Only the devices it was seen on: BTS-233, TRN-042",
  observed_on: ["BTS-233", "TRN-042"],
  sources: [
    { source_id: "E008", source_type: "email", author: "Tiina Tuominen", timestamp: "2024-11-20T16:05:00+02:00" },
  ],
};

const aggCard: KnowledgeCard = {
  assertion_id: "E002-1",
  knowledge_ids: ["E002-1", "T012-1"],
  knowledge_type: "troubleshooting_rule",
  status: "confirmed",
  outcome: "worked",
  confidence: 0.8,
  summary:
    "On aggregation routers, CRC errors on an uplink right after cable work are almost always caused by the patch cable; replace the patch cable before replacing the line card.",
  actions: [{ code: "REPLACE_PATCH_CABLE", text: "Replace the patch cable" }],
  avoid: [{ code: "REPLACE_LINE_CARD", text: "Don't replace the line card first" }],
  scope: { device_type: "aggregation_router" },
  scope_text: "All aggregation routers",
  observed_on: ["AGG-003", "AGG-012"],
  sources: [
    { source_id: "E002", source_type: "email", author: "Antti Aalto", timestamp: "2024-11-20T13:30:00+02:00" },
    { source_id: "T012", source_type: "teams", author: "Antti Aalto", timestamp: "2025-01-28T08:41:00+02:00" },
  ],
};

const mwIce: KnowledgeCard = {
  ...base,
  assertion_id: "T003-1",
  knowledge_ids: ["T003-1"],
  knowledge_type: "troubleshooting_rule",
  status: "disputed",
  outcome: "worked",
  confidence: 0.7,
  summary:
    "When a microwave link flaps during heavy snow or icing, check the radome for ice before touching the radio; clearing the ice restores the link.",
  actions: [{ code: "CLEAR_ICE_RADOME", text: "Check and clear ice from the radome" }],
  scope: { device_type: "microwave_link" },
  scope_text: "All microwave links",
  observed_on: ["MW-405"],
  sources: [
    { source_id: "T003", source_type: "teams", author: "Erkki Expert", timestamp: "2024-01-18T10:38:00+02:00" },
  ],
};

const mwPsu: KnowledgeCard = {
  ...base,
  assertion_id: "T017-1",
  knowledge_ids: ["T017-1"],
  knowledge_type: "troubleshooting_rule",
  status: "disputed",
  outcome: "unknown",
  confidence: 0.5,
  summary:
    "Jari claims microwave link drops in hard frost are caused by the outdoor unit power supply, not ice, and that the PSU should be replaced; not confirmed.",
  actions: [{ code: "REPLACE_PSU", text: "Replace the outdoor unit power supply" }],
  details: "-32 C, no ice on radome.",
  scope: { device_type: "microwave_link" },
  scope_text: "All microwave links",
  observed_on: ["MW-405"],
  sources: [
    { source_id: "T017", source_type: "teams", author: "Jari Jänne", timestamp: "2024-01-25T21:46:00+02:00" },
  ],
  conflicts_with: [mwIce],
};

export interface MockScenario {
  id: string;
  match: (text: string) => boolean;
  answer: string;
  cards: KnowledgeCard[];
}

const has = (t: string, ...words: string[]) => words.some((w) => t.includes(w));

export const MOCK_SCENARIOS: MockScenario[] = [
  {
    id: "access",
    match: (t) => has(t, "how do i get", "gate", "barrier", "access", "kolari", "road"),
    answer:
      "The road to the TRN-042 / BTS-233 site near Kolari has a locked barrier. The key is in a lockbox at the neighbouring farm (the red house just before the barrier), code **2580**. Please return the key.\n\nSource: Tiina Tuominen (email, 20 Nov 2024).",
    cards: [accessCard],
  },
  {
    id: "trn031",
    match: (t) => has(t, "trn-031", "sfp", "no traffic"),
    answer:
      "Likely a forwarding-state issue after the SFP swap on an older transmission node.\n\n1. Check that the traffic counters are increasing.\n2. Disable and re-enable the interface.\n\n**Don't** reboot the whole unit or replace the SFP again: both were tried on similar units and didn't help.\n\nConfirmed on 3 devices by 4 sources (Erkki Expert, Teams and email, Mar 2025 – Feb 2026).",
    cards: [trn031Main, trn031Fw],
  },
  {
    id: "bts233",
    match: (t) => has(t, "bts-233", "cell down", "power outage", "sähkökatko"),
    answer:
      "Older base stations can keep the cell down after a power outage. A normal (warm) reboot does not help.\n\n1. Do a cold restart of the baseband unit.\n\n**Don't** do a warm reboot.\n\nBTS-233 runs firmware 2.4.1; the problem is fixed from 2.6, so the workaround still applies here. Confirmed on BTS-210 and BTS-233 by Sanna Siirto (Teams, Jun 2024; night call, Dec 2025).",
    cards: [bts233Main, bts233Fw],
  },
  {
    id: "agg",
    match: (t) => has(t, "agg-003", "crc"),
    answer:
      "CRC errors on an aggregation router uplink right after cable work are almost always the patch cable.\n\n1. Replace the patch cable.\n\n**Don't** replace the line card first.\n\nConfirmed on AGG-012 and AGG-003 by Antti Aalto (email Nov 2024, Teams Jan 2025).",
    cards: [aggCard],
  },
  {
    id: "mw405",
    match: (t) => has(t, "mw-405", "pakka", "frost", "microwave", "linkki"),
    answer:
      "Experts disagree on this one.\n\n- **Erkki Expert:** link drops in snow or icing are caused by ice on the radome; clearing the ice restored the link (confirmed).\n- **Jari Jänne:** in hard frost (-32 °C, no ice) it is the outdoor unit power supply; replace the PSU (not confirmed).\n\nCheck the radome for ice first; if it is clear, report back so the PSU theory can be confirmed or ruled out.",
    cards: [mwPsu],
  },
];

export const NO_KNOWLEDGE_ANSWER =
  "No captured expert knowledge for this yet. Consider asking an expert.";

export function findScenario(message: string, nodeId?: string): MockScenario | null {
  const t = `${message} ${nodeId ?? ""}`.toLowerCase();
  return MOCK_SCENARIOS.find((s) => s.match(t)) ?? null;
}

const ev = (
  event_id: string,
  timestamp: string,
  event_type: NodeEvent["event_type"],
  detail: string,
  related_thread?: string,
  from_firmware?: string,
  to_firmware?: string,
): NodeEvent => ({ event_id, timestamp, event_type, detail, related_thread, from_firmware, to_firmware });

export const MOCK_EVENTS: Record<string, NodeEvent[]> = {
  "TRN-031": [
    ev("EV-0056", "2025-07-15T07:40:00+03:00", "alarm_raised", "LOS on port 1/1/2", "T015"),
    ev("EV-0057", "2025-07-15T11:05:00+03:00", "hw_replacement", "SFP replaced on port 1/1/2", "T015"),
    ev("EV-0058", "2025-07-15T11:38:00+03:00", "hw_replacement", "SFP replaced again on port 1/1/2", "T015"),
    ev("EV-0073", "2026-02-13T08:15:00+02:00", "alarm_raised", "LOS on port 1/1/2", "E006"),
    ev("EV-0074", "2026-02-13T11:20:00+02:00", "hw_replacement", "SFP replaced on port 1/1/2", "E006"),
  ],
  "TRN-042": [
    ev("EV-0028", "2024-11-19T09:00:00+02:00", "dispatch", "Dispatch delayed 2 h: locked barrier on private access road", "E008"),
    ev("EV-0043", "2025-03-12T07:58:00+02:00", "alarm_raised", "LOS on port 1/1/3", "T001"),
    ev("EV-0044", "2025-03-12T08:40:00+02:00", "work_order", "WO-55120: Replace SFP on port 1/1/3, reason: LOS alarm", "T001"),
    ev("EV-0045", "2025-03-12T09:05:00+02:00", "alarm_cleared", "LOS on port 1/1/3 cleared", "T001"),
  ],
  "TRN-077": [
    ev("EV-0060", "2025-09-04T07:20:00+03:00", "alarm_raised", "LOS on port 1/1/2", "T002"),
    ev("EV-0061", "2025-09-04T07:45:00+03:00", "work_order", "WO-58873: Replace SFP on port 1/1/2, reason: LOS alarm", "T002"),
    ev("EV-0062", "2025-09-04T10:02:00+03:00", "alarm_cleared", "LOS on port 1/1/2 cleared", "T002"),
    ev("EV-0078", "2026-03-24T10:00:00+02:00", "firmware_upgrade", "Planned firmware upgrade", "E007", "3.2.1", "3.4.0"),
    ev("EV-0080", "2026-03-31T10:40:00+03:00", "hw_replacement", "SFP replaced on port 1/1/1", "E007"),
  ],
  "BTS-233": [
    ev("EV-0019", "2024-06-03T05:40:00+03:00", "alarm_raised", "Mains power failure", "T004"),
    ev("EV-0020", "2024-06-03T05:41:00+03:00", "alarm_raised", "Cell out of service", "T004"),
    ev("EV-0021", "2024-06-03T07:00:00+03:00", "dispatch", "Field engineer dispatched, cell down after power outage", "T004"),
    ev("EV-0022", "2024-06-03T08:44:00+03:00", "alarm_cleared", "Cell in service", "T004"),
  ],
  "MW-405": [
    ev("EV-0004", "2023-10-18T10:00:00+03:00", "firmware_upgrade", "Planned firmware upgrade", undefined, "1.3.2", "1.4.0"),
    ev("EV-0009", "2024-01-18T06:30:00+02:00", "alarm_raised", "Radio link unstable: repeated link down/up", "T003"),
    ev("EV-0010", "2024-01-18T07:15:00+02:00", "dispatch", "Field engineer dispatched to Kittilä mast", "T003"),
    ev("EV-0011", "2024-01-18T10:38:00+02:00", "alarm_cleared", "Radio link stable", "T003"),
    ev("EV-0012", "2024-01-25T19:50:00+02:00", "alarm_raised", "Radio link down", "T017"),
  ],
  "AGG-003": [
    ev("EV-0013", "2024-03-19T02:00:00+02:00", "alarm_raised", "CPU utilisation 88%", "T010"),
    ev("EV-0014", "2024-03-19T02:14:00+02:00", "alarm_cleared", "CPU utilisation normal", "T010"),
    ev("EV-0033", "2025-01-27T13:00:00+02:00", "work_order", "WO-52031: Rack maintenance, re-patching", "T012"),
    ev("EV-0034", "2025-01-28T08:10:00+02:00", "alarm_raised", "CRC errors on uplink port", "T012"),
    ev("EV-0035", "2025-01-28T08:41:00+02:00", "alarm_cleared", "CRC errors on uplink port cleared", "T012"),
  ],
};

/** All unique cards across scenarios. */
function allCards(): KnowledgeCard[] {
  const seen = new Map<string, KnowledgeCard>();
  for (const s of MOCK_SCENARIOS) for (const c of s.cards) seen.set(c.assertion_id, c);
  return [...seen.values()];
}

/** Firmware 3.4 fixes the forwarding-state problem; below it the interface bounce still applies. */
const FW_FIXED = "3.4";

/** Per-device view of a card: what the device's firmware makes of the rule. */
function applyDeviceFacts(card: KnowledgeCard, node: Node): KnowledgeCard {
  if (node.firmware < FW_FIXED) return card;
  if (card.assertion_id === "T001-1") {
    return {
      ...card,
      status: "outdated",
      scope_note: `Not needed on ${node.node_id}: only applies below firmware ${FW_FIXED}, device has ${node.firmware}`,
    };
  }
  if (card.assertion_id === "E007-1") {
    // The fix is already installed here, so the "not yet" note does not apply.
    const { scope_note, ...rest } = card;
    return rest;
  }
  return card;
}

/** Mock GET /api/nodes/{node_id}: facts + knowledge observed on the device + events. */
export function mockNodeDetail(nodeId: string): NodeDetail | null {
  const node = MOCK_NODES.find((n) => n.node_id === nodeId);
  if (!node) return null;
  const knowledge = allCards()
    .filter((c) => c.observed_on.includes(nodeId))
    .map((c) => applyDeviceFacts(c, node));
  const events = [...(MOCK_EVENTS[nodeId] ?? [])].sort((a, b) => b.timestamp.localeCompare(a.timestamp));
  return { node, knowledge, events };
}
