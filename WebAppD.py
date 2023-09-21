#!/usr/bin/env python
"""
このモジュールは WebApp 用のデーモンです。
"""
import configparser
import signal
import time
import tempfile
import subprocess
from datetime import datetime, timedelta
import os
import re

from multiprocessing import Process

from pgmagick import Image

from WebAppFile import WebAppFile
from WebAppQueue import WebAppQueue

WEB_APP_CONFIG_FILE_PATH = '/usr/local/etc/WebApp/WebApp.conf'


def sigterm(signum, frame):
    Daemon.LOOP = False


class Daemon:
    LOOP = True
    def __init__(self, config):
        self.web_app_file = WebAppFile(config)
        self.web_app_queue = WebAppQueue(config)

        signal.signal(signal.SIGTERM, sigterm)
        signal.signal(signal.SIGINT, sigterm)

    def __del__(self):
        del self.web_app_file
        del self.web_app_queue

    def loop(self):
        while Daemon.LOOP:
            time.sleep(0.1)
            for queue in self.web_app_queue.dequeue():
                if queue['command'].startswith("#wkhtmltoimage"):
                    Process(target=self.html_to_png, args=(queue,), daemon=True).start()

    def html_to_png(self, queue):
        if not queue['command'].startswith("#wkhtmltoimage"):
            return

        # 設定ファイルの読み込み
        config = configparser.ConfigParser()
        config.read(WEB_APP_CONFIG_FILE_PATH)

        alive_minutes = int(config['wkhtmltoimage']['alive_minutes'])

        argument = queue['argument']
        command_argument = {}
        for arg in argument.split(','):
            if '=' not in arg:
                continue
            key = arg.split('=')[0]
            value = arg.split('=')[1]

            command_argument[key] = value

        url = command_argument['url']
        width = command_argument['width']

        if url is None or not re.match('^https?://', url):
            queue['status'] = 'error'
            self.web_app_queue.update(queue)
            return

        ip_addr = queue['ip_addr']

        fd, filename = tempfile.mkstemp(suffix='.png')
        result = subprocess.run(['wkhtmltoimage', '--quiet', '--width', width, url, filename]).returncode
        if result == 0:
            fd, compressed_filename = tempfile.mkstemp(suffix='.png')
            im = Image(filename)
            im.quality(90)
            im.write(compressed_filename)
            os.remove(filename)

            alive_datetime = datetime.now() + timedelta(minutes=alive_minutes)
            file_id = self.web_app_file.upload_file(compressed_filename, alive_datetime, ip_addr, True)
            os.remove(compressed_filename)

            if file_id == -1:
                queue['status'] = 'error'
            else:
                queue['file_id'] = file_id
                queue['status'] = 'success'

            self.web_app_queue.update(queue)
            return
        else:
            os.remove(filename)
            queue['status'] = 'error'
            queue['result_code'] = result
            self.web_app_queue.update(queue)
            return

if __name__ == '__main__':
    daemon = Daemon(WEB_APP_CONFIG_FILE_PATH)
    daemon.loop()

