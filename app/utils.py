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

def normalize_mqtt(data):
    rows = []
    print("data", data)

    for path, values in data.items():
        parts = path.split("/")
        _, client, toid, rmid, devid, devtype, devmodel, status = parts
        row = {
            "client": client.removeprefix("client"),
            "point": toid.removeprefix("to"),
            "workplace": rmid.removeprefix("rm"),
            "dev_id": devid.removeprefix("dev"),
            "dev_name": DEVICE_TYPES.get(devtype, devtype),
            "dev_model": DEVICE_MODELS.get(devmodel, devmodel),
            "parameter_name": status,
            "parameter_kod": "",
            "comment": ""
        }
        if devtype == "kkm":
            row["parameter_name"] = "Статус"
            row["parameter_kod"] = values.get("kod", "")
            row["comment"] = values.get("descr", "")
        elif devtype == "sclife":
            if "sctemp" in values:
                row["parameter_name"] = "Температура платы"
                row["parameter_kod"] = values["sctemp"]

        row["state"] = get_state(devtype, devmodel, row["parameter_kod"])

        rows.append(row)
    return rows

def get_state(devtype, devmodel, kod):
    base = os.path.dirname(__file__)
    path = os.path.join(base, "..", "devsettings.json")  # если devsettings.json в корне
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
                return check_range(range, kod)

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
    if os.path.exists(f"users/{db_data['id_sc']}.json"): 
        with open(f"users/{db_data['id_sc']}.json", 'w', encoding='utf-8') as file: json.dump(data, file, ensure_ascii=False, indent=4) 
    else: 
        with open(f"users/{db_data['id_sc']}.json", 'a', encoding='utf-8') as file: json.dump(data, file, ensure_ascii=False, indent=4)