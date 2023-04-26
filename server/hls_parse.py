import array
import serial
from time import sleep
from struct import Struct, pack, unpack_from
from collections import namedtuple
import serial.tools.list_ports

def id_lidar():
    desired_vid = 1027
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        if p.vid == desired_vid:
            return p.name
        
    raise RuntimeError("The expected LIDAR USB-Serial USB bridge was not found. If you're using something else, specify the port in the LIDAR constructor")

def checksum(packet):
    c = 0
    for b in packet[:-2]:
        c += b
    return (0xFF - c) & 0xFF, packet[-1]

class Lidar:
    fmt = Struct("<BBHHHxxHHxxHHxxHHxxHHxxHHxxxB")

    def __init__(self, port=id_lidar()):
        self.ser = serial.Serial(port, 230400, exclusive=True, timeout=5)
    
    def __iter__(self):
        # Start scanning
        self.ser.write(b'b')
        self.ser.reset_input_buffer()

        buf = memoryview(bytearray([0xFA] * 42))

        while True:
            self.ser.read_until(b'\xFA')
            self.ser.readinto(buf[1:])

            actual, expected = checksum(buf)
            if actual != expected:
                print(self.ser.in_waiting)
                print("Got a corrupt packet!")
                continue

            [_, degree, rpm, *readings, chk] = self.fmt.unpack(buf)

            base_angle = (degree - 160) * 6
            rpm /= 10

            for i in range(0, len(readings), 2):
                # intensity = readings[i]
                distance = readings[i+1]
                angle = base_angle + i // 2

                yield angle, distance

            # print(self.ser.in_waiting)

        

if __name__ == "__main__":
    l = Lidar()

    for angle, distance in l:
        print(angle, distance)

