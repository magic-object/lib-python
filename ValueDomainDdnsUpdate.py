#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import re
import socket
import dns.resolver
import urllib.request

if __name__ == '__main__':

    domain_name = 'magic-object.com'
    password = 'KanraKara4Domain'
    status_dict = { '0': '更新に成功',
                    '1': '不正なリクエスト',
                    '2': '不正なドメインとパスワード',
                    '3': '不正なIPアドレス',
                    '4': 'パスワードが一致しない',
                    '5': 'データベースサーバーが混雑している',
                    '8': '更新対象のレコードがない',
                    '9': 'その他のエラー',
                    '503': '連続アクセス等の過負荷エラー'
                    }

    # グローバルIPの取得
    global_ipaddress = None

    req = urllib.request.Request(url='http://inet-ip.info/ip', method='GET')
    with urllib.request.urlopen(req) as f:
        if f.status == 200:
            global_ipaddress = f.read().decode('utf-8').strip()

    if global_ipaddress is None:
        req = urllib.request.Request(url='http://globalip.me', method='GET')
        req.add_header('User-Agent', 'curl')
        with urllib.request.urlopen(req) as f:
            if f.status == 200:
                global_ipaddress = f.read().decode('utf-8').strip()

    # グローバルIPアドレスの取得失敗
    if global_ipaddress is None:
        print('Get faild Global IP Address!!', file=sys.stderr)
        exit(1)

    # 外部 DNS から現在のアドレスを取得
    resolver = dns.resolver.Resolver()
    resolver.nameservers = ['8.8.8.8', '8.8.4.4']
    address_list = resolver.resolve(domain_name, 'A')
    for ipaddress in address_list:
        if global_ipaddress == str(ipaddress):
            print(f'アドレス({global_ipaddress})の変更は必要ありません。')
            exit(0)

    # VALUE DOMAIN にアドレスを登録
    print('アドレスの変更が必要です。')
    post_data = f'd={domain_name}&p={password}&h=*&i={global_ipaddress}'.encode('utf-8')
    req = urllib.request.Request(url='https://dyn.value-domain.com/cgi-bin/dyn.fcg', data=post_data, method='POST')
    with urllib.request.urlopen(req) as f:
        if f.status == 200:
            message = ''
            results = f.read().decode('utf-8').strip()
            match = re.match(r'status\s*=\s*(\d+)', results, re.IGNORECASE)
            if match is not None:
                code = match.group(1)
                if code in status_dict:
                    message = status_dict[code]
                if code == '0':
                    print(f'{domain_name} は {global_ipaddress} に設定されました。')
                else:
                    print(f'{domain_name} のアドレス({global_ipaddress})変更は、失敗しました。{results} 理由:{message}', file=sys.stderr)
                    exit(1)
            else:
                print(f'{domain_name} のアドレス({global_ipaddress})変更は、失敗しました。{results} 理由:{message}', file=sys.stderr)
                exit(1)
        else:
            print(f'{domain_name} のアドレス({global_ipaddress})変更は、失敗しました。　接続ステータス:{f.status}', file=sys.stderr)
            exit(1)

    exit(0)