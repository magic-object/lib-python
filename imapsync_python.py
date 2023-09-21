#!/usr/bin/env python
"""このモジュールは、マスターの imap サーバーを local のimap サーバーに対し、同期を行なう為に存在します。
このモジュールは、以下のクラスを含みます
imapsync

このモジュールは以下のパッケージを必要とします。
subprocess
configparser
pathlib
sys
mysql.connector
getEtc
"""

import subprocess
import configparser
import pathlib
import sys
import mysql.connector
import getEtc


##########################################################################
class ImapSync:
    ##########################################################################
    """このクラはは、外部の POP サーバーと rlocal のimap サーバーに対し、同期を行なう為に存在します。
	このクラスは Linux / NUIX で動作します。"""
    ##########################################################################
    etcDir = getEtc.getEtc('imapsync_python').getTargetPath()
    configFile = etcDir.joinpath('imapsync_python.conf')
    localhost = 'localhost'
    ##########################################################################
    getUserListSQL = '''
		select * from users
	'''.strip()

    ##########################################################################
    def __init__(self, config_file=None):
        """このクラはは、マスターの imap サーバーから local のimap サーバーに対し、同期を行なう為に存在します。"""
        if config_file is None:
            config_file = ImapSync.configFile
        elif type(config_file) is not str:
            raise TypeError('設定ファイル({config_file})が文字列ではありません。'.format(config_file=config_file))
        ##########################################################################
        self.default = {}
        self.config = {}
        self.userList = []
        ##########################################################################
        if not pathlib.Path(config_file).exists():
            config_file = ImapSync.configFile
            if not pathlib.Path(config_file).exists():
                raise FileNotFoundError('設定ファイル({config_file})が存在しません。'.format(config_file=config_file))
        if not pathlib.Path(config_file).is_file():
            config_file = ImapSync.configFile
            if not pathlib.Path(config_file).is_file():
                raise FileNotFoundError('設定ファイル({config_file})がファイルではありません。'.format(config_file=config_file))
        if pathlib.Path(config_file).stat().st_size < 1:
            config_file = ImapSync.configFile
            if pathlib.Path(config_file).stat().st_size < 1:
                raise KeyError('設定ファイル({config_file})の中身が空です。'.format(config_file=config_file))
        ##########################################################################
        self.configFile = pathlib.Path(config_file).resolve()
        self.config = configparser.ConfigParser()
        self.config.read(self.configFile)
        self.default = self.config.defaults()
        self.sections = self.config.sections()
        self.database_config = {}
        ##########################################################################
        self.database_config = {}
        for key in self.default.keys():
            self.database_config[key] = self.default[key]
        ##########################################################################
        self.connector = mysql.connector.connect(**self.database_config)
        if not self.connector.is_connected():
            raise KeyError('データベース接続バラメータに問題があります。' + str(self.database_config))
        self.cursor = self.connector.cursor(dictionary=True)
        ##########################################################################
        self.cursor.execute(ImapSync.getUserListSQL)
        self.userList = self.cursor.fetchall()

    ##########################################################################
    ##########################################################################
    def __del__(self):
        if self.connector.is_connected():
            self.connector.close()
        return

    ##########################################################################
    def download(self):
        """マスターの imap サーバーから local のimap サーバーに対し、同期を行ないます。"""
        ##########################################################################
        self.resultsList = []
        for user in self.userList:
            masterHost = '--host1=' + user['domain']
            masterUser = '--user1=' + user['auth_user']
            masterPassword = '--password1=' + user['password']
            localHost = '--host2=' + ImapSync.localhost
            localUser = '--user2=' + user['auth_user']
            localPassword = '--password2=' + user['password']
            user['returncode'] = subprocess.run(
                ['imapsync', '--nolog', masterHost, masterUser, masterPassword, localHost, localUser, localPassword],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
            self.resultsList.append(user)
        ##########################################################################
        return self.resultsList
##########################################################################


__all__ = ['ImapSync']
##########################################################################
if __name__ == "__main__":
    import system_sync

    sys_sync = system_sync.system_sync()
    if not sys_sync.isSlave():
        exit(0)

    ImapSync_python = ImapSync()
    ImapSync_python.download()

    exit(0)
