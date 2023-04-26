import asyncio
import copy
import queue
from threading import Thread
from typing import Sequence
import rplidar_parse
from web import sio
from aio import el


class API:
    lidar_thread = None
    scan_queue = queue.Queue()
    
    def __init__(self, loop):
        self.loop = loop
        self.lidar_t = Thread(target=self._read_lidar_thread, daemon=True).start()
        
    
    def run_main(self, main_fn):
        self.user_main = main_fn
        self.user_t = Thread(target=main_fn, daemon=True).start()


    def _read_lidar_thread(self):
        l = rplidar_parse.Lidar()

        scan = {
            "rpm": 0,
            "points": [100 for _ in range(360)]
        }

        for angle, distance in l:
            scan["points"][angle] = distance

            if angle == 359:
                self.scan_queue.put(copy.deepcopy(scan))
                self._emit_lidar("scan", copy.deepcopy(scan))
    
    def scans(self):
        return iter(self.scan_queue, None)
    
    def exit(self):
        return iter(self.scan_queue, None)

    def lidar_annotate(self, highlight: Sequence[int], lines: Sequence[Sequence[float]], points: Sequence[Sequence[float]]):
        annotations = {
            "highlights": highlight,
            "lines": lines,
            "points": points,
        }
        self._emit_lidar("annotations", annotations)
    
    def _emit_lidar(self, evt, data):
        asyncio.run_coroutine_threadsafe(sio.emit(evt, data, namespace="/lidar"), self.loop)

api = API(el)