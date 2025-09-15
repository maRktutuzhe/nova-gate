import fdb
from app.config import get_config

def get_db_login_data(handler, params):
    config = get_config()
    db_path = config.get('databases', 'db0_path')
    db_user = config.get('databases', 'db0_user')
    db_password = config.get('databases', 'db0_password')
    db_charset = config.get('databases', 'db0_charset')

    try:
        conn = fdb.connect(
            dsn=db_path,
            user=db_user,
            password=db_password,
            charset=db_charset
        )
    except Exception as e:
        return False, handler.send_answer(500, {"error_code": 1, "message": f"Ошибка подключения к БД: {e}"})

    try:
        login = params.get("login")
        password = params.get("pass")
        sql = "SELECT * FROM w3_auth_mon('%s', '%s')" % (login, password)

        cur = conn.cursor()
        cur.execute(sql)
        result = [dict(zip([d[0].lower() for d in cur.description], row)) for row in cur.fetchall()]
        return True, result
    except Exception as e:
        return False, handler.send_answer(500, {"error_code": 1, "message": f"Ошибка выполнения SQL: {e}"})
    finally:
        conn.close()
