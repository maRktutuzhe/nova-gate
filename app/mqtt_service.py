import os
import json
import app.mqtt_client as mqtt_client

mqtt_user = {"login": "", "password": "", "client": {}}

def start_mqtt(user_id):
    base = os.path.dirname(__file__)  # app/
    path = os.path.join(base, "users", f"{user_id}.json")
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as file:
            loaded_data = json.load(file)
            mqtt_user['login'] = loaded_data['mqtt_login']
            mqtt_user['password'] = loaded_data['mqtt_pass']
    return mqtt_client.start_mqtt(mqtt_user)