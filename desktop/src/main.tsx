import { StrictMode, Suspense, lazy } from 'react';
import { createRoot } from 'react-dom/client';
import { ConnectedWorkspace } from './connected/ConnectedWorkspace.tsx';
import './workspace/workspace.css';
const params=new URLSearchParams(location.search);
// Historical fixtures are a development tool, never a production route.
const preview=import.meta.env.DEV&&params.get('preview')==='1';
const PreviewWorkspace=import.meta.env.DEV?lazy(async()=>({default:(await import('./workspace/Workspace.tsx')).Workspace})):null;
createRoot(document.getElementById('root')!).render(<StrictMode>{preview&&PreviewWorkspace?<Suspense fallback={<main role="status">Abriendo los ejemplos de interfaz…</main>}><PreviewWorkspace/></Suspense>:<ConnectedWorkspace/>}</StrictMode>);
