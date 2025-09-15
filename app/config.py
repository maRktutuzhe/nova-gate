import os
import configparser

def get_config():
    config_file_name = "webtest.ini"
    if not os.path.isfile(config_file_name):
        return None
    config = configparser.ConfigParser()
    config.read(config_file_name)
    return config
