from __future__ import annotations

import html
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from h_mesh_gateway.storage import GatewayStorage, parse_iso_timestamp


FAILURE_OBSERVATION_KINDS = (
    "publish_failed",
    "gateway_state_publish_failed",
    "mqtt_receive_timeout",
    "rf_emit_blocked",
)


def tail_text_file(path: Path, *, max_lines: int = 200) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-max_lines:]


def render_sparkline(points: list[int], *, width: int = 220, height: int = 56) -> str:
    if not points:
        return '<svg viewBox="0 0 220 56" width="220" height="56"><text x="10" y="30" fill="#64748b" font-size="12">no data</text></svg>'
    if len(points) == 1:
        points = [points[0], points[0]]
    minimum = min(points)
    maximum = max(points)
    span = max(maximum - minimum, 1)
    step = width / max(len(points) - 1, 1)
    coordinates: list[str] = []
    for index, point in enumerate(points):
        x = round(index * step, 2)
        y = round(height - ((point - minimum) / span) * (height - 8) - 4, 2)
        coordinates.append(f"{x},{y}")
    return (
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        'preserveAspectRatio="none">'
        '<polyline fill="none" stroke="#0f766e" stroke-width="2.5" '
        f'points="{" ".join(coordinates)}" /></svg>'
    )


class ManagementRepository:
    def __init__(self, *, state_dir: Path, log_dir: Path | None = None) -> None:
        self.state_dir = state_dir
        self.log_dir = log_dir or state_dir

    def database_paths(self) -> list[Path]:
        if not self.state_dir.exists():
            return []
        return sorted(self.state_dir.glob("*.sqlite3"))

    def log_paths(self) -> list[Path]:
        if not self.log_dir.exists():
            return []
        return sorted(self.log_dir.glob("*.log"))

    def _storage_for(self, path: Path) -> GatewayStorage:
        return GatewayStorage(path)

    def management_snapshot(self) -> dict[str, object]:
        gateways: list[dict[str, object]] = []
        recent_failures: list[dict[str, object]] = []
        failure_counts: dict[str, int] = {}
        queue_status_totals: dict[str, int] = {}
        total_queue_depth = 0

        for db_path in self.database_paths():
            storage = self._storage_for(db_path)
            latest_health = storage.latest_gateway_health()
            if latest_health is None:
                continue

            queue_depth = int(latest_health["queue_depth"])
            total_queue_depth += queue_depth

            queue_status_counts = storage.queue_status_counts()
            for status, count in queue_status_counts.items():
                queue_status_totals[status] = queue_status_totals.get(status, 0) + count

            observation_counts = storage.count_gateway_observations_by_kind()
            for kind, count in observation_counts.items():
                failure_counts[kind] = failure_counts.get(kind, 0) + count

            health_history = list(reversed(storage.list_gateway_health_snapshots(limit=24)))
            gateways.append(
                {
                    "database_path": str(db_path),
                    "gateway_id": str(latest_health["gateway_id"]),
                    "site_code": str(latest_health["site_code"]),
                    "process_state": str(latest_health["process_state"]),
                    "broker_state": str(latest_health["broker_state"]),
                    "radio_state": str(latest_health["radio_state"]),
                    "queue_depth": queue_depth,
                    "delivery_state": str(latest_health["delivery_state"]),
                    "observed_at": str(latest_health["observed_at"]),
                    "topic": str(latest_health["topic"]),
                    "queue_depth_points": [int(row["queue_depth"]) for row in health_history],
                }
            )

            for observation in storage.list_recent_gateway_observations(
                limit=20,
                kinds=FAILURE_OBSERVATION_KINDS,
            ):
                recent_failures.append(
                    {
                        **observation,
                        "database_path": str(db_path),
                    }
                )

        recent_failures.sort(
            key=lambda row: parse_iso_timestamp(str(row["observed_at"])),
            reverse=True,
        )
        gateways.sort(key=lambda row: str(row["gateway_id"]))

        return {
            "gateway_count": len(gateways),
            "queue_depth_total": total_queue_depth,
            "queue_status_totals": queue_status_totals,
            "failure_counts": failure_counts,
            "gateways": gateways,
            "recent_failures": recent_failures[:25],
        }

    def recent_logs(self, *, max_lines: int = 120) -> list[dict[str, object]]:
        log_entries: list[dict[str, object]] = []
        for log_path in self.log_paths():
            log_entries.append(
                {
                    "path": str(log_path),
                    "name": log_path.name,
                    "lines": tail_text_file(log_path, max_lines=max_lines),
                }
            )
        return log_entries


def render_dashboard_html(snapshot: dict[str, object], logs: list[dict[str, object]]) -> str:
    queue_status_totals = snapshot["queue_status_totals"]
    failure_counts = snapshot["failure_counts"]
    gateways = snapshot["gateways"]
    recent_failures = snapshot["recent_failures"]

    gateway_rows = "".join(
        (
            "<tr>"
            f"<td>{html.escape(str(gateway['gateway_id']))}</td>"
            f"<td>{html.escape(str(gateway['site_code']))}</td>"
            f"<td>{html.escape(str(gateway['process_state']))}</td>"
            f"<td>{html.escape(str(gateway['broker_state']))}</td>"
            f"<td>{html.escape(str(gateway['radio_state']))}</td>"
            f"<td>{int(gateway['queue_depth'])}</td>"
            f"<td>{html.escape(str(gateway['delivery_state']))}</td>"
            f"<td>{html.escape(str(gateway['observed_at']))}</td>"
            f"<td>{render_sparkline(list(gateway['queue_depth_points']))}</td>"
            "</tr>"
        )
        for gateway in gateways
    )

    failure_rows = "".join(
        (
            "<tr>"
            f"<td>{html.escape(str(row['observed_at']))}</td>"
            f"<td>{html.escape(str(row['gateway_id']))}</td>"
            f"<td>{html.escape(str(row['kind']))}</td>"
            f"<td>{html.escape(str(row['detail']))}</td>"
            "</tr>"
        )
        for row in recent_failures
    )

    log_sections = "".join(
        (
            "<details open>"
            f"<summary>{html.escape(str(entry['name']))}</summary>"
            f"<pre>{html.escape(chr(10).join(entry['lines']))}</pre>"
            "</details>"
        )
        for entry in logs
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="15">
  <title>h-mesh management dashboard</title>
  <style>
    :root {{
      --bg: #f4efe6;
      --card: #fffdf7;
      --ink: #14213d;
      --muted: #5c677d;
      --accent: #0f766e;
      --warn: #b45309;
      --border: #d9d4c7;
    }}
    body {{
      margin: 0;
      padding: 24px;
      background: linear-gradient(180deg, #f8f2e7 0%, #eef3f3 100%);
      color: var(--ink);
      font-family: Georgia, "Times New Roman", serif;
    }}
    h1, h2 {{
      margin: 0 0 12px;
    }}
    p {{
      color: var(--muted);
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 14px;
      margin: 18px 0 24px;
    }}
    .card, section {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 16px 18px;
      box-shadow: 0 10px 30px rgba(20, 33, 61, 0.06);
    }}
    .metric {{
      font-size: 2rem;
      font-weight: 700;
      color: var(--accent);
    }}
    .label {{
      color: var(--muted);
      font-size: 0.95rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.95rem;
    }}
    th, td {{
      text-align: left;
      padding: 10px 8px;
      border-bottom: 1px solid var(--border);
      vertical-align: top;
    }}
    th {{
      color: var(--muted);
      font-size: 0.85rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .two-col {{
      display: grid;
      grid-template-columns: 1.4fr 1fr;
      gap: 18px;
    }}
    pre {{
      overflow-x: auto;
      white-space: pre-wrap;
      background: #f8fafc;
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 12px;
      font-family: Consolas, "Courier New", monospace;
      font-size: 0.85rem;
    }}
    @media (max-width: 960px) {{
      .two-col {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>h-mesh management dashboard</h1>
    <p>Broker path health, queue depth, recent failures, and local gateway logs from the shared state directory.</p>
  </header>
  <div class="grid">
    <div class="card"><div class="label">Gateways</div><div class="metric">{snapshot["gateway_count"]}</div></div>
    <div class="card"><div class="label">Total Queue Depth</div><div class="metric">{snapshot["queue_depth_total"]}</div></div>
    <div class="card"><div class="label">Pending</div><div class="metric">{queue_status_totals.get("pending", 0)}</div></div>
    <div class="card"><div class="label">Retrying</div><div class="metric">{queue_status_totals.get("retrying", 0)}</div></div>
    <div class="card"><div class="label">Publish Failed</div><div class="metric">{failure_counts.get("publish_failed", 0)}</div></div>
    <div class="card"><div class="label">Health Publish Failed</div><div class="metric">{failure_counts.get("gateway_state_publish_failed", 0)}</div></div>
    <div class="card"><div class="label">MQTT Receive Timeout</div><div class="metric">{failure_counts.get("mqtt_receive_timeout", 0)}</div></div>
    <div class="card"><div class="label">RF Emit Blocked</div><div class="metric">{failure_counts.get("rf_emit_blocked", 0)}</div></div>
  </div>
  <section>
    <h2>Gateway health</h2>
    <table>
      <thead>
        <tr>
          <th>Gateway</th>
          <th>Site</th>
          <th>Process</th>
          <th>Broker</th>
          <th>Radio</th>
          <th>Queue</th>
          <th>Delivery</th>
          <th>Observed</th>
          <th>Queue depth graph</th>
        </tr>
      </thead>
      <tbody>{gateway_rows or '<tr><td colspan="9">No gateway state found.</td></tr>'}</tbody>
    </table>
  </section>
  <div class="two-col">
    <section>
      <h2>Recent failures</h2>
      <table>
        <thead>
          <tr>
            <th>Observed</th>
            <th>Gateway</th>
            <th>Kind</th>
            <th>Detail</th>
          </tr>
        </thead>
        <tbody>{failure_rows or '<tr><td colspan="4">No failures recorded.</td></tr>'}</tbody>
      </table>
    </section>
    <section>
      <h2>Recent logs</h2>
      {log_sections or '<p>No log files found.</p>'}
    </section>
  </div>
</body>
</html>"""


def build_management_handler(repo: ManagementRepository):
    class ManagementHandler(BaseHTTPRequestHandler):
        def _respond_json(self, payload: dict[str, object]) -> None:
            body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _respond_html(self, body: str) -> None:
            payload = body.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/healthz":
                self.send_response(HTTPStatus.OK)
                self.end_headers()
                self.wfile.write(b"ok")
                return

            if parsed.path == "/api/summary":
                self._respond_json(repo.management_snapshot())
                return

            if parsed.path == "/api/logs":
                query = parse_qs(parsed.query)
                max_lines = int(query.get("lines", ["120"])[0])
                self._respond_json({"logs": repo.recent_logs(max_lines=max_lines)})
                return

            if parsed.path == "/":
                snapshot = repo.management_snapshot()
                self._respond_html(
                    render_dashboard_html(snapshot, repo.recent_logs(max_lines=120))
                )
                return

            self.send_error(HTTPStatus.NOT_FOUND, "not found")

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    return ManagementHandler


def run_dashboard_server(
    *,
    state_dir: Path,
    log_dir: Path | None,
    host: str,
    port: int,
) -> None:
    repo = ManagementRepository(state_dir=state_dir, log_dir=log_dir)
    server = ThreadingHTTPServer((host, port), build_management_handler(repo))
    try:
        server.serve_forever()
    finally:
        server.server_close()
