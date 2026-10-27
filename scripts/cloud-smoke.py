#!/usr/bin/env python3
"""Post-approval integration check. Writes one demo-paid order when explicitly enabled."""
import argparse
import asyncio
import getpass
import json
import secrets
from urllib.parse import urlparse, parse_qs
import httpx
from websockets.asyncio.client import connect

async def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frontend',required=True)
    parser.add_argument('--backend',required=True)
    parser.add_argument('--allow-demo-order',action='store_true')
    args=parser.parse_args()
    frontend=args.frontend.rstrip('/');backend=args.backend.rstrip('/')
    if not frontend.startswith('https://') or not backend.startswith('https://'):
        raise SystemExit('Public smoke checks require HTTPS origins.')
    if not args.allow_demo_order:
        raise SystemExit('This check creates a simulated order. Run with --allow-demo-order only after deployment/test approval.')
    email=input('Admin email: ').strip();password=getpass.getpass('Admin password: ')
    origin={'Origin':frontend}
    async with httpx.AsyncClient(base_url=frontend,headers=origin,timeout=60) as admin, httpx.AsyncClient(base_url=frontend,headers=origin,timeout=60) as customer:
        async def request(client,method,path,**kwargs):
            result=await client.request(method,path,**kwargs)
            if result.status_code>=400: raise RuntimeError(f'{method} {path.split("?")[0]} returned {result.status_code}')
            return result
        await request(admin,'GET','/api/ready')
        await request(admin,'POST','/api/auth/login',json={'email':email,'password':password})
        password=''
        try:
            tables=(await request(admin,'GET','/api/admin/tables')).json()
            table=tables[0];url=urlparse(table['url'])
            if url.scheme+'://'+url.netloc!=frontend: raise RuntimeError('QR FRONTEND_URL does not match the public frontend')
            _,_,slug,number=url.path.split('/')
            scope=f'/api/stores/{slug}/tables/{number}'
            headers={'X-Table-Token':parse_qs(url.query)['token'][0],'X-Customer-Token':secrets.token_hex(24),'Idempotency-Key':secrets.token_hex(20)}
            catalog=(await request(customer,'GET',scope+'/menu',headers=headers)).json()
            menu=next((m for m in catalog['menus'] if not m['sold_out']),None)
            if not menu: raise RuntimeError('Add an available menu in the administrator UI before running this test.')
            ticket=(await request(admin,'POST','/api/auth/ws-ticket')).json()['ticket']
            async with connect(backend.replace('https://','wss://',1)+'/ws',origin=frontend,open_timeout=60) as ws:
                await ws.send(json.dumps({'role':'admin','ticket':ticket}))
                if json.loads(await asyncio.wait_for(ws.recv(),10))['type']!='connected': raise RuntimeError('WebSocket authentication failed')
                order=(await request(customer,'POST',scope+'/orders',headers=headers,json={'items':[{'menu_id':menu['id'],'quantity':1,'option_ids':[]}],'note':'배포 검증용 데모 주문'})).json()
                event=json.loads(await asyncio.wait_for(ws.recv(),10))
                if event['type']!='order.created': raise RuntimeError('New order event missing')
                for status in ('cooking','completed'):
                    await request(admin,'PATCH',f"/api/admin/orders/{order['id']}/status",json={'status':status})
                    if json.loads(await asyncio.wait_for(ws.recv(),10))['type']!='orders.changed': raise RuntimeError('Status event missing')
                history=(await request(customer,'GET',scope+'/orders',headers=headers)).json()
                if not any(x['id']==order['id'] and x['status']=='completed' for x in history): raise RuntimeError('Customer order state did not update')
                print(f"PASS: HTTPS proxy login, QR URL, REST order {order['number']}, WSS ticket/events, completed customer state.")
        finally:
            await admin.post('/api/auth/logout')

if __name__=='__main__': asyncio.run(main())
