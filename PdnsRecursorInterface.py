#!/usr/bin/env python
"""このモジュールは、pdns-recursor のインターフェース設定を変更する為に存在します。
このモジュールは、以下のクラスを含みます
PdnsRecursorInterface

このモジュールは以下のパッケージを必要とします。
netifaces
pathlib
re
"""

import netifaces
import pathlib
import re
import sys


##########################################################################
class PdnsRecursorInterface:
    ##########################################################################
    """PdnsRecursorInterface は、pdns-recursor のインターフェース設定を変更するクラスです。
    このクラスは Linux / NUIX で動作します。"""
    ##########################################################################
    pdns_recursor_config_file = '/etc/pdns-recursor/recursor.conf'
    pdns_recursorInterfaceTemplate = '\tinterface:\t%(address)s'
    pdns_recursor_open_address_pattern = r'^(\s*local-address\s*=)(.*)$'

    ##########################################################################
    def __init__(self, config_file_path='/etc/pdns-recursor/recursor.conf', interface_pattern='^en', interface_flag=0):
        """このクラスは、ネットワークハードウェアのインターフェースから pdns_recursor のインターフェース設定ファイルを作成します。"""
        ##########################################################################
        self.config_file_path = config_file_path
        self.set_interface_pattern(interface_pattern, interface_flag)

    ##########################################################################
    def __del__(self):
        pass

    ##########################################################################
    def set_interface_pattern(self, interface_pattern='^en', interface_flag=0):
        """ハードウェア・ネットワークインターフェースの正規表現パターンを設定します。"""
        ##########################################################################
        self.interface_pattern = interface_pattern
        self.interface_flag = interface_flag
        self.interface_regexp = re.compile(self.interface_pattern, self.interface_flag)
        self.open_address_regexp = re.compile(self.pdns_recursor_open_address_pattern)

    ##########################################################################
    def get_net_hard_interfaces(self):
        """全てのハードウェア・ネットワークインターフェースを取得します。"""
        ##########################################################################
        net_hard_interfaces = []
        for interface in netifaces.interfaces():
            if self.interface_regexp.search(interface):
                net_hard_interfaces.append(interface)
            else:
                continue
        return net_hard_interfaces

    ##########################################################################
    def get_net_hard_interface_ipv4_addresses(self):
        """全てのハードウェア・ネットワークインターフェースの IPv4 アドレスを取得します。"""
        ##########################################################################
        net_hard_interface_addresses = []
        for interface in self.get_net_hard_interfaces():
            net_hard_interface_addresses.append(netifaces.ifaddresses(interface)[netifaces.AF_INET][0]['addr'])
        return net_hard_interface_addresses

    ##########################################################################
    def get_net_hard_interface_ipv6_addresses(self):
        """全てのハードウェア・ネットワークインターフェースの IPv6 アドレスを取得します。"""
        ##########################################################################
        net_hard_interface_addresses = []
        for interface in self.get_net_hard_interfaces():
            net_hard_interface_addresses.append(netifaces.ifaddresses(interface)[netifaces.AF_INET6][0]['addr'])
        return net_hard_interface_addresses

    ##########################################################################
    def write_pdns_recursor_config_file(self, including_ipv6=False):
        """pdns_recursor のインターフェースファイルを作成します。"""
        ##########################################################################
        config_file = pathlib.Path(self.config_file_path)
        address_list = ['127.0.0.1', '::1']
        for address in self.get_net_hard_interface_ipv4_addresses():
            address_list.append(address)
        if including_ipv6:
            for address in self.get_net_hard_interface_ipv6_addresses():
                address_list.append(address)
        lines = []
        with config_file.open(mode='r') as file:
            for line in file:
                m = self.open_address_regexp.match(line)
                if m:
                    line = m.group(1) + ', '.join(address_list) + "\n"
                    lines.append(line)
                else:
                    lines.append(line)

        with config_file.open(mode='w') as file:
            for line in lines:
                print(line, file=file, end='')


#            for address in address_list:
#                line = PdnsRecursorInterface.pdns_recursorInterfaceTemplate % {'address': address}
#                print(line, file=interface_file)


##########################################################################
__all__ = ['PdnsRecursorInterface']
