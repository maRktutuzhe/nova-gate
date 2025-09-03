from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import jwt
import datetime
import os
from typing import Dict, Any
from http import cookies
from http.cookies import SimpleCookie
import mqtt_client



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
    if "web/" in url:
        _, part2 = url.split("web/", 1)
        print("part2", part2)
        if part2 and part2 in web_procedures:
            if part2 == 'login':
                login(handler, params)
            else: 
                web_procedures[part2](handler, params)
            # elif part2 == 'getData':
            #     protected(handler, params)
            # elif part2 == 'get_mqtt':
            #     get_mqtt(handler, params)
        else:
            handler.send_answer(200, {"error_code": 1, "message": 'не существует пути' + part2})
    else:
        handler.send_answer(404, {"error_code": 1, "message": "not found"})
    
def login(handler, params):

    print('params', params)
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
                "devices": ['dev1', 'dev2']
            },
            cookies=[
                f"access_token={access}; HttpOnly; Path=/; Max-Age=900",
                f"refresh_token={refresh}; HttpOnly; Path=/; Max-Age=604800"
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
                "devices": ['dev3', 'dev4']
            },
            cookies=[
                f"access_token={access}; HttpOnly; Path=/; Max-Age=900",
                f"refresh_token={refresh}; HttpOnly; Path=/; Max-Age=604800"
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
        # "username": "admin",
        # "role": "administrator",
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
    token = None
    if cookie_header:
        cookies = SimpleCookie()
        print('cookies', cookies)
        cookies.load(cookie_header)
        if "access_token" in cookies:
            token = cookies["access_token"].value
            print('token', token)
            

    if not token:
        return False

    payload = verify_token(token, SECRET)
    print('payload', payload)
    if not payload or payload.get("type") != "access":
        return False
    return payload

def protected(handler, params):
    if is_JWT_working(handler):
        handler.send_answer(200, {"error_code": 0, "message": 'JWT работает'})
    else:
        handler.send_answer(200, {"error_code": 1, "message": 'JWT не работает'})

    

def start_mqtt(user_id):

    # get_pass(handler, params)
    if os.path.exists(f"users/{user_id}.json"):
        with open(f"users/{user_id}.json", 'r', encoding='utf-8') as file:
            loaded_data = json.load(file)
            mqtt_user['login'] = loaded_data['mqtt_login']
            mqtt_user['password'] = loaded_data['mqtt_pass']
    return mqtt_client.start_mqtt(mqtt_user)
    # print('mqtt_user[client]', mqtt_user['client'])
    # mqtt_client.fetch_last_messages("user1", "pass1", timeout=2)

    # handler.send_answer(200, {"error_code": 0, "message": 'mqtt start!'})
    
    
    
def get_pass(handler, params):
    cookie_header = handler.headers.get("Cookie")
    token = None
    if cookie_header:
        cookies = SimpleCookie()
        print('cookies', cookies)
        cookies.load(cookie_header)
        if "access_token" in cookies:
            token = cookies["access_token"].value
            print('token', token)
            

    if not token:
        handler.send_answer(401, {"message": "missing token"})
        return

    payload = verify_token(token, SECRET)
    print('payloa', payload)
    if not payload or payload.get("type") != "access":
        handler.send_answer(401, {"message": "invalid or expired token"})
        return

    if os.path.exists(f"users/{payload['user_id']}.json"):
        with open(f"users/{payload['user_id']}.json", 'r', encoding='utf-8') as file:
            loaded_data = json.load(file)
            user['login'] = loaded_data['mqtt_login']
            user['password'] = loaded_data['mqtt_pass']
    
def get_mqtt(handler, params):

    if is_JWT_working(handler) == False:
        handler.send_answer(
            200,
            {"error_code": 1, "message": "JWT не работает, подключения к mqtt нет"}
        )
    user_id = is_JWT_working(handler)['user_id']
    messages = start_mqtt(user_id)



    if messages is not None:
        handler.send_answer(
            200,
            {"error_code": 0, "message": messages}
        )
    else:
        handler.send_answer(
            200,
            {"error_code": 1, "message": "Нет новых сообщений от MQTT"}
        )

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
    'protected': protected,
    'logout': logout
}
