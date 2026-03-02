use once_cell::sync::Lazy;
use serde::de::DeserializeOwned;
use serde::Serialize;
use serde_json::Value;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::Instant;
use tokio::time::{sleep, Duration};

const SIDECAR_BASE: &str = "http://127.0.0.1:8765";
static SIDECAR_PROCESS: Lazy<Mutex<Option<Child>>> = Lazy::new(|| Mutex::new(None));
static HTTP_CLIENT: Lazy<reqwest::Client> = Lazy::new(|| {
    reqwest::Client::builder()
        .timeout(Duration::from_secs(45))
        .build()
        .expect("failed to build reqwest client")
});
static HEALTH_CLIENT: Lazy<reqwest::Client> = Lazy::new(|| {
    reqwest::Client::builder()
        .connect_timeout(Duration::from_millis(700))
        .timeout(Duration::from_millis(1200))
        .build()
        .expect("failed to build healthcheck client")
});

fn repo_root() -> Result<PathBuf, String> {
    let manifest = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    manifest
        .join("../../..")
        .canonicalize()
        .map_err(|err| format!("failed to resolve repo root: {err}"))
}

fn sidecar_script() -> Result<PathBuf, String> {
    Ok(repo_root()?.join("services/controller/run_service.py"))
}

fn sidecar_workdir() -> Result<PathBuf, String> {
    Ok(repo_root()?.join("services/controller"))
}

fn spawn_sidecar() -> Result<(), String> {
    let script = sidecar_script()?;
    if !script.exists() {
        return Err(format!("sidecar script not found: {}", script.display()));
    }

    let workdir = sidecar_workdir()?;
    let repo = repo_root()?;
    let mut interpreter_candidates: Vec<String> = Vec::new();

    if cfg!(target_os = "windows") {
        let venv_python = repo.join("services/controller/.venv/Scripts/python.exe");
        if venv_python.exists() {
            interpreter_candidates.push(venv_python.to_string_lossy().to_string());
        }
        interpreter_candidates.push("py".to_string());
        interpreter_candidates.push("python".to_string());
        interpreter_candidates.push("python3".to_string());
    } else {
        let venv_python = repo.join("services/controller/.venv/bin/python");
        if venv_python.exists() {
            interpreter_candidates.push(venv_python.to_string_lossy().to_string());
        }
        interpreter_candidates.push("python3".to_string());
        interpreter_candidates.push("python".to_string());
    }

    let mut last_error = String::new();
    for candidate in interpreter_candidates {
        let mut cmd = Command::new(&candidate);
        if candidate == "py" {
            cmd.arg("-3");
        }

        cmd.arg(script.as_os_str())
            .current_dir(&workdir)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .env("PYTHONUNBUFFERED", "1");

        match cmd.spawn() {
            Ok(child) => {
                let mut guard = SIDECAR_PROCESS
                    .lock()
                    .map_err(|_| "failed to lock sidecar state".to_string())?;
                *guard = Some(child);
                return Ok(());
            }
            Err(err) => {
                last_error = format!("{candidate}: {err}");
            }
        }
    }

    Err(format!("unable to spawn sidecar ({last_error})"))
}

async fn healthcheck() -> bool {
    match HEALTH_CLIENT
        .get(format!("{SIDECAR_BASE}/health"))
        .send()
        .await
    {
        Ok(resp) => resp.status().is_success(),
        Err(_) => false,
    }
}

async fn sidecar_supports_required_routes() -> bool {
    let response = match HEALTH_CLIENT
        .get(format!("{SIDECAR_BASE}/openapi.json"))
        .send()
        .await
    {
        Ok(resp) if resp.status().is_success() => resp,
        _ => return false,
    };

    let payload: Value = match response.json().await {
        Ok(value) => value,
        Err(_) => return false,
    };

    let Some(paths) = payload.get("paths").and_then(|v| v.as_object()) else {
        return false;
    };

    paths.contains_key("/api/databases/{project_id}/admin-url")
        && paths.contains_key("/api/databases/{project_id}/admin")
}

fn kill_stale_sidecar_listener_best_effort() {
    if cfg!(target_os = "windows") {
        let ps = "Get-NetTCPConnection -LocalPort 8765 -State Listen | Select-Object -ExpandProperty OwningProcess -Unique";
        let output = match Command::new("powershell")
            .args(["-NoProfile", "-Command", ps])
            .output()
        {
            Ok(out) => out,
            Err(_) => return,
        };

        if !output.status.success() {
            return;
        }

        let pids = String::from_utf8_lossy(&output.stdout);
        for pid in pids.split_whitespace() {
            let _ = Command::new("taskkill").args(["/PID", pid, "/T", "/F"]).status();
        }
        return;
    }

    let output = match Command::new("lsof")
        .args(["-ti", "tcp:8765", "-sTCP:LISTEN"])
        .output()
    {
        Ok(out) => out,
        Err(_) => return,
    };

    if !output.status.success() {
        return;
    }

    let pids = String::from_utf8_lossy(&output.stdout);
    for pid in pids.split_whitespace() {
        let _ = Command::new("kill").args(["-TERM", pid]).status();
    }
}

fn sidecar_process_running() -> Result<bool, String> {
    let mut guard = SIDECAR_PROCESS
        .lock()
        .map_err(|_| "failed to lock sidecar state".to_string())?;

    let Some(child) = guard.as_mut() else {
        return Ok(false);
    };

    match child.try_wait() {
        Ok(Some(_)) => {
            *guard = None;
            Ok(false)
        }
        Ok(None) => Ok(true),
        Err(_) => {
            *guard = None;
            Ok(false)
        }
    }
}

async fn request_json(
    method: reqwest::Method,
    path: &str,
    body: Option<Value>,
) -> Result<Value, String> {
    let url = format!("{SIDECAR_BASE}{path}");
    let mut req = HTTP_CLIENT.request(method, url);
    if let Some(payload) = body {
        req = req.json(&payload);
    }

    let resp = req.send().await.map_err(|err| format!("request failed: {err}"))?;
    let status = resp.status();
    let text = resp.text().await.map_err(|err| format!("read response failed: {err}"))?;
    if !status.is_success() {
        return Err(if text.trim().is_empty() {
            format!("request failed with status {status}")
        } else {
            text
        });
    }

    if text.trim().is_empty() {
        return Ok(Value::Null);
    }

    serde_json::from_str::<Value>(&text).map_err(|err| format!("invalid json response: {err}"))
}

pub async fn ensure_sidecar_started() -> Result<(), String> {
    if healthcheck().await {
        if sidecar_supports_required_routes().await {
            return Ok(());
        }

        // A stale controller may still be listening on 8765 from an older run.
        // Restart it so the desktop app always talks to the current API shape.
        if sidecar_process_running()? {
            stop_sidecar_best_effort();
        } else {
            kill_stale_sidecar_listener_best_effort();
        }
    }

    if !sidecar_process_running()? {
        spawn_sidecar()?;
    }

    for _ in 0..20 {
        if healthcheck().await && sidecar_supports_required_routes().await {
            return Ok(());
        }
        sleep(Duration::from_millis(200)).await;
    }

    Err("sidecar did not become healthy on time".to_string())
}

pub async fn get_json<T: DeserializeOwned>(path: &str) -> Result<T, String> {
    ensure_sidecar_started().await?;
    let value = request_json(reqwest::Method::GET, path, None).await?;
    serde_json::from_value(value).map_err(|err| format!("response decode failed: {err}"))
}

pub async fn post_json<B: Serialize, T: DeserializeOwned>(path: &str, body: &B) -> Result<T, String> {
    ensure_sidecar_started().await?;
    let payload = serde_json::to_value(body).map_err(|err| format!("encode body failed: {err}"))?;
    let value = request_json(reqwest::Method::POST, path, Some(payload)).await?;
    serde_json::from_value(value).map_err(|err| format!("response decode failed: {err}"))
}

pub async fn patch_json<B: Serialize, T: DeserializeOwned>(path: &str, body: &B) -> Result<T, String> {
    ensure_sidecar_started().await?;
    let payload = serde_json::to_value(body).map_err(|err| format!("encode body failed: {err}"))?;
    let value = request_json(reqwest::Method::PATCH, path, Some(payload)).await?;
    serde_json::from_value(value).map_err(|err| format!("response decode failed: {err}"))
}

pub async fn delete(path: &str) -> Result<(), String> {
    ensure_sidecar_started().await?;
    let _ = request_json(reqwest::Method::DELETE, path, None).await?;
    Ok(())
}

pub fn stop_sidecar_best_effort() {
    let mut guard = match SIDECAR_PROCESS.lock() {
        Ok(g) => g,
        Err(_) => return,
    };

    let mut child = match guard.take() {
        Some(c) => c,
        None => return,
    };

    let pid = child.id();
    #[cfg(unix)]
    {
        let _ = Command::new("kill")
            .arg("-TERM")
            .arg(pid.to_string())
            .status();
    }

    let start = Instant::now();
    while start.elapsed() < Duration::from_secs(3) {
        match child.try_wait() {
            Ok(Some(_)) => return,
            Ok(None) => std::thread::sleep(std::time::Duration::from_millis(100)),
            Err(_) => break,
        }
    }

    let _ = child.kill();
    let _ = child.wait();
}
