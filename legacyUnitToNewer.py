#!/usr/bin/env python
'''このモジュールは、ユニット（デーモン）の /var/run/ ディレクトリを使う設定ファイルを /run/ に置き換えます。
このモジュールは、以下のクラスを含みます
legacyUnitToNewer

このモジュールは以下のパッケージを必要とします。
pathlib
magic
re
os
subprocess
'''

import pathlib
import magic
import re
import os
import subprocess
##########################################################################
class legacyUnitToNewer:
	##########################################################################
	'''legacyUnitToNewer は、ユニット（デーモン）の /var/run/ ディレクトリを使う設定ファイルを /run/ に置き換えます。
	このクラスは Linux / NUIX で動作します。'''
	##########################################################################
	semanagePath = '/usr/sbin/semanage'
	semanagePath2 = '/sbin/semanage'
	##########################################################################
	legacyRunDir = '/var/run/'
	newerRunDir = '/run/'
	##########################################################################
	serviceFileDirectory = '/usr/lib/systemd/system/'
	configDirectory = '/etc/'
	configUnitDirectory = configDirectory + '{unit}/'
	serviceSuiffix = '.service'
	daemonReloadCommand = [ "systemctl", "daemon-reload" ]
	##########################################################################
	commentChar = '#'
	commentCharPattern = '[' + commentChar + ']'
	commentLinePattern = '''\s*''' + commentCharPattern
	##########################################################################
	def __init__( self, unit_name ):
		'''このクラスは、ユニット（デーモン）の /var/run/ ディレクトリを使う設定ファイルを /run/ に置き換えます。'''
		##########################################################################
		if type( unit_name ) is not str:
			raise TypeError( 'ユニット名が({unit_name})が文字列ではありません。'.format( unit_name = str( unit_name ) ) )
		elif len( unit_name ) < 1:
			raise TypeError( 'ユニット名が({unit_name})が空文字列です。'.format( unit_name = unit_name ) )
		elif not pathlib.Path( legacyUnitToNewer.newerRunDir ).exists():
			raise FileNotFoundError( '({run_dir})ディレクトリが存在しません。'.format( run_dir = legacyUnitToNewer.newerRunDir ) )
		elif not pathlib.Path( legacyUnitToNewer.newerRunDir ).is_dir():
			raise FileNotFoundError( '({run_dir})ディレクトリが存在しません。'.format( run_dir = legacyUnitToNewer.newerRunDir ) )
		elif pathlib.Path( legacyUnitToNewer.newerRunDir ).is_symlink():
			raise FileNotFoundError( '({run_dir})ディレクトリが存在しません。'.format( run_dir = legacyUnitToNewer.newerRunDir ) )
		elif os.getuid() != 0:
			raise PermissionError( 'root ユーザー以外では実行できません。' )
		##########################################################################
		self.configUnitDirectory = legacyUnitToNewer.configUnitDirectory.format( unit = unit_name )
		self.serviceFile = legacyUnitToNewer.serviceFileDirectory + unit_name + legacyUnitToNewer.serviceSuiffix
		self.useSELinux = pathlib.Path( legacyUnitToNewer.semanagePath ).exists() or pathlib.Path( legacyUnitToNewer.semanagePath2 ).exists()
		##########################################################################
		self.commentLinePattern = re.compile( legacyUnitToNewer.commentLinePattern )
		self.commentCharPattern = re.compile( legacyUnitToNewer.commentCharPattern )
		self.legacyRunDirPattern = re.compile( re.escape( legacyUnitToNewer.legacyRunDir ) )
		##########################################################################
	##########################################################################
	def __del__( self ):
		pass
	##########################################################################
	def do( self ):
		'''ユニット（デーモン）の /var/run/ ディレクトリを使う設定ファイルを /run/ に置き換えます。'''
		##########################################################################
		result = self.doFile( self.serviceFile )
		if result:
			result = subprocess.run( legacyUnitToNewer.daemonReloadCommand ).returncode == 0
		##########################################################################
		result = self.doDir( self.configUnitDirectory ) or result
		##########################################################################
		return result
		##########################################################################
	##########################################################################
	def doFile( self, path ):
		'''ファイルの /var/run/ ディレクトリを /run/ に置き換えます。'''
		##########################################################################
		if not pathlib.Path( path ).exists():
			return False
		##########################################################################
		if not pathlib.Path( path ).is_file():
			return False
		##########################################################################
		fileMagic = magic.detect_from_filename( path )
		if not fileMagic.mime_type.lower().startswith('text/'):
			return False
		##########################################################################
		lines = []
		with pathlib.Path( path ).open() as file:
			lines = file.readlines()
		if len( lines ) < 1:
			return False
		##########################################################################
		changed = False
		##########################################################################
		newLines = []
		for line in lines:
			if self.commentLinePattern.match( line ):
				newLines.append( line )
				continue

			comment = ''
			targetLine = line
			match = self.commentCharPattern.search( line )
			if match is not None:
				comment = line[ match.start() : ]
				targetLine = line[ : match.start() ]

			newLine = self.legacyRunDirPattern.sub( legacyUnitToNewer.newerRunDir, targetLine )
			if newLine == targetLine:
				newLines.append( line )
				continue

			
			changed = True
			newLines.append( legacyUnitToNewer.commentChar[0] + line )
			newLines.append( newLine + comment )
		##########################################################################
		if not changed:
			return False
		##########################################################################
		with pathlib.Path( path ).open( mode = 'wt' ) as file:
			for line in newLines:
				file.write( line )
		##########################################################################
		return True
	##########################################################################
	def doDir( self, path, isRecursive=True ):
		'''ディテクトリ内に存在するテキストファイルの /var/run/ ディレクトリを /run/ に置き換えます。'''
		##########################################################################
		if not pathlib.Path( path ).exists():
			return False
		##########################################################################
		if not pathlib.Path( path ).is_dir():
			return False
		##########################################################################
		result = False
		for child in pathlib.Path( path ).iterdir():
			if isRecursive and child.is_dir():
				result = self.doDir( str( child ) ) or result
			elif not child.is_file():
				continue
			else:
				fileMagic = magic.detect_from_filename( path )
				if not fileMagic.mime_type.lower().startswith('text/'):
					continue
				else:
					result = self.doFile( str( child ) ) or result
		##########################################################################
		return result
	##########################################################################

__all__ = [ 'legacyUnitToNewer' ]

if __name__ == "__main__" :
	import sys

	if len( sys.argv ) < 2:
		print( 'usage: {command} unit'.format( command = sys.argv[0] ), file = sys.stderr ) 
		exit( 1 )

	for unit in sys.argv[1:]:
		unitToNewer = legacyUnitToNewer( unit )
		if unitToNewer.do():
			print( 'unit:	{unit}	changed'.format( unit = unit ) )
		else:
			print( 'unit:	{unit}	not changed'.format( unit = unit ) )

	exit( 0 )
