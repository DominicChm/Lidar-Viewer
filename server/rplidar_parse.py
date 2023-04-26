import array
import serial
from time import sleep
from struct import Struct, pack, unpack_from
from collections import namedtuple
import serial.tools.list_ports

def id_rplidar():
    desired_vid = 4292
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        if p.vid == desired_vid:
            return p.name
        
    raise RuntimeError("The expected LIDAR USB-Serial USB bridge was not found. If you're using something else, specify the port in the LIDAR constructor")

def checksum(packet):
    c = 0
    for b in packet:
        c ^= b
    return pack("B", c)


def parse_angle(w, last_w, i, th_corr):
    return w + i * (w - last_w + (360 if last_w > w else 0)) / 32.0 # - th_corr # Don't care enough to debug this.


class Lidar:
    RPInfo = namedtuple("RPInfo", ["model", "fw_minor", "fw_major", "hardware", "serial_number"])
    RPHealth = namedtuple("RPHealth", ["status", "error_code"])
    RPScanRate = namedtuple("RPScanRate", ["standard_period_us", "express_period_us"])
    
    cabin_fmt = Struct("<HHB")

    # Cache lidar state.
    info = None
    
    def __init__(self, port=id_rplidar()):
        self.ser = serial.Serial(port, 115200, exclusive=True, timeout=5)
        self.set_motor(True)
        self.req_reset()
        self.ser.reset_input_buffer()
    

    def req(self, command, data=None):
        b = pack("<BB", 0xA5, command)

        if data is not None:
            b += pack("<B", len(data))
            b += data
            b += checksum(b)
        self.ser.write(b)

    def read_struct(self, fmt_str):
        fmt = Struct(fmt_str)
        dat = self.ser.read(fmt.size)

        if len(dat) != fmt.size:
            raise Exception("Didn't get expected data. Is the lidar connected, spinning, and are you *sure* you have the right serial port?")

        return fmt.unpack(dat)

    def read_into(self, fmt_str, tuple_class):
        return tuple_class(*self.read_struct(fmt_str))
    
    def read_descriptor(self, assert_multi=None, assert_len=None, assert_dtype=None):
        """Reads an RPLidar descriptor from the opened serial port. Optionally checks for validity"""

        [start_flag_1, start_flag_2, data_len, data_type] = self.read_struct("<BBLB")
        
        assert start_flag_1 == 0xA5, "Incorrect descriptor start flag 1"
        assert start_flag_2 == 0x5A, "Incorrect descriptor start flag 2"

        is_multi_response = (data_len & 0xC0000000) != 0
        data_len = data_len & 0x3FFFFFFF

        assert assert_multi is None or assert_multi == is_multi_response, \
            f"The descriptor's multi-message field doesn't match what was expected! Expected: {assert_multi}; Got: {is_multi_response}"
        assert assert_len is None or assert_len == data_len, \
            f"The descriptor's data length doesn't match what was expected! Expected: {assert_len}; Got: {data_len}"
        assert assert_dtype is None or assert_dtype == data_type, \
            f"The descriptor's data type byte doesn't match what was expected! Expected: {assert_dtype}; Got: {data_type}"

        return (is_multi_response, data_len, data_type)
    
    def set_motor(self, state):
        self.ser.dtr = not state

    def get_health(self):
        self.req(0x52)
        self.read_descriptor(False, 3, 0x06)

        return self.read_into("<BH", self.RPHealth)

    def get_info(self):
        if self.info is not None:
            return self.info

        self.req(0x50)
        self.read_descriptor(False, 20, 0x04)

        self.info = self.read_into("<BBBB16s", self.RPInfo)

        return self.info

    def req_stop(self):
        self.req(0x25)
        self.set_motor(False)

    def req_reset(self):
        # Reset internal state
        self.sample_rate = None
        self.info = None

        self.req(0x40)

        # Wait for the startup message.
        for _ in range(3):
            while True:
                b = self.ser.read(1)

                if b == b'': # Timeout. Reset.
                    print("Sending additional reset...")
                    self.req(0x40)

                elif b == b"\n":
                    break
    
    # Many, many ugly hacks.
    # I really wish python had c++ bitfields :(
    # Or... like... the rplidar protocol wasn't dumb >:(
    def iter_express(self):
        # Initialize scan
        self.req(0x82, pack("<BL", 0x00, 0))
        self.read_descriptor(True, 0x54, 0x82)

        # Start parsing scan
        start_angle_last = None
        last_angle = 0

        # This is all a dirty hack. I know it looks bad. Sorry :/
        # This protocol is very annoying to parse.
        # Also Python's `bytes` object is sooooo annoying.
        while True:
            # Parse start bytes, restarting if there's a mismatch.
            s1 = int.from_bytes(self.ser.read(), "little")

            if s1 & 0xF0 != 0xA0:
                continue

            s2 = int.from_bytes(self.ser.read(), "little")

            if s2 & 0xF0 != 0x50:
                continue
            
            chk = ((s2 & 0x0F) << 4) | (s1 & 0x0F) 

            # Start bytes read and parsed. We can be reasonably sure we have a packet.
            # Receive the rest of the packet
            
            data = self.ser.read(82)
            if chk != checksum(data):
                #print("LIDAR checksum error!")
                ##continue
                pass

            # Parse angle and the start bit
            [start_angle] = unpack_from("<H", data)
            is_start = start_angle & 0x8000 != 0
            start_angle = (start_angle & 0x7FFF) / 64.0
            
            if(is_start):
                print("Express scan Start")

            cabins = [self.cabin_fmt.unpack_from(data, i) for i in range(2, len(data), 5)]

            for i, [d1, d2, th_base] in enumerate(cabins):
                thoff_1 = float((((d1 << 4) | (th_base & 0x0F)) & 0x3F)) / 8.
                thoff_2 = float((((d2 << 4) | (th_base & 0xF0)) & 0x3F)) / 8.
                d1 >>= 2
                d2 >>= 2

                # Constrain angles to be ints. This discards some data and precision, but whatever.
                th1 = int(parse_angle(start_angle, start_angle_last or 0, 2*i, thoff_1)) % 360
                th2 = int(parse_angle(start_angle, start_angle_last or 0, 2*i + 1, thoff_2 )) % 360

                if th1 != last_angle:
                    yield th1, d1
                    last_angle = th1

                if th2 != last_angle:
                    yield th2, d2
                    last_angle = th2

            
            start_angle_last = start_angle

    def sync_with_lidar(self):
        for i in range(5):
            try:
                self.get_info()
                return
            except AssertionError: # Look specifically for errors caused by descriptor verification
                print(f"Sync {i} failed because unexpected data was received Will try again.")
                self.req_reset()
        
        raise ConnectionError("Not able to sync with LIDAR after 5 retries. Check connections.")
    
    def __iter__(self):
        self.sync_with_lidar()
        print(self.get_info())
        print(self.get_health())
        
        self.set_motor(True)
        return self.iter_express()

if __name__ == "__main__":
    l = Lidar()
    # sleep(5)
    for angle, distance in l:
        print(angle, distance)

