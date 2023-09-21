#!/usr/bin/env python
"""
このモジュールは WebApp で使用するファイルを操作するものです。
"""
import configparser
import mysql.connector
import magic
import pathlib


class WebAppFile:
    """
    このクラスは WebApp で使用するファイルを操作するものです。
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

        # データベースに接続する。
        connector, cursor = self.connect()

        # ファイル設定情報を取得する。
        self.file_config = {}
        cursor.execute( """select * from config where name like 'file_%'""")
        for row in cursor.fetchall():
            self.file_config[row['name']] = row['value']

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

    def get_used_storage_size(self):
        """
        格納合計サイズを習得します。
        :return: サイズ
        """
        connector, cursor = self.connect()

        cursor.execute("""select sum(size) as sum_size from file""")
        record = cursor.fetchone()
        sum_size = 0 if record['sum_size'] is None else record['sum_size']

        return sum_size

    def get_file(self, file_id):
        """
        格納されているファイルデータを取得します。
        :param file_id: file の ID
        :return: file レコード
        """
        connector, cursor = self.connect()

        cursor.execute("""select * from file where id = %(id)s""", {"id": file_id})
        record = cursor.fetchone()

        return record

    def upload_file(self, file_path, alive_limit_date, ip_addr, skip_size_check=False) -> object:
        """
        ファイルをアップロードします。
        :param file_path: ファイルのパス
        :param alive_limit_date: ファイルの生存期日
        :return: 成功 id、失敗 -1
        """
        connector, cursor = self.connect()

        # 古いファイルの削除
        queue_id_list = []
        cursor.execute("""select queue.id as queue_id from file, queue where file.id = queue.file_id and file.alive_limit_date < now()""")
        for queue_id in cursor.fetchall():
            queue_id_list.append(queue_id)

        for queue_id in queue_id_list:
            cursor.execute("""delete from queue where id = %(id)s""", { 'id': queue_id['queue_id']})
            connector.commit()

        cursor.execute("""delete from file where alive_limit_date < now()""")
        connector.commit()

        # 現在の格納サイズを取得する
        sum_size = self.get_used_storage_size()

        # 限界一杯まで格納されていたら、登録を拒否
        if not skip_size_check and sum_size >= int(self.file_config['file_sum_limit']):
            return -1

        try:
            abs_path = pathlib.Path(file_path).resolve()

            # ファイル上限サイズを越えていたら拒否
            size = abs_path.stat().st_size
            if not skip_size_check and size > int(self.file_config['file_size_limit']):
                return -1

            # データの読み込み
            data = abs_path.read_bytes()

            # mime 情報の読み込み
            abs_path_str = str(abs_path)
            file_magic = magic.detect_from_filename(abs_path_str)

            mime_type = file_magic.mime_type
            mime_encoding = file_magic.encoding
            mime_value = file_magic.name

            cursor.execute(
                """
                insert into file (
                    mime_encoding,
                    mime_type,
                    mime_value,
                    ip_addr,
                    data,
                    size,
                    alive_limit_date
                    )
                    values (
                        %(mime_encoding)s,
                        %(mime_type)s,
                        %(mime_value)s,
                        %(ip_addr)s,
                        %(data)s,
                        %(size)s,
                        %(alive_limit_date)s
                        )
                """.strip(),
                {
                    'mime_encoding': mime_encoding,
                    'mime_type': mime_type,
                    'mime_value': mime_value,
                    'ip_addr': ip_addr,
                    'data': data,
                    'size': size,
                    'alive_limit_date': alive_limit_date
                })
            connector.commit()
            lastrowid = cursor.lastrowid

            return lastrowid
        except mysql.connector.Error as err:
            print("Something went wrong: {}".format(err))
            return -1
        except :
            return -1
