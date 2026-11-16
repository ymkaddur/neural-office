#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
#[cfg(not(windows))]
compile_error!("This V5.5 host is verified only for Windows process ownership.");

mod bridge;
mod owned_job;
mod protocol;

use bridge::Bridge;
use protocol::{allowed_navigation, cancelled_picker, validate_request};
use serde_json::{json, Value};
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc,
};
use tauri::Manager;

struct Host {
    bridge: Result<Arc<Bridge>, &'static str>,
    closing: AtomicBool,
    picking: AtomicBool,
}

#[tauri::command]
async fn desktop_request(
    window: tauri::WebviewWindow,
    host: tauri::State<'_, Host>,
    message: Value,
) -> Result<Value, String> {
    if window.label() != "main"
        || !window
            .url()
            .is_ok_and(|u| allowed_navigation(&u, cfg!(debug_assertions)))
    {
        return Err("HOST_ORIGIN_DENIED".into());
    }
    validate_request(&message).map_err(str::to_owned)?;
    let bridge = host.bridge.as_ref().map_err(|e| e.to_string())?.clone();
    if message["method"] == "source.pick" {
        if host.picking.swap(true, Ordering::AcqRel) {
            return Err("HOST_PICKER_BUSY".into());
        }
        let selected = tauri::async_runtime::spawn_blocking(move || {
            rfd::FileDialog::new()
                .set_title("Elegir HTML para revisar")
                .add_filter("Documento HTML", &["html", "htm"])
                .pick_file()
        })
        .await;
        host.picking.store(false, Ordering::Release);
        let selected = selected.map_err(|_| "HOST_PICKER_FAILED")?;
        let Some(path) = selected else {
            return Ok(cancelled_picker(&message["id"]));
        };
        // No JS-supplied path crosses this boundary. Python freezes the selected
        // file and returns an opaque expiring token, never the local path.
        let path = path.to_str().ok_or("HOST_PICKER_ENCODING")?;
        let captured = json!({"version":1,"id":message["id"],"method":"host.source.capture",
            "params":{"project_id":message["params"]["project_id"],"path":path}});
        return tauri::async_runtime::spawn_blocking(move || bridge.request(captured))
            .await
            .map_err(|_| "HOST_REQUEST_FAILED".to_string())?
            .map_err(str::to_owned);
    }
    tauri::async_runtime::spawn_blocking(move || bridge.request(message))
        .await
        .map_err(|_| "HOST_REQUEST_FAILED".to_string())?
        .map_err(str::to_owned)
}

fn main() {
    let app = tauri::Builder::default()
        .manage(Host {
            bridge: Bridge::spawn(),
            closing: AtomicBool::new(false),
            picking: AtomicBool::new(false),
        })
        .invoke_handler(tauri::generate_handler![desktop_request])
        .setup(|app| {
            tauri::WebviewWindowBuilder::new(
                app,
                "main",
                tauri::WebviewUrl::App("index.html".into()),
            )
            .title("Neural Office · V5.5")
            .inner_size(1320.0, 860.0)
            .min_inner_size(760.0, 540.0)
            .on_navigation(|url| allowed_navigation(url, cfg!(debug_assertions)))
            .on_new_window(|_, _| tauri::webview::NewWindowResponse::Deny)
            .build()?;
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let handle = window.app_handle().clone();
                let host = handle.state::<Host>();
                if host.closing.swap(true, Ordering::AcqRel) {
                    return;
                }
                let bridge = host.bridge.as_ref().ok().cloned();
                tauri::async_runtime::spawn_blocking(move || {
                    if let Some(bridge) = bridge {
                        bridge.shutdown();
                    }
                    handle.exit(0);
                });
            }
        })
        .build(tauri::generate_context!())
        .expect("Neural Office could not create its desktop window");
    app.run(|handle, event| {
        if let tauri::RunEvent::Exit = event {
            if let Ok(bridge) = &handle.state::<Host>().bridge {
                bridge.shutdown();
            }
        }
    });
}
