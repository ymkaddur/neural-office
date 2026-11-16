import { StrictMode, Suspense, lazy } from 'react';
import { createRoot } from 'react-dom/client';
import { ConnectedWorkspace } from './connected/ConnectedWorkspace.tsx';
import './workspace/workspace.css';
const params=new URLSearchParams(location.search);
const preview=params.get('preview')==='1'||params.has('screen');
const PreviewWorkspace=lazy(async()=>({default:(await import('./workspace/Workspace.tsx')).Workspace}));
createRoot(document.getElementById('root')!).render(<StrictMode>{preview?<Suspense fallback={<main role="status">Abriendo los ejemplos de interfaz…</main>}><PreviewWorkspace/></Suspense>:<ConnectedWorkspace/>}</StrictMode>);
