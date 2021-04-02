import telebot
import requests
import config
import utils
import re
import time
import datetime
import json

bot = telebot.TeleBot(config.bot_token)
rate_database = {'last_timestamp': 0, 'rates': []}
base_currency = 'EUR'


"""
    it requests data from exchange rate service and puts the data in the rate_database
"""
def _pull_rate_list():
    response = requests.get('{}/{}'.format(config.api_url, 'latest'),
                            params={'access_key': config.access_key, 'base': base_currency})
    json_data = response.json()
    if 'error' in json_data:
        return 0
    else:
        rate_database['last_timestamp'] = int(time.time())
        rate_database['rates'] = json_data['rates']
        for currency, value in rate_database['rates'].items():
            rate_database['rates'][currency] = float("{:.2f}".format(value))
        return 1

"""
    /list
    it requests data from the exchange rate service and returns data to a client
    it also checks if last update time is greater than refresh_interval:
        if it is time to update local database, then do request
        otherwise, return the cached data

    I would be nice if a client had abillity to pass a list of symbols (/list USD UAH EUR)
                                            and the response list will have only three rates
"""
@bot.message_handler(commands=['list', 'lst'])
def get_list(message):
    diff = int(time.time()) - rate_database['last_timestamp']
    if diff > config.update_interval:
        # update local database
        if _pull_rate_list():
            currencies = []
            for currency, value in rate_database['rates'].items():
                currencies.append('{} : {}'.format(currency, value))
            bot.send_message(message.chat.id, '\n'.join(currencies))
        else:
            bot.send_message(message.chat.id, 'I can\'t to update local database')
    else:
        rates_list = []
        for currency, value in rate_database['rates'].items():
            rates_list.append('{} : {}'.format(currency, value))
        bot.send_message(message.chat.id, '\n'.join(rates_list))

"""
    /exchange amount CURRENCY
    exchange some amount of base currency to CURRENCY
    base currency is always EUR due to subscription plan restrictions on the web service
"""
@bot.message_handler(commands=['exchange'])
def exchange(message):
    # /exchange 10 CAD - convert my base_currency to CAD
    params = message.text.split('/exchange')[1].strip()
    # base currency to the second
    if re.fullmatch(r'^[0-9.]+ +[a-zA-Z]{3}$', params):
        params = params.split()
        params = {'number': params[0], 'target_currency': params[1]}
        number = utils.is_valid_number(params['number'])
        if not number:
            bot.send_message(message.chat.id, 'invalid number {}'.format(params['number']))
        elif params['target_currency'] not in rate_database['rates']:
            bot.send_message(message.chat.id,
                             'target currency {} is not present in my database. Try to /list to update my database'.format(
                                 params['target_currency']))
        else:
            converted = '{:.2f}'.format(number * rate_database['rates'][params['target_currency']])
            bot.send_message(message.chat.id,
                             '{} {} to {} is {}'.format(number, base_currency, params['target_currency'], converted))
    else:
        bot.send_message(message.chat.id, 'invalid request')

"""
    /history CURRENCY
    creates chart of exchange rate between base_currency and CURRENCY
    chart is created using service quickchart.io/

    it would be nice to pass a few symbols and specify day period
    /history SYMBOL1 SYMBOL2 SYMBOL3 10 (means days)
"""
@bot.message_handler(commands=['history'])
def history(message):
    # /history currency - draws graph chart to base currency and target currency for last 7 days
    # generate a list of 7 days start day is today
    numdays = 7
    base = datetime.datetime.today()
    date_list = []
    for day in range(numdays):
        previous_day = base - datetime.timedelta(days=day)
        date_list.append(previous_day.strftime('%Y-%m-%d'))
    date_list.reverse()
    symbol = message.text.split('/history')[1].strip()
    if re.fullmatch(r'^[a-zA-Z]{3}$', symbol):
        if symbol not in rate_database['rates']:
            bot.send_message(message.chat.id,
                             'target currency {} is present in my database.')
            return
        _history = {}
        for date in date_list:
            response = requests.get('{}/{}'.format(config.api_url, date),
                                    params={'access_key': config.access_key, 'symbols': symbol})
            json_data = response.json()
            if 'error' in json_data:
                bot.send_message(message.chat.id, 'error from web service is {}'.format(json_data['error']['code']))
                return
            _history[date] = float("{:.2f}".format(json_data['rates'][symbol]))
        days = []
        rates = []
        for day, rate in _history.items():
            days.append(day)
            rates.append(rate)
        url = get_graph(days, rates, symbol)
        if not url:
            bot.send_message(message.chat.id, 'can\'t draw chart for you')
        bot.send_message(message.chat.id, url)
    else:
        bot.send_message(message.chat.id, 'invalid request')


def get_graph(days, rates, symbol):
    quickchart_url = 'https://quickchart.io/chart/create'
    post_data = {
        'chart': {
            'type': 'bar',
            'data': {
                'labels': days,
                'datasets': [
                    {
                        'label': '{} to {}'.format(base_currency, symbol),
                        'data': rates,
                        'backgroundColor': 'rgba(54, 162, 235, 0.5)',
                        'borderColor': 'rgb(54, 162, 235)',
                        'borderWidth': 1,
                    }
                ]
            },
            'options': {
                'plugins': {
                    'datalabels': {
                        'anchor': 'end',
                        'align': 'top',
                        'color': '#fff',
                        'backgroundColor': 'rgba(34, 139, 34, 0.6)',
                        'borderColor': 'rgba(34, 139, 34, 1.0)',
                        'borderWidth': 1,
                        'borderRadius': 5,
                        'formatter': '(value) => {return value + \'k\'};'
                    }
                }
            }
        }
    }
    response = requests.post(quickchart_url, json=post_data)
    if response.status_code != 200:
        return 0
    else:
        chart_response = json.loads(response.text)
        if chart_response['success']:
            return chart_response['url']


_pull_rate_list()
bot.polling()
