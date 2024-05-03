#!/usr/bin/env python
"""
このプログラムは、入力された IPV4 アドレスの DROP マスクを作成します。
"""
import sys
import re
import configparser
import maxminddb
import subprocess


def int_ip_from_str(str):
    """
    ipv4 文字列から　int の ip アドレスを作成する。
    :param str: ipv4 アドレス
    :return: int の ipv4 アドレス
    """
    ipv4list = re.split(r'\.', str)
    address = 0

    for part in ipv4list:
        address *= 256
        address += int(part)

    return address


def whois(str):
    """
    whois をサブプロセスで実行する。
    :param str: ipv4 アドレス
    :return: dic 項目
    """
    ret = {'start': '0.0.0.0', 'end': '0.0.0.0'}
    with subprocess.Popen(['whois', str], stdout=subprocess.PIPE) as proc:
        for line in proc.stdout.readlines():
            m = re.match(r'^(inetnum|NetRange):\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*-\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})',
                         line.decode('utf-8'))
            if m:
                ret['start'] = m.group(2)
                ret['end'] = m.group(3)
                break

    return ret


def mask_len(mask):
    """
    マスクからマスク長を取り出す。
    :param mask: int マスク
    :return: マスク長
    """

    count = 0
    mask &= 0x0ffffffff
    for shift in range(32):
        if mask & (0x01 << shift):
            count += 1

    return count


# Shift+F10 を押して実行するか、ご自身のコードに置き換えてください。
# Shift を2回押す を押すと、クラス/ファイル/ツールウィンドウ/アクション/設定を検索します。


if __name__ == '__main__':

    args = sys.argv
    address_list = []
    addressDB = {}

    for arg in args:
        # IPV4 アドレスだけを抜き出す
        if re.match(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', arg):
            address_list.append(arg)

    if len(address_list) < 1:
        print('USAGE: dropMask ipv4アドレス')
        sys.exit(1)

    print(address_list)

    # 設定ファイル読み込み
    config = configparser.ConfigParser()
    config.read('/usr/local/etc/dropMask/dropMask.conf')

    # 国の拒否リスト
    deny_countries = re.split(r',\s*', config['DEFAULT']['deny_country'])

    print(deny_countries)

    reader = maxminddb.Reader(config['DEFAULT']['maxminddb'])

    for address in address_list:
        addressDB[address] = {'country': reader.get(address)['country']['iso_code']}
        addressDB[address]['name'] = reader.get(address)['country']['names']['ja']
        addressDB[address]['status'] = 'deny' if addressDB[address]['country'] in deny_countries else 'allow'
        addressDB[address]['int'] = int_ip_from_str(address)

        ret = whois(address)
        addressDB[address]['start'] = ret['start']
        addressDB[address]['start_int'] = int_ip_from_str(ret['start'])
        addressDB[address]['end'] = ret['end']
        addressDB[address]['end_int'] = int_ip_from_str(ret['end'])

        addressDB[address]['mask'] = 0x0ffffffff - (addressDB[address]['end_int'] - addressDB[address]['start_int'])
        addressDB[address]['mask_len'] = mask_len(addressDB[address]['mask'])

        addressDB[address]['hash'] = addressDB[address]['start'] + '/' + str(addressDB[address]['mask_len'])

        print(bin(addressDB[address]['mask']))

    print(addressDB)

    sys.exit(0)
