# -*- coding: utf-8 -*-
import configparser
import os
import fdb
import zipfile
import datetime
from threading import Lock, get_ident
import pickle
import shutil

IniFileName = 'HTTPSGate.ini'
TemporaryBlocked = 'temporary_blocked.pkl'

BLOCK_COUNTER = 3
BLOCK_PERIOD = 10 * 60

LogFileLock = Lock()
TemporaryBlockedLock = Lock()

config = configparser.ConfigParser()
config.read(IniFileName)

def get_client_ip(self):
    # Проверяем наличие заголовка X-Forwarded-For
    x_forwarded_for = self.headers.get('X-Forwarded-For')
    if x_forwarded_for:
        # Обычно первое значение является настоящим IP клиента
        return x_forwarded_for.split(',')[0].strip()
    else:
        # Если заголовок отсутствует, используем стандартный адрес клиента
        return self.client_address[0] 

def is_temporary_blocked(address: str) -> bool:
    if not os.path.isfile(TemporaryBlocked):
        return False
    TemporaryBlockedLock.acquire()
    try:
        loaded_dict = {}
        with open(TemporaryBlocked, 'rb') as f:
            loaded_dict = dict(pickle.load(f))
        if address not in loaded_dict.keys():
            return False
        info = dict(loaded_dict[address])
        res = info["counter"] >= BLOCK_COUNTER and info["dt"] > datetime.datetime.now()
        b = False
        r = {}
        for a in loaded_dict:
            if loaded_dict[a]["dt"] < datetime.datetime.now():
                continue
            r[a] = loaded_dict[a]
            b = True
        if b:
            with open(TemporaryBlocked, 'wb') as f:
                pickle.dump(r, f)
        return res
    finally:
        TemporaryBlockedLock.release()


def get_temporary_blocked() -> dict:
    if not os.path.isfile(TemporaryBlocked):
        return {}
    loaded_dict = {}
    with open(TemporaryBlocked, 'rb') as f:
        loaded_dict = dict(pickle.load(f))
    return loaded_dict

def temporary_block(address: str):
    if not os.path.isfile(TemporaryBlocked):
        with open(TemporaryBlocked, 'wb') as f:
            pickle.dump({address: {"dt": datetime.datetime.now() + datetime.timedelta(seconds=BLOCK_PERIOD), "counter": 1}}, f)
        return
    loaded_dict = {}
    with open(TemporaryBlocked, 'rb') as f:
        loaded_dict = dict(pickle.load(f))
    if address not in loaded_dict:
        loaded_dict[address] = {"dt": datetime.datetime.now() + datetime.timedelta(seconds=BLOCK_PERIOD), "counter": 1}
        with open(TemporaryBlocked, 'wb') as f:
            pickle.dump(loaded_dict, f)
        return
    if loaded_dict[address]["dt"] > datetime.datetime.now():
        loaded_dict[address]["counter"] += 1
        loaded_dict[address]["dt"] = datetime.datetime.now() + datetime.timedelta(seconds=BLOCK_PERIOD)
    else:
        loaded_dict[address] = {"dt": datetime.datetime.now() + datetime.timedelta(seconds=BLOCK_PERIOD), "counter": 1}
    with open(TemporaryBlocked, 'wb') as f:
        pickle.dump(loaded_dict, f)


def save_config(config: configparser.ConfigParser, path: str):
    with open(path, 'w') as configfile:
        config.write(configfile)
        
def save_config_key(config: configparser.ConfigParser, path: str):
    with open(path, 'w') as configfile:
        config.write(configfile)        


def prepare_sql_string(s: str) -> str:
    return s.replace("'", "''")


def get_db_connection(db_path: str, db_user: str = "SYSDBA", db_password: str = "masterkey", db_charset: str = "utf-8") -> fdb.Connection:
    return fdb.connect(dsn=db_path, user=db_user, password=db_password, charset=db_charset, utf8params=True)


def execute_sql_query(sql: str, project_name: str,db_connection: fdb.Connection) -> list:
    try:
        cur = db_connection.cursor()
        cur.execute(sql)
        return cur.fetchallmap()
        db_connection.cummit()
    except Exception as err:
        write_log("Project %s: %s" % (project_name, str(err)))
        return []


def is_integer(s: str) -> bool:
    try:
        i = int(s)
        return True
    except ValueError:
        return False


def write_log(s, project_name: str = "httpsgate"):
    s = str(s)
    log_file = "%s_error.log" % project_name.lower()
    with LogFileLock:
        if os.path.isfile(log_file) and FileSize(log_file) > 1024 * 1024:
            if not os.path.exists("LOGS"):
                os.makedirs("LOGS")
            new_file_name = "LOGS" + os.sep + project_name + "_" + datetime.datetime.strftime(datetime.datetime.today(), '%y_%m_%d_%H_%M_%S.log')
            shutil.copyfile(log_file, new_file_name)
            os.remove(log_file)
    with LogFileLock, open(log_file, 'a') as file:
        try:
            file.write("%s %s: %s\n" % (datetime.datetime.now().strftime("%y.%m.%d %H:%M:%S"), get_ident(), s))
        except:
            pass
    try:
        print(s)
    except Exception as err:
        print("WriteLog: ", err, '\n', bytearray(s))

# возвращает размер файла в байтах или -1, если файл не найден
def FileSize(fileName: str):
    return os.path.getsize(fileName)


# процедура архивирующая файл - аргуметы - название файла для архивации и имя нового архива
def ZIP(arFilename: str, arSaveTo: str):
    try:
        zipFile = zipfile.ZipFile(arSaveTo, 'w')
        zipFile.write(arFilename)
        zipFile.close()
        return True
    except Exception as err:
        print(err)
        return False

