import os
import sys
import time
import logging

import requests
import telegram
from dotenv import load_dotenv

from exceptions import (
    EndpointException, ListErrorException,
    StatuseErrorException
)
from logging.handlers import RotatingFileHandler

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.',
}


def send_message(bot, message):
    """Отправить сообщение в чат."""
    try:
        logging.info(f'Отправлено сообщение: {message}')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception:
        raise Exception('Не удалось отправить сообщение.')


def get_api_answer(current_timestamp):
    """Запрос к эндпоинту для получения данных домашних работ."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
        if homework_statuses.status_code != 200:
            raise Exception('Неуспешный запрос!')
    except Exception as error:
        logging.exception(f'Ошибка при запросе основного API: {error}')
        raise EndpointException('Ошибка ответа от сервера')
    return homework_statuses.json()


def check_response(response):
    """Проверка, что в полученном API eсть ключ 'homeworks'."""
    if not isinstance(response, dict):
        logging.error('response возвращет не словарь')
        raise TypeError('response - не словарь.Ошибка!')
    if 'homeworks' not in response:
        logging.error('Отсутствует ключ "homeworks" в response.')
        raise KeyError('Ключ "homeworks" не найден.')
    if not isinstance(response['homeworks'], list):
        logging.error('Домашняя работа не представлена списком.')
        raise ListErrorException('Домашняя работа не представлена списком.')
    if 'current_date' not in response:
        logging.error('Отсутствует ключ "current_date" в response.')
        raise KeyError('Ключ "current_date" не найден.')
    homeworks = response.get('homeworks')
    logging.info(f'Получен список ДЗ: {homeworks}')
    logging.info(f'Ключи в response: {response.keys()}')
    return homeworks


def parse_status(homework):
    """Информация о конкретной домашней работе."""
    homework_name = homework.get('homework_name')
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ в словаре!')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_STATUSES:
        logging.error(f'{homework_status} - неизвестный статус.')
        raise StatuseErrorException('Неизвестный статус ДЗ!')
    logging.info(f'Получено ДЗ {homework_name} со статусом {homework_status}.')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности переменных окружения."""
    tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    return all(tokens)


def main():
    """Основная логика работы бота."""
    logger.info('Бот запущен!')
    last_message = None
    try:
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
    except telegram.error.InvalidToken:
        logger.critical('Ошибка в обязательных переменных окружения!')
        raise Exception('Неверный токен!')
    current_timestamp = int(time.time())
    if not check_tokens():
        logger.error('Проверь обязательные переменные окружения!')

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            logger.info(f'homework: {homework}')
            if len(homework) > 0:
                message_hom = parse_status(homework[0])
                if last_message != message_hom:
                    last_message = message_hom
                    send_message(bot, message_hom)
            current_timestamp = response['current_date']
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.exception(f'Сбой в работе программы: {error}')
            if last_message != message:
                last_message = message
                send_message(bot, message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    try:
        logging.basicConfig(
            level=logging.DEBUG,
            filename='program.log',
            format='%(asctime)s, %(levelname)s, %(message)s.',
            encoding='UTF-8',
            filemode='w'
        )
        logger = logging.getLogger(__name__)
        handler = RotatingFileHandler(
            'my_logger.log',
            maxBytes=50000000,
            backupCount=5,
            encoding='UTF-8'
        )
        logger.addHandler(handler)
        main()
    except KeyboardInterrupt:
        print('Работа бота завершена.')
        sys.exit(0)
