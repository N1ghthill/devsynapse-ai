// ── state ────────────────────────────────────────────────────────────────────

use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Arc;
use tauri::Manager;
use tokio::sync::Mutex;

pub struct ManagedProcess {
    pub port: u16,
    pub child: Option<Child>,
    pub child_pid: Option<u32>,
}

pub type BackendState = Arc<Mutex<ManagedProcess>>;

// ── port discovery ───────────────────────────────────────────────────────────

pub fn find_free_port() -> u16 {
    std::net::TcpListener::bind("127.0.0.1:0")
        .ok()
        .and_then(|l| l.local_addr().ok())
        .map(|a| a.port())
        .unwrap_or(8000)
}

pub fn is_port_open(port: u16) -> bool {
    std::net::TcpStream::connect(format!("127.0.0.1:{}", port)).is_ok()
}

// ── backend lifecycle ────────────────────────────────────────────────────────

pub fn kill_child(child: &mut Option<Child>) {
    if let Some(mut c) = child.take() {
        log::info!("Stopping backend (pid {})", c.id());
        let _ = c.kill();
        let _ = c.wait();
    }
}

fn sidecar_file_names() -> Vec<String> {
    let target = env!("DEVSYNAPSE_TARGET_TRIPLE");
    let base_name = "devsynapse-backend";

    let mut names = Vec::new();
    if cfg!(target_os = "windows") {
        names.push(format!("{base_name}-{target}.exe"));
        names.push(format!("{base_name}.exe"));
    }
    names.push(format!("{base_name}-{target}"));
    names.push(base_name.to_string());
    names
}

fn sidecar_search_dirs(app: &tauri::AppHandle) -> Vec<PathBuf> {
    let mut dirs = Vec::new();

    if let Ok(resource_dir) = app.path().resource_dir() {
        dirs.push(resource_dir.clone());
        dirs.push(resource_dir.join("binaries"));
    }

    if let Ok(exe_path) = std::env::current_exe() {
        if let Some(exe_dir) = exe_path.parent() {
            dirs.push(exe_dir.to_path_buf());
            dirs.push(exe_dir.join("binaries"));
        }
    }

    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    dirs.push(manifest_dir.join("binaries"));
    dirs.push(manifest_dir.join("target").join(if cfg!(debug_assertions) {
        "debug"
    } else {
        "release"
    }));

    dirs.sort();
    dirs.dedup();
    dirs
}

fn sidecar_candidates(app: &tauri::AppHandle) -> Vec<PathBuf> {
    let names = sidecar_file_names();
    sidecar_search_dirs(app)
        .into_iter()
        .flat_map(|dir| names.iter().map(move |name| dir.join(name)))
        .collect()
}

fn resolve_sidecar_path(app: &tauri::AppHandle) -> Option<PathBuf> {
    sidecar_candidates(app).into_iter().find(|path| {
        if path.exists() {
            log::info!("Found sidecar at {}", path.display());
            return true;
        }
        false
    })
}

pub async fn start_backend_with_port(
    port: u16,
    app: &tauri::AppHandle,
    state: &BackendState,
) -> Result<u16, String> {
    let sidecar_path = resolve_sidecar_path(app).ok_or_else(|| {
        let searched = sidecar_candidates(app)
            .into_iter()
            .take(12)
            .map(|path| path.display().to_string())
            .collect::<Vec<_>>()
            .join(", ");
        format!(
            "Backend binary not found. Run `bash scripts/build-backend.sh`; searched: {searched}"
        )
    })?;

    // Ensure the binary is executable on Unix
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        if let Ok(meta) = std::fs::metadata(&sidecar_path) {
            let perms = meta.permissions();
            if perms.mode() & 0o111 == 0 {
                let _ = std::fs::set_permissions(&sidecar_path, PermissionsExt::from_mode(0o755));
            }
        }
    }

    // Resolve data directory via Tauri path API
    let data_dir = app
        .path()
        .app_data_dir()
        .unwrap_or_else(|_| std::path::PathBuf::from("."));

    log::info!(
        "Starting backend on port {} (data: {}, binary: {})",
        port,
        data_dir.display(),
        sidecar_path.display()
    );

    let child = Command::new(&sidecar_path)
        .args(["--port", &port.to_string(), "--data-dir"])
        .arg(&data_dir)
        .stdout(std::process::Stdio::inherit())
        .stderr(std::process::Stdio::inherit())
        .spawn()
        .map_err(|e| format!("Failed to start backend: {}", e))?;

    let pid = child.id();

    let mut guard = state.lock().await;
    guard.child = Some(child);
    guard.child_pid = Some(pid);
    guard.port = port;

    log::info!("Backend started with pid {}", pid);
    Ok(port)
}

impl Drop for ManagedProcess {
    fn drop(&mut self) {
        kill_child(&mut self.child);
    }
}
