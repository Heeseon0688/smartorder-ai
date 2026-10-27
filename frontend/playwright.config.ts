import { defineConfig } from '@playwright/test'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
const database = join(tmpdir(), `smartorder-e2e-${Date.now()}.db`)
export default defineConfig({
  testDir:'./e2e', fullyParallel:false, workers:1, timeout:45000,
  use:{baseURL:'http://127.0.0.1:5174',channel:process.platform==='darwin'?'chrome':undefined,viewport:{width:1440,height:1050},trace:'retain-on-failure',screenshot:'only-on-failure'},
  reporter:[['list'],['html',{open:'never'}]],
  webServer:[
    {command:'.venv/bin/python -m app.e2e_server',cwd:'../backend',url:'http://127.0.0.1:8001/api/health',reuseExistingServer:false,env:{DATABASE_URL:`sqlite:///${database}`,APP_ENV:'test',SEED_DEMO:'true',FRONTEND_URL:'http://127.0.0.1:5174',ALLOWED_ORIGINS:'["http://127.0.0.1:5174"]',OPENAI_API_KEY:'',MIGRATION_DATABASE_URL:'',E2E_DATABASE_URL:process.env.E2E_DATABASE_URL||''}},
    {command:'npm run dev -- --port 5174 --host 127.0.0.1',url:'http://127.0.0.1:5174',reuseExistingServer:false,env:{API_TARGET:'http://127.0.0.1:8001',VITE_WS_URL:'ws://localhost:8001/ws'}}
  ],
})
