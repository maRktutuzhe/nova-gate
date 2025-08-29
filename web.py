from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import jwt
import datetime
import os
from typing import Dict, Any
from http import cookies

SECRET = "supersecretkey"
REFRESH_SECRET = "superrefreshkey"

ACCESS_EXPIRE_MINUTES = 15
REFRESH_EXPIRE_DAYS = 7

def router(handler, url: str, params):


    if "web/" in url:
        _, part2 = url.split("web/", 1)
        print("part2", part2)
        if part2 == 'login':
            login(handler, params)
        elif part2 == 'getData':
            protected(handler, params, handler.headers.get("Authorization"))
        else:
            handler.send_answer(200, {"error_code": 0, "message": 'не существует пути' + part2})
    else:
        handler.send_answer(404, {"error_code": 1, "message": "not found"})
    
def login(handler, params):

    print('params', params)
    user_id = 0

    if params["login"] == "user1" and params["pass"] == "pass1":
        user_id = 1
        access = generate_access_token(user_id)
        refresh = generate_refresh_token(user_id)
        handler.send_answer(
            status=200,
            js={
                "error_code": 0,
                "user_name": "Name1",
                "access_token": access,
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
        handler.send_answer(
            status=200,
            js={
                "error_code": 0,
                "user_name": "Name2",
                "access_token": access,
                "devices": ['dev3', 'dev4']
            },
            cookies=[
                f"access_token={access}; HttpOnly; Path=/; Max-Age=900",
                f"refresh_token={refresh}; HttpOnly; Path=/; Max-Age=604800"
            ]
        )
    else:
        handler.send_answer(401, {"error_code": 2, "message": "invalid credentials"})

def generate_access_token(user_id: int):
    payload = {
        "user_id": user_id,
        # "username": "admin",
        # "role": "administrator",
        "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=ACCESS_EXPIRE_MINUTES),
        "iat": datetime.datetime.utcnow(),
        "type": "access"
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")

def generate_refresh_token(user_id: int):
    payload = {
        "user_id": user_id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=REFRESH_EXPIRE_DAYS),
        "iat": datetime.datetime.utcnow(),
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


def protected(handler, params, auth_header: str):
    if not auth_header or not auth_header.startswith("Bearer "):
        handler.send_answer(401, {"message": "missing token"})
        return

    token = auth_header.split(" ")[1]
    payload = verify_token(token, SECRET)
    if not payload or payload.get("type") != "access":
        handler.send_answer(401, {"message": "invalid or expired token"})
        return

    handler.send_answer(200, {"message": f"Hello user {payload['user_id']}!"})
