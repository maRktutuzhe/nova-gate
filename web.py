from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import jwt
import datetime
import os
from typing import Dict, Any
from http import cookies
from http.cookies import SimpleCookie
import mqtt_client
import logging


logging.basicConfig(
    filename="server_debug.log",
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",  
    datefmt="%Y-%m-%d %H:%M:%S"
)

SECRET = "supersecretkey"
REFRESH_SECRET = "superrefreshkey"

ACCESS_EXPIRE_MINUTES = 15
REFRESH_EXPIRE_DAYS = 7



fileData = {
    'user_id': 0,
    'refresh': '',
    'mqtt_login': '',
    'mqtt_pass': ''
}

mqtt_user = {
    'login': '',
    'password': '',
    'client': {}
}

def router(handler, url: str, params):
    if "web/" not in url:
        handler.send_answer(404, {"error_code": 1, "message": "not found"})
        return
        
    _, part2 = url.split("web/", 1)
    print("part2", part2)

    if not part2 and part2 not in web_procedures:
        handler.send_answer(200, {"error_code": 1, "message": 'не существует пути' + part2})
        return

    if part2 in PUBLIC_ENDPOINTS:
        print('PUBLIC_ENDPOINTS')
        return web_procedures[part2](handler, params)
    payload, new_access = is_JWT_working(handler)
    if not payload:
        handler.send_answer(401, {"error_code": 1, "message": "unauthorized"})
        return
    return web_procedures[part2](handler, params, payload, new_access)
    
def login(handler, params):


    user_id = 0

    if params["login"] == "user1" and params["pass"] == "pass1":
        user_id = 1
        access = generate_access_token(user_id)
        refresh = generate_refresh_token(user_id)


        check_file(user_id, refresh)

        start_mqtt(user_id)

        

        handler.send_answer(
            status=200,
            js={
                "error_code": 0,
                "user_name": "Name1",
            },
            cookies=[
                f"access_token={access}; HttpOnly; Path=/; Max-Age=900",
                f"refresh_token={refresh}; HttpOnly; Path=/; Max-Age=604800"
            ],
            headers=[
                ("Access-Control-Allow-Origin", "https://testmon.svoyclub.com"),
                ("Access-Control-Allow-Credentials", "true"),
                ("Access-Control-Allow-Headers", "Content-Type"),
                ("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            ]
        )
    elif params["login"] == "user2" and params["pass"] == "pass2":
        user_id = 2
        access = generate_access_token(user_id)
        refresh = generate_refresh_token(user_id)
        check_file(user_id, refresh)
        messages = start_mqtt(user_id)

        handler.send_answer(
            status=200,
            js={
                "error_code": 0,
                "user_name": "Name2",
            },
            cookies=[
                f"access_token={access}; HttpOnly; Path=/; Max-Age=900",
                f"refresh_token={refresh}; HttpOnly; Path=/; Max-Age=604800"
            ],
            headers=[
                ("Access-Control-Allow-Origin", "https://testmon.svoyclub.com"),
                ("Access-Control-Allow-Credentials", "true"),
                ("Access-Control-Allow-Headers", "Content-Type"),
                ("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            ]
        )
    else:
        handler.send_answer(401, {"error_code": 2, "message": "invalid credentials"})

def check_file(user_id, refresh):
    data = {
        "user_id": user_id,
        "refresh": refresh,
    }
    loaded_data = {}

    if os.path.exists(f"users/{user_id}.json"):
        with open(f"users/{user_id}.json", 'r', encoding='utf-8') as file:
            loaded_data = json.load(file)
            loaded_data['refresh'] = data['refresh']
        with open(f"users/{user_id}.json", 'w', encoding='utf-8') as file:
            json.dump(loaded_data, file, ensure_ascii=False, indent=4)
    else:
        with open(f"users/{user_id}.json", 'a', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
    


def generate_access_token(user_id: int):
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=ACCESS_EXPIRE_MINUTES)
    payload = {
        "user_id": user_id,
        "exp": int(expire.timestamp()),
        "iat": int(datetime.datetime.now(datetime.timezone.utc).timestamp()),
        "type": "access"
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")

def generate_refresh_token(user_id: int):
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=REFRESH_EXPIRE_DAYS)
    payload = {
        "user_id": user_id,
        "exp": int(expire.timestamp()),
        "iat": int(datetime.datetime.now(datetime.timezone.utc).timestamp()),
        "type": "refresh"
    }
    return jwt.encode(payload, REFRESH_SECRET, algorithm="HS256")

def verify_token(token: str, secret: str):
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def is_JWT_working(handler):
    
    cookie_header = handler.headers.get("Cookie")

    if not cookie_header:
        return None, None

    # получение cookie
    cookies = SimpleCookie()
    cookies.load(cookie_header)
    access_token = cookies.get("access_token")
    refresh_token = cookies.get("refresh_token")

    if access_token:
        payload = verify_token(access_token.value, SECRET)
        print('payload', payload)
        
        if payload and payload.get("type") == "access":
            print("access_token ещё работает")
            return payload, None

    if not refresh_token:
        print("refresh_token отсутствует")
        return None, None

    refresh_payload = verify_token(refresh_token.value, REFRESH_SECRET)
    if not refresh_payload or refresh_payload["type"] != "refresh":
        return None, None

    user_id = refresh_payload["user_id"]
    if not user_id:
        return None, None

    # Проверяем refresh в файле
    file_refresh = read_refresh_from_file(user_id)
    if not file_refresh or file_refresh != refresh_token.value:
        return None, None

    new_access = generate_access_token(user_id)
    print("рефрешнули")

    return {"user_id": user_id}, new_access

def read_refresh_from_file(user_id: int) -> str | None:
    try:       
        with open(f"users/{user_id}.json", 'r', encoding='utf-8') as file:
            loaded_data = json.load(file)
            return loaded_data['refresh']
    except FileNotFoundError:
        return None

def protected(handler, params):
    if is_JWT_working(handler):
        handler.send_answer(200, {"error_code": 0, "message": 'JWT работает'})
    else:
        handler.send_answer(200, {"error_code": 1, "message": 'JWT не работает'})

    

def start_mqtt(user_id):
    logging.debug(f"старт mqtt:")
    if os.path.exists(f"users/{user_id}.json"):
        with open(f"users/{user_id}.json", 'r', encoding='utf-8') as file:
            loaded_data = json.load(file)
            mqtt_user['login'] = loaded_data['mqtt_login']
            mqtt_user['password'] = loaded_data['mqtt_pass']
    return mqtt_client.start_mqtt(mqtt_user)
    
def get_mqtt(handler, params, payload, new_access):
    # logging.debug(f"get mqtt:")

    # res = is_JWT_working(handler)

    # if res == False:
    #     handler.send_answer(
    #         200,
    #         {"error_code": 1, "message": "JWT не работает, подключения к mqtt нет"}
    #     )
    #     return


    # logging.debug(f"JWT сработал!:")
    
    user_id = payload['user_id']
    messages = start_mqtt(user_id)

    logging.debug(f"получили сообщение:")
    
    cookies = []

    if new_access:  # если обновили access
        cookies.append(
            f"access_token={new_access}; HttpOnly; Path=/; Max-Age={ACCESS_EXPIRE_MINUTES*60}"
        )

    if messages:
        handler.send_answer(
            200,
            {"error_code": 0, "message": normalize_mqtt(messages), "old_values": messages},
            cookies=cookies
        )
    else:
        handler.send_answer(
            200,
            {"error_code": 1, "message": "Нет новых сообщений от MQTT"},
            cookies=cookies
        )

DEVICE_TYPES = {
    "kkm": "ККМ",
    "sclife": "Плата жизнеобеспечения",
    "casher": "Купюроприемник",
}

DEVICE_MODELS = {
    "atol": "АТОЛ",
    "shtrih": "Штрих-М",
    "sc": "Svoy.Club",
    "ablog": "ab-log.ru",
}

def normalize_mqtt(data):
    rows = []
    print("data", data)
    logging.debug(f"пришли в normalize_mqtt:")

    for path, values in data.items():
        parts = path.split("/")
        _, client, toid, rmid, devid, devtype, devmodel, status = parts
        row = {
            "point": toid.removeprefix("to"),
            "workplace": rmid.removeprefix("rm"),
            "dev_id": devid.removeprefix("dev"),
            "dev_name": DEVICE_TYPES.get(devtype, devtype),
            "dev_model": DEVICE_MODELS.get(devmodel, devmodel),
            "parameter_name": status,
            "parameter_kod": "",
            "comment": ""
        }
        if devtype == "kkm":
            row["parameter_name"] = "Статус"
            row["parameter_kod"] = values.get("kod", "")
            row["comment"] = values.get("descr", "")
        elif devtype == "sclife":
            if "sctemp" in values:
                row["parameter_name"] = "Температура платы"
                row["parameter_kod"] = values["sctemp"]

        row["state"] = get_state(devtype, devmodel, row["parameter_kod"])

        rows.append(row)
    return rows

def get_state(devtype, devmodel, kod):
    logging.debug(f"пришли в get_state:")

    with open("devsettings.json", 'r', encoding='utf-8') as file:

        all_settings = json.load(file)
        logging.debug(f"пришли в get_state:")
        logging.debug(f"{all_settings}")
        if not all_settings['devices'].get(devtype):
            print("не нашли устройство в файле()", devtype)
        else:
            if not all_settings['devices'][devtype].get(devmodel):
                print("не нашли модель в файле()", devmodel)
            else:
                settings = all_settings['devices'][devtype][devmodel]
                first_param_name = next(iter(settings))
                range = settings[first_param_name]
                return check_range(range, kod)


def check_range(ranges, kod):
    logging.debug(f"пришли в check_range:")

    for state in ["critical", "warning", "normal"]:
        if state not in ranges:
            continue
        for segment in ranges[state]:
            if in_range(kod, segment):
                return state
    return "critical"

def in_range(value, segment):
    logging.debug(f"пришли в in_range:")


    try:
        value = int(value)
    except (TypeError, ValueError):
        return False  # если в
    lower = segment["lower"]
    upper = segment["upper"]
    
    if lower == upper and value == upper:
        return True         

    # нижняя граница
    if lower is None:
        lower_ok = True
    else:
        lower_ok = value > lower

    # верхняя граница
    if upper is None:
        upper_ok = True
    else:
        upper_ok = value <= upper
    return lower_ok and upper_ok


def logout(handler, params):
    print('DEL COOKIE')
    handler.send_answer(
        status=200,
        js={
            "error_code": 0,
            "message": "Successfully logged out"
        },
        cookies=[
            "access_token=; HttpOnly; Path=/; Max-Age=0",
            "refresh_token=; HttpOnly; Path=/; Max-Age=0"
        ]
    )

web_procedures = {
    'login': login,
    'get_mqtt': get_mqtt,
    # 'protected': protected,
    'logout': logout
}

PUBLIC_ENDPOINTS = {"login", "logout"}
