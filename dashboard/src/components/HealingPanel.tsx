import { healingSummary, parseSemantic, type DriftLog } from "../api";

interface Props {
  logs: DriftLog[];
}

export default function HealingPanel({ logs }: Props) {
  const healed = logs.filter((l) => l.healed);

  if (!healed.length) {
    return <p className="empty">No healing history for this product yet.</p>;
  }

  return (
    <table className="table">
      <thead>
        <tr>
          <th>Page</th>
          <th>Summary</th>
          <th>Healed at</th>
        </tr>
      </thead>
      <tbody>
        {healed.map((log) => {
          const semantic = parseSemantic(log.semantic_diff);
          return (
            <tr key={log.id}>
              <td>
                <strong>{log.node_title || "Untitled"}</strong>
                <div className="meta-line">{log.node_url}</div>
              </td>
              <td>{healingSummary(semantic)}</td>
              <td>{log.healed_at ? new Date(log.healed_at).toLocaleString() : "—"}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
