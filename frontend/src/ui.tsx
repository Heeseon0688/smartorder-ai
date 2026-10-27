import { useEffect, useRef, type ReactNode } from 'react'
import { X, LoaderCircle, AlertCircle, Menu as MenuIcon } from 'lucide-react'
import { statusLabel } from './api'
import type { Status } from './types'
export function Logo({small=false}:{small?:boolean}){return <div className={`brand ${small?'small':''}`}><span className="brand-icon"><MenuIcon size={24}/></span><span>SmartOrder<span className="brand-ai">AI</span></span></div>}
export function Loading(){return <div className="loading" role="status"><LoaderCircle className="spin"/>불러오는 중입니다…</div>}
export function ErrorBox({message,retry}:{message:string;retry?:()=>void}){return <div className="error-box" role="alert"><AlertCircle size={18}/><span>{message}</span>{retry&&<button onClick={retry}>다시 시도</button>}</div>}
export function Badge({status}:{status:Status}){return <span className={`status-badge ${status}`}><i/>{statusLabel[status]}</span>}
export function Empty({children}:{children:ReactNode}){return <div className="empty"><span>↗</span>{children}</div>}
export function Modal({title,children,onClose,wide=false}:{title:string;children:ReactNode;onClose:()=>void;wide?:boolean}){
  const ref=useRef<HTMLDivElement>(null)
  const closeRef=useRef(onClose);closeRef.current=onClose
  useEffect(()=>{
    const previous=document.activeElement as HTMLElement|null
    const previousOverflow=document.body.style.overflow;document.body.style.overflow='hidden'
    ref.current?.focus()
    const handle=(event:KeyboardEvent)=>{
      if(event.key==='Escape')closeRef.current()
      if(event.key==='Tab'){
        const list=ref.current?.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], input:not(:disabled), select, textarea, [tabindex="0"]')
        if(!list?.length)return
        const first=list[0],last=list[list.length-1]
        if(event.shiftKey&&(document.activeElement===first||document.activeElement===ref.current)){event.preventDefault();last.focus()}
        else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus()}
      }
    }
    document.addEventListener('keydown',handle)
    return()=>{document.body.style.overflow=previousOverflow;document.removeEventListener('keydown',handle);previous?.focus()}
  },[])
  return <div className="modal-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)onClose()}}><div className={`modal ${wide?'wide':''}`} role="dialog" aria-modal="true" aria-label={title} tabIndex={-1} ref={ref}><header><h2>{title}</h2><button className="icon-button" aria-label="닫기" onClick={onClose}><X/></button></header>{children}</div></div>
}
