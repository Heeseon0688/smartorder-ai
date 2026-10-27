from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select, func, case
from .models import Order, OrderItem, Menu

KST = ZoneInfo('Asia/Seoul')

def day_bounds(day):
    start = datetime.combine(day, datetime.min.time(), KST).astimezone(timezone.utc).replace(tzinfo=None)
    return start, start + timedelta(days=1)

def aggregate(db, store_id, days=7):
    today = datetime.now(KST).date()
    first = today-timedelta(days=days-1)
    start, _ = day_bounds(first)
    _, end = day_bounds(today)
    filters = [Order.store_id == store_id, Order.created_at >= start, Order.created_at < end, Order.payment_status == 'demo_paid']
    def totals(extra=()):
        revenue, count = db.execute(select(func.coalesce(func.sum(Order.total),0),func.count(Order.id)).where(*filters,*extra)).one()
        return {'revenue':int(revenue), 'orders':count, 'average':round(revenue/count) if count else 0}
    series = []
    for i in range(days):
        date = first+timedelta(days=i); a,b = day_bounds(date)
        series.append({'date':date.isoformat(), 'label':date.strftime('%m.%d'), **totals([Order.created_at>=a,Order.created_at<b])})
    # SQL conditional sums preserve portability between SQLite and PostgreSQL.
    hour_expr = func.extract('hour', Order.created_at + timedelta(hours=9)) if db.bind.dialect.name == 'postgresql' else func.strftime('%H', Order.created_at, '+9 hours')
    hourly_rows = db.execute(select(hour_expr,func.count(Order.id)).where(*filters).group_by(hour_expr)).all()
    counts = {int(h):n for h,n in hourly_rows}
    hourly = [{'hour':h,'orders':counts.get(h,0)} for h in range(24)]
    sold = select(OrderItem.menu_id.label('menu_id'),func.sum(OrderItem.quantity).label('quantity'),func.sum(OrderItem.subtotal).label('revenue')).join(Order,Order.id==OrderItem.order_id).where(*filters).group_by(OrderItem.menu_id).subquery()
    ranking = [{'id':m.id,'name':m.name,'image_url':m.image_url,'quantity':int(q or 0),'revenue':int(r or 0)} for m,q,r in db.execute(select(Menu,sold.c.quantity,sold.c.revenue).outerjoin(sold,Menu.id==sold.c.menu_id).where(Menu.store_id==store_id).order_by(func.coalesce(sold.c.quantity,0).desc(),Menu.id)).all()]
    status_counts = dict(db.execute(select(Order.status,func.count(Order.id)).where(*filters).group_by(Order.status)).all())
    a,b = day_bounds(today-timedelta(days=1))
    previous = db.execute(select(func.coalesce(func.sum(Order.total),0),func.count(Order.id)).where(Order.store_id==store_id, Order.created_at>=a, Order.created_at<b, Order.payment_status=='demo_paid')).one()
    return {'period':{'start':first.isoformat(),'end':today.isoformat(),'timezone':'Asia/Seoul'}, **totals(), 'today':series[-1], 'yesterday':{'revenue':int(previous[0]),'orders':previous[1]},'daily':series,'hourly':hourly,'ranking':ranking,'statuses':status_counts,'basis':'데모 결제 완료 주문 · 주문 생성일 기준 · KST'}
