from threading import Thread
from aiohttp import web
import socketio
import asyncio
import rplidar_parse

sio = socketio.AsyncServer()
app = web.Application()
sio.attach(app, "/api")

async def index(request):
    """Serve the client-side application."""
    with open('index.html') as f:
        return web.Response(text=f.read(), content_type='text/html')

class LidarNamespace(socketio.AsyncNamespace):

    def __init__(self, namespace):
        super().__init__(namespace)
        

    def read_lidar_thread(self, el):
        print("Starting lidar thread")
        l = rplidar_parse.Lidar("COM8")

        scan = {
            "rpm": 0,
            "points": [100 for _ in range(360)]
        }

        for angle, distance in l:
            p = scan["points"][angle] = distance

            if angle == 359:
                t = asyncio.run_coroutine_threadsafe(self.emit("scan", scan, namespace="/lidar"), el)
                t.result(timeout=3)                

    def on_connect(self, sid, environ):
        if not hasattr(self, "t"):
            el = asyncio.get_running_loop()
            self.t = Thread(target=self.read_lidar_thread, daemon=True, args=[el]).start()

        print("lidar connect")

    def on_disconnect(self, sid):
        print("lidar disconnect")


# app.router.add_static('/static', 'static')
app.router.add_get('/', index)
sio.register_namespace(LidarNamespace("/lidar"))

if __name__ == '__main__':
    web.run_app(app, host="localhost", port=4000)
