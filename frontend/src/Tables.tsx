import { useEffect, useState } from 'react'
import { Download, ExternalLink, Printer, QrCode } from 'lucide-react'
import { api } from './api'
import { ErrorBox, Loading } from './ui'
type TableInfo={id:number;number:number;url:string}
export default function Tables({onUnauthorized}:{onUnauthorized:(e:unknown)=>void}){
  const [tables,setTables]=useState<TableInfo[]>([]),[error,setError]=useState('')
  useEffect(()=>{let active=true;api<TableInfo[]>('/admin/tables').then(data=>{if(active)setTables(data)}).catch(e=>{if(active){setError(e.message);onUnauthorized(e)}});return()=>{active=false}},[onUnauthorized])
  return <><div className="page-heading"><div><span className="tiny-label">SCAN. ORDER. ENJOY.</span><h1>테이블 · QR 관리</h1><p>테이블마다 준비된 QR코드로 간편한 주문을 시작하세요.</p></div><button className="secondary" onClick={()=>window.print()}><Printer size={17}/> QR 인쇄</button></div><div className="qr-guide"><span><QrCode size={24}/></span><div><strong>한 번의 스캔으로, 맛있는 주문의 시작</strong><p>QR코드를 다운로드하거나 인쇄해 테이블에 비치하세요. 휴대폰 테스트 시 README의 같은 Wi-Fi 설정을 참고하세요.</p></div></div>{error&&<ErrorBox message={error}/>} {!tables.length&&!error?<Loading/>:<div className="qr-grid">{tables.map(t=><article className="qr-card" key={t.id}><span className="tiny-label">SMART BURGER</span><h2>TABLE <b>{String(t.number).padStart(2,'0')}</b></h2><img src={`/api/admin/tables/${t.id}/qr`} alt={`테이블 ${t.number} 주문 QR코드`}/><h3>스캔하고, 맛있게 즐기세요.</h3><p>카메라로 QR코드를 비춰 주세요</p><div><a className="secondary" href={`/api/admin/tables/${t.id}/qr`} download={`smartburger-table-${t.number}.png`}><Download size={15}/> 저장</a><a className="primary" href={new URL(t.url).pathname+new URL(t.url).search} target="_blank" rel="noreferrer"><ExternalLink size={15}/> 주문 화면</a></div></article>)}</div>}</>
}
