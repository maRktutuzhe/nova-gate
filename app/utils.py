import json
import os
import logging

logging.basicConfig(
    filename="server_debug.log",
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
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

BASE_DIR = os.path.dirname(__file__)  # папка app
USERS_DIR = os.path.join(BASE_DIR, "users")

def normalize_mqtt(data):
    logging.debug(f"start normalize_mqtt")

    rows = []
    print("data", data)

    for path, values in data.items():
        parts = path.split("/")
        _, client, toid, rmid, devid, devtype, devmodel, status = parts
        

        # row["state"] = get_state(devtype, devmodel, values)
        dev_info, params = get_state(devtype, devmodel, values)
        client_info = get_client(client, toid)

        row = {
            "client": client_info['name'],
            "point": client_info['point'],
            "workplace": rmid.removeprefix("rm"),
            "dev_id": devid.removeprefix("dev"),
            "dev_name": dev_info['type'],
            "dev_model":dev_info['model'],
            "parameter_name": params['param_name'],
            "state": params['state'],
            "parameter_kod": params['param_kod'],
            "comment": values.get("descr", "")
        }

        rows.append(row)
    return rows

def get_client(client, point):

    base = os.path.dirname(__file__)
    path = os.path.join(base, "..", "clients.json")
    path = os.path.abspath(path)
    client_info = {}
    client_info['name'] = client.removeprefix("client")
    client_info['point'] = point.removeprefix("to")
    print("********КЛИЕНТ************", client)
    print("********ТОЧКА************", point)

    with open(path, 'r', encoding='utf-8') as file:

        all_settings = json.load(file)
        print("зашли в файл", all_settings)
        if not all_settings['clients'].get(client):
            print("не нашли клиента в файле()", client)
        else:
            print("клиент есть", all_settings['clients'].get(client))
            print("точки клиента", all_settings['clients'][client]['to'])

            client_info['name'] = all_settings['clients'][client].get('name')
            if not all_settings['clients'][client]['to'].get(point):
                print("не нашли точку обслуживания в файле()", point)
            else:
                print("точка есть", all_settings['clients'][client]['to'][point])

                client_info['point'] = all_settings['clients'][client]['to'][point].get('name')
               
    return client_info

def get_state(devtype, devmodel, values):
    logging.debug(f"start get_state")

    base = os.path.dirname(__file__)
    path = os.path.join(base, "..", "devsettings.json")
    path = os.path.abspath(path)
    with open(path, 'r', encoding='utf-8') as file:

        all_settings = json.load(file)
        if not all_settings['devices'].get(devtype):
            print("не нашли устройство в файле()", devtype)
        else:
            if not all_settings['devices'][devtype].get(devmodel):
                print("не нашли модель в файле()", devmodel)
            else:
                settings = all_settings['devices'][devtype][devmodel]
                first_param_name = next(iter(settings))
                range = settings[first_param_name]
                value = values.get(first_param_name, '')
                dev_info = {
                    'type': settings['descrdev']['devtype'],
                    'model': settings['descrdev']['devmodel']
                }
     
                params = {
                    'state': check_range(range, value),
                    'param_name': settings[first_param_name]['parname'],
                    'param_kod': value
                }
                return dev_info, params

def check_range(ranges, kod):
    logging.debug(f"start check_range")

    for state in ["critical", "warning", "normal"]:
        if state not in ranges:
            continue
        for segment in ranges[state]:
            if in_range(kod, segment):
                return state
    return "critical"

def in_range(value, segment):
    logging.debug(f"start in_range")


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

def check_file(db_data, refresh): 
    logging.debug(f"start check_file")

    data = { "user_id": db_data['id_sc'], "refresh": refresh, "mqtt_login": db_data['mqtt_login'], "mqtt_pass": db_data['mqtt_pass'] } 
    loaded_data = {} 
    os.makedirs(USERS_DIR, exist_ok=True)

    user_file = os.path.join(USERS_DIR, f"{db_data['id_sc']}.json")
    with open(user_file, 'w', encoding='utf-8') as file: 
        json.dump(data, file, ensure_ascii=False, indent=4)