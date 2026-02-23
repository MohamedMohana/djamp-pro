use serde::{Deserialize, Serialize};
use serde_json::json;
use std::env;
use std::fs;
use std::io::{Read, Write};
use std::net::{IpAddr, Ipv4Addr, Ipv6Addr, SocketAddr, TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;

const BLOCK_BEGIN: &str = "# BEGIN DJAMP PRO MANAGED";
const BLOCK_END: &str = "# END DJAMP PRO MANAGED";

#[cfg(unix)]
const SOCKET_DIR: &str = "/var/run/djamp-pro";
#[cfg(unix)]
const SOCKET_PATH: &str = "/var/run/djamp-pro/helper.sock";

fn hosts_path() -> PathBuf {
    if cfg!(windows) {
        PathBuf::from(r"C:\Windows\System32\drivers\etc\hosts")
    } else {
        PathBuf::from("/etc/hosts")
    }
}

#[derive(Debug, Serialize)]
struct Response {
    ok: bool,
    output: String,
    error: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    data: Option<serde_json::Value>,
}

impl Response {
    fn ok(output: impl Into<String>) -> Self {
        Self {
            ok: true,
            output: output.into(),
            error: String::new(),
            data: None,
        }
    }

    fn ok_with_data(output: impl Into<String>, data: serde_json::Value) -> Self {
        Self {
            ok: true,
            output: output.into(),
            error: String::new(),
            data: Some(data),
        }
    }

    fn err(error: impl Into<String>) -> Self {
        Self {
            ok: false,
            output: String::new(),
            error: error.into(),
            data: None,
        }
    }
}

#[derive(Debug, Deserialize)]
#[serde(tag = "cmd", rename_all = "snake_case")]
enum Request {
    Status,
    HostsApply { domains: Vec<String> },
    HostsClear,
    StandardPortsEnable {
        http_target_port: u16,
        https_target_port: u16,
    },
    StandardPortsDisable,
}

fn split_sections(content: &str) -> (Vec<String>, Vec<String>, Vec<String>) {
    let lines: Vec<String> = content.lines().map(|s| s.to_string()).collect();
    let mut begin: Option<usize> = None;
    let mut end: Option<usize> = None;

    for (idx, line) in lines.iter().enumerate() {
        if line.trim() == BLOCK_BEGIN {
            begin = Some(idx);
        }
        if line.trim() == BLOCK_END && begin.is_some() {
            end = Some(idx);
            break;
        }
    }

    if let (Some(b), Some(e)) = (begin, end) {
        let before = lines[..b].to_vec();
        let managed = lines[b..=e].to_vec();
        let after = lines[e + 1..].to_vec();
        (before, managed, after)
    } else {
        (lines, vec![], vec![])
    }
}

fn sanitize_hostname(raw: &str) -> Result<String, String> {
    let host = raw.trim().to_lowercase();
    if host.is_empty() {
        return Err("domain is empty".to_string());
    }
    if host.len() > 253 {
        return Err("domain is too long".to_string());
    }
    if host.starts_with('.') || host.ends_with('.') {
        return Err("domain must not start or end with '.'".to_string());
    }
    if host.contains("..") {
        return Err("domain must not contain '..'".to_string());
    }

    for label in host.split('.') {
        if label.is_empty() {
            return Err("domain contains an empty label".to_string());
        }
        if label.len() > 63 {
            return Err("domain label is too long".to_string());
        }
        if label.starts_with('-') || label.ends_with('-') {
            return Err("domain label must not start or end with '-'".to_string());
        }
        if !label
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || c == '-')
        {
            return Err("domain contains invalid characters".to_string());
        }
    }

    Ok(host)
}

fn write_hosts_block(domains: &[String]) -> Result<(), String> {
    let path = hosts_path();
    let content = fs::read_to_string(&path).map_err(|e| e.to_string())?;
    let (mut before, _managed, after) = split_sections(&content);

    let mut entries: Vec<String> = Vec::new();
    for domain in domains {
        let safe = sanitize_hostname(domain)?;
        entries.push(format!("127.0.0.1 {safe}"));
    }

    let mut out: Vec<String> = Vec::new();
    out.append(&mut before);
    if let Some(last) = out.last() {
        if !last.trim().is_empty() {
            out.push(String::new());
        }
    }

    out.push(BLOCK_BEGIN.to_string());
    out.extend(entries);
    out.push(BLOCK_END.to_string());

    if !after.is_empty() {
        out.push(String::new());
        out.extend(after);
    }

    let mut final_content = out.join("\n");
    final_content.push('\n');
    fs::write(&path, final_content).map_err(|e| e.to_string())
}

fn clear_hosts_block() -> Result<(), String> {
    let path = hosts_path();
    let content = fs::read_to_string(&path).map_err(|e| e.to_string())?;
    let (before, _managed, after) = split_sections(&content);
    let mut out = before;
    if !after.is_empty() {
        if let Some(last) = out.last() {
            if !last.trim().is_empty() {
                out.push(String::new());
            }
        }
        out.extend(after);
    }
    let mut final_content = out.join("\n");
    final_content.push('\n');
    fs::write(&path, final_content).map_err(|e| e.to_string())
}

fn flush_macos_dns_cache_best_effort() {
    if !cfg!(target_os = "macos") {
        return;
    }
    let _ = Command::new("/usr/bin/dscacheutil")
        .arg("-flushcache")
        .status();
    let _ = Command::new("/usr/bin/killall")
        .args(["-HUP", "mDNSResponder"])
        .status();
}

fn forward_stream(mut inbound: TcpStream, primary_target: SocketAddr, fallback_target: SocketAddr) {
    let mut outbound = match TcpStream::connect(primary_target)
        .or_else(|_| TcpStream::connect(fallback_target))
    {
        Ok(s) => s,
        Err(_) => return,
    };
    // Accepted sockets can inherit nonblocking mode from the listener.
    // Force blocking I/O for stable bidirectional stream copy.
    let _ = inbound.set_nonblocking(false);
    let _ = outbound.set_nonblocking(false);
    let _ = inbound.set_nodelay(true);
    let _ = outbound.set_nodelay(true);

    let mut inbound_clone = match inbound.try_clone() {
        Ok(s) => s,
        Err(_) => return,
    };
    let mut outbound_clone = match outbound.try_clone() {
        Ok(s) => s,
        Err(_) => return,
    };

    let t1 = thread::spawn(move || {
        let _ = std::io::copy(&mut inbound, &mut outbound_clone);
        let _ = outbound_clone.shutdown(std::net::Shutdown::Write);
    });
    let t2 = thread::spawn(move || {
        let _ = std::io::copy(&mut outbound, &mut inbound_clone);
        let _ = inbound_clone.shutdown(std::net::Shutdown::Write);
    });
    let _ = t1.join();
    let _ = t2.join();
}

struct Forwarder {
    stop: Arc<AtomicBool>,
    handles: Vec<thread::JoinHandle<()>>,
}

impl Forwarder {
    fn start(listen_port: u16, target_port: u16) -> Result<Self, String> {
        let stop = Arc::new(AtomicBool::new(false));
        let mut handles: Vec<thread::JoinHandle<()>> = Vec::new();

        let listen_addrs = [
            SocketAddr::new(IpAddr::V4(Ipv4Addr::LOCALHOST), listen_port),
            SocketAddr::new(IpAddr::V6(Ipv6Addr::LOCALHOST), listen_port),
        ];
        let target_addrs = [
            SocketAddr::new(IpAddr::V4(Ipv4Addr::LOCALHOST), target_port),
            SocketAddr::new(IpAddr::V6(Ipv6Addr::LOCALHOST), target_port),
        ];

        // Try v4 first (required); v6 is best-effort.
        for (idx, listen_addr) in listen_addrs.iter().enumerate() {
            let listener = match TcpListener::bind(listen_addr) {
                Ok(l) => l,
                Err(err) => {
                    if idx == 0 {
                        return Err(format!("failed to bind {listen_addr}: {err}"));
                    }
                    continue;
                }
            };
            let _ = listener.set_nonblocking(true);
            let stop_flag = Arc::clone(&stop);
            let primary_target = target_addrs[idx];
            let fallback_target = target_addrs[1 - idx];
            handles.push(thread::spawn(move || loop {
                if stop_flag.load(Ordering::Relaxed) {
                    break;
                }
                match listener.accept() {
                    Ok((stream, _addr)) => {
                        let _ = stream.set_nonblocking(false);
                        let _ = stream.set_nodelay(true);
                        thread::spawn(move || forward_stream(stream, primary_target, fallback_target));
                    }
                    Err(err) if err.kind() == std::io::ErrorKind::WouldBlock => {
                        thread::sleep(Duration::from_millis(40));
                    }
                    Err(_) => {
                        thread::sleep(Duration::from_millis(80));
                    }
                }
            }));
        }

        Ok(Self { stop, handles })
    }

    fn stop(self) {
        self.stop.store(true, Ordering::Relaxed);
        for handle in self.handles {
            let _ = handle.join();
        }
    }
}

#[derive(Default)]
struct State {
    http_forwarder: Option<Forwarder>,
    https_forwarder: Option<Forwarder>,
    http_target_port: u16,
    https_target_port: u16,
}

#[cfg(unix)]
fn ensure_socket_permissions(path: &Path) -> Result<(), String> {
    use libc::{chmod, chown, getgrnam, gid_t};
    use std::ffi::CString;

    let admin = CString::new("admin").map_err(|e| e.to_string())?;
    let group = unsafe { getgrnam(admin.as_ptr()) };
    if group.is_null() {
        return Err("unable to resolve admin group".to_string());
    }
    let admin_gid: gid_t = unsafe { (*group).gr_gid };

    let c_path = CString::new(
        path.to_str()
            .ok_or_else(|| "invalid socket path".to_string())?,
    )
    .map_err(|e| e.to_string())?;

    // root:admin, mode 0660
    let res = unsafe { chown(c_path.as_ptr(), 0, admin_gid) };
    if res != 0 {
        return Err("failed to set socket ownership".to_string());
    }
    let res = unsafe { chmod(c_path.as_ptr(), 0o660) };
    if res != 0 {
        return Err("failed to set socket permissions".to_string());
    }
    Ok(())
}

#[cfg(unix)]
fn daemon_main() -> Result<(), String> {
    use std::os::unix::net::UnixListener;

    // Ensure /var/run/djamp-pro exists.
    fs::create_dir_all(SOCKET_DIR).map_err(|e| format!("create socket dir failed: {e}"))?;

    let socket_path = Path::new(SOCKET_PATH);
    if socket_path.exists() {
        let _ = fs::remove_file(socket_path);
    }

    let listener =
        UnixListener::bind(socket_path).map_err(|e| format!("bind unix socket failed: {e}"))?;
    ensure_socket_permissions(socket_path)?;

    let state: Arc<Mutex<State>> = Arc::new(Mutex::new(State::default()));

    for stream in listener.incoming() {
        let mut stream = match stream {
            Ok(s) => s,
            Err(_) => continue,
        };

        let state = Arc::clone(&state);
        thread::spawn(move || {
            let mut buf: Vec<u8> = Vec::new();
            if stream.read_to_end(&mut buf).is_err() {
                let _ = write_response(&mut stream, Response::err("read request failed"));
                return;
            }

            let req: Request = match serde_json::from_slice(&buf) {
                Ok(v) => v,
                Err(_) => {
                    let _ = write_response(&mut stream, Response::err("invalid json request"));
                    return;
                }
            };

            let resp = handle_request(req, state);
            let _ = write_response(&mut stream, resp);
        });
    }

    Ok(())
}

#[cfg(not(unix))]
fn daemon_main() -> Result<(), String> {
    Err("daemon mode is only available on macOS/Linux".to_string())
}

fn handle_request(req: Request, state: Arc<Mutex<State>>) -> Response {
    match req {
        Request::Status => {
            let guard = match state.lock() {
                Ok(g) => g,
                Err(_) => return Response::err("failed to lock state"),
            };
            Response::ok_with_data(
                "ok",
                json!({
                    "socketPath": if cfg!(unix) { SOCKET_PATH } else { "" },
                    "standardHttpActive": guard.http_forwarder.is_some(),
                    "standardHttpsActive": guard.https_forwarder.is_some(),
                    "httpTargetPort": guard.http_target_port,
                    "httpsTargetPort": guard.https_target_port,
                }),
            )
        }
        Request::HostsApply { domains } => match write_hosts_block(&domains) {
            Ok(()) => {
                flush_macos_dns_cache_best_effort();
                Response::ok("hosts updated")
            }
            Err(err) => Response::err(err),
        },
        Request::HostsClear => match clear_hosts_block() {
            Ok(()) => {
                flush_macos_dns_cache_best_effort();
                Response::ok("hosts cleared")
            }
            Err(err) => Response::err(err),
        },
        Request::StandardPortsEnable {
            http_target_port,
            https_target_port,
        } => {
            let mut guard = match state.lock() {
                Ok(g) => g,
                Err(_) => return Response::err("failed to lock state"),
            };

            // Restart if targets changed.
            let needs_restart = guard.http_target_port != http_target_port
                || guard.https_target_port != https_target_port
                || guard.http_forwarder.is_none()
                || guard.https_forwarder.is_none();

            if needs_restart {
                if let Some(f) = guard.http_forwarder.take() {
                    f.stop();
                }
                if let Some(f) = guard.https_forwarder.take() {
                    f.stop();
                }

                match Forwarder::start(80, http_target_port) {
                    Ok(f) => guard.http_forwarder = Some(f),
                    Err(err) => return Response::err(err),
                }
                match Forwarder::start(443, https_target_port) {
                    Ok(f) => guard.https_forwarder = Some(f),
                    Err(err) => {
                        if let Some(f) = guard.http_forwarder.take() {
                            f.stop();
                        }
                        return Response::err(err);
                    }
                }
                guard.http_target_port = http_target_port;
                guard.https_target_port = https_target_port;
            }

            Response::ok("standard ports enabled")
        }
        Request::StandardPortsDisable => {
            let mut guard = match state.lock() {
                Ok(g) => g,
                Err(_) => return Response::err("failed to lock state"),
            };
            if let Some(f) = guard.http_forwarder.take() {
                f.stop();
            }
            if let Some(f) = guard.https_forwarder.take() {
                f.stop();
            }
            guard.http_target_port = 0;
            guard.https_target_port = 0;
            Response::ok("standard ports disabled")
        }
    }
}

fn write_response(stream: &mut impl Write, resp: Response) -> Result<(), String> {
    let payload =
        serde_json::to_vec(&resp).map_err(|e| format!("serialize response failed: {e}"))?;
    stream.write_all(&payload).map_err(|e| e.to_string())?;
    Ok(())
}

fn print_usage() {
    eprintln!("usage:");
    eprintln!("  djamp-priv-helper daemon");
    eprintln!("  djamp-priv-helper hosts apply <domain1> <domain2> ...");
    eprintln!("  djamp-priv-helper hosts clear");
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        print_usage();
        std::process::exit(2);
    }

    if args[1] == "daemon" {
        if let Err(err) = daemon_main() {
            eprintln!("{err}");
            std::process::exit(1);
        }
        return;
    }

    if args[1] != "hosts" {
        print_usage();
        std::process::exit(2);
    }
    if args.len() < 3 {
        eprintln!("missing hosts subcommand");
        std::process::exit(2);
    }

    let result = match args[2].as_str() {
        "apply" => {
            if args.len() < 4 {
                Err("missing domains".to_string())
            } else {
                write_hosts_block(&args[3..].to_vec())
            }
        }
        "clear" => clear_hosts_block(),
        _ => Err("unsupported hosts subcommand".to_string()),
    };

    if let Err(err) = result {
        eprintln!("{err}");
        std::process::exit(1);
    }
}
