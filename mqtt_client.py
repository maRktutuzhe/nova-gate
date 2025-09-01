import paho.mqtt.client as mqtt

last_message = None

def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT with result code " + str(rc))
    client.subscribe("nova/client0/#")  # ← твой топик

def on_message(client, userdata, msg):
    global last_message
    last_message = msg.payload.decode()
    # print("MQTT message received:", last_message)

def start_mqtt(user):
    print('mqtt user^', user)
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    # если нужен логин/пароль:
    client.username_pw_set(user['login'], user['password'])

    client.connect("89.169.141.81", 1883, 60)
    client.loop_start()
    return client
