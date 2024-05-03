#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import re
from socket import inet_aton
import struct
import urllib.request
import io
import xml.etree.ElementTree as ET
import filecmp
import pathlib
import shutil
import os
import subprocess


def tor_address_ipv4(file=sys.stdout, url='https://check.torproject.org/exit-addresses'):
    """ファイルに Tor 出口 IPv4 アドレスを出力する。"""
    # 正規表現パターンを 正規表現オブジェクト にコンパイル
    # IPv4 アドレス抽出用
    prog = re.compile(r'ExitAddress\s+(\d+\.\d+\.\d+\.\d+)\s+.*$', re.IGNORECASE)

    address_list = []
    # Tor の出口リストの取得
    req = urllib.request.Request(url=url, method='GET')
    with urllib.request.urlopen(req) as f:
        if f.status not in [200, 301]:
            print(f'サーバーの接続に失敗しました。({f.status})', file=sys.stderr)
            return False
        elif f.status == 301:
            print(f'警告：サーバーが移転したようです。({f.status})', file=sys.stderr)

        for line in re.split(r'\r?\n', f.read().decode('utf-8').strip()):
            result = prog.search(line)
            if result is None:
                continue
            if result.group(1) in address_list:
                continue

            address_list.append(result.group(1))

    if len(address_list) < 1:
        print('アドレスの取得に失敗しました。', file=sys.stderr)

    # アドレスをソートして出力
    address_list = sorted(address_list, key=lambda ip: struct.unpack("!L", inet_aton(ip))[0])
    for address in address_list:
        print(address, file=file)

    return True


def firewalld_tor_ipset(path, url='https://check.torproject.org/exit-addresses'):
    """FirewallD の ipset 形式（XML）で出力します。"""
    with io.StringIO() as f:
        if not tor_address_ipv4( file=f, url=url):
            return False
        f.seek(0, io.SEEK_SET)


        rootElement = ET.Element('ipset', {'type':'hash:net'})
        for line in f.readlines():
            ET.SubElement( rootElement, 'entry').text = line.strip()

    tree = ET.ElementTree(rootElement)
    ET.indent(tree, '    ')

    encoding = 'utf-8'
    tree.write(path, encoding=encoding, xml_declaration=True)

    return True


if __name__ == '__main__':

    if os.getuid() != 0:
        print('root ユーザー以外は実行できません。', file=sys.stderr)
        exit(1)

    url = 'https://check.torproject.org/exit-addresses'
    filrname = 'Tor.xml'
    tmp_file = pathlib.Path('/tmp').joinpath(filrname)
    ipset_file = pathlib.Path('/etc/firewalld/ipsets').joinpath(filrname)

    if not firewalld_tor_ipset(path=tmp_file.absolute()):
        print('Tor 情報の取得に失敗しました。', file=sys.stderr)
        exit(1)
    if ipset_file.exists():
        if filecmp.cmp(tmp_file, ipset_file, shallow=False):
            tmp_file.unlink()
            print('Tor ファイルの更新は必要ありません。')
            exit(0)

    shutil.move(tmp_file, ipset_file)
    if subprocess.run(['restorecon', ipset_file.absolute()]).returncode != 0:
        print(f'ERROR: restorecon {ipset_file.absolute()}', file=sys.stderr)
        exit(1)

    drop_sources_list = []

    # drop ゾーンの sources リストを取得
    with subprocess.Popen(['firewall-cmd', '--permanent', '--zone=drop', '--list-sources'], stdout=subprocess.PIPE) as proc:
        drop_sources_str = proc.stdout.read().decode('utf-8').strip()
        drop_sources_list = re.split(r'[\s\n]+', drop_sources_str)

    ipv4_filename = ipset_file.name.split('.')[0]
    if f'ipset:{ipv4_filename}' not in drop_sources_list:
        subprocess.run(
            ['firewall-cmd', '--permanent', '--zone=drop', '--add-source', f'ipset:{ipv4_filename}'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

    if 0 != subprocess.run(['firewall-cmd', '--reload'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
        print( '設定の反映に失敗しました。', file=sys.stderr)
        exit(1)

    exit(0)
