import { defineConfig } from 'vite';

// A production-only CSP: dev mode needs Vite's stylesheet injection/HMR.
// The distributed preview makes no provider, telemetry or backend connections.
export default defineConfig(({command,mode})=>({
  // Native builds receive the stricter IPC-aware policy from Tauri. Keeping
  // the offline preview's connect-src 'none' there would disable native IPC.
  plugins: command==='build' && mode!=='native' ? [{
    name:'offline-preview-policy',
    transformIndexHtml() {
      return [{tag:'meta',attrs:{'http-equiv':'Content-Security-Policy',content:"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'"},injectTo:'head-prepend' as const}];
    },
  }] : [],
}));
