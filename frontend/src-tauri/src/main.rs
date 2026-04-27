// Prevents additional console window on Windows in release builds.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use devsynapse_ai::{
    find_free_port, is_port_open, kill_child, start_backend_with_port, BackendState, ManagedProcess,
};
use std::sync::Arc;
use tauri::Manager;
use tauri_plugin_updater::UpdaterExt;
use tokio::sync::Mutex;

#[cfg(feature = "tray-icon")]
use tauri::menu::{MenuBuilder, MenuItemBuilder};
#[cfg(feature = "tray-icon")]
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};

// ── Tauri commands ───────────────────────────────────────────────────────────

#[derive(Clone, serde::Serialize)]
pub struct BackendStatus {
    pub port: u16,
    pub running: bool,
    pub pid: u32,
}

#[derive(Clone, serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DesktopUpdateStatus {
    pub configured: bool,
    pub available: bool,
    pub current_version: String,
    pub version: Option<String>,
    pub date: Option<String>,
    pub body: Option<String>,
    pub endpoint: Option<String>,
}

fn updater_endpoint() -> String {
    option_env!("DEVSYNAPSE_UPDATER_ENDPOINT")
        .unwrap_or("https://github.com/N1ghthill/devsynapse-ai/releases/latest/download/latest.json")
        .to_string()
}

fn updater_public_key() -> Option<&'static str> {
    option_env!("DEVSYNAPSE_UPDATER_PUBLIC_KEY")
        .map(str::trim)
        .filter(|value| !value.is_empty())
}

fn updater_endpoint_url(endpoint: &str) -> Result<tauri::Url, String> {
    tauri::Url::parse(endpoint)
        .map_err(|error| format!("Invalid desktop updater endpoint: {}", error))
}

#[tauri::command]
async fn get_backend_status(
    state: tauri::State<'_, BackendState>,
) -> Result<BackendStatus, String> {
    let mut guard = state.lock().await;
    let mut running = false;
    let mut clear_child = false;
    let pid = guard.child_pid.unwrap_or(0);

    if let Some(child) = guard.child.as_mut() {
        match child.try_wait() {
            Ok(Some(status)) => {
                log::warn!("Backend exited with status {}", status);
                clear_child = true;
            }
            Ok(None) => {
                running = true;
            }
            Err(error) => {
                log::warn!("Could not inspect backend status: {}", error);
                clear_child = true;
            }
        }
    }

    if clear_child {
        guard.child = None;
        guard.child_pid = None;
    }

    Ok(BackendStatus {
        port: guard.port,
        running,
        pid: if running { pid } else { 0 },
    })
}

#[tauri::command]
async fn restart_backend(
    app: tauri::AppHandle,
    state: tauri::State<'_, BackendState>,
) -> Result<BackendStatus, String> {
    let port = {
        let mut guard = state.lock().await;
        kill_child(&mut guard.child);
        guard.port
    };
    start_backend_with_port(port, &app, state.inner()).await?;
    get_backend_status(state).await
}

#[tauri::command]
async fn check_desktop_update(app: tauri::AppHandle) -> Result<DesktopUpdateStatus, String> {
    let current_version = app.package_info().version.to_string();
    let Some(public_key) = updater_public_key() else {
        return Ok(DesktopUpdateStatus {
            configured: false,
            available: false,
            current_version,
            version: None,
            date: None,
            body: None,
            endpoint: Some(updater_endpoint()),
        });
    };

    let endpoint = updater_endpoint();
    let endpoint_url = updater_endpoint_url(&endpoint)?;
    let update = app
        .updater_builder()
        .pubkey(public_key)
        .endpoints(vec![endpoint_url])
        .map_err(|error| error.to_string())?
        .build()
        .map_err(|error| error.to_string())?
        .check()
        .await
        .map_err(|error| error.to_string())?;

    Ok(match update {
        Some(update) => DesktopUpdateStatus {
            configured: true,
            available: true,
            current_version: update.current_version,
            version: Some(update.version),
            date: update.date.map(|date| date.to_string()),
            body: update.body,
            endpoint: Some(endpoint),
        },
        None => DesktopUpdateStatus {
            configured: true,
            available: false,
            current_version,
            version: None,
            date: None,
            body: None,
            endpoint: Some(endpoint),
        },
    })
}

#[tauri::command]
async fn install_desktop_update(app: tauri::AppHandle) -> Result<(), String> {
    let Some(public_key) = updater_public_key() else {
        return Err("Desktop updater is not configured for this build".to_string());
    };

    let endpoint = updater_endpoint();
    let endpoint_url = updater_endpoint_url(&endpoint)?;
    let update = app
        .updater_builder()
        .pubkey(public_key)
        .endpoints(vec![endpoint_url])
        .map_err(|error| error.to_string())?
        .build()
        .map_err(|error| error.to_string())?
        .check()
        .await
        .map_err(|error| error.to_string())?;

    let Some(update) = update else {
        return Err("No desktop update is available".to_string());
    };

    update
        .download_and_install(
            |chunk_length, content_length| {
                log::debug!("Downloaded update chunk: {} of {:?}", chunk_length, content_length);
            },
            || {
                log::info!("Desktop update download finished");
            },
        )
        .await
        .map_err(|error| error.to_string())?;

    app.restart();
}

fn main() {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();

    let backend_state: BackendState = Arc::new(Mutex::new(ManagedProcess {
        port: 0,
        child: None,
        child_pid: None,
    }));

    let backend_state_clone = backend_state.clone();

    tauri::Builder::default()
        .manage(backend_state)
        .plugin(tauri_plugin_updater::Builder::new().build())
        .invoke_handler(tauri::generate_handler![
            get_backend_status,
            restart_backend,
            check_desktop_update,
            install_desktop_update,
        ])
        .setup(move |app| {
            let handle = app.handle().clone();
            let state = backend_state_clone.clone();

            let port = find_free_port();
            log::info!("DevSynapse AI starting — backend on port {}", port);

            let state_clone = state.clone();
            tauri::async_runtime::spawn(async move {
                match start_backend_with_port(port, &handle, &state_clone).await {
                    Ok(p) => log::info!("Backend ready on port {}", p),
                    Err(e) => log::error!("Backend start failed: {}", e),
                }

                // Wait for backend to be reachable
                let start = std::time::Instant::now();
                let timeout = std::time::Duration::from_secs(15);
                while start.elapsed() < timeout {
                    if is_port_open(port) {
                        log::info!(
                            "Backend health check OK ({}ms)",
                            start.elapsed().as_millis()
                        );
                        break;
                    }
                    tokio::time::sleep(std::time::Duration::from_millis(400)).await;
                }
                if start.elapsed() >= timeout {
                    log::warn!(
                        "Backend did not respond within {} seconds",
                        timeout.as_secs()
                    );
                }
            });

            // ── system tray ────────────────────────────────────────────────
            #[cfg(feature = "tray-icon")]
            {
                let show_item = MenuItemBuilder::with_id("show", "Show DevSynapse").build(app)?;
                let hide_item = MenuItemBuilder::with_id("hide", "Hide Window").build(app)?;
                let separator = tauri::menu::PredefinedMenuItem::separator(app)?;
                let quit_item = MenuItemBuilder::with_id("quit", "Quit").build(app)?;

                let menu = MenuBuilder::new(app)
                    .item(&show_item)
                    .item(&hide_item)
                    .item(&separator)
                    .item(&quit_item)
                    .build()?;

                let _tray = TrayIconBuilder::new()
                    .menu(&menu)
                    .tooltip("DevSynapse AI")
                    .icon(app.default_window_icon().unwrap().clone())
                    .on_menu_event(|app, event| match event.id().as_ref() {
                        "show" => {
                            if let Some(w) = app.get_webview_window("main") {
                                let _ = w.show();
                                let _ = w.set_focus();
                            }
                        }
                        "hide" => {
                            if let Some(w) = app.get_webview_window("main") {
                                let _ = w.hide();
                            }
                        }
                        "quit" => {
                            app.exit(0);
                        }
                        _ => {}
                    })
                    .on_tray_icon_event(|tray, event| {
                        if let TrayIconEvent::Click {
                            button: MouseButton::Left,
                            button_state: MouseButtonState::Up,
                            ..
                        } = event
                        {
                            let app = tray.app_handle();
                            if let Some(w) = app.get_webview_window("main") {
                                let _ = w.show();
                                let _ = w.set_focus();
                            }
                        }
                    })
                    .build(app)?;
            }

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                #[cfg(feature = "tray-icon")]
                {
                    let _ = window.hide();
                    api.prevent_close();
                }
                // Without tray-icon, close = quit (default behavior)
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
