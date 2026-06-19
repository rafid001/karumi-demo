export interface Product {
  id: string;
  name: string;
  base_url: string;
  created_at?: string | null;
  last_crawled_at?: string | null;
  last_checked_at?: string | null;
  node_count?: number;
}

export interface GraphNode {
  id: string;
  url: string;
  title: string | null;
  metadata: Record<string, unknown>;
}

export interface GraphEdge {
  id: string;
  from_node_id: string;
  to_node_id: string;
  trigger: string | null;
}

export interface Graph {
  product_id: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface DriftLog {
  id: string;
  node_id: string;
  node_url: string | null;
  node_title: string | null;
  detected_at: string | null;
  visual_diff_score: number | null;
  semantic_diff: string | Record<string, unknown> | null;
  needs_healing: boolean;
  healed: boolean;
  healed_at: string | null;
}

export interface DemoStep {
  step: number;
  node_id: string;
  url: string;
  title: string | null;
  action: string;
  narration: string;
  action_result: string | null;
  screenshot_url: string | null;
  executed: boolean;
}

export interface DemoResult {
  run_id: string;
  product_id: string;
  product_name: string;
  persona: string;
  steps: DemoStep[];
}

export interface CrawlStreamEvent {
  event: string;
  url?: string;
  title?: string | null;
  nodes_so_far?: number;
  product_id?: string;
  nodes_discovered?: number;
  edges_discovered?: number;
  pages_visited?: string[];
  detail?: string;
  max_pages?: number;
}

export interface RecheckResult {
  status: string;
  product_id: string | null;
  product_name: string;
  nodes_checked: number;
  nodes_unchanged: number;
  nodes_drifted: number;
  nodes_meaningful: number;
  events: Array<{
    drift_log_id: string;
    node_id: string;
    url: string;
    title: string | null;
    visual_diff_score: number;
    semantic_diff: string | Record<string, unknown>;
    is_meaningful: boolean;
    needs_healing?: boolean;
  }>;
  healing?: {
    healed: number;
    skipped: number;
    failed: number;
  };
}

const API = "";

function formatApiError(text: string): string {
  try {
    const parsed = JSON.parse(text) as { detail?: string };
    if (typeof parsed.detail === "string") return parsed.detail;
  } catch {
    /* plain text */
  }
  return text || "Request failed";
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(formatApiError(await res.text()));
  return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(formatApiError(await res.text()));
  return res.json();
}

export const api = {
  products: () => get<{ products: Product[] }>("/products"),
  graph: (productId: string) => get<Graph>(`/graph?product_id=${productId}`),
  driftLogs: (productId?: string) =>
    get<{ logs: DriftLog[] }>(
      productId ? `/drift/logs?limit=100&product_id=${productId}` : "/drift/logs?limit=100"
    ),
  runDemo: (productId: string, persona: string) =>
    post<DemoResult>("/demo", { product_id: productId, persona, execute: true }),
  health: () => get<{ status: string; llm: { provider: string; status: string } }>("/health"),
  recheckProduct: (productId: string) =>
    post<RecheckResult>(`/products/${productId}/recheck`, {}),
};

export function crawlStream(
  params: { url: string; productName: string; maxPages: number },
  handlers: {
    onEvent: (event: CrawlStreamEvent) => void;
    onError: (message: string) => void;
    onDone: () => void;
  }
): () => void {
  const query = new URLSearchParams({
    url: params.url,
    product_name: params.productName,
    max_pages: String(params.maxPages),
  });
  const source = new EventSource(`/crawl/stream?${query.toString()}`);

  source.onmessage = (message) => {
    try {
      const event = JSON.parse(message.data) as CrawlStreamEvent;
      if (event.event === "heartbeat") return;
      if (event.event === "error") {
        handlers.onError(event.detail || "Crawl failed");
        source.close();
        handlers.onDone();
        return;
      }
      handlers.onEvent(event);
      if (event.event === "done") {
        source.close();
        handlers.onDone();
      }
    } catch {
      handlers.onError("Failed to parse crawl progress");
      source.close();
      handlers.onDone();
    }
  };

  source.onerror = () => {
    if (source.readyState === EventSource.CLOSED) return;
    handlers.onError("Lost connection to crawl stream — is the API running?");
    source.close();
    handlers.onDone();
  };

  return () => source.close();
}

export function parseSemantic(raw: string | Record<string, unknown> | null): Record<string, unknown> {
  if (!raw) return {};
  if (typeof raw === "object") return raw as Record<string, unknown>;
  try {
    return JSON.parse(raw);
  } catch {
    return { summary: raw };
  }
}

export function formatSemanticValue(value: unknown): string {
  if (value == null || value === "") return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) {
    return value.map((item) => formatSemanticValue(item)).filter((s) => s !== "—").join("; ") || "—";
  }
  if (typeof value === "object") {
    const obj = value as Record<string, unknown>;
    if (typeof obj.summary === "string") return obj.summary;
    if (typeof obj.description === "string") return obj.description;
    if (typeof obj.text === "string") return obj.text;
    const parts = Object.entries(obj)
      .filter(([, v]) => v != null && v !== "")
      .map(([k, v]) => `${k}: ${formatSemanticValue(v)}`);
    return parts.length ? parts.join(" · ") : "—";
  }
  return String(value);
}

export function driftNeedsHealing(log: DriftLog): boolean {
  if (log.healed) return false;
  const semantic = parseSemantic(log.semantic_diff);
  return Boolean(semantic.needs_healing ?? semantic.is_meaningful ?? log.needs_healing);
}

export function driftChangeSummary(semantic: Record<string, unknown>): string {
  return formatSemanticValue(
    semantic.changes ?? semantic.change_type ?? semantic.summary ?? semantic.semantic_diff
  );
}

export function healingSummary(semantic: Record<string, unknown>): string {
  return formatSemanticValue(
    semantic.healing_summary ?? semantic.change_summary ?? semantic.changes ?? semantic.summary
  );
}

export function severityLabel(semantic: Record<string, unknown>): string | null {
  const severity = semantic.severity;
  return typeof severity === "string" ? severity : null;
}
