import {
  driftChangeSummary,
  driftNeedsHealing,
  parseSemantic,
  severityLabel,
  type DriftLog,
} from "../api";

interface Props {
  logs: DriftLog[];
  emptyMessage?: string;
  onlyActive?: boolean;
}

export default function DriftPanel({
  logs,
  emptyMessage = "No active drift events for this product.",
  onlyActive = true,
}: Props) {
  const visible = onlyActive ? logs.filter((l) => !l.healed) : logs;

  if (!visible.length) {
    return <p className="empty">{emptyMessage}</p>;
  }

  return (
    <table className="table">
      <thead>
        <tr>
          <th>Page</th>
          <th>Score</th>
          <th>Change</th>
          <th>Severity</th>
          <th>Needs healing</th>
          <th>Detected</th>
        </tr>
      </thead>
      <tbody>
        {visible.map((log) => {
          const semantic = parseSemantic(log.semantic_diff);
          const needsHealing = driftNeedsHealing(log);
          return (
            <tr key={log.id}>
              <td>
                <strong>{log.node_title || "Untitled"}</strong>
                <div className="meta-line">{log.node_url}</div>
              </td>
              <td>{log.visual_diff_score?.toFixed(3) ?? "—"}</td>
              <td>{driftChangeSummary(semantic)}</td>
              <td>{severityLabel(semantic) ?? "—"}</td>
              <td>
                <span className={needsHealing ? "status-yes" : "status-no"}>
                  {needsHealing ? "Yes" : "No"}
                </span>
              </td>
              <td>{log.detected_at ? new Date(log.detected_at).toLocaleString() : "—"}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export function recheckEventsToLogs(
  events: RecheckDriftEvent[],
  detectedAt: string
): DriftLog[] {
  return events.map((event) => ({
    id: event.drift_log_id,
    node_id: event.node_id,
    node_url: event.url,
    node_title: event.title,
    detected_at: detectedAt,
    visual_diff_score: event.visual_diff_score,
    semantic_diff: event.semantic_diff,
    needs_healing: Boolean(event.needs_healing ?? event.is_meaningful),
    healed: false,
    healed_at: null,
  }));
}

export interface RecheckDriftEvent {
  drift_log_id: string;
  node_id: string;
  url: string;
  title: string | null;
  visual_diff_score: number;
  semantic_diff: string | Record<string, unknown>;
  is_meaningful: boolean;
  needs_healing?: boolean;
}
