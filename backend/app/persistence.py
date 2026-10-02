from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from sqlalchemy import Boolean, DateTime, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .config import settings

class Base(DeclarativeBase): pass
class UserRow(Base):
    __tablename__='users'; username:Mapped[str]=mapped_column(String(50),primary_key=True); display_name:Mapped[str]=mapped_column(String(80)); password_hash:Mapped[str]=mapped_column(Text); role:Mapped[str]=mapped_column(String(20)); enabled:Mapped[bool]=mapped_column(Boolean,default=True)
class WorkOrderRow(Base):
    __tablename__='work_orders'; id:Mapped[str]=mapped_column(String(40),primary_key=True); asset_id:Mapped[str]=mapped_column(String(80),index=True); title:Mapped[str]=mapped_column(String(140)); priority:Mapped[str]=mapped_column(String(20)); assignee:Mapped[str]=mapped_column(String(100)); status:Mapped[str]=mapped_column(String(20),default='OPEN'); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True)); completed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
class IncidentRow(Base):
    __tablename__='incidents'; id:Mapped[str]=mapped_column(String(40),primary_key=True); asset_id:Mapped[str]=mapped_column(String(80),index=True); title:Mapped[str]=mapped_column(String(140)); severity:Mapped[str]=mapped_column(String(20)); description:Mapped[str]=mapped_column(Text); status:Mapped[str]=mapped_column(String(20)); owner:Mapped[str]=mapped_column(String(50)); opened_at:Mapped[datetime]=mapped_column(DateTime(timezone=True)); resolved_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
class ApiKeyRow(Base):
    __tablename__='api_keys'; id:Mapped[str]=mapped_column(String(40),primary_key=True); name:Mapped[str]=mapped_column(String(80)); prefix:Mapped[str]=mapped_column(String(20)); key_hash:Mapped[str]=mapped_column(Text); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True)); enabled:Mapped[bool]=mapped_column(Boolean,default=True)
class SettingRow(Base):
    __tablename__='platform_settings'; key:Mapped[str]=mapped_column(String(80),primary_key=True); value:Mapped[str]=mapped_column(Text)
class AuditRow(Base):
    __tablename__='audit_events'; id:Mapped[str]=mapped_column(String(40),primary_key=True); actor:Mapped[str]=mapped_column(String(50)); action:Mapped[str]=mapped_column(String(80)); resource:Mapped[str]=mapped_column(String(140)); timestamp:Mapped[datetime]=mapped_column(DateTime(timezone=True),index=True)

class IntegrationOutboxRow(Base):
    __tablename__='integration_outbox'; id:Mapped[str]=mapped_column(String(40),primary_key=True); event_type:Mapped[str]=mapped_column(String(100),index=True); aggregate_id:Mapped[str]=mapped_column(String(100),index=True); payload:Mapped[str]=mapped_column(Text); status:Mapped[str]=mapped_column(String(20),index=True); attempts:Mapped[int]=mapped_column(default=0); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),index=True); next_attempt_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True); published_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True); last_error:Mapped[str|None]=mapped_column(Text,nullable=True)
class WebhookSubscriptionRow(Base):
    __tablename__='webhook_subscriptions'; id:Mapped[str]=mapped_column(String(40),primary_key=True); name:Mapped[str]=mapped_column(String(80)); url:Mapped[str]=mapped_column(Text); events:Mapped[str]=mapped_column(Text); secret_hash:Mapped[str]=mapped_column(Text); secret:Mapped[str]=mapped_column(Text); enabled:Mapped[bool]=mapped_column(Boolean,default=True); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))

engine=create_engine(settings.POSTGRES_URL,pool_pre_ping=True,pool_recycle=1800)
SessionLocal=sessionmaker(bind=engine,expire_on_commit=False)

def init_database(): Base.metadata.create_all(engine)
@contextmanager
def session_scope():
    s=SessionLocal()
    try: yield s; s.commit()
    except Exception: s.rollback(); raise
    finally: s.close()
def ping()->bool:
    try:
        with engine.connect() as c: c.exec_driver_sql('SELECT 1')
        return True
    except Exception:return False
