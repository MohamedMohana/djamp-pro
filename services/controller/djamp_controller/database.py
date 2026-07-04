from __future__ import annotations

import asyncio
import html
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus, urlparse

from .domains import _join_marked_sections, _split_marked_sections
from .models import (
    MANAGED_MYSQL_PORT,
    MANAGED_POSTGRES_PORT,
    MANAGED_REDIS_PORT,
    CommandResult,
    Project,
)
from .paths import paths, service_log_path
from .processes import SERVICE_PROCESSES, _is_port_open
from .subprocess_security import _find_allowed_executable, _run_blocking

MANAGED_ENV_BEGIN = "# BEGIN DJAMP PRO MANAGED ENV"
MANAGED_ENV_END = "# END DJAMP PRO MANAGED ENV"


def _parse_dotenv_file(path: Path) -> Dict[str, str]:
    """Minimal .env parser for KEY=VALUE lines.

    This is intentionally conservative: it handles comments/blank lines and basic quoting.
    """
    if not path.exists():
        return {}
    try:
        raw = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return {}

    env: Dict[str, str] = {}
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export ") :].lstrip()
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        env[key] = value
    return env


def _dotenv_path(project: Project) -> Path:
    return Path(project.path) / ".env"


def _extract_db_from_dotenv(env: Dict[str, str]) -> Dict[str, Any]:
    """Return DB fields found in .env (best-effort)."""
    out: Dict[str, Any] = {}

    db_name = (env.get("DB_NAME") or env.get("POSTGRES_DB") or "").strip()
    db_user = (env.get("DB_USER") or env.get("POSTGRES_USER") or "").strip()
    db_password = (env.get("DB_PASSWORD") or env.get("POSTGRES_PASSWORD") or "").strip()
    db_host = (env.get("DB_HOST") or "").strip()
    db_port = (env.get("DB_PORT") or "").strip()

    if db_name:
        out["name"] = db_name
    if db_user:
        out["username"] = db_user
    if db_password or "DB_PASSWORD" in env or "POSTGRES_PASSWORD" in env:
        out["password"] = db_password
    if db_host:
        out["host"] = db_host
    if db_port.isdigit():
        out["port"] = int(db_port)

    database_url = (env.get("DATABASE_URL") or "").strip()
    if database_url:
        out["database_url"] = database_url
        try:
            parsed = urlparse(database_url)
            if parsed.scheme in ("postgres", "postgresql"):
                out.setdefault("type", "postgres")
            elif parsed.scheme in ("mysql", "mysql2"):
                out.setdefault("type", "mysql")
            if parsed.hostname:
                out.setdefault("host", parsed.hostname)
            if parsed.port:
                out.setdefault("port", int(parsed.port))
            if parsed.username:
                out.setdefault("username", parsed.username)
            if parsed.password is not None:
                out.setdefault("password", parsed.password)
            if parsed.path and parsed.path != "/":
                out.setdefault("name", parsed.path.lstrip("/"))
        except Exception:
            pass

    return out


def _is_sensitive_env_key(key: str) -> bool:
    upper = (key or "").upper()
    if not upper:
        return False
    if "PASSWORD" in upper or upper.endswith("_PASS"):
        return True
    if "SECRET" in upper or "TOKEN" in upper or "PRIVATE" in upper:
        return True
    if upper.endswith("_KEY") and upper not in {"SECRET_KEY_FALLBACK"}:
        return True
    return upper in {"DB_PASSWORD", "KKU_SERVICES_PASS"}


def _mask_sensitive_env_value(value: str) -> str:
    raw = value or ""
    if len(raw) <= 2:
        return "*" * len(raw)
    if len(raw) <= 6:
        return f"{raw[0]}{'*' * (len(raw) - 2)}{raw[-1]}"
    return f"{raw[:2]}{'*' * (len(raw) - 4)}{raw[-2:]}"


def _display_environment_vars(project: Project) -> Dict[str, str]:
    """Return .env values for UI display with sensitive keys masked."""
    env = _parse_dotenv_file(_dotenv_path(project))
    if project.settingsModule:
        env.setdefault("DJANGO_SETTINGS_MODULE", project.settingsModule)

    visible: Dict[str, str] = {}
    for key in sorted(env.keys()):
        value = env.get(key, "")
        visible[key] = _mask_sensitive_env_value(value) if _is_sensitive_env_key(key) else value
    return visible


def _sync_managed_env_block(project: Project, values: Dict[str, str]) -> CommandResult:
    """Write a DJAMP-managed .env block at the end of the project's .env file.

    This keeps the project as the source of truth (it reads .env), while allowing DJAMP
    to override DB host/port to the managed local services without destroying user config.
    """
    env_path = _dotenv_path(project)
    try:
        current = env_path.read_text(encoding="utf-8", errors="ignore") if env_path.exists() else ""
        before, _managed, after = _split_marked_sections(current, MANAGED_ENV_BEGIN, MANAGED_ENV_END)

        ordered_keys = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD", "DATABASE_URL"]
        block_lines: List[str] = [MANAGED_ENV_BEGIN]
        for key in ordered_keys:
            if key in values and values[key] is not None:
                block_lines.append(f"{key}={values[key]}")
        block_lines.append(MANAGED_ENV_END)

        new_content = _join_marked_sections(before, block_lines, after)
        if new_content.strip() != current.strip():
            env_path.write_text(new_content, encoding="utf-8")
        return CommandResult(success=True, output=f"Updated {env_path.name}")
    except Exception as exc:
        return CommandResult(success=False, error=f"Failed to update .env: {exc}")


def _hydrate_project_db_from_dotenv(project: Project) -> Project:
    """Update project.database fields from the project's .env (best-effort).

    The .env is treated as authoritative for DB_NAME/DB_USER/DB_PASSWORD to reduce confusion.
    """
    env = _parse_dotenv_file(_dotenv_path(project))
    db = _extract_db_from_dotenv(env)

    # Only apply when we have at least one concrete DB credential.
    if not any(k in db for k in ("name", "username", "password", "database_url")):
        return project

    if "type" in db and project.database.type == "none":
        # If the project did not configure a managed DB, don't change that automatically.
        return project

    if "name" in db and db["name"]:
        project.database.name = str(db["name"])
    if "username" in db and db["username"]:
        project.database.username = str(db["username"])
    if "password" in db and db["password"] is not None:
        project.database.password = str(db["password"])

    # Do not take host/port from .env for managed services; DJAMP manages these.
    return project


def _service_binary(name: str) -> Optional[str]:
    if name == "postgres":
        return _find_allowed_executable("postgres", paths()["home"])
    if name == "mysql":
        return _find_allowed_executable("mysqld", paths()["home"])
    if name == "redis":
        return _find_allowed_executable("redis-server", paths()["home"])
    return None


async def _start_service(name: str) -> CommandResult:
    if name in SERVICE_PROCESSES and SERVICE_PROCESSES[name][0].returncode is None:
        return CommandResult(success=True, output=f"{name} already running")

    if name == "postgres" and _is_port_open(MANAGED_POSTGRES_PORT):
        return CommandResult(success=True, output="postgres already running")
    if name == "mysql" and _is_port_open(MANAGED_MYSQL_PORT):
        return CommandResult(success=True, output="mysql already running")
    if name == "redis" and _is_port_open(MANAGED_REDIS_PORT):
        return CommandResult(success=True, output="redis already running")

    binary = _service_binary(name)
    if not binary:
        return CommandResult(success=False, error=f"{name} binary not found in PATH")

    data_root = paths()["service_data"] / name
    data_root.mkdir(parents=True, exist_ok=True)

    if name == "postgres":
        initdb = _find_allowed_executable("initdb", paths()["home"])
        if not (data_root / "PG_VERSION").exists() and initdb:
            init_result = _run_blocking(
                [
                    initdb,
                    "-D",
                    str(data_root),
                    "--auth-local=trust",
                    "--auth-host=trust",
                ],
                data_root,
            )
            if not init_result.success:
                return init_result

    # Open the log handle only after all preflight checks so failures above
    # cannot leak a file descriptor; close it if spawning itself fails.
    log_handle = open(service_log_path(name), "a", encoding="utf-8")
    try:
        if name == "postgres":
            proc = await asyncio.create_subprocess_exec(
                binary,
                "-D",
                str(data_root),
                "-p",
                str(MANAGED_POSTGRES_PORT),
                "-h",
                "127.0.0.1",
                stdout=log_handle,
                stderr=asyncio.subprocess.STDOUT,
            )
        elif name == "mysql":
            proc = await asyncio.create_subprocess_exec(
                binary,
                "--datadir",
                str(data_root),
                f"--port={MANAGED_MYSQL_PORT}",
                "--bind-address=127.0.0.1",
                stdout=log_handle,
                stderr=asyncio.subprocess.STDOUT,
            )
        else:
            conf = data_root / "redis.conf"
            conf.write_text(
                "\n".join(["bind 127.0.0.1", f"port {MANAGED_REDIS_PORT}", f"dir {data_root}"]),
                encoding="utf-8",
            )
            proc = await asyncio.create_subprocess_exec(
                binary,
                str(conf),
                stdout=log_handle,
                stderr=asyncio.subprocess.STDOUT,
            )
    except BaseException:
        log_handle.close()
        raise

    SERVICE_PROCESSES[name] = (proc, log_handle)
    return CommandResult(success=True, output=f"{name} started")


async def _stop_service(name: str) -> CommandResult:
    if name not in SERVICE_PROCESSES:
        return CommandResult(success=True, output=f"{name} already stopped")

    proc, handle = SERVICE_PROCESSES.pop(name)
    if proc.returncode is None:
        proc.terminate()
        await proc.wait()
    handle.close()
    return CommandResult(success=True, output=f"{name} stopped")


def _validate_simple_identifier(value: str, label: str) -> str:
    v = (value or "").strip()
    if not v:
        raise RuntimeError(f"Missing {label}")
    # Keep it simple/safe for SQL identifiers in MVP.
    if not all(ch.isalnum() or ch == "_" for ch in v):
        raise RuntimeError(f"Invalid {label}: only letters, numbers, and '_' are allowed")
    return v


def _ensure_postgres_db_and_role(project: Project) -> CommandResult:
    psql = _find_allowed_executable("psql", paths()["home"])
    pg_isready = _find_allowed_executable("pg_isready", paths()["home"])
    if not psql or not pg_isready:
        return CommandResult(success=False, error="Postgres tools (psql/pg_isready) not found in PATH")

    db_name = _validate_simple_identifier(project.database.name, "database name")
    db_user = _validate_simple_identifier(project.database.username, "database username")
    port = int(project.database.port or MANAGED_POSTGRES_PORT)

    # Wait briefly for Postgres to become ready.
    deadline = time.time() + 4.0
    while time.time() < deadline:
        ready = _run_blocking(
            [pg_isready, "-h", "127.0.0.1", "-p", str(port), "-d", "postgres"],
            paths()["home"],
        )
        if ready.success:
            break
        time.sleep(0.2)

    role_exists = _run_blocking(
        [psql, "-h", "127.0.0.1", "-p", str(port), "-d", "postgres", "-tAc", f"SELECT 1 FROM pg_roles WHERE rolname = '{db_user}'"],
        paths()["home"],
    )
    if not role_exists.success:
        return role_exists
    password_sql = ""
    if project.database.password:
        pw = project.database.password.replace("'", "''")
        password_sql = f" PASSWORD '{pw}'"

    if role_exists.output.strip() != "1":
        role_create = _run_blocking(
            [
                psql,
                "-h",
                "127.0.0.1",
                "-p",
                str(port),
                "-d",
                "postgres",
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                f'CREATE ROLE "{db_user}" LOGIN{password_sql};',
            ],
            paths()["home"],
        )
        if not role_create.success:
            return role_create
    elif password_sql:
        # Best-effort: align password with .env when provided.
        alter = _run_blocking(
            [
                psql,
                "-h",
                "127.0.0.1",
                "-p",
                str(port),
                "-d",
                "postgres",
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                f'ALTER ROLE "{db_user}" WITH{password_sql};',
            ],
            paths()["home"],
        )
        if not alter.success:
            return alter

    db_exists = _run_blocking(
        [psql, "-h", "127.0.0.1", "-p", str(port), "-d", "postgres", "-tAc", f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'"],
        paths()["home"],
    )
    if not db_exists.success:
        return db_exists
    if db_exists.output.strip() != "1":
        db_create = _run_blocking(
            [psql, "-h", "127.0.0.1", "-p", str(port), "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", f'CREATE DATABASE "{db_name}" OWNER "{db_user}";'],
            paths()["home"],
        )
        return db_create

    return CommandResult(success=True, output="Postgres database ready")


def _run_postgres_query_text(project: Project, query: str) -> CommandResult:
    psql = _find_allowed_executable("psql", paths()["home"])
    if not psql:
        return CommandResult(success=False, error="psql is not installed or not in PATH")

    safe_query = (query or "").strip()
    if not safe_query:
        return CommandResult(success=False, error="Query is empty")
    if len(safe_query) > 20000:
        return CommandResult(success=False, error="Query is too long")

    db_name = (project.database.name or "postgres").strip() or "postgres"
    db_user = (project.database.username or "postgres").strip() or "postgres"
    db_password = project.database.password or ""
    db_port = int(project.database.port or MANAGED_POSTGRES_PORT)

    env = os.environ.copy()
    if db_password:
        env["PGPASSWORD"] = db_password

    command = [
        psql,
        "-X",
        "-h",
        "127.0.0.1",
        "-p",
        str(db_port),
        "-U",
        db_user,
        "-d",
        db_name,
        "-v",
        "ON_ERROR_STOP=1",
        "-P",
        "pager=off",
        "-f",
        "-",
    ]

    return _run_blocking(command, Path(project.path), env=env, input_text=safe_query)


def _parse_psql_result(output: str) -> Optional[Dict[str, Any]]:
    lines = [line.rstrip() for line in output.splitlines() if line.strip()]
    if len(lines) < 2:
        return None

    header_line = lines[0]
    if "|" not in header_line:
        return None

    headers = [part.strip() for part in header_line.split("|")]
    if not any(headers):
        return None

    rows: List[List[str]] = []
    row_count: Optional[int] = None

    for line in lines[2:]:
        stripped = line.strip()
        if stripped.startswith("(") and "row" in stripped:
            m = re.search(r"\((\d+)\s+rows?\)", stripped)
            if m:
                row_count = int(m.group(1))
            break

        if "|" not in line:
            continue

        cells = [part.strip() for part in line.split("|")]
        if len(cells) < len(headers):
            cells = cells + [""] * (len(headers) - len(cells))
        elif len(cells) > len(headers):
            cells = cells[: len(headers) - 1] + ["|".join(cells[len(headers) - 1 :]).strip()]
        rows.append(cells)

    if row_count is None:
        row_count = len(rows)

    return {
        "headers": headers,
        "rows": rows,
        "row_count": row_count,
    }


def _render_psql_result_table(output: str) -> Tuple[str, int]:
    parsed = _parse_psql_result(output)
    if not parsed:
        return "", 0

    headers: List[str] = parsed["headers"]
    rows: List[List[str]] = parsed["rows"]
    row_count = int(parsed["row_count"])

    head = "<th class='col-actions'>Actions</th>" + "".join(f"<th>{html.escape(col)}</th>" for col in headers)

    if rows:
        body = ""
        for idx, row in enumerate(rows, start=1):
            row_actions = (
                "<td class='row-actions'>"
                "<a href='#'>Edit</a>"
                "<a href='#'>Copy</a>"
                "<a href='#'>Delete</a>"
                "</td>"
            )
            cells = "".join(f"<td>{html.escape(cell)}</td>" for cell in row)
            body += f"<tr><td class='row-index'>{idx}</td>{row_actions}{cells}</tr>"
    else:
        body = (
            "<tr><td class='row-index'>-</td><td class='row-actions empty'>No row actions</td>"
            + f"<td class='empty-cell' colspan='{max(len(headers), 1)}'>No rows returned.</td></tr>"
        )

    shown_from = 0
    shown_to = max(len(rows) - 1, 0) if row_count > 0 else 0
    summary = (
        "<div class='query-ok'>"
        + f"Showing rows {shown_from} - {shown_to} ({row_count} total)."
        + "</div>"
    )

    tools = (
        "<div class='result-tools'>"
        "<span class='tool-chip'>Rows: 25</span>"
        "<span class='tool-chip'>Filter: table</span>"
        "<span class='tool-chip'>Sort: none</span>"
        "</div>"
    )

    table_html = (
        "<div class='result-table-wrap'><table class='result-table'><thead><tr>"
        + "<th class='row-index-head'>#</th>"
        + head
        + "</tr></thead><tbody>"
        + body
        + "</tbody></table></div>"
    )

    return summary + tools + table_html, row_count


def _render_postgres_admin_html(
    project: Project,
    tables_output: str,
    query: str = "",
    query_output: str = "",
    query_error: str = "",
) -> str:
    project_name = html.escape(project.name)
    db_name = html.escape((project.database.name or "postgres").strip() or "postgres")
    db_user = html.escape((project.database.username or "postgres").strip() or "postgres")
    db_port = int(project.database.port or MANAGED_POSTGRES_PORT)
    safe_query = html.escape(query)
    safe_tables = html.escape((tables_output or "No tables found").strip() or "No tables found")

    table_names: List[str] = []
    seen: set[str] = set()
    for raw_line in (tables_output or "").splitlines():
        line = raw_line.strip()
        if not line or line.lower() == "table_name":
            continue
        if set(line) <= {"-", "+", "|", " "}:
            continue
        if line.startswith("(") and line.endswith("rows)"):
            continue

        candidate = line
        if "|" in candidate:
            candidate = candidate.split("|", 1)[0].strip()
        if not candidate or "." not in candidate:
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        table_names.append(candidate)

    if table_names:
        table_links = "".join(
            (
                "<a class='table-link' href='?query="
                + quote_plus(f"SELECT * FROM {table} LIMIT 100;")
                + "'>"
                + html.escape(table)
                + "</a>"
            )
            for table in table_names
        )
    else:
        table_links = "<div class='empty-note'>No tables detected yet.</div>"

    result_block = "<div class='result-empty'>Run a SQL query to preview results.</div>"
    if query.strip():
        if query_error:
            result_block = (
                "<div class='result-card error'><div class='result-title'>Query Error</div><pre class='result-raw'>"
                + html.escape(query_error.strip() or "Query failed")
                + "</pre></div>"
            )
        else:
            output_text = (query_output or "(No output)").strip() or "(No output)"
            parsed_table, _row_count = _render_psql_result_table(output_text)
            if parsed_table:
                result_block = (
                    "<div class='result-card'><div class='result-title'>Query Result</div>"
                    + parsed_table
                    + "<details class='raw-toggle'><summary>Raw output</summary><pre class='result-raw'>"
                    + html.escape(output_text)
                    + "</pre></details></div>"
                )
            else:
                result_block = (
                    "<div class='result-card'><div class='result-title'>Query Result</div><pre class='result-raw'>"
                    + html.escape(output_text)
                    + "</pre></div>"
                )

    now_query = quote_plus("SELECT NOW();")
    tables_query = quote_plus(
        "SELECT table_schema || '.' || table_name AS table_name "
        "FROM information_schema.tables "
        "WHERE table_schema NOT IN ('pg_catalog', 'information_schema') "
        "ORDER BY 1;"
    )

    return f"""<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8' />
  <meta name='viewport' content='width=device-width, initial-scale=1' />
  <title>DJAMP DB Admin - {project_name}</title>
  <style>
    :root {{
      --bg: #eceff3;
      --panel: #ffffff;
      --line: #ccd4df;
      --line-soft: #e5e9f0;
      --text: #283341;
      --muted: #6b7584;
      --brand: #3d6ea7;
      --brand-2: #2f557f;
      --accent: #f2f5f9;
      --danger-bg: #fff0f0;
      --danger-line: #efb0b0;
      --danger-text: #7d2525;
    }}

    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
      min-height: 100vh;
    }}

    .topbar {{
      background: linear-gradient(180deg, #f9fafc 0%, #edf1f6 100%);
      border-bottom: 1px solid var(--line);
      padding: 12px 18px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
    }}

    .brand {{
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 20px;
      font-weight: 700;
      color: #2f3c4d;
      letter-spacing: 0.2px;
    }}

    .brand-badge {{
      width: 28px;
      height: 28px;
      border-radius: 7px;
      background: linear-gradient(145deg, #5aa6ff 0%, #2d4eb3 100%);
      color: #fff;
      font-weight: 800;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-size: 13px;
      box-shadow: inset 0 1px 0 rgba(255,255,255,.25);
    }}

    .meta {{
      font-size: 13px;
      color: var(--muted);
      text-align: right;
    }}

    .tabs {{
      display: flex;
      gap: 6px;
      padding: 10px 18px 0;
      background: #f4f6fa;
      border-bottom: 1px solid var(--line);
    }}

    .tab {{
      display: inline-flex;
      align-items: center;
      border: 1px solid var(--line-soft);
      border-bottom-color: var(--line);
      background: #f7f9fc;
      color: #54657b;
      border-radius: 8px 8px 0 0;
      padding: 8px 12px;
      font-size: 13px;
      font-weight: 600;
      text-decoration: none;
    }}

    .tab.active {{
      background: #fff;
      color: var(--brand-2);
      border-color: var(--line);
      border-bottom-color: #fff;
    }}

    .layout {{
      display: grid;
      grid-template-columns: 300px 1fr;
      gap: 14px;
      padding: 14px;
    }}

    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 10px;
      overflow: hidden;
      box-shadow: 0 1px 0 rgba(0,0,0,.02);
    }}

    .panel-head {{
      padding: 12px 14px;
      border-bottom: 1px solid var(--line-soft);
      background: linear-gradient(180deg, #f8fafd 0%, #eef2f8 100%);
      font-size: 14px;
      font-weight: 700;
      color: #334359;
    }}

    .panel-body {{ padding: 12px 14px; }}

    .kv {{
      display: grid;
      grid-template-columns: 92px 1fr;
      gap: 6px 8px;
      font-size: 13px;
      margin-bottom: 12px;
    }}
    .kv .k {{ color: var(--muted); }}
    .kv .v {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace; font-size: 12px; color: #3d4c5f; }}

    .table-list {{
      max-height: calc(100vh - 270px);
      overflow: auto;
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      background: #fbfcfe;
    }}

    .table-link {{
      display: block;
      padding: 8px 10px;
      color: #3f5064;
      text-decoration: none;
      border-bottom: 1px solid #eef2f7;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
      font-size: 12px;
    }}

    .table-link:hover {{ background: #edf3fb; color: #214c80; }}
    .table-link:last-child {{ border-bottom: 0; }}

    .empty-note {{ padding: 10px; color: #7a8798; font-size: 12px; }}

    .action-row {{ display: flex; gap: 8px; margin-bottom: 10px; }}
    .chip {{
      text-decoration: none;
      border: 1px solid var(--line);
      background: var(--accent);
      color: #425469;
      border-radius: 7px;
      padding: 6px 10px;
      font-size: 12px;
      font-weight: 600;
    }}
    .chip:hover {{ background: #e6edf7; }}

    textarea {{
      width: 100%;
      min-height: 180px;
      resize: vertical;
      border: 1px solid #c5ceda;
      border-radius: 8px;
      padding: 10px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
      font-size: 13px;
      color: #243345;
      background: #ffffff;
    }}

    .btn {{
      margin-top: 10px;
      border: 1px solid #2a5d98;
      background: linear-gradient(180deg, #4f81be 0%, #2f5d95 100%);
      color: #fff;
      border-radius: 7px;
      padding: 9px 13px;
      font-size: 13px;
      font-weight: 700;
      cursor: pointer;
    }}
    .btn:hover {{ filter: brightness(1.04); }}

    .result-card {{
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      background: #fbfcfe;
      padding: 10px;
    }}

    .result-card.error {{
      background: var(--danger-bg);
      border-color: var(--danger-line);
      color: var(--danger-text);
    }}

    .result-title {{ font-size: 13px; font-weight: 700; margin-bottom: 8px; color: #3c4d62; }}
    .result-card.error .result-title {{ color: var(--danger-text); }}

    .result-empty {{
      border: 1px dashed var(--line);
      border-radius: 8px;
      padding: 12px;
      color: #78879b;
      background: #fafcff;
      font-size: 13px;
    }}

    .query-ok {{
      border: 1px solid #c6d67a;
      background: linear-gradient(180deg, #eef5bf 0%, #d8e89a 100%);
      color: #4a5d1f;
      border-radius: 7px;
      padding: 8px 10px;
      font-size: 12px;
      font-weight: 600;
      margin-bottom: 10px;
    }}

    .result-tools {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }}
    .tool-chip {{
      border: 1px solid var(--line-soft);
      background: #f5f8fc;
      color: #4d6078;
      border-radius: 999px;
      padding: 5px 10px;
      font-size: 11px;
      font-weight: 600;
    }}

    .result-table-wrap {{ overflow: auto; border: 1px solid var(--line-soft); border-radius: 8px; background: #fff; }}
    .result-table {{ border-collapse: collapse; width: 100%; min-width: 640px; font-size: 12px; }}
    .result-table th {{ background: #eef3f9; color: #32465d; text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line-soft); border-right: 1px solid #e5ebf3; white-space: nowrap; }}
    .result-table td {{ padding: 8px 10px; border-bottom: 1px solid #eef2f7; border-right: 1px solid #f0f3f8; color: #25374c; vertical-align: top; }}
    .result-table tr:nth-child(even) td {{ background: #fbfdff; }}
    .result-table th:last-child, .result-table td:last-child {{ border-right: 0; }}

    .row-index-head, .row-index {{ width: 40px; text-align: center; color: #6e7d90; background: #f7f9fc; }}
    .row-index {{ font-weight: 600; }}
    .col-actions {{ min-width: 160px; }}
    .row-actions {{ white-space: nowrap; min-width: 160px; }}
    .row-actions a {{ color: #2e6aa9; text-decoration: none; margin-right: 10px; font-size: 11px; font-weight: 600; }}
    .row-actions a:hover {{ text-decoration: underline; }}
    .row-actions.empty {{ color: #8695a8; font-size: 11px; }}
    .empty-cell {{ color: #7a8798; font-style: italic; }}

    .raw-toggle {{ margin-top: 10px; }}
    .raw-toggle > summary {{ cursor: pointer; color: #516378; font-size: 12px; font-weight: 600; }}

    .result-raw {{
      margin: 8px 0 0;
      padding: 10px;
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      background: #fff;
      color: #2a384a;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
      font-size: 12px;
      max-height: 330px;
      overflow: auto;
    }}

    .footer-raw {{
      margin-top: 12px;
      color: #7f8ca0;
      font-size: 11px;
      border-top: 1px solid var(--line-soft);
      padding-top: 10px;
    }}

    @media (max-width: 1080px) {{
      .layout {{ grid-template-columns: 1fr; }}
      .table-list {{ max-height: 240px; }}
      .meta {{ text-align: left; }}
      .topbar {{ flex-direction: column; align-items: flex-start; }}
    }}
  </style>
</head>
<body>
  <header class='topbar'>
    <div class='brand'>
      <span class='brand-badge'>DJ</span>
      <span>DJAMP Database Admin</span>
    </div>
    <div class='meta'>
      <div><strong>Project:</strong> {project_name}</div>
      <div><strong>PostgreSQL:</strong> 127.0.0.1:{db_port} &nbsp;|&nbsp; <strong>DB:</strong> {db_name} &nbsp;|&nbsp; <strong>User:</strong> {db_user}</div>
    </div>
  </header>

  <nav class='tabs'>
    <a class='tab active' href='?'>Databases</a>
    <a class='tab' href='?query={now_query}'>SQL</a>
    <a class='tab' href='?query={tables_query}'>Structure</a>
    <a class='tab' href='?'>Status</a>
    <a class='tab' href='?'>Settings</a>
  </nav>

  <div class='layout'>
    <aside class='panel'>
      <div class='panel-head'>Database Overview</div>
      <div class='panel-body'>
        <div class='kv'>
          <div class='k'>Engine</div><div class='v'>PostgreSQL</div>
          <div class='k'>Host</div><div class='v'>127.0.0.1:{db_port}</div>
          <div class='k'>Database</div><div class='v'>{db_name}</div>
          <div class='k'>User</div><div class='v'>{db_user}</div>
        </div>
        <div class='panel-head' style='margin:0 -14px 10px; border-left:0; border-right:0; border-radius:0;'>Tables</div>
        <div class='table-list'>
          {table_links}
        </div>
      </div>
    </aside>

    <main>
      <section class='panel'>
        <div class='panel-head'>Run SQL</div>
        <div class='panel-body'>
          <div class='action-row'>
            <a class='chip' href='?query={now_query}'>SELECT NOW()</a>
            <a class='chip' href='?query={tables_query}'>List Tables</a>
          </div>
          <form method='get'>
            <textarea name='query' placeholder='SELECT * FROM public.auth_user LIMIT 20;'>{safe_query}</textarea>
            <div><button class='btn' type='submit'>Run Query</button></div>
          </form>
        </div>
      </section>

      <section class='panel' style='margin-top: 14px;'>
        <div class='panel-head'>Results</div>
        <div class='panel-body'>
          {result_block}
          <details class='raw-toggle'>
            <summary>Raw table listing output</summary>
            <pre class='result-raw'>{safe_tables}</pre>
          </details>
          <div class='footer-raw'>This UI is PostgreSQL-backed and intentionally local-only for development.</div>
        </div>
      </section>
    </main>
  </div>
</body>
</html>"""
