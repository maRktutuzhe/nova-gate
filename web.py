from http.server import HTTPServer, BaseHTTPRequestHandler

class MyHTTPRequestHandler(BaseHTTPRequestHandler):
    def send_answer(self, status: int, js: dict):
        answer = json.dumps(js, indent=4)
        self.send_response(status)
        self.send_header(keyword='Content-Type', value='application/json;charset=utf-8')
        self.end_headers()
        self.wfile.write(answer.encode('utf-8'))

    def router(url):
        part1, part2 = url.split('web/')
        print('part2', part2)
        print("ПОПАЛИ КУДА НАДО")
        # result = {"error_code": 0, "message": part2}
        # response_helper.send_answer( 200, result)
        self.send_answer(200, {"error_code": 0, "message": part2})
    