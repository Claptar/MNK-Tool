import os
import logging
import pickle

import pandas as pd
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor
from aiogram.utils.exceptions import TelegramAPIError, BotBlocked

from activity import stat
from math_module import math_part
from koryavov import kor
from data_constructor import psg
import datetime

logging.basicConfig(level=logging.INFO)

API_TOKEN = os.environ['TOKEN']

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


class Start(StatesGroup):
    group = State()
    custom = State()


class Profile(StatesGroup):
    choose = State()
    group = State()
    custom = State()


class Timetable(StatesGroup):
    choose = State()
    another_group = State()
    weekday = State()


class Koryavov(StatesGroup):
    sem_num_state = State()
    task_num_state = State()
    finish_state = State()


class Custom(StatesGroup):
    existing = State()
    new = State()
    weekday = State()
    time = State()
    edit = State()
    again = State()


class Exam(StatesGroup):
    another_group = State()
    choose = State()


class Plots(StatesGroup):
    title_state = State()
    mnk_state = State()
    error_bars_state = State()
    plot_state = State()


class Stat(StatesGroup):
    choice = State()
    unique = State()
    frequency = State()


class Mailing(StatesGroup):
    mailing = State()


def today_tomorrow_keyboard():
    """
    Кнопки для получения расписания на сегодня или завтра.
    """
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*[types.KeyboardButton(name) for name in ['На сегодня', 'На завтра', '/help']])
    return keyboard


def schedule_string(schedule: pd.DataFrame):
    """
    Строка с расписанием, которую отправляет бот.
    ВАЖНО! parse_mode='HTML' - чтобы читалcя измененный шрифт.
    """
    STRING = ''  # "строка" с расписанием, которую отправляем сообщением
    for row in schedule.iterrows():  # проходимся по строкам расписания, приплюсовываем их в общую "строку"
        # время пары - жирный + наклонный шрифт, название пары на следующей строке
        string: str = '<b>' + '<i>' + row[0] + '</i>' + '</b>' + '\n' + row[1][0]
        STRING += string + '\n\n'  # между парами пропуск (1 enter)
    return STRING


@dp.message_handler(Text(equals='Выход'), state='*')
async def user_exit(message: types.Message, state: FSMContext):
    """
    Функция, выполняющая выход по желанию пользователя (на любой стадии).
    """
    await psg.insert_action('exit', message.chat.id)
    current_state = await state.get_state()  # проверка, что запущено хотя бы какое-то из состояний
    if current_state is None:
        return
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    await bot.send_message(
        message.chat.id,
        'Без проблем! Но ты это, заходи, если что 😉',
        reply_markup=today_tomorrow_keyboard()
    )
    # стикос "Ты заходи есчо"
    await bot.send_sticker(
        message.chat.id,
        'CAACAgIAAxkBAAIsCV42vjU8mR9P-zoPiyBu_3_eG-wTAAIMDQACkjajC9UvBD6_RUE4GAQ'
    )
    # При выходе выключаем машину состояний
    await state.finish()


@dp.message_handler(Text(equals=['На сегодня', 'На завтра']))
async def send_today_tomorrow_schedule(message):
    """
    Функция ловит сообщение с текстом 'На сегодня/завтра'.
    Возвращает расписание на этот день, вызывает функцию timetable.timetable_by_group().
    По умолчанию, если у этого пользователя есть личное расписание, выдает его,
    иначе - расписание группы пользователя.
    Схема:
                             CUSTOM
                            /     \
                        True    False (ERR or EMPTY_RES)
                       /   \         \
                  (SMTH,) (None,) — MY_GROUP — True — SEND()
                    /                   /
                  SEND()             False — EMPTY_RES — Знакомы ли мы?
                                       |
                              CONN_ERR or OTHER_ERR — Попробуй позже, пожалуйста
    """
    await psg.insert_action('to/yes', message.chat.id)
    # список дней для удобной конвертации номеров дней недели (0, 1, ..., 6) в их названия
    week = tuple(['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'])
    today = datetime.datetime.today().weekday()  # today - какой сегодня день недели (от 0 до 6)
    tomorrow = today + 1 if today in range(6) else 0  # номер дня для завтра, если это воскресенье (6), то 0
    day = today if message.text == 'На сегодня' else tomorrow  # выбор дня в зависимости от запроса
    custom_timetable = await psg.send_timetable(custom=True, chat_id=message.chat.id)
    # проверка, есть ли у этого пользователя личное расписание в базе данных (+ не произошло ли ошибок)
    if custom_timetable[0] and custom_timetable[1][0] is not None:
        schedule = pickle.loads(custom_timetable[1][0])[week[day]].to_frame()
        await bot.send_message(  # отправляем расписание
            message.chat.id,
            schedule_string(schedule),
            parse_mode='HTML'
        )
    # если у этого пользователя нет личного расписания в базе данных или произошла ошибка при запросе
    # личного расписания, то пробуем отправить расписание группы
    else:
        group_timetable = await psg.send_timetable(my_group=True, chat_id=message.chat.id)
        if group_timetable[0]:  # если пользователь есть в базе
            if bytes(group_timetable[1][0]) == b'DEFAULT':
                await bot.send_message(  # отправляем расписание
                    message.chat.id,
                    'В этом семестре нет официального расписания для твоей группы( '
                    'Пожалуйста, измени номер своей группы в /profile '
                    'или создай личное расписание в /custom 😉',
                    reply_markup=today_tomorrow_keyboard()
                )
            else:
                schedule = pickle.loads(group_timetable[1][0])[week[day]].to_frame()
                await bot.send_message(  # отправляем расписание
                    message.chat.id,
                    schedule_string(schedule),
                    parse_mode='HTML'
                )
                await bot.send_message(
                    message.chat.id,
                    'Чем ещё я могу помочь?',
                    reply_markup=today_tomorrow_keyboard()
                )
        # если в базе данных нет этого пользователя
        elif not group_timetable[0] and group_timetable[1] == 'empty_result':
            await bot.send_message(
                message.chat.id,
                'Кажется, мы с тобой еще не знакомы... 😢\n'
                'Скорей пиши мне /start!',
                reply_markup=today_tomorrow_keyboard()
            )
        # если произошла ошибка
        else:
            await bot.send_message(
                message.chat.id,
                'Что-то пошло не так, попробуй еще раз позже, пожалуйста)',
                reply_markup=today_tomorrow_keyboard()
            )


@dp.message_handler(commands=['help'])
async def help_def(message: types.Message):
    """
    Функция ловит сообщение с командой '/help' и присылает описание комманд бота.
    """
    await psg.insert_action('help', message.chat.id)
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    with open('files/help.txt', encoding='utf-8', mode='r') as f:
        text = f.read()
    await bot.send_message(message.chat.id, text)


@dp.message_handler(commands='start')
async def start_initiate(message: types.Message):
    """
    Функция ловит сообщение с командой '/start' и приветствует пользователя.
    """
    group = await psg.check_user_group(message.chat.id)
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    if group[0]:  # если пользователь уже есть в базе данных
        await bot.send_message(
            message.chat.id,
            'Привет-привет! 🙃\nМы уже с тобой знакомы 😉 '
            'Напиши /help, чтобы я напомнил тебе, что я умею)',
            reply_markup=today_tomorrow_keyboard()
        )
    elif not group[0] and group[1] == 'empty_result':  # пользователя нет в базе данных
        await Start.group.set()  # изменяем состояние на Start.group
        await bot.send_message(
            message.chat.id,
            'Привет-привет! 🙃\nДавай знакомиться! Меня зовут Помогатор. '
            'Можешь рассказать мне немного о себе, '
            'чтобы я знал, чем могу тебе помочь?'
        )
        await psg.insert_action('start', message.chat.id)  # Запись события о новом пользователе
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(*[types.KeyboardButton(name) for name in ['Уже не учусь', 'Выход']])
        await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
        await bot.send_message(  # 'Уже не учусь' - вариант для выпускников
            message.chat.id,
            ' Не подскажешь номер своей группы?\n'
            '(В формате Б00-228 или 777, как в расписании)',
            reply_markup=keyboard
        )
    # произошла какая-то ошибка (с соединением или другая)
    else:
        await bot.send_message(
            message.chat.id,
            'Что-то пошло не так, попробуй еще раз позже, пожалуйста)'
        )


@dp.message_handler(state=Start.group)
async def start_proceed_group(message: types.Message, state: FSMContext):
    """
    Функция принимает значение номера группы и проверяет, есть ли такая группа в базе.
    Если группы нет в базе данных (или произошла какая-то ошибка), то функция просит ввести номер группы заново.
    Если группа есть в базе данных, информация о пользователе заносится в таблицу User, а пользователю
    отправляется запрос, нужно ли ему личное расписание.
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    (group, text) = (
        'ALUMNI',
        'Привет достопочтенному выпускнику! 👋'
    ) if message.text == 'Уже не учусь' else (  # разные варианты для выпускника и студента
        message.text,
        'Отлично, вот мы и познакомились 🙃'
    )
    insert = await psg.insert_user(message.chat.id, group)
    if insert[0]:  # группа есть в базе, добавление пользователя прошло успешно
        # async with state.proxy() as data:
        #     data['group'] = group
        await Start.custom.set()  # меняем состояние на Start.custom
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(*[types.KeyboardButton(name) for name in ['Хочу', 'Не хочу']])
        await bot.send_message(  # запрос о личном расписании
            message.chat.id,
            text + '\nЕсли хочешь получить возможность использовать '
                   'личное расписание, нажми на нужную кнопку внизу.',
            reply_markup=keyboard
        )
    # группы нет в базе / что-то другое, не связанное с подключением, просим повторить ввод
    elif not insert[0] and insert[1] == 'other_error':
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(*[types.KeyboardButton(name) for name in ['Уже не учусь', 'Выход']])
        await bot.send_message(
            message.chat.id,
            'Что-то пошло не так, введи номер своей группы ещё раз, пожалуйста)',
            reply_markup=keyboard
        )
    # произошла какая-то ошибка с соединением
    else:
        await bot.send_message(
            message.chat.id,
            'Что-то не так с соединением, попробуй ещё раз позже, пожалуйста)'
        )
        await state.finish()


@dp.message_handler(lambda message: message.content_type != types.message.ContentType.TEXT,
                    content_types=types.message.ContentType.ANY, state=Start.group)
async def start_proceed_group_invalid_type(message: types.Message):
    """
    Функция просит ввести номер группы заново, если формат ввода номера группы неправильный.
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    await message.reply("Пришли номер группы в верном формате, пожалуйста)")


@dp.message_handler(Text(equals=['Хочу', 'Не хочу']), state=Start.custom)
async def start_proceed_custom(message: types.Message, state: FSMContext):
    """
    Функция принимает ответ пользователя, нужно ли ему личное расписание, заносит заготовку
    в базу данных, если ответ положительный.
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    if message.text == 'Не хочу':  # ответ пользователя отрицательный
        await bot.send_message(
            message.chat.id,
            'Хорошо, но не забывай, что ты всегда можешь вернуться, '
            'если захочешь опробовать его в деле 😉\n'
            'Чтобы вызвать личное расписание, напиши /custom.'
        )
        await bot.send_message(  # в любом случае пишем про /help
            message.chat.id,
            'А теперь скорее пиши /help, чтобы узнать, '
            'чем еще я могу помочь тебе!',
            reply_markup=today_tomorrow_keyboard()
        )
    elif message.text == 'Хочу':  # ответ пользователя положительный
        # async with state.proxy() as data:
        #     group = data['group']
        # если номер группы верный (по идее должно быть выполнено)
        # и добавление заготовки расписания прошло успешно
        update = await psg.create_custom_timetable(message.chat.id)
        if update[0]:
            await bot.send_message(
                message.chat.id,
                'Отлично, все получилось 🙃\n'
                'Теперь ты можешь использовать личное расписание! '
                'Чтобы вызвать его, напиши /custom.'
            )
            await bot.send_message(
                message.chat.id,
                'А теперь скорее пиши /help, чтобы узнать, '
                'чем еще я могу помочь тебе!',
                reply_markup=today_tomorrow_keyboard()
            )
        else:
            await bot.send_message(
                message.chat.id,
                'Что-то пошло не так, попробуй еще раз позже, пожалуйста)\n'
                'Чтобы настроить личное расписание, напиши /custom.'
            )
            await bot.send_message(
                message.chat.id,
                'Не расстраивайся! Напиши /help, чтобы узнать, '
                'чем еще я могу помочь тебе!',
                reply_markup=today_tomorrow_keyboard()
            )
    await state.finish()  # в любом случае останавливаем машину состояний


@dp.message_handler(lambda message: message.content_type != types.message.ContentType.TEXT
                    or message.text not in ['Хочу', 'Не хочу'],
                    content_types=types.message.ContentType.ANY, state=Start.custom)
async def start_proceed_custom_invalid(message: types.Message):
    """
    Функция просит выбрать вариант из предложенных, если формат ввода неправильный.
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    await message.reply("Выбери вариант из предложенных, пожалуйста)")


@dp.message_handler(commands='profile')
async def edit_initiate(message: types.Message):
    """
    Функция ловит сообщение с командой '/profile' и спрашивает у пользователя,
    хочет ли он изменить группу, закрепленную за ним.
    """
    await psg.insert_action('profile', message.chat.id)
    cur_group = await psg.check_user_group(message.chat.id)
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    if cur_group[0]:
        await Profile.choose.set()  # изменяем состояние на Profile.choose
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(*[types.KeyboardButton(name) for name in ['Да', 'Нет', 'Выход']])
        if cur_group[1][0] == 'ALUMNI':
            await bot.send_message(
                message.chat.id,
                f'Сейчас у тебя указано, что ты – выпускник. '
                'Ты хочешь изменить это значение на номер группы?',
                reply_markup=keyboard
            )
        else:
            await bot.send_message(
                message.chat.id,
                f'Сейчас у тебя указано, что ты учишься в группе {cur_group[1][0]}. '
                'Ты хочешь изменить это значение?',
                reply_markup=keyboard
            )
    # если в базе данных нет этого пользователя
    elif not cur_group[0] and cur_group[1] == 'empty_result':
        await bot.send_message(
            message.chat.id,
            'Кажется, мы с тобой еще не знакомы... 😢\n'
            'Скорей пиши мне /start!',
            reply_markup=today_tomorrow_keyboard()
        )
    # если произошла ошибка
    else:
        await bot.send_message(
            message.chat.id,
            'Что-то пошло не так, попробуй еще раз позже, пожалуйста)',
            reply_markup=today_tomorrow_keyboard()
        )


@dp.message_handler(Text(equals=['Да', 'Нет']), state=Profile.choose)
async def edit_proceed_choose(message: types.Message, state: FSMContext):
    """
    Функция принимает ответ пользователя, хочет ли он поменять значение группы
    и просит пользователя ввести желаемый номер группы.
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    if message.text == 'Да':  # положительный ответ, запрос о вводе номера группы
        await Profile.group.set()  # изменяем состояние на Profile.group
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(*[types.KeyboardButton(name) for name in ['Уже не учусь', 'Выход']])
        await bot.send_message(
            message.chat.id,
            'Введи номер группы, пожалуйста)',
            reply_markup=keyboard
        )
    elif message.text == 'Нет':  # отрицательный ответ
        await bot.send_message(
            message.chat.id,
            'Я рад, что тебя все устраивает 😉',
            reply_markup=today_tomorrow_keyboard()
        )
        await state.finish()  # выключаем машину состояний


@dp.message_handler(lambda message: message.content_type != types.message.ContentType.TEXT
                    or message.text not in ['Да', 'Нет', 'Выход'],
                    content_types=types.message.ContentType.ANY, state=Profile.choose)
async def edit_proceed_choose_invalid(message: types.Message):
    """
    Функция просит выбрать из вариант из предложенных, если формат ввода неправильный.
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    await message.reply("Выбери вариант из предложенных, пожалуйста)")


@dp.message_handler(state=Profile.group)
async def edit_proceed_group(message: types.Message, state: FSMContext):
    """
    Функция ловит ответ пользователя с номером группы, если обновление удалось сделать,
    посылает пользователю запрос, хочет ли он изменить свое личное расписание.
    :param message:
    :param state:
    :return:
    """
    # получилось обновить номер группы, запрос о изменении личного расписания
    group = 'ALUMNI' if message.text == 'Уже не учусь' else message.text
    update = await psg.update_user(message.chat.id, group)
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    if update[0]:
        # async with state.proxy() as data:
        #     data['group'] = group
        await Profile.custom.set()  # изменяем состояние на Profile.custom
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(*[types.KeyboardButton(name) for name in ['Хочу', 'Не хочу']])
        await bot.send_message(
            message.chat.id,
            'Все готово) Ты хочешь поменять личное '
            'расписание на расписание новой группы?',
            reply_markup=keyboard
        )
    # номера группы нет в базе (или произошла какая-то другая ошибка, не связанная с соединением)
    elif not update[0] and update[1] == 'other_error':
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(*[types.KeyboardButton(name) for name in ['Уже не учусь', 'Выход']])
        await bot.send_message(  # просим пользователя ввести номер группы еще раз
            message.chat.id,
            'Что-то пошло не так, введи номер своей группы ещё раз, пожалуйста)',
            reply_markup=keyboard
        )
    else:
        await bot.send_message(  # просим пользователя ввести номер группы еще раз
            message.chat.id,
            'Что-то не так с соединением, попробуй ещё раз позже, пожалуйста)',
            reply_markup=today_tomorrow_keyboard()
        )
        await state.finish()


@dp.message_handler(lambda message: message.content_type != types.message.ContentType.TEXT,
                    content_types=types.message.ContentType.ANY, state=Profile.group)
async def edit_proceed_group_invalid_type(message: types.Message):
    """
    Функция просит ввести номер группы заново, если формат ввода номера группы неправильный.
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    await message.reply("Пришли номер группы в верном формате, пожалуйста)")


@dp.message_handler(Text(equals=['Хочу', 'Не хочу']), state=Profile.custom)
async def edit_proceed_custom(message: types.Message, state: FSMContext):
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    if message.text == 'Не хочу':  # если пришел отрицательный ответ
        await bot.send_message(
            message.chat.id,
            'Я рад, что тебя все устраивает 😉',
            reply_markup=today_tomorrow_keyboard()
        )
    elif message.text == 'Хочу':  # если пришел положительный ответ, то изменяем личное расписание
        # async with state.proxy() as data:
        #     group = data['group']
        update = await psg.create_custom_timetable(message.chat.id)
        if update[0]:
            await bot.send_message(
                message.chat.id,
                'Отлично, все получилось 🙃\n'
                'Чтобы вызвать личное расписание, напиши /custom.',
                reply_markup=today_tomorrow_keyboard()
            )
        else:  # если произошла ошибка при обновлении расписания
            await bot.send_message(
                message.chat.id,
                'Что-то пошло не так, попробуй еще раз позже, пожалуйста)\n'
                'Чтобы настроить личное расписание, напиши /custom.',
                reply_markup=today_tomorrow_keyboard()
            )
    await state.finish()


@dp.message_handler(lambda message: message.content_type != types.message.ContentType.TEXT
                    or message.text not in ['Хочу', 'Не хочу'],
                    content_types=types.message.ContentType.ANY, state=Profile.custom)
async def edit_proceed_custom_invalid(message: types.Message):
    """
    Функция просит выбрать из вариант из предложенных, если формат ввода неправильный.
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    await message.reply("Выбери вариант из предложенных, пожалуйста)")


@dp.message_handler(commands='koryavov')
async def koryavov(message: types.Message):
    """
    Функция ловит сообщение с текстом /koryavov.
    Отправляет пользователю сообщение с просьбой выбрать интересующий его номер семестра курса общей физики
    """
    await psg.insert_action('koryavov', message.chat.id)
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*[types.KeyboardButton(name) for name in [1, 2, 3, 4, 5, 'Выход']])  # кнопки c номерами семестров
    await bot.send_message(message.chat.id, 'Выбери номер семестра общей физики: \n'
                                            '1) Механика \n'
                                            '2) Термодинамика \n'
                                            '3) Электричество \n'
                                            '4) Оптика\n'
                                            '5) Атомная и ядерная физика', reply_markup=keyboard)
    await Koryavov.sem_num_state.set()


@dp.message_handler(lambda message: message.text.isdigit(), state=Koryavov.sem_num_state)
async def sem_num(message: types.Message, state: FSMContext):
    """
    Функция принимает сообщение от пользователя с номером семестра и записывает его в data storage.
    Так же отправляется сообщение с просьбой указать номер задачи, интересующей пользователя.
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    async with state.proxy() as data:
        data['sem_num'] = message.text
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*[types.KeyboardButton(name) for name in ['Выход']])
    await bot.send_message(message.chat.id, 'Отлично, напиши теперь номер задачи', reply_markup=keyboard)
    await Koryavov.task_num_state.set()


# If some invalid input
@dp.message_handler(state=Koryavov.sem_num_state)
async def kor_sem_inv_input(message: types.Message):
    """
    В случае некоректного ответа на запрос номера семестра отправляется сообщение с просьбой
    указать правильный номер семестра
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*[types.KeyboardButton(name) for name in [1, 2, 3, 4, 5, 'Выход']])  # кнопки c номерами семестров
    await bot.send_message(message.chat.id, 'Что-то не так, давай ещё раз. Выбери номер семестра:')


@dp.message_handler(lambda message: math_part.is_digit(message.text) or message.text == "Ещё одну",
                    state=Koryavov.task_num_state)
async def task_page(message: types.Message, state: FSMContext):
    """
    Функция ловит сообщение с номером задачи и делает запрос на сайт mipt1.ru чтобы
    узнать номер страницы в корявове с этой задаче. После чего отправляет пользователю
    эту информацию. Так же присылается вопрос "нужна ли ещё одна задача ?".
    """
    task_num = message.text
    await bot.send_chat_action(message.chat.id, 'typing')
    async with state.proxy() as data:
        sem_num = int(data['sem_num'])
    reply = 'Информация взята с сайта mipt1.ru \n\n' + kor.kor_page(sem_num, task_num)
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*[types.KeyboardButton(name) for name in ['Ещё одну', 'Всё, хватит']])
    await bot.send_message(message.chat.id, reply, reply_markup=keyboard)
    await Koryavov.finish_state.set()


# If some invalid input
@dp.message_handler(state=Koryavov.task_num_state)
async def kor_task_inv_input(message: types.Message):
    """
    В случае некорректоного ввода номера задачи, функция отправляет сообщение с просьбой повторить ввод
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*[types.KeyboardButton(name) for name in ['Выход']])
    await bot.send_message(message.chat.id, 'Что-то не так, введи номер задачи ещё раз)', reply_markup=keyboard)


@dp.message_handler(Text(equals=['Ещё одну', 'Всё, хватит']), state=Koryavov.finish_state, )
async def kor_finish(message: types.Message, state: FSMContext):
    """
    Функция принимает сообщение содержащее ['Ещё одну', 'Всё, хватит'] и Koryavov.finish_state(). И в зависимости
    от сообщения завершает функцию /koryavov или отправляет на предыдущий шаг.
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    if message.text == 'Ещё одну':
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(*[types.KeyboardButton(name) for name in ['Выход']])
        await bot.send_message(
            message.chat.id,
            'Окей, напиши номер нужной задачи',
            reply_markup=keyboard)
        await Koryavov.task_num_state.set()
    else:
        async with state.proxy() as data:
            data.clear()
        await bot.send_message(
            message.chat.id,
            'Рад был помочь😉 Удачи !',
            reply_markup=today_tomorrow_keyboard())
        await state.finish()


# If some invalid input
@dp.message_handler(state=Koryavov.finish_state)
async def kor_task_inv_input(message: types.Message):
    """
    В случае некорректоного сообщения, функция отправляет сообщение с просьбой попробовать ещё раз.
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*[types.KeyboardButton(name) for name in ['Ещё одну', 'Всё, хватит', 'Выход']])
    await bot.send_message(
        message.chat.id,
        'Что-то пошло не так. Ты хочешь узнать номер страницы для ещё одной задачи ?',
        reply_markup=keyboard)


@dp.message_handler(commands='timetable')
async def timetable_initiate(message: types.Message):
    """
    Функция ловит сообщение с текстом "/timetable".
    Отправляет пользователю вопрос, расписание своей или другой группы ему нужно.
    """
    await psg.insert_action('timetable', message.chat.id)
    await Timetable.choose.set()  # ставим состояние Timetable.choose
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    await bot.send_message(
        message.chat.id,
        'Снова не можешь вспомнить, какая пара следующая?\n'
        'Ничего, я уже тут! 😉'
    )
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*[types.KeyboardButton(name) for name in ['Личное', 'Моя группа']])
    keyboard.add(*[types.KeyboardButton(name) for name in ['Другая группа', 'Выход']])
    await bot.send_message(
        message.chat.id,
        'Выбери, пожалуйста, какое расписание тебе нужно)',
        reply_markup=keyboard
    )


@dp.message_handler(lambda message: message.content_type != types.message.ContentType.TEXT
                    or message.text not in ['Личное', 'Моя группа', 'Другая группа', 'Выход'],
                    state=Timetable.choose, content_types=types.message.ContentType.ANY)
async def timetable_proceed_choose_invalid(message: types.Message):
    """
    Функция просит пользователя выбрать вариант из списка ['Личное', 'Моя группа', 'Другая группа', 'Выход'],
    если сообщение не содержит никакую из этих строк (+ проверка типа сообщения).
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    await message.reply("Выбери вариант из предложенных, пожалуйста)")


@dp.message_handler(Text(equals=['Другая группа']), state=Timetable.choose)
async def timetable_proceed_choose(message: types.Message):
    """
    Функция ловит сообщение с текстом 'Другая группа' и отправляет пользователю вопрос о номере группы.
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    await Timetable.another_group.set()  # изменяем состояние на Timetable.another_group
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*[types.KeyboardButton(name) for name in ['Выход']])  # кнопка для выхода из функции
    await bot.send_message(
        message.chat.id,  # просим пользователя ввести номер группы
        'Не подскажешь номер группы?\n'
        '(В формате Б00–228 или 777, как в расписании)',
        reply_markup=keyboard
    )


@dp.message_handler(state=Timetable.another_group)
async def timetable_proceed_another_group(message: types.Message, state: FSMContext):
    """
    Функция принимает сообщение с номером группы и проверяет его. Если все хорошо, то отправляет
    пользователю запрос о дне недели. Если произошла какая-то ошибка, то функция просит пользователя
    ввести номер группы еще раз.
    """
    timetable = await psg.send_timetable(another_group=message.text)
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    if timetable[0]:
        await Timetable.weekday.set()  # изменяем состояние на Timetable.weekday
        async with state.proxy() as data:
            data['schedule'] = pickle.loads(timetable[1][0])  # записываем расписание
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        # дни недели для тыков и кнопка для выхода (строки выбраны по размеру слов)
        keyboard.add(*[types.KeyboardButton(name) for name in ['На неделю']])
        keyboard.add(*[types.KeyboardButton(name) for name in ['Понедельник', 'Вторник']])
        keyboard.add(*[types.KeyboardButton(name) for name in ['Среда', 'Четверг']])
        keyboard.add(*[types.KeyboardButton(name) for name in ['Пятница', 'Суббота']])
        keyboard.add(*[types.KeyboardButton(name) for name in ['Воскресенье', 'Выход']])
        await bot.send_message(
            message.chat.id,
            'Расписание на какой день недели ты хочешь узнать?',
            reply_markup=keyboard
        )
    # номера группы нет в базе / произошла какая-то ошибка, связанная с соединением
    elif not timetable[0] and timetable[1] == 'connection_error':
        await bot.send_message(
            message.chat.id,
            'Что-то не так с соединением, попробуй еще раз позже, пожалуйста)',
            reply_markup=today_tomorrow_keyboard()
        )
        await state.finish()
    # произошла какая-то ошибка другого рода
    else:
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(*[types.KeyboardButton(name) for name in ['Выход']])
        await bot.send_message(  # просим пользователя ввести номер группы еще раз
            message.chat.id,
            'К сожалению я не знаю такой группы(\n'
            'Введи номер ещё раз, пожалуйста)',
            reply_markup=keyboard
        )


@dp.message_handler(lambda message: message.content_type != types.message.ContentType.TEXT,
                    state=Timetable.another_group,
                    content_types=types.message.ContentType.ANY)
async def timetable_proceed_another_group_invalid_type(message: types.Message):
    """
    Функция просит ввести номер группы заново, если формат ввода неправильный.
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    await message.reply("Пришли номер группы в верном формате, пожалуйста)")


@dp.message_handler(Text(equals=['Личное', 'Моя группа']), state=Timetable.choose)
async def timetable_proceed_my_group_custom(message: types.Message, state: FSMContext):
    """
    Функция принимает сообщение от пользователя с запросом нужного ему варианта расписания.
    Отправляет пользователю вопрос о нужном дне недели. В случае ошибки отправляет пользователю
    сообщение о необходимости редактирования номера группы или личного расписания.
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    timetable = (await psg.send_timetable(custom=True, chat_id=message.chat.id) if message.text == 'Личное' else
                 await psg.send_timetable(my_group=True, chat_id=message.chat.id))
    if timetable[0]:  # если расписание было найдено
        print(bytes(timetable[1][0]))
        if bytes(timetable[1][0]) == b'DEFAULT':
            print(bytes(timetable[1][0]))
            await bot.send_message(  # отправляем расписание
                message.chat.id,
                'В этом семестре нет официального расписания для твоей группы( '
                'Пожалуйста, измени номер своей группы в /profile 😉',
                reply_markup=today_tomorrow_keyboard()
            )
            await state.finish()
        elif timetable[1][0] is not None and bytes(timetable[1][0]) != b'DEFAULT':
            await Timetable.weekday.set()  # изменяем состояние на Timetable.weekday
            async with state.proxy() as data:
                data['schedule'] = pickle.loads(timetable[1][0])  # записываем расписание
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            # дни недели для тыков и кнопка для выхода (строки выбраны по размеру слов)
            keyboard.add(*[types.KeyboardButton(name) for name in ['На неделю']])
            keyboard.add(*[types.KeyboardButton(name) for name in ['Понедельник', 'Вторник']])
            keyboard.add(*[types.KeyboardButton(name) for name in ['Среда', 'Четверг']])
            keyboard.add(*[types.KeyboardButton(name) for name in ['Пятница', 'Суббота']])
            keyboard.add(*[types.KeyboardButton(name) for name in ['Воскресенье', 'Выход']])
            await bot.send_message(
                message.chat.id,
                'Расписание на какой день недели ты хочешь узнать?',
                reply_markup=keyboard
            )
        else:
            await bot.send_message(
                message.chat.id,
                'Не могу найти твое личное расписание 😞\n'
                'Нажми /custom чтобы проверить корректность данных.',
                reply_markup=today_tomorrow_keyboard()
            )
            await state.finish()
    # если в базе данных нет этого пользователя
    elif not timetable[0] and timetable[1] == 'empty_result':
        await bot.send_message(
            message.chat.id,
            'Кажется, мы с тобой еще не знакомы... 😢\n'
            'Cкорей пиши мне /start!',
            reply_markup=today_tomorrow_keyboard()
        )
        await state.finish()  # в случае ошибки выключаем машину состояний
    # произошла ошибка
    else:
        await bot.send_message(
            message.chat.id,
            'Что-то пошло не так, попробуй еще раз позже, пожалуйста)',
            reply_markup=today_tomorrow_keyboard()
        )
        await state.finish()


@dp.message_handler(lambda message: message.content_type != types.message.ContentType.TEXT
                    or message.text not in ['На неделю', 'Понедельник', 'Вторник', 'Среда',
                                            'Четверг', 'Пятница', 'Суббота', 'Воскресенье', 'Выход'],
                    state=Timetable.weekday,
                    content_types=types.message.ContentType.ANY)
async def timetable_proceed_weekday_invalid(message: types.Message):
    """
    Функция просит пользователя выбрать вариант из списка ['На неделю', 'Понедельник', 'Вторник', 'Среда',
                                                           'Четверг', 'Пятница', 'Суббота', 'Воскресенье', 'Выход'],
    если сообщение не содержит никакую из этих строк.
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    await message.reply("Выбери вариант из предложенных, пожалуйста)")


@dp.message_handler(Text(equals=['На неделю', 'Понедельник', 'Вторник', 'Среда',
                                 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']),
                    state=Timetable.weekday)
async def timetable_return_schedule(message: types.Message, state: FSMContext):
    """
    Функция отправляет расписание на выбранный день недели.
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    async with state.proxy() as data:
        schedule = data['schedule']  # берем расписание из памяти
        data.clear()
    if message.text != 'На неделю':  # расписание на 1 день
        await bot.send_message(  # отправляем расписание
            message.chat.id,
            schedule_string(schedule[message.text].to_frame()),
            parse_mode='HTML'
        )
    else:  # расписание на неделю (на каждый из 7 дней)
        for day in ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']:
            await bot.send_message(  # отправляем расписание
                message.chat.id,
                '<b>' + day.upper() + '</b>'
                + '\n\n'
                + schedule_string(schedule[day].to_frame()),
                parse_mode='HTML'
            )
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    await bot.send_message(
        message.chat.id,
        'Чем ещё я могу помочь?',
        reply_markup=today_tomorrow_keyboard()
    )
    await state.finish()  # выключаем машину состояний


@dp.message_handler(commands=['exam'])
async def exam_initiate(message: types.Message):
    """
    Функция ловит сообщение с текстом '/exam'.
    Отправляет запрос о выборе группы и вызывает функцию get_exam_timetable().
    """
    await psg.insert_action('exam', message.chat.id)
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    await bot.send_message(
        message.chat.id,
        'Ещё не время... Но ты не забывай...'
    )
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    await bot.send_sticker(
        message.chat.id,
        'CAACAgIAAxkBAAMEXj8IxnJkYATlpAOTkJyLiXH2u0UAAvYfAAKiipYBsZcZ_su45LkYBA'
    )


# async def exam_initiate(message: types.Message):
#     """
#     Функция ловит сообщение с текстом '/exam'.
#     Отправляет запрос о выборе группы.
#     """
#     await psg.insert_action('exam', message.chat.id)
#     await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
#     keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
#     keyboard.add(*[types.KeyboardButton(name) for name in ['Моя группа', 'Другая группа', 'Выход']])
#     await bot.send_message(
#         message.chat.id,
#         'Это время настало... Выбери, расписание экзаменов'
#         ' какой группы ты хочешь посмотреть)',
#         reply_markup=keyboard
#     )
#     await Exam.choose.set()
#
#
# @dp.message_handler(lambda message: message.content_type != types.message.ContentType.TEXT
#                     or message.text not in ['Моя группа', 'Другая группа', 'Выход'],
#                     state=Exam.choose, content_types=types.message.ContentType.ANY)
# async def exam_proceed_choose_invalid(message: types.Message):
#     """
#     Функция просит пользователя выбрать вариант из списка ['Личное', 'Моя группа', 'Другая группа', 'Выход'],
#     если сообщение не содержит никакую из этих строк (+ проверка типа сообщения).
#     """
#     await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
#     await message.reply("Выбери вариант из предложенных, пожалуйста)")
#
#
# @dp.message_handler(Text(equals=['Моя группа']), state=Exam.choose)
# async def exam_return_my_group_schedule(message: types.Message, state: FSMContext):
#     timetable = await psg.send_exam_timetable(my_group=True, chat_id=message.chat.id)
#     if timetable[0]:  # если расписание было найдено
#         if timetable[1][0] is not None:
#             await bot.send_message(  # отправляем расписание
#                 message.chat.id,
#                 schedule_string(pickle.loads(timetable[1][0])),
#                 parse_mode='HTML'
#             )
#             await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
#             await bot.send_message(
#                 message.chat.id,
#                 'Чем ещё я могу помочь?',
#                 reply_markup=today_tomorrow_keyboard()
#             )
#             await state.finish()  # выключаем машину состояний
#         else:  # если расписания этой группы не нашлось
#             await bot.send_message(
#                 message.chat.id,
#                 'Извини, расписания сессии для твоей группы мы не нашли,'
#                 ' попробуй еще раз позже, пожалуйста)',
#                 reply_markup=today_tomorrow_keyboard()
#             )
#             await state.finish()
#     # если в базе данных нет этого пользователя
#     elif not timetable[0] and timetable[1] == 'empty_result':
#         await bot.send_message(
#             message.chat.id,
#             'Кажется, мы с тобой еще не знакомы... 😢\n'
#             'Cкорей пиши мне /start!',
#             reply_markup=today_tomorrow_keyboard()
#         )
#         await state.finish()  # в случае ошибки выключаем машину состояний
#     # произошла ошибка
#     else:
#         await bot.send_message(
#             message.chat.id,
#             'Что-то пошло не так, попробуй еще раз позже, пожалуйста)',
#             reply_markup=today_tomorrow_keyboard()
#         )
#         await state.finish()
#
#
# @dp.message_handler(Text(equals=['Другая группа']), state=Exam.choose)
# async def exam_proceed_another_group(message: types.Message):
#     """
#     Функция ловит сообщение с текстом 'Другая группа' и отправляет пользователю вопрос о номере группы.
#     """
#     await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
#     await Exam.another_group.set()  # изменяем состояние на Timetable.another_group
#     keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
#     keyboard.add(*[types.KeyboardButton(name) for name in ['Выход']])  # кнопка для выхода из функции
#     await bot.send_message(
#         message.chat.id,  # просим пользователя ввести номер группы
#         'Не подскажешь номер группы?\n'
#         '(В формате Б00–228 или 777, как в расписании)',
#         reply_markup=keyboard
#     )
#
#
# @dp.message_handler(lambda message: message.content_type != types.message.ContentType.TEXT,
#                     state=Exam.another_group,
#                     content_types=types.message.ContentType.ANY)
# async def exam_proceed_another_group_invalid_type(message: types.Message):
#     """
#     Функция просит ввести номер группы заново, если формат ввода неправильный.
#     """
#     await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
#     await message.reply("Пришли номер группы в верном формате, пожалуйста)")
#
#
# @dp.message_handler(state=Exam.another_group)
# async def exam_proceed_another_group(message: types.Message, state: FSMContext):
#     """
#     Функция принимает сообщение с номером группы и проверяет его. Если все хорошо, то отправляет
#     пользователю расписание. Если произошла какая-то ошибка, то функция просит пользователя
#     ввести номер группы еще раз.
#     """
#     timetable = await psg.send_exam_timetable(another_group=message.text)
#     await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
#     if timetable[0]:
#         if timetable[1][0] is not None:
#             await bot.send_message(  # отправляем расписание
#                 message.chat.id,
#                 schedule_string(pickle.loads(timetable[1][0])),
#                 parse_mode='HTML'
#             )
#             await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
#             await bot.send_message(
#                 message.chat.id,
#                 'Чем ещё я могу помочь?',
#                 reply_markup=today_tomorrow_keyboard()
#             )
#             await state.finish()  # выключаем машину состояний
#         else:  # если расписания этой группы не нашлось
#             await bot.send_message(
#                 message.chat.id,
#                 'Извини, расписания сессии для твоей группы мы не нашли,'
#                 ' попробуй еще раз позже, пожалуйста)',
#                 reply_markup=today_tomorrow_keyboard()
#             )
#             await state.finish()
#     # номера группы нет в базе / произошла какая-то ошибка, связанная с соединением
#     elif not timetable[0] and timetable[1] == 'connection_error':
#         await bot.send_message(
#             message.chat.id,
#             'Что-то не так с соединением, попробуй еще раз позже, пожалуйста)',
#             reply_markup=today_tomorrow_keyboard()
#         )
#         await state.finish()
#     # произошла какая-то ошибка другого рода
#     else:
#         keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
#         keyboard.add(*[types.KeyboardButton(name) for name in ['Выход']])
#         await bot.send_message(  # просим пользователя ввести номер группы еще раз
#             message.chat.id,
#             'К сожалению я не знаю такой группы(\n'
#             'Введи номер ещё раз, пожалуйста)',
#             reply_markup=keyboard
#         )


@dp.message_handler(commands=['custom'])
async def custom_initiate(message: types.Message):
    """
    Функция ловит сообщение с текстом '/custom'.
    Если пользователь есть в базе, то функция проверяет наличие личного расписания.
    В случае отсутствия такового в базе данных отправляет пользователю вопрос, хочет ли он
    завести такое расписание. Если личное расписание для этого пользователя есть в базе,
    фукция посылает запрос о выборе дня недели, расписание на который нужно выдать или как-то поменять.
    """
    await psg.insert_action('custom', message.chat.id)
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    await bot.send_message(
        message.chat.id,
        'Хочешь посмотреть личное расписание '
        'или что-то отредактировать в нем? '
        'В этом я всегда рад тебе помочь 😉'
    )
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    timetable = await psg.send_timetable(custom=True, chat_id=message.chat.id)
    if timetable[0] and timetable[1][0] is not None:  # если пользователь есть в базе
        await Custom.existing.set()  # изменяем состояние на Custom.existing
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(*[types.KeyboardButton(name) for name in ['Посмотреть', 'Изменить', 'Выход']])
        await bot.send_message(  # вопрос, что пользователь хочет сделать с расписанием
            message.chat.id,
            'Выбери, пожалуйста, что ты хочешь '
            'сделать с личным расписанием)',
            reply_markup=keyboard
        )
    elif timetable[0] and timetable[1][0] is None:  # если у пользователя еще нет личного расписания
        await Custom.new.set()  # изменяем состояние на Custom.new
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(*[types.KeyboardButton(name) for name in ['Давай', 'Как-нибудь потом', 'Выход']])
        await bot.send_message(
            message.chat.id,
            'У тебя пока еще нет личного расписания 😢\n'
            'Давай заведем его тебе?',
            reply_markup=keyboard
        )
    elif not timetable[0] and timetable[1] == 'empty_result':
        await bot.send_message(
            message.chat.id,
            'Кажется, мы с тобой еще не знакомы... 😢\n'
            'Cкорей пиши мне /start!',
            reply_markup=today_tomorrow_keyboard()
        )
    # произошла ошибка
    else:
        await bot.send_message(
            message.chat.id,
            'Что-то пошло не так, попробуй еще раз позже, пожалуйста)',
            reply_markup=today_tomorrow_keyboard()
        )


@dp.message_handler(lambda message: message.content_type != types.message.ContentType.TEXT
                    or message.text not in ['Давай', 'Как-нибудь потом', 'Выход'],
                    state=Custom.new,
                    content_types=types.message.ContentType.ANY)
async def custom_add_new_invalid(message: types.Message):
    """
    Функция просит пользователя выбрать вариант из списка ['Давай', 'Как-нибудь потом', 'Выход'],
    если сообщение не содержит никакую из этих строк.
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    await message.reply("Выбери вариант из предложенных, пожалуйста)")


@dp.message_handler(Text(equals=['Давай', 'Как-нибудь потом']), state=Custom.new)
async def custom_add_new(message: types.Message, state: FSMContext):
    """
    Функция принимает ответ пользователя, нужно ли ему личное расписание,
    в случае положительного ответа заводит ему такое расписание.
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    if message.text == 'Давай':  # положительный ответ
        update = await psg.create_custom_timetable(message.chat.id)
        if update[0]:
            await bot.send_message(  # все нормально обновилось
                message.chat.id,
                'Отлично, все получилось 🙃\n'
                'Теперь ты можешь использовать личное расписание! '
                'Чтобы вызвать его, напиши /custom.',
                reply_markup=today_tomorrow_keyboard()
            )
        else:  # произошла какая-то ошибка
            await bot.send_message(
                message.chat.id,
                'Что-то пошло не так, попробуй еще раз позже, пожалуйста)',
                reply_markup=today_tomorrow_keyboard()
            )
    else:  # отрицательный ответ
        await bot.send_message(
            message.chat.id,
            'Хорошо, но не забывай, что ты всегда можешь вернуться, '
            'если захочешь опробовать его в деле 😉',
            reply_markup=today_tomorrow_keyboard()
        )
    await state.finish()  # тупиковая ветка, останавливаем машину состояний


@dp.message_handler(lambda message: message.content_type != types.message.ContentType.TEXT
                    or message.text not in ['Посмотреть', 'Изменить', 'Выход'],
                    state=Custom.existing,
                    content_types=types.message.ContentType.ANY)
async def custom_choose_existing_invalid(message: types.Message):
    """
    Функция просит пользователя выбрать вариант из списка ['Посмотреть', 'Изменить', 'Выход'],
    если сообщение не содержит никакую из этих строк.
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    await message.reply("Выбери вариант из предложенных, пожалуйста)")


@dp.message_handler(Text(equals=['Посмотреть', 'Изменить']), state=Custom.existing)
async def custom_choose_existing(message: types.Message, state: FSMContext):
    """
    Функция ловит запрос пользователя о просмотре или изменении личного расписания,
    отправляет запрос о нужном дне недели.
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    await Custom.weekday.set()  # изменяем состояние на Custom.weekday
    async with state.proxy() as data:
        data['choice'] = message.text  # сохраняем ответ, понадобится дальше
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    # дни недели для тыков и кнопка для выхода (строки выбраны по размеру слов)
    keyboard.add(*[types.KeyboardButton(name) for name in ['Понедельник', 'Вторник']])
    keyboard.add(*[types.KeyboardButton(name) for name in ['Среда', 'Четверг']])
    keyboard.add(*[types.KeyboardButton(name) for name in ['Пятница', 'Суббота']])
    keyboard.add(*[types.KeyboardButton(name) for name in ['Воскресенье', 'Выход']])
    text = ('расписание на который ты хочешь посмотреть)'
            if message.text == 'Посмотреть' else
            'в расписание на который ты хочешь внести изменения)'
            )  # в зависимости от ответа выбираем строчку, которую будем отправлять
    await bot.send_message(
        message.chat.id,
        'Выбери, пожалуйста, день недели, ' + text,
        reply_markup=keyboard
    )


@dp.message_handler(lambda message: message.content_type != types.message.ContentType.TEXT
                    or message.text not in ['Понедельник', 'Вторник', 'Среда', 'Четверг',
                                            'Пятница', 'Суббота', 'Воскресенье', 'Выход'],
                    state=Custom.weekday,
                    content_types=types.message.ContentType.ANY)
async def custom_proceed_weekday_invalid(message: types.Message):
    """
    Функция просит пользователя выбрать вариант из списка ['Понедельник', 'Вторник', 'Среда', 'Четверг',
                                                           'Пятница', 'Суббота', 'Воскресенье', 'Выход'],
    если сообщение не содержит никакую из этих строк.
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    await message.reply("Выбери вариант из предложенных, пожалуйста)")


@dp.message_handler(Text(equals=['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']),
                    state=Custom.weekday)
async def custom_proceed_weekday(message: types.Message, state: FSMContext):
    """
    Функция ловит сообщение с днем недели и, в зависимости от того, что нужно пользователю,
    либо выдает ему расписание, либо посылает запрос о времени пары, расписание на которую нужно поменять.
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    timetable = await psg.send_timetable(custom=True, chat_id=message.chat.id)
    if timetable[0]:  # не произошло никакой ошибки (личное расписание точно есть, проверено ранее)
        schedule = pickle.loads(timetable[1][0])  # расписание на неделю
        await bot.send_message(  # присылаем текущее состояние расписания
            message.chat.id,
            schedule_string(schedule[message.text].to_frame()),
            parse_mode='HTML'
        )  # parse_mode - чтобы читал измененный шрифт
        async with state.proxy() as data:
            choice = data['choice']
            data.clear()
        if choice == 'Посмотреть':  # смотрим на ответ, сохраненный ранее
            await bot.send_message(  # если пользователю нужно было посмотреть расписание,
                message.chat.id,  # то это уже сделано
                'Чем ещё я могу помочь?',
                reply_markup=today_tomorrow_keyboard()
            )
            await state.finish()  # в этом случае выключаем машину состояний
        else:  # если польователю нужно было изменить расписание, то спрашиваем, какую пару он хочет поменять
            await Custom.time.set()  # изменяем состояние на Custom.time
            async with state.proxy() as data:
                data['schedule'] = schedule  # сохраняем расписание и день
                data['day'] = message.text
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            keyboard.add(*[types.KeyboardButton(name) for name in ['09:00 – 10:25', '10:45 – 12:10']])
            keyboard.add(*[types.KeyboardButton(name) for name in ['12:20 – 13:45', '13:55 – 15:20']])
            keyboard.add(*[types.KeyboardButton(name) for name in ['15:30 – 16:55', '17:05 – 18:30']])
            keyboard.add(*[types.KeyboardButton(name) for name in ['18:35 – 20:00', 'Выход']])
            await bot.send_message(
                message.chat.id,
                'Выбери, пожалуйста, время, расписание '
                'на которое ты хочешь поменять)',
                reply_markup=keyboard
            )
    else:  # если произошла какая-то ошибка
        await bot.send_message(
            message.chat.id,
            'Что-то пошло не так, попробуй еще раз позже, пожалуйста)',
            reply_markup=today_tomorrow_keyboard()
        )
        await state.finish()  # останавливаем машину состояний


@dp.message_handler(lambda message: message.content_type != types.message.ContentType.TEXT
                    or message.text not in ['09:00 – 10:25', '10:45 – 12:10', '12:20 – 13:45', '13:55 – 15:20',
                                            '15:30 – 16:55', '17:05 – 18:30', '18:35 – 20:00', 'Выход'],
                    state=Custom.time,
                    content_types=types.message.ContentType.ANY)
async def custom_proceed_time_invalid(message: types.Message):
    """
    Функция просит пользователя выбрать вариант из списка ['09:00 – 10:25', '10:45 – 12:10', '12:20 – 13:45',
                                                           '13:55 – 15:20', '15:30 – 16:55', '17:05 – 18:30',
                                                           '18:35 – 20:00', 'Выход'],
    если сообщение не содержит никакую из этих строк.
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    await message.reply("Выбери вариант из предложенных, пожалуйста)")


@dp.message_handler(Text(equals=['09:00 – 10:25', '10:45 – 12:10', '12:20 – 13:45', '13:55 – 15:20',
                                 '15:30 – 16:55', '17:05 – 18:30', '18:35 – 20:00']), state=Custom.time)
async def custom_proceed_time(message: types.Message, state: FSMContext):
    """
    Функция ловит сообщение со временем пары, расписание на которую нужно изменить,
    спрашивает у пользователя, на что нужно заменить текущее значение.
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    await Custom.edit.set()  # изменяем состояние на Custom.edit
    async with state.proxy() as data:
        data['time'] = message.text  # сохраняем время пары
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*[types.KeyboardButton(name) for name in ['Выход']])  # кнопка для выхода из функции
    await bot.send_message(
        message.chat.id,  # просим пользователя ввести номер группы
        'Введи, пожалуйста, на что ты хочешь заменить '
        'это значение) (Можешь присылать мне и смайлики)',
        reply_markup=keyboard
    )


@dp.message_handler(lambda message: message.content_type != types.message.ContentType.TEXT,
                    state=Custom.edit,
                    content_types=types.message.ContentType.ANY)
async def custom_proceed_edit_invalid_type(message: types.Message):
    """
    Функция просит ввести номер группы заново, если формат ввода неправильный.
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    await message.reply("Пришли значение в верном формате, пожалуйста)")


@dp.message_handler(state=Custom.edit)
async def custom_proceed_edit(message: types.Message, state: FSMContext):
    """
    Функция принимает строку, на которую нужно поменять текущее значение пары,
    и сохраняет новое расписание в базе данных.
    Спрашивает пользователя, хочет ли он изменить что-то еще в расписании на этот день.
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    async with state.proxy() as data:
        schedule = data['schedule']  # достаем расписание и день
        day = data['day']
        schedule[day].loc[data['time']] = message.text  # заменяем нужную пару
        data.clear()
    # сохраняем новое расписание
    update = await psg.update_custom_timetable(
        message.chat.id,
        pickle.dumps(schedule, protocol=pickle.HIGHEST_PROTOCOL)
    )
    if update[0]:
        await Custom.again.set()  # изменяем состояние на Custom.again
        async with state.proxy() as data:
            data['schedule'] = schedule  # перезаписываем расписание и день (особенности state.proxy())
            data['day'] = day
        await bot.send_message(
            message.chat.id,
            'Отлично, все получилось 🙃\n'
            'Хочешь изменить еще какое-то значение '
            'в расписании на этот день?'
        )
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(*[types.KeyboardButton(name) for name in ['Хочу', 'Не хочу', 'Выход']])
        await bot.send_message(  # посылаем запрос, хочет ли пользователь изменить
            message.chat.id,  # в расписании на этот день что-то еще
            schedule_string(schedule[day].to_frame()),
            parse_mode='HTML',
            reply_markup=keyboard
        )
    else:  # если произошла какая-то ошибка
        await bot.send_message(
            message.chat.id,
            'Что-то пошло не так, попробуй еще раз позже, пожалуйста)',
            reply_markup=today_tomorrow_keyboard()
        )
        await state.finish()


@dp.message_handler(lambda message: message.content_type != types.message.ContentType.TEXT
                    or message.text not in ['Хочу', 'Не хочу', 'Выход'],
                    content_types=types.message.ContentType.ANY, state=Custom.again)
async def custom_proceed_again_invalid(message: types.Message):
    """
    Функция просит выбрать из вариант из предложенных, если формат ввода неправильный.
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    await message.reply("Выбери вариант из предложенных, пожалуйста)")


@dp.message_handler(Text(equals=['Хочу', 'Не хочу']), state=Custom.again)
async def custom_proceed_again(message: types.Message, state: FSMContext):
    """
    Функция ловит ответ от пользователя, хочет ли он продолжить редактирование.
    Если хочет, то функция задает вопрос про время пары.
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    if message.text == 'Не хочу':  # отрицательный ответ
        await bot.send_message(
            message.chat.id,
            'Хорошо, но не забывай, что ты всегда можешь вернуться, '
            'если захочешь что-то изменить в нем 😉',
            reply_markup=today_tomorrow_keyboard()
        )
        await state.finish()  # останавливаем машину состояний
    else:  # положительный ответ
        await Custom.time.set()  # изменяем состояние на Custom.time
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(*[types.KeyboardButton(name) for name in ['09:00 – 10:25', '10:45 – 12:10']])
        keyboard.add(*[types.KeyboardButton(name) for name in ['12:20 – 13:45', '13:55 – 15:20']])
        keyboard.add(*[types.KeyboardButton(name) for name in ['15:30 – 16:55', '17:05 – 18:30']])
        keyboard.add(*[types.KeyboardButton(name) for name in ['18:35 – 20:00', 'Выход']])
        await bot.send_message(
            message.chat.id,
            'Выбери, пожалуйста, время, расписание '
            'на которое ты хочешь поменять)',
            reply_markup=keyboard
        )


@dp.message_handler(commands='plot')
async def plot(message: types.Message):
    """
    Функция ловит сообщение с текстом '/plot' и отправляет сообщение пользователю с просьбой
    указать название графика.
    """
    await psg.insert_action('plot', message.chat.id)
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    await bot.send_message(message.chat.id, 'Снова лабки делаешь?) Ох уж эти графики!...'
                                            ' Сейчас быстренько всё построю, только тебе придётся'
                                            ' ответить на пару вопросов'
                                            '😉 И не засиживайся, ложись спать)')
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*[types.KeyboardButton(name) for name in ['Без названия', 'Выход']])
    await bot.send_message(
        message.chat.id,
        'Как мы назовём график?\n'
        'Если не хочешь давать ему название, '
        'то нажми на кнопку ниже 😉',
        reply_markup=keyboard
    )
    await Plots.title_state.set()


@dp.message_handler(lambda message: message.content_type == types.message.ContentType.TEXT, state=Plots.title_state)
async def title(message: types.Message, state: FSMContext):
    """
    Функция записывает название графика присланное пользователем в data storage и отправляет
    сообщение пользователю с просьбой указать нужно ли строить прямую по мнк.
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    async with state.proxy() as data:
        if message.text == 'Без названия':
            data['title'] = ''
        else:
            data['title'] = message.text
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*[types.KeyboardButton(name) for name in ['✅', '❌', 'Выход']])
    await bot.send_message(
        message.chat.id,
        'Прямую по МНК строим?',
        reply_markup=keyboard
    )
    await Plots.mnk_state.set()


# In case some bad input
@dp.message_handler(state=Plots.title_state, content_types=types.message.ContentType.ANY)
async def title_bad_input(message: types.Message):
    """
    В случае неккоректного названия графика, функция просит пользователя повторить ввод.
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*[types.KeyboardButton(name) for name in ['Без названия']])
    await bot.send_message(
        message.chat.id,
        'Я тебя не понял... Напиши ещё раз название графика.\n'
        'Если не хочешь давать ему название, '
        'то нажми кнопку ниже 😉',
        reply_markup=keyboard
    )


@dp.message_handler(Text(equals=['✅', '❌']), state=Plots.mnk_state)
async def mnk(message: types.Message, state: FSMContext):
    """
    Функция ловит сообщение с одним из символов ['✅', '❌'] и в зависимости от ответа
    выставляет error_bars_state или plot_state.
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    if message.text == '✅':
        async with state.proxy() as data:
            data['mnk'] = True
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(*[types.KeyboardButton(name) for name in ['0.0/0.0']])
        await bot.send_message(
            message.chat.id,
            'Укажи погрешности по осям х и y в '
            'формате "2.51/2.51", '
            'если кресты не нужны, то нажми на кнопку ниже.',
            reply_markup=keyboard
        )
        await Plots.error_bars_state.set()
    else:
        async with state.proxy() as data:
            data['mnk'] = False
            data['errors'] = [0.0, 0.0]
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(*[types.KeyboardButton(name) for name in ['Выход']])
        with open('files/Example.xlsx', 'rb') as example:
            await bot.send_document(message.chat.id, example)
        await bot.send_message(
            message.chat.id,
            'Пришли .xlsx файл с данными как в example.xlsx, и всё будет готово.',
            reply_markup=keyboard
        )
        await Plots.plot_state.set()


# In case of bad input
@dp.message_handler(state=Plots.mnk_state, content_types=types.message.ContentType.ANY)
async def mnk_bad_input(message: types.Message):
    """
    В случае если сообщение не содержит ['✅', '❌'], функция просит пользователя повторить ввод.
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*[types.KeyboardButton(name) for name in ['✅', '❌', 'Выход']])
    await bot.send_message(
        message.chat.id,
        'Извини, повтори ещё раз... Прямую по МНК строим?',
        reply_markup=keyboard
    )


@dp.message_handler(lambda message: message.content_type == types.message.ContentType.TEXT,
                    state=Plots.error_bars_state)
async def error_bars(message: types.Message, state: FSMContext):
    """
    Функция ловит сообщение с размерами крестов погрешностей и просит прислать excel файл, по которому будет
    строиться график.
    """
    try:
        await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
        async with state.proxy() as data:
            data['errors'] = list(map(float, message.text.split('/')))
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(*[types.KeyboardButton(name) for name in ['Выход']])
        with open('files/Example.xlsx', 'rb') as expl:
            await bot.send_document(message.chat.id, expl)
        await bot.send_message(
            message.chat.id,
            'Пришли .xlsx файл с данными как в example.xlsx и всё будет готово.',
            reply_markup=keyboard
        )
        await Plots.plot_state.set()
    except Exception as e:
        print(e)
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(*[types.KeyboardButton(name) for name in ['0.0/0.0']])
        await bot.send_message(
            message.chat.id,
            'Не могу распознать формат данных( Давай ещё раз. '
            'Пришли данные для крестов погрешностей по осям х и y в '
            'формате "2.51/2.51", если кресты не нужны, то'
            ' нажми на кнопку ниже.',
            reply_markup=keyboard
        )


# In case of bad input
@dp.message_handler(state=Plots.error_bars_state, content_types=types.message.ContentType.ANY)
async def eror_bars_bad_input(message: types.Message):
    """
    В случае если сообщение не содержит погрешности в формате "2.51/2.51",
    функция просит пользователя повторить ввод.
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*[types.KeyboardButton(name) for name in ['0.0/0.0']])
    await bot.send_message(
        message.chat.id,
        'Ты прислал что-то не то( Давай ещё раз. '
        'Пришли данные для крестов погрешностей по осям х и y в '
        'формате "2.51/2.51", если кресты не нужны, то'
        ' нажми на кнопку ниже.',
        reply_markup=keyboard
    )


@dp.message_handler(content_types=types.message.ContentTypes.DOCUMENT, state=Plots.plot_state)
async def plot(message: types.Message, state: FSMContext):
    """
    Функция ловит сообщение с Excel-файлом, строит график по данным внутри него и присылает сообщение пользователю с
    коэффициентами прямых (если надо) и pdf и png файлы с изображением графика.
    """
    try:
        await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
        file_id = message.document.file_id
        file = await bot.get_file(file_id)
        await bot.download_file(file.file_path, 'file.xlsx')
        async with state.proxy() as data:
            title = data['title']
            errors = data['errors']
            mnk = data['mnk']
            data.clear()
        coef = math_part.plots_drawer('file.xlsx', title, errors[0], errors[1], mnk)
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(*[types.KeyboardButton(name) for name in ['На сегодня', 'На завтра']])
        await bot.send_message(
            message.chat.id,
            'Принимай работу!)',
            reply_markup=keyboard
        )
        with open('plot.png', 'rb') as photo:
            await bot.send_chat_action(message.chat.id, 'upload_document')  # Отображение "upload document"
            await bot.send_document(
                message.chat.id,
                photo
            )
        if mnk:
            for i in range(len(coef)):
                a, b, d_a, d_b = coef[i]
                await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
                await bot.send_message(
                    message.chat.id,
                    f"Коэффициенты {i + 1}-ой прямой:\n"
                    f" a = {a} +- {d_a}\n"
                    f" b = {b} +- {d_b}"
                )
        with open('plot.pdf', 'rb') as photo:
            await bot.send_chat_action(message.chat.id, 'upload_document')  # Отображение "upload document"
            await bot.send_document(message.chat.id, photo)
        os.remove('plot.pdf')
        os.remove('plot.png')
        math_part.BOT_PLOT = False
        os.remove('file.xlsx')
        await state.finish()
    except Exception as e:
        os.remove('file.xlsx')
        print(e)
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(*[types.KeyboardButton(name) for name in ['Выход']])
        await bot.send_message(
            message.chat.id,
            'Ты точно прислал .xlsx файл как в примере? Давай ещё раз!',
            reply_markup=keyboard
        )


# In case of bad input
@dp.message_handler(content_types=types.message.ContentType.ANY, state=Plots.plot_state)
async def plot_bad_input(message: types.Message):
    """
    В случае некорректного сообщения функция просит пользователя прислать excel-файл ещё раз.
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*[types.KeyboardButton(name) for name in ['Выход']])
    await bot.send_message(
        message.chat.id,
        'Ты точно прислал .xlsx файл? Давай ещё раз! '
        'Пришли .xlsx файл с данными, и всё будет готово',
        reply_markup=keyboard
    )


@dp.message_handler(commands=['stat'])
async def stat_start(message: types.Message):
    """
    Функция присылает сообщение с просьбой выбрать нужную функцию
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*[types.KeyboardButton(name) for name in ['Frequency', 'Unique']])
    await bot.send_message(
        message.chat.id,
        'Выбери нужную функцию',
        reply_markup=keyboard
    )
    await Stat.choice.set()


@dp.message_handler(Text(equals='Unique'), state=Stat.choice)
async def stat_start(message: types.Message):
    """
    Функция присылает сообщение с вопросом о том за какой период вермени нужна статистика
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*[types.KeyboardButton(name) for name in ['За сегодня', 'За вчера', 'За неделю']])
    await bot.send_message(
        message.chat.id,
        'За какой день показать колличество уникальных пользователей',
        reply_markup=keyboard
    )
    await Stat.unique.set()


@dp.message_handler(state=Stat.unique)
async def stat_start(message: types.Message, state: FSMContext):
    """
    Функция присылает сообщением с числом уникальных пользователей за нужный период времени
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    number = stat.uniqe_users(message.text)
    keyboard = today_tomorrow_keyboard()
    await bot.send_message(
        message.chat.id,
        f'В этот день было {number} уникальных пользователей',
        reply_markup=keyboard
    )
    await state.finish()


@dp.message_handler(Text(equals='Frequency'), state=Stat.choice)
async def stat_start(message: types.Message, state: FSMContext):
    """
    Функция присылает сообщением с частотами использования функций за последнюю неделю
    """
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    await bot.send_message(
        message.chat.id,
        'Частота использования функций за последнюю неделю:'
    )
    freq = stat.frequency_of_use()
    text = '\n'.join(freq)
    keyboard = today_tomorrow_keyboard()
    await bot.send_chat_action(message.chat.id, 'typing')  # Отображение "typing"
    await bot.send_message(
        message.chat.id,
        text,
        reply_markup=keyboard
    )
    await state.finish()


@dp.message_handler(commands=['mail'])
async def mailing_start(message):
    pers_id = message.chat.id
    admins = [int(os.environ['ADMIN_1']), int(os.environ['ADMIN_2'])]
    await bot.send_chat_action(message.chat.id, 'typing')
    if pers_id in admins:
        await bot.send_message(message.chat.id, 'Пришли мне сообщение текст сообщения')
    else:
        await bot.send_message(message.chat.id, 'Боюсь, я не совсем понимаю, о чём ты. \n'
                                                'Напиши /help, чтобы узнать, что я умею.\n')
    await Mailing.mailing.set()


@dp.message_handler(state=Mailing.mailing)
async def mailing(message: types.Message, state: FSMContext):
    users = stat.get_user_list()
    await state.finish()
    for user in users:
        try:
            await bot.send_message(user, message.text)
        except BotBlocked:
            print(f'Bot was blocked by user with chat_id = {user}')
        except TelegramAPIError:
            print(f'Smth went wrong with user chat_id = {user}')
executor.start_polling(dp, skip_updates=True)
