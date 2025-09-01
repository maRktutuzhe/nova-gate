# -*- coding: utf-8 -*-
import lib
import mqtt_client
import web
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from lib import (write_log, get_db_connection, execute_sql_query, prepare_sql_string, is_integer, save_config, save_config_key,
                 is_temporary_blocked, temporary_block, ZIP, get_client_ip)
import datetime
import json
import jwt
import os
import fdb
from typing import List, Optional
import uuid
import configparser
import ftplib

# mqtt_client.start_mqtt('5')

absFilePath = os.path.abspath(__file__)
server_path, _ = os.path.split(absFilePath)
certs_path = server_path + os.sep + 'certs'


class MyHTTPRequestHandler(BaseHTTPRequestHandler):

    DT_FORMAT = "%Y-%m-%d %H:%M:%S"
    PROC_ARCHLOG = "archlog"
    PROC_PING = "ping"
    PROC_MQTT = "mqtt_last"
    PROC_WEB = "web"
    PROC_PINGSERVER = "pingserver"
    PROC_PROCUPDATEALL = "procupdateall"
    PROC_REGISTER = "register"
    PROC_NEW_TOKEN = "new_token"
    PROC_SECRETUPDATE = "secretupdate"
    PROC_PROCEDURES = "procedures"
    service_procedures = [
        PROC_ARCHLOG,
        PROC_PING,
        PROC_MQTT,
        PROC_WEB,
        PROC_PINGSERVER,
        PROC_PROCUPDATEALL,
        PROC_REGISTER,
        PROC_NEW_TOKEN,
        PROC_SECRETUPDATE
    ]
    RESULT_ERROR_CODE = "error_code"
    RESULT_SECRET = "secret"
    RESULT_OPENED_PROCEDURES = "opened_procedures"
    RESULT_EXPIRED_ACCESS_S = "expired_acces_s"
    RESULT_EXPIRED_REFRESH_S = "expired_refresh_s"
    RESULT_SC_ID = "sc_id"
    REQUIRED_FIELDS = {
        PROC_REGISTER: [
              RESULT_ERROR_CODE
            , RESULT_SECRET
            , RESULT_OPENED_PROCEDURES
            , RESULT_EXPIRED_ACCESS_S
            , RESULT_EXPIRED_REFRESH_S
            , RESULT_SC_ID
        ]
    }
    ERROR_CODE_OK = 0
    BEARER_PREFIX = "Bearer "
    JWT_SECTION_PREFIX = "jwt_"

    def mqtt_last(self, project_name: str):
        if mqtt_client.last_message is None:
            self.send_answer(200, {"error_code": 1, "message": "no data yet"})
        else:
            self.send_answer(200, {"error_code": 0, "message": mqtt_client.last_message})
    
    def is_web(self, path_url: str) -> bool:
        url_prefix = lib.config["settings"]["url_prefix"]
        if path_url.lower().startswith(url_prefix + self.PROC_WEB):
            return True
        else:
            return False

    def send_answer(self, status: int, js: dict, cookies=None):
        answer = json.dumps(js, indent=4, ensure_ascii=False)
        self.send_response(status)
        self.send_header(keyword='Content-Type', value='application/json;charset=utf-8')
        if cookies:
            for cookie in cookies:
                self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(answer.encode('utf-8'))

    def get_config(self, project_name: str) -> Optional[configparser.ConfigParser]:
        config_file_name = "%s.ini" % project_name
        if not os.path.isfile(config_file_name):
            return None
        config = configparser.ConfigParser()
        config.read(config_file_name)
        return config
        
    def get_config_key(self, project_name: str) -> Optional[configparser.ConfigParser]:
        config_file_name = "%s_key.ini" % project_name
        if not os.path.isfile(config_file_name):
            return None
        config = configparser.ConfigParser()
        config.read(config_file_name)
        return config        

    def save_config(self, config: configparser.ConfigParser, project_name: str):
        config_file_name = "%s.ini" % project_name
        with open(config_file_name, 'w') as configfile:
            config.write(configfile)
            
    def save_config_key(self, config: configparser.ConfigParser, project_name: str):
        config_file_name = "%s_key.ini" % project_name
        with open(config_file_name, 'w') as configfile:
            config.write(configfile)

    def get_token(self, project_name: str, secret: str, login: str, name: str, dt: datetime.datetime, expired_s: int) -> str:
        current_token_valid = False
        expired_s_name = "%s_expire_s" % name
        token_name = "%s_token" % name
        exp_name = "%s_exp" % name
        salt_name = "%s_salt" % name
        section_login = "%s%s" % (self.JWT_SECTION_PREFIX, login)
        dt_exp = dt + datetime.timedelta(seconds=expired_s)

        config_file_name = "%s_key.ini" % project_name
        config = configparser.ConfigParser()
        config.read(config_file_name)
        if section_login in config and token_name in config[section_login].keys():
            if exp_name in config[section_login].keys():
                if datetime.datetime.strptime(config[section_login][exp_name], self.DT_FORMAT) > dt:
                    current_token_valid = True
                    current_token_valid = False
        if current_token_valid:
            return config[section_login][token_name]
        if section_login not in config:
            config.add_section(section_login)
        config[section_login]["secret"] = secret
        #config.remove_option(section, "refresh_salt")
        salt = uuid.uuid4().hex
        token = jwt.encode(
            payload={
                "iis": "SvoyClub",
                "sub": "httpsgate",
                "exp": dt_exp.strftime(self.DT_FORMAT)
            },
            key=secret + salt,
            algorithm="HS256",
        )
        config[section_login][exp_name] = dt_exp.strftime(self.DT_FORMAT)
        config[section_login][salt_name] = salt
        config[section_login][token_name] = token
        config[section_login][expired_s_name] = str(expired_s)
        save_config_key(config, config_file_name)
        return token

    def get_db_params(self, project_name: str, db_index: int = 0) -> Optional[dict]:
        config = configparser.ConfigParser()
        config.read("%s.ini" % project_name)
        if "databases" not in config:
            return None
        key_db_path = "db%d_path" % db_index
        key_db_user = "db%d_user" % db_index
        key_db_password = "db%d_password" % db_index
        key_db_charset = "db%d_charset" % db_index
        if key_db_path not in config["databases"]:
            return None
        return {
            "db_path": config["databases"][key_db_path],
            "db_user": config["databases"][key_db_user] if key_db_user in config["databases"] else "SYSDBA",
            "db_password": config["databases"][key_db_password] if key_db_password in config["databases"] else "masterkey",
            "db_charset": config["databases"][key_db_charset] if key_db_charset in config["databases"] else "utf-8"
        }

    def get_connection(self, db_parans: dict) -> fdb.Connection:
        return get_db_connection(
            db_parans["db_path"],
            db_parans["db_user"],
            db_parans["db_password"],
            db_parans["db_charset"]
        )

    def get_db_connection(self, project_name: str, db_index: int = 0) -> Optional[fdb.Connection]:
        db_params = self.get_db_params(project_name, db_index)
        if db_params is None:
            return None
        return self.get_connection(db_params)

    # процедура возвращает первое обязательное поле не указанное в ответе
    def get_not_existing_key(self, first_record: dict, procedure: str) -> Optional[str]:
        required_fields = self.REQUIRED_FIELDS[procedure]
        for field in required_fields:
            if field not in first_record:
                return field
        return None

    # сохранение данных по проекту и пользователю
    def save_user_data(self, project_name: str, login: str, key: str, value: str) -> None:
        config = self.get_config_key(project_name)
        section = "%s%s" % (self.JWT_SECTION_PREFIX, login)
        if section not in config.sections():
            config.add_section(section)
        config[section][key] = value
        self.save_config_key(config, project_name)

    # процедура регистрации пользователя проверяет только login и password в первой БД проекта
    # из БД должен прийти положительный ответ, а так же secret для пользователя, он будет возвращён пользователю
    def register(self, js: dict, project_name: str):
        result = {}
        status = 400
        try:
            if "login" not in js or "pass" not in js:
                write_log("Нет пары login, pass в запросе register.", project_name)
                status = 400
                #temporary_block(self.client_address[0])
                temporary_block(get_client_ip(self))
                return
            if str(js["login"]).strip() == "" or str(js["pass"]).strip() == "":
                write_log("Пустой login или pass в запросе register.", project_name)
                status = 400
                #temporary_block(self.client_address[0])
                temporary_block(get_client_ip(self))
                return
            db_params = self.get_db_params(project_name, 0)
            if db_params is None:
                write_log("Не удалось получить параметры подключения к БД #%d для проекта %s." % (0, project_name), project_name)
                status = 500
                return
            connection = self.get_connection(db_params)
            login = prepare_sql_string(js["login"])
            password = prepare_sql_string(js["pass"])
            sql = "select * from register('%s', '%s')" % (login, password)
            query_result = execute_sql_query(sql, project_name, connection)
            connection.commit()
            if query_result is None or len(query_result) == 0:
                write_log("Процедура register не вернула результат.", project_name)
                status = 500
                return
            first_record = query_result[0]
            not_existing_key = self.get_not_existing_key(first_record, "register")
            if not_existing_key:
                write_log("Процедура register не вернула %s." % not_existing_key, project_name)
                status = 500
                return
            if not is_integer(first_record[self.RESULT_ERROR_CODE]):
                write_log("В результате вызова register, error_code не является целым числом.", project_name)
                status = 500
                return
            error_code = int(first_record[self.RESULT_ERROR_CODE])
            if error_code != self.ERROR_CODE_OK:
                #temporary_block(self.client_address[0])
                temporary_block(get_client_ip(self))
                status = 401
                return
            if not is_integer(first_record[self.RESULT_EXPIRED_ACCESS_S]):
                write_log("В результате вызова register, %s не является целым числом." % self.RESULT_EXPIRED_ACCESS_S, project_name)
                status = 500
                return
            if not is_integer(first_record[self.RESULT_EXPIRED_REFRESH_S]):
                write_log("В результате вызова register, %s не является целым числом." % self.RESULT_EXPIRED_REFRESH_S, project_name)
                status = 500
                return
            if not is_integer(first_record[self.RESULT_SC_ID]):
                write_log("В результате вызова register, %s не является целым числом." % self.RESULT_SC_ID, project_name)
                status = 500
                return
            opened_procedures = first_record[self.RESULT_OPENED_PROCEDURES]
            sc_id = int(first_record[self.RESULT_SC_ID])
            self.save_user_data(project_name, login, self.RESULT_SC_ID, str(sc_id))
            self.save_user_data(project_name, login, self.RESULT_OPENED_PROCEDURES, opened_procedures)
            expired_access_s = first_record[self.RESULT_EXPIRED_ACCESS_S]
            expired_refresh_s = first_record[self.RESULT_EXPIRED_REFRESH_S]
            secret = str(first_record[self.RESULT_SECRET])
            dt = datetime.datetime.now()
            result["secret"] = secret
            result["access_token"] = self.get_token(
                project_name,
                secret,
                login,
                'access',
                dt,
                expired_access_s
            )
            result["refresh_token"] = self.get_token(
                project_name,
                secret,
                login,
                'refresh',
                dt,
                expired_refresh_s
            )
            status = 200
        finally:
            result["error_code"] = 0 if status == 200 else 1
            write_log("Answer: %d %s" % (status, json.dumps(result, indent=4)), project_name)
            self.send_answer(status, result)

    def new_tokens(self, js: dict, project_name: str):
        valid = True
        if valid and "refresh_token" not in js:
            valid = False
        login = ""
        config_file_name = "%s_key.ini" % project_name
        config = configparser.ConfigParser()
        if valid:
            refresh_token = js["refresh_token"]
            config.read(config_file_name)
            for section in config.sections():
                if section.startswith(self.JWT_SECTION_PREFIX) and "refresh_token" in config[section].keys():
                    if config[section]["refresh_token"] == refresh_token:
                        login = section[len(self.JWT_SECTION_PREFIX):]
                        if "refresh_exp" not in config[section].keys():
                            write_log("Нет периода действия refresh_token-а пользователя %s." % login, project_name)
                            valid = False
                            break
                        dt = datetime.datetime.now()
                        if valid and datetime.datetime.strptime(config[section]["refresh_exp"], self.DT_FORMAT) < dt:
                            write_log("refresh_token пользователя %s просрочен." % login, project_name)
                            valid = False
                        else:
                            write_log("Пользователь: %s" % login, project_name)
                            valid = True
                        break

        if not valid:
            self.send_answer(400, {})
            return
        section = "%s%s" % (self.JWT_SECTION_PREFIX, login)
        result = {}
        status = 400
        try:
            config.remove_option(section, "access_token")
            config.remove_option(section, "access_exp")
            config.remove_option(section, "access_salt")
            config.remove_option(section, "refresh_token")
            config.remove_option(section, "refresh_exp")
            config.remove_option(section, "refresh_salt")
            self.save_config_key(config, project_name)
            dt = datetime.datetime.now()
            result["access_token"] = self.get_token(
                project_name,
                config[section]["secret"],
                login,
                'access',
                dt,
                int(config[section]["access_expire_s"])
            )
            result["refresh_token"] = self.get_token(
                project_name,
                config[section]["secret"],
                login,
                'refresh',
                dt,
                int(config[section]["refresh_expire_s"])
            )
            status = 200
        finally:
            result["error_code"] = 0 if status == 200 else 1
            write_log("Answer: %d %s" % (status, json.dumps(result, indent=4)), project_name)
            self.send_answer(status, result)

    # проверка заголовка Authorization: Bearer <access_token>
    # словарь user_info заполняется информацией о пользователе
    def check_authorization(self, project_name: str, user_info: dict):
        # в указанном проекте/ini файле перебираю все разделы начинающиеся с jwt - ищу совпадающий access_token
        auth = False
        try:
            if "Authorization" not in self.headers:
                return
            if not str(self.headers["Authorization"]).startswith(self.BEARER_PREFIX):
                return
            access_token = str(self.headers["Authorization"])[len(self.BEARER_PREFIX):]
            config_file_name = "%s_key.ini" % project_name
            config = configparser.ConfigParser()
            config.read(config_file_name)

            for section in config.sections():
                if section.startswith(self.JWT_SECTION_PREFIX) and "access_token" in config[section].keys():
                    if config[section]["access_token"] == access_token:
                        login = section[len(self.JWT_SECTION_PREFIX):]
                        if "access_exp" not in config[section].keys():
                            write_log("Нет периода действия access_exp-а пользователя %s." % login, project_name)
                            auth = False
                            break
                        dt = datetime.datetime.now()
                        if datetime.datetime.strptime(config[section]["access_exp"], self.DT_FORMAT) < dt:
                            write_log("access_exp пользователя %s просрочен." % login, project_name)
                            auth = False
                        else:
                            write_log("Пользователь: %s" % login, project_name)
                            user_info["login"] = login
                            if "sc_id" in config[section]:
                                user_info["sc_id"] = int(config[section]["sc_id"])
                            else:
                                user_info["sc_id"] = -1
                            user_info["rights"] = []
                            if self.RESULT_OPENED_PROCEDURES in config[section].keys():
                                opened_procedures = config[section][self.RESULT_OPENED_PROCEDURES].split(',')
                                for opened_procedure in opened_procedures:
                                    user_info["rights"].append(opened_procedure.strip().lower())
                            auth = True
                        break
        finally:
            if not auth:
                write_log("Авторизация не пройдена", project_name)
            return auth

    def archlog(self, project_name: str, params: dict):
        result = {"files": [], "error_code": 1}
        status = 500
        try:
            files_to_zip = list(filter(lambda s: str(s).startswith(project_name) and str(s).endswith(".log"), os.listdir("LOGS")))
            for file in files_to_zip:
                if ZIP("LOGS" + os.sep + file, "LOGS" + os.sep + str(file).replace(".log", ".zip")):
                    os.remove("LOGS" + os.sep + file)

            files_to_ftp = list(filter(lambda s: str(s).startswith(project_name) and str(s).endswith(".zip"), os.listdir("LOGS")))
            if len(files_to_ftp) == 0:
                result["error_code"] = 0
                status = 200
                self.send_answer(status, result)
                return
            if "server" not in params or "port" not in params or "user" not in params or "password" not in params or "path" not in params:
                write_log("В запросе acrhlog необходимы параметры server, port, user, password, path.", project_name)
                result["error_code"] = 1
                status = 500
                self.send_answer(status, result)
                return

            ftp = ftplib.FTP()
            ftp.encoding = "utf-8"
            ftp.connect(host=params["server"], port=int(params["port"]))
            ftp.login(user=params["user"], passwd=params["password"])
            ftp.cwd(dirname=params["path"])

            for file in files_to_ftp:
                with open("LOGS" + os.sep + file, "rb") as f:
                    ftp.storbinary("STOR %s" % file, f)
                result["files"].append(file)
                os.remove("LOGS" + os.sep + file)

            ftp.close()
            result["error_code"] = 0
            self.send_answer(200, result)
        except Exception as err:
            write_log("archlog: %s" % str(err), project_name)
            self.send_answer(status, result)



    # получение списка ini файлов по указанному пути
    def get_projects(self, directory: str) -> List[str]:
        files = [f.lower() for f in os.listdir(directory)]
        ini_files = filter(lambda s: str(s).endswith('.ini'), files)
        project_ini_files = filter(lambda s: s != lib.IniFileName.lower(), ini_files)
        projects = list(map(lambda s: str(s)[:-4], project_ini_files))
        return projects

    # получение имени проекта из url
    def parse_project_name(self, path_url: str) -> Optional[str]:
        url_prefix = lib.config["settings"]["url_prefix"]
        write_log("url_prefix")
        write_log(url_prefix)
        if path_url.startswith(url_prefix):
            write_log("if")

            path_url = path_url[len(url_prefix):]
        path_url.strip("/")
        parts = path_url.split("/")

        return None if len(parts) != 2 else parts[0].lower()

    # получение имени проекта из url
    def parse_procedure_name(self, path_url: str) -> Optional[str]:
        url_prefix = lib.config["settings"]["url_prefix"]
        if path_url.startswith(url_prefix):
            path_url = path_url[len(url_prefix):]
        path_url.strip("/")
        parts = path_url.split("/")
        return None if len(parts) != 2 else parts[1].lower()

    def is_global_ping(self, path_url: str) -> bool:
        url_prefix = lib.config["settings"]["url_prefix"]
        return path_url.lower() == url_prefix + self.PROC_PING

    def is_global_archlog(self, path_url: str) -> bool:
        url_prefix = lib.config["settings"]["url_prefix"]
        return path_url.lower() == url_prefix + self.PROC_ARCHLOG

    def db_count(self, project_name: str) -> int:
        config = self.get_config(project_name)
        if "databases" not in config.sections():
            return 0
        i = 0
        while ("db%d_path" % i) in config["databases"].keys():
            i += 1
        return i

    def procedures_in_db(self, project_name: str, connection: fdb.Connection):
        sql = "SELECT RDB$PROCEDURE_NAME AS PROCNAME FROM RDB$PROCEDURES ORDER BY RDB$PROCEDURE_NAME"
        query_result = execute_sql_query(sql, project_name, connection)
        res = []
        for pr in query_result:
            res.append(pr["PROCNAME"].strip().lower())
        connection.commit()
        return res

    def get_procedure_params(self, project_name: str, connection: fdb.Connection, procedure_name: str, params: list):
        sql = ("select RDB$PARAMETER_NAME as PARAM_NAME from RDB$PROCEDURE_PARAMETERS "
               "where RDB$PROCEDURE_NAME = '%s' and RDB$PARAMETER_TYPE=0") % procedure_name.upper()
        query_result = execute_sql_query(sql, project_name, connection)
        for pr in query_result:
            params.append(pr["PARAM_NAME"].strip().lower())
        connection.commit()
        return True

    # сохранение информации о разрешённых процедурах в ini файл проекта
    def save_procedures_info(self, project_name: str, procedures_info: list):
        config_file_name = "%s.ini" % project_name
        config = configparser.ConfigParser()
        config.read(config_file_name)
        if "procedures" in config.sections():
            config.remove_section("procedures")
            self.save_config(config, project_name)
        config.add_section("procedures")
        config["procedures"]["count"] = str(len(procedures_info))
        for i in range(len(procedures_info)):
            config["procedures"]["proc%d_db_index" % i] = str(procedures_info[i]["db_index"])
            config["procedures"]["proc%d_procedure_name" % i] = str(procedures_info[i]["procedure_name"])
            config["procedures"]["proc%d_headers" % i] = str(procedures_info[i]["headers"])
            config["procedures"]["proc%d_loginput" % i] = str(procedures_info[i]["loginput"])
            config["procedures"]["proc%d_logdb" % i] = str(procedures_info[i]["logdb"])
            config["procedures"]["proc%d_logdatadb" % i] = str(procedures_info[i]["logdatadb"])
            config["procedures"]["proc%d_fields" % i] = str(procedures_info[i]["fields"])
        self.save_config(config, project_name)

    def procupdateall(self, params: dict, project_name: str):
        try:
            procedures = []
            procedures_info = []
            for db_index in range(self.db_count(project_name)):
                procedures_in_db = []
                db_params = self.get_db_params(project_name, db_index)
                connection = self.get_connection(db_params)
                if connection is None:
                    write_log("Не удалось подкючиться к БД № %d в проекте %s." % (db_index, project_name), project_name)
                    continue
                sql = "select * from procupdateall"
                query_result = execute_sql_query(sql, project_name, connection)
                if query_result is None or len(query_result) == 0:
                    write_log("Процедура procupdateall не вернула результат.", project_name)
                    continue
                for record in query_result:
                    procedure_name = str(record["procedure_name"]).strip().lower()
                    if procedure_name in procedures:
                        write_log("Процедура %s дублируется, пропускаем." % procedure_name, project_name)
                        continue
                    procedures_in_db.append({
                        "db_index": db_index,
                        "procedure_name": procedure_name,
                        "headers": record["headers"],
                        "loginput": record["loginput"],
                        "logdb": record["logdb"],
                        "logdatadb": record["logdatadb"]
                    })
                    procedures.append(procedure_name)
                all_procedures_in_db = self.procedures_in_db(project_name, connection)
                # для каждой процедуры в данной БД получаю список входных параметров
                for i in range(len(procedures_in_db)):
                    procedure_name = procedures_in_db[i]["procedure_name"]
                    if procedure_name not in all_procedures_in_db:
                        write_log("Процедура %s из procupdateall не найдена в БД № %d." % (procedure_name, db_index), project_name)
                        continue
                    procedure_fields = []
                    if not self.get_procedure_params(project_name, connection, procedure_name, procedure_fields):
                        write_log("Не удалось получить параметры процедуры %s в БД № %d." % (procedure_name, db_index), project_name)
                        continue
                    procedures_in_db[i]["fields"] = ','.join(procedure_fields)
                    procedures_info.append(procedures_in_db[i])
            self.save_procedures_info(project_name, procedures_info)
            js = {"error_code": 0, "procedures_info": procedures_info}
            write_log("Answer: %s" % str(js), project_name)
            self.send_answer(200, js)
        except Exception as err:
            js = {"error_code": 1, "error_message": str(err)}
            write_log("Answer: %s" % str(js), project_name)
            self.send_answer(500, js)

    def get_procedure_info(self, project_name: str, procedure_name: str) -> Optional[dict]:
        config = self.get_config(project_name)
        if "procedures" not in config.sections() or "count" not in config["procedures"].keys():
            return None
        for i in range(int(config["procedures"]["count"])):
            if ("proc%d_procedure_name" % i) in config["procedures"].keys():
                if config["procedures"]["proc%d_procedure_name" % i] == procedure_name:
                    return {
                        "db_index": int(config["procedures"]["proc%d_db_index" % i]),
                        "procedure_name": config["procedures"]["proc%d_procedure_name" % i],
                        "headers": config["procedures"]["proc%d_headers" % i],
                        "loginput": int(config["procedures"]["proc%d_loginput" % i]),
                        "logdb": int(config["procedures"]["proc%d_logdb" % i]),
                        "logdatadb": int(config["procedures"]["proc%d_logdatadb" % i]),
                        "fields": config["procedures"]["proc%d_fields" % i],
                    }
        return None

    def get_select_query(self, procedure_name: str, params: dict, fields: List[str]):
        sql = "select * from %s" % procedure_name
        if len(fields) > 0:
            sql += "("
            values = ""
            for field in fields:
                if values != "":
                    values += ", "
                if field in params.keys():
                    values += "'" + str(params[field]) + "'"
                else:
                    values += "null"
            sql += values
            sql += ")"
        return sql

    def parse_headers(self, project_name: str, str_headers: str) -> list:
        headers = str_headers.split(",")
        res = []
        for header in headers:
            header = header.strip()
            header = header.split("#")
            if len(header) == 0:
                write_log("Внезапно не удалось разобрать заголовок %s." % header, project_name)
                continue
            while len(header) < 3:
                header.append(header[-1])
            res.append(header)
        return list(map(lambda h: {"field_in_result": h[0], "field_in_header": h[1], "default": h[2]}, res))

    def get_header(self, project_name: str, data: dict, headers: List[dict]) -> dict:
        res = {h["field_in_header"]: h["default"] for h in headers}
        for field in data.keys():
            for header in headers:
                if str(field).lower() == str(header["field_in_result"]).lower():
                    res[header["field_in_header"]] = data[field]
        return res


    def process_user_query(self, project_name: str, procedure_name: str, params: dict):
        try:
            procedure_info = self.get_procedure_info(project_name, procedure_name)
            if procedure_info is None:
                write_log("Не найдена информация о процедуре %s в проекте %s." % (procedure_name, project_name), project_name)
                self.send_answer(500, {"error_code": 1})
                return
            loginput = int(procedure_info["loginput"]) > 0
            logdb = int(procedure_info["logdb"]) > 0
            logdatadb = int(procedure_info["logdatadb"]) > 0

            if loginput:
                write_log("Проект %s, запрос %s, параметры %s" % (project_name, project_name, str(params)), project_name)

            db_index = int(procedure_info["db_index"])
            db_params = self.get_db_params(project_name, db_index)
            if db_params is None:
                write_log("Не удалось получить параметры подключения к БД #%d для проекта %s." % (0, project_name), project_name)
                self.send_answer(500, {"error_code": 1})
                return
            connection = self.get_connection(db_params)
            if connection is None:
                write_log("Не удалось подкючиться к БД № %d в проекте %s." % (db_index, project_name), project_name)
                self.send_answer(500, {"error_code": 1})
                return

            sql = self.get_select_query(procedure_name, params, procedure_info["fields"].split(","))
            if logdb:
                write_log("Запрос к БД: %s" % sql)

            query_result = execute_sql_query(sql, project_name, connection)
            connection.commit()
            if query_result is None:
                write_log("Вызов процедуры %s завершился ошибкой." % procedure_name, project_name)
                self.send_answer(500, {"error_code": 1})
                return
            data = []
            header = {}
            ignore_in_result = []
            if len(query_result) > 0:
                first_record = query_result[0]
                headers = self.parse_headers(project_name, procedure_info["headers"])
                header = self.get_header(project_name, first_record, headers)
                ignore_in_result = [str(h["field_in_result"]).lower() for h in headers]

            for record in query_result:
                d = {}
                is_none = True
                for field in record:
                    field = str(field).lower()
                    if field in ignore_in_result:
                        continue
                    if isinstance(record[field], datetime.datetime):
                        d[field] = str(record[field].strftime(self.DT_FORMAT))
                    elif isinstance(record[field], float):
                        d[field] = record[field]
                    elif isinstance(record[field], int):
                        d[field] = record[field]
                    elif isinstance(record[field], str):
                        d[field] = record[field]
                    else:
                        d[field] = str(record[field])
                    if is_none and str(d[field]) != "None":
                        is_none = False
                if not is_none:
                    data.append(d)
            js = {"header": header, "data": data}
            if logdatadb:
                write_log("Answer: %s" % str(js), project_name)
            self.send_answer(200, js)
        except Exception as err:
            js = {"error_code": 1, "error_message": str(err)}
            write_log("Answer: %s" % str(js), project_name)
            self.send_answer(500, js)

    def ping(self, project_name: str):
        self.send_answer(200, {"error_code": 0})

    def pingserver(self, project_name: str):
        connection = self.get_db_connection(project_name, 0)
        if connection is None:
            write_log("Не удалось установить соединение с БД проекта %s." % project_name, project_name)
            self.send_answer(500, {"error_code": 1, "error_message": "Не удалось установить соединение с БД проекта %s." % project_name})
            return
        sql = "select * from pingserver"
        query_result = execute_sql_query(sql, project_name, connection)
        connection.commit()
        if query_result is None:
            write_log("Вызов процедуры ping в проекте %s завершился ошибкой." % project_name, project_name)
            self.send_answer(500, {"error_code": 1})
            return
        if len(query_result) == 0:
            write_log("Вызов процедуры ping в проекте %s не вернул результат." % project_name, project_name)
            self.send_answer(500, {"error_code": 1})
            return
        first_record = query_result[0]
        js = {}
        for field in first_record:
            field = str(field).lower()
            if isinstance(first_record[field], datetime.datetime):
                js[field] = str(first_record[field])
            elif isinstance(first_record[field], float):
                js[field] = first_record[field]
            elif isinstance(first_record[field], int):
                js[field] = first_record[field]
            elif isinstance(first_record[field], str):
                js[field] = first_record[field]
            else:
                js[field] = str(first_record[field])
        self.send_answer(200, js)

    def secretupdate(self, params: dict, project_name: str):
        self.send_answer(200, {"error_code": 0})

    def process_query(self, params: dict, path: str):
        url_path = path.strip().lower()
        url_prefix = lib.config["settings"]["url_prefix"]
        if not url_path.startswith(url_prefix):
            write_log("Запрос %s не начинается с нужного префикса." % url_path)
            return
        projects = self.get_projects(server_path)
        project_name = self.parse_project_name(url_path)
        procedure_name = self.parse_procedure_name(url_path)
        # команда /api/v2_1/sc/ping
        if self.is_global_ping(url_path):
            self.send_answer(200, {"error_code": 0})
            return
        if url_path == "/api/v2_1/sc/mqtt_last":
            write_log("mQtT")
            self.mqtt_last(project_name)
            return
        if self.is_web(url_path):
            web.router(self, path, params)
            return
        if self.is_global_archlog(url_path):
            if "server_secret" not in params or params["server_secret"] != lib.config["settings"]["secret"]:
                self.send_answer(401, {"error_code": 1})
                return
            self.archlog("httpsgate", params)
            return
        if project_name is None:
            write_log("URL: %s" % url_path)
            write_log("Из запроса %s не удалось получить название проекта." % url_path)
            return
        if project_name not in projects:
            write_log("Проекта %s нет в списке доступных проектов." % project_name)
            return
        if procedure_name in self.service_procedures:
            write_log("URL: %s" % url_path, project_name)
            # register не требует авторизации по токену
            if procedure_name == self.PROC_REGISTER:
                self.register(params, project_name)
                return

            user_info = {}
            if not self.check_authorization(project_name, user_info):
                js = {"error_code": 1}
                write_log("Answer: %s" % str(js), project_name)
                self.send_answer(403, js)
                #temporary_block(self.client_address[0])
                temporary_block(get_client_ip(self))
                return
            if "rights" not in user_info.keys() or procedure_name not in user_info["rights"]:
                js = {"error_code": 1}
                write_log("У пользователя нет разрешение на запуск %s.\nAnswer: %s" % (procedure_name, str(js)), project_name)
                self.send_answer(403, js)
                return
            if procedure_name == self.PROC_PING:
                self.ping(project_name)
            if procedure_name == self.PROC_PINGSERVER:
                self.pingserver(project_name)
            if procedure_name == self.PROC_NEW_TOKEN:
                self.new_tokens(params, project_name)
            if procedure_name == self.PROC_PROCUPDATEALL:
                self.procupdateall(params, project_name)
            if procedure_name == self.PROC_SECRETUPDATE:
                self.secretupdate(params, project_name)
            if procedure_name == self.PROC_ARCHLOG:
                self.archlog(project_name, params)
        else:
            user_info = {}
            if not self.check_authorization(project_name, user_info):
                js = {"error_code": 1}
                write_log("Answer: %s" % str(js), project_name)
                self.send_answer(403, js)
                #temporary_block(self.client_address[0])
                temporary_block(get_client_ip(self))
                return
            if "rights" not in user_info.keys() or self.PROC_PROCEDURES not in user_info["rights"]:
                js = {"error_code": 1}
                write_log("У пользователя нет разрешение на запуск %s.\nAnswer: %s" % (self.PROC_PROCEDURES, str(js)), project_name)
                self.send_answer(403, js)
                return
            params["sc_id"] = user_info["sc_id"]
            self.process_user_query(project_name, procedure_name, params)

    def do_POST(self):
        #if is_temporary_blocked(self.client_address[0]):
        if is_temporary_blocked(get_client_ip(self)):
            #write_log("Блокирован запрос от IP %s." % self.client_address)
            write_log("Блокирован запрос от IP %s." % get_client_ip(self))
            self.close_connection = True
            return

        if 'Content-Length' not in self.headers:
            write_log('В запросе нет Content-Length')
            self.close_connection = True
            return

        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length).decode()
        if "Authorization" in self.headers.keys():
            write_log("Header\n\t%s=%s" % ("Authorization", self.headers["Authorization"]))
        write_log(
            "Запрос:\n\tAddress: %s\n\tQuery: %s\n\tAuthorization: %s" % (
                #self.client_address,
                get_client_ip(self),
                body,
                self.headers.get("Authorization", "empty")
            )
        )
        try:
            params = json.loads(body)
            params = {key.lower(): value for key, value in params.items()}
            self.process_query(params, self.path)
        except Exception as err:
            write_log(err)

    def do_GET(self):
        pass


class ThreadingSimpleServer(ThreadingMixIn, HTTPServer):
    pass


if __name__ == '__main__':
    httpd = ThreadingSimpleServer(('0.0.0.0', int(lib.config['settings']['port'])), MyHTTPRequestHandler)
    #httpd.socket = ssl.wrap_socket(
    #    httpd.socket,
    #    keyfile=certs_path + os.sep + 'server.key',
    #    certfile=certs_path + os.sep + "server.cer",
    #    server_side=False
    #)
    write_log("Сервер запущен %s: %d" % ('0.0.0.0', int(lib.config['settings']['port'])))
    httpd.serve_forever()
