/** Device IDs like TRN-031, BTS-233, AGG-003, MW-405 inside free text. */
export const DEVICE_ID_RE = /\b(?:TRN|BTS|AGG|MW)-\d{3}\b/g;

export type DeviceRefSegment = { kind: "text" | "device"; value: string };

/** Split text into plain segments and device IDs, preserving order. */
export function splitDeviceRefs(text: string): DeviceRefSegment[] {
  const out: DeviceRefSegment[] = [];
  let last = 0;
  for (const m of text.matchAll(DEVICE_ID_RE)) {
    if (m.index > last) out.push({ kind: "text", value: text.slice(last, m.index) });
    out.push({ kind: "device", value: m[0] });
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push({ kind: "text", value: text.slice(last) });
  return out;
}
