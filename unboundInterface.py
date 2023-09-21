#!/usr/bin/env python
'''このモジュールは、unbound のインターフェース設定ファイルを作成する為に存在します。
このモジュールは、以下のクラスを含みます
unboundInterface

このモジュールは以下のパッケージを必要とします。
netifaces
pathlib
re
'''

import netifaces
import pathlib
import re
##########################################################################
class unboundInterface:
	##########################################################################
	'''unboundInterface は、unbound のインターフェース設定ファイルを作成するクラスです。
	このクラスは Linux / NUIX で動作します。'''
	##########################################################################
	unboundInterfaceFile = '/etc/unbound/local.d/interface.conf'
	unboundInterfaceTemplate = '\tinterface:\t%(address)s'
	##########################################################################
	def __init__( self, interfaceFilePath='/etc/unbound/local.d/interface.conf', interfacePattern='^en', interfaceFlag=0 ):
		'''このクラスは、ネットワークハードウェアのインターフェースから unbound のインターフェース設定ファイルを作成します。'''
		##########################################################################
		self.interfaceFilePath = interfaceFilePath
		self.setInterfacePattern( interfacePattern, interfaceFlag )
	##########################################################################
	def __del__( self ):
		pass
	##########################################################################
	def setInterfacePattern( self, interfacePattern='^en', interfaceFlag=0 ):
		'''ハードウェア・ネットワークインターフェースの正規表現パターンを設定します。'''
		##########################################################################
		self.interfacePattern = interfacePattern
		self.interfaceFlag = interfaceFlag
		self.interfaceRegexp = re.compile( self.interfacePattern, self.interfaceFlag )
	##########################################################################
	def getNetHardInterfaces( self ):
		'''全てのハードウェア・ネットワークインターフェースを取得します。'''
		##########################################################################
		netHardInterfaces = []
		for interface in netifaces.interfaces():
			if self.interfaceRegexp.search( interface ):
				netHardInterfaces.append( interface )
			else:
				continue
		return netHardInterfaces
	##########################################################################
	def getNetHardInterfaceIPv4Addresses( self ):
		'''全てのハードウェア・ネットワークインターフェースの IPv4 アドレスを取得します。'''
		##########################################################################
		netHardInterfaceAddresses = []
		for interface in self.getNetHardInterfaces():
			netHardInterfaceAddresses.append( netifaces.ifaddresses( interface )[netifaces.AF_INET][0]['addr'] )
		return netHardInterfaceAddresses
	##########################################################################
	def getNetHardInterfaceIPv6Addresses( self ):
		'''全てのハードウェア・ネットワークインターフェースの IPv6 アドレスを取得します。'''
		##########################################################################
		netHardInterfaceAddresses = []
		for interface in self.getNetHardInterfaces():
			netHardInterfaceAddresses.append( netifaces.ifaddresses( interface )[netifaces.AF_INET6][0]['addr'] )
		return netHardInterfaceAddresses
	##########################################################################
	def writeUnboundInterfaceFile( self, includingIPv6=False ):
		'''unbound のインターフェースファイルを作成します。'''
		##########################################################################
		interfaceFile = pathlib.Path( self.interfaceFilePath )
		addressList = [ '127.0.0.1', '::1' ]
		for address in self.getNetHardInterfaceIPv4Addresses():
			addressList.append( address )
		if includingIPv6:
			for address in self.getNetHardInterfaceIPv6Addresses():
				addressList.append( address )
		with interfaceFile.open( mode = 'w' ) as interfaceFile:
			for address in addressList:
				line = unboundInterface.unboundInterfaceTemplate % { 'address' : address }
				print( line, file = interfaceFile )
##########################################################################
__all__ = [ 'unboundInterface' ]
