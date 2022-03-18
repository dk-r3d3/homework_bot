import logging
from logging.handlers import RotatingFileHandler
import sys
import requests
import os
from dotenv import load_dotenv
import time
import telegram
from requests import RequestException

load_dotenv()

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
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    logger.info(f'Отправлено сообщение: {message}')


def get_api_answer(current_timestamp):
    """Запрос к эндпоинту для получения данных домашних работ."""
    timestamp = current_timestamp
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
        if homework_statuses.status_code != 200:
            logging.error(f'Эндпоинт на несуществующую страницу {ENDPOINT}.')
            raise Exception('Неуспешный запрос!')
    except RequestException as error:
        logging.exception(f'Ошибка при запросе основного API: {error}')
        raise RequestException('Ошибка ответа от сервера')
    return homework_statuses.json()


def check_response(response):
    """Проверка, что в полученном API eсть ключ 'homeworks'."""
    if 'homeworks' in response:
        homeworks = response.get('homeworks')
        logger.info(f'Получен список ДЗ: {homeworks}')
    if not isinstance(response['homeworks'], list):
        raise TypeError('Домашняя работа нет представлена списком.')
    if 'homeworks' not in response:
        logging.error('Отсутствует ключ "homeworks".')
        raise KeyError('Ключ "homeworks" не найден.')
    return homeworks


def parse_status(homework):
    """Информация о конкретной домашней работе."""
    homework_name = homework.get('homework_name')
    if homework_name is None:
        raise KeyError('Отсутствует ключ в словаре!')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_STATUSES.keys():
        logger.error(f'{homework_status} - неизвестный статус.')
        raise KeyError('Неизвестный статус ДЗ!')
    logger.info(f'Получено ДЗ {homework_name} со статусом {homework_status}.')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности переменных окружения."""
    if PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID is not None:
        return True
    else:
        return False


def main():
    """Основная логика работы бота."""
    logger.info('Бот запущен!')
    try:
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
    except telegram.error.InvalidToken:
        logging.critical('Ошибка в бязательных переменных окружения!')
        raise Exception('Неверный токен!')
    current_timestamp = 0

    if check_tokens() is False:
        logging.error('Отсутствует токен!')

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            message_hom = parse_status(homework[0])
            send_message(bot, message_hom)
            current_timestamp = response['current_date']
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.exception(f'Сбой в работе программы: {error}')
            send_message(bot, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Работа бота завершена.')
        sys.exit(0)
