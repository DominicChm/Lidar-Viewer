from time import sleep
from api import API, api


def main():
    while True:
        api.lidar_annotate(
            highlight=[0, 90, 180, 270],
            lines=[[0, 0, 10000, 10000]],
            points=[[100, 100]],
        )
        sleep(1)
