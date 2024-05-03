#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import re
import urllib.request
from pathlib import Path
import subprocess
import configparser


if __name__ == '__main__':
    # root ユーザーのみ許可する
    if 0 != os.getuid():
        print( 'root ユーザーではありません。', file=sys.stderr)
        exit(1)

    if 0 != subprocess.run(['systemctl', 'status', 'firewalld'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
        print( 'FirewallD が動作していません。', file=sys.stderr)
        exit(1)

    # 環境設定ファイル
    config_file = '/usr/local/etc/ipDeny/ipDeny.conf'

    # 環境設定の読み込み
    config = configparser.ConfigParser()
    config.read(config_file)

    # 拒否する国のコードを小文字で取得
    deny_countries = config['DEFAULT']['deny_country'].strip().lower()
    deny_countries_list = re.split(r',\s*', deny_countries)

    print(deny_countries_list)

    # 作業ディレクトリの取得
    tmp_dir = Path(config['DEFAULT']['tmp_directory'])
    if not tmp_dir.exists():
        print( '作業ティレクトリが存在しません', file=sys.stderr)
        exit(1)
    if not tmp_dir.is_dir():
        print( '作業ティレクトリの指定が不正です。', file=sys.stderr)
        exit(1)

    # ゾーンファイルの拡張子を取得
    zone_suffix = config['DEFAULT']['address_file_suffix']

    # URL の取得
    url_ipv4 = config['DEFAULT']['url_ipv4']
    url_ipv6 = config['DEFAULT']['url_ipv6']

    # URL が「/」で終わっていない場合は追加
    if not url_ipv4.endswith('/'):
        url_ipv4 += '/'
    if not url_ipv6.endswith('/'):
        url_ipv6 += '/'

    # 一時ファイルの自動削除フラグの取得
    tmp_file_auto_remove = config['DEFAULT']['auto_remove_download_file'].lower()

    # ipset リストの取得
    with subprocess.Popen(['firewall-cmd', '--permanent', '--get-ipsets'], stdout=subprocess.PIPE) as proc:
        ipsets_str = proc.stdout.read().decode('utf-8').strip()
        ipset_list = re.split(r'[\s\n]+', ipsets_str)

    # drop ゾーンの sources リストを取得
    with subprocess.Popen(['firewall-cmd', '--permanent', '--zone=drop', '--list-sources'], stdout=subprocess.PIPE) as proc:
        drop_sources_str = proc.stdout.read().decode('utf-8').strip()
        drop_sources_list = re.split(r'[\s\n]+', drop_sources_str)

    for deny_country in deny_countries_list:
        # ファイル名の作成
        master_filename = f'{deny_country}{zone_suffix}'
        ipv4_filename = f'{master_filename}.ipv4'
        ipv6_filename = f'{master_filename}.ipv6'

        # URL の作成
        url_path_ipv4 = url_ipv4 + master_filename
        url_path_ipv6 = url_ipv6 + master_filename

        # 一時ファイルのパス作成
        tmp_file_ipv4 = tmp_dir.joinpath(ipv4_filename)
        tmp_file_ipv6 = tmp_dir.joinpath(ipv6_filename)

        print(url_path_ipv4)
        print(url_path_ipv6)

        # ipv4 ファイルを取得
        with urllib.request.urlopen(url_path_ipv4) as response:
            tmp_file_ipv4.write_text(response.read().decode('utf-8'))

        # ipv6 ファイルを取得
        with urllib.request.urlopen(url_path_ipv6) as response:
            tmp_file_ipv6.write_text(response.read().decode('utf-8'))

        print(tmp_file_ipv4)
        print(tmp_file_ipv6)

        # ipv4 を ipset に追加
        if ipv4_filename not in ipset_list:
            subprocess.run(
                ['firewall-cmd', '--permanent', f'--new-ipset={ipv4_filename}', '--type=hash:net'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

        # ipv6 を ipset に追加
        if ipv6_filename not in ipset_list:
            subprocess.run(
                ['firewall-cmd', '--permanent', f'--new-ipset={ipv6_filename}', '--type=hash:net', '--option=family=inet6'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

        # ipv4 ipset をファイルから読み込む
        subprocess.run(
            ['firewall-cmd', '--permanent', f'--ipset={ipv4_filename}', f'--add-entries-from-file={tmp_file_ipv4}'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        # ipv6 ipset をファイルから読み込む
        subprocess.run(
            ['firewall-cmd', '--permanent', f'--ipset={ipv6_filename}', f'--add-entries-from-file={tmp_file_ipv6}'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        # ipv4 DROP ゾーンに ipset を追加
        if f'{ipv4_filename}' not in drop_sources_list:
            subprocess.run(
                ['firewall-cmd', '--permanent', '--zone=drop', '--add-source', f'ipset:{ipv4_filename}'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

        # ipv6 DROP ゾーンに ipset を追加
        if f'{ipv6_filename}' not in drop_sources_list:
            subprocess.run(
                ['firewall-cmd', '--permanent', '--zone=drop', '--add-source', f'ipset:{ipv6_filename}'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

        # 一時ファイルの削除
        if tmp_file_auto_remove in ['ok', 'yes']:
            tmp_file_ipv4.unlink()
            tmp_file_ipv6.unlink()

    if 0 != subprocess.run(['firewall-cmd', '--reload'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
        print( '設定の反映に失敗しました。', file=sys.stderr)
        exit(1)

    exit(0)
