// Exercise the production slot with independently observable child lifetimes.
#[path = "../src/peers.rs"]
mod peers;

mod bridge {
    use std::sync::{
        atomic::{AtomicBool, Ordering},
        Arc,
    };

    #[derive(Debug, Default)]
    pub struct Bridge {
        pub exited: AtomicBool,
        pub closed: AtomicBool,
    }
    impl Bridge {
        pub fn spawn() -> Result<Arc<Self>, &'static str> {
            Ok(Arc::new(Self::default()))
        }
        pub fn disconnected_and_exited(&self) -> bool {
            self.exited.load(Ordering::SeqCst)
        }
        pub fn shutdown(&self) {
            self.closed.store(true, Ordering::SeqCst);
        }
    }
}

use bridge::Bridge;
use peers::{close_peer, read_peer, BridgeSlot};
use std::sync::{atomic::Ordering, Arc, Barrier};

#[test]
fn a_write_cannot_create_a_peer_and_close_is_final() {
    let slot = BridgeSlot::new(Err("HOST_SIDECAR_START"));
    assert_eq!(read_peer(&slot, false).unwrap_err(), "HOST_SIDECAR_START");
    let first = read_peer(&slot, true).unwrap();
    assert!(Arc::ptr_eq(&first, &read_peer(&slot, true).unwrap()));
    first.exited.store(true, Ordering::SeqCst);
    assert!(Arc::ptr_eq(&first, &read_peer(&slot, false).unwrap()));
    let second = read_peer(&slot, true).unwrap();
    assert!(first.closed.load(Ordering::SeqCst));
    assert!(!Arc::ptr_eq(&first, &second));
    close_peer(&slot);
    assert!(second.closed.load(Ordering::SeqCst));
    for handshake in [false, true] {
        assert_eq!(read_peer(&slot, handshake).unwrap_err(), "HOST_CLOSING");
    }
}

#[test]
fn simultaneous_handshakes_observe_one_replacement() {
    let first = Bridge::spawn().unwrap();
    first.exited.store(true, Ordering::SeqCst);
    let slot = Arc::new(BridgeSlot::new(Ok(first.clone())));
    let ready = Arc::new(Barrier::new(8));
    let threads: Vec<_> = (0..8)
        .map(|_| {
            let slot = slot.clone();
            let ready = ready.clone();
            std::thread::spawn(move || {
                ready.wait();
                read_peer(&slot, true).unwrap()
            })
        })
        .collect();
    let observed: Vec<_> = threads
        .into_iter()
        .map(|thread| thread.join().unwrap())
        .collect();
    assert!(observed.iter().all(|peer| Arc::ptr_eq(peer, &observed[0])));
    assert!(!Arc::ptr_eq(&observed[0], &first));
    assert!(first.closed.load(Ordering::SeqCst));
    close_peer(&slot);
}
