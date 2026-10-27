import { useEffect, useRef, useState } from 'react'
export class ApiError extends Error { status:number; constructor(message:string,status:number){super(message);this.status=status} }
export async function api<T>(path:string,init:RequestInit={}):Promise<T>{
  const response=await fetch((import.meta.env.VITE_API_BASE_URL||'/api').replace(/\/$/,'')+path,{...init,credentials:'include',headers:{'Content-Type':'application/json',...init.headers}})
  if(!response.ok){
    const body=await response.json().catch(()=>({}))
    throw new ApiError(typeof body.detail==='string'?body.detail:'입력 내용을 확인해 주세요.',response.status)
  }
  return response.json()
}
// getRandomValues also works on HTTP LAN origins; randomUUID requires a secure context.
export function randomToken(){return Array.from(crypto.getRandomValues(new Uint8Array(24)),b=>b.toString(16).padStart(2,'0')).join('')}
export const money=(value:number)=>new Intl.NumberFormat('ko-KR').format(value)+'원'
export const time=(value:string)=>new Date(value).toLocaleTimeString('ko-KR',{hour:'2-digit',minute:'2-digit',hour12:false,timeZone:'Asia/Seoul'})
export const dateTime=(value:string)=>new Date(value).toLocaleString('ko-KR',{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',timeZone:'Asia/Seoul'})
export const statusLabel={pending:'접수 대기',cooking:'조리 중',completed:'완료'}
export function useRealtime(auth:Record<string,unknown>,onEvent:(type:string)=>void){
  const [connected,setConnected]=useState(false)
  const callback=useRef(onEvent);callback.current=onEvent
  const serialized=JSON.stringify(auth)
  useEffect(()=>{
    let ws:WebSocket|undefined, retry:ReturnType<typeof setTimeout>,stop=false
    const connect=async()=>{
      if(stop)return
      try{
        const payload=JSON.parse(serialized)
        if(payload.role==='admin'){
          const {ticket}=await api<{ticket:string}>('/auth/ws-ticket',{method:'POST'})
          payload.ticket=ticket
        }
        if(stop)return
        const target=import.meta.env.VITE_WS_URL||`${location.protocol==='https:'?'wss:':'ws:'}//${location.host}/ws`
        ws=new WebSocket(target)
        ws.onopen=()=>ws?.send(JSON.stringify(payload))
        ws.onmessage=e=>{const data=JSON.parse(e.data);if(data.type==='connected'){setConnected(true);callback.current('refresh')}else if(data.type!=='heartbeat')callback.current(data.type)}
        ws.onerror=()=>ws?.close()
        ws.onclose=e=>{setConnected(false);if(!stop && e.code!==4401 && e.code!==4403)retry=setTimeout(connect,3000)}
      }catch(e){
        setConnected(false)
        if(!stop && !(e instanceof ApiError&&e.status===401))retry=setTimeout(connect,3000)
      }
    }
    connect()
    const interval=setInterval(()=>callback.current('refresh'),15000)
    return()=>{stop=true;clearTimeout(retry);clearInterval(interval);ws?.close()}
  },[serialized])
  return connected
}
