import array
import serial
from time import sleep
from struct import Struct, pack, unpack_from
from collections import namedtuple

def checksum(packet):
    c = 0
    for b in packet:
        c ^= b
    return pack("B", c)

cabin_fmt = Struct("<HHB")
def parse_cabin(bytes):
    cabin_fmt.unpack_from(bytes)

def parse_angle(w, last_w, i, th_corr):
    return w + i * (w - last_w + (360 if last_w > w else 0)) / 32.0 # - th_corr # Don't care enough to debug this.


class Lidar:
    RPInfo = namedtuple("RPInfo", ["model", "fw_minor", "fw_major", "hardware", "serial_number"])
    RPHealth = namedtuple("RPHealth", ["status", "error_code"])
    RPScanRate = namedtuple("RPScanRate", ["standard_period_us", "express_period_us"])
    
    is_initialized = False
    sample_rate = None
    info = None
    
    def __init__(self, port):
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

    def assert_fw_version(self, major, minor):
        model, fw_minor, fw_major, _, _ = self.get_info()

        if fw_major < major or fw_minor < minor:
            raise RuntimeError(f"Feature is only supported on FW versions {major}.{minor} and above. Connected lidar (model {model}) is on {fw_major}.{fw_minor}. Try updating the firmware.")
        
    def set_motor(self, state):
        self.ser.dtr = not state

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
    
    def get_sample_rate(self):
        self.assert_fw_version(1, 17)

        if self.sample_rate is not None:
            return self.sample_rate

        self.req(0x59)
        self.read_descriptor(False, 4, 0x15)

        self.sample_rate = self.read_into("<HH", self.RPScanRate)
        
        return self.sample_rate
    
    def get_conf(self):
        self.assert_fw_version(1, 24)
        raise NotImplementedError("Get conf currently not implemented")

        self.req(0x84, pack("<L", 0x70))
        self.read_descriptor(False, None, 0x20)
        print(self.read_struct("<LH"))

    def req_stop(self):
        self.req(0x25)
        self.set_motor(False)
        sleep(100 / 1000)

    def req_reset(self):
        # Reset internal state
        self.sample_rate = None
        self.info = None

        self.req(0x40)

        # Skip over the plaintext startup message.
        for _ in range(3):
            while True:
                b = self.ser.read(1)

                if b == b'': # Timeout. Reset the thing.
                    print("Sending additional reset...")
                    self.req(0x40)

                elif b == b"\n":
                    break

        print("Reset completed.")
    
    def req_express(self):
        """
        "Extended" packet express scans are not supported. 
        """
        print("Starting express scan")
        
        # Expect the extended packet mode.
        # Not documented properly, but 0x02 seems
        # to trigger extended mode.
        self.req(0x82, pack("<BL", 0x00, 0))
        dtype = self.read_descriptor(True, 0x54)[2]

        self.set_motor(True)
        if dtype == 0x82: # dtype for standard express scan
            return self.iter_express_packets
        elif dtype == 0x85: # dtype for dense express scan (Look at protocol 2.2)
            return self.iter_dense_express_packets
        else:
             raise RuntimeError("Unsupported scan type")

    # Many, many ugly hacks.
    # I really wish python had c++ bitfields :(
    # Or... like... the rplidar protocol wasn't dumb >:(
    def iter_express_packets(self):
        idx = 0
        a = array.array('B', [0] * 0x54)
        start_angle_last = None
        last_angle = 0
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
            # Start parsing the rest of the packet.
            
            data = self.ser.read(82)

            # Parse angle and the start bit
            [start_angle] = unpack_from("<H", data)
            is_start = start_angle & 0x8000 != 0
            start_angle = (start_angle & 0x7FFF) / 64.0
            
            if(is_start):
                print("Express scan Start")

            cabins = [cabin_fmt.unpack_from(data, i) for i in range(2, len(data), 5)]

            for i, [d1, d2, th_base] in enumerate(cabins):
                thoff_1 = float((((d1 << 4) | (th_base & 0x0F)) & 0x3F)) / 8.
                thoff_2 = float((((d2 << 4) | (th_base & 0xF0)) & 0x3F)) / 8.
                d1 >>= 2
                d2 >>= 2

                th1 = int(parse_angle(start_angle, start_angle_last or 0, 2*i, thoff_1)) % 360
                th2 = int(parse_angle(start_angle, start_angle_last or 0, 2*i + 1, thoff_2 )) % 360

                if th1 != last_angle:
                    yield th1, d1
                    last_angle = th1

                if th2 != last_angle:
                    yield th2, d2
                    last_angle = th2

            
            start_angle_last = start_angle
        pass

    def iter_dense_express_packets(self):
        raise NotImplementedError("Dense scan format is unsupported for now")

    def __iter__(self):
        print("IS ITER")
        print(self.get_info())
        print(self.get_health())
        print(self.get_sample_rate())        
        
        # self.set_motor(True)
        return self.req_express()()

if __name__ == "__main__":
    l = Lidar("COM8")
    # sleep(5)
    for angle, distance in l:
        print(angle, distance)

