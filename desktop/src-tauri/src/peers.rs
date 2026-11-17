use crate::bridge::Bridge;
use std::sync::{Arc, Mutex};

pub type BridgeSlot = Mutex<Result<Arc<Bridge>, &'static str>>;

pub fn read_peer(slot: &BridgeSlot, handshake: bool) -> Result<Arc<Bridge>, &'static str> {
    let mut current = slot.lock().unwrap_or_else(|e| e.into_inner());
    let reconnect = match &*current {
        Err("HOST_CLOSING") => return Err("HOST_CLOSING"),
        Ok(peer) => handshake && peer.disconnected_and_exited(),
        Err(_) => handshake,
    };
    if reconnect {
        if let Ok(old) = &*current {
            old.shutdown();
        }
        *current = Bridge::spawn();
    }
    current.clone()
}

pub fn close_peer(slot: &BridgeSlot) {
    let old = std::mem::replace(
        &mut *slot.lock().unwrap_or_else(|e| e.into_inner()),
        Err("HOST_CLOSING"),
    );
    if let Ok(peer) = old {
        peer.shutdown();
    }
}
