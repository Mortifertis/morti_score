import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.services.prediction import PredictionService

logger = logging.getLogger(__name__)
settings = get_settings()


def create_dispatcher(
    session_factory: async_sessionmaker[AsyncSession],
) -> Dispatcher:
    dispatcher = Dispatcher()

    @dispatcher.message(Command("start"))
    async def start_handler(message: Message) -> None:
        await message.answer(
            "Welcome to Football Analytics Platform bot. "
            "Use /help to see commands."
        )

    @dispatcher.message(Command("help"))
    async def help_handler(message: Message) -> None:
        await message.answer(
            "Commands:\n"
            "/start - welcome message\n"
            "/help - usage help\n"
            "/predict <home_team_id> <away_team_id> - match prediction"
        )

    @dispatcher.message(Command("predict"))
    async def predict_handler(message: Message) -> None:
        parts = (message.text or "").split()
        if len(parts) != 3:
            await message.answer(
                "Usage: /predict <home_team_id> <away_team_id>"
            )
            return
        try:
            home_team_id = int(parts[1])
            away_team_id = int(parts[2])
        except ValueError:
            await message.answer("Team IDs must be integer values.")
            return

        try:
            async with session_factory() as session:
                service = PredictionService(session)
                prediction = await service.predict_match(
                    home_team_id, away_team_id
                )
        except HTTPException as exc:
            await message.answer(f"Prediction error: {exc.detail}")
            return
        lines = [
            f"{prediction.home_team.name} vs {prediction.away_team.name}",
            (
                "Expected goals: "
                f"{prediction.expected_home_goals} - "
                f"{prediction.expected_away_goals}"
            ),
            (
                "Probabilities: "
                f"H {prediction.probabilities.home_win:.2%}, "
                f"D {prediction.probabilities.draw:.2%}, "
                f"A {prediction.probabilities.away_win:.2%}"
            ),
        ]
        await message.answer("\n".join(lines))

    return dispatcher


async def run_bot(session_factory: async_sessionmaker[AsyncSession]) -> None:
    if not settings.telegram_bot_token:
        logger.info("Telegram bot token missing; bot will not start")
        return
    bot = Bot(token=settings.telegram_bot_token)
    dispatcher = create_dispatcher(session_factory)
    await dispatcher.start_polling(bot)


def launch_bot(
    session_factory: async_sessionmaker[AsyncSession],
) -> asyncio.Task:
    return asyncio.create_task(run_bot(session_factory))
