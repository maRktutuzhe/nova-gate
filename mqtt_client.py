import paho.mqtt.client as mqtt
import jwt
import json
import time

last_message = None

def fetch_last_messages(login, password, timeout=2):
    """
    Подключается к MQTT от имени пользователя и возвращает все доступные ему retained-сообщения.
    """
    messages = {}

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            # Подписываемся на все топики
            client.subscribe("#")
        else:
            print("Ошибка подключения:", rc)

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
        except Exception:
            payload = msg.payload.decode()
        messages[msg.topic] = payload

    client = mqtt.Client()
    client.username_pw_set(login, password)
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect("your-mqtt-host", 1883, 60)
    client.loop_start()

    time.sleep(timeout)  # ждём retained-сообщения

    client.loop_stop()
    client.disconnect()

    return messages

# def on_connect(client, userdata, flags, rc):
#     print("Connected to MQTT with result code " + str(rc))
#     client.subscribe("nova/client0/#")  # ← твой топик

# def on_message(client, userdata, msg):
#     global last_message
#     try:
#         last_message = json.loads(msg.payload.decode())
#     except json.JSONDecodeError:
#         last_message = {"raw": msg.payload.decode()}
#     # print("MQTT message received:", last_message)

# def start_mqtt(user):
#     print('mqtt user^', user)
#     client = mqtt.Client()
#     client.on_connect = on_connect
#     client.on_message = on_message

#     # если нужен логин/пароль:
#     client.username_pw_set(user['login'], user['password'])

#     client.connect("89.169.141.81", 1883, 60)
#     client.loop_start()
#     fetch_last_messages()
#     return client


def start_mqtt(user: dict, timeout: int = 2) -> dict:
    """
    Временно подключается к MQTT под учеткой пользователя,
    подписывается на все доступные топики и возвращает их последние retained-сообщения.

    :param user: словарь с ключами 'login' и 'password'
    :param timeout: сколько секунд ждать сообщения от брокера
    :return: dict {топик: сообщение}
    """
    messages = {}

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            # Подписываемся на все топики, доступные для этой учетной записи
            client.subscribe("#")
        else:
            print("Ошибка подключения к MQTT:", rc)

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
        except Exception:
            payload = msg.payload.decode()
        messages[msg.topic] = payload

    # создаем MQTT-клиент
    client = mqtt.Client()
    client.username_pw_set(user['login'], user['password'])
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect("89.169.141.81", 1883, 60)
    client.loop_start()

    # ждём, пока брокер отдаст retained-сообщения
    time.sleep(timeout)

    client.loop_stop()
    client.disconnect()

    return messages