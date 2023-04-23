import serial
from struct import Struct


class Measurement:
    def __init__(self, d):
        self.d = d

        self.invalid = 0x8000 & d != 0
        self.strength_warn = 0x4000  & d != 0

        self.distance = d & 0x3FFF if not self.invalid else 0
        self.strength = d >> 16


class Lidar:
    format = "<BHLLLLH"

    def __init__(self, port):
        self.ser = serial.Serial(port, 460800, exclusive=True, timeout=2)
        self.ser.setDTR(False)
        self.ser.setRTS(False)

    def iter_measurements(self):
        fmt = Struct(self.format)
        while True:
            # Wait for start-of-packet
            # while self.ser.read() != b'\xfa':
            #     pass
            # Wait for start-of-packet
            self.ser.read_until(b"\xfa")
            dat = self.ser.read(21)
            if len(dat) != 21:
                raise Exception("Didn't get expected data. Is the lidar connected, spinning, and are you *sure* you have the right serial port?")

            dat = fmt.unpack(dat)
            # print(dat)
            ang = (dat[0] - 160) * 4
            rpm = dat[1] / 64

            yield (ang, rpm, Measurement(dat[2]))
            yield (ang + 1, rpm, Measurement(dat[3]))
            yield (ang + 2, rpm, Measurement(dat[4]))
            yield (ang + 3, rpm, Measurement(dat[5]))


if __name__ == "__main__":
    l = Lidar("COM5")
    
    for (ang, rpm, meas) in l.iter_measurements():
        if ang == 0:
            print(meas.distance)

