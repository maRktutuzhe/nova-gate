from http.server import HTTPServer, BaseHTTPRequestHandler
import logging

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
    logging.debug(f"пришли в логин")
    
    connect, resource = get_db_login_data(handler, params)
    data = resource[0]

    if connect and data.get("err") == 0:
        logging.debug(f"прошли проверку БД")
        
        access = generate_access_token(data["id_sc"])
        refresh = generate_refresh_token(data["id_sc"])

        check_file(data, refresh)
        start_mqtt(data["id_sc"])

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


web_procedures = {
    "login": login,
    "get_mqtt": get_mqtt,
    "logout": logout,
}

PUBLIC_ENDPOINTS = {"login", "logout"}
