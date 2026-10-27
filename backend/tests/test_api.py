import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from types import SimpleNamespace
import pytest
from sqlalchemy import select, func
from starlette.websockets import WebSocketDisconnect
from app.db import SessionLocal
from app.models import Store, Table, MenuCategory, Menu, Order, AdminUser, AdminSession, utcnow
from app.security import password_hasher


def payload(menu_id=1, quantity=2, options=None):
    return {'items':[{'menu_id':menu_id,'quantity':quantity,'option_ids':options or []}], 'note':'양파 빼 주세요'}

def create(client, customer, body=None):
    base,headers=customer
    return client.post(base+'/orders',headers=headers,json=body or payload())

def test_seed_and_catalog(client,customer):
    base,headers=customer
    assert client.get('/api/health').json()=={'status':'ok'}
    catalog=client.get(base+'/menu',headers=headers).json()
    assert catalog['store']['name']=='Smart Burger'
    assert len(catalog['menus'])>=15
    with SessionLocal() as db:
        assert db.scalar(select(func.count(Order.id)))>=50
        assert db.scalar(select(func.count(Table.id)))==10
        user=db.scalar(select(AdminUser))
        assert user.password_hash!='SmartBurger!2026'
        assert password_hasher.verify('SmartBurger!2026',user.password_hash)

def test_auth_and_logout(client):
    assert client.get('/api/admin/orders').status_code==401
    assert client.post('/api/auth/login',json={'email':'bad','password':'bad'}).status_code==401
    response=client.post('/api/auth/login',json={'email':'admin@smartburger.demo','password':'SmartBurger!2026'})
    assert 'HttpOnly' in response.headers['set-cookie']
    assert 'SameSite=lax' in response.headers['set-cookie']
    cookie=client.cookies.get('smartorder_session')
    assert client.get('/api/auth/me').status_code==200
    client.post('/api/auth/logout')
    assert client.get('/api/admin/orders',headers={'Cookie':f'smartorder_session={cookie}'}).status_code==401

def test_login_limit_survives_spoofed_forwarded_ip(client):
    # Rotating X-Forwarded-For (trusted on Render) must not bypass the per-account cap.
    from app.security import limiter
    for n in range(20):
        limiter.buckets.pop('login:testclient',None)
        assert client.post('/api/auth/login',headers={'X-Forwarded-For':f'10.0.0.{n}'},json={'email':'admin@smartburger.demo','password':'wrong-password'}).status_code==401
    assert client.post('/api/auth/login',json={'email':'admin@smartburger.demo','password':'SmartBurger!2026'}).status_code==429

def test_origin_and_invalid_qr(client,customer):
    base,headers=customer
    assert client.get(base+'/menu').status_code==403
    assert client.post('/api/auth/login',headers={'Origin':'https://evil.example'},json={'email':'a','password':'b'}).status_code==403
    assert client.get(base+'/menu',headers={**headers,'X-Table-Token':'wrong'}).status_code==403
    assert client.get(base.replace('/1','/2')+'/menu',headers=headers).status_code==403

def test_server_prices_options_snapshot(admin,customer):
    base,headers=customer
    menu=admin.get(base+'/menu',headers=headers).json()['menus'][0]
    body=payload(options=[menu['options'][0]['id']])
    response=create(admin,customer,body)
    assert response.status_code==201
    order=response.json()
    assert order['total']==(menu['price']+menu['options'][0]['price'])*2
    assert order['items'][0]['unit_price']==9900
    with SessionLocal() as db:
        m=db.get(Menu,menu['id']);m.price=10;db.commit()
    stored=admin.get(base+'/orders',headers=headers).json()[0]
    assert stored['total']==19800 and stored['items'][0]['unit_price']==9900
    assert stored['payment_status']=='demo_paid'

def test_idempotency_and_conflict(client,customer):
    first=create(client,customer)
    replay=create(client,customer)
    assert first.status_code==201 and replay.status_code==200
    assert first.json()['id']==replay.json()['id']
    assert create(client,customer,payload(quantity=3)).status_code==409

def test_concurrent_idempotency(client,customer):
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses=list(pool.map(lambda _:create(client,customer), range(4)))
    assert sorted(r.status_code for r in responses)==[200,200,200,201]
    assert len({r.json()['id'] for r in responses})==1

@pytest.mark.parametrize('body',[
    {'items':[]},payload(quantity=0),payload(quantity=21),
    {'items':[{'menu_id':1,'quantity':1,'unit_price':1}]},
    payload(options=[1,1]),{'items':payload()['items'],'total':1},
])
def test_payload_validation(client,customer,body):
    assert create(client,customer,body).status_code==422

def test_foreign_options_and_sold_out(admin,customer):
    assert create(admin,customer,payload(options=[9999])).status_code==400
    assert create(admin,customer,payload(options=[4])).status_code==400
    assert admin.patch('/api/admin/menus/1/availability',json={'sold_out':True}).status_code==200
    assert create(admin,customer).status_code==409

def test_customer_isolation(client,customer):
    assert create(client,customer).status_code==201
    base,headers=customer
    assert len(client.get(base+'/orders',headers=headers).json())==1
    assert client.get(base+'/orders',headers={**headers,'X-Customer-Token':uuid.uuid4().hex}).json()==[]
    assert client.get(base+'/orders',headers={**headers,'X-Customer-Token':''}).status_code==400

def test_status_machine_history_and_duplicate(admin,customer):
    order=create(admin,customer).json();path=f"/api/admin/orders/{order['id']}/status"
    assert admin.patch(path,json={'status':'completed'}).status_code==409
    assert admin.patch(path,json={'status':'pending'}).status_code==422
    assert admin.patch(path,json={'status':'cooking'}).status_code==200
    assert admin.patch(path,json={'status':'cooking'}).status_code==409
    completed=admin.patch(path,json={'status':'completed'})
    assert completed.status_code==200
    assert [h['status'] for h in completed.json()['history']]==['pending','cooking','completed']
    assert admin.patch(path,json={'status':'cooking'}).status_code==409

def test_menu_crud_preserves_orders(admin,customer):
    data={'category_id':1,'name':'테스트 메뉴','description':'신메뉴','price':7000,'image_url':'/images/burger.jpg','options':[{'name':'치즈','price':1000}]}
    menu=admin.post('/api/admin/menus',json=data).json()
    result=create(admin,customer,payload(menu_id=menu['id'],options=[menu['options'][0]['id']]))
    assert result.status_code==201
    assert admin.put(f"/api/admin/menus/{menu['id']}",json={**data,'price':8000}).status_code==200
    assert admin.delete(f"/api/admin/menus/{menu['id']}").status_code==200
    assert menu['id'] not in [m['id'] for m in admin.get('/api/admin/menus').json()['menus']]
    base,headers=customer
    assert admin.get(base+'/orders',headers=headers).json()[0]['total']==16000
    assert admin.post('/api/admin/menus',json={**data,'image_url':'javascript:alert(1)'}).status_code==422

def test_store_isolation(admin):
    with SessionLocal() as db:
        s=Store(slug='other',name='Other');db.add(s);db.flush()
        c=MenuCategory(store_id=s.id,name='Other');db.add(c);db.flush()
        m=Menu(store_id=s.id,category_id=c.id,name='Private',price=1);db.add(m)
        t=Table(store_id=s.id,number=1,token='other-secret');db.add(t);db.flush()
        o=Order(store_id=s.id,table_id=t.id,customer_hash='other',idempotency_key='other',request_hash='other',total=1);db.add(o);db.commit()
        mid,oid,tid,cid=m.id,o.id,t.id,c.id
    assert admin.delete(f'/api/admin/menus/{mid}').status_code==404
    assert admin.patch(f'/api/admin/orders/{oid}/status',json={'status':'cooking'}).status_code==404
    assert admin.get(f'/api/admin/tables/{tid}/qr').status_code==404
    assert admin.post('/api/admin/menus',json={'name':'Bad','price':1,'category_id':cid}).status_code==400

def test_stats_equal_sql_and_qr(admin,customer):
    create(admin,customer)
    stats=admin.get('/api/admin/stats').json()
    assert len(stats['daily'])==7
    assert len(stats['hourly'])==24
    assert sum(d['orders'] for d in stats['daily'])==stats['orders']
    assert sum(d['revenue'] for d in stats['daily'])==stats['revenue']
    assert sum(h['orders'] for h in stats['hourly'])==stats['orders']
    assert sum(m['revenue'] for m in stats['ranking'])==stats['revenue']
    with SessionLocal() as db:
        assert stats['revenue']==db.scalar(select(func.sum(Order.total)))
    tables=admin.get('/api/admin/tables').json()
    assert len(tables)==10
    qr=admin.get('/api/admin/tables/1/qr')
    assert qr.status_code==200 and qr.content.startswith(b'\x89PNG')
    assert '?token=' in tables[0]['url']

def test_ai_fallback_and_empty(admin):
    stats=admin.get('/api/admin/stats?days=1').json()
    answer=admin.post('/api/admin/analysis',json={'question':'오늘 매출은 얼마야?','days':1}).json()
    assert answer['source']=='statistics'
    assert answer['metrics']['revenue']==stats['revenue']
    assert f"{stats['revenue']:,}원" in answer['answer']
    from app.ai import analyze
    empty={**stats,'revenue':0,'orders':0,'average':0,'ranking':[],'hourly':[{'hour':h,'orders':0} for h in range(24)]}
    result=asyncio.run(analyze('오늘 가장 많이 팔린 메뉴는?',empty))
    assert '없습니다' in result['answer']

def test_ai_openai_plan_and_failure(admin,monkeypatch):
    import app.ai as ai
    monkeypatch.setattr(ai.settings,'openai_api_key','test-not-real')
    class Client:
        def __init__(self,**kwargs): self.responses=self
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def parse(self,**kwargs):
            assert kwargs['store'] is False
            return SimpleNamespace(output_parsed=ai.AnalysisPlan(focus=['top_menu','revenue'],suggestions=['bundle']))
    monkeypatch.setattr(ai,'AsyncOpenAI',Client)
    result=admin.post('/api/admin/analysis',json={'question':'분석해 줘'}).json()
    assert result['source']=='openai' and len(result['suggestions'])==1
    class FailedClient(Client):
        async def parse(self,**kwargs): raise TimeoutError()
    monkeypatch.setattr(ai,'AsyncOpenAI',FailedClient)
    result=admin.post('/api/admin/analysis',json={'question':'매출은?'}).json()
    assert result['source']=='statistics' and '연결' in result['notice']

def test_websocket_auth_realtime_and_logout(admin,customer):
    base,headers=customer
    origin={'Origin':'http://localhost:5173'}
    with admin.websocket_connect('/ws',headers=origin) as ws_admin:
        ws_admin.send_json({'role':'admin'})
        assert ws_admin.receive_json()['type']=='connected'
        with admin.websocket_connect('/ws',headers=origin) as ws_customer:
            ws_customer.send_json({'role':'customer','slug':'smart-burger','table':1,'token':headers['X-Table-Token']})
            assert ws_customer.receive_json()['type']=='connected'
            order=create(admin,customer).json()
            assert ws_admin.receive_json()['type']=='order.created'
            assert ws_customer.receive_json()['type']=='order.created'
            admin.patch(f"/api/admin/orders/{order['id']}/status",json={'status':'cooking'})
            assert ws_admin.receive_json()['type']=='orders.changed'
            assert ws_customer.receive_json()['type']=='orders.changed'
        admin.post('/api/auth/logout')
        ws_admin.send_text('ping')
        with pytest.raises(WebSocketDisconnect) as exc: ws_admin.receive_json()
        assert exc.value.code==4401

def test_websocket_rejects_invalid_auth(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect('/ws',headers={'Origin':'https://evil.example'}): pass
    with client.websocket_connect('/ws',headers={'Origin':'http://localhost:5173'}) as ws:
        ws.send_json({'role':'admin'})
        with pytest.raises(WebSocketDisconnect) as exc: ws.receive_json()
        assert exc.value.code==4401

def test_expired_session(admin):
    with SessionLocal() as db:
        session=db.scalar(select(AdminSession));session.expires_at=utcnow()-timedelta(seconds=1);db.commit()
    assert admin.get('/api/admin/stats').status_code==401
