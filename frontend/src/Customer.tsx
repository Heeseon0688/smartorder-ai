import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft, ArrowRight, Check, ChefHat, ChevronRight, Clock3, Leaf, Minus, Plus, ReceiptText, Search, ShoppingBag, Sparkles, Trash2, UtensilsCrossed } from 'lucide-react'
import { api, ApiError, dateTime, money, statusLabel, randomToken, useRealtime } from './api'
import type { Catalog, Menu, Order } from './types'
import { Badge, Empty, ErrorBox, Loading, Logo, Modal } from './ui'

type CartItem={key:string;menu:Menu;quantity:number;optionIds:number[]}
const unitPrice=(item:CartItem)=>item.menu.price+item.menu.options.filter(o=>item.optionIds.includes(o.id)).reduce((sum,o)=>sum+o.price,0)
export default function Customer(){
  const {slug='',number='1'}=useParams(),[params]=useSearchParams(),token=params.get('token')||''
  const storageKey=`smartorder:${slug}:${number}`
  const [customerToken]=useState(()=>{let value=localStorage.getItem('smartorder.customer');if(!value){value=randomToken();localStorage.setItem('smartorder.customer',value)}return value})
  const [catalog,setCatalog]=useState<Catalog|null>(null),[error,setError]=useState(''),[orders,setOrders]=useState<Order[]>([])
  const [category,setCategory]=useState(0),[search,setSearch]=useState(''),[selected,setSelected]=useState<Menu|null>(null)
  const [options,setOptions]=useState<number[]>([]),[quantity,setQuantity]=useState(1)
  const [cart,setCart]=useState<CartItem[]>(()=>{try{return JSON.parse(localStorage.getItem(storageKey+'.cart')||'[]')}catch{return []}})
  const [cartOpen,setCartOpen]=useState(false),[historyOpen,setHistoryOpen]=useState(false),[success,setSuccess]=useState<Order|null>(null)
  const [note,setNote]=useState(''),[busy,setBusy]=useState(false),[checkoutError,setCheckoutError]=useState(''),[notice,setNotice]=useState('')
  const headers=useMemo(()=>({'X-Table-Token':token,'X-Customer-Token':customerToken}),[token,customerToken])
  const base=`/stores/${slug}/tables/${number}`
  const load=useCallback(async()=>{
    try{const [menuData,orderData]=await Promise.all([api<Catalog>(base+'/menu',{headers}),api<Order[]>(base+'/orders',{headers})]);setCatalog(menuData);setOrders(orderData);setError('');setSuccess(old=>old?orderData.find(o=>o.id===old.id)||old:null)}catch(e){setError((e as Error).message)}
  },[base,headers])
  useEffect(()=>{void load()},[load])
  useEffect(()=>{localStorage.setItem(storageKey+'.cart',JSON.stringify(cart))},[cart,storageKey])
  useEffect(()=>{if(!notice)return;const t=setTimeout(()=>setNotice(''),3000);return()=>clearTimeout(t)},[notice])
  const connected=useRealtime({role:'customer',slug,table:Number(number),token},()=>void load())
  const total=cart.reduce((sum,item)=>sum+unitPrice(item)*item.quantity,0),count=cart.reduce((sum,item)=>sum+item.quantity,0)
  const openMenu=(menu:Menu)=>{setSelected(menu);setOptions([]);setQuantity(1)}
  function addToCart(){
    if(!selected)return
    const key=`${selected.id}:${[...options].sort().join(',')}`
    setCart(old=>{const match=old.find(x=>x.key===key);return match?old.map(x=>x.key===key?{...x,quantity:Math.min(20,x.quantity+quantity)}:x):[...old,{key,menu:selected,optionIds:options,quantity}]})
    setSelected(null);setNotice('장바구니에 담았어요')
  }
  async function checkout(){
    if(busy||!cart.length)return
    setBusy(true);setCheckoutError('')
    const payload={items:cart.map(i=>({menu_id:i.menu.id,quantity:i.quantity,option_ids:i.optionIds})),note}
    const signature=JSON.stringify(payload)
    let attempt:{signature:string;key:string}|null=null
    try{attempt=JSON.parse(localStorage.getItem(storageKey+'.attempt')||'null')}catch{ /* start a new attempt */ }
    if(attempt?.signature!==signature)attempt={signature,key:randomToken()}
    localStorage.setItem(storageKey+'.attempt',JSON.stringify(attempt))
    try{
      const order=await api<Order>(base+'/orders',{method:'POST',headers:{...headers,'Idempotency-Key':attempt!.key},body:signature})
      setSuccess(order);setCart([]);setCartOpen(false);setNote('');localStorage.removeItem(storageKey+'.attempt');void load()
    }catch(e){setCheckoutError((e as Error).message);if(e instanceof ApiError&&e.status<500)localStorage.removeItem(storageKey+'.attempt')}
    finally{setBusy(false)}
  }
  const shown=catalog?.menus.filter(m=>(!category||m.category_id===category)&&m.name.toLowerCase().includes(search.toLowerCase()))||[]
  return <div className="customer-page">
    <header className="customer-header"><Link to="/admin" aria-label="관리자 화면"><Logo small/></Link><div className="table-chip"><UtensilsCrossed size={15}/> TABLE {number.padStart(2,'0')}</div></header>
    {!catalog ? error?<div className="customer-container"><ErrorBox message={error} retry={load}/></div>:<Loading/> : <>
      <section className="store-hero"><img src="/images/burger.jpg" alt="갓 구운 수제 버거"/><div className="hero-shade"/><div className="hero-copy"><span className="eyebrow"><i/> FRESHLY MADE, JUST FOR YOU</span><h1>{catalog.store.name}<span>오늘도, 맛있는 순간.</span></h1><p>{catalog.store.description}</p><div className="hero-tags"><span><Clock3 size={14}/> 약 10–15분</span><span><Leaf size={14}/> 신선한 재료</span><span>매장에서 즐기는 수제 버거</span></div></div><span className="hero-stamp">MADE WITH<br/><b>GOOD<br/>INGREDIENTS</b><br/>SINCE 2024</span></section>
      <div className="customer-container">
        <div className="welcome-bar"><div><span className="tiny-orange">WELCOME TO SMART BURGER</span><h2>무엇을 드시겠어요? <span>🍔</span></h2><p>좋아하는 메뉴를 담고, 편하게 주문하세요.</p></div><button className="secondary" onClick={()=>setHistoryOpen(true)}><ReceiptText size={17}/> 주문 내역 {orders.length>0&&<b>{orders.length}</b>}</button></div>
        <div className="menu-toolbar"><div className="category-tabs"><button className={!category?'active':''} onClick={()=>setCategory(0)}>전체 메뉴</button>{catalog.categories.map(c=><button key={c.id} className={category===c.id?'active':''} onClick={()=>setCategory(c.id)}>{c.name}</button>)}</div><label className="search-box"><Search size={17}/><input aria-label="메뉴 검색" placeholder="먹고 싶은 메뉴를 찾아보세요" value={search} onChange={e=>setSearch(e.target.value)}/></label></div>
        {error&&<ErrorBox message={error} retry={load}/>}
        <div className="menu-section-heading"><h3>{category?catalog.categories.find(c=>c.id===category)?.name:'오늘의 맛있는 선택'} <span>{shown.length}</span></h3><span>주문 즉시 정성껏 만들어요</span></div>
        <div className="menu-grid">{shown.map(m=><button className={`food-card ${m.sold_out?'sold-out':''}`} key={m.id} onClick={()=>openMenu(m)} disabled={m.sold_out} aria-label={`${m.name} ${money(m.price)}${m.sold_out?' 품절':''}`}><div className="food-image"><img src={m.image_url} alt={m.name} loading="lazy"/>{m.badge&&<span className="food-badge">{m.badge}</span>}{m.sold_out&&<div className="sold-out-overlay">오늘은 품절이에요</div>}</div><div className="food-content"><h3>{m.name}</h3><p>{m.description}</p><div className="food-bottom"><strong>{money(m.price)}</strong><span className="add-icon"><Plus size={20}/></span></div></div></button>)}</div>
        {!shown.length&&<Empty>검색한 메뉴가 없습니다.</Empty>}
        <div className="ingredient-note"><Leaf size={22}/><div><strong>좋은 재료가 만드는, 기분 좋은 한 끼</strong><p>알레르기나 원산지 정보는 주문 전 매장 직원에게 문의해 주세요.</p></div></div>
        <footer className="customer-footer"><Logo small/><span>맛있는 순간을 더 간편하게.</span><span className={`connection ${connected?'online':''}`}><i/>{connected?'실시간 주문 연결됨':'연결 복구 중 · 자동 새로고침'}</span></footer>
      </div>
      {count>0&&<div className="cart-dock"><button onClick={()=>{setCartOpen(true);setCheckoutError('')}}><span><ShoppingBag size={20}/><b className="cart-count">{count}</b> 장바구니 보기</span><strong>{money(total)} <ArrowRight size={19}/></strong></button></div>}
    </>}
    {notice&&<div className="toast" role="status"><Check size={18}/>{notice}</div>}
    {selected&&<Modal title="메뉴 선택" onClose={()=>setSelected(null)}><img className="menu-detail-image" src={selected.image_url} alt={selected.name}/><div className="modal-body"><span className="tiny-orange">MADE TO ORDER</span><h2>{selected.name}</h2><p className="muted">{selected.description}</p><strong className="detail-price">{money(selected.price)}</strong>{selected.options.length>0&&<fieldset className="option-list"><legend>더 맛있게 즐기기 <small>선택 사항 · 복수 선택 가능</small></legend>{selected.options.map(o=><label key={o.id}><input type="checkbox" checked={options.includes(o.id)} onChange={e=>setOptions(old=>e.target.checked?[...old,o.id]:old.filter(id=>id!==o.id))}/><span>{o.name}</span><b>+{money(o.price)}</b></label>)}</fieldset>}<div className="quantity-line"><strong>수량</strong><div className="stepper"><button aria-label="수량 줄이기" disabled={quantity<=1} onClick={()=>setQuantity(q=>q-1)}><Minus size={16}/></button><span>{quantity}</span><button aria-label="수량 늘리기" disabled={quantity>=20} onClick={()=>setQuantity(q=>q+1)}><Plus size={16}/></button></div></div><button className="primary full" onClick={addToCart}><ShoppingBag size={18}/>{money((selected.price+selected.options.filter(o=>options.includes(o.id)).reduce((s,o)=>s+o.price,0))*quantity)} 담기</button></div></Modal>}
    {cartOpen&&<Modal title="내 장바구니" onClose={()=>{if(!busy)setCartOpen(false)}}><div className="modal-body"><p className="muted">테이블 {number} · 맛있는 메뉴를 준비할게요.</p>{cart.map(item=><div className="cart-item" key={item.key}><img src={item.menu.image_url} alt=""/><div><strong>{item.menu.name}</strong><p>{item.menu.options.filter(o=>item.optionIds.includes(o.id)).map(o=>o.name).join(', ')||'기본 구성'}</p><b>{money(unitPrice(item)*item.quantity)}</b><div className="stepper"><button aria-label={`${item.menu.name} 수량 줄이기`} disabled={busy||item.quantity<=1} onClick={()=>setCart(old=>old.map(x=>x.key===item.key?{...x,quantity:x.quantity-1}:x))}><Minus size={14}/></button><span>{item.quantity}</span><button aria-label={`${item.menu.name} 수량 늘리기`} disabled={busy||item.quantity>=20} onClick={()=>setCart(old=>old.map(x=>x.key===item.key?{...x,quantity:x.quantity+1}:x))}><Plus size={14}/></button></div></div><button className="icon-button" aria-label={`${item.menu.name} 삭제`} disabled={busy} onClick={()=>setCart(old=>old.filter(x=>x.key!==item.key))}><Trash2 size={17}/></button></div>)}{!cart.length&&<Empty>아직 담은 메뉴가 없어요.</Empty>}<label className="form-field">매장에 전할 요청<textarea maxLength={300} placeholder="예: 양파는 빼 주세요 (선택 사항)" value={note} onChange={e=>setNote(e.target.value)} disabled={busy}/></label><div className="total-row"><span>총 주문 금액</span><strong>{money(total)}</strong></div><div className="demo-note">데모 결제 · 실제 결제나 청구는 발생하지 않습니다.<br/>주문 시 최신 메뉴 가격으로 금액이 확정됩니다.</div>{checkoutError&&<ErrorBox message={checkoutError}/>}<button className="primary full" disabled={busy||!cart.length} onClick={checkout}>{busy?'주문을 보내고 있어요…':`${money(total)} 주문하기`}<ArrowRight size={18}/></button></div></Modal>}
    {success&&<Modal title="주문이 완료되었어요" onClose={()=>setSuccess(null)}><div className="success-body"><span className="success-icon"><Check size={35}/></span><span className="tiny-orange">THANK YOU FOR YOUR ORDER</span><h2>맛있게 준비할게요!</h2><p>테이블 {success.table_number} · {success.number}</p><Badge status={success.status}/><div className="order-progress">{(['pending','cooking','completed'] as const).map((s,i)=><div key={s} className={i<=(['pending','cooking','completed'].indexOf(success.status))?'done':''}><span>{s==='completed'?<Check size={18}/>:s==='cooking'?<ChefHat size={18}/>:<ReceiptText size={18}/>}</span><small>{statusLabel[s]}</small></div>)}</div><p className="muted">주문 상태는 실시간으로 업데이트됩니다.</p><div className="receipt-summary">{success.items.map(i=><div key={i.id}><span>{i.name} × {i.quantity}</span><b>{money(i.subtotal)}</b></div>)}<div><strong>결제 금액 (데모)</strong><strong>{money(success.total)}</strong></div></div><button className="primary full" onClick={()=>{setSuccess(null);setHistoryOpen(true)}}>주문 내역 확인<ChevronRight size={17}/></button><button className="text-button" onClick={()=>setSuccess(null)}><ArrowLeft size={15}/> 메뉴 더 둘러보기</button></div></Modal>}
    {historyOpen&&<Modal title="내 주문 내역" onClose={()=>setHistoryOpen(false)}><div className="modal-body"><p className="muted">이 브라우저에서 주문한 내역을 확인할 수 있어요.</p>{orders.length===0?<Empty>아직 주문 내역이 없어요.</Empty>:orders.map(o=><article className="history-card" key={o.id}><div className="flex-between"><strong>{o.number}</strong><Badge status={o.status}/></div><small>{dateTime(o.created_at)}</small>{o.items.map(i=><p key={i.id}>{i.name} <b>× {i.quantity}</b></p>)}<div className="flex-between"><strong>{money(o.total)}</strong><button className="text-button" onClick={()=>{setHistoryOpen(false);setSuccess(o)}}>주문 상세 <ChevronRight size={15}/></button></div></article>)}<div className="demo-note"><Sparkles size={15}/> SmartOrder와 함께하는 편리한 주문</div></div></Modal>}
  </div>
}
