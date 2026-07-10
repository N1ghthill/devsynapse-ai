use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use serde::Deserialize;
use tauri::Manager;

type BackendState = Arc<Mutex<ManagedBackend>>;

#[derive(Default)]
struct ManagedBackend {
    port: Option<u16>,
    token: Option<String>,
    child: Option<Child>,
    pid: Option<u32>,
    data_dir: Option<PathBuf>,
    last_error: Option<String>,
}

impl Drop for ManagedBackend {
    fn drop(&mut self) {
        stop_backend(self);
    }
}

#[derive(Clone, serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BackendHealth {
    pub status: String,
    pub port: Option<u16>,
    pub pid: Option<u32>,
    pub data_dir: Option<String>,
    pub message: Option<String>,
}

#[derive(Clone, serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AppHealth {
    pub status: String,
    pub version: String,
    pub backend: BackendHealth,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ConversationStartArgs {
    request_id: String,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ConversationSendArgs {
    request_id: String,
    conversation_id: String,
    message: String,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ConversationCancelArgs {
    request_id: String,
    conversation_id: String,
}

#[derive(Clone, serde::Deserialize, serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ConversationEvent {
    #[serde(rename = "type")]
    pub event_type: String,
    pub request_id: String,
    pub conversation_id: String,
    pub delta: Option<String>,
    pub error: Option<String>,
}

#[derive(Clone, serde::Deserialize, serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ConversationResponse {
    pub conversation_id: String,
    pub events: Vec<ConversationEvent>,
}

fn find_free_port() -> Result<u16, String> {
    std::net::TcpListener::bind("127.0.0.1:0")
        .map_err(|error| format!("could not bind local port: {error}"))?
        .local_addr()
        .map(|address| address.port())
        .map_err(|error| format!("could not inspect local port: {error}"))
}

fn random_token() -> Result<String, String> {
    let mut bytes = [0_u8; 32];
    if getrandom::fill(&mut bytes).is_err() {
        let fallback = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_err(|error| error.to_string())?
            .as_nanos();
        return Ok(format!("devsynapse-{fallback}-{}", std::process::id()));
    }

    Ok(bytes.iter().map(|byte| format!("{byte:02x}")).collect())
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

fn manifest_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}

fn workspace_root() -> PathBuf {
    manifest_dir()
        .parent()
        .and_then(|frontend| frontend.parent())
        .map(PathBuf::from)
        .unwrap_or_else(manifest_dir)
}

fn sidecar_candidates(app: &tauri::AppHandle) -> Vec<PathBuf> {
    let mut dirs = Vec::new();
    if let Ok(resource_dir) = app.path().resource_dir() {
        dirs.push(resource_dir.clone());
        dirs.push(resource_dir.join("binaries"));
    }
    dirs.push(manifest_dir().join("binaries"));

    sidecar_file_names()
        .into_iter()
        .flat_map(|name| dirs.iter().map(move |dir| dir.join(&name)).collect::<Vec<_>>())
        .collect()
}

fn resolve_sidecar_path(app: &tauri::AppHandle) -> Option<PathBuf> {
    sidecar_candidates(app).into_iter().find(|path| path.exists())
}

fn dev_python_command() -> Option<(PathBuf, Vec<String>)> {
    let root = workspace_root();
    let entry = root.join("backend-entry.py");
    if !entry.exists() {
        return None;
    }

    let venv_python = if cfg!(target_os = "windows") {
        root.join("venv").join("Scripts").join("python.exe")
    } else {
        root.join("venv").join("bin").join("python")
    };

    if venv_python.exists() {
        return Some((venv_python, vec![entry.display().to_string()]));
    }

    Some((PathBuf::from("python3"), vec![entry.display().to_string()]))
}

fn stop_backend(backend: &mut ManagedBackend) {
    if let Some(mut child) = backend.child.take() {
        let _ = child.kill();
        let _ = child.wait();
    }
    backend.pid = None;
}

fn start_backend(app: &tauri::AppHandle, backend: &mut ManagedBackend) -> Result<(), String> {
    stop_backend(backend);

    let port = find_free_port()?;
    let token = random_token()?;
    let data_dir = app
        .path()
        .app_data_dir()
        .map_err(|error| format!("could not resolve app data dir: {error}"))?;
    std::fs::create_dir_all(&data_dir)
        .map_err(|error| format!("could not create app data dir: {error}"))?;

    let mut command = if let Some(sidecar_path) = resolve_sidecar_path(app) {
        Command::new(sidecar_path)
    } else if let Some((python, prefix_args)) = dev_python_command() {
        let mut command = Command::new(python);
        command.args(prefix_args);
        command
    } else {
        return Err("backend sidecar was not found".to_string());
    };

    command
        .args(["--port", &port.to_string(), "--data-dir"])
        .arg(&data_dir)
        .env("DEVSYNAPSE_SIDECAR_TOKEN", &token)
        .env("DEVSYNAPSE_HOME", &data_dir)
        .stdout(Stdio::null())
        .stderr(Stdio::null());

    let child = command
        .spawn()
        .map_err(|error| format!("could not start backend sidecar: {error}"))?;
    let pid = child.id();

    backend.port = Some(port);
    backend.token = Some(token);
    backend.pid = Some(pid);
    backend.child = Some(child);
    backend.data_dir = Some(data_dir);
    backend.last_error = None;
    Ok(())
}

fn check_backend_http(port: u16, token: &str) -> Result<(), String> {
    let address = SocketAddr::from(([127, 0, 0, 1], port));
    let mut stream = TcpStream::connect_timeout(&address, Duration::from_millis(600))
        .map_err(|error| error.to_string())?;
    stream
        .set_read_timeout(Some(Duration::from_millis(600)))
        .map_err(|error| error.to_string())?;
    stream
        .set_write_timeout(Some(Duration::from_millis(600)))
        .map_err(|error| error.to_string())?;

    let request = format!(
        "GET /health HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nAuthorization: Bearer {token}\r\nConnection: close\r\n\r\n"
    );
    stream
        .write_all(request.as_bytes())
        .map_err(|error| error.to_string())?;

    let mut response = String::new();
    stream
        .read_to_string(&mut response)
        .map_err(|error| error.to_string())?;

    if response.starts_with("HTTP/1.0 200") || response.starts_with("HTTP/1.1 200") {
        Ok(())
    } else {
        Err("backend health endpoint returned a non-200 response".to_string())
    }
}

fn split_http_body(response: &str) -> Result<&str, String> {
    let (headers, body) = response
        .split_once("\r\n\r\n")
        .ok_or_else(|| "backend returned an invalid HTTP response".to_string())?;
    if headers.starts_with("HTTP/1.0 200") || headers.starts_with("HTTP/1.1 200") {
        Ok(body)
    } else {
        Err("backend returned a non-200 response".to_string())
    }
}

fn post_backend_json(
    port: u16,
    token: &str,
    path: &str,
    payload: serde_json::Value,
) -> Result<serde_json::Value, String> {
    let address = SocketAddr::from(([127, 0, 0, 1], port));
    let mut stream = TcpStream::connect_timeout(&address, Duration::from_secs(2))
        .map_err(|error| error.to_string())?;
    stream
        .set_read_timeout(Some(Duration::from_secs(2)))
        .map_err(|error| error.to_string())?;
    stream
        .set_write_timeout(Some(Duration::from_secs(2)))
        .map_err(|error| error.to_string())?;

    let body = payload.to_string();
    let request = format!(
        "POST {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nAuthorization: Bearer {token}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
        body.len()
    );
    stream
        .write_all(request.as_bytes())
        .map_err(|error| error.to_string())?;

    let mut response = String::new();
    stream
        .read_to_string(&mut response)
        .map_err(|error| error.to_string())?;

    serde_json::from_str(split_http_body(&response)?).map_err(|error| error.to_string())
}

fn backend_connection(state: &BackendState) -> Result<(u16, String), String> {
    let mut backend = state.lock().expect("backend state lock poisoned");
    let health = backend_health(&mut backend);
    if health.status != "healthy" {
        return Err(health.message.unwrap_or_else(|| "backend is not healthy".to_string()));
    }

    let port = backend
        .port
        .ok_or_else(|| "backend port is missing".to_string())?;
    let token = backend
        .token
        .clone()
        .ok_or_else(|| "backend token is missing".to_string())?;
    Ok((port, token))
}

fn conversation_request(
    state: &BackendState,
    path: &str,
    payload: serde_json::Value,
) -> Result<ConversationResponse, String> {
    let (port, token) = backend_connection(state)?;
    let response = post_backend_json(port, &token, path, payload)?;
    serde_json::from_value(response).map_err(|error| error.to_string())
}

fn backend_health(backend: &mut ManagedBackend) -> BackendHealth {
    let data_dir = backend
        .data_dir
        .as_ref()
        .map(|path| path.display().to_string());

    if let Some(child) = backend.child.as_mut() {
        match child.try_wait() {
            Ok(Some(status)) => {
                backend.child = None;
                backend.pid = None;
                backend.last_error = Some(format!("backend exited with {status}"));
            }
            Ok(None) => {}
            Err(error) => {
                backend.child = None;
                backend.pid = None;
                backend.last_error = Some(format!("could not inspect backend: {error}"));
            }
        }
    }

    let Some(port) = backend.port else {
        return BackendHealth {
            status: "stopped".to_string(),
            port: None,
            pid: None,
            data_dir,
            message: backend.last_error.clone(),
        };
    };

    if backend.child.is_none() {
        return BackendHealth {
            status: "stopped".to_string(),
            port: Some(port),
            pid: None,
            data_dir,
            message: backend.last_error.clone(),
        };
    }

    let Some(token) = backend.token.as_deref() else {
        return BackendHealth {
            status: "unhealthy".to_string(),
            port: Some(port),
            pid: backend.pid,
            data_dir,
            message: Some("backend token missing".to_string()),
        };
    };

    match check_backend_http(port, token) {
        Ok(()) => BackendHealth {
            status: "healthy".to_string(),
            port: Some(port),
            pid: backend.pid,
            data_dir,
            message: None,
        },
        Err(error) => BackendHealth {
            status: "starting".to_string(),
            port: Some(port),
            pid: backend.pid,
            data_dir,
            message: Some(error),
        },
    }
}

fn app_health_payload(app: &tauri::AppHandle, state: &BackendState) -> AppHealth {
    let mut backend = state.lock().expect("backend state lock poisoned");
    let backend = backend_health(&mut backend);
    let status = if backend.status == "healthy" {
        "ok"
    } else {
        "degraded"
    };

    AppHealth {
        status: status.to_string(),
        version: app.package_info().version.to_string(),
        backend,
    }
}

#[tauri::command]
fn app_health(app: tauri::AppHandle, state: tauri::State<'_, BackendState>) -> AppHealth {
    app_health_payload(&app, state.inner())
}

#[tauri::command]
fn app_version(app: tauri::AppHandle) -> String {
    app.package_info().version.to_string()
}

#[tauri::command]
fn restart_backend(
    app: tauri::AppHandle,
    state: tauri::State<'_, BackendState>,
) -> AppHealth {
    {
        let mut backend = state.lock().expect("backend state lock poisoned");
        if let Err(error) = start_backend(&app, &mut backend) {
            backend.last_error = Some(error);
        }
    }
    app_health_payload(&app, state.inner())
}

#[tauri::command]
fn conversation_start(
    args: ConversationStartArgs,
    state: tauri::State<'_, BackendState>,
) -> Result<ConversationResponse, String> {
    conversation_request(
        state.inner(),
        "/conversation/start",
        serde_json::json!({ "requestId": args.request_id }),
    )
}

#[tauri::command]
fn conversation_send(
    args: ConversationSendArgs,
    state: tauri::State<'_, BackendState>,
) -> Result<ConversationResponse, String> {
    conversation_request(
        state.inner(),
        "/conversation/send",
        serde_json::json!({
            "requestId": args.request_id,
            "conversationId": args.conversation_id,
            "message": args.message,
        }),
    )
}

#[tauri::command]
fn conversation_cancel(
    args: ConversationCancelArgs,
    state: tauri::State<'_, BackendState>,
) -> Result<ConversationResponse, String> {
    conversation_request(
        state.inner(),
        "/conversation/cancel",
        serde_json::json!({
            "requestId": args.request_id,
            "conversationId": args.conversation_id,
        }),
    )
}

pub fn run() {
    let backend_state: BackendState = Arc::new(Mutex::new(ManagedBackend::default()));
    let setup_state = backend_state.clone();

    tauri::Builder::default()
        .manage(backend_state)
        .invoke_handler(tauri::generate_handler![
            app_health,
            app_version,
            restart_backend,
            conversation_start,
            conversation_send,
            conversation_cancel
        ])
        .setup(move |app| {
            let mut backend = setup_state.lock().expect("backend state lock poisoned");
            if let Err(error) = start_backend(app.handle(), &mut backend) {
                backend.last_error = Some(error);
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running DevSynapse AI");
}
