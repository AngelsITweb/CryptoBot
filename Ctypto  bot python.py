import telebot
from telebot import *
from telebot import types
import sqlite3
from aiocryptopay import AioCryptoPay, Networks
import asyncio
import requests

crypto = AioCryptoPay(token='8714:AAUUr4JvyOlgJwk1NW0pWm6q83Y9CvYsgsL', network=Networks.TEST_NET)
bot = telebot.TeleBot('6030011051:AAGJ-iNvagpkwCIEXqBDn9ZH-RcYy3lHDtQ')

conn = sqlite3.connect('yourdatabase.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS profiles 
               (id INTEGER PRIMARY KEY, phone VARCHAR(15), first_name TEXT, username TEXT, balance INTEGER DEFAULT 0)''')
conn.commit()

def dollarexchangerate():
    response = requests.get("https://open.er-api.com/v6/latest/USD")
    
    if response.status_code == 200:
        data = response.json()
        
        usd_to_rub = data['rates']['RUB']
    
    return usd_to_rub

dollarexchangerate = dollarexchangerate()

def format_with_commas(number):
    number_str = str(number)
    parts = number_str.split('.')
    whole_part = "{:,}".format(int(parts[0])).replace(',', '.')
    formatted_number = whole_part if len(parts) == 1 else f"{whole_part}.{parts[1]}"
    
    return formatted_number

zakazmarkup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
profilebutton = telebot.types.KeyboardButton("🖥 Профиль")
zakazmarkup.add(profilebutton)

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Ваш текст",reply_markup=zakazmarkup)

@bot.message_handler(func=lambda message: message.text == '🖥 Профиль')
def profileokda(message):  
    user_id = message.chat.id
    cursor.execute("SELECT * FROM profiles WHERE id=?", (message.chat.id,))
    profile = cursor.fetchone()
    popolneniebutton = types.InlineKeyboardButton("💰Пополнить", callback_data='popolnitbalans')
    popolneniemarkup = types.InlineKeyboardMarkup()
    popolneniemarkup.add(popolneniebutton)
    if not profile:
            startmarkup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            sendnumber = telebot.types.KeyboardButton("Отправить номер телефона📞", request_contact=True)
            startmarkup.add(sendnumber)
            bot.send_message(message.chat.id, "Пожалуйста, отправьте свой номер телефона для регестрации.", reply_markup=startmarkup)
            return
    if profile:
        cursor.execute("SELECT id, balance FROM profiles WHERE id = ?", (user_id,))
        result = cursor.fetchone()
    if result:
            id, balance = result
            formatted_balance = format_with_commas(balance)
            bot.send_message(message.chat.id, f"👤 <b>Ваш профиль:</b>\n➖➖➖➖➖➖➖➖➖➖\n🆔: <code>{id}</code>\n💰Баланс: <code>{formatted_balance}₽</code>\n➖➖➖➖➖➖➖➖➖➖", reply_markup=popolneniemarkup, parse_mode='HTML')
    return

@bot.callback_query_handler(func=lambda call: call.data == 'popolnitbalans')
def popolnitbalans(call):
    cryptobotusdtbutton = types.InlineKeyboardButton("⚜️ CryptoBot (USDT)", callback_data='cryptobotusdt')
    platezkamarkup = types.InlineKeyboardMarkup()
    platezkamarkup.add(cryptobotusdtbutton)
    bot.send_message(call.message.chat.id,"💰 <b>Выберите способ пополнения</b>", reply_markup=platezkamarkup, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data == 'cryptobotusdt')
def cryptobotusdt(call):
    currency = "USDT"
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, f"⚜️ <a href='https://t.me/CryptoBot?start=r-302453'>CryptoBot</a>\n\n— Минимум: <b>50 ₽</b>\n\n💸 <b>Введите сумму пополнения в рублях</b>", parse_mode='HTML', disable_web_page_preview=True)
    bot.register_next_step_handler(call.message, process_amount_and_curency, currency)
    
data_pay = {}
    
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

MINIMUM_AMOUNT = 50.0

def process_amount_and_curency(message, currency):
    amount_input = int(message.text)
    amount = loop.run_until_complete(crypto.get_amount_by_fiat(summ=amount_input, asset='USDT', target='RUB'))
    print(amount)
    if amount_input < MINIMUM_AMOUNT:
            bot.send_message(message.chat.id, f"Минимальная сумма для пополнения - {MINIMUM_AMOUNT}₽")
            return cryptobotusdt
    
    invoice = loop.run_until_complete(crypto.create_invoice(asset=currency, amount=amount))
    
    data_pay['invoice_id'] = invoice.invoice_id
    
    oplatamarkup = types.InlineKeyboardMarkup()
    paybutton = types.InlineKeyboardButton("Оплатить счёт", url=invoice.pay_url)
    checkbutton = types.InlineKeyboardButton("Проверить оплату", callback_data=f"get_payment_status_{invoice.invoice_id}")
    oplatamarkup.add(paybutton)
    oplatamarkup.add(checkbutton)

    message_sent = bot.send_message(message.chat.id, "Счёт создан\n\nДля оплаты нажмите кнопку 'Оплатить счёт'", reply_markup=oplatamarkup)

    data_pay['message_id'] = message_sent.message_id

@bot.callback_query_handler(func=lambda call: call.data.startswith('get_payment_status_'))
def handle_payment_status_check(call):
    cursor.execute("SELECT balance FROM profiles WHERE id=?", (call.message.chat.id,))
    result = cursor.fetchone()
    invoice_id = data_pay.get('invoice_id')
    invoices = loop.run_until_complete(crypto.get_invoices(invoice_ids=[invoice_id]))
    if invoices:
        invoice = invoices[0]
        amount = invoice.amount
        if invoice.status == 'active':
            bot.send_message(call.message.chat.id, "Оплата не обнаружена, попробуйте снова через некоторое время.")
        elif invoice.status == 'paid':
            if result is not None:
                balance = int(amount * dollarexchangerate)
                new_balance = result[0] + balance
                formatted_balance = format_with_commas(balance)
                cursor.execute("UPDATE profiles SET balance=? WHERE id=?", (new_balance, call.message.chat.id))
                conn.commit()
                bot.send_message(call.message.chat.id, f"Счёт успешно оплачен, вам было зачисленно {formatted_balance}₽ на баланс")
                data_pay.pop('invoice_id', None)
                message_id = data_pay.get('message_id')
                bot.delete_message(call.message.chat.id, message_id)
                data_pay.pop('message_id', None)
    return

@bot.message_handler(content_types=['contact'])
def handle_contact(message):
    contact = message.contact
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    username = message.from_user.username
    phone = contact.phone_number

    insert_query = "INSERT INTO profiles (id, phone, first_name, username) VALUES (?, ?, ?, ?)"
    values = (user_id, contact.phone_number, first_name, username)

    cursor.execute(insert_query, values)
    conn.commit()
    
    bot.send_message(user_id, "Вы успешно зарегестрировались, для использования бота используйте кнопки ниже", reply_markup=zakazmarkup)

bot.polling(non_stop=True)