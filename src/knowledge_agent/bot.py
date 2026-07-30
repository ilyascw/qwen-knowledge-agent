from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, Message
from aiogram.utils.chat_action import ChatActionSender

from knowledge_agent.qwen_runner import QwenError
from knowledge_agent.service import AssistantService, split_telegram_text
from knowledge_agent.settings import Settings

logger = logging.getLogger(__name__)


def create_dispatcher(
    settings: Settings,
    service: AssistantService,
) -> Dispatcher:
    dispatcher = Dispatcher()

    @dispatcher.message()
    async def handle_message(message: Message) -> None:
        sender = message.from_user
        if sender is None or sender.id != settings.telegram_user_id:
            logger.warning("Ignored a Telegram update from an unauthorized user")
            return

        if not message.text:
            await message.answer("Пока я принимаю только текстовые сообщения.")
            return

        if message.text == "/start":
            await message.answer(
                "Готов. Я могу искать в Jira и Confluence в режиме read-only "
                "и хранить только собственные заметки. Контекст диалога сохраняется; "
                "/new начинает чистую сессию без удаления долговременной памяти."
            )
            return

        if message.text == "/new":
            await service.start_new_session()
            await message.answer(
                "Новая сессия начата. Контекст диалога очищен, долговременная память сохранена."
            )
            return

        if len(message.text) > settings.max_message_length:
            await message.answer(
                f"Сообщение слишком длинное. Максимум: {settings.max_message_length} символов."
            )
            return

        bot = message.bot
        if bot is None:
            logger.error("Telegram message is not bound to a bot instance")
            return
        try:
            async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
                reply = await service.reply(message.text)
        except QwenError:
            logger.exception("Qwen request failed")
            await message.answer(
                "Не удалось обработать запрос. Ошибка записана в лог без текста сообщения."
            )
            return
        except Exception:
            logger.exception("Unexpected request failure")
            await message.answer("Внутренняя ошибка. Попробуйте ещё раз.")
            return

        for chunk in split_telegram_text(reply):
            await message.answer(chunk, disable_web_page_preview=True)

    return dispatcher


async def run_bot(settings: Settings, service: AssistantService) -> None:
    bot = Bot(token=settings.telegram_bot_token.get_secret_value())
    dispatcher = create_dispatcher(settings, service)
    try:
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Возможности агента"),
                BotCommand(command="new", description="Начать чистую сессию"),
            ]
        )
        await dispatcher.start_polling(
            bot,
            allowed_updates=dispatcher.resolve_used_update_types(),
        )
    finally:
        await bot.session.close()
