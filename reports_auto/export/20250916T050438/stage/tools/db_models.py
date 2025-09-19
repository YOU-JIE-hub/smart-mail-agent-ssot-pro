from __future__ import annotations
import os, datetime as dt
from sqlalchemy import create_engine, Column, Integer, String, Text, Float, DateTime, Index
try:
    from sqlalchemy import JSON
except Exception:
    JSON = Text
from sqlalchemy.orm import declarative_base, sessionmaker

PG_DSN = os.environ.get("SMA_PG_DSN","").strip()
DB_URL = PG_DSN if PG_DSN else "sqlite:///db/sma.sqlite"
engine  = create_engine(DB_URL, future=True)
Session = sessionmaker(bind=engine, future=True)
Base = declarative_base()

# 這些 ORM 表是「專業層」；你的舊 sqlite actions 仍可用（視圖會直接讀舊 actions）
class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    mail_id = Column(String(64), index=True)
    ts = Column(DateTime, default=dt.datetime.utcnow, index=True)
    from_addr = Column(String(256))
    to_addr   = Column(String(256))
    subject   = Column(Text)
    body_path = Column(String(512))

class Classification(Base):
    __tablename__ = "classifications"
    id = Column(Integer, primary_key=True)
    ts = Column(DateTime, default=dt.datetime.utcnow, index=True)
    mail_id = Column(String(64), index=True)
    backend = Column(String(32))      # rule / ml / boosted
    intent  = Column(String(64), index=True)
    confidence = Column(Float)
    extras  = Column(JSON)            # {"raw_label":..., "pkl":...}
Index("ix_cls_mail_backend", Classification.mail_id, Classification.backend)

# 對應你 sqlite 舊表：actions
class ActionLog(Base):
    __tablename__ = "actions"
    id = Column(Integer, primary_key=True)
    ts = Column(String(32), index=True)     # 注意：沿用你原本 TEXT 時戳 'YYYY-MM-DDTHH:MM:SS'
    intent = Column(String(64), index=True)
    action = Column(String(64), index=True)
    status = Column(String(16), index=True)
    artifact_path = Column(String(512))
    ext = Column(String(256))
    message = Column(Text)

class DeadLetter(Base):
    __tablename__ = "dead_letters"
    id = Column(Integer, primary_key=True)
    ts = Column(String(32), index=True)     # 舊表可能為 TEXT
    intent = Column(String(64))
    action = Column(String(64))
    reason = Column(String(256))
    payload = Column(JSON)

class KIESlot(Base):
    __tablename__ = "kie_slots"
    id = Column(Integer, primary_key=True)
    ts = Column(DateTime, default=dt.datetime.utcnow, index=True)
    mail_id = Column(String(64), index=True)
    slots = Column(JSON)

class SpamScore(Base):
    __tablename__ = "spam_scores"
    id = Column(Integer, primary_key=True)
    ts = Column(DateTime, default=dt.datetime.utcnow, index=True)
    mail_id = Column(String(64), index=True)
    model = Column(String(64))  # text/rule/ens
    score = Column(Float)

def init_db():
    # 只會建立 ORM 新表；不會破壞你現有的 actions/ dead_letters
    Base.metadata.create_all(engine)
    return engine
