import { spawnSync } from 'node:child_process'
import { cp, mkdir, rm, writeFile } from 'node:fs/promises'

const value=process.env.BACKEND_ORIGIN
if(!value)throw new Error('Set BACKEND_ORIGIN=https://your-service.onrender.com in Vercel build environment')
const backend=new URL(value)
if(backend.protocol!=='https:'||backend.username||backend.password||backend.search||backend.hash||backend.pathname!=='/'){
  throw new Error('BACKEND_ORIGIN must be an HTTPS origin without credentials, path or query')
}
const ws=new URL('/ws',backend);ws.protocol='wss:'
const build=spawnSync('npm',['run','build'],{stdio:'inherit',env:{...process.env,VITE_API_BASE_URL:'/api',VITE_WS_URL:ws.href,VITE_DEMO_MODE:'false'}})
if(build.status!==0)process.exit(build.status||1)
// Build Output API: static SPA + environment-derived external REST proxy.
await rm('.vercel/output',{recursive:true,force:true})
await mkdir('.vercel/output/static',{recursive:true})
await cp('dist','.vercel/output/static',{recursive:true})
const config={version:3,routes:[
  {src:'/api/(.*)',dest:backend.origin+'/api/$1',headers:{'Cache-Control':'no-store'}},
  {src:'/(.*)',headers:{'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','X-Frame-Options':'DENY'},continue:true},
  {handle:'filesystem'},
  {src:'/(.*)',dest:'/index.html'},
]}
await writeFile('.vercel/output/config.json',JSON.stringify(config,null,2)+'\n')
console.log('Vercel static output and same-origin REST routes prepared. No deployment performed.')
