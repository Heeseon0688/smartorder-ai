from datetime import datetime, timezone
from sqlalchemy import String, Text, ForeignKey, UniqueConstraint, CheckConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class Store(Base):
    __tablename__ = 'stores'
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default='')

class Table(Base):
    __tablename__ = 'tables'
    __table_args__ = (UniqueConstraint('store_id', 'number'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey('stores.id'), index=True)
    number: Mapped[int]
    token: Mapped[str] = mapped_column(String(100), unique=True)

class MenuCategory(Base):
    __tablename__ = 'menu_categories'
    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey('stores.id'))
    name: Mapped[str] = mapped_column(String(50))
    position: Mapped[int] = mapped_column(default=0)

class Menu(Base):
    __tablename__ = 'menus'
    __table_args__ = (CheckConstraint('price >= 0'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey('stores.id'), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey('menu_categories.id'))
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default='')
    price: Mapped[int]
    image_url: Mapped[str] = mapped_column(Text, default='/images/burger.jpg')
    sold_out: Mapped[bool] = mapped_column(default=False)
    active: Mapped[bool] = mapped_column(default=True)
    badge: Mapped[str] = mapped_column(String(30), default='')
    options: Mapped[list['MenuOption']] = relationship(cascade='all, delete-orphan', lazy='selectin')

class MenuOption(Base):
    __tablename__ = 'menu_options'
    id: Mapped[int] = mapped_column(primary_key=True)
    menu_id: Mapped[int] = mapped_column(ForeignKey('menus.id'))
    name: Mapped[str] = mapped_column(String(60))
    price: Mapped[int]
    active: Mapped[bool] = mapped_column(default=True)

class Order(Base):
    __tablename__ = 'orders'
    __table_args__ = (UniqueConstraint('store_id', 'idempotency_key'), CheckConstraint('total >= 0'), CheckConstraint("status IN ('pending','cooking','completed')"))
    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey('stores.id'), index=True)
    table_id: Mapped[int] = mapped_column(ForeignKey('tables.id'), index=True)
    customer_hash: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(80))
    request_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default='pending')
    total: Mapped[int]
    payment_status: Mapped[str] = mapped_column(String(30), default='demo_paid')
    note: Mapped[str] = mapped_column(String(300), default='')
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    items: Mapped[list['OrderItem']] = relationship(cascade='all, delete-orphan', lazy='selectin')
    history: Mapped[list['OrderStatusHistory']] = relationship(cascade='all, delete-orphan', lazy='selectin', order_by='OrderStatusHistory.id')
    table: Mapped[Table] = relationship(lazy='joined')

class OrderItem(Base):
    __tablename__ = 'order_items'
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey('orders.id'), index=True)
    menu_id: Mapped[int] = mapped_column(ForeignKey('menus.id'))
    name: Mapped[str] = mapped_column(String(100))
    unit_price: Mapped[int]
    quantity: Mapped[int]
    options: Mapped[list] = mapped_column(JSON, default=list)
    subtotal: Mapped[int]

class OrderStatusHistory(Base):
    __tablename__ = 'order_status_history'
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey('orders.id'))
    status: Mapped[str] = mapped_column(String(20))
    changed_at: Mapped[datetime] = mapped_column(default=utcnow)
    admin_id: Mapped[int | None] = mapped_column(ForeignKey('admin_users.id'), nullable=True)

class AdminUser(Base):
    __tablename__ = 'admin_users'
    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey('stores.id'))
    email: Mapped[str] = mapped_column(String(200), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(Text)

class AdminSession(Base):
    __tablename__ = 'admin_sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey('admin_users.id'))
    expires_at: Mapped[datetime]

class WebSocketTicket(Base):
    __tablename__ = 'websocket_tickets'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_hash: Mapped[str] = mapped_column(String(64), index=True)
    expires_at: Mapped[datetime] = mapped_column(index=True)
