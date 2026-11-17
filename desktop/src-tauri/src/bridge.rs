use crate::owned_job::OwnedJob;
use crate::protocol::{bounded_line, valid_response, MAX_COMMAND, MAX_PENDING, MAX_RESPONSE};
use serde_json::Value;
use std::collections::HashMap;
use std::io::{BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::{
    atomic::{AtomicBool, AtomicU64, Ordering},
    mpsc, Arc, Mutex,
};
use std::thread;
use std::time::{Duration, Instant};

type Reply = Result<Value, &'static str>;
type Pending = Arc<Mutex<HashMap<String, mpsc::SyncSender<Reply>>>>;

pub struct Bridge {
    outgoing: Mutex<Option<mpsc::SyncSender<Vec<u8>>>>,
    pending: Pending,
    child: Mutex<Child>,
    job: Mutex<Option<OwnedJob>>,
    next_id: AtomicU64,
    closing: Arc<AtomicBool>,
    disconnected: Arc<AtomicBool>,
}

fn fail_pending(pending: &Pending, reason: &'static str) {
    let entries = std::mem::take(&mut *pending.lock().unwrap_or_else(|e| e.into_inner()));
    for (_, sender) in entries {
        let _ = sender.try_send(Err(reason));
    }
}

fn configured_path(name: &str) -> Result<PathBuf, &'static str> {
    let value = std::env::var_os(name).ok_or("HOST_CONFIGURATION_REQUIRED")?;
    let path = PathBuf::from(value);
    let text = path.to_string_lossy();
    if !path.is_absolute() || text.starts_with("\\\\") || text.starts_with("//") {
        return Err("HOST_CONFIGURATION_INVALID");
    }
    Ok(path)
}

impl Bridge {
    pub fn disconnected_and_exited(&self) -> bool {
        self.disconnected.load(Ordering::Acquire)
            && self
                .child
                .lock()
                .unwrap_or_else(|e| e.into_inner())
                .try_wait()
                .is_ok_and(|s| s.is_some())
    }

    pub fn spawn() -> Result<Arc<Self>, &'static str> {
        // Only the trusted launcher configures paths. Webview messages cannot.
        let python = configured_path("NEURAL_OFFICE_PYTHON")?;
        let root = configured_path("NEURAL_OFFICE_ROOT")?;
        let state = configured_path("NEURAL_OFFICE_STATE")?;
        if !python.is_file() || !root.join("neural_office/desktop_stdio.py").is_file() {
            return Err("HOST_CONFIGURATION_INVALID");
        }
        let mut command = Command::new(python);
        command
            .args(["-B", "-m", "neural_office.desktop_stdio", "--state"])
            .arg(state)
            .current_dir(root)
            .env("PYTHONUTF8", "1")
            .env_remove("PYTHONPATH")
            .env_remove("PYTHONHOME")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null());
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            command.creation_flags(0x0800_0000);
        }
        let mut child = command.spawn().map_err(|_| "HOST_SIDECAR_START")?;
        let job = match OwnedJob::attach(&child) {
            Ok(job) => job,
            Err(error) => {
                let _ = child.kill();
                let _ = child.wait();
                return Err(error);
            }
        };
        let mut stdin = child.stdin.take().ok_or("HOST_PIPE_UNAVAILABLE")?;
        let stdout = child.stdout.take().ok_or("HOST_PIPE_UNAVAILABLE")?;
        let (outgoing, receiver) = mpsc::sync_channel::<Vec<u8>>(MAX_PENDING);
        let pending: Pending = Arc::new(Mutex::new(HashMap::new()));
        let closing = Arc::new(AtomicBool::new(false));
        let disconnected = Arc::new(AtomicBool::new(false));

        let write_closing = closing.clone();
        let write_disconnected = disconnected.clone();
        let write_pending = pending.clone();
        thread::Builder::new()
            .name("neural-office-pipe-write".into())
            .spawn(move || {
                while let Ok(bytes) = receiver.recv() {
                    if write_closing.load(Ordering::Acquire) {
                        break;
                    }
                    if stdin
                        .write_all(&bytes)
                        .and_then(|_| stdin.write_all(b"\n"))
                        .and_then(|_| stdin.flush())
                        .is_err()
                    {
                        write_disconnected.store(true, Ordering::Release);
                        fail_pending(&write_pending, "HOST_DISCONNECTED");
                        break;
                    }
                }
                // Dropping stdin signals EOF, triggering the service cancellation.
            })
            .map_err(|_| "HOST_THREAD_START")?;

        let read_pending = pending.clone();
        let read_disconnected = disconnected.clone();
        thread::Builder::new()
            .name("neural-office-pipe-read".into())
            .spawn(move || {
                let mut reader = BufReader::new(stdout);
                while let Ok(Some(raw)) = bounded_line(&mut reader, MAX_RESPONSE) {
                    let response: Value = match serde_json::from_slice(&raw) {
                        Ok(value) if valid_response(&value) => value,
                        _ => break,
                    };
                    let id = response["id"].as_str().unwrap();
                    if let Some(sender) = read_pending
                        .lock()
                        .unwrap_or_else(|e| e.into_inner())
                        .remove(id)
                    {
                        let _ = sender.try_send(Ok(response));
                    }
                    // A response to a timed-out command is ignored; IDs are never
                    // reused, and the frontend must reconcile the durable request key.
                }
                read_disconnected.store(true, Ordering::Release);
                fail_pending(&read_pending, "HOST_DISCONNECTED");
            })
            .map_err(|_| "HOST_THREAD_START")?;

        Ok(Arc::new(Self {
            outgoing: Mutex::new(Some(outgoing)),
            pending,
            child: Mutex::new(child),
            job: Mutex::new(Some(job)),
            next_id: AtomicU64::new(1),
            closing,
            disconnected,
        }))
    }

    pub fn request(&self, mut message: Value) -> Reply {
        if self.closing.load(Ordering::Acquire) || self.disconnected.load(Ordering::Acquire) {
            return Err("HOST_DISCONNECTED");
        }
        let client_id = message["id"].clone();
        let serial = self
            .next_id
            .fetch_update(Ordering::Relaxed, Ordering::Relaxed, |n| n.checked_add(1))
            .map_err(|_| "HOST_REQUEST_ID_EXHAUSTED")?;
        let transport_id = format!("p{serial}");
        message["id"] = Value::String(transport_id.clone());
        let bytes = serde_json::to_vec(&message).map_err(|_| "HOST_REQUEST_INVALID")?;
        if bytes.len() > MAX_COMMAND {
            return Err("HOST_REQUEST_SIZE");
        }
        let (sender, receiver) = mpsc::sync_channel(1);
        {
            let mut pending = self.pending.lock().unwrap_or_else(|e| e.into_inner());
            if pending.len() >= MAX_PENDING {
                return Err("HOST_BUSY");
            }
            pending.insert(transport_id.clone(), sender);
        }
        let sent = self
            .outgoing
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .as_ref()
            .ok_or("HOST_DISCONNECTED")
            .and_then(|out| out.try_send(bytes).map_err(|_| "HOST_BUSY"));
        if let Err(error) = sent {
            self.pending
                .lock()
                .unwrap_or_else(|e| e.into_inner())
                .remove(&transport_id);
            return Err(error);
        }
        let result = receiver
            .recv_timeout(Duration::from_secs(30))
            .unwrap_or(Err("HOST_RESPONSE_TIMEOUT"));
        self.pending
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .remove(&transport_id);
        result.map(|mut response| {
            response["id"] = client_id;
            response
        })
    }

    pub fn shutdown(&self) {
        if self.closing.swap(true, Ordering::AcqRel) {
            return;
        }
        self.outgoing
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .take();
        fail_pending(&self.pending, "HOST_CLOSING");
        let deadline = Instant::now() + Duration::from_secs(20);
        loop {
            let exited = self
                .child
                .lock()
                .unwrap_or_else(|e| e.into_inner())
                .try_wait()
                .map(|state| state.is_some())
                .unwrap_or(true);
            if exited || Instant::now() >= deadline {
                break;
            }
            thread::sleep(Duration::from_millis(50));
        }
        // Closing the job kills the owned process tree even if EOF cleanup failed.
        self.job.lock().unwrap_or_else(|e| e.into_inner()).take();
        let _ = self.child.lock().unwrap_or_else(|e| e.into_inner()).wait();
    }
}

impl Drop for Bridge {
    fn drop(&mut self) {
        self.shutdown();
    }
}
