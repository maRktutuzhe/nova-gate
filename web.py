from http.server import HTTPServer, BaseHTTPRequestHandler
import json

class MyHTTPRequestHandler(BaseHTTPRequestHandler):
    def send_answer(self, status: int, js: dict):
        answer = json.dumps(js, indent=4)
        self.send_response(status)
        self.send_header(keyword='Content-Type', value='application/json;charset=utf-8')
        self.end_headers()
        self.wfile.write(answer.encode('utf-8'))

def router(handler: MyHTTPRequestHandler, url: str, params):


    if "web/" in url:
        _, part2 = url.split("web/", 1)
        print("part2", part2)
        if part2 == 'login':
            login(handler, params)
        else:
            handler.send_answer(200, {"error_code": 0, "message": part2})
    else:
        handler.send_answer(404, {"error_code": 1, "message": "not found"})
    
def login(handler: MyHTTPRequestHandler, params):

    print('params', params)

    if params["login"] == "user1" and params["pass"] == "pass1":
        user_id = 1
    elif params["login"] == "user2" and params["pass"] == "pass2":
        user_id = 2
    
    handler.send_answer(200, {"error_code": 0, "message": user_id})
