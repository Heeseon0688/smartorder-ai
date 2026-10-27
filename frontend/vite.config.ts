import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
export default defineConfig({ plugins: [react()], build:{rollupOptions:{output:{manualChunks:{charts:['recharts']}}}}, server: {port:5173, strictPort:true, watch:{usePolling:process.env.CHOKIDAR_USEPOLLING==='true'}, proxy:{'/api':{target:process.env.API_TARGET||'http://127.0.0.1:8000',changeOrigin:true},'/ws':{target:process.env.API_TARGET||'ws://127.0.0.1:8000',ws:true}}}})
