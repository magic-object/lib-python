#!/usr/bin/env python
"""
このクラスは　HTML を PNG に変換するデーモンで利用される JSON ファイルを入出力します。
"""
import pathlib
import json
from datetime import datetime


class HtmlToPngJson:
    def __init__(self, file_path):
        self.path = pathlib.Path(file_path)
        self.url = ''
        self.status = 'unknown'
        self.image_file = ''
        self.date = datetime.now()
        self.width = '1280'

        if self.path.exists():
            with self.path.open(mode='r') as file:
                try:
                    data = json.load(file)
                    self.url = data['url']
                    self.status = data['status']
                    self.image_file = data['image_file']
                    self.date = datetime.fromisoformat(data['date'])
                    self.width = data['width']
                except:
                    self.url = ''
                    self.status = 'error'
                    self.image_file = ''
                    self.date = datetime.now()
                    self.width = '1280'

    def save(self):
        with self.path.open(mode='w') as file:
            data_str = json.dumps(
                    {'url': self.url, 'status': self.status, 'image_file': self.image_file, 'date': str(self.date), 'width': self.width})
            file.write(data_str)

    def set(self, url, status, image_file, date, width):
        self.url = url
        self.status = status
        self.image_file = image_file
        self.date = date
        self.width = width

    def get(self):
        with self.path.open(mode='r') as file:
            return file.read()

__all__ = ['HtmlToPngJson']
