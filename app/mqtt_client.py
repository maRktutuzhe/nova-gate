import paho.mqtt.client as mqtt
import json
import time
import configparser
import logging

logging.basicConfig(
    filename="server_debug.log",
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",  
    datefmt="%Y-%m-%d %H:%M:%S"
)

config = configparser.ConfigParser()
config.read("mqtt.ini")
MQTT_HOST = config["MQTT"]["host"]
MQTT_PORT = int(config["MQTT"]["port"])
MQTT_KEEPALIVE = int(config["MQTT"]["keepalive"])

def start_mqtt(user: dict, timeout: int = 2) -> dict:

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

    client.connect(MQTT_HOST, MQTT_PORT, MQTT_KEEPALIVE)
    client.loop_start()

    # ждём, пока брокер отдаст retained-сообщения
    time.sleep(timeout)

    client.loop_stop()
    client.disconnect()

    return messages