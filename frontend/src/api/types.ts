export type KnowledgeType =
  | "troubleshooting_rule"
  | "access_info"
  | "device_fact"
  | "procedure"
  | "warning"
  | (string & {});
export type KnowledgeStatus = "confirmed" | "unconfirmed" | "disputed" | "superseded" | "outdated";
export type Outcome = "worked" | "failed" | "unknown";
export type SourceType = "teams" | "email" | "call" | "ticket" | "manual" | (string & {});
export type DeviceType = "transmission" | "aggregation_router" | "base_station" | "microwave_link";
export type Verdict = "worked" | "failed" | "skip";

export interface KnowledgeAction {
  code: string;
  text: string;
}

export interface KnowledgeSource {
  source_id: string;
  source_type: SourceType;
  author: string;
  timestamp: string;
  excerpt?: string;
  note?: string;
}

export interface KnowledgeScope {
  device_type?: DeviceType | "all";
  installed_before?: string;
  firmware_below?: string;
  firmware_at_least?: string;
}

export interface RelatedFailed {
  assertion_id: string;
  summary: string;
  author: string;
  source_type: SourceType;
  date: string;
}

export interface KnowledgeCard {
  assertion_id: string;
  knowledge_ids: string[];
  knowledge_type: KnowledgeType;
  status: KnowledgeStatus;
  outcome: Outcome;
  confidence: number;
  summary: string;
  details?: string;
  actions: KnowledgeAction[];
  avoid: KnowledgeAction[];
  scope: KnowledgeScope;
  scope_text?: string;
  scope_note?: string;
  observed_on: string[];
  valid_from?: string;
  valid_to?: string;
  how_it_applies?: string;
  sources: KnowledgeSource[];
  related_failed?: RelatedFailed[];
  conflicts_with?: KnowledgeCard[];
}

export interface Node {
  node_id: string;
  type: DeviceType;
  install_date: string;
  firmware: string;
  location: string;
  status: "in_service" | "maintenance" | "decommissioned";
}

export type NodeEventType =
  | "alarm_raised"
  | "alarm_cleared"
  | "work_order"
  | "firmware_upgrade"
  | "hw_replacement"
  | "dispatch"
  | (string & {});

export interface NodeEvent {
  event_id: string;
  timestamp: string;
  event_type: NodeEventType;
  detail: string;
  from_firmware?: string | undefined;
  to_firmware?: string | undefined;
  related_thread?: string | undefined;
}

/** Response of GET /api/nodes/{node_id}. */
export interface NodeDetail {
  node: Node;
  knowledge: KnowledgeCard[];
  events: NodeEvent[];
}

export interface Health {
  ok: boolean;
  version?: string;
}

export interface Stats {
  assertions: number;
  valid_assertions: number;
  devices: number;
  sources: number;
  terms: number;
  feedback: number;
}

export interface ChatRequest {
  message: string;
  conversation_id?: string | undefined;
  node_id?: string | undefined;
}

/** Non-streaming JSON fallback response of POST /api/chat. */
export interface ChatResponse {
  conversation_id: string;
  message_id?: string | undefined;
  answer: string;
  cards: KnowledgeCard[];
}

export interface FeedbackRequest {
  message_id?: string | undefined;
  assertion_id: string;
  verdict: Verdict;
  comment?: string | null;
}

export interface FeedbackResponse {
  ok: boolean;
  updated: string[];
  comment_queued: boolean;
}

export type StreamEvent =
  | { type: "meta"; conversation_id: string }
  | { type: "token"; text: string }
  | { type: "cards"; cards: KnowledgeCard[] }
  | { type: "done"; message_id?: string | undefined }
  | { type: "error"; message: string };

export interface StreamHandlers {
  onEvent: (event: StreamEvent) => void;
}

export interface ApiClient {
  mode: "live" | "mock";
  health(signal?: AbortSignal): Promise<Health>;
  nodes(signal?: AbortSignal): Promise<Node[]>;
  node(nodeId: string, signal?: AbortSignal): Promise<NodeDetail>;
  stats(signal?: AbortSignal): Promise<Stats>;
  feedback(req: FeedbackRequest): Promise<FeedbackResponse>;
  /** Resolves when the stream ends. Rejects on network failure or abort. */
  chat(req: ChatRequest, handlers: StreamHandlers, signal?: AbortSignal): Promise<void>;
}
