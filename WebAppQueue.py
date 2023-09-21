#!/usr/bin/env python
"""
このモジュールは WebApp で使用するキューを操作するものです。
"""
import configparser
import mysql.connector


class WebAppQueue:
    """
    このクラスは WebApp で使用するキューを操作するものです。
    """

    def __init__(self, config_file, section='DEFAULT'):
        """
        初期化を行います。
        :param config_file: 設定ファイルのパス
        :param section: 設定ファイルの参照するセクション
        """
        # データベースの接続設定ファイルを読み込む。
        with open(config_file, 'r') as file:
            self.database_config = configparser.ConfigParser()
            self.database_config.read_file(file)

        # データベースの接続設定を作成する。
        self.connect_setting = {}
        for key in self.database_config[section]:
            self.connect_setting[key] = self.database_config[section][key]

    def __del__(self):
        """
        終了処理を行います。
        :return: なし
        """
        pass

    def connect(self):
        """
        データベースに接続する。
        :return: connector, cursor
        """
        connector = mysql.connector.connect(**self.connect_setting)
        cursor = connector.cursor(dictionary=True)
        return connector, cursor

    def enqueue(self, command, argument, ip_addr):
        """
        エンキューします。
        :param command: 要求するコマンド
        :param argument: コマンド引数
        :param ip_addr: IPアドレス
        :return: 成功 id、失敗 -1
        """
        connector, cursor = self.connect()

        # 古くなったデータを削除
        cursor.execute('''delete from queue WHERE queue.date < SUBTIME( now(), maketime( 6, 0, 0 ) )''')
        cursor.execute(
            '''delete from queue WHERE is_done = TRUE and queue.date < SUBTIME( now(), maketime( 1, 0, 0 ) )''')
        connector.commit()

        cursor.execute(
            '''insert into queue(type, command, argument, ip_addr, status) values('request',%(command)s, %(argument)s, %(ip_addr)s, 'enqueue')''',
            {'command': command, 'argument': argument, 'ip_addr': ip_addr})
        connector.commit()
        insert_id = cursor.lastrowid

        return insert_id

    def dequeue(self):
        """
        デキューします。
        :return: queue のレコード
        """
        connector, cursor = self.connect()

        records = []
        cursor.execute('''select * from queue where status = 'enqueue' and is_done = FALSE order by date''')

        for row in cursor.fetchall():
            records.append(row)

        for row in records:
            row['status'] = 'dequeue'
            cursor.execute('''update queue set status = 'dequeue' where id = %(id)s''',
                                {'id': row['id']})
            connector.commit()

        return records

    def get(self, queue_id):
        """
        キューレコードを取得します。
        :param queue_id: キューID
        :return: レコード
        """
        connector, cursor = self.connect()

        cursor.execute('''select * from queue where id = %(id)s''', {'id': queue_id})

        result = cursor.fetchone()

        return result

    def update(self, record):
        """
        キューを更新します。
        :param record: queue レコード
        :return: 更新件数
        """
        connector, cursor = self.connect()

        cursor.execute(
            '''update queue
                set type = %(type)s,
                 command = %(command)s,
                 argument = %(argument)s,
                 result_code = %(result_code)s,
                 file_id = %(file_id)s,
                 status = %(status)s,
                 is_done = %(is_done)s
                where id = %(id)s'''.strip(),
            {
                'type': record['type'],
                'command': record['command'],
                'argument': record['argument'],
                'result_code': record['result_code'],
                'file_id': record['file_id'],
                'status': record['status'],
                'is_done': record['is_done'],
                'id': record['id']
            })
        connector.commit()

        rowcount = cursor.rowcount

        return rowcount
