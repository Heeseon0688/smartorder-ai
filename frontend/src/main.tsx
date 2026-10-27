import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ErrorBox, Loading } from './ui'
import { api } from './api'
const Customer = React.lazy(() => import('./Customer'))
const Admin = React.lazy(() => import('./Admin'))
import './styles.css'
function DemoEntry(){
  const [url,setUrl]=React.useState(''),[error,setError]=React.useState('')
  React.useEffect(()=>{api<{order_url:string}>('/demo').then(d=>{const u=new URL(d.order_url);setUrl(u.pathname+u.search)}).catch(e=>setError(e.message))},[])
  if(error)return <div className="customer-container"><ErrorBox message={error}/></div>
  return url?<Navigate to={url} replace/>:<Loading/>
}
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><BrowserRouter><React.Suspense fallback={<Loading/>}><Routes><Route path="/" element={<Navigate to="/admin" replace/>}/><Route path="/demo" element={<DemoEntry/>}/><Route path="/order/:slug/:number" element={<Customer/>}/><Route path="/admin/*" element={<Admin/>}/><Route path="*" element={<div className="not-found"><h1>페이지를 찾을 수 없습니다.</h1><a href="/admin">SmartOrder로 돌아가기</a></div>}/></Routes></React.Suspense></BrowserRouter></React.StrictMode>)
