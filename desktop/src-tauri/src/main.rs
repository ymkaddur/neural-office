#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
#[cfg(not(windows))]
compile_error!("This host is verified only for Windows process ownership.");

mod bridge;
mod owned_job;
mod peers;
mod protocol;

use bridge::Bridge;
use peers::{close_peer, read_peer, BridgeSlot};
use protocol::{allowed_navigation, cancelled_picker, validate_request};
use serde_json::{json, Value};
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc, Mutex,
};
use tauri::Manager;

struct Host {
    bridge: Arc<BridgeSlot>,
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
    let slot = host.bridge.clone();
    if host.closing.load(Ordering::Acquire) {
        return Err("HOST_CLOSING".into());
    }
    let multiple = message["method"] == "attachments.pick";
    if multiple || message["method"] == "source.pick" {
        let bridge = tauri::async_runtime::spawn_blocking(move || read_peer(&slot, false))
            .await
            .map_err(|_| "HOST_REQUEST_FAILED".to_string())?
            .map_err(str::to_owned)?;
        if host.picking.swap(true, Ordering::AcqRel) {
            return Err("HOST_PICKER_BUSY".into());
        }
        let selected = tauri::async_runtime::spawn_blocking(move || {
            let dialog = rfd::FileDialog::new();
            if multiple {
                dialog
                    .set_title("Adjuntar archivos al hilo")
                    .add_filter("Documentos e imágenes", &["pdf", "zip", "json", "png", "jpg", "jpeg", "htm", "html"])
                    .pick_files()
            } else {
                dialog
                    .set_title("Elegir HTML para revisar")
                    .add_filter("Documento HTML", &["html", "htm"])
                    .pick_file()
                    .map(|file| vec![file])
            }
        })
        .await;
        host.picking.store(false, Ordering::Release);
        let selected = selected.map_err(|_| "HOST_PICKER_FAILED")?;
        let Some(paths) = selected else {
            let mut reply = cancelled_picker(&message["id"]);
            if multiple {
                reply["result"] = json!([]);
            }
            return Ok(reply);
        };
        if host.closing.load(Ordering::Acquire) {
            return Err("HOST_CLOSING".into());
        }
        if paths.is_empty() || paths.len() > 8 {
            return Err("HOST_PICKER_FILE_LIMIT".into());
        }
        let local: Vec<&str> = paths
            .iter()
            .map(|path| path.to_str().ok_or("HOST_PICKER_ENCODING"))
            .collect::<Result<_, _>>()?;
        // Only paths returned by the operating-system dialog reach the private pipe.
        let captured = if multiple {
            json!({"version":1,"id":message["id"],"method":"host.attachments.capture",
                "params":{"project_id":message["params"]["project_id"],
                          "thread_id":message["params"]["thread_id"],"paths":local}})
        } else {
            json!({"version":1,"id":message["id"],"method":"host.source.capture",
                "params":{"project_id":message["params"]["project_id"],"path":local[0]}})
        };
        return tauri::async_runtime::spawn_blocking(move || bridge.request(captured))
            .await
            .map_err(|_| "HOST_REQUEST_FAILED".to_string())?
            .map_err(str::to_owned);
    }
    tauri::async_runtime::spawn_blocking(move || {
        // Only a read-only handshake can create a replacement for a dead peer.
        let bridge = read_peer(&slot, message["method"] == "describe")?;
        bridge.request(message)
    })
    .await
    .map_err(|_| "HOST_REQUEST_FAILED".to_string())?
    .map_err(str::to_owned)
}

fn main() {
    let app = tauri::Builder::default()
        .manage(Host {
            bridge: Arc::new(Mutex::new(Bridge::spawn())),
            closing: AtomicBool::new(false),
            picking: AtomicBool::new(false),
        })
        .invoke_handler(tauri::generate_handler![desktop_request])
        .setup(|app| {
            let window = tauri::WebviewWindowBuilder::new(
                app,
                "main",
                tauri::WebviewUrl::App("index.html".into()),
            )
            .title(concat!("Neural Office · V", env!("CARGO_PKG_VERSION")))
            .inner_size(1320.0, 860.0)
            .min_inner_size(760.0, 540.0)
            .on_navigation(|url| allowed_navigation(url, cfg!(debug_assertions)))
            .on_new_window(|_, _| tauri::webview::NewWindowResponse::Deny)
            .build()?;
            // Keep the normal/restored size inside a small monitor's work area,
            // then let Windows maximize it without covering the taskbar.
            if let Some(monitor) = window.current_monitor()? {
                let outer = window.outer_size()?;
                let area = monitor.work_area();
                if outer.width > area.size.width || outer.height > area.size.height {
                    let inner = window.inner_size()?;
                    let fit = tauri::PhysicalSize::new(
                        inner
                            .width
                            .min(
                                area.size
                                    .width
                                    .saturating_sub(outer.width.saturating_sub(inner.width)),
                            )
                            .max(1),
                        inner
                            .height
                            .min(
                                area.size
                                    .height
                                    .saturating_sub(outer.height.saturating_sub(inner.height)),
                            )
                            .max(1),
                    );
                    let minimum = tauri::LogicalSize::new(760.0, 540.0)
                        .to_physical::<u32>(window.scale_factor()?);
                    window.set_min_size(Some(tauri::PhysicalSize::new(
                        minimum.width.min(fit.width),
                        minimum.height.min(fit.height),
                    )))?;
                    window.set_size(fit)?;
                    window.set_position(area.position)?;
                    window.maximize()?;
                }
            }
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
                let slot = host.bridge.clone();
                tauri::async_runtime::spawn_blocking(move || {
                    close_peer(&slot);
                    handle.exit(0);
                });
            }
        })
        .build(tauri::generate_context!())
        .expect("Neural Office could not create its desktop window");
    app.run(|handle, event| {
        if let tauri::RunEvent::Exit = event {
            close_peer(&handle.state::<Host>().bridge);
        }
    });
}

#[cfg(all(test, feature = "custom-protocol"))]
mod packaged_assets {
    #[test]
    fn release_contains_its_frontend_without_a_vite_server() {
        assert!(
            !tauri::is_dev(),
            "The distributed host must use its embedded assets"
        );
        let context: tauri::Context<tauri::Wry> = tauri::generate_context!();
        let key = "/index.html".into();
        let html = context
            .assets()
            .get(&key)
            .expect("Packaged index.html is missing");
        assert!(std::str::from_utf8(&html)
            .unwrap()
            .contains("Neural Office"));
    }
}
