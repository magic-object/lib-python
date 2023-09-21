#!/usr/bin/env python
"""このモジュールは、対象の etc ディレクトリを取得する為に存在します。
このモジュールは、以下のクラスを含みます
getetc

このモジュールは以下のパッケージを必要とします。
pathlib
re
"""

import pathlib
import re


##########################################################################
class getetc:
    ##########################################################################
    """getEtc は、対象の etc ディレクトリを取得するクラスです。
	このクラスは Linux / NUIX で動作します。"""
    ##########################################################################
    pythonLibPattern = re.compile(r'/lib(\d?)/python(\d\+(\.\d+)?)?/?$')
    binPattern = re.compile(r'/(s)?bin/?$')
    etcPattern = re.compile(r'/etc/?$')

    ##########################################################################
    def __init__(self, config_dir_name='', create_dir=False):
        """このクラスは、象の etc ディレクトリを取得します。"""
        ##########################################################################
        self.parent = pathlib.Path(__file__).resolve().parent
        self.etcPath = self.parent
        ##########################################################################
        while self.etcPath.name != '/':
            self.etcPath = self.etcPath.parent
            if self.etcPath.joinpath('etc').exists():
                self.etcPath = self.etcPath.joinpath('etc')
                break
        ##########################################################################
        if type(config_dir_name) is str and len(config_dir_name) > 0:
            self.targetPath = self.etcPath.joinpath(config_dir_name)
        else:
            self.targetPath = self.etcPath
        ##########################################################################
        if create_dir and not self.targetPath.exists():
            self.targetPath.mkdir(ok=True)

    ##########################################################################
    def __del__(self):
        pass

    ##########################################################################
    def get_target_path(self):
        """対象ディレクトリのパスオブジェクトを取得します。"""
        return self.targetPath


##########################################################################


##########################################################################
__all__ = ['getetc']
