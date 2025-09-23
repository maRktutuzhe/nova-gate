from http.server import HTTPServer, BaseHTTPRequestHandler
import logging
import json
from urllib import request as urllib_request
from urllib.error import URLError



PY_SERVER = "http://158.160.35.144:5000"

# авторизация (jwt) — в auth.py
from app.auth import (
    is_JWT_working,
    generate_access_token,
    generate_refresh_token,
)

from app.db import get_db_login_data
from app.mqtt_service import start_mqtt
from app.utils import (
    normalize_mqtt,
    check_file,
    check_range,    # если используешь напрямую
)
# константы можно брать из auth или объявить локально
from app.auth import ACCESS_EXPIRE_MINUTES, REFRESH_EXPIRE_DAYS

logging.basicConfig(
    filename="server_debug.log",
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)


def router(handler, url: str, params):
    if "web/" not in url:
        handler.send_answer(404, {"error_code": 1, "message": "not found"})
        return

    _, part2 = url.split("web/", 1)
    logging.debug(f"part2: {part2}")

    if not part2 or part2 not in web_procedures:
        handler.send_answer(200, {"error_code": 1, "message": "не существует пути " + part2})
        return

    if part2 in PUBLIC_ENDPOINTS:
        
        return web_procedures[part2](handler, params)

    payload, new_access = is_JWT_working(handler)
    if not payload:
        handler.send_answer(401, {"error_code": 1, "message": "unauthorized"})
        return

    return web_procedures[part2](handler, params, payload, new_access)


def login(handler, params):
    connect, resource = get_db_login_data(handler, params)
    data = resource[0]

    if connect and data.get("err") == 0:
        # data = {}
        # data["id_sc"] = 27
        # data["mqtt_login"] = 'bolotina'
        # data["mqtt_pass"] = 'bolotina112234'
    
        access = generate_access_token(data["id_sc"])
        refresh = generate_refresh_token(data["id_sc"])

        check_file(data, refresh)

        handler.send_answer(
            status=200,
            js={
                "error_code": 0,
                "user_name": data["id_sc"],
            },
            cookies=[
                f"access_token={access}; HttpOnly; Path=/; Max-Age={ACCESS_EXPIRE_MINUTES * 60}",
                f"refresh_token={refresh}; HttpOnly; Path=/; Max-Age={REFRESH_EXPIRE_DAYS * 60 * 60 * 24}",
            ],
            headers=[
                ("Access-Control-Allow-Origin", "https://testmon.svoyclub.com"),
                ("Access-Control-Allow-Credentials", "true"),
                ("Access-Control-Allow-Headers", "Content-Type"),
                ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
            ],
        )
    else:
        handler.send_answer(
            status=401,
            js={
                "error_code": data.get("err"),
                "message": data.get("error_message"),
            }
        )


def get_mqtt(handler, params, payload, new_access):
    user_id = payload["user_id"]
    messages = start_mqtt(user_id)

    cookies = []
    headers = []

    if new_access:  # если обновили access
        cookies.append(
            f"access_token={new_access}; HttpOnly; Path=/; Max-Age={ACCESS_EXPIRE_MINUTES*60}"
        )
        headers = [
            ("Access-Control-Allow-Origin", "https://testmon.svoyclub.com"),
            ("Access-Control-Allow-Credentials", "true"),
            ("Access-Control-Allow-Headers", "Content-Type"),
            ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
        ]

    if messages:
        handler.send_answer(
            200,
            {"error_code": 0, "message": normalize_mqtt(messages), "old_values": messages},
            cookies=cookies,
            headers=headers,
        )
    else:
        handler.send_answer(
            200,
            {"error_code": 1, "message": "Нет новых сообщений от MQTT"},
            cookies=cookies,
            headers=headers,
        )


def logout(handler, params):
    handler.send_answer(
        status=200,
        js={
            "error_code": 0,
            "message": "Successfully logged out",
        },
        cookies=[
            "access_token=; HttpOnly; Path=/; Max-Age=0",
            "refresh_token=; HttpOnly; Path=/; Max-Age=0",
        ],
    )


def proxy_post(handler, params, path):
    try:
        data = json.dumps(params).encode('utf-8')
        req = urllib_request.Request(PY_SERVER + "/" + path, data=data, headers={'Content-Type': 'application/json'})
        with urllib_request.urlopen(req, timeout=5) as resp:
            resp_data = resp.read()
            try:
                js = json.loads(resp_data)
            except:
                js = {"message": resp_data.decode()}
            handler.send_answer(resp.getcode(), js)
    except URLError as e:
        handler.send_answer(500, {"error_code": 1, "message": str(e)})

def proxy_get(handler, params, path):
    logging.debug(f"proxy_get called with path: {path}, params: {params}")
    try:
        url = PY_SERVER + "/" + path
        logging.debug(f"Opening URL: {url}")
        req = urllib_request.Request(url, headers={'Content-Type': 'application/json'})

        with urllib_request.urlopen(req, timeout=5) as resp:
            logging.debug(f"Response opened, status: {resp.getcode()}")
            resp_data = resp.read()
            logging.debug(f"Raw response data: {resp_data}")
            try:
                js = json.loads(resp_data)
                logging.debug(f"JSON parsed: {js}")
            except Exception as e:
                logging.debug(f"JSON parse error: {e}")
                js = {"message": resp_data.decode()}
            handler.send_answer(resp.getcode(), js)
            logging.debug("Response sent to client")

    except URLError as e:
        logging.debug(f"URLError: {e}")
        handler.send_answer(500, {"error_code": 1, "message": str(e)})


def users_list(handler, params, payload, new_access): 
    return proxy_post(handler, params, "users/list") 
    
def change_password(handler, params, payload, new_access):
    return proxy_post(handler, params, "users/change_password")

def view_acl(handler, params, payload, new_access):
    username = 'bolotina'
    if not username:
        handler.send_answer(400, {"error_code": 1, "message": "username не указан"})
        return
    return proxy_get(handler, params, f"acl/view/{username}")

web_procedures = {
    "login": login,
    "get_mqtt": get_mqtt,
    "logout": logout,
    "users_list": users_list,
    "change_password": change_password,
    "view_acl": view_acl,
}

PUBLIC_ENDPOINTS = {"login", "logout"}
