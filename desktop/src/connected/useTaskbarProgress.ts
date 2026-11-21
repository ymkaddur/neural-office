import {useEffect, useRef} from 'react';
import {isTauri} from '@tauri-apps/api/core';
import {getCurrentWindow, ProgressBarStatus} from '@tauri-apps/api/window';

type Activity = {active:boolean; stopping:boolean; reading:boolean};

export function taskbarStatus({active, stopping, reading}:Activity):ProgressBarStatus {
  if (stopping) return ProgressBarStatus.Paused;
  return active || reading ? ProgressBarStatus.Indeterminate : ProgressBarStatus.None;
}

export function useTaskbarProgress(activity:Activity) {
  const status = taskbarStatus(activity);
  const queue = useRef(Promise.resolve());
  function send(state:ProgressBarStatus) {
    if (!isTauri()) return;
    queue.current = queue.current.then(() => getCurrentWindow().setProgressBar({status:state}))
      .catch(error => { console.warn('Taskbar progress', error); });
  }
  useEffect(() => {
    // Serialize updates so a delayed "running" request cannot win over completion.
    send(status);
  }, [status]);
  useEffect(() => () => send(ProgressBarStatus.None), []);
}
