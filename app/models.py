from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship

from .database import Base


class ProjectCard(Base):
    __tablename__ = "project_cards"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    url = Column(String(500), nullable=False)
    order = Column(Integer, default=0, nullable=False)
    icon = Column(String(200), nullable=True)
    is_internal = Column(Boolean, default=False, nullable=False)


class Podcast(Base):
    __tablename__ = "podcasts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)
    published_at = Column(DateTime, default=datetime.utcnow)
    duration_seconds = Column(Integer, default=0)
    cover_path = Column(String(500), nullable=True)
    audio_preview_path = Column(String(500), nullable=True)
    audio_full_path = Column(String(500), nullable=True)
    is_published = Column(Boolean, default=False)
    is_free = Column(Boolean, default=False)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String(64), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    free_podcast_id = Column(Integer, ForeignKey("podcasts.id"), nullable=True)
    has_subscription = Column(Boolean, default=False)

    free_podcast = relationship("Podcast")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(String(50), nullable=False)  # 'single' or 'subscription'
    podcast_id = Column(Integer, ForeignKey("podcasts.id"), nullable=True)
    status = Column(String(50), default="success")  # 'success' / 'error'
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    podcast = relationship("Podcast")


