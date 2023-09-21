#!/usr/bin/env python

import configparser
import os
import pwd
import glob
from datetime import datetime, timedelta
import shutil
from pathlib import Path
import subprocess
import getetc
import HtmlToPngJson

# ガター内の緑色のボタンを押すとスクリプトを実行します。
if __name__ == '__main__':

    daemon = 'htmlToPngD'
    json_filename = 'data.json'
    image_file_name = 'data.png'

    # 設定ファイルディレクトリの取得
    etc = getetc.getetc()

    # 設定ファイルの読み込み
    config = configparser.ConfigParser()
    config.read(etc.get_target_path().joinpath(daemon, daemon + '.conf'))

    # ユーザーの変更
    new_id = pwd.getpwnam(config['DEFAULT']['user'])
    os.setuid(new_id.pw_uid)

    dir_path = Path(config['DEFAULT']['dir'])

    # 対象ディレクトリが無ければ作成
    if not dir_path.exists():
        if dir_path.name == daemon:
            dir_path.mkdir()
        else:
            dir_path = dir_path.joinpath(daemon)
            dir_path.mkdir()

    dirs = glob.glob(
        str(dir_path) + '/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*')

    alive_seconds = int(config['DEFAULT']['alive_seconds'])

    for dir_name in sorted(dirs):
        path = Path(dir_name)
        #dir_date = datetime.fromisoformat(path.name)
        dir_date = datetime.fromtimestamp(path.stat().st_mtime)
        now_date = datetime.now()

        # 時間が過ぎたディレクトリを削除
        if (dir_date + timedelta(seconds=alive_seconds)) < now_date:
            shutil.rmtree(path)
            continue

        # JSON ファイル
        target_dir = Path(dir_name)
        file_json = target_dir.joinpath(json_filename)
        json_data = HtmlToPngJson.HtmlToPngJson(file_json)

        if json_data.status != 'wait':
            continue

        json_data.date = now_date
        json_data.status = 'processing'
        json_data.save()

        result = subprocess.run(['wkhtmltoimage', '--quiet', '--width', json_data.width, json_data.url, str(target_dir.joinpath(image_file_name))]).returncode
        if result == 0:
            json_data.status = 'success'
            json_data.save()
        else:
            json_data.status = 'error'
            json_data.save()

    exit(0)
