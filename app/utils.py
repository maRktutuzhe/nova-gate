import json
import os

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
    rows = []
    print("data", data)

    for path, values in data.items():
        parts = path.split("/")
        _, client, toid, rmid, devid, devtype, devmodel, status = parts
        

        # row["state"] = get_state(devtype, devmodel, values)
        dev_info, params = get_state(devtype, devmodel, values)

        row = {
            "client": client.removeprefix("client"),
            "point": toid.removeprefix("to"),
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

def get_state(devtype, devmodel, values):
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
                print('first_param_name', first_param_name)
                print('values', values)
                print('value', value)
                dev_info = {
                    'type': settings['descrdev']['devtype'],
                    'model': settings['descrdev']['devmodel']
                }
                print('valusettings[first_param_name]e', settings[first_param_name])
     
                params = {
                    'state': check_range(range, value),
                    'param_name': settings[first_param_name]['parname'],
                    'param_kod': value
                }
                return dev_info, params

def check_range(ranges, kod):

    for state in ["critical", "warning", "normal"]:
        if state not in ranges:
            continue
        for segment in ranges[state]:
            if in_range(kod, segment):
                return state
    return "critical"

def in_range(value, segment):


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
    data = { "user_id": db_data['id_sc'], "refresh": refresh, "mqtt_login": db_data['mqtt_login'], "mqtt_pass": db_data['mqtt_pass'] } 
    loaded_data = {} 
    os.makedirs(USERS_DIR, exist_ok=True)

    user_file = os.path.join(USERS_DIR, f"{db_data['id_sc']}.json")
    with open(user_file, 'w', encoding='utf-8') as file: 
        json.dump(data, file, ensure_ascii=False, indent=4)