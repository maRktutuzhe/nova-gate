import jwt
import datetime
import json
import os
from http.cookies import SimpleCookie

SECRET = "supersecretkey"
REFRESH_SECRET = "superrefreshkey"
ACCESS_EXPIRE_MINUTES = 15
REFRESH_EXPIRE_DAYS = 7

def generate_access_token(user_id):
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=ACCESS_EXPIRE_MINUTES)
    payload = {
        "user_id": user_id,
        "exp": int(expire.timestamp()),
        "iat": int(datetime.datetime.now(datetime.timezone.utc).timestamp()),
        "type": "access"
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")

def generate_refresh_token(user_id):
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
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def is_JWT_working(handler):
    cookie_header = handler.headers.get("Cookie")
    if not cookie_header:
        return None, None

    cookies = SimpleCookie()
    cookies.load(cookie_header)
    access_token = cookies.get("access_token")
    refresh_token = cookies.get("refresh_token")

    if access_token:
        payload = verify_token(access_token.value, SECRET)
        if payload and payload.get("type") == "access":
            return payload, None

    if not refresh_token:
        return None, None

    refresh_payload = verify_token(refresh_token.value, REFRESH_SECRET)
    if not refresh_payload or refresh_payload.get("type") != "refresh":
        return None, None

    user_id = refresh_payload["user_id"]
    if not user_id:
        return None, None

    file_refresh = read_refresh_from_file(user_id)
    if not file_refresh or file_refresh != refresh_token.value:
        return None, None

    new_access = generate_access_token(user_id)
    return {"user_id": user_id}, new_access

def read_refresh_from_file(user_id: int):
    try:
        base = os.path.dirname(__file__)  # app/
        path = os.path.join(base, "users", f"{user_id}.json")
        with open(path, 'r', encoding='utf-8') as file:
            return json.load(file)['refresh']
    except FileNotFoundError:
        return None
