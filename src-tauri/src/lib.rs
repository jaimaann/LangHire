use std::sync::Mutex;
use tauri::Manager;
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::CommandChild;

struct Backend(Mutex<Option<CommandChild>>);

#[tauri::command]
fn get_api_token() -> Result<String, String> {
    let base = if cfg!(target_os = "macos") {
        dirs::home_dir().map(|h| h.join("Library/Application Support/job-applicant"))
    } else if cfg!(target_os = "windows") {
        dirs::home_dir().map(|h| h.join("AppData/Roaming/job-applicant"))
    } else {
        dirs::home_dir().map(|h| h.join(".config/job-applicant"))
    }
    .ok_or("no home dir")?;

    let token_path = base.join(".api_token");

    // Backend sidecar may take a few seconds to start and write the token file.
    // Retry up to 15 times (15 seconds total) with 1-second intervals.
    for i in 0..15 {
        match std::fs::read_to_string(&token_path) {
            Ok(s) => {
                let trimmed = s.trim().to_string();
                if !trimmed.is_empty() {
                    return Ok(trimmed);
                }
            }
            Err(_) => {}
        }
        if i < 14 {
            std::thread::sleep(std::time::Duration::from_secs(1));
        }
    }

    Err(format!("Token file not found after 15s: {}", token_path.display()))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_log::Builder::new().build())
        .manage(Backend(Mutex::new(None)))
        .invoke_handler(tauri::generate_handler![get_api_token])
        .setup(|app| {
            let shell = app.shell();
            match shell.sidecar("job-applicant-backend") {
                Ok(sidecar) => match sidecar.args(["8742"]).spawn() {
                    Ok((_rx, child)) => {
                        log::info!("Backend sidecar started on port 8742");
                        *app.state::<Backend>().0.lock().unwrap() = Some(child);
                    }
                    Err(e) => log::error!("Failed to spawn backend sidecar: {e}"),
                },
                Err(e) => log::error!("Backend sidecar binary not found: {e}"),
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|_app, _event| {
            // Sidecar lifecycle is self-managed:
            // - Parent watchdog thread in Python detects when Tauri exits
            // - SIGTERM handler cleans up browser processes
            // We don't kill the sidecar here because Tauri may fire Exit
            // before the sidecar finishes starting (observed on macOS M1)
        });
}
