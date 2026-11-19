// Desired sizes survive viewport changes; effective sizes always fit the container.
export const PANE_DEFAULT = { navigation:208, director:44, inspection:64 } as const;
export type PaneKind = keyof typeof PANE_DEFAULT;
export function paneBounds(kind:PaneKind, extent:number) {
  if(kind==='navigation') return {min:180,max:280};
  const usable=Number.isFinite(extent)?Math.max(0,extent-9):0;
  if(usable<620) return {min:50,max:50}; // stacked layout; no interactive divider
  return {min:300/usable*100,max:(usable-320)/usable*100};
}
export function clampPane(kind:PaneKind, value:number, extent:number) {
  const {min,max}=paneBounds(kind,extent);
  return Math.min(max,Math.max(min,Number.isFinite(value)?value:PANE_DEFAULT[kind]));
}
export function readPane(kind:PaneKind, storage:Pick<Storage,'getItem'>|null) {
  try {
    const raw=storage?.getItem(`neural-office.v541.pane.${kind}`);
    if(!raw?.trim()) return PANE_DEFAULT[kind];
    const value=Number(raw), min=kind==='navigation'?180:10, max=kind==='navigation'?280:90;
    return Number.isFinite(value)&&value>=min&&value<=max?value:PANE_DEFAULT[kind];
  } catch { return PANE_DEFAULT[kind]; }
}
export function keyPane(kind:PaneKind, key:string, value:number, extent:number, shift=false) {
  const {min,max}=paneBounds(kind,extent), step=(kind==='navigation'?8:2)*(shift?5:1);
  if(key==='Home') return min;
  if(key==='End') return max;
  if(key==='ArrowLeft') return clampPane(kind,value-step,extent);
  if(key==='ArrowRight') return clampPane(kind,value+step,extent);
  return null;
}
