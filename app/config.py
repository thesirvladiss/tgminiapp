import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseModel):
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    admin_login: str = os.getenv("ADMIN_LOGIN", "admin")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "admin123")
    uploads_dir: str = os.getenv("UPLOADS_DIR", "uploads")
    bot_token: str = os.getenv("BOT_TOKEN", "")
    webapp_url: str = os.getenv("WEBAPP_URL", "http://127.0.0.1:8000/")
    # Payform (Prodamus) settings
    payform_url: str = os.getenv("PAYFORM_URL", "https://demo.payform.ru/")
    payform_secret: str = os.getenv("PAYFORM_SECRET", "2y2aw4oknnke80bp1a8fniwuuq7tdkwmmuq7vwi4nzbr8z1182ftbn6p8mhw3bhz")
    payform_sys: str = os.getenv("PAYFORM_SYS", "")


settings = Settings()

# Ensure uploads directory exists
os.makedirs(settings.uploads_dir, exist_ok=True)

