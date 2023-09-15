import collections
from enum import Enum


class DebugLevel(Enum):
    ERROR = 0
    WARN = 1
    INFO = 2
    DEBUG = 3


DPCD_PRINT_LOG_LEVEL = DebugLevel.INFO


def dpcd_print(debug_level=DebugLevel.INFO, msg="", verbose=False):
    """
    print debug message, Print only if the given
    level is less than or equal to the specified debug level

    Args:
         msg (str): The message to print.
         debug_level (int): debug level, integer. Default is 1.
         verbose (bool): Whether to enable verbose output. If True, the debug level will be ignored.
    """
    debug_levels = {
        DebugLevel.ERROR: "ERR  :",
        DebugLevel.WARN:  "WARN :",
        DebugLevel.INFO:  "INFO :",
        DebugLevel.DEBUG: "DEBUG:"
    }
    debug_string = debug_levels.get(debug_level, "INFO :")
    if debug_level.value <= DPCD_PRINT_LOG_LEVEL.value:
        print(f"{debug_string} {msg}")


class ParserBase(object):
    pass


class MultiByteParser(ParserBase):
    Result = collections.namedtuple('Result',
                                    [
                                        'register',
                                        'value',
                                        'output'
                                    ])
    name = None
    start = None
    end = None

    def __init__(self, bytes, value_offset):
        self.value = bytes[value_offset:value_offset + self.num_bytes()]
        dpcd_print(DebugLevel.DEBUG, "MultiByteParser")
        self.output = None

    @classmethod
    def can_parse(cls, start):
        # TODO: add partial parsing support
        dpcd_print(DebugLevel.DEBUG, "start:" + hex(start) +
                   " cls.start:" + hex(cls.start) + " cls.end:" + hex(cls.end))
        if start >= cls.start and start <= cls.end:
            return True
        return False

    def num_bytes(self):
        return type(self).end - type(self).start + 1

    def add_result(self, printfn=lambda x: x):
        self.output = printfn(self.value)

    def print(self):
        print('  {:<10}{:<41}[{}]'.format(hex(type(self).start),
                                          type(self).name,
                                          ', '.join(hex(x) for x in self.value)))
        print('  {:<11}{:<40}{}'.format('', 'Value', self.output))

    def parse(self):
        raise NotImplementedError()


class RangeParser(ParserBase):
    Result = collections.namedtuple('Result',
                                    [
                                        'register',
                                        'start_bit',
                                        'end_bit',
                                        'label',
                                        'value',
                                        'output'
                                    ])

    name = None
    start = None
    end = None

    def __init__(self, bytes, value_offset):
        dpcd_print(DebugLevel.DEBUG, "value_offset: {}".format(value_offset))
        self.value = bytes[value_offset:value_offset + self.num_bytes()]
        dpcd_print(DebugLevel.DEBUG, "self.value: {}".format(self.value))
        dpcd_print(DebugLevel.DEBUG, "bytes: {}".format(bytes))
        byte_num = len(bytes) - 1
        dpcd_print(DebugLevel.DEBUG, "byte_num: {}".format(byte_num))
        self.value = bytes[1:]
        dpcd_print(DebugLevel.DEBUG, "self.value: {}".format(self.value))
        self.parse_result = []

    @classmethod
    def can_parse(cls, start):
        # Only support parsing from the beginning of the range
        # TODO: maybe add partial parsing at some point
        if start == cls.start:
            return True
        return False

    def num_bytes(self):
        return type(self).end - type(self).start + 1

    def field(self, value, start_bit, end_bit):
        start_mask = ((1 << (start_bit)) - 1)
        end_mask = ((1 << (end_bit + 1)) - 1)
        mask = start_mask ^ end_mask
        return (value & mask) >> start_bit

    def add_result(self, label, offset, start_bit, end_bit=None, printfn=lambda x: x):
        if end_bit == None:
            end_bit = start_bit
        if end_bit < start_bit:
            raise ValueError('Inverted start/end bits!')
        if offset >= len(self.value):
            raise ValueError(f'Invalid offset {offset} len={len(self.value)}!')
        value = self.field(self.value[offset], start_bit, end_bit)
        result = RangeParser.Result(
            self.name, start_bit, end_bit, label, value, printfn(value))
        self.parse_result.append(result)

    def print(self):
        print('  {:<10}{:<41}[{}]'.format(hex(type(self).start),
                                          type(self).name,
                                          ', '.join(hex(x) for x in self.value)))
        for v in self.parse_result:
            print('  [{:<3}{}:{}]  {:41}{}'.format(
                v.value,
                v.start_bit,
                v.end_bit,
                v.label,
                v.output))

    def parse(self):
        raise NotImplementedError()


class RangeDPCDRev(RangeParser):
    name = "DPCD_REV"
    start = 0
    end = 0

    def parse(self):
        self.add_result('Major rev', 0, 4, 7)
        self.add_result('Minor rev', 0, 0, 3)


class RangeMaxLinkRate(RangeParser):
    name = 'MAX_LINK_RATE'
    start = 1
    end = 1

    def parse(self):
        self.add_result('Max link rate', 0, 0, 7,
                        lambda x: '{} Gpbs'.format(x * 0.27))


class RangeMaxLaneCount(RangeParser):
    name = 'MAX_LANE_COUNT'
    start = 2
    end = 2

    def parse(self):
        self.add_result('Enhanced frame caps', 0, 7)
        self.add_result('Supports TPS3 pattern', 0, 6)
        self.add_result('Supports post-lt adjust', 0, 5)
        self.add_result('Max lane count', 0, 0, 4)


class RangeMaxDownspread(RangeParser):
    name = 'MAX_DOWNSPREAD'
    start = 3
    end = 3

    def parse(self):
        self.add_result('Supports TPS4 pattern', 0, 7)
        self.add_result('Requires AUX for sync', 0, 6)
        self.add_result('Reserved', 0, 2, 5)
        self.add_result('Supports stream regen bit', 0, 1)
        self.add_result('Max downspread', 0, 0,
                        printfn=lambda x: '<=0.5%' if x else 'None')


class RangeRecvPorts(RangeParser):
    name = 'NORP/DP_PWR_VOLTAGE_CAP'
    start = 4
    end = 4

    def parse(self):
        self.add_result('Capable of 18V', 0, 7)
        self.add_result('Capable of 12V', 0, 6)
        self.add_result('Capable of 5V', 0, 5)
        self.add_result('Reserved', 0, 2, 4)
        self.add_result('CRC 3D supported', 0, 1)
        self.add_result('Number recv ports', 0, 0)


class RangeDownstreamPortPresent(RangeParser):
    name = 'DOWN_STREAM_PORT_PRESENT'
    start = 5
    end = 5

    def downstream_port_type(self, val):
        if val == 0:
            return 'DisplayPort'
        elif val == 1:
            return 'Analog VGA'
        elif val == 2:
            return 'HDMI/DVI/DP++'
        elif val == 3:
            return 'Others'

    def parse(self):
        self.add_result('Reserved', 0, 7)
        self.add_result('Detailed capability available', 0, 4)
        self.add_result('Branch converts format', 0, 3)
        self.add_result('Downstream facing port type', 0, 1, 2,
                        self.downstream_port_type)
        self.add_result('Downstream facing port present', 0, 0)


class RangeMainLinkChannelCoding(RangeParser):
    name = 'MAIN_LINK_CHANNEL_CODING'
    start = 6
    end = 6

    def parse(self):
        self.add_result('Reserved', 0, 2, 7)
        self.add_result('Supports 128b/132b encoding', 0, 1)
        self.add_result('Supports 8b/10b encoding', 0, 0)


class RangeDownStreamPortCount(RangeParser):
    name = 'DOWN_STREAM_PORT_COUNT'
    start = 7
    end = 7

    def parse(self):
        self.add_result('IEEE unique ID support', 0, 7)
        self.add_result('Sink requires MSA timing', 0, 6)
        self.add_result('Reserved', 0, 4, 5)
        self.add_result('Downstream port count', 0, 0, 3)


class RangeReceivePortCap(RangeParser):
    def parse(self):
        self.add_result('Reserved', 0, 6, 7)
        self.add_result('Buffer size per-lane/port', 0, 5,
                        printfn=lambda x: 'Per port' if x else 'Per lane')
        self.add_result('Buffer size units', 0, 4,
                        printfn=lambda x: 'Bytes' if x else 'Pixels')
        self.add_result('HBlank expansion supported', 0, 3)
        self.add_result(
            'usage', 0, 2, printfn=lambda x: 'Secondary stream' if x else 'Primary stream')
        self.add_result('Local EDID present', 0, 1)
        self.add_result('Reserved', 0, 0)
        self.add_result('Buffer Size', 1, 0, 7, lambda x: (x + 1) * 32)


class RangeReceivePortCap0(RangeReceivePortCap):
    name = 'RECEIVE_PORT0_CAP'
    start = 8
    end = 9


class RangeReceivePortCap1(RangeReceivePortCap):
    name = 'RECEIVE_PORT1_CAP'
    start = 0xA
    end = 0xB


class RangeI2CSpeedCap(RangeParser):
    name = 'I2C Speed Control Capabilities Bit Map'
    start = 0xC
    end = 0xC

    def i2c_speed_caps(self, val):
        if val == 0:
            return 'No physical i2c bus'
        speeds = []
        if val & 1:
            speeds.append('1 Kbps')
        if val & 2:
            speeds.append('5 Kbps')
        if val & 4:
            speeds.append('10 Kbps')
        if val & 8:
            speeds.append('100 Kbps')
        if val & 0x10:
            speeds.append('400 Kbps')
        if val & 0x20:
            speeds.append('1 Mbps')
        if val & 0x40 or val & 0x80:
            speeds.append('RESERVED')
        return '/'.join(speeds)

    def parse(self):
        self.add_result('I2C speed support', 0, 0, 7, self.i2c_speed_caps)


class RangeEDPConfigCap(RangeParser):
    name = 'eDP_CONFIGURATION_CAP'
    start = 0xD
    end = 0xD

    def parse(self):
        # TODO: Implement this from eDP spec
        self.add_result('Reserved for eDP', 0, 0, 7)


class RangeTrainingAuxInterval(RangeParser):
    name = 'TRAINING_AUX_RD_INTERVAL'
    start = 0xE
    end = 0xE

    def aux_rd_interval(self, val):
        def fn(x): return 'ClockReqDone=100us / ChannelEqDone={}us'.format(x)
        if val == 0:
            return fn(400)
        elif val == 1:
            return fn(4000)
        elif val == 2:
            return fn(8000)
        elif val == 3:
            return fn(12000)
        elif val == 4:
            return fn(16000)

    def parse(self):
        self.add_result('Extended receiver caps available', 0, 7)
        self.add_result('Training AUX read interval',
                        0, 0, 6, self.aux_rd_interval)


class RangeMSTMCaps(RangeParser):
    name = 'MSTM_CAP'
    start = 0x21
    end = 0x21

    def parse(self):
        self.add_result('Reserved', 0, 2, 7)
        self.add_result('SINGLE_STREAM_SIDEBAND_MSG_SUPPORT', 0, 1)
        self.add_result('MST_CAP', 0, 0)


class RangeDetailedCapInfo(RangeParser):
    def dfpx_attribute(self, val):
        ret = []
        if val & 1:
            ret.append('480i@60')
        if val & 2:
            ret.append('480i@50')
        if val & 3:
            ret.append('1080i@60')
        if val & 4:
            ret.append('1080i@50')
        if val & 5:
            ret.append('720p@60')
        if val & 6:
            ret.append('720p@50')
        return ','.join(ret)

    def dfpx_type(self, val):
        if val == 0:
            return 'DisplayPort'
        elif val == 1:
            return 'Analog VGA'
        elif val == 2:
            return 'DVI'
        elif val == 3:
            return 'HDMI'
        elif val == 4:
            return 'Other (No DisplayID/EDID support)'
        elif val == 5:
            return 'DP++'
        elif val == 6:
            return 'Wireless'
        elif val == 7:
            return 'Reserved'

    def max_bits_per_component(self, val):
        ret = ['8bpc']
        if val & 1:
            ret.append('10bpc')
        if val & 2:
            ret.append('12bpc')
        if val & 3:
            ret.append('16bpc')
        return '/'.join(ret)

    def parse(self):
        self.add_result('NON_EDID_DFPX_ATTRIBUTE',
                        0, 4, 7, self.dfpx_attribute)
        self.add_result('DFPX_HPD', 0, 3, 3,
                        lambda x: 'HPD Aware' if x else 'HPD Unaware')
        self.add_result('DFPX_TYPE', 0, 0, 2, self.dfpx_type)
        # Detailed cap info for downstream ports isn't always available
        if len(self.value) <= 1:
            return

        # DP
        type = self.field(self.value[0], 0, 2)
        if type == 0:
            self.add_result('Reserved', 1, 0, 7)
            self.add_result('Reserved', 2, 0, 7)
            self.add_result('Reserved', 3, 0, 7)
        # VGA
        elif type == 1:
            self.add_result('Maximum Pixel Rate', 1, 0, 7,
                            lambda x: '{} MP/s'.format(x * 8))
            self.add_result('Reserved', 2, 2, 7)
            self.add_result('Maximum Bits/component', 2, 0,
                            1, self.max_bits_per_component)
            self.add_result('Reserved', 3, 0, 7)
        # DVI
        elif type == 2:
            self.add_result('Maximum TMDS Char Clock Rate', 1,
                            0, 7, lambda x: '{} MHz'.format(x * 2.5))
            self.add_result('Reserved', 2, 2, 7)
            self.add_result('Maximum Bits/component', 2, 0,
                            1, self.max_bits_per_component)
            self.add_result('Reserved', 3, 3, 7)
            self.add_result('High Color Depth', 3, 2)
            self.add_result('Dual Link', 3, 1)
            self.add_result('Reserved', 3, 0)
        # HDMI
        elif type == 3:
            self.add_result('Maximum TMDS Char Clock Rate', 1,
                            0, 7, lambda x: '{} MHz'.format(x * 2.5))
            self.add_result('Reserved', 2, 2, 7)
            self.add_result('Maximum Bits/component', 2, 0,
                            1, self.max_bits_per_component)
            self.add_result('Reserved', 3, 5, 7)
            self.add_result(
                'CONVERSION_FROM_YCBCR444_TO_YCBCR420_SUPPORT', 3, 4)
            self.add_result(
                'CONVERSION_FROM_YCBCR444_TO_YCBCR422_SUPPORT', 3, 3)
            self.add_result('YCBCR420_PASS_THROUGH_SUPPORT', 3, 2)
            self.add_result('YCBCR422_PASS_THROUGH_SUPPORT', 3, 1)
            self.add_result('FRAME_SEQ_TO_FRAME_PACK', 3, 0)
        # Other
        elif type == 4:
            self.add_result('UNDEFINED', 1, 0, 7)
            self.add_result('UNDEFINED', 2, 0, 7)
            self.add_result('UNDEFINED', 3, 0, 7)
        # DP++
        elif type == 5:
            self.add_result('Maximum TMDS Char Clock Rate', 1,
                            0, 7, lambda x: '{} MHz'.format(x * 2.5))
            self.add_result('Reserved', 2, 2, 7)
            self.add_result('Maximum Bits/component', 2, 0,
                            1, self.max_bits_per_component)
            self.add_result('Reserved', 3, 2, 7)
            self.add_result('UNDEFINED', 3, 1, 7)
            self.add_result('FRAME_SEQ_TO_FRAME_PACK', 3, 0)
        # Wireless
        elif type == 6:
            self.add_result('Reserved', 1, 4, 7)
            self.add_result('WIRELESS_TECHNOLOGY', 1, 0, 3,
                            lambda x: 'WiGig' if x == 0 else 'Reserved')
            self.add_result('Reserved', 2, 4, 7)
            self.add_result('WDE_TX_CONCURRENCY_CAP', 2, 2, 3)
            self.add_result('NUMBER_OF_WDE_TX_ON_DEVICE', 2, 0, 1)
            self.add_result('Reserved', 3, 0, 7)


class RangeDetailedCapInfoDFP0(RangeDetailedCapInfo):
    name = 'Downstream Facing Port 0 Capabilities'
    start = 0x80
    end = 0x83


class RangeDetailedCapInfoDFP1(RangeDetailedCapInfo):
    name = 'Downstream Facing Port 1 Capabilities'
    start = 0x84
    end = 0x87


class RangeDetailedCapInfoDFP2(RangeDetailedCapInfo):
    name = 'Downstream Facing Port 2 Capabilities'
    start = 0x88
    end = 0x8B


class RangeDetailedCapInfoDFP3(RangeDetailedCapInfo):
    name = 'Downstream Facing Port 3 Capabilities'
    start = 0x8C
    end = 0x8F


class FecCap(RangeParser):
    name = "Fec Capability.(New to DP v1.4)"
    start = 0x90
    end = 0x90

    def parse(self):
        self.add_result('FEC_CAPABLE', 0, 0,
                        printfn=lambda x: 'Capable' if x else 'Not capable')
        self.add_result('UNCORRECTED_BLOCK_ERROR_COUNT_CAPABLE(Support required for an FEC-capable DPRX)  ', 0,
                        1, printfn=lambda x: 'Capable' if x else 'Not capable')
        self.add_result('CORRECTED_BLOCK_ERROR_COUNT_CAPABLE', 0, 2,
                        printfn=lambda x: 'Capable' if x else 'Not capable')
        self.add_result('BIT_ERROR_COUNT_CAPABLE', 0, 3,
                        printfn=lambda x: 'Capable' if x else 'Not capable')
        self.add_result('Reserved', 0, 4, 7)


class Reserved(RangeParser):
    name = 'Reserved'
    start = 0x91
    end = 0xFF

    def parse(self):
        self.add_result("Reserved", 0, 0, 7)


class RangePanelReplayCap(RangeParser):
    name = 'PANEL_REPLAY_CAPABILITY_SUPPORTED'
    start = 0xB0
    end = 0xB1

    def parse(self):
        self.add_result('Reserved', 0, 2, 7)
        self.add_result('Selective Update Support', 0, 1)
        self.add_result('Replay Support', 0, 0)
        self.add_result('Reserved', 1, 6, 7)
        self.add_result('Selective Update Granularity', 1, 5, 5,
                        lambda x: 'Required' if x else 'Not Required')
        self.add_result('Reserved', 1, 0, 4)


class RangeSinkCountParser(RangeParser):
    def parse(self):
        self.add_result('SINK_COUNT_bit7', 0, 7)
        self.add_result('CP_READY', 0, 6)
        self.add_result('SINK_COUNT', 0, 0, 5)


class LinkConfigField(RangeParser):
    name = 'Main-Link Bandwidth Setting = Value x 0.27Gbps/lane'
    start = 0x100
    end = 0x100

    def lane_rate(self, val):
        if val == 0x06:
            return '1.62Gbps/lane'
        elif val == 0x0A:
            return '2.7Gbps/lane'
        elif val == 0x14:
            return '5.4Gbps/lane'
        elif val == 0x1e:
            return '8.1Gbps/lane'

    def parse(self):
        self.add_result("LINK_BW_SET = ",
                        0, 0, 7, self.lane_rate)


class LinkConfigFieldLaneCount(RangeParser):
    name = 'Main-Link Lane Count = Value.'
    start = 0x101
    end = 0x101

    def lane_num(self, val):
        if val == 0x1:
            return '1 lane (Lane 0 only)'
        elif val == 0x2:
            return '2 lanes (Lanes 0 and 1 only)'
        elif val == 0x4:
            return '4 lanes (Lanes 0, 1, 2, and 3)'

    def parse(self):
        self.add_result('LANE_COUNT_SET', 0, 0, 4, self.lane_num)
        self.add_result('POST_LT_ADJ_REQ_GRANTED', 0, 5, 5)
        self.add_result('Reserved', 0, 6, 6)
        self.add_result('ENHANCED_FRAME_EN', 0, 7, 7,
                        lambda x: 'Enable Enhanced Framing symbol sequence' if x else "Disable Enhanced Framing symbol sequence")


class LinkConfigFieldTrainingPattern(RangeParser):
    name = 'TRAINING_PATTERN_SET'
    start = 0x102
    end = 0x102

    def pattern(self, val):
        if val == 0x1:
            return 'Link Training Pattern Sequence 1.'
        elif val == 0x0:
            return 'Training not in progress (or disabled).'
        elif val == 0x2:
            return 'Link Training Pattern Sequence 2.'
        elif val == 0x3:
            return 'Link Training Pattern Sequence 3.'
        elif val == 0b0111:
            return 'Link Training Pattern Sequence 4.'

    def errcount(self, val):
        if val == 0b00:
            return 'Count Disparity and Illegal Symbol errors.'
        elif val == 0b01:
            return 'Count Disparity errors only.'
        elif val == 0b10:
            return 'Count Illegal Symbol errors only.'
        elif val == 0b11:
            return 'Reserved.'

    def parse(self):
        self.add_result('Link Training Pattern Selection.',
                        0, 0, 3, self.pattern)
        self.add_result('RECOVERED_CLOCK_OUT_EN', 0, 4, 4,
                        lambda x: 'Recovered clock output from a test pad of DPRX is enabled.' if x else 'Recovered clock output from a test pad of DPRX is not enabled')
        self.add_result('SCRAMBLING_DISABLE', 0, 5, 5,
                        lambda x: 'DPTX scrambles data symbols before transmission.' if x else 'DPTX disables scrambler and transmits all symbols without scrambling.')
        self.add_result('SYMBOL_ERROR_COUNT_SEL', 0, 6, 7,  self.errcount)


class LinkConfigFieldTrainingLaneSet(RangeParser):
    def voltage(self, val):
        if val == 0b00:
            return 'Voltage swing level 0.'
        elif val == 0b01:
            return 'Voltage swing level 1.'
        elif val == 0b10:
            return 'Voltage swing level 2.'
        elif val == 0b11:
            return 'Voltage swing level 3.'

    def pre_emphasis(self, val):
        if val == 0b00:
            return 'Pre-emphasis level 0.'
        elif val == 0b01:
            return 'Pre-emphasis level 1.'
        elif val == 0b10:
            return 'Pre-emphasis level 2.'
        elif val == 0b11:
            return 'Pre-emphasis level 3.'

    def parse(self):
        self.add_result('VOLTAGE SWING SET', 0, 0, 1, self.voltage)
        self.add_result('MAX_SWING_REACHED', 0, 2)
        self.add_result('PRE-EMPHASIS_SET', 0, 3, 4, self.pre_emphasis)
        self.add_result('MAX_PRE-EMPHASIS_REACHED', 0, 5, 5)


class LinkConfigFieldTrainingLane0(LinkConfigFieldTrainingLaneSet):
    name = 'TRAINING_LANE0_SET'
    start = 0x103
    end = 0x103


class LinkConfigFieldTrainingLane1(LinkConfigFieldTrainingLaneSet):
    name = 'TRAINING_LANE1_SET'
    start = 0x104
    end = 0x104


class LinkConfigFieldTrainingLane2(LinkConfigFieldTrainingLaneSet):
    name = 'TRAINING_LANE2_SET'
    start = 0x105
    end = 0x105


class LinkConfigFieldTrainingLane3(LinkConfigFieldTrainingLaneSet):
    name = 'TRAINING_LANE3_SET'
    start = 0x106
    end = 0x106


class LinkConfigFieldDownSpread(RangeParser):
    name = 'DOWNSPREAD_CTRL'
    start = 0x107
    end = 0x107

    def parse(self):
        self.add_result('RESERVED', 0, 0, 3)
        self.add_result('SPREAD_AMP', 0, 4, 4,
                        lambda x: ' Main-Link signal is not down-spread' if x else ' Main-Link signal is down-spread by equal to or less than 0.5 % with a modulation frequency in the range of 30 to 33kHz.')
        self.add_result('RESERVED', 0, 5, 6)
        self.add_result('MSA_TIMING_PAR_IGNORE_EN', 0, 7, 7,
                        lambda x: """Source device sends valid data for MSA timing parameters HTotal[15:0], HStart[15:0], HSyncPolarity[0]( HSP), HSyncWidth[14:0](HSW), VTotal[15:0], VStart[15:0], VSyncPolarity[0](VSP), and VSyncWidth[14:0](VSW)""" if x else """Source device may send invalid data for the above-mentioned MSA timing parameters. The Sink device must ignore these parameters and regenerate the incoming video stream without depending on these parameters. (This bit can be set to 1 only if the MSA_TIMING_PAR_IGNORED bit in the DOWN_STREAM_PORT_COUNT register (DPCD Address 00007h, bit 6) is set to 1""")


class LinkConfigFieldChannelCoding(RangeParser):
    name = 'MAIN_LINK_CHANNEL_CODING_SET'
    start = 0x108
    end = 0x108

    def parse(self):
        self.add_result('SET_ANSI 8b/10b', 0, 0)
        self.add_result('RESERVED', 0, 1, 7)


class LinkConfigFieldChannelCoding(RangeParser):
    name = 'I2C Speed Control/Status Bit Map'
    start = 0x109
    end = 0x109

    def i2cspeed(self, val):
        if val == 0b1:
            return '1Kbps.'
        elif val == 0b10:
            return '5Kbps.'
        elif val == 0b100:
            return '10Kbps.'
        elif val == 0b1000:
            return '100Kbps.'
        elif val == 0b10000:
            return '400Kbps.'
        elif val == 0b100000:
            return '1Mbps.'
        elif val == 0b1000000:
            return 'RESERVED.'
        elif val == 0b10000000:
            return 'RESERVED.'

    def parse(self):
        self.add_result('I2C speeds', 0, 0, 7, self.i2cspeed)


class LinkConfigFieldeDPSet(RangeParser):
    name = 'eDP_CONFIGURATION_SET(For eDP Sink)'
    start = 0x10A
    end = 0x10A

    def parse(self):
        self.add_result('ALTERNATE_SCRAMBLER_RESET_ENABLE', 0, 0)
        self.add_result('RESERVED', 0, 0, 1)
        self.add_result('RESERVED', 0, 2, 6)
        self.add_result('PANEL_SELF_TEST_ENABLE', 0, 7, 7,
                        lambda x: "Enable" if x else 'Disable')


class LinkConfigFieldLinkQualLane(RangeParser):
    def qual_pattern(self, val):
        if val == 0b00:
            return 'Link quality test pattern not transmitted.'
        elif val == 0b01:
            return 'D10.2 test pattern(unscrambled) transmitted(same as Link Training Pattern Sequence 1)'
        elif val == 0b10:
            return 'Symbol Error Rate Measurement Pattern transmitted.'
        elif val == 0b11:
            return 'PRBS7 transmitted.'
        elif val == 0b100:
            return '80-bit custom pattern transmitted.'
        elif val == 0b101:
            return 'CP2520 (HBR2 Compliance EYE pattern) transmitted.'
        elif val == 0b110 or val == 0b111:
            return 'Reserved.'

    def parse(self):
        self.add_result('LINK_QUAL_PATTERN_SET', 0, 0, 2, self.qual_pattern)
        self.add_result('Reserved', 0, 3, 7)


class LinkConfigFieldLinkQualLane0Set(LinkConfigFieldLinkQualLane):
    name = 'LINK_QUAL_LANE0_SET'
    start = 0x10B
    end = 0x10B


class LinkConfigFieldLinkQualLane1Set(LinkConfigFieldLinkQualLane):
    name = 'LINK_QUAL_LANE1_SET'
    start = 0x10C
    end = 0x10C


class LinkConfigFieldLinkQualLane2Set(LinkConfigFieldLinkQualLane):
    name = 'LINK_QUAL_LANE2_SET'
    start = 0x10D
    end = 0x10D


class LinkConfigFieldLinkQualLane3Set(LinkConfigFieldLinkQualLane):
    name = 'LINK_QUAL_LANE3_SET'
    start = 0x10E
    end = 0x10E


class PrintReserved(RangeParser):
    def parse(self):
        self.add_result('Reserved', 0, 0, 7)


class LinkConfigFieldReserved(PrintReserved):
    name = 'Reserved'
    start = 0x10F
    end = 0x110


class LinkCfgMstCtl(RangeParser):
    name = 'MSTM_CTRL'
    start = 0x111
    end = 0x111

    def parse(self):
        self.add_result(
            'MST_EN', 0, 0, 0, lambda x: 'Single Stream Format' if x else 'Multi-Stream Format')
        self.add_result('UP_REQ_EN', 0, 1, 1, lambda x: 'Allows the Downstream DPRX to originating/forwarding an UP_REQ message transaction ' if x else 'Prohibits the Downstream DPRX from originating/forwarding an UP_REQ message transaction')
        self.add_result('UPSTREAM_IS_SRC', 0, 2, 2, lambda x: 'Set to 1 by a DP Source device to indicate to the downstream device the presence of a Source device, not a Branch device' if x else 'Upstream device is either a Source device predating DP Standard Ver.1.2 or a Branch device')
        self.add_result('Reserved', 0, 3, 7)


class LinkCfgAudioDelay(RangeParser):
    name = 'AUDIO_DELAY'
    start = 0x112
    end = 0x114

    def parse(self):
        self.add_result('AUDIO_DELAY[7:0]', 0, 0, 7)
        self.add_result('AUDIO_DELAY[15:8]', 1, 0, 7)
        self.add_result('AUDIO_DELAY[23:16]', 2, 0, 7)


# --------------------------------------
# DPCD Address 0x200 - 0x2ff
# --------------------------------------
class RangeSinkCount(RangeSinkCountParser):
    name = 'SINK_COUNT'
    start = 0x200
    end = 0x200


class RangeDeviceServiceIRQParser(RangeParser):
    def parse(self):
        self.add_result('Reserved', 0, 7)
        self.add_result('SINK_SPECIFIC_IRQ', 0, 6)
        self.add_result('UP_REQ_MSG_RDY', 0, 5)
        self.add_result('DOWN_REP_MSG_RDY', 0, 4)
        self.add_result('MCCS_IRQ', 0, 3)
        self.add_result('CP_IRQ', 0, 2)
        self.add_result('AUTOMATED_TEST_REQUEST', 0, 1)
        self.add_result('REMOTE_CONTROL_COMMAND_PENDING', 0, 0)


class RangeDeviceServiceIRQ(RangeDeviceServiceIRQParser):
    name = 'DEVICE_SERVICE_IRQ_VECTOR'
    start = 0x201
    end = 0x201


class RangeLaneStatus(RangeParser):
    def __init__(self, bytes, value_offset, lane_offset):
        super().__init__(bytes, value_offset)
        self.pfx = ('LANE{}'.format(lane_offset), 'LANE{}'.format(lane_offset))

    def parse(self):
        self.add_result('Reserved', 0, 7)
        self.add_result('{}_SYMBOL_LOCKED'.format(self.pfx[1]), 0, 6)
        self.add_result('{}_CHANNEL_EQ'.format(self.pfx[1]), 0, 5)
        self.add_result('{}_CR_DONE'.format(self.pfx[1]), 0, 4)
        self.add_result('Reserved', 0, 3)
        self.add_result('{}_SYMBOL_LOCKED'.format(self.pfx[0]), 0, 2)
        self.add_result('{}_CHANNEL_EQ'.format(self.pfx[0]), 0, 1)
        self.add_result('{}_CR_DONE'.format(self.pfx[0]), 0, 0)


class RangeLane01Status(RangeLaneStatus):
    name = 'LANE0_1_STATUS'
    start = 0x202
    end = 0x202

    def __init__(self, bytes, value_offset):
        super().__init__(bytes, value_offset, 0)


class RangeLane23Status(RangeLaneStatus):
    name = 'LANE2_3_STATUS'
    start = 0x203
    end = 0x203

    def __init__(self, bytes, value_offset):
        super().__init__(bytes, value_offset, 2)


class RangeLaneAlignStatusUpdatedParser(RangeParser):
    def parse(self):
        self.add_result('LINK_STATUS_UPDATED', 0, 7)
        self.add_result('DOWNSTREAM_PORT_STATUS_CHANGED', 0, 6)
        self.add_result('Reserved', 0, 2, 5)
        self.add_result('POST_LT_ADJ_REQ_IN_PROGRESS', 0, 1)
        self.add_result('INTERLANE_ALIGN_DONE', 0, 0)


class RangeLaneAlignStatusUpdated(RangeLaneAlignStatusUpdatedParser):
    name = 'LANE_ALIGN_STATUS_UPDATED'
    start = 0x204
    end = 0x204


class RangeSinkStatusParser(RangeParser):
    def parse(self):
        self.add_result('Reserved', 0, 3, 7)
        self.add_result('STREAM_REGENERATION_STATUS', 0, 2)
        self.add_result('RECEIVE_PORT_1_STATUS', 0, 1,
                        printfn=lambda x: '{} sync'.format('IN' if x else 'OUT'))
        self.add_result('RECEIVE_PORT_0_STATUS', 0, 0,
                        printfn=lambda x: '{} sync'.format('IN' if x else 'OUT'))


class RangeSinkStatus(RangeSinkStatusParser):
    name = 'SINK_STATUS'
    start = 0x205
    end = 0x205


class MultiByteIEEEOUI(MultiByteParser):
    def parse(self):
        self.add_result(lambda x: '{}-{}-{}'.format(
                        hex(x[0])[2:],
                        hex(x[1])[2:],
                        hex(x[2])[2:]))


class RangeFirmwareMajorRevision(RangeParser):
    def parse(self):
        self.add_result('Revision', 0, 0, 7)


class MultiByteDeviceId(MultiByteParser):
    def parse(self):
        self.add_result(lambda x: '"{}"'.format(bytes(x).decode('utf-8')))


class RangeHardwareRevision(RangeParser):
    def parse(self):
        self.add_result('Minor Revision', 0, 0, 3)
        self.add_result('Major Revision', 0, 4, 7)


class RangeFirmwareMinorRevision(RangeParser):
    def parse(self):
        self.add_result('Revision', 0, 0, 7)

class LinkSinkDevStatusFieldAdjustRequestLane01(RangeParser):
    name = "ADJUST_REQUEST_LANE0_1"
    start = 0x206
    end = 0x206

    voltage_swing_map = {
        0b00: "0",
        0b01: "1",
        0b10: "2",
        0b11: "3",
    }

    def voltage_swing_lvl(self, val):
        return "Level {}".format(self.voltage_swing_map.get(val, "Error"))
    def parse(self):
        self.add_result("VOLTAGE_SWING_LANE0", 0, 0, 1, self.voltage_swing_lvl)
        self.add_result("PRE-EMPHASIS_LANE0", 0, 2, 3, self.voltage_swing_lvl)
        self.add_result("VOLTAGE_SWING_LANE1", 0, 4, 5, self.voltage_swing_lvl)
        self.add_result("PRE-EMPHASIS_LANE1", 0, 6, 7, self.voltage_swing_lvl)

class LinkSinkDevStatusFieldAdjustRequestLane23(RangeParser):
    name = "ADJUST_REQUEST_LANE2_3"
    start = 0x207
    end = 0x207

    def parse(self):
        self.add_result('ADJUST_REQUEST_LANE2_3', 0, 7)
class LinkSinkDevStatusFieldTrainingScoreLane0(RangeParser):
    name = "TRAINING_SCORE_LANE0"
    start = 0x208
    end = 0x208

    def parse(self):
        self.add_result('TRAINING_SCORE_LANE0', 0, 7)
class LinkSinkDevStatusFieldTrainingScoreLane1(RangeParser):
    name = "TRAINING_SCORE_LANE1"
    start = 0x209
    end = 0x209

    def parse(self):
        self.add_result('ADJUST_REQUEST_LANE2_3', 0, 7)
class LinkSinkDevStatusFieldTrainingScoreLane2(RangeParser):
    name = "TRAINING_SCORE_LANE2"
    start = 0x20A
    end = 0x20A

    def parse(self):
        self.add_result('TRAINING_SCORE_LANE2', 0, 7)
class LinkSinkDevStatusFieldTrainingScoreLane3(RangeParser):
    name = "TRAINING_SCORE_LANE3"
    start = 0x20B
    end = 0x20B

    def parse(self):
        self.add_result('TRAINING_SCORE_LANE3', 0, 7)

class LinkSinkDevStatusFieldReserved20C_20E(PrintReserved):
    name = "Reserved"
    start = 0x20C
    end = 0x20E

# --------------------------------------
# DPCD Address 0x300 - 0x3ff
# --------------------------------------
#  "0x300 0x00000"


class SourceDevspecFieldMultiByteSinkIEEEOUI(MultiByteIEEEOUI):
    name = 'Source IEEE_OUI'
    start = 0x300
    end = 0x302


class SourceDevspecFieldMultiByteSinkDeviceId(MultiByteDeviceId):
    name = 'Source Device Identification String'
    start = 0x303
    end = 0x308


class SourceFieldRangeSinkHardwareRevision(RangeHardwareRevision):
    name = 'Source Hardware Revision'
    start = 0x309
    end = 0x309


class SourceDevspecFieldRangeSinkFirmwareMajorRevision(RangeFirmwareMajorRevision):
    name = 'Source Firmware Major Revision'
    start = 0x30A
    end = 0x30A


class SourceDevspecFieldRangeFirmwareMinorRevision(RangeParser):
    def parse(self):
        self.add_result('Revision', 0, 0, 7)


class SourceDevspecFieldRangeSinkFirmwareMinorRevision(RangeFirmwareMinorRevision):
    name = 'Source Firmware Minor Revision'
    start = 0x30B
    end = 0x30B


class SourceDevspecFieldMultiByteReserved40C(MultiByteParser):
    name = 'RESERVED'
    start = 0x30C
    end = 0x3FF

    def parse(self):
        self.add_result()


# --------------------------------------
# DPCD Address 0x400 - 0x4ff
# --------------------------------------
class MultiByteSinkIEEEOUI(MultiByteIEEEOUI):
    name = 'Sink IEEE_OUI'
    start = 0x400
    end = 0x402


class MultiByteSinkDeviceId(MultiByteDeviceId):
    name = 'Sink Device Identification String'
    start = 0x403
    end = 0x408


class RangeSinkHardwareRevision(RangeHardwareRevision):
    name = 'Sink Hardware Revision'
    start = 0x409
    end = 0x409


class RangeSinkFirmwareMajorRevision(RangeFirmwareMajorRevision):
    name = 'Sink Firmware Major Revision'
    start = 0x40A
    end = 0x40A


class RangeSinkFirmwareMinorRevision(RangeFirmwareMinorRevision):
    name = 'Sink Firmware Minor Revision'
    start = 0x40B
    end = 0x40B


class MultiByteReserved40C(MultiByteParser):
    name = 'RESERVED'
    start = 0x40C
    end = 0x4FF

    def parse(self):
        self.add_result()

# --------------------------------------
# DPCD Address 0x500 - 0x5ff
# --------------------------------------


class MultiByteBranchIEEEOUI(MultiByteIEEEOUI):
    name = 'Branch IEEE_OUI'
    start = 0x500
    end = 0x502


class MultiByteBranchDeviceId(MultiByteDeviceId):
    name = 'Branch Device Identification String'
    start = 0x503
    end = 0x508


class RangeBranchHardwareRevision(RangeHardwareRevision):
    name = 'Branch Hardware Revision'
    start = 0x509
    end = 0x509


class RangeBranchFirmwareMajorRevision(RangeFirmwareMajorRevision):
    name = 'Branch Firmware Major Revision'
    start = 0x50A
    end = 0x50A


class RangeBranchFirmwareMinorRevision(RangeFirmwareMinorRevision):
    name = 'Branch Firmware Minor Revision'
    start = 0x50B
    end = 0x50B


class BranchMultiByteReserved40C(MultiByteParser):
    name = 'RESERVED'
    start = 0x50C
    end = 0x5FF

    def parse(self):
        self.add_result()
# --------------------------------------
# DPCD Address 0x600 - 0x6ff
# --------------------------------------


class SinkDevPowerCtrlField(RangeParser):
    name = "SET_POWER & SET_DP_PWR_VOLTAGE"
    start = 0x600
    end = 0x600

    def power_state(self, val):
        if val == 0b001:
            return "Sink devices to D0(normal)"
        elif val == 0b010:
            return "Sink devices to D3(powe-down)"
        elif val == 0b101:
            return "Sink devices to D3, AUX block fully powered."
        else:
            return "Reserved"

    def parse(self):
        self.add_result('SET_POWER_STATE', 0, 0, 2, self.power_state)
        self.add_result('RESERVED', 0, 3, 4)
        self.add_result('SET_DN_DEVICE_DP_PWR_5V', 0, 5, 5,
                        lambda x: "DP_PWR 5V" if x else "None")
        self.add_result('SET_DN_DEVICE_DP_PWR_12V', 0, 6, 6,
                        lambda x: "DP_PWR 12V" if x else "None")
        self.add_result('SET_DN_DEVICE_DP_PWR_18V', 0, 7, printfn=lambda x: '{}'.format(
            'DP_PWR 18V' if x else 'None'))


class BranchMultiByteReserved40C(MultiByteParser):
    name = 'RESERVED'
    start = 0x601
    end = 0x6FF

    def parse(self):
        self.add_result()

# --------------------------------------
# DPCD Address 0x700 - 0x7ff
# --------------------------------------


class BranchMultiByteReserved40C(PrintReserved):
    name = 'RESERVED for EDP'
    start = 0x701
    end = 0x7FF

# --------------------------------------
# DPCD Address 0x1000 - 0x17ff
# --------------------------------------
class MultiByteDownRequest(MultiByteParser):
    name = 'DOWN_REQ'
    start = 0x1000
    end = 0x11FF

    def parse(self):
        self.add_result()


class MultiByteUpReply(MultiByteParser):
    name = 'UP_REP'
    start = 0x1200
    end = 0x13FF

    def parse(self):
        self.add_result()


class MultiByteDownReply(MultiByteParser):
    name = 'DOWN_REP'
    start = 0x1400
    end = 0x15FF

    def parse(self):
        self.add_result()


class MultiByteUpRequest(MultiByteParser):
    name = 'UP_REQ'
    start = 0x1600
    end = 0x17FF

    def parse(self):
        self.add_result()

# --------------------------------------
# DPCD Address 0x2000 - 0x21ff
# --------------------------------------


class DPRXEventMultiByteReserved40C(PrintReserved):
    name = 'RESERVED'
    start = 0x2000
    end = 0x2001


class RangeSinkCountESI(RangeSinkCountParser):
    name = 'SINK_COUNT_ESI'
    start = 0x2002
    end = 0x2002


class RangeDeviceServiceIRQESI0(RangeDeviceServiceIRQParser):
    name = 'DEVICE_SERVICE_IRQ_VECTOR_ESI0'
    start = 0x2003
    end = 0x2003


class RangeDeviceServiceIRQESI1(RangeParser):
    name = 'DEVICE_SERVICE_IRQ_VECTOR_ESI1'
    start = 0x2004
    end = 0x2004

    def parse(self):
        self.add_result('Reserved', 0, 5, 7)
        self.add_result('DSC_ERROR_STATUS', 0, 4)
        self.add_result('PANEL_REPLAY_ERROR_STATUS', 0, 3)
        self.add_result('CEC_IRQ', 0, 2)
        self.add_result('LOCK_ACQUISITION_REQUEST', 0, 1)
        self.add_result('RX_GTC_MSTR_REQ_STATUS_CHANGE', 0, 0)


class RangeLinkServiceIRQESI0(RangeParser):
    name = 'LINK_SERVICE_IRQ_VECTOR_ESI0'
    start = 0x2005
    end = 0x2005

    def parse(self):
        self.add_result('Reserved', 0, 5, 7)
        self.add_result('CONNECTED_OFF_ENTRY_REQUESTED', 0, 4)
        self.add_result('HDMI_LINK_STATUS_CHANGED', 0, 3)
        self.add_result('STREAM_STATUS_CHANGED', 0, 2)
        self.add_result('LINK_STATUS_CHANGED', 0, 1)
        self.add_result('RX_CAP_CHANGED', 0, 0)


class RangeEDPPSR(RangeParser):
    name = 'eDP PSR Registers (TODO)'
    start = 0x2006
    end = 0x200B

    # TODO
    def parse(self):
        self.add_result('Reserved', 0, 0, 7)
        self.add_result('Reserved', 1, 0, 7)
        self.add_result('Reserved', 2, 0, 7)
        self.add_result('Reserved', 3, 0, 7)
        self.add_result('Reserved', 4, 0, 7)


class RangeLane01StatusESI(RangeLaneStatus):
    name = 'LANE0_1_STATUS_ESI'
    start = 0x200C
    end = 0x200C

    def __init__(self, bytes, value_offset):
        super().__init__(bytes, value_offset, 0)


class RangeLane23StatusESI(RangeLaneStatus):
    name = 'LANE2_3_STATUS_ESI'
    start = 0x200D
    end = 0x200D

    def __init__(self, bytes, value_offset):
        super().__init__(bytes, value_offset, 2)


class RangeLaneAlignStatusUpdatedESI(RangeLaneAlignStatusUpdatedParser):
    name = 'LANE_ALIGN_STATUS_UPDATED_ESI'
    start = 0x200E
    end = 0x200E


class RangeSinkStatusESI(RangeSinkStatusParser):
    name = 'SINK_STATUS_ESI'
    start = 0x200F
    end = 0x200F


class DPRXEventStatusMultiByteReserved40C(PrintReserved):
    name = 'RESERVED for eDP'
    start = 0x2010
    end = 0x2012


class DPRXEventStatusReservedMultiByteReserved40C(PrintReserved):
    name = 'RESERVED for eDP'
    start = 0x2013
    end = 0x21ff


class ExtendedReceivrCapVer(RangeParser):
    name = 'DP1.3_DPCD_REV'
    start = 0x2200
    end = 0x2200

    def parse(self):
        self.add_result("Minor Revision Number", 0, 0, 3)
        self.add_result("Major Revision Number", 0, 4, 7)


class ExtendedReceivrCapLinkRate(RangeParser):
    name = 'MAX_LINK_RATE'
    start = 0x2201
    end = 0x2201

    def lane_rate(self, val):
        if val == 0x06:
            return '1.62Gbps/lane'
        elif val == 0x0A:
            return '2.7Gbps/lane'
        elif val == 0x14:
            return '5.4Gbps/lane'
        elif val == 0x1e:
            return '8.1Gbps/lane'

    def parse(self):
        # type = self.field(self.value[0], 0, 7)
        self.add_result("Maximum link rate of Main-Link lanes = ",
                        0, 0, 7, self.lane_rate)


class ExtendedReceivrCapMaxLaneCount(RangeParser):
    name = 'MAX_LANE_COUNT'
    start = 0x2202
    end = 0x2202

    def lane_num(self, val):
        if val == 0x1:
            return 'One lane (Lane 0 only)'
        elif val == 0x2:
            return 'Two lanes (Lanes 0 and 1 only)'
        elif val == 0x4:
            return 'Four lanes (Lanes 0, 1, 2, and 3)'
        else:
            return "Error"

    def parse(self):
        self.add_result('Maximum number of lanes = ', 0, 0, 4, self.lane_num)
        self.add_result('Post-Link Training Adjust Request is ', 0, 5, 5,
                        lambda x: 'supported' if x else 'not supported')
        self.add_result('Indicates Link Training Pattern Sequence 3 (TPS3) is ', 0, 6, 6,
                        lambda x: 'supported' if x else 'not supported')
        self.add_result('Enhanced Framing symbol sequence for BS and SR is ', 0, 7, 7,
                        lambda x: 'supported' if x else 'not supported')


class ExtendedReceivrCapMaxDownSpread(RangeParser):
    name = 'MAX_LANE_COUNT'
    start = 0x2203
    end = 0x2203

    def parse(self):
        self.add_result(
            'MAX_DOWNSPREAD', 0, 0, 0, lambda x: 'Up to 0.5% down-spread' if x else 'No down spread')
        self.add_result('RESERVED', 0, 1, 5)
        self.add_result(
            'NO_AUX_TRANSACTION_LINK_TRAINING', 0, 6, 6, lambda x: 'Requires AUX transactions to synchronize to a DPTX' if x else 'Does not require AUX transactions when the link configuration is already known')


class ExtendedReceiverCapField(RangeParser):
    name = "NORP & DP_PWR_VOLTAGE_CAP"
    start = 0x2204
    end = 0x2204

    def parse(self):
        self.add_result('Number of Receiver Ports', 0, 0, printfn=lambda x: "{}".format(
            "Two or more receiver ports" if x else "One receiver port"))
        self.add_result('RESERVED', 0, 1, 4)
        self.add_result('5V_DP_PWR_CAP', 0, 5,
                        printfn=lambda x: "{} capable of producing +4.9 to +5.5V".format(" " if x else "Not"))
        self.add_result('12V_DP_PWR_CAP', 0, 6,
                        printfn=lambda x: "{} capable of producing +12V ±10%".format(" " if x else "Not"))
        self.add_result('18V_DP_PWR_CAP', 0, 7,
                        printfn=lambda x: "{} capable of producing +18V ±10%".format(" " if x else "Not"))


class ExtendedReceiveCapFieldPortPresent(RangeParser):
    name = "DOWN_STREAM_PORT_PRESENT"
    start = 0x2205
    end = 0x2205

    def dfp_type(self, val):
        if val == 0b00:
            return "DisplayPort"
        elif val == 0b01:
            return "Analog VGA or analog video over DVI-I"
        elif val == 0b10:
            return "DVI, HDMI, or DP++"
        elif val == 0b11:
            return "Others"

    def parse(self):
        self.add_result("DFP_PRESENT", 0, 0, printfn=lambda x: "{} Branch device and DFP(s)".format(
            "IS" if x else "Not"))
        self.add_result("DFP_TYPE", 0, 1, 2, self.dfp_type)
        self.add_result("FORMAT_CONVERSION", 0, 3, printfn=lambda x: "This {} a format conversion block".format(
            "DFP has" if x else "Branch device does not have"))
        self.add_result("DETAILED_CAP_INFO_AVAILABLE", 0, 4,
                        printfn=lambda x: "DFP capability field is {} byte per port".format("4" if x else "1"))
        self.add_result("Reserved", 0, 5, 7)


class ExtendedReceiveCapFieldChannelCoding(RangeParser):
    name = "MAIN_LINK_CHANNEL_CODING"
    start = 0x2206
    end = 0x2206

    def parse(self):
        self.add_result("ANSI 8b/10b", 0, 0, printfn=lambda x: "DisplayPort receiver {} the Main-Link channel coding specification".format(
            "Support" if x else "Not support"))
        self.add_result("Reserved", 0, 1, 7)


class ExtendedReceiveCapFieldPortCount(RangeParser):
    name = "DOWN_STREAM_PORT_COUNT"
    start = 0x2207
    end = 0x2207

    def dfp_count(self, val):
        if val == 0b00:
            return "No DFPs"
        else:
            return "{} DFPs".format(val)

    def parse(self):
        self.add_result("DFP_COUNT", 0, 0, 3, self.dfp_count)
        self.add_result("RESERVED", 0, 4, 5)
        self.add_result("MSA_TIMING_PAR_IGNORED", 0, 6, printfn=lambda x: "{}".format(
            "Sink device requires the MSA timing parameters" if x else "Sink device is capable of rendering the incoming video stream"))
        self.add_result("OUI Support", 0, 7, printfn=lambda x: "OUI is {} supported".format(
            "" if x else "Not"))


class ExtendedReceiveCapFieldPortxCapx(RangeParser):
    def parse(self):
        self.add_result("RESERVED", 0, 0)
        self.add_result("LOCAL_EDID_PRESENT", 0, 1, printfn=lambda x: "This receiver port {} a local EDID".format(
            "has" if x else "does not have"))
        self.add_result("ASSOCIATED_TO_PRECEDING_PORT", 0, 2,
                        printfn=lambda x: "This port is used for the  {} isochronous stream".format("secondary" if x else "main"))
        self.add_result("RESERVED", 0, 3, 7)


class ExtendedReceiveCapFieldPort0Cap0(ExtendedReceiveCapFieldPortxCapx):
    name = "RECEIVE_PORT0_CAP_0"
    start = 0x2208
    end = 0x2208


class ExtendedReceiveCapFieldPort0Cap1(PrintReserved):
    name = "RECEIVE_PORT0_CAP_1"
    start = 0x2209
    end = 0x2209


class ExtendedReceiveCapFieldPort1Cap0(ExtendedReceiveCapFieldPortxCapx):
    name = "RECEIVE_PORT1_CAP_0"
    start = 0x220A
    end = 0x220A


class ExtendedReceiveCapFieldPort1Cap1(PrintReserved):
    name = "RECEIVE_PORT1_CAP_1"
    start = 0x220B
    end = 0x220B


class ExtendedReceiveCapFieldI2CSpeedCtrlCapBitMap(RangeParser):
    name = "I2C Speed Control Capabilities Bit Map"
    start = 0x220C
    end = 0x220C

    def i2c_speed(self, val):
        if val == 0b00000001:
            return "1Kbps."
        elif val == 0b00000010:
            return "5Kbps."
        elif val == 0b00000100:
            return "10Kbps."
        elif val == 0b00001000:
            return "100Kbps."
        elif val == 0b00010000:
            return "400Kbps."
        elif val == 0b00100000:
            return "1Mbps."
        elif val == 0b01000000:
            return "Reserved."
        elif val == 0b10000000:
            return "Reserved."

    def parse(self):
        self.add_result("I2C Speed", 0, 0, 7, self.i2c_speed)


class ExtendedReceiveCapFieldeDPConfiCap(RangeParser):
    name = "EDP_CONFIGURATION_CAP"
    start = 0x220D
    end = 0x220D

    def parse(self):
        self.add_result("ALTERNATE_SCRAMBLER_RESET_CAPABLE", 0, 0,
                        printfn=lambda x: "{} can use the eDP alternate scrambler".format(" " if x else "Not"))
        self.add_result("RESERVED", 0, 1, 7)


class ExtendedReceiveCapFieldTrainingAuxRDInterval(RangeParser):
    name = "TRAINING_AUX_RD_INTERVAL"
    start = 0x220E
    end = 0x220E

    interval_mapping = {
        0x00: "400us",
        0x01: "4ms",
        0x02: "8ms",
        0x03: "12ms",
        0x04: "16ms",
    }

    def aux_interval(self, val):
        return "00us for the Main-Link Clock Recovery phase; {} for the Main-Link Channel Equalization phase".format(self.interval_mapping.get(val, "400us"))

    def parse(self):
        self.add_result("TRAINING_AUX_RD_INTERVAL", 0, 0, 6, self.aux_interval)
        self.add_result("EXTENDED_RECEIVER_CAPABILITY_FIELD_PRESENT", 0,
                        7, printfn=lambda x: "{} present".format(" " if x else "Not"))


class ExtendedReceiveCapFieldAdapterCap(RangeParser):
    name = "ADAPTOR_CAP"
    start = 0x220F
    end = 0x220F

    def parse(self):
        self.add_result("FORCE_LOAD_SENSE_CAP", 0, 0,
                        printfn=lambda x: "{} support VGA force load adaptor sense mechanism".format("" if x else "Does not"))
        self.add_result("ALTERNATE_I2C_PATTERN_CAP", 0, 1,
                        printfn=lambda x: "{} support alternate i2c patterns".format("" if x else "Does not"))
        self.add_result("Reserved", 0, 2, 7)


class ExtendedReceiveCapFieldEnumerationList(RangeParser):
    name = "DPRX_FEATURE_ENUMERATION_LIST"
    start = 0x2210
    end = 0x2210

    def parse(self):
        self.add_result(
            "GTC_CAP", 0, 0, printfn=lambda x: "{} supported".format("" if x else "Not"))
        self.add_result("SST_SPLIT_SDP_CAP", 0, 1,
                        printfn=lambda x: "{} supported".format("" if x else "Not"))
        self.add_result("AV_SYNC_CAP", 0, 2, printfn=lambda x: "{} supported".format(
            "" if x else "Not"))
        self.add_result("VSC_SDP_EXTENSION_FOR_COLORIMETRY_SUPPORTED", 0,
                        3, printfn=lambda x: "{} supported".format("" if x else "Not"))
        self.add_result("VSC_EXT_VESA_SDP_SUPPORTED", 0, 4,
                        printfn=lambda x: "{} supported".format("" if x else "Not"))
        self.add_result("VSC_EXT_VESA_SDP_CHAINING_SUPPORTED", 0, 5,
                        printfn=lambda x: "{} supported".format("" if x else "Not"))
        self.add_result("VSC_EXT_CEA_SDP_SUPPORTED", 0, 6,
                        printfn=lambda x: "{} supported".format("" if x else "Not"))
        self.add_result("VSC_EXT_CEA_SDP_CHAINING_SUPPORTED", 0, 7,
                        printfn=lambda x: "{} supported".format("" if x else "Not"))


class ExtendedReceiveCapFieldSleepWakeTimeoutRequest(RangeParser):
    name = "EXTENDED_DPRX_SLEEP_WAKE_TIMEOUT_REQUEST"
    start = 0x2211
    end = 0x2211

    timeout_mapping = {
        0x00: "1ms",
        0x01: "20ms",
        0x02: "40ms",
        0x03: "60ms",
        0x04: "80ms",
        0x05: "100ms",
    }

    def wake_timeout(self, val):
        return self.timeout_mapping.get(val, "Reserved")

    def parse(self):
        self.add_result("DPRX_SLEEP_WAKE_TIMEOUT_PERIOD",
                        0, 0, 7, self.wake_timeout)


class ExtendedReceiveCapFieldVSCVesaSDPMaxChaining(RangeParser):
    name = "VSC_EXT_VESA_SDP_MAX_CHAINING"
    start = 0x2212
    end = 0x2212

    def parse(self):
        self.add_result("VSC_EXT_VESA_SDP_MAX_CHAINING_COUNT", 0, 0, 7)


class ExtendedReceiveCapFieldVSCCEASDPMaxChaining(RangeParser):
    name = "VSC_EXT_CEA_SDP_MAX_CHAINING"
    start = 0x2213
    end = 0x2213

    def parse(self):
        self.add_result("VSC_EXT_CEA_SDP_MAX_CHAINING_COUNT", 0, 0, 7)


class ExtendedReceiveCapFieldReserved(PrintReserved):
    name = "RESERVED"
    start = 0x2214
    end = 0x22FF

# --------------------------------------
# DPCD Address 0x3000 - 0x30ff
# --------------------------------------
class ProtocolConverterExtensionFieldCECTunelingCap(RangeParser):
    name = "CEC_TUNNELING_CAPABILITY"
    start = 0x3000
    end = 0x3000

    def parse(self):
        self.add_result("CEC_TUNNELING_CAPABLE", 0, 0,
                        printfn=lambda x: "{} Surpport CEC-Tunnelingover-AUX".format("" if x else "Not"))
        self.add_result("CEC_SNOOPING_CAPABLE", 0, 1,
                        printfn=lambda x: "{} Surpport passively snooping CEC messages".format("" if x else "Not"))
        self.add_result("CEC_MULTIPLE_LA_CAPABLE", 0, 2,
                        printfn=lambda x: "{} Supports  acting as a Follower for multiple CEC Logical Addresses".format("" if x else "Not"))
        self.add_result("RESERVED", 0, 3, 7)


class ProtocolConverterExtensionFieldTunningCtrl(RangeParser):
    name = "CEC_TUNNELING_CONTROL"
    start = 0x3001
    end = 0x3001

    def parse(self):
        self.add_result('CEC_TUNNELING_ENABLE', 0, 0,
                        printfn=lambda x: "Prompts a DP-to-HDMI protocol converter to {} CEC message reception from, and transmission to".format("enable" if x else "disable"))
        self.add_result("CEC_SNOOPING_ENABLE", 0, 1, 1,
                        lambda x: "Receive all CEC messages, regardless of the Destination logical address." if x else "Receive all directly addressed CEC messages")
        self.add_result("RESERVED", 0, 2, 7)


class ProtocolConverterExtensionFieldCECRxMsgInfo(RangeParser):
    name = 'CEC_RX_MESSAGE_INFO'
    start = 0x3002
    end = 0x3002

    def parse(self):
        self.add_result("CEC_RX_MESSAGE_LEN", 0, 0, 3)
        self.add_result('CEC_RX_MESSAGE_HPD_STATE', 0, 4, 4)
        self.add_result('CEC_RX_MESSAGE_HPD_LOST', 0, 5, 5)
        self.add_result('CEC_RX_MESSAGE_ACKED', 0, 6, 6)
        self.add_result('CEC_RX_MESSAGE_ENDED', 0, 7, 7)

class ProtocolConverterExtensionFieldCECTxMsgInfo(RangeParser):
    name = 'CEC_TX_MESSAGE_INFO'
    start = 0x3002
    end = 0x3002

    def parse(self):
        self.add_result("CEC_TX_MESSAGE_LEN", 0, 0, 3)
        self.add_result('CEC_TX_RETRY_COUNT', 0, 4, 6)
        self.add_result('CEC_TX_MESSAGE_SEND / CEC_TX_MESSAGE_BUFFER_UNAVAILABLE', 0, 7, 7)

class ProtocolConverterExtensionFieldCECTunnelingIRQFlags(RangeParser):
    name = "CEC_TUNNELING_IRQ_FLAGS"
    start = 0x3004
    end = 0x3004

    def parse(self):
        self.add_result('CEC_RX_MESSAGE_INFO_VALID', 0, 0, 0)
        self.add_result('CEC_RX_MESSAGE_OVERFLOW', 0, 1, 1)
        self.add_result('Reserved', 0, 2, 3)
        self.add_result('CEC_TX_MESSAGE_SENT', 0, 4, 4)
        self.add_result('CEC_TX_LINE_ERROR', 0, 5, 5)
        self.add_result('CEC_TX_ADDRESS_NACK_ERROR', 0, 6, 6)
        self.add_result('CEC_TX_DATA_NACK_ERROR', 0, 7, 7)
class ProtocolConverterExtensionFieldReserved(PrintReserved):
    name = "Reserved"
    start = 0x3005
    end = 0x300D
class ProtocolConverterExtensionFieldCECLogicalAddrMask(RangeParser):
    name = "CEC_LOGICAL_ADDRESS_MASK"
    start = 0x300E
    end = 0x300F

    def parse(self):
        self.add_result('CEC_LOGICAL_ADDRESS_MASK', 1, 0, 6)
        self.add_result('CEC_LOGICAL_ADDRESS_MASK', 0, 0, 7)
        self.add_result('CEC_LOGICAL_ADDRESS_MASK', 1, 7, 7)
class ProtocolConverterExtensionFieldCECRxMsgBuf(RangeParser):
    name = "CEC_RX_MESSAGE_BUFFER"
    start = 0x3010
    end = 0x301F

    def parse(self):
        self.add_result('CEC_RX_MESSAGE_BUFFER', 0, 0, 7)
        self.add_result('CEC_RX_MESSAGE_BUFFER', 1, 0, 7)
        self.add_result('CEC_RX_MESSAGE_BUFFER', 2, 0, 7)
        self.add_result('CEC_RX_MESSAGE_BUFFER', 3, 0, 7)
        self.add_result('CEC_RX_MESSAGE_BUFFER', 4, 0, 7)
        self.add_result('CEC_RX_MESSAGE_BUFFER', 5, 0, 7)
        self.add_result('CEC_RX_MESSAGE_BUFFER', 6, 0, 7)
        self.add_result('CEC_RX_MESSAGE_BUFFER', 7, 0, 7)
        self.add_result('CEC_RX_MESSAGE_BUFFER', 8, 0, 7)
        self.add_result('CEC_RX_MESSAGE_BUFFER', 9, 0, 7)
        self.add_result('CEC_RX_MESSAGE_BUFFER', 10, 0, 7)
        self.add_result('CEC_RX_MESSAGE_BUFFER', 11, 0, 7)
        self.add_result('CEC_RX_MESSAGE_BUFFER', 12, 0, 7)
        self.add_result('CEC_RX_MESSAGE_BUFFER', 13, 0, 7)
        self.add_result('CEC_RX_MESSAGE_BUFFER', 14, 0, 7)
        self.add_result('CEC_RX_MESSAGE_BUFFER', 15, 0, 7)

class ProtocolConverterExtensionFieldCECTxMsgBuf(RangeParser):
    name = "CEC_TX_MESSAGE_BUFFER"
    start = 0x3020
    end = 0x302F

    def parse(self):
        self.add_result('CEC_TX_MESSAGE_BUFFER', 0, 0, 7)
        self.add_result('CEC_TX_MESSAGE_BUFFER', 1, 0, 7)
        self.add_result('CEC_TX_MESSAGE_BUFFER', 2, 0, 7)
        self.add_result('CEC_TX_MESSAGE_BUFFER', 3, 0, 7)
        self.add_result('CEC_TX_MESSAGE_BUFFER', 4, 0, 7)
        self.add_result('CEC_TX_MESSAGE_BUFFER', 5, 0, 7)
        self.add_result('CEC_TX_MESSAGE_BUFFER', 6, 0, 7)
        self.add_result('CEC_TX_MESSAGE_BUFFER', 7, 0, 7)
        self.add_result('CEC_TX_MESSAGE_BUFFER', 8, 0, 7)
        self.add_result('CEC_TX_MESSAGE_BUFFER', 9, 0, 7)
        self.add_result('CEC_TX_MESSAGE_BUFFER', 10, 0, 7)
        self.add_result('CEC_TX_MESSAGE_BUFFER', 11, 0, 7)
        self.add_result('CEC_TX_MESSAGE_BUFFER', 12, 0, 7)
        self.add_result('CEC_TX_MESSAGE_BUFFER', 13, 0, 7)
        self.add_result('CEC_TX_MESSAGE_BUFFER', 14, 0, 7)
        self.add_result('CEC_TX_MESSAGE_BUFFER', 15, 0, 7)
class ProtocolConverterExtensionFieldDownStreamLinkErrorReport(RangeParser):
    name = "DOWNSTREAM_LINK_ERROR_REPORTING_SUPPORTED"
    start = 0x3030
    end = 0x3030

    def parse(self):
        self.add_result('DOWNSTREAM_LINK_ERROR_REPORTING_SUPPORTED', 0, 0, printfn=lambda x:"{} Supported".format("" if x else "Not"))
        self.add_result('RESERVED', 0, 1, 7)
class ProtocolConverterExtensionFieldDownstreamHDMIErrorStatusCH0(RangeParser):
    name = "DOWNSTREAM_HDMI_ERROR_STATUS_CH0"
    start = 0x3031
    end = 0x3031

    def parse(self):
        self.add_result('DOWNSTREAM_HDMI_ERROR_STATUS_CH0', 0, 0, printfn=lambda x:"{} more than 3 errors since the last read".format("" if x else "Not"))
        self.add_result('DOWNSTREAM_HDMI_ERROR_STATUS_CH0', 0, 1, printfn=lambda x:"{} more than 10 errors since the last read".format("" if x else "Not"))
        self.add_result('DOWNSTREAM_HDMI_ERROR_STATUS_CH0', 0, 2, printfn=lambda x:"{} more than 100 errors since the last read".format("" if x else "Not"))
        self.add_result('Reserved', 0, 3, 7)
class ProtocolConverterExtensionFieldDownstreamHDMIErrorStatusCH1(RangeParser):
    name = "DOWNSTREAM_HDMI_ERROR_STATUS_CH1"
    start = 0x3031
    end = 0x3031

    def parse(self):
        self.add_result('DOWNSTREAM_HDMI_ERROR_STATUS_CH1', 0, 0, printfn=lambda x:"{} more than 3 errors since the last read".format("" if x else "Not"))
        self.add_result('DOWNSTREAM_HDMI_ERROR_STATUS_CH1', 0, 1, printfn=lambda x:"{} more than 10 errors since the last read".format("" if x else "Not"))
        self.add_result('DOWNSTREAM_HDMI_ERROR_STATUS_CH1', 0, 2, printfn=lambda x:"{} more than 100 errors since the last read".format("" if x else "Not"))
        self.add_result('Reserved', 0, 3, 7)
class ProtocolConverterExtensionFieldDownstreamHDMIErrorStatusCH2(RangeParser):
    name = "DOWNSTREAM_HDMI_ERROR_STATUS_CH2"
    start = 0x3031
    end = 0x3031

    def parse(self):
        self.add_result('DOWNSTREAM_HDMI_ERROR_STATUS_CH2', 0, 0, printfn=lambda x:"{} more than 3 errors since the last read".format("" if x else "Not"))
        self.add_result('DOWNSTREAM_HDMI_ERROR_STATUS_CH2', 0, 1, printfn=lambda x:"{} more than 10 errors since the last read".format("" if x else "Not"))
        self.add_result('DOWNSTREAM_HDMI_ERROR_STATUS_CH2', 0, 2, printfn=lambda x:"{} more than 100 errors since the last read".format("" if x else "Not"))
        self.add_result('Reserved', 0, 3, 7)
class ProtocolConverterExtensionFieldSinkYUVComponentBitDepthSupport(RangeParser):
    name = 'HDMI_SINK_YCBCR420_COMPONENT_BIT_DEPTH_SUPPORT'
    start = 0x3034
    end = 0x3034
    def parse(self):
        self.add_result('BIT_DEPTH', 0, 0, printfn=lambda x:'10 bpc is {} supported'.format(""if x else "Not"))
        self.add_result('BIT_DEPTH', 0, 1, printfn=lambda x:'12 bpc is {} supported'.format(""if x else "Not"))
        self.add_result('BIT_DEPTH', 0, 2, printfn=lambda x:'16 bpc is {} supported'.format(""if x else "Not"))
        self.add_result('Reserved', 0, 3, 7)
class ProtocolConverterExtensionFieldReserved3035_304F(PrintReserved):
    name = "Reserved"
    start = 0x3035
    end = 0x304F

class ProtocolConverterExtensionFieldCtrl0(RangeParser):
    name = "PROTOCOL_CONVERTER_CONTROL_0"
    start = 0x3050
    end = 0x3050

    def parse(self):
        self.add_result('HDMI_DVI_OUTPUT_CONFIG', 0, 0, printfn=lambda x:"{}".format("HDMI" if x else "DVI"))
        self.add_result('RESERVED', 0, 1, 7)
class ProtocolConverterExtensionFieldCtrl1(RangeParser):
    name = "PROTOCOL_CONVERTER_CONTROL_1"
    start = 0x3051
    end = 0x3051

    def parse(self):
        self.add_result('CONVERSION_TO_YCBCR420_ENABLE', 0, 0, printfn=lambda x:"{}".format("Enable" if x else "Disable"))
        self.add_result('HDMI_EDID_PROCESSING_DISABLE', 0, 1, printfn=lambda x:"HDMI autonomous EDID processing {}".format("disabled" if x else "enbled"))
        self.add_result('HDMI_AUTONOMOUS_SCRAMBLING_DISABLE', 0, 2, printfn=lambda x:"HDMI autonomous scrambling is {}".format("disabled"if x else "enabled"))
        self.add_result('HDMI_FORCE_SCRAMBLING', 0, 3, printfn=lambda x:"HDMI scrambling is {}".format("enabled"if x else "disabled"))
        self.add_result('RESERVED', 0, 4, 7)
class ProtocolConverterExtensionFieldCtrl2(RangeParser):
    name = "PROTOCOL_CONVERTER_CONTROL_2"
    start = 0x3052
    end = 0x3052

    def parse(self):
        self.add_result('CONVERSION_TO_YCBCR422_ENABLE', 0, 0, printfn=lambda x:"{}".format("Enable" if x else "Disable"))
        self.add_result('RESERVED', 0, 1, 7)

class ProtocolConverterExtensionFieldReserved_3053(PrintReserved):
    name = "Reserved"
    start = 0x3053
    end = 0x3053
class ProtocolConverterExtensionFieldOutputHtt(RangeParser):
    name = "OUTPUT_HTOTAL"
    start = 0x3054
    end = 0x3055

    def parse(self):
        self.add_result('OUTPUT_HTOTAL7:0', 0, 0, 7)
        self.add_result('OUTPUT_HTOTAL15:8', 1, 0, 7)
class ProtocolConverterExtensionFieldOutputHstart(RangeParser):
    name = "OUTPUT_HSTART"
    start = 0x3056
    end = 0x3057

    def parse(self):
        self.add_result('OUTPUT_HSTART7:0', 0, 0, 7)
        self.add_result('OUTPUT_HSTART15:8', 1, 0, 7)
class ProtocolConverterExtensionFieldOutputHSPHSW(RangeParser):
    name = "OUTPUT_HSP_HSW"
    start = 0x3058
    end = 0x3059

    def parse(self):
        self.add_result('OUTPUT_HSP_HSW7:0', 0, 0, 7)
        self.add_result('OUTPUT_HSP_HSW14:8', 1, 0, 6)
        self.add_result('OUTPUT_HSP', 1, 7, 7, lambda x:"Negative pulse" if x else "Positive pulse(default)")

class ProtocolConverterExtensionFieldReserved_305A_30FF(PrintReserved):
    name = "Reserved"
    start = 0x305A
    end = 0x30FF

# --------------------------------------
# DPCD Address 0x60000 - 0x61CFF
# --------------------------------------
class MultiTouchField(PrintReserved):
    name = "RESERVED for Multi-touch (for eDP v1.4 or higher)"
    start = 0x60000
    end = 0x61CFF

# class HDCP13_22Field(PrintReserved):
#     name = "RESERVED for HDCP1.3"
#     start = 0x68000
#     end = 0x68FFF

# class HDCP13_22Field_22(PrintReserved):
#     name = "RESERVED for HDCP2.2"
#     start = 0x69000
#     end = 0x69FFF

# --------------------------------------
# DPCD Address 0x61D00 - 0x67FFF
# --------------------------------------
class DPCD_RESERVED_61d00_67fff(PrintReserved):
    name = "RESERVED"
    start = 0x61D00
    end = 0x67FFF


# --------------------------------------
# DPCD Address 0x68000 - 0x69FFF
# --------------------------------------
class MultiByteKsvParser(MultiByteParser):
    def bit_weight(self, x):
        weight = 0
        for i in x:
            weight += bin(i).count('1')
        return '{} 1s, {} 0s'.format(weight, 40 - weight)

    def parse(self):
        self.add_result(self.bit_weight)


class MultiByteBksv(MultiByteKsvParser):
    name = 'Bksv'
    start = 0x68000
    end = 0x68004


class MultiByteR0Prime(MultiByteParser):
    name = 'R0`'
    start = 0x68005
    end = 0x68006

    def parse(self):
        self.add_result()


class MultiByteAksv(MultiByteKsvParser):
    name = 'Aksv'
    start = 0x68007
    end = 0x6800B


class MultiByteAn(MultiByteParser):
    name = 'An'
    start = 0x6800C
    end = 0x68013

    def parse(self):
        self.add_result()


class MultiByteVPrimeH0(MultiByteParser):
    name = 'V`H0'
    start = 0x68014
    end = 0x68017

    def parse(self):
        self.add_result()


class MultiByteVPrimeH1(MultiByteParser):
    name = 'V`H1'
    start = 0x68018
    end = 0x6801B

    def parse(self):
        self.add_result()


class MultiByteVPrimeH2(MultiByteParser):
    name = 'V`H2'
    start = 0x6801C
    end = 0x6801F

    def parse(self):
        self.add_result()


class MultiByteVPrimeH3(MultiByteParser):
    name = 'V`H3'
    start = 0x68020
    end = 0x68023

    def parse(self):
        self.add_result()


class MultiByteVPrimeH4(MultiByteParser):
    name = 'V`H4'
    start = 0x68024
    end = 0x68027

    def parse(self):
        self.add_result()


class RangeBcaps(RangeParser):
    name = 'Bcaps'
    start = 0x68028
    end = 0x68028

    def parse(self):
        self.add_result('Reserved', 0, 2, 7)
        self.add_result('REPEATER', 0, 1)
        self.add_result('HDCP_CAPABLE', 0, 0)


class RangeBstatus(RangeParser):
    name = 'Bstatus'
    start = 0x68029
    end = 0x68029

    def parse(self):
        self.add_result('Reserved', 0, 4, 7)
        self.add_result('REAUTHENTICATION_REQUEST', 0, 3)
        self.add_result('LINK_INTEGRITY_FAILURE', 0, 2)
        self.add_result('R0`_AVAILABLE', 0, 1)
        self.add_result('READY', 0, 0)


class RangeBinfo(RangeParser):
    name = 'Binfo'
    start = 0x6802A
    end = 0x6802B

    def parse(self):
        self.add_result('MAX_DEVS_EXCEEDED', 0, 7)
        self.add_result('DEVICE_COUNT', 0, 0, 6)
        self.add_result('Reserved', 1, 4, 7)
        self.add_result('MAX_CASCADE_EXCEEDED', 1, 3)
        self.add_result('DEPTH', 1, 0, 2)


class MultiByteKsvFifo(MultiByteParser):
    name = 'KSV FIFO'
    start = 0x6802C
    end = 0x6803A

    def parse(self):
        self.add_result()


class RangeAinfo(RangeParser):
    name = 'Ainfo'
    start = 0x6803B
    end = 0x6803B

    def parse(self):
        self.add_result('Reserved', 0, 1, 7)
        self.add_result('REAUTHENTICATION_ENABLE_IRQ_HPD', 0, 0)


class RangeCPReserved(RangeParser):
    name = 'RESERVED'
    start = 0x6803C
    end = 0x6803C

    def parse(self):
        self.add_result('Reserved', 0, 0, 7)
# --------------------------------------
# DPCD Address 0x6A000 - 0xEFFFF
# --------------------------------------
class DPCD_RESERVED_6A000_EFFFF(PrintReserved):
    name = "RESERVED"
    start = 0x6A000
    end = 0xEFFFF
# --------------------------------------
# DPCD Address 0xF0000 - 0xFFFFF
# --------------------------------------
class LTTunablePHYRepeaterFieldDataStructureRev(RangeParser):
    name = "LT_TUNABLE_PHY_REPEATER_FIELD_DATA_STRUCTURE_REV"
    start = 0xF0000
    end = 0xF0000
    def parse(self):
        self.add_result('Minor Revision Number', 0, 0, 3)
        self.add_result('Major Revision Number', 0, 4, 7)
class LTTunablePHYRepeaterFieldMaxLinkRate(RangeParser):
    name = "MAX_LINK_RATE_PHY_REPEATER"
    start = 0xF0001
    end = 0xF0001

    link_rate = {
        0x06: "1.62",
        0x0a: "2.7",
        0x14: "5.4",
        0x1E: "8.1"
    }
    def get_rate(self, value):
        return "{} Gbps/lane".format(self.link_rate.get(value, "Error"))
    def parse(self):
        self.add_result('MAX_LINK_RATE', 0, 0, 7, self.get_rate)
class LTTunablePHYRepeaterFieldPhyRepeaterCnt(RangeParser):
    name = "PHY_REPEATER_CNT"
    start = 0xF0002
    end = 0xF0002

    link_rate = {
        0x01: "8",
        0x02: "7",
        0x04: "6",
        0x08: "5",
        0x0F: "4",
        0x20: "3",
        0x40: "2",
        0x80: "1"
    }
    def get_repeater_cnt(self, value):
        return "{} PHY Repeater are present".format(self.link_rate.get(value, "Error"))
    def parse(self):
        self.add_result('PHY_REPEATER_CNT', 0, 0, 7, self.get_repeater_cnt)

class LTTunablePHYRepeaterFieldPhyRepeaterMode(RangeParser):
    name = "PHY_REPEATER_MODE"
    start = 0xF0003
    end = 0xF0003

    def repeater_mode(self, value):
        if value == 0x55:
            return "Transparent mode (default)"
        elif value == 0xAA:
            return "Non-transparent mode"
        else:
            return "Error"

    def parse(self):
        self.add_result('PHY_REPEATER_MODE', 0, 0, 7, self.repeater_mode)
class LTTunablePHYRepeaterFieldFECCapCapability(RangeParser):
    name = "Repeater_FEC_CAPABILITY"
    start = 0xF0004
    end = 0xF0004

    def parse(self):
        self.add_result('FEC_CAPABLE', 0, 0, printfn=lambda x:"{} Capable".format("" if x else "Not"))
        self.add_result('UNCORRECTED_BLOCK_ERROR_COUNT_CAPABLE', 0, 1, printfn=lambda x:"{} Capable".format("" if x else "Not"))
        self.add_result('CORRECTED_BLOCK_ERROR_COUNT_CAPABLE', 0, 2, printfn=lambda x:"{} Capable".format("" if x else "Not"))
        self.add_result('BIT_ERROR_COUNT_CAPABLE', 0, 3, printfn=lambda x:"{} Capable".format("" if x else "Not"))
        self.add_result('RESERVED', 0, 4, 7)
class LTTunablePHYRepeaterFieldReservedF0005_F000F(PrintReserved):
    name = "RESERVED for LT-tunable PHY Repeater"
    start = 0xF0005
    end = 0xF000F


class LTTunablePHYRepeaterFieldTrainingPatternSetPhyRepeater1(RangeParser):
    name = "TRAINING_PATTERN_SET_PHY_REPEATER1"
    start = 0xF0010
    end = 0xF0010
    def parse(self):
        self.add_result('TRAINING_PATTERN_SET_PHY_REPEATER1', 0, 7)

class LTTunablePHYRepeaterFieldTrainingLane0SetPhy(RangeParser):
    name = "TRAINING_LANE0_SET_PHY_REPEATER1"
    start = 0xF0011
    end = 0xF0011
    def parse(self):
        self.add_result('TRAINING_LANE0_SET_PHY_REPEATER1', 0, 7)
class LTTunablePHYRepeaterFieldTrainingLane1SetPhy(RangeParser):
    name = "TRAINING_LANE1_SET_PHY_REPEATER1"
    start = 0xF0012
    end = 0xF0012
    def parse(self):
        self.add_result('TRAINING_LANE1_SET_PHY_REPEATER1', 0, 7)
class LTTunablePHYRepeaterFieldTrainingLane2SetPhy(RangeParser):
    name = "TRAINING_LANE2_SET_PHY_REPEATER1"
    start = 0xF0013
    end = 0xF0013
    def parse(self):
        self.add_result('TRAINING_LANE2_SET_PHY_REPEATER1', 0, 7)
class LTTunablePHYRepeaterFieldTrainingLane3SetPhy(RangeParser):
    name = "TRAINING_LANE3_SET_PHY_REPEATER1"
    start = 0xF0014
    end = 0xF0014
    def parse(self):
        self.add_result('TRAINING_LANE3_SET_PHY_REPEATER1', 0, 7)
class LTTunablePHYRepeaterFieldLinkQualLane0SetPhyRepeater1(RangeParser):
    name = "LINK_QUAL_LANE0_SET_PHY_REPEATER1"
    start = 0xF0015
    end = 0xF0015

    def parse(self):
        self.add_result('LINK_QUAL_LANE0_SET_PHY_REPEATER1', 0, 7)
class LTTunablePHYRepeaterFieldLinkQualLane1SetPhyRepeater1(RangeParser):
    name = "LINK_QUAL_LANE1_SET_PHY_REPEATER1"
    start = 0xF0016
    end = 0xF0016

    def parse(self):
        self.add_result('LINK_QUAL_LANE1_SET_PHY_REPEATER1', 0, 7)
class LTTunablePHYRepeaterFieldLinkQualLane2SetPhyRepeater1(RangeParser):
    name = "LINK_QUAL_LANE2_SET_PHY_REPEATER1"
    start = 0xF0017
    end = 0xF0017

    def parse(self):
        self.add_result('LINK_QUAL_LANE2_SET_PHY_REPEATER1', 0, 7)
class LTTunablePHYRepeaterFieldLinkQualLane3SetPhyRepeater1(RangeParser):
    name = "LINK_QUAL_LANE3_SET_PHY_REPEATER1"
    start = 0xF0018
    end = 0xF0018

    def parse(self):
        self.add_result('LINK_QUAL_LANE3_SET_PHY_REPEATER1', 0, 7)
class LTTunablePHYRepeaterFieldReservedF0019_F002F(PrintReserved):
    name = "Reserved"
    start = 0xF0019
    end = 0xF002F

class LTTunablePHYRepeaterFieldLane01StatusPhyRepeater1(RangeParser):
    name = "LANE0_1_STATUS_PHY_REPEATER1"
    start = 0xF0030
    end = 0xF0030

    def parse(self):
        self.add_result('LANE0_1_STATUS_PHY_REPEATER1', 0, 7)
class LTTunablePHYRepeaterFieldLane23StatusPhyRepeater1(RangeParser):
    name = "LANE2_3_STATUS_PHY_REPEATER1"
    start = 0xF0031
    end = 0xF0031

    def parse(self):
        self.add_result('LANE2_3_STATUS_PHY_REPEATER1', 0, 7)
class LTTunablePHYRepeaterFieldLaneAlignStatusUpdated(RangeParser):
    name = "LANE_ALIGN_STATUS_UPDATED_PHY_REPEATER1"
    start = 0xF0032
    end = 0xF0032

    def parse(self):
        self.add_result('LANE_ALIGN_STATUS_UPDATED_PHY_REPEATER1', 0, 7)
class LTTunablePHYRepeaterFieldAdjustRequestLane01(RangeParser):
    name = "ADJUST_REQUEST_LANE0_1_PHY_REPEATER1"
    start = 0xF0033
    end = 0xF0033

    def parse(self):
        self.add_result('ADJUST_REQUEST_LANE0_1_PHY_REPEATER1', 0, 7)
class LTTunablePHYRepeaterFieldAdjustRequestLane23(RangeParser):
    name = "ADJUST_REQUEST_LANE2_3_PHY_REPEATER1"
    start = 0xF0034
    end = 0xF0034

    def parse(self):
        self.add_result('ADJUST_REQUEST_LANE2_3_PHY_REPEATER1', 0, 7)
class LTTunablePHYRepeaterFieldSymbolErrorCntLane0(RangeParser):
    name = "SYMBOL_ERROR_COUNT_LANE0_PHY_REPEATER1"
    start = 0xF0035
    end = 0xF0036

    def parse(self):
        self.add_result('SYMBOL_ERROR_COUNT_LANE0_PHY_REPEATER1', 0, 7)
        self.add_result('SYMBOL_ERROR_COUNT_LANE0_PHY_REPEATER1', 1, 7)
class LTTunablePHYRepeaterFieldSymbolErrorCntLane1(RangeParser):
    name = "SYMBOL_ERROR_COUNT_LANE1_PHY_REPEATER1"
    start = 0xF0037
    end = 0xF0038

    def parse(self):
        self.add_result('SYMBOL_ERROR_COUNT_LANE1_PHY_REPEATER1', 0, 7)
        self.add_result('SYMBOL_ERROR_COUNT_LANE1_PHY_REPEATER1', 1, 7)
class LTTunablePHYRepeaterFieldSymbolErrorCntLane2(RangeParser):
    name = "SYMBOL_ERROR_COUNT_LANE2_PHY_REPEATER1"
    start = 0xF0039
    end = 0xF003A

    def parse(self):
        self.add_result('SYMBOL_ERROR_COUNT_LANE2_PHY_REPEATER1', 0, 7)
        self.add_result('SYMBOL_ERROR_COUNT_LANE2_PHY_REPEATER1', 1, 7)
class LTTunablePHYRepeaterFieldSymbolErrorCntLane3(RangeParser):
    name = "SYMBOL_ERROR_COUNT_LANE3_PHY_REPEATER1"
    start = 0xF003B
    end = 0xF003C

    def parse(self):
        self.add_result('SYMBOL_ERROR_COUNT_LANE3_PHY_REPEATER1', 0, 7)
        self.add_result('SYMBOL_ERROR_COUNT_LANE3_PHY_REPEATER1', 1, 7)
class LTTunablePHYRepeaterFieldIEEEOUI(RangeParser):
    name = 'IEEE_OUI'
    start = 0xF003D
    end = 0xF003F

    def parse(self):
        self.add_result('First two hex digits', 0, 0, 7)
        self.add_result('Second two hex digits', 1, 0, 7)
        self.add_result('Third two hex digits', 2, 0, 7)


class LTTunablePHYRepeaterFieldLTtunnablePhyRepeaterDevIdStr(RangeParser):
    name = "LT-tunable PHY Repeater Device Identification String"
    start = 0xF0040
    end = 0xF0045

    def parse(self):
        def decode_bytes(x):
            try:
                decoded_str = chr(x)
                print("decoded_str:"+decoded_str+" x:"+chr(x))
                return '"{}"'.format(decoded_str)
            except UnicodeDecodeError as e:
                return 'Decoding Error: {}'.format(e)

        self.add_result(' ', 0, 0, 7, decode_bytes)
        self.add_result(' ', 1, 0, 7, decode_bytes)
        self.add_result(' ', 2, 0, 7, decode_bytes)
        self.add_result(' ', 3, 0, 7, decode_bytes)
        self.add_result(' ', 4, 0, 7, decode_bytes)
        self.add_result(' ', 5, 0, 7, decode_bytes)

class LTTunablePHYRepeaterFieldHardwareRev(RangeParser):
    name = "Hardware Revision"
    start = 0xF0046
    end = 0xF0048

    def parse(self):
        self.add_result("Hardware Revision", 0, 0, 7)
        self.add_result("Firmware/Software Major Revision", 1, 0, 7)
        self.add_result("Firmware/Software Minor Revision", 2, 0, 7)

class LTTunablePhyRepeaterField(RangeParser):
    name = "FEC_ERROR_COUNT_PHY_REPEATER1"
    start = 0xF0291
    end = 0xF092

    def parse(self):
        self.add_result('FEC_ERROR_COUNT_PHY_REPEATER1_7:0', 0, 0, 7)
        self.add_result('FEC_ERROR_COUNT_PHY_REPEATER1_14:8', 1, 0, 6)
        self.add_result('FEC_ERROR_COUNT_VALID', 1, 7, 7, lambda x : "{} Valid".format("" if x else "Not"))

class LTTunablePHYRepeaterFieldReservedF0292_F0297(PrintReserved):
    name = "RESERVED"
    start = 0xF0293
    end = 0xF0297

class FECPrintConfig(RangeParser):
    def parse(self):
        self.add_result(' ', 0, 0, 7)
        self.add_result(' ', 1, 0, 7)
        self.add_result(' ', 2, 0, 7)
        self.add_result(' ', 3, 0, 7)
        self.add_result(' ', 4, 0, 7)
        self.add_result(' ', 5, 0, 7)
        self.add_result(' ', 6, 0, 7)
        self.add_result(' ', 7, 0, 7)
class LTTunablePHYRepeaterFieldFecPhyRepeater2ConfigAndStatus(FECPrintConfig):
    name = "FEC_PHY_REPEATER2 CONFIGURATION AND STATUS FIELD"
    start = 0xF0298
    end = 0xF029F

class LTTunablePHYRepeaterFieldFecPhyRepeater3ConfigAndStatus(FECPrintConfig):
    name = "FEC_PHY_REPEATER3 CONFIGURATION AND STATUS FIELD"
    start = 0xF02A0
    end = 0xF02A7

class LTTunablePHYRepeaterFieldFecPhyRepeater4ConfigAndStatus(FECPrintConfig):
    name = "FEC_PHY_REPEATER4 CONFIGURATION AND STATUS FIELD"
    start = 0xF02A8
    end = 0xF02AF
class LTTunablePHYRepeaterFieldFecPhyRepeater5ConfigAndStatus(FECPrintConfig):
    name = "FEC_PHY_REPEATER4 CONFIGURATION AND STATUS FIELD"
    start = 0xF02B0
    end = 0xF02B7
class LTTunablePHYRepeaterFieldFecPhyRepeater6ConfigAndStatus(FECPrintConfig):
    name = "FEC_PHY_REPEATER4 CONFIGURATION AND STATUS FIELD"
    start = 0xF02B8
    end = 0xF02BF
class LTTunablePHYRepeaterFieldFecPhyRepeater7ConfigAndStatus(FECPrintConfig):
    name = "FEC_PHY_REPEATER4 CONFIGURATION AND STATUS FIELD"
    start = 0xF02C0
    end = 0xF02C7
class LTTunablePHYRepeaterFieldFecPhyRepeater8ConfigAndStatus(FECPrintConfig):
    name = "FEC_PHY_REPEATER4 CONFIGURATION AND STATUS FIELD"
    start = 0xF02C8
    end = 0xF02CF
class LTTunablePHYRepeaterFieldReservedF02D0_F02FF(PrintReserved):
    name = "RESERVED"
    start = 0xF02D0
    end = 0xF02FF

# class LTTunablePHYRepeaterFeld

# --------------------------------------
# DPCD Address 0xFFF00 - 0xFFFFF
# --------------------------------------

class MyDPSpecReserved(PrintReserved):
    name = "RESERVED"
    start = 0xFFF00
    end = 0xFFF00

class MyDPSpec(RangeParser):
    name = "MyDP_POWR_CAP"
    start = 0xFFF01
    end = 0xFFF01

    def parse(self):
        self.add_result('MyDP_POWR_CAP', 0, 7)

class DPCD_RESERVED_FFF02_FFFFF(PrintReserved):
    name = "RESERVED"
    start = 0xFFF02
    end = 0xFFFFF
def print_dpcd_address_mapping():
    addr_mapping = """
                Table 2-154: DPCD Field Address Mapping
    -------------------------------------------------------------------
      DPCD Address    |        DPCD Field                |    See
    -------------------------------------------------------------------
    00000h - 000FFh   |   Receiver Capability            |  Table 2-155
    00100h - 001FFh   |   Link Configuration             |  Table 2-156
    00200h - 002FFh   |   Link/Sink Device Status        |  Table 2-157
    00300h - 003FFh   |   Source Device-specific         |  Table 2-158
    00400h - 004FFh   |   Sink Device-specific           |  Table 2-159
    00500h - 005FFh   |   Branch Device-specific         |  Table 2-160
    00600h - 006FFh   |   Link/Sink Device Power Control |  Table 2-161
    00700h - 007FFh   |   eDP-specific                   |  Table 2-162
    00800h - 00FFFh   |   RESERVED (usage to be defined) |      –
    01000h - 017FFh   |   Sideband MSG Buffers           |  Table 2-163
    01800h - 01FFFh   |   RESERVED (usage to be defined) |      –
    02000h - 021FFh   |   DPRX Event Status Indicator    |  Table 2-164
    02200h - 022FFh   |   Extended Receiver Capability   |  Table 2-165
    02300h - 02FFFh   |   RESERVED (usage to be defined) |      –
    03000h - 030FFh   |   Protocol Converter Extension   |  Table 2-166
    03100h - 5FFFFh   |   RESERVED (usage to be defined) |      –
    60000h - 61CFFh   |   Multi-touch (for eDP)          |  Table 2-167
    61D00h - 67FFFh   |   RESERVED (usage to be defined) |      –
    68000h - 69FFFh   |   HDCP 1.3 and HDCP2.2           |  Table 2-168
    6A000h - EFFFFh   |   RESERVED (usage to be defined) |      –
    F0000h - F02FFh   |   LT-tunable PHY Repeater        |  Table 2-169
    F0300h - FFEFFh   |   RESERVED (usage to be defined) |      –
    FFF00h - FFFFFh   |   MyDP-specific                  |  Table 2-170
    """
    print(addr_mapping)


class Parser(object):
    def __init__(self):
        self.registry = self.build_registry(ParserBase)
        self.result = []
        self.unparsed = {}

    def build_registry(self, cls):
        ret = []
        for c in cls.__subclasses__():
            ret += self.build_registry(c)
        # BADCODE: assume if a class is subclassed, it is not a parser
        if not ret:
            ret.append(cls)
        return ret

    def print_mapping(self):
        print_dpcd_address_mapping()

    def parse(self, bytes, offset):
        i = 0
        while i < len(bytes):
            addr = i + offset
            parsed_bytes = 0
            for r in self.registry:
                if not r.can_parse(addr):
                    continue

                parser = r(bytes, i)
                parser.parse()
                parsed_bytes = parser.num_bytes()
                self.result.append(parser)
                break

            if not parsed_bytes:
                self.unparsed[addr] = bytes[i]
                i += 1
            else:
                i += parsed_bytes

    def parse_hdcp(self, data):
        for r in self.registry:
            if not r.can_parse(data[0]):
                continue
            parser = r(data, 1)
            parser.parse()
            self.result.append(parser)
            break

    def print(self):
        print("-----------------------------------------------------------")
        for r in self.result:
            r.print()

        if not self.unparsed:
            print("-----------------------------------------------------------")
            return

        print('')
        print('-- Unparsed values')
        for a, v in self.unparsed.items():
            print('{:<10}{:<41}[{}]'.format(hex(a),
                                            'UNKNOWN',
                                            hex(v)))
        print("-----------------------------------------------------------")
