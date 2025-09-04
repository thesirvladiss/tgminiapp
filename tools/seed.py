from datetime import datetime, timedelta
import sys
import os

# Ensure project root is on sys.path when running as a script
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.database import Base, engine, SessionLocal
from app import models


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Seed project cards if empty
        if db.query(models.ProjectCard).count() == 0:
            cards = [
                models.ProjectCard(title="Магазин подкастов", url="/podcasts", order=1, is_internal=True),
                models.ProjectCard(title="Закрытый канал", url="https://t.me/", order=2),
                models.ProjectCard(title="Курс по финансам", url="https://example.com/finance", order=3),
                models.ProjectCard(title="Пересказы книг", url="https://example.com/books", order=4),
                models.ProjectCard(title="Пост и молитва", url="https://example.com/pray", order=5),
                models.ProjectCard(title="Благотворительность", url="https://example.com/donate", order=6),
            ]
            db.add_all(cards)

        # Seed podcasts if empty
        if db.query(models.Podcast).count() == 0:
            now = datetime.utcnow()
            items = []
            for i in range(1, 6 + 1):
                items.append(
                    models.Podcast(
                        title=f"Подкаст #{i}",
                        description="Описание подкаста. Это демо-данные.",
                        category=["финансы", "отношения", "психология"][i % 3],
                        published_at=now - timedelta(days=i * 7),
                        duration_seconds=1800 + i * 120,
                        cover_path=None,
                        audio_preview_path=None,
                        audio_full_path=None,
                        is_published=True,
                        is_free=(i == 1),
                    )
                )
            db.add_all(items)

        db.commit()
        print("Seeding completed.")
    finally:
        db.close()


if __name__ == "__main__":
    main()


