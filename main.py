import asyncio
import logging
from datetime import datetime

from aiogram import executor
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Command
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.callback_data import CallbackData


logging.basicConfig(level=logging.INFO)

API_TOKEN = 'BOT_TOKEN'

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


class ReminderForm(StatesGroup):
    tel_id = State()
    text = State()
    date = State()
    time = State()
    answer_time = State()


lang_callback = CallbackData('lang', 'lang_ru', 'lang_en')


def inline_keyboard():
    """Инлайн клавиатура."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text='Выполнено', callback_data=lang_callback.new(
                    lang_ru='Выполнено', lang_en='done'))
            ],
            [
                InlineKeyboardButton(text='Не сделано', callback_data=lang_callback.new(
                    lang_ru='Не сделано', lang_en='not_done'))
            ]
        ]
    )
    return keyboard


@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    """Обработчик команды /start."""
    await message.answer('Привет! Я бот напоминаний.\n'
                         'Воспользуйся командой для создания напоминания: /set_reminder')


@dp.message_handler(Command('set_reminder'))
async def set_reminder_start(message: types.Message):
    """Обработчик команды /set_reminder."""
    await message.reply(
        'Для создания напоминания введите следующие данные: '
        'телеграм ID сотрудника, текст напоминания, дату (ДД.ММ.ГГГГ), '
        'время (ЧЧ:ММ) и время на ответ (в минутах).'
    )

    await message.answer('Введите телеграм ID сотрудника')
    await ReminderForm.tel_id.set()


@dp.message_handler(state=ReminderForm.tel_id)
async def set_reminder_enter_tel_id(message: types.Message, state: FSMContext):
    """Обработка состояния 'tel_id'."""
    await state.update_data(tel_id=message.text)
    await message.answer('Введите текст напоминания.')

    await ReminderForm.text.set()


@dp.message_handler(state=ReminderForm.text)
async def set_reminder_enter_text(message: types.Message, state: FSMContext):
    """Обработка состояния 'text'."""
    await state.update_data(text_tasks=message.text)
    await message.answer('Введите дату (ДД.ММ.ГГГГ).')

    await ReminderForm.date.set()


@dp.message_handler(state=ReminderForm.date)
async def set_reminder_enter_date(message: types.Message, state: FSMContext):
    """Обработка состояния 'date'."""
    try:
        date_tasks = datetime.strptime(message.text, '%d.%m.%Y').date().strftime('%d.%m.%Y')
    except ValueError:
        await message.reply('Неправильный формат даты. Введите дату в формате ДД.ММ.ГГГГ.')
        return

    await state.update_data(date_tasks=date_tasks)
    await message.answer('Введите время (ЧЧ:ММ).')

    await ReminderForm.time.set()


@dp.message_handler(state=ReminderForm.time)
async def set_reminder_enter_time(message: types.Message, state: FSMContext):
    """Обработка состояния 'time'."""
    try:
        time_tasks = datetime.strptime(message.text, '%H:%M').time()

    except ValueError:
        await message.reply('Неправильный формат времени. Введите время в формате ЧЧ:ММ.')
        return

    await state.update_data(time_tasks=time_tasks)
    await message.answer('Введите время на ответ (в минутах).')

    await ReminderForm.answer_time.set()


@dp.message_handler(state=ReminderForm.answer_time)
async def set_reminder_enter_answer_time(message: types.Message, state: FSMContext):
    """Обработка состояния 'answer_time'."""
    try:
        answer_time = int(message.text)
    except ValueError:
        await message.reply('Неправильный формат времени на ответ. Введите число в минутах.')
        return

    manager = message.chat.id
    await state.update_data(answer_time=answer_time,
                            manager=manager)

    data = await state.get_data()
    tel_id = data.get('tel_id')
    text_tasks = data.get('text_tasks')
    date_tasks = data.get('date_tasks')
    time_tasks = data.get('time_tasks')
    answer_time = data.get('answer_time')
    text_to_send = f'{date_tasks} {time_tasks}\n' \
                   f'Задача: {text_tasks}\n' \
                   f'Время на выполнение: {answer_time}'

    keyboard = inline_keyboard()
    msg_for_delete = await bot.send_message(tel_id, text_to_send, reply_markup=keyboard)
    await state.update_data(msg_for_delete=msg_for_delete.message_id)

    await state.reset_state(with_data=False)

    # пока время на ответ не равно 0
    answer_time_sec = answer_time * 60
    while answer_time_sec >= 0:
        await asyncio.sleep(1)
        answer_time_sec -= 1
        if answer_time_sec == 0:
            await bot.send_message(
                text=f'Сотрудник ({tel_id}) проигнорировал задачу',
                chat_id=manager
            )
        # проверяется клик на кнопку, где осуществляется сброс состояния пользователя
        if (await state.get_data()).get('answer_time') is None:
            break


@dp.callback_query_handler(lang_callback.filter(lang_en=['done', 'not_done']))
async def process_callback_button(call: types.CallbackQuery, callback_data: dict, state: FSMContext):
    """Обработка кнопок сотрудника о выполнении задачи."""
    answer_text = callback_data.get('lang_ru')
    data = await state.get_data()
    manager = data.get('manager')
    msg_for_delete = data.get('msg_for_delete')

    await bot.send_message(text=f'{answer_text} от {call.from_user.full_name}', chat_id=manager)
    await bot.delete_message(chat_id=call.message.chat.id, message_id=msg_for_delete)

    await state.finish()


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
