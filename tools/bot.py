from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import asyncio
import os
import sys

# Ensure project root is on sys.path when running as a script
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if PROJECT_ROOT not in sys.path:
	sys.path.insert(0, PROJECT_ROOT)

from app.config import settings


async def main() -> None:
	bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
	dp = Dispatcher()

	@dp.message(CommandStart())
	async def on_start(message: Message):
		if not settings.webapp_url:
			await message.answer("WEBAPP_URL is not configured")
			return
		kb = InlineKeyboardMarkup(
			inline_keyboard=[[InlineKeyboardButton(text="Открыть Mini App", web_app=WebAppInfo(url=settings.webapp_url))]]
		)
		await message.answer("Открой Mini App по кнопке ниже", reply_markup=kb)

	# Ensure polling mode by removing any existing webhook
	try:
		await bot.delete_webhook(drop_pending_updates=True)
	except Exception:
		pass

	await dp.start_polling(bot)


if __name__ == "__main__":
	if not settings.bot_token:
		print("BOT_TOKEN is not set. Configure it in .env")
		raise SystemExit(1)
	asyncio.run(main())
