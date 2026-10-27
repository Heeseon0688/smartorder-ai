import random
import secrets
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select
from .models import Store, Table, MenuCategory, Menu, MenuOption, Order, OrderItem, OrderStatusHistory, AdminUser
from .security import password_hasher, digest
from .config import settings

CATALOG = [
    ('시그니처 버거', '스마트 클래식 버거', 8900, '육즙 가득한 비프 패티와 신선한 채소, 시그니처 소스의 완벽한 밸런스.', 'burger', 'BEST'),
    ('시그니처 버거', '더블 치즈 버거', 11900, '두 장의 비프 패티에 체더 치즈를 듬뿍. 진한 풍미의 더블 플레이.', 'double', 'POPULAR'),
    ('시그니처 버거', '스모키 베이컨 버거', 10900, '바삭한 베이컨과 스모키 바비큐 소스, 직화 패티의 조화.', 'bacon', ''),
    ('시그니처 버거', '크리스피 치킨 버거', 8500, '겉은 바삭, 속은 촉촉한 치킨과 산뜻한 코울슬로.', 'chicken', ''),
    ('시그니처 버거', '트러플 머쉬룸 버거', 12900, '구운 버섯과 은은한 트러플 향을 담은 프리미엄 버거.', 'burger', 'CHEF’S PICK'),
    ('시그니처 버거', '그린 베지 버거', 9900, '고소한 식물성 패티와 아보카도, 신선함을 가득 담았어요.', 'double', 'NEW'),
    ('사이드', '골든 프렌치 프라이', 3900, '주문과 동시에 튀겨 더욱 바삭한 감자튀김.', 'fries', 'BEST'),
    ('사이드', '트러플 파르메산 프라이', 5900, '향긋한 트러플 오일과 파르메산 치즈 토핑.', 'fries', ''),
    ('사이드', '크리스피 어니언 링', 4500, '달콤한 양파를 바삭하게 튀긴 인기 사이드.', 'rings', ''),
    ('사이드', '치킨 텐더', 6500, '부드러운 치킨 안심과 허니 머스터드 소스.', 'chicken', ''),
    ('사이드', '프레시 코울슬로', 3000, '아삭한 양배추와 부드러운 홈메이드 드레싱.', 'salad', ''),
    ('음료', '코카콜라', 2500, '버거와 가장 잘 어울리는 시원한 클래식.', 'cola', ''),
    ('음료', '제로 콜라', 2500, '가볍게 즐기는 시원하고 짜릿한 탄산.', 'cola', ''),
    ('음료', '홈메이드 레모네이드', 4500, '상큼한 레몬으로 매일 직접 만드는 레모네이드.', 'lemonade', 'NEW'),
    ('음료', '아이스 아메리카노', 3500, '깊고 깔끔한 풍미의 스페셜티 커피.', 'coffee', ''),
    ('디저트', '클래식 바닐라 쉐이크', 5900, '진한 바닐라 아이스크림으로 만든 부드러운 쉐이크.', 'shake', ''),
]

STORE_DESCRIPTION = '좋은 재료, 정직한 맛. 매일 새롭게 만드는 수제 버거.'

def create_catalog(db, store):
    """Smart Burger categories and menus only: no orders, no accounts."""
    categories = {}
    for i, name in enumerate(dict.fromkeys(row[0] for row in CATALOG)):
        cat = MenuCategory(store_id=store.id, name=name, position=i)
        db.add(cat); db.flush(); categories[name] = cat.id
    menus = []
    for category, name, price, description, image, badge in CATALOG:
        menu = Menu(store_id=store.id, category_id=categories[category], name=name, price=price, description=description, image_url=f'/images/{image}.jpg', badge=badge)
        if category == '시그니처 버거':
            menu.options = [MenuOption(name='체더 치즈 추가', price=1000), MenuOption(name='비프 패티 추가', price=3000), MenuOption(name='베이컨 추가', price=1500)]
        db.add(menu); menus.append(menu)
    return menus

def seed(db):
    if db.scalar(select(Store).limit(1)):
        return
    rng = random.Random(42)
    store = Store(slug='smart-burger', name='Smart Burger', description=STORE_DESCRIPTION)
    db.add(store); db.flush()
    admin = AdminUser(store_id=store.id, email=settings.demo_admin_email, name='김스마트', password_hash=password_hasher.hash(settings.demo_admin_password))
    db.add(admin)
    tables = [Table(store_id=store.id, number=i, token=secrets.token_urlsafe(32)) for i in range(1,11)]
    db.add_all(tables)
    menus = create_catalog(db, store)
    db.flush()
    now = datetime.now(ZoneInfo('Asia/Seoul'))
    for day in range(7):
        for j in range(12 + (6-day)*2):
            hour = rng.choice([11,12,12,13,14,17,18,18,19,20])
            local = (now-timedelta(days=day)).replace(hour=hour, minute=rng.randrange(60), second=0, microsecond=0)
            if local > now:
                local = now-timedelta(minutes=5+j*7)
            created = local.astimezone(timezone.utc).replace(tzinfo=None)
            status = ('pending' if j < 2 else 'cooking') if day == 0 and j < 4 else 'completed'
            order = Order(store_id=store.id, table_id=rng.choice(tables).id, customer_hash=digest('seed'), idempotency_key=f'seed-{day}-{j}', request_hash='seed', total=0, status=status, created_at=created)
            selected = [rng.choices(menus[:6], weights=[7,5,4,3,2,1])[0], rng.choice(menus[6:11]), rng.choice(menus[11:])]
            for m in selected:
                qty = rng.choice([1,1,1,2])
                order.items.append(OrderItem(menu_id=m.id, name=m.name, unit_price=m.price, quantity=qty, subtotal=m.price*qty, options=[]))
            order.total = sum(i.subtotal for i in order.items)
            order.history.append(OrderStatusHistory(status='pending', changed_at=created))
            if status != 'pending':
                order.history.append(OrderStatusHistory(status='cooking', changed_at=created+timedelta(minutes=1), admin_id=admin.id))
            if status == 'completed':
                order.history.append(OrderStatusHistory(status='completed', changed_at=created+timedelta(minutes=4), admin_id=admin.id))
            db.add(order)
    db.commit()
