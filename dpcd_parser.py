#!/usr/bin/env python3
import argparse
import collections
import re
import sys

import parser_hpcd

DrmLog = collections.namedtuple('DrmLog',
                                [
                                    'operation',
                                    'port',
                                    'offset',
                                    'type',
                                    'retcode',
                                    'bytes',
                                    'timestamp'
                                ])


def log_bytes_to_list(log_bytes):
    ret = []
    for b in log_bytes.split(' '):
        ret.append(int(b, 16))
    return ret


def cmdline_to_list(addr, params):
    # Remove the "0x" prefix from the input parameters if it exists
    params = params.replace("0x", "")

    # Calculate the number of bytes based on the length of the input parameters
    num_bytes = (len(params) + 1) // 2

    # Pad the input parameters with leading zeros to make sure it has even length
    params = params.zfill(num_bytes * 2)

    # Split the input parameters into individual bytes and convert them to integers
    byte_values = [int(params[i:i + 2], 16) for i in range(0, len(params), 2)]

    # Insert the first address value at the beginning of the list
    byte_values.insert(0, int(addr, 16))

    return byte_values

def log_reader():
    patt_ts = r'(?:.{16}-[0-9]+\s+\[[0-9]+\] .{4}\s+([0-9]+\.[0-9]+): drm_trace_printf:)'
    patt_legacy_ts = r'(?:\[\s*(?:[0-9]+\s+)?([0-9]+\.[0-9]+)\])'
    patt_timestamp = f'(?:{patt_ts}|{patt_legacy_ts})'
    patt_function = r'\[(?:drm:)?drm_dp_dpcd_(read|write)\]'
    patt_port = r'([^:]+):'
    patt_addr = r'0x([0-9A-Fa-f]+)'
    patt_type = r'([\S]+)'
    patt_dir = r'-[><]'
    patt_ret = r'\(ret=\s+([0-9-]+)\)'
    patt_data = r'((?:[0-9a-fA-F]{2}\s?)+)'
    patt_whitespace = r'\s+'
    pattern = r'{ts}{ws}{fn}{ws}{pt}{ws}{ad}{ws}{tp}{ws}{dr}{ws}{rt}{ws}{dt}'.format(
        ts=patt_timestamp, fn=patt_function, pt=patt_port, ad=patt_addr, tp=patt_type,
        dr=patt_dir, rt=patt_ret, dt=patt_data, ws=patt_whitespace
    )
    regex = re.compile(pattern)
    for line in sys.stdin:
        if line == '\n':
            break
        line = line.rstrip()
        m = regex.findall(line)
        if m:
            d = DrmLog(operation=m[0][2],
                       port=m[0][3],
                       offset=int(m[0][4], 16),
                       type=m[0][5],
                       retcode=int(m[0][6]),
                       bytes=log_bytes_to_list(m[0][7]),
                       timestamp=m[0][0] if m[0][0] else m[0][1])
            p = parser_hpcd.Parser()
            p.parse(d.bytes, d.offset)
            print('')
            print('[{}] {} {} [{}:{}] on {}'.format(d.timestamp, d.type, d.operation, hex(
                d.offset), hex(d.offset + len(d.bytes) - 1), d.port))
            p.print()


def main():
    arg_parser = argparse.ArgumentParser(description='Parse DPCD registers')
    arg_parser.add_argument(
        '--dpcd', help='DPCD values, base16 space separated', default=None)
    arg_parser.add_argument(
        '-m', help='DPCD Field Address Mapping', action='store_true', default=None)
    arg_parser.add_argument(
        '-p', '--parse', help='Read DPCD registers value and parse them. [dpcd_parser.py -p 0x3000  0x1]',  default=None)
    arg_parser.add_argument(
        '--logs', help='Read logs from stdin', action='store_true', default=False)
    args = arg_parser.parse_args()

    if args.dpcd:
        p = parser_hpcd.Parser()
        dpcd = log_bytes_to_list(args.dpcd)
        p.parse(dpcd, 0)
        p.print()

    if args.logs:
        data = log_reader()

    if args.parse:
        params = args.parse.split()
        if len(params) == 2:
            print("addr:" + params[0] + " value:" + params[1])
        else:
            print("Error, args len is " + str(len(params)))
            return
        p = parser_hpcd.Parser()
        data = cmdline_to_list(params[0], params[1])
        if 2 > len(data):
            print("Error, args len is " + str(len(data)))
            print("./" + arg_parser.prog + " -p 0x3000  0x1")
            return
        print(data)
        p.parse_hdcp(data)
        p.print()

    if args.m:
        p = parser_hpcd.Parser()
        p.print_mapping()


if __name__ == '__main__':
    main()
