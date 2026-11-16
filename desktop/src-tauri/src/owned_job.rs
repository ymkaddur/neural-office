//! A host crash closes this handle, killing the sidecar and its descendants.
//! This owns processes; it is not a filesystem/network sandbox.
#[cfg(windows)]
mod implementation {
    use std::os::windows::io::AsRawHandle;
    use std::process::Child;
    use windows_sys::Win32::Foundation::CloseHandle;
    use windows_sys::Win32::System::JobObjects::{
        AssignProcessToJobObject, CreateJobObjectW, JobObjectExtendedLimitInformation,
        SetInformationJobObject, JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    };

    pub struct OwnedJob(isize);
    impl OwnedJob {
        pub fn attach(child: &Child) -> Result<Self, &'static str> {
            // The child is still initializing and receives no commands until
            // assignment succeeds. Failure kills it before the bridge is exposed.
            let handle = unsafe { CreateJobObjectW(std::ptr::null(), std::ptr::null()) };
            if handle.is_null() {
                return Err("HOST_JOB_CREATE");
            }
            let job = Self(handle as isize);
            let mut limits: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = unsafe { std::mem::zeroed() };
            limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
            let ok = unsafe {
                SetInformationJobObject(
                    handle,
                    JobObjectExtendedLimitInformation,
                    &limits as *const _ as *const _,
                    std::mem::size_of_val(&limits) as u32,
                )
            };
            if ok == 0 || unsafe { AssignProcessToJobObject(handle, child.as_raw_handle()) } == 0 {
                return Err("HOST_JOB_ASSIGN");
            }
            Ok(job)
        }
    }
    impl Drop for OwnedJob {
        fn drop(&mut self) {
            unsafe {
                CloseHandle(self.0 as _);
            }
        }
    }
}
#[cfg(windows)]
pub use implementation::OwnedJob;
