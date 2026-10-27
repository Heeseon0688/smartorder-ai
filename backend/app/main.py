import asyncio
import io
import json
import secrets
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Annotated
import qrcode
from alembic.script import ScriptDirectory
from fastapi import FastAPI, Depends, Header, HTTPException, Request, Response, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, update, delete, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from .config import settings
from .db import Base, engine, SessionLocal, get_db
from .models import Store, Table, MenuCategory, Menu, MenuOption, Order, OrderItem, OrderStatusHistory, AdminUser, AdminSession, WebSocketTicket, utcnow
from .schemas import Login, OrderInput, StatusInput, MenuInput, AvailabilityInput, AnalysisInput
from .security import admin_user, resolve_admin, password_hasher, DUMMY_HASH, digest, limiter
from .analytics import aggregate
from .ai import analyze
from .manage import alembic_config

DB = Annotated[Session, Depends(get_db)]
MIGRATION_HEAD = ScriptDirectory.from_config(alembic_config()).get_current_head()
Admin = Annotated[AdminUser, Depends(admin_user)]

class Hub:
    def __init__(self): self.connections: dict[WebSocket,tuple[int,int|None]] = {}
    async def broadcast(self, store_id, table_id=None, event='orders.changed'):
        async def send(ws):
            try: await asyncio.wait_for(ws.send_json({'type':event}), timeout=3)
            except Exception: self.connections.pop(ws, None)
        await asyncio.gather(*(send(ws) for ws,(s,t) in list(self.connections.items()) if s==store_id and (t is None or table_id is None or t==table_id)))
hub = Hub()

@asynccontextmanager
async def lifespan(app):
    # Schema changes and demo data are explicit CLI operations.
    yield
    for ws in list(hub.connections):
        await ws.close(code=1001)
    hub.connections.clear()

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s %(message)s')

app = FastAPI(title='SmartOrder AI', version='1.0.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_credentials=True, allow_methods=['GET','POST','PUT','PATCH','DELETE'], allow_headers=['Content-Type','Idempotency-Key','X-Table-Token','X-Customer-Token'])

@app.middleware('http')
async def browser_security(request, call_next):
    started = time.monotonic()
    request_id = uuid.uuid4().hex
    origin = request.headers.get('origin')
    if request.method not in ('GET','HEAD','OPTIONS') and origin and origin not in settings.allowed_origins:
        return JSONResponse(status_code=403, content={'detail':'허용되지 않은 요청 출처입니다.'})
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Request-ID'] = request_id
    route = getattr(request.scope.get('route'), 'path', '<unmatched>')
    logging.getLogger('smartorder.requests').info(json.dumps({'request_id':request_id, 'method':request.method, 'route':route, 'status':response.status_code, 'duration_ms':round((time.monotonic()-started)*1000)}))
    return response

@app.exception_handler(Exception)
async def unexpected_error(request, exc):
    import logging
    logging.getLogger(__name__).error('Unhandled API error: %s', type(exc).__name__)
    return JSONResponse(status_code=500, content={'detail':'서버 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.'})

def table_access(db, slug, number, token):
    store = db.scalar(select(Store).where(Store.slug==slug))
    table = db.scalar(select(Table).where(Table.store_id==store.id, Table.number==number)) if store else None
    if not table or not secrets.compare_digest(table.token, token or ''):
        raise HTTPException(403,'유효한 테이블 QR코드로 접속해 주세요.')
    return store, table

def customer_hash(token):
    if not token or not 32 <= len(token) <= 128:
        raise HTTPException(400,'고객 세션이 올바르지 않습니다.')
    return digest(token)

def menu_json(m):
    return {k:getattr(m,k) for k in ['id','category_id','name','description','price','image_url','sold_out','badge']} | {'options':[{'id':o.id,'name':o.name,'price':o.price} for o in m.options if o.active]}

def order_json(o):
    return {'id':o.id,'number':f'SB-{o.id:04d}','table_number':o.table.number,'status':o.status,'total':o.total,'payment_status':o.payment_status,'note':o.note,'created_at':o.created_at.isoformat()+'Z', 'items':[{'id':i.id,'menu_id':i.menu_id,'name':i.name,'unit_price':i.unit_price,'quantity':i.quantity,'subtotal':i.subtotal,'options':i.options} for i in o.items], 'history':[{'status':h.status,'changed_at':h.changed_at.isoformat()+'Z'} for h in o.history]}

def table_url(store, table):
    return f'{settings.frontend_url.rstrip("/")}/order/{store.slug}/{table.number}?token={table.token}'

@app.get('/api/health')
def health(): return {'status':'ok'}

@app.get('/api/ready')
def ready(db: DB):
    try:
        db.execute(text('SELECT 1'))
        revision = db.execute(text('SELECT version_num FROM alembic_version')).scalar()
        if revision != MIGRATION_HEAD:
            raise HTTPException(503, 'DB migration is required.')
    except SQLAlchemyError:
        raise HTTPException(503, 'Database is temporarily unavailable.')
    return {'status':'ready','database':'ok','schema':revision}


@app.get('/api/demo')
def demo(db: DB):
    if not (settings.enable_demo_link or settings.seed_demo): raise HTTPException(404,'데모 모드가 비활성화되었습니다.')
    store = db.scalar(select(Store).where(Store.slug=='smart-burger'))
    if not store: raise HTTPException(404,'데모 데이터가 없습니다. 관리자가 seed-demo 명령을 실행해야 합니다.')
    table = db.scalar(select(Table).where(Table.store_id==store.id,Table.number==1))
    return {'order_url':table_url(store,table), 'store_name':store.name}

@app.get('/api/stores/{slug}/tables/{number}/menu')
def public_menu(slug: str, number: int, db: DB, x_table_token: str = Header(default='')):
    store,table = table_access(db,slug,number,x_table_token)
    categories = db.scalars(select(MenuCategory).where(MenuCategory.store_id==store.id).order_by(MenuCategory.position)).all()
    menus = db.scalars(select(Menu).where(Menu.store_id==store.id,Menu.active==True).order_by(Menu.id)).all()
    return {'store':{'name':store.name,'slug':store.slug,'description':store.description},'table_number':table.number,'categories':[{'id':c.id,'name':c.name} for c in categories],'menus':[menu_json(m) for m in menus]}

@app.post('/api/stores/{slug}/tables/{number}/orders')
async def create_order(slug: str, number: int, data: OrderInput, db: DB, response: Response, idempotency_key: str = Header(min_length=16,max_length=80), x_table_token: str = Header(default=''), x_customer_token: str = Header(default='')):
    store,table = table_access(db,slug,number,x_table_token)
    owner = customer_hash(x_customer_token)
    fingerprint = digest(json.dumps({'table':table.id,'customer':owner,**data.model_dump()},sort_keys=True))
    def replay(existing):
        if existing.request_hash != fingerprint: raise HTTPException(409,'같은 주문 키로 다른 주문을 보낼 수 없습니다.')
        response.status_code=200
        return order_json(existing)
    existing = db.scalar(select(Order).where(Order.store_id==store.id,Order.idempotency_key==idempotency_key))
    if existing: return replay(existing)
    limiter.check(f'order:{owner}',30)
    order = Order(store_id=store.id,table_id=table.id,customer_hash=owner,idempotency_key=idempotency_key,request_hash=fingerprint,total=0,note=data.note)
    for item in data.items:
        menu = db.get(Menu,item.menu_id)
        if not menu or menu.store_id!=store.id or not menu.active: raise HTTPException(400,'판매하지 않는 메뉴입니다.')
        if menu.sold_out: raise HTTPException(409,f'{menu.name} 메뉴가 품절되었습니다.')
        options = [o for o in menu.options if o.active and o.id in item.option_ids]
        if len(options)!=len(item.option_ids): raise HTTPException(400,'해당 메뉴의 유효한 옵션을 선택해 주세요.')
        price = menu.price+sum(o.price for o in options)
        order.items.append(OrderItem(menu_id=menu.id,name=menu.name,unit_price=price,quantity=item.quantity,subtotal=price*item.quantity,options=[{'name':o.name,'price':o.price} for o in options]))
    order.total = sum(i.subtotal for i in order.items)
    order.history.append(OrderStatusHistory(status='pending'))
    db.add(order)
    try: db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Order).where(Order.store_id==store.id,Order.idempotency_key==idempotency_key))
        if existing: return replay(existing)
        raise
    response.status_code=201
    await hub.broadcast(store.id,table.id,'order.created')
    return order_json(order)

@app.get('/api/stores/{slug}/tables/{number}/orders')
def my_orders(slug:str, number:int, db: DB, x_table_token:str=Header(default=''), x_customer_token:str=Header(default='')):
    store,table = table_access(db,slug,number,x_table_token)
    owner = customer_hash(x_customer_token)
    orders=db.scalars(select(Order).where(Order.store_id==store.id,Order.table_id==table.id,Order.customer_hash==owner).order_by(Order.created_at.desc()).limit(100)).all()
    return [order_json(o) for o in orders]

@app.post('/api/auth/login')
def login(data:Login, request:Request, response:Response, db:DB):
    email=data.email.strip().lower()
    limiter.check(f'login:{request.client.host if request.client else "unknown"}',10,300)
    # Per-account cap still applies if a spoofed X-Forwarded-For bypasses the IP bucket.
    limiter.check(f'login-email:{email}',20,300)
    admin=db.scalar(select(AdminUser).where(AdminUser.email==email))
    valid=password_hasher.verify(data.password,admin.password_hash if admin else DUMMY_HASH)
    if not admin or not valid: raise HTTPException(401,'이메일 또는 비밀번호를 확인해 주세요.')
    old=request.cookies.get('smartorder_session')
    if old: db.execute(delete(AdminSession).where(AdminSession.token_hash==digest(old)))
    db.execute(delete(AdminSession).where(AdminSession.expires_at<=utcnow()))
    token=secrets.token_urlsafe(48)
    db.add(AdminSession(token_hash=digest(token),admin_id=admin.id,expires_at=utcnow()+timedelta(hours=8))); db.commit()
    response.set_cookie('smartorder_session',token,httponly=True,secure=settings.cookie_secure,samesite='lax',max_age=28800,path='/')
    return {'name':admin.name,'email':admin.email}

@app.post('/api/auth/logout')
def logout(request:Request,response:Response,db:DB):
    db.execute(delete(WebSocketTicket).where(WebSocketTicket.session_hash==digest(request.cookies.get('smartorder_session',''))))
    db.execute(delete(AdminSession).where(AdminSession.token_hash==digest(request.cookies.get('smartorder_session',''))));db.commit()
    response.delete_cookie('smartorder_session',path='/')
    return {'ok':True}

@app.post('/api/auth/ws-ticket')
def ws_ticket(request:Request,admin:Admin,db:DB):
    limiter.check(f'ws-ticket:{admin.id}',60)
    db.execute(delete(WebSocketTicket).where(WebSocketTicket.expires_at<=utcnow()))
    ticket=secrets.token_urlsafe(32)
    db.add(WebSocketTicket(token_hash=digest(ticket),session_hash=digest(request.cookies.get('smartorder_session','')),expires_at=utcnow()+timedelta(seconds=30)))
    db.commit()
    return {'ticket':ticket,'expires_in':30}

@app.get('/api/auth/me')
def me(admin:Admin,db:DB):
    store=db.get(Store,admin.store_id)
    return {'name':admin.name,'email':admin.email,'store_name':store.name}

@app.get('/api/admin/orders')
def admin_orders(admin:Admin,db:DB,table_number:int|None=None,limit:int=Query(default=100,ge=1,le=200),offset:int=Query(default=0,ge=0)):
    query=select(Order).where(Order.store_id==admin.store_id)
    if table_number is not None: query=query.join(Table).where(Table.number==table_number)
    return [order_json(o) for o in db.scalars(query.order_by(Order.created_at.desc(),Order.id.desc()).offset(offset).limit(limit)).all()]

@app.patch('/api/admin/orders/{order_id}/status')
async def change_status(order_id:int,data:StatusInput,admin:Admin,db:DB):
    order=db.get(Order,order_id)
    if not order or order.store_id!=admin.store_id: raise HTTPException(404,'주문을 찾을 수 없습니다.')
    expected={'cooking':'pending','completed':'cooking'}[data.status]
    result=db.execute(update(Order).where(Order.id==order_id,Order.status==expected).values(status=data.status))
    if result.rowcount != 1:
        db.rollback(); raise HTTPException(409,'접수 대기 → 조리 중 → 완료 순서로 변경해 주세요. 다른 화면에서 이미 변경되었을 수 있습니다.')
    db.add(OrderStatusHistory(order_id=order_id,status=data.status,admin_id=admin.id));db.commit();db.refresh(order)
    await hub.broadcast(admin.store_id,order.table_id)
    return order_json(order)

@app.get('/api/admin/menus')
def admin_menus(admin:Admin,db:DB):
    cats=db.scalars(select(MenuCategory).where(MenuCategory.store_id==admin.store_id).order_by(MenuCategory.position)).all()
    menus=db.scalars(select(Menu).where(Menu.store_id==admin.store_id,Menu.active==True).order_by(Menu.id)).all()
    return {'categories':[{'id':c.id,'name':c.name} for c in cats],'menus':[menu_json(m) for m in menus]}

def owned_menu(db,admin,menu_id):
    m=db.get(Menu,menu_id)
    if not m or m.store_id!=admin.store_id or not m.active: raise HTTPException(404,'메뉴를 찾을 수 없습니다.')
    return m

def assign_menu(db,admin,m,data):
    c=db.get(MenuCategory,data.category_id)
    if not c or c.store_id!=admin.store_id: raise HTTPException(400,'유효한 카테고리를 선택해 주세요.')
    for key,value in data.model_dump(exclude={'options'}).items(): setattr(m,key,value)
    # Retire old option IDs; historical order snapshots stay immutable.
    for option in m.options: option.active=False
    m.options.extend(MenuOption(**o.model_dump()) for o in data.options)

@app.post('/api/admin/menus',status_code=201)
async def add_menu(data:MenuInput,admin:Admin,db:DB):
    m=Menu(store_id=admin.store_id);assign_menu(db,admin,m,data);db.add(m);db.commit()
    await hub.broadcast(admin.store_id,event='menu.changed');return menu_json(m)

@app.put('/api/admin/menus/{menu_id}')
async def edit_menu(menu_id:int,data:MenuInput,admin:Admin,db:DB):
    m=owned_menu(db,admin,menu_id);assign_menu(db,admin,m,data);db.commit()
    await hub.broadcast(admin.store_id,event='menu.changed');return menu_json(m)

@app.patch('/api/admin/menus/{menu_id}/availability')
async def availability(menu_id:int,data:AvailabilityInput,admin:Admin,db:DB):
    m=owned_menu(db,admin,menu_id);m.sold_out=data.sold_out;db.commit()
    await hub.broadcast(admin.store_id,event='menu.changed');return menu_json(m)

@app.delete('/api/admin/menus/{menu_id}')
async def remove_menu(menu_id:int,admin:Admin,db:DB):
    m=owned_menu(db,admin,menu_id);m.active=False;db.commit()
    await hub.broadcast(admin.store_id,event='menu.changed');return {'ok':True}

@app.get('/api/admin/stats')
def stats(admin:Admin,db:DB,days:int=Query(default=7,ge=1,le=31)):
    return aggregate(db,admin.store_id,days)

@app.post('/api/admin/analysis')
async def analysis(data:AnalysisInput,admin:Admin,db:DB):
    limiter.check(f'ai:{admin.id}',10)
    return await analyze(data.question,aggregate(db,admin.store_id,data.days))

@app.get('/api/admin/tables')
def tables(admin:Admin,db:DB):
    store=db.get(Store,admin.store_id)
    return [{'id':t.id,'number':t.number,'url':table_url(store,t)} for t in db.scalars(select(Table).where(Table.store_id==admin.store_id).order_by(Table.number))]

@app.get('/api/admin/tables/{table_id}/qr')
def qr(table_id:int,admin:Admin,db:DB):
    table=db.get(Table,table_id)
    if not table or table.store_id!=admin.store_id: raise HTTPException(404,'테이블을 찾을 수 없습니다.')
    output=io.BytesIO();qrcode.make(table_url(db.get(Store,admin.store_id),table)).save(output,format='PNG')
    return Response(output.getvalue(),media_type='image/png',headers={'Content-Disposition':f'inline; filename="smartburger-table-{table.number}.png"'})

@app.websocket('/ws')
async def websocket(ws:WebSocket):
    if ws.headers.get('origin') not in settings.allowed_origins:
        await ws.close(code=4403); return
    await ws.accept()
    try:
        payload=await asyncio.wait_for(ws.receive_json(),timeout=5)
        with SessionLocal() as db:
            if payload.get('role')=='admin':
                session_hash=digest(ws.cookies.get('smartorder_session',''))
                if payload.get('ticket'):
                    session_hash=db.execute(delete(WebSocketTicket).where(WebSocketTicket.token_hash==digest(str(payload['ticket'])),WebSocketTicket.expires_at>utcnow()).returning(WebSocketTicket.session_hash)).scalar_one_or_none()
                    db.commit()
                session=db.get(AdminSession,session_hash) if session_hash else None
                admin=db.get(AdminUser,session.admin_id) if session and session.expires_at>utcnow() else None
                if not admin: await ws.close(code=4401);return
                scope=(admin.store_id,None)
            else:
                store,table=table_access(db,str(payload.get('slug','')),int(payload.get('table',0)),str(payload.get('token','')))
                scope=(store.id,table.id)
        hub.connections[ws]=scope
        await ws.send_json({'type':'connected'})
        while True:
            try: await asyncio.wait_for(ws.receive_text(),timeout=25)
            except asyncio.TimeoutError: pass
            if scope[1] is None:
                with SessionLocal() as db:
                    session=db.get(AdminSession,session_hash)
                    if not session or session.expires_at<=utcnow():
                        await ws.close(code=4401);break
            await ws.send_json({'type':'heartbeat'})
    except (WebSocketDisconnect,RuntimeError): pass
    except (HTTPException,ValueError,TypeError,AttributeError,asyncio.TimeoutError):
        await ws.close(code=4403)
    finally: hub.connections.pop(ws,None)
