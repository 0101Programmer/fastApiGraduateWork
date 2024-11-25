import datetime
import sqlite3
import threading
import time
from ast import literal_eval
from PIL import Image
from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import pandas as pd

app = FastAPI()

outer_scope_connection = sqlite3.connect('my_fastapi_database.db')
outer_scope_cursor = outer_scope_connection.cursor()
outer_scope_cursor.execute('''
CREATE TABLE IF NOT EXISTS Clients(
id INTEGER PRIMARY KEY,
last_name TEXT NOT NULL,
first_name TEXT NOT NULL,
patronymic TEXT,
email TEXT NOT NULL,
password INTEGER NOT NULL,
date_of_birthday TEXT NOT NULL,
is_authorized INTEGER NOT NULL
);
''')

outer_scope_cursor.execute("CREATE INDEX IF NOT EXISTS idx_email ON Clients (email)")
outer_scope_connection.commit()
outer_scope_connection.close()

outer_scope_connection = sqlite3.connect('my_fastapi_database.db')
outer_scope_cursor = outer_scope_connection.cursor()

# outer_scope_cursor.execute('DROP TABLE ClientsBooking')

outer_scope_cursor.execute('''
CREATE TABLE IF NOT EXISTS ClientsBooking(
id INTEGER PRIMARY KEY,
client_email TEXT NOT NULL,
hotel_name TEXT NOT NULL,
date_in TEXT NOT NULL,
date_out TEXT NOT NULL,
total_days INTEGER NOT NULL,
price_per_day INTEGER NOT NULL,
is_confirm INTEGER NOT NULL,
hotel_address TEXT NOT NULL
);
''')

outer_scope_connection.commit()
outer_scope_connection.close()

templates = Jinja2Templates(directory='templates')
app.mount("/static", StaticFiles(directory="static"), name="static")


def check_auth():
    connection = sqlite3.connect('my_fastapi_database.db')
    cursor = connection.cursor()
    cursor.execute("SELECT is_authorized FROM Clients WHERE is_authorized = ?", (1,))
    result = cursor.fetchone()
    connection.close()
    if result:
        return True
    else:
        return False


def check_confirmed():
    time.sleep(60)
    connection = sqlite3.connect('my_fastapi_database.db')
    cursor = connection.cursor()
    cursor.execute("DELETE FROM ClientsBooking WHERE is_confirm = ?", (False,))
    connection.commit()
    connection.close()


@app.get('/')
async def home(request: Request):
    home_p = True
    if check_auth():
        client = True
        return templates.TemplateResponse('home.html', {
            'request': request,
            'client': client,
            'home_p': home_p,
        })
    return templates.TemplateResponse('home.html', {
        'request': request,
        'home_p': home_p,
    })


@app.get('/moscow')
async def moscow_page(request: Request):
    return templates.TemplateResponse('moscow.html', {
        'request': request,
    })


@app.get('/beta')
async def get_beta_hotel_page(request: Request):
    main_images_paths_list = []
    mini_images_paths_list = []
    captions_list = ['Гостинная', 'Ванная', 'Кухня']
    if len(main_images_paths_list) <= 0 or len(mini_images_paths_list) <= 0:
        for i in range(3):
            img_path = f'static/moscow/beta/b{i + 1}.jpg'
            mini_img_path = f'static/moscow/beta/b{i + 1}_mini.jpg'
            img_for_resize = Image.open(img_path)
            resized_main_img = img_for_resize.resize((1024, 768), Image.Resampling.LANCZOS)
            resized_mini_img = img_for_resize.resize((200, 150), Image.Resampling.LANCZOS)
            resized_main_img.save(img_path)
            resized_mini_img.save(mini_img_path)
            main_images_paths_list.append(img_path)
            mini_images_paths_list.append(mini_img_path)

    zipped = zip(main_images_paths_list, mini_images_paths_list, captions_list)

    if check_auth():
        client = True

        connection = sqlite3.connect('my_fastapi_database.db')
        cursor = connection.cursor()
        cursor.execute("SELECT date_in, date_out FROM ClientsBooking WHERE date_in IS NOT NULL AND date_out IS NOT "
                       "NULL AND hotel_name = ?",
                       ('Измайлово Бета',))
        booked_dates = cursor.fetchall()
        connection.close()
        dt_range = []
        for i in booked_dates:
            i_dt_range = pd.date_range(start=i[0], end=i[1])
            dt_range.append(i_dt_range)

        min_available_booking_date_in = datetime.date.today() + datetime.timedelta(days=8)

        if len(dt_range) != 0:
            for i in dt_range:
                flag = True
                while flag:
                    if str(min_available_booking_date_in) in i or str(
                            min_available_booking_date_in + datetime.timedelta(days=1)) in i:
                        min_available_booking_date_in += datetime.timedelta(days=1)
                        continue
                    else:
                        break

        connection = sqlite3.connect('my_fastapi_database.db')
        cursor = connection.cursor()
        cursor.execute("SELECT date_in, date_out FROM ClientsBooking WHERE hotel_name = ?", ('Измайлово Бета',))
        not_available_booking_dates = cursor.fetchall()
        cursor.execute("SELECT client_email FROM ClientsBooking WHERE is_confirm = ?", (False,))
        not_confirmed_order = cursor.fetchone()
        connection.close()
        connection = sqlite3.connect('my_fastapi_database.db')
        cursor = connection.cursor()
        cursor.execute("SELECT email FROM Clients WHERE is_authorized = ?", (1,))
        client_email = cursor.fetchone()[0]

        return templates.TemplateResponse('moscow_hotels/beta.html', {
            'request': request,
            'client': client,
            'client_email': client_email,
            'min_available_booking_date_in': min_available_booking_date_in,
            'not_available_booking_dates': not_available_booking_dates,
            'not_confirmed_order': not_confirmed_order,
            'zipped': zipped,
        })

    return templates.TemplateResponse('moscow_hotels/beta.html', {
        'request': request,
        'zipped': zipped,
    })


@app.post('/beta')
async def post_beta_hotel_page(request: Request, booking_date_first: str = Form(), booking_date_second: str = Form(),
                               hotel_name: str = Form(),
                               client_email_from_page: str = Form(),
                               one_day_price: int = Form(),
                               hotel_address: str = Form()):
    if check_auth():
        client = True
        connection = sqlite3.connect('my_fastapi_database.db')
        cursor = connection.cursor()
        cursor.execute("SELECT email FROM Clients WHERE is_authorized = ?", (1,))
        client_email = cursor.fetchone()[0]
        connection.close()
        connection = sqlite3.connect('my_fastapi_database.db')
        cursor = connection.cursor()
        booking_date_first_split = booking_date_first.split('-')
        booking_date_first_nulls_off = []
        for _ in booking_date_first_split:
            booking_date_first_nulls_off.append(int(_.lstrip('0')))
        booking_date_first_nulls_off = str(booking_date_first_nulls_off)
        if str(datetime.date.today()) > booking_date_first or (
                datetime.date(*literal_eval(booking_date_first_nulls_off)) - datetime.timedelta(
            days=7)) <= datetime.date.today():
            connection.close()
            message = 'Извините, но бронирование возможно только за 7 дней до заселения'
            return templates.TemplateResponse('error.html', {
                'request': request,
                'message': message,
            })
        if booking_date_second <= booking_date_first:
            connection.close()
            message = 'Похоже, что вы выбрали неверную дату выезда, бронирование возможно не менее, чем на 1 день'
            return templates.TemplateResponse('error.html', {
                'request': request,
                'message': message,
            })
        if booking_date_second > str(datetime.date.today() + datetime.timedelta(days=365)):
            connection.close()
            message = 'Извините, бронирование более чем на год невозможно'
            return templates.TemplateResponse('error.html', {
                'request': request,
                'message': message,
            })

        cursor.execute("SELECT date_in, date_out FROM ClientsBooking WHERE date_in IS NOT NULL AND date_out IS NOT "
                       "NULL AND hotel_name = ?",
                       ('Измайлово Бета',))

        post_booked_dates = cursor.fetchall()
        post_dt_range = []
        for i in post_booked_dates:
            i_post_dt_range = pd.date_range(start=i[0], end=i[1])
            post_dt_range.append(i_post_dt_range)

        for j in post_dt_range:
            if str(booking_date_second) in j or str(booking_date_first) in j:
                connection.close()
                message = 'Извините, выбранная дата уже забронирована'
                return templates.TemplateResponse('error.html', {
                    'request': request,
                    'message': message,
                })

        booking_date_second_split = booking_date_second.split('-')
        booking_date_second_nulls_off = []
        for _ in booking_date_second_split:
            booking_date_second_nulls_off.append(int(_.lstrip('0')))
        booking_date_second_nulls_off = str(booking_date_second_nulls_off)
        total_days = (datetime.date(*literal_eval(booking_date_second_nulls_off)) - datetime.date(
            *literal_eval(booking_date_first_nulls_off))).days
        cursor.execute(
            "INSERT INTO ClientsBooking (client_email, hotel_name, date_in, date_out, total_days, price_per_day, "
            "is_confirm, hotel_address) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (client_email_from_page, hotel_name, booking_date_first, booking_date_second, total_days, one_day_price,
             False, hotel_address))
        connection.commit()
        connection.close()
        thread_check_confirmed = threading.Thread(target=check_confirmed, daemon=True)
        if not thread_check_confirmed.is_alive():
            thread_check_confirmed.start()
        return templates.TemplateResponse('order_confirmation.html', {
            'request': request,
            'client': client,
            'client_email': client_email,
            'one_day_price': one_day_price,
            'total_days': total_days,
            'hotel_name': hotel_name,
        })


@app.get('/movenpick')
async def get_movenpick_hotel_page(request: Request):
    main_images_paths_list = []
    mini_images_paths_list = []
    captions_list = ['Гостинная', 'Ванная', 'Кухня']
    if len(main_images_paths_list) <= 0 or len(mini_images_paths_list) <= 0:
        for i in range(3):
            img_path = f'static/moscow/movenpick/m{i + 1}.jpg'
            mini_img_path = f'static/moscow/movenpick/m{i + 1}_mini.jpg'
            img_for_resize = Image.open(img_path)
            resized_main_img = img_for_resize.resize((1024, 768), Image.Resampling.LANCZOS)
            resized_mini_img = img_for_resize.resize((200, 150), Image.Resampling.LANCZOS)
            resized_main_img.save(img_path)
            resized_mini_img.save(mini_img_path)
            main_images_paths_list.append(img_path)
            mini_images_paths_list.append(mini_img_path)

    zipped = zip(main_images_paths_list, mini_images_paths_list, captions_list)

    if check_auth():
        client = True

        connection = sqlite3.connect('my_fastapi_database.db')
        cursor = connection.cursor()
        cursor.execute("SELECT date_in, date_out FROM ClientsBooking WHERE date_in IS NOT NULL AND date_out IS NOT "
                       "NULL AND hotel_name = ?",
                       ('Movenpiсk Москва Таганская',))
        booked_dates = cursor.fetchall()
        connection.close()
        dt_range = []
        for i in booked_dates:
            i_dt_range = pd.date_range(start=i[0], end=i[1])
            dt_range.append(i_dt_range)

        min_available_booking_date_in = datetime.date.today() + datetime.timedelta(days=8)

        if len(dt_range) != 0:
            for i in dt_range:
                flag = True
                while flag:
                    if str(min_available_booking_date_in) in i or str(
                            min_available_booking_date_in + datetime.timedelta(days=1)) in i:
                        min_available_booking_date_in += datetime.timedelta(days=1)
                        continue
                    else:
                        break

        connection = sqlite3.connect('my_fastapi_database.db')
        cursor = connection.cursor()
        cursor.execute("SELECT date_in, date_out FROM ClientsBooking WHERE hotel_name = ?",
                       ('Movenpiсk Москва Таганская',))
        not_available_booking_dates = cursor.fetchall()
        cursor.execute("SELECT client_email FROM ClientsBooking WHERE is_confirm = ?", (False,))
        not_confirmed_order = cursor.fetchone()
        connection.close()
        connection = sqlite3.connect('my_fastapi_database.db')
        cursor = connection.cursor()
        cursor.execute("SELECT email FROM Clients WHERE is_authorized = ?", (1,))
        client_email = cursor.fetchone()[0]

        return templates.TemplateResponse('moscow_hotels/movenpick.html', {
            'request': request,
            'client': client,
            'client_email': client_email,
            'min_available_booking_date_in': min_available_booking_date_in,
            'not_available_booking_dates': not_available_booking_dates,
            'not_confirmed_order': not_confirmed_order,
            'zipped': zipped,
        })

    return templates.TemplateResponse('moscow_hotels/movenpick.html', {
        'request': request,
        'zipped': zipped,
    })


@app.post('/movenpick')
async def post_movenpick_hotel_page(request: Request, booking_date_first: str = Form(),
                                    booking_date_second: str = Form(),
                                    hotel_name: str = Form(),
                                    client_email_from_page: str = Form(),
                                    one_day_price: int = Form(),
                                    hotel_address: str = Form()):
    if check_auth():
        client = True
        connection = sqlite3.connect('my_fastapi_database.db')
        cursor = connection.cursor()
        cursor.execute("SELECT email FROM Clients WHERE is_authorized = ?", (1,))
        client_email = cursor.fetchone()[0]
        connection.close()
        connection = sqlite3.connect('my_fastapi_database.db')
        cursor = connection.cursor()
        booking_date_first_split = booking_date_first.split('-')
        booking_date_first_nulls_off = []
        for _ in booking_date_first_split:
            booking_date_first_nulls_off.append(int(_.lstrip('0')))
        booking_date_first_nulls_off = str(booking_date_first_nulls_off)
        if str(datetime.date.today()) > booking_date_first or (
                datetime.date(*literal_eval(booking_date_first_nulls_off)) - datetime.timedelta(
            days=7)) <= datetime.date.today():
            connection.close()
            message = 'Извините, но бронирование возможно только за 7 дней до заселения'
            return templates.TemplateResponse('error.html', {
                'request': request,
                'message': message,
            })
        if booking_date_second <= booking_date_first:
            connection.close()
            message = 'Похоже, что вы выбрали неверную дату выезда, бронирование возможно не менее, чем на 1 день'
            return templates.TemplateResponse('error.html', {
                'request': request,
                'message': message,
            })
        if booking_date_second > str(datetime.date.today() + datetime.timedelta(days=365)):
            connection.close()
            message = 'Извините, бронирование более чем на год невозможно'
            return templates.TemplateResponse('error.html', {
                'request': request,
                'message': message,
            })

        cursor.execute("SELECT date_in, date_out FROM ClientsBooking WHERE date_in IS NOT NULL AND date_out IS NOT "
                       "NULL AND hotel_name = ?",
                       ('Movenpiсk Москва Таганская',))

        post_booked_dates = cursor.fetchall()
        post_dt_range = []
        for i in post_booked_dates:
            i_post_dt_range = pd.date_range(start=i[0], end=i[1])
            post_dt_range.append(i_post_dt_range)

        for j in post_dt_range:
            if str(booking_date_second) in j or str(booking_date_first) in j:
                connection.close()
                message = 'Извините, выбранная дата уже забронирована'
                return templates.TemplateResponse('error.html', {
                    'request': request,
                    'message': message,
                })

        booking_date_second_split = booking_date_second.split('-')
        booking_date_second_nulls_off = []
        for _ in booking_date_second_split:
            booking_date_second_nulls_off.append(int(_.lstrip('0')))
        booking_date_second_nulls_off = str(booking_date_second_nulls_off)
        total_days = (datetime.date(*literal_eval(booking_date_second_nulls_off)) - datetime.date(
            *literal_eval(booking_date_first_nulls_off))).days
        cursor.execute(
            "INSERT INTO ClientsBooking (client_email, hotel_name, date_in, date_out, total_days, price_per_day, "
            "is_confirm, hotel_address) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (client_email_from_page, hotel_name, booking_date_first, booking_date_second, total_days, one_day_price,
             False, hotel_address))
        connection.commit()
        connection.close()
        thread_check_confirmed = threading.Thread(target=check_confirmed, daemon=True)
        if not thread_check_confirmed.is_alive():
            thread_check_confirmed.start()
        return templates.TemplateResponse('order_confirmation.html', {
            'request': request,
            'client': client,
            'client_email': client_email,
            'one_day_price': one_day_price,
            'total_days': total_days,
            'hotel_name': hotel_name,
        })


@app.get('/mercure')
async def get_mercure_hotel_page(request: Request):
    main_images_paths_list = []
    mini_images_paths_list = []
    captions_list = ['Гостинная', 'Ванная', 'Кухня']
    if len(main_images_paths_list) <= 0 or len(mini_images_paths_list) <= 0:
        for i in range(3):
            img_path = f'static/moscow/mercure/mc{i + 1}.jpg'
            mini_img_path = f'static/moscow/mercure/mc{i + 1}_mini.jpg'
            img_for_resize = Image.open(img_path)
            resized_main_img = img_for_resize.resize((1024, 768), Image.Resampling.LANCZOS)
            resized_mini_img = img_for_resize.resize((200, 150), Image.Resampling.LANCZOS)
            resized_main_img.save(img_path)
            resized_mini_img.save(mini_img_path)
            main_images_paths_list.append(img_path)
            mini_images_paths_list.append(mini_img_path)

    zipped = zip(main_images_paths_list, mini_images_paths_list, captions_list)


    if check_auth():
        client = True

        connection = sqlite3.connect('my_fastapi_database.db')
        cursor = connection.cursor()
        cursor.execute("SELECT date_in, date_out FROM ClientsBooking WHERE date_in IS NOT NULL AND date_out IS NOT "
                       "NULL AND hotel_name = ?",
                       ('Mercure',))
        booked_dates = cursor.fetchall()
        connection.close()
        dt_range = []
        for i in booked_dates:
            i_dt_range = pd.date_range(start=i[0], end=i[1])
            dt_range.append(i_dt_range)

        min_available_booking_date_in = datetime.date.today() + datetime.timedelta(days=8)

        if len(dt_range) != 0:
            for i in dt_range:
                flag = True
                while flag:
                    if str(min_available_booking_date_in) in i or str(
                            min_available_booking_date_in + datetime.timedelta(days=1)) in i:
                        min_available_booking_date_in += datetime.timedelta(days=1)
                        continue
                    else:
                        break

        connection = sqlite3.connect('my_fastapi_database.db')
        cursor = connection.cursor()
        cursor.execute("SELECT date_in, date_out FROM ClientsBooking WHERE hotel_name = ?", ('Mercure',))
        not_available_booking_dates = cursor.fetchall()
        cursor.execute("SELECT client_email FROM ClientsBooking WHERE is_confirm = ?", (False,))
        not_confirmed_order = cursor.fetchone()
        connection.close()
        connection = sqlite3.connect('my_fastapi_database.db')
        cursor = connection.cursor()
        cursor.execute("SELECT email FROM Clients WHERE is_authorized = ?", (1,))
        client_email = cursor.fetchone()[0]

        return templates.TemplateResponse('moscow_hotels/mercure.html', {
            'request': request,
            'client': client,
            'client_email': client_email,
            'min_available_booking_date_in': min_available_booking_date_in,
            'not_available_booking_dates': not_available_booking_dates,
            'not_confirmed_order': not_confirmed_order,
            'zipped': zipped,
        })

    return templates.TemplateResponse('moscow_hotels/mercure.html', {
        'request': request,
        'zipped': zipped,
    })


@app.post('/mercure')
async def post_mercure_hotel_page(request: Request, booking_date_first: str = Form(), booking_date_second: str = Form(),
                                  hotel_name: str = Form(),
                                  client_email_from_page: str = Form(),
                                  one_day_price: int = Form(),
                                  hotel_address: str = Form()):


    if check_auth():
        client = True
        connection = sqlite3.connect('my_fastapi_database.db')
        cursor = connection.cursor()
        cursor.execute("SELECT email FROM Clients WHERE is_authorized = ?", (1,))
        client_email = cursor.fetchone()[0]
        connection.close()
        connection = sqlite3.connect('my_fastapi_database.db')
        cursor = connection.cursor()
        booking_date_first_split = booking_date_first.split('-')
        booking_date_first_nulls_off = []
        for _ in booking_date_first_split:
            booking_date_first_nulls_off.append(int(_.lstrip('0')))
        booking_date_first_nulls_off = str(booking_date_first_nulls_off)
        if str(datetime.date.today()) > booking_date_first or (
                datetime.date(*literal_eval(booking_date_first_nulls_off)) - datetime.timedelta(
            days=7)) <= datetime.date.today():
            connection.close()
            message = 'Извините, но бронирование возможно только за 7 дней до заселения'
            return templates.TemplateResponse('error.html', {
                'request': request,
                'message': message,
            })
        if booking_date_second <= booking_date_first:
            connection.close()
            message = 'Похоже, что вы выбрали неверную дату выезда, бронирование возможно не менее, чем на 1 день'
            return templates.TemplateResponse('error.html', {
                'request': request,
                'message': message,
            })
        if booking_date_second > str(datetime.date.today() + datetime.timedelta(days=365)):
            connection.close()
            message = 'Извините, бронирование более чем на год невозможно'
            return templates.TemplateResponse('error.html', {
                'request': request,
                'message': message,
            })

        cursor.execute("SELECT date_in, date_out FROM ClientsBooking WHERE date_in IS NOT NULL AND date_out IS NOT "
                       "NULL AND hotel_name = ?",
                       ('Mercure',))

        post_booked_dates = cursor.fetchall()
        post_dt_range = []
        for i in post_booked_dates:
            i_post_dt_range = pd.date_range(start=i[0], end=i[1])
            post_dt_range.append(i_post_dt_range)

        for j in post_dt_range:
            if str(booking_date_second) in j or str(booking_date_first) in j:
                connection.close()
                message = 'Извините, выбранная дата уже забронирована'
                return templates.TemplateResponse('error.html', {
                    'request': request,
                    'message': message,
                })

        booking_date_second_split = booking_date_second.split('-')
        booking_date_second_nulls_off = []
        for _ in booking_date_second_split:
            booking_date_second_nulls_off.append(int(_.lstrip('0')))
        booking_date_second_nulls_off = str(booking_date_second_nulls_off)
        total_days = (datetime.date(*literal_eval(booking_date_second_nulls_off)) - datetime.date(
            *literal_eval(booking_date_first_nulls_off))).days
        cursor.execute(
            "INSERT INTO ClientsBooking (client_email, hotel_name, date_in, date_out, total_days, price_per_day, "
            "is_confirm, hotel_address) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (client_email_from_page, hotel_name, booking_date_first, booking_date_second, total_days, one_day_price,
             False, hotel_address))
        connection.commit()
        connection.close()
        thread_check_confirmed = threading.Thread(target=check_confirmed, daemon=True)
        if not thread_check_confirmed.is_alive():
            thread_check_confirmed.start()
        return templates.TemplateResponse('order_confirmation.html', {
            'request': request,
            'client': client,
            'client_email': client_email,
            'one_day_price': one_day_price,
            'total_days': total_days,
            'hotel_name': hotel_name,
        })


@app.get("/register")
async def register(request: Request):
    return templates.TemplateResponse('register.html', {
        'request': request,
    })


@app.post("/register")
async def register(request: Request, firstname: str = Form(), lastname: str = Form(), patronymic: str = Form(),
                   email: str = Form(), password: str = Form(), repeat_password: str = Form(),
                   date_of_birthday: str = Form()):
    if repeat_password != password:
        message = 'Пароли не совпадают'
        return templates.TemplateResponse('error.html', {
            'request': request,
            'message': message,
        })
    connection = sqlite3.connect('my_fastapi_database.db')
    cursor = connection.cursor()
    cursor.execute("SELECT is_authorized FROM Clients WHERE email = ?", (email,))
    result = cursor.fetchone()
    if result:
        connection.close()
        message = 'Пользователь с таким email уже существует'
        return templates.TemplateResponse('error.html', {
            'request': request,
            'message': message,
        })
    cursor.execute(
        "INSERT INTO Clients (last_name, first_name, patronymic, email, password, date_of_birthday, "
        "is_authorized) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (f'{firstname}', f'{lastname}', f'{patronymic}', f'{email}', f'{password}', f'{date_of_birthday}', 1))
    connection.commit()
    connection.close()
    return templates.TemplateResponse('redirect.html', {
        'request': request,
    })


@app.get("/logout")
async def logout(request: Request):
    return templates.TemplateResponse('logout.html', {
        'request': request,
    })


@app.post("/logout")
async def logout(request: Request):
    if check_auth():
        connection = sqlite3.connect('my_fastapi_database.db')
        cursor = connection.cursor()
        cursor.execute('UPDATE Clients SET is_authorized = ? WHERE is_authorized = ?', (0, 1))
        connection.commit()
        connection.close()
        return templates.TemplateResponse('redirect.html', {
            'request': request,
        })


@app.get("/login")
async def login(request: Request):
    return templates.TemplateResponse('login.html', {
        'request': request,
    })


@app.post("/login")
async def login(request: Request, email: str = Form(), password: str = Form()):
    connection = sqlite3.connect('my_fastapi_database.db')
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM Clients WHERE email = ?", (email,))
    result = cursor.fetchone()
    if result:
        if password == result[5]:
            cursor.execute('UPDATE Clients SET is_authorized = ? WHERE email = ?', (1, email))
            connection.commit()
            connection.close()
            return templates.TemplateResponse('redirect.html', {
                'request': request,
            })
        else:
            connection.close()
            message = 'Неверный пароль'
            return templates.TemplateResponse('error.html', {
                'request': request,
                'message': message,
            })
    else:
        connection.close()
        message = 'Пользователь с таким email не существует'
        return templates.TemplateResponse('error.html', {
            'request': request,
            'message': message,
        })


@app.get("/order_confirmation")
async def order_confirmation(request: Request):
    return templates.TemplateResponse('order_confirmation.html', {
        'request': request,
    })


@app.post("/order_confirmation")
async def order_confirmation(request: Request, pay_confirm: int = Form(), client_email: str = Form()):
    connection = sqlite3.connect('my_fastapi_database.db')
    cursor = connection.cursor()
    cursor.execute('UPDATE ClientsBooking SET is_confirm = ? WHERE is_confirm = ? AND client_email = ?',
                   (pay_confirm, False, client_email))
    connection.commit()
    connection.close()
    redirect_time = '3'
    redirect_url = '/client_page'
    redirect_message = 'Спасибо за оплату, вы будете перенаправлены в личный кабинет через несколько секунд!'
    return templates.TemplateResponse('redirect.html', {
        'request': request,
        'redirect_time': redirect_time,
        'redirect_url': redirect_url,
        'redirect_message': redirect_message,
    })


@app.get("/client_page")
async def client_page(request: Request):
    connection = sqlite3.connect('my_fastapi_database.db')
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM Clients WHERE is_authorized = ?", (1,))
    clients_result = cursor.fetchone()
    cursor.execute("SELECT * FROM ClientsBooking WHERE client_email = ?", (clients_result[4],))
    clients_booking_result = cursor.fetchall()
    connection.close()
    future_week = str(datetime.date.today() + datetime.timedelta(days=7))
    return templates.TemplateResponse('client_page.html', {
        'request': request,
        'clients_result': clients_result,
        'clients_booking_result': clients_booking_result,
        'future_week': future_week,
    })


@app.post("/client_page_delete_order")
async def client_page(request: Request, order_id_for_delete: int = Form()):
    connection = sqlite3.connect('my_fastapi_database.db')
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM Clients WHERE is_authorized = ?", (1,))
    clients_result = cursor.fetchone()
    cursor.execute("SELECT * FROM ClientsBooking WHERE client_email = ?", (clients_result[4],))
    clients_booking_result = cursor.fetchall()
    connection.close()
    future_week = str(datetime.date.today() + datetime.timedelta(days=7))
    if order_id_for_delete:
        connection = sqlite3.connect('my_fastapi_database.db')
        cursor = connection.cursor()
        cursor.execute("DELETE FROM ClientsBooking WHERE client_email = ? AND id = ?",
                       (clients_result[4], order_id_for_delete))
        connection.commit()
        connection.close()
        redirect_time = '2'
        redirect_url = '/client_page'
        redirect_message = 'Бронь снята. Вы будете перенаправлены в личный кабинет через несколько секунд'
        return templates.TemplateResponse('redirect.html', {
            'request': request,
            'redirect_time': redirect_time,
            'redirect_url': redirect_url,
            'redirect_message': redirect_message,
        })
    # return templates.TemplateResponse('client_page.html', {
    #     'request': request,
    #     'clients_result': clients_result,
    #     'clients_booking_result': clients_booking_result,
    #     'future_week': future_week,
    # })


@app.post("/client_page_confirm_order")
async def client_page(request: Request, order_id_for_confirm: int = Form()):
    connection = sqlite3.connect('my_fastapi_database.db')
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM Clients WHERE is_authorized = ?", (1,))
    clients_result = cursor.fetchone()
    cursor.execute("SELECT * FROM ClientsBooking WHERE client_email = ?", (clients_result[4],))
    clients_booking_result = cursor.fetchall()
    connection.close()
    future_week = str(datetime.date.today() + datetime.timedelta(days=7))
    connection = sqlite3.connect('my_fastapi_database.db')
    cursor = connection.cursor()
    cursor.execute('UPDATE ClientsBooking SET is_confirm = ? WHERE client_email = ? AND id = ?',
                   (True, clients_result[4], order_id_for_confirm))
    connection.commit()
    connection.close()
    redirect_time = '2'
    redirect_url = '/client_page'
    redirect_message = 'Спасибо за оплату, вы будете перенаправлены в личный кабинет через несколько секунд!'
    return templates.TemplateResponse('redirect.html', {
        'request': request,
        'redirect_time': redirect_time,
        'redirect_url': redirect_url,
        'redirect_message': redirect_message,
    })
