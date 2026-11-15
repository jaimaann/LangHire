//! LangHire Tauri host.
//!
//! Responsibilities:
//! - Supervise the Python backend sidecar (`langhire-backend`): pick a free
//!   localhost port, generate a per-launch API token, spawn the sidecar with
//!   those values in its environment, restart it with exponential backoff if it
//!   crashes, and kill it when the app exits.
//! - Expose `get_backend_info` so the frontend learns the port and token
//!   without polling the filesystem.
//! - Open generated files (resumes etc.) safely via the opener plugin.

use std::net::{SocketAddr, TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use serde::Serialize;
use tauri::async_runtime::Receiver;
use tauri::{AppHandle, Emitter, Manager, RunEvent};
use tauri_plugin_opener::OpenerExt;
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

/// Port used by a backend started by hand during development
/// (`python backend/main.py`). Overridable with `LANGHIRE_DEV_PORT`.
const DEV_DEFAULT_PORT: u16 = 8743;
/// Name of the event the frontend listens to for sidecar lifecycle changes.
const STATUS_EVENT: &str = "backend-status";
/// Restart policy: at most this many restarts inside `RESTART_WINDOW`.
const MAX_RESTARTS: usize = 5;
const RESTART_WINDOW: Duration = Duration::from_secs(120);
/// How long to wait for a (re)started sidecar to accept TCP connections.
const READY_TIMEOUT: Duration = Duration::from_secs(90);

/// File extensions that may be opened even when they live outside the data dir.
const OPEN_EXT_ALLOWLIST: &[&str] = &[
    "pdf", "docx", "doc", "txt", "md", "csv", "json", "html", "png", "jpg",
];

/// Shared state for the managed backend sidecar.
struct Backend {
    /// Port the sidecar listens on (or the dev port when unmanaged).
    port: u16,
    /// Per-launch API token handed to the sidecar via `LANGHIRE_API_TOKEN`.
    token: String,
    /// True when this process spawned the sidecar.
    managed: AtomicBool,
    /// Set once the app is really exiting so the supervisor stops restarting.
    shutting_down: AtomicBool,
    child: Mutex<Option<CommandChild>>,
    /// Last emitted status, so late subscribers can query it.
    status: Mutex<&'static str>,
    /// Timestamps of recent restarts (for the restart budget).
    restarts: Mutex<Vec<Instant>>,
}

#[derive(Clone, Serialize)]
struct BackendStatusPayload {
    status: &'static str,
    /// Number of restarts within the current window.
    restarts: usize,
}

#[derive(Serialize)]
struct BackendInfo {
    port: u16,
    token: String,
    managed: bool,
    status: &'static str,
}

/// LangHire data directory. MUST stay identical to the historical location
/// (and to the Python backend's default) so existing user data is kept.
fn data_dir() -> Option<PathBuf> {
    if cfg!(target_os = "macos") {
        dirs::home_dir().map(|h| h.join("Library/Application Support/langhire"))
    } else if cfg!(target_os = "windows") {
        dirs::data_dir()
            .map(|d| d.join("langhire"))
            .or_else(|| dirs::home_dir().map(|h| h.join("AppData").join("Roaming").join("langhire")))
    } else {
        dirs::home_dir().map(|h| h.join(".config/langhire"))
    }
}

/// Ask the OS for a free localhost port. The listener is dropped right away;
/// there is a tiny race window, which is acceptable for a local sidecar.
fn pick_free_port() -> std::io::Result<u16> {
    let listener = TcpListener::bind("127.0.0.1:0")?;
    Ok(listener.local_addr()?.port())
}

/// 32 random bytes, hex-encoded (64 chars).
fn generate_token() -> Result<String, String> {
    let mut bytes = [0u8; 32];
    getrandom::getrandom(&mut bytes).map_err(|e| format!("RNG failure: {e}"))?;
    Ok(bytes.iter().map(|b| format!("{b:02x}")).collect())
}

fn dev_port() -> u16 {
    std::env::var("LANGHIRE_DEV_PORT")
        .ok()
        .and_then(|v| v.trim().parse().ok())
        .unwrap_or(DEV_DEFAULT_PORT)
}

fn set_status(app: &AppHandle, status: &'static str) {
    let backend = app.state::<Backend>();
    *backend.status.lock().unwrap() = status;
    let restarts = backend.restarts.lock().unwrap().len();
    if let Err(e) = app.emit(STATUS_EVENT, BackendStatusPayload { status, restarts }) {
        log::warn!("Failed to emit {STATUS_EVENT}: {e}");
    }
}

/// Spawn the sidecar with the port/token/data-dir/version in its environment.
fn spawn_sidecar(app: &AppHandle) -> Result<Receiver<CommandEvent>, String> {
    let backend = app.state::<Backend>();
    let port = backend.port.to_string();
    let mut cmd = app
        .shell()
        .sidecar("langhire-backend")
        .map_err(|e| format!("sidecar binary not found: {e}"))?
        // Positional port kept for compatibility with older backends.
        .args([port.as_str()])
        .env("LANGHIRE_PORT", &port)
        .env("LANGHIRE_API_TOKEN", &backend.token)
        .env("LANGHIRE_APP_VERSION", app.package_info().version.to_string());
    if let Some(dir) = data_dir() {
        cmd = cmd.env("LANGHIRE_DATA_DIR", dir);
    }
    let (rx, child) = cmd.spawn().map_err(|e| format!("spawn failed: {e}"))?;
    log::info!("Backend sidecar started (pid {}) on port {}", child.pid(), backend.port);
    *backend.child.lock().unwrap() = Some(child);
    Ok(rx)
}

/// Kill the sidecar (if any) and stop the supervisor from restarting it.
fn shutdown_sidecar(app: &AppHandle) {
    let backend = app.state::<Backend>();
    backend.shutting_down.store(true, Ordering::SeqCst);
    let child = backend.child.lock().unwrap().take();
    if let Some(child) = child {
        log::info!("Stopping backend sidecar (pid {})", child.pid());
        if let Err(e) = child.kill() {
            log::warn!("Failed to kill backend sidecar: {e}");
        }
    }
}

/// Poll the sidecar's port until it accepts connections, then report `running`.
async fn wait_until_ready(app: AppHandle) {
    let port = app.state::<Backend>().port;
    let addr = SocketAddr::from(([127, 0, 0, 1], port));
    let deadline = Instant::now() + READY_TIMEOUT;
    while Instant::now() < deadline {
        if app.state::<Backend>().shutting_down.load(Ordering::SeqCst) {
            return;
        }
        let ok = tauri::async_runtime::spawn_blocking(move || {
            TcpStream::connect_timeout(&addr, Duration::from_millis(300)).is_ok()
        })
        .await
        .unwrap_or(false);
        if ok {
            // Only flip to running if we are still in the starting phase
            // (a crash may have happened in the meantime).
            if *app.state::<Backend>().status.lock().unwrap() == "starting" {
                set_status(&app, "running");
            }
            return;
        }
        tokio::time::sleep(Duration::from_millis(500)).await;
    }
    log::warn!("Backend did not accept connections within {READY_TIMEOUT:?}");
}

/// Forward a sidecar output event to the app log.
fn log_output(event: CommandEvent) {
    match event {
        CommandEvent::Stdout(line) => {
            log::info!("[backend] {}", String::from_utf8_lossy(&line).trim_end());
        }
        CommandEvent::Stderr(line) => {
            // Python logging writes to stderr; don't treat it as an error.
            log::info!("[backend:err] {}", String::from_utf8_lossy(&line).trim_end());
        }
        CommandEvent::Error(e) => log::error!("[backend] error: {e}"),
        _ => {}
    }
}

/// Consume sidecar events: log output, and restart with backoff on exit.
async fn supervise(app: AppHandle, mut rx: Receiver<CommandEvent>) {
    loop {
        tauri::async_runtime::spawn(wait_until_ready(app.clone()));

        // Drain events until the process terminates (or the channel closes).
        let mut exit_desc = String::from("event channel closed");
        while let Some(event) = rx.recv().await {
            if let CommandEvent::Terminated(p) = event {
                exit_desc = format!("code {:?}, signal {:?}", p.code, p.signal);
                break;
            }
            log_output(event);
        }
        // `Terminated` can arrive before the reader threads have forwarded the
        // last output lines (usually the crash traceback); flush them too.
        while let Ok(Some(event)) =
            tokio::time::timeout(Duration::from_millis(250), rx.recv()).await
        {
            log_output(event);
        }

        let backend = app.state::<Backend>();
        backend.child.lock().unwrap().take();
        if backend.shutting_down.load(Ordering::SeqCst) {
            log::info!("Backend sidecar exited during shutdown ({exit_desc})");
            return;
        }
        log::error!("Backend sidecar exited unexpectedly ({exit_desc})");
        set_status(&app, "crashed");

        // Restart budget: at most MAX_RESTARTS within RESTART_WINDOW.
        let attempt = {
            let mut restarts = backend.restarts.lock().unwrap();
            let now = Instant::now();
            restarts.retain(|t| now.duration_since(*t) < RESTART_WINDOW);
            if restarts.len() >= MAX_RESTARTS {
                None
            } else {
                restarts.push(now);
                Some(restarts.len())
            }
        };
        let Some(attempt) = attempt else {
            log::error!("Backend crashed {MAX_RESTARTS} times within {RESTART_WINDOW:?}; giving up");
            set_status(&app, "failed");
            return;
        };

        // 1s, 2s, 4s, 8s, 16s
        let delay = Duration::from_secs(1u64 << (attempt - 1).min(4));
        log::info!("Restarting backend sidecar in {delay:?} (attempt {attempt}/{MAX_RESTARTS})");
        tokio::time::sleep(delay).await;
        if backend.shutting_down.load(Ordering::SeqCst) {
            return;
        }

        set_status(&app, "starting");
        match spawn_sidecar(&app) {
            Ok(new_rx) => rx = new_rx,
            Err(e) => {
                log::error!("Failed to restart backend sidecar: {e}");
                set_status(&app, "failed");
                return;
            }
        }
    }
}

/// Read `<data dir>/.api_token`, waiting up to 30 s for a hand-started dev
/// backend to write it. Async so it never blocks the main thread.
async fn read_dev_token() -> Result<String, String> {
    let token_path = data_dir().ok_or("no home dir")?.join(".api_token");
    for i in 0..30 {
        if let Ok(s) = tokio::fs::read_to_string(&token_path).await {
            let trimmed = s.trim();
            if !trimmed.is_empty() {
                return Ok(trimmed.to_string());
            }
        }
        if i < 29 {
            tokio::time::sleep(Duration::from_secs(1)).await;
        }
    }
    Err(format!("Token file not found after 30s: {}", token_path.display()))
}

/// Connection details for the backend. When the sidecar is managed by this
/// process the answer is immediate; otherwise (dev mode) fall back to the
/// token file written by a hand-started backend.
#[tauri::command]
async fn get_backend_info(app: AppHandle) -> Result<BackendInfo, String> {
    let backend = app.state::<Backend>();
    let status = *backend.status.lock().unwrap();
    if backend.managed.load(Ordering::SeqCst) {
        return Ok(BackendInfo {
            port: backend.port,
            token: backend.token.clone(),
            managed: true,
            status,
        });
    }
    let token = read_dev_token().await?;
    Ok(BackendInfo {
        port: dev_port(),
        token,
        managed: false,
        status,
    })
}

/// Backward-compatible wrapper around `get_backend_info`.
#[tauri::command]
async fn get_api_token(app: AppHandle) -> Result<String, String> {
    get_backend_info(app).await.map(|i| i.token)
}

/// Strip the Windows verbatim prefix that `canonicalize` adds, which some
/// shell handlers do not understand.
fn display_path(p: &Path) -> PathBuf {
    let s = p.to_string_lossy();
    if let Some(rest) = s.strip_prefix(r"\\?\UNC\") {
        PathBuf::from(format!(r"\\{rest}"))
    } else if let Some(rest) = s.strip_prefix(r"\\?\") {
        PathBuf::from(rest)
    } else {
        p.to_path_buf()
    }
}

/// Validate that `path` is an existing regular file that is either inside the
/// LangHire data dir or has an allowlisted document/image extension.
fn validate_open_path(path: &str) -> Result<PathBuf, String> {
    let canonical = std::fs::canonicalize(path).map_err(|e| format!("File not found: {e}"))?;
    if !canonical.is_file() {
        return Err("Not a file".into());
    }
    let in_data_dir = data_dir()
        .and_then(|d| std::fs::canonicalize(d).ok())
        .is_some_and(|d| canonical.starts_with(d));
    let ext_ok = canonical
        .extension()
        .and_then(|e| e.to_str())
        .map(|e| e.to_ascii_lowercase())
        .is_some_and(|e| OPEN_EXT_ALLOWLIST.contains(&e.as_str()));
    if !in_data_dir && !ext_ok {
        return Err("Refusing to open this file type".into());
    }
    Ok(display_path(&canonical))
}

/// Open a generated file (e.g. a tailored resume PDF) with the OS default app.
#[tauri::command]
fn open_file(app: AppHandle, path: String) -> Result<(), String> {
    let target = validate_open_path(&path)?;
    app.opener()
        .open_path(target.to_string_lossy(), None::<&str>)
        .map_err(|e| format!("Failed to open file: {e}"))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let port = pick_free_port().unwrap_or_else(|e| {
        log::error!("Could not pick a free port ({e}); using {DEV_DEFAULT_PORT}");
        DEV_DEFAULT_PORT
    });
    let token = generate_token().expect("failed to generate API token");

    let mut builder = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_log::Builder::new().build());
    #[cfg(desktop)]
    {
        builder = builder.plugin(tauri_plugin_updater::Builder::new().build());
    }

    builder
        .manage(Backend {
            port,
            token,
            managed: AtomicBool::new(false),
            shutting_down: AtomicBool::new(false),
            child: Mutex::new(None),
            status: Mutex::new("starting"),
            restarts: Mutex::new(Vec::new()),
        })
        .invoke_handler(tauri::generate_handler![get_backend_info, get_api_token, open_file])
        .setup(|app| {
            let handle = app.handle().clone();
            match spawn_sidecar(&handle) {
                Ok(rx) => {
                    app.state::<Backend>().managed.store(true, Ordering::SeqCst);
                    tauri::async_runtime::spawn(supervise(handle, rx));
                }
                Err(e) => {
                    // Dev mode: the developer runs `python backend/main.py`.
                    log::warn!("Backend sidecar not started ({e}); expecting a dev backend on port {}", dev_port());
                }
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app, event| {
            // Only real exits reach here: ExitRequested fires after the last
            // window closes (or on app.exit()), Exit right before the process
            // ends. Both happen after setup, so the sidecar has been spawned.
            if matches!(event, RunEvent::ExitRequested { .. } | RunEvent::Exit) {
                shutdown_sidecar(app);
            }
        });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn token_is_64_hex_chars_and_random() {
        let a = generate_token().unwrap();
        let b = generate_token().unwrap();
        assert_eq!(a.len(), 64);
        assert!(a.chars().all(|c| c.is_ascii_hexdigit()));
        assert_ne!(a, b);
    }

    #[test]
    fn free_port_is_nonzero() {
        assert_ne!(pick_free_port().unwrap(), 0);
    }

    #[test]
    fn strips_windows_verbatim_prefix() {
        assert_eq!(display_path(Path::new(r"\\?\C:\a\b.pdf")), PathBuf::from(r"C:\a\b.pdf"));
        assert_eq!(display_path(Path::new(r"\\?\UNC\srv\share\x.pdf")), PathBuf::from(r"\\srv\share\x.pdf"));
        assert_eq!(display_path(Path::new("/tmp/x.pdf")), PathBuf::from("/tmp/x.pdf"));
    }

    #[test]
    fn open_path_validation() {
        let dir = std::env::temp_dir().join(format!("langhire-test-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let pdf = dir.join("resume & calc.pdf");
        let exe = dir.join("evil.bat");
        std::fs::write(&pdf, b"x").unwrap();
        std::fs::write(&exe, b"x").unwrap();

        assert!(validate_open_path(pdf.to_str().unwrap()).is_ok());
        assert!(validate_open_path(exe.to_str().unwrap()).is_err());
        assert!(validate_open_path(dir.to_str().unwrap()).is_err());
        assert!(validate_open_path(dir.join("missing.pdf").to_str().unwrap()).is_err());

        std::fs::remove_dir_all(&dir).ok();
    }
}
