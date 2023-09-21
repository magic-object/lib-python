#!/usr/bin/env python
'''このモジュールは、外部の POP サーバーと local のimap サーバーに対し、同期を行なう為に存在します。
このモジュールは、以下のクラスを含みます
pop3_lmtp

このモジュールは以下のパッケージを必要とします。
configparser
pathlib
smtplib
poplib
imaplib
email
sys
mysql.connector
getEtc
'''

import configparser
import pathlib
import smtplib
import poplib
import imaplib
import email
import sys
import mysql.connector
import getEtc
##########################################################################
class pop3_lmtp:
	##########################################################################
	'''このクラはは、外部の POP サーバーと rlocal のimap サーバーに対し、同期を行なう為に存在します。
	このクラスは Linux / NUIX で動作します。'''
	##########################################################################
	etcDir = getEtc.getEtc( 'pop3_lmtp' ).getTargetPath()
	configFile = etcDir.joinpath( 'pop3_lmtp.conf' )
	datbase_prefix = 'database_'
	imap_prefix ='imap_'
	##########################################################################
	getMessageCountSQL = '''
		select count(*) as isForwared from forwarded
		where message_id = %(message_id)s
		and forward_address = %(forward_address)s
	'''.strip()
	getMessageIdListSQL = '''
		select * from forwarded
		where forward_address = %(forward_address)s
	'''.strip()
	insertMessageIdSQL = '''
		insert into forwarded ( forward_address, message_id )
		values ( %(forward_address)s, %(message_id)s )
	'''.strip()
	##########################################################################
	def __init__( self, config_file=None ):
		'''このクラはは、外部の POP サーバーと local のimap サーバーに対し、同期を行なう為に存在します。
		メールの転送に対し LMTP を利用します。'''
		if config_file is None:
			config_file = pop3_lmtp.configFile
		elif type( config_file ) is not str:
			raise TypeError( '設定ファイル({config_file})が文字列ではありません。'.format( config_file = config_file ) )
		##########################################################################
		self.default = {}
		self.config = {}
		self.hostList = []
		self.email = {}
		self.MessageIdList = {}
		self.lmtp = None
		self.imapInfo = {}
		##########################################################################
		if not pathlib.Path( config_file ).exists():
			config_file = pop3_lmtp.configFile
			if not pathlib.Path( config_file ).exists():
				raise FileNotFoundError( '設定ファイル({config_file})が存在しません。'.format( config_file = config_file ) )
		if not pathlib.Path( config_file ).is_file():
			config_file=pop3_lmtp.configFile
			if not pathlib.Path( config_file ).is_file():
				raise FileNotFoundError( '設定ファイル({config_file})がファイルではありません。'.format( config_file = config_file ) )
		if pathlib.Path( config_file ).stat().st_size < 1:
			config_file=pop3_lmtp.configFile
			if pathlib.Path( config_file ).stat().st_size < 1:
				raise KeyError( '設定ファイル({config_file})の中身が空です。'.format( config_file = config_file ) )
		##########################################################################
		self.configFile = pathlib.Path( config_file ).resolve()
		self.config = configparser.ConfigParser()
		self.config.read( self.configFile )
		self.default = self.config.defaults()
		self.hostList = self.config.sections()
		for hostName in self.hostList:
			self.config[ hostName ]['protocol'] = self.config[ hostName ]['protocol'].lower()
			self.email[ hostName ] = []
			self.MessageIdList[ hostName ] = []
			self.imapInfo[ hostName ] = {}
		##########################################################################
		self.database_config = {}
		for key in self.default.keys():
			if not key.startswith( pop3_lmtp.datbase_prefix ):
				continue
			newKey = key[ len( pop3_lmtp.datbase_prefix ) : ]
			self.database_config[ newKey ] = self.default[ key ]
		##########################################################################
		self.connector = mysql.connector.connect( **self.database_config )
		if not self.connector.is_connected():
			raise KeyError( 'データベース接続バラメータに問題があります。' + str( self.database_config ) )
		self.cursor = self.connector.cursor( dictionary = True )
		##########################################################################
		self.getAllMessageIdList()
		##########################################################################
		for key in self.config[ hostName ].keys():
			if not key.startswith( pop3_lmtp.imap_prefix ):
				continue
			newKey = key[ len( pop3_lmtp.imap_prefix ) : ]
			if newKey.lower() == 'ssl':
				self.imapInfo[ hostName ][ newKey ] = self.config[ hostName ].getboolean( key )
			else:
				self.imapInfo[ hostName ][ newKey ] = self.config[ hostName ][ key ]
		##########################################################################
	##########################################################################
	def __del__( self ):
		if self.connector.is_connected():
			self.connector.close()
		return
	##########################################################################
	def getMessageIdList( self, host ):
		'''指定された POP サーバーの転送済みメッセージ ID 一覧を取得します。
		この一覧は、設定ファイルに記載されているサーバーのみ有効です。
		'''
		##########################################################################
		if type( host ) is not str:
			raise TypeError( 'ホスト名({host})の型が不正です。'.format( host = str( host ) ) )
		if len( host ) < 1:
			raise TypeError( 'ホスト名({host})が空欄です。'.format( host = host ) )
		if host not in self.MessageIdList.keys():
			raise KeyError( 'ホスト名({host})が不正です。'.format( host = host  ) )
		if host not in self.hostList:
			raise KeyError( 'ホスト名({host})が不正です。'.format( host = host  ) )
		##########################################################################
		forward_address = self.config[ host ][ 'forward' ]
		self.cursor.execute( pop3_lmtp.getMessageIdListSQL, { 'forward_address': forward_address } )
		for row in self.cursor.fetchall() :
			if row[ 'message_id' ] not in self.MessageIdList[ host ]:
				self.MessageIdList[ host ].append( row[ 'message_id' ] )
		return self.MessageIdList[ host ]
	##########################################################################
	def insertMessageIdList( self, host, message_id ):
		'''POP サーバーから受信したメールの「Message-ID」を転送済みの ID として登録します。'''
		##########################################################################
		if type( message_id ) is not str:
			raise TypeError( 'メッセージID({message_id})の型が不正です。'.format( message_id = str( message_id ) ) )
		if len( message_id ) < 1:
			raise TypeError( 'メッセージID({message_id})が空です。'.format( message_id = str( message_id ) ) )
		##########################################################################
		if message_id in self.getMessageIdList( host ):
			return 0
		##########################################################################
		self.cursor.execute( pop3_lmtp.insertMessageIdSQL, { 'forward_address': self.config[ host ][ 'forward' ], 'message_id': message_id } )
		self.connector.commit()
		return ( self.cursor.lastrowid )
	##########################################################################
	def getAllMessageIdList( self ):
		'''設定ファイルに記載されている全ての POP サーバーの転送済みメッセージ ID 一覧を取得します。'''
		##########################################################################
		for host in self.hostList:
			self.getMessageIdList( host )
		##########################################################################
		return self.MessageIdList
	##########################################################################
	def getMail( self, host ):
		'''指定された POP サーバーに存在する全てのメールを取得します。
		取得されるメッセージは email.message.Message オブジェクトのリストとして得られます。
		この一覧は、設定ファイルに記載されているサーバーのみ有効です。
		'''
		##########################################################################
		if type( host ) is not str:
			raise TypeError( 'ホスト名({host})の型が不正です。'.format( host = str( host ) ) )
		if len( host ) < 1:
			raise TypeError( 'ホスト名({host})が空欄です。'.format( host = host ) )
		##########################################################################
		if host not in self.hostList:
			raise KeyError( 'ホスト名({host})が不正です。'.format( host = host  ) )
		##########################################################################
		self.server = None
		##########################################################################
		if self.config[ host ][ 'protocol' ].startswith( 'pop' ):
			if self.config[ host ].getboolean( 'ssl' ):
				self.server = poplib.POP3_SSL( host )
			else:
				self.server = poplib.POP3( host )
			##########################################################################
			self.server.user( self.config[ host ][ 'user' ] )
			self.server.pass_( self.config[ host ][ 'password' ] )
			##########################################################################
			( numMessages, mailBoxSize ) = self.server.stat()
			##########################################################################
			for i in range( numMessages ):
				wich = i + 1
				for messageLines in self.server.retr( wich ):
					messageObject = None
					##########################################################################
					if type( messageLines ) is not list:
						continue;
					if len( messageLines ) < 1:
						continue
					if type( messageLines[0] ) is bytes:
						message = b'\r\n'.join( messageLines )
						messageObject = email.message_from_bytes( message )
					elif type( messageLines[0] ) is str:
						message = '\r\n'.join( messageLines )
						messageObject = email.message_from_string( message )
					else:
						continue
					##########################################################################
					message_id = messageObject.get('Message-ID')
					if message_id is None:
						message_id = messageObject.get('Message-Id')
						if message_id is None:
							continue
						else:
							messageObject.add_header( 'Message-ID', message_id )
					##########################################################################
					if messageObject.get('Message-ID') in self.MessageIdList[ host ]:
						continue
					self.email[ host ].append( messageObject )
			##########################################################################
			self.server.quit()
		##########################################################################
		if self.server is None:
			raise TypeError( 'ホスト名({host})に予期しないプロトコル({protocol})が指定されています。'.format( host = host, protocol = self.config[ host ][ 'protocol' ] ) )
		##########################################################################
		return self.email[ host ]
	##########################################################################
	def hasImapMessageFromMessageId( self, host, message_id ):
		'''IMAP サーバーに対し、指定されたメッセージ ID のメールを保有しているかどうかを問い合わせます。
		返される値は bool 型です。
		この一覧は、設定ファイルに記載されているサーバーのみ有効です。
		'''
		##########################################################################
		if type( host ) is not str:
			raise TypeError( 'ホスト名({host})の型が不正です。'.format( host = str( host ) ) )
		if len( host ) < 1:
			raise TypeError( 'ホスト名({host})が空欄です。'.format( host = host ) )
		##########################################################################
		if host not in self.hostList:
			raise KeyError( 'ホスト名({host})が不正です。'.format( host = host  ) )
		if host not in self.imapInfo:
			raise KeyError( 'ホスト名({host})が IMAP リストに記載されていません。'.format( host = host  ) )
		##########################################################################
		if type( message_id ) is not str:
			raise TypeError( 'メッセージID({message_id})の型が不正です。'.format( message_id = str( message_id ) ) )
		if len( message_id ) < 1:
			raise TypeError( 'メッセージID({message_id})が空です。'.format( message_id = str( message_id ) ) )
		##########################################################################
		if message_id in self.getMessageIdList( host ):
			return True
		##########################################################################
		if self.imapInfo[ host ][ 'ssl' ]:
			self.imap = imaplib.IMAP4_SSL( host = self.imapInfo[ host ][ 'host' ] )
		else:
			self.imap = imaplib.IMAP4( host = self.imapInfo[ host ][ 'host' ] )
		##########################################################################
		( status, replay ) = self.imap.login( user = self.imapInfo[ host ][ 'user' ], password = self.imapInfo[ host ][ 'password' ] )
		##########################################################################
		( status, replay ) = self.imap.select()
		( status, replay ) = self.imap.search( None, '(HEADER Message-ID "{message_id}")'.format( message_id = message_id ) )
		self.imap.close()
		self.imap.logout()
		##########################################################################
		if status.lower() == 'ok' and len( replay[0] ) > 1:
			self.insertMessageIdList( host, message_id )
			return True
		return False
	##########################################################################
	def storeMessage( self, host, message=None ):
		'''指定された POP サーバーに存在する全てのメールを取得し、IMAP サーバーに格納します。
		メッセージが指定されなかった場合は、格納した件数を返します。
		message に email.message.Message オブジェクトが指定された場合、そのメッセージのみを格納します。
		メッセージが指定された場合は、格納した時には True を、格納しなかった場合は False を返します。
		指定できる POP サーバーは、設定ファイルに記載されているサーバーのみ有効です。
		また、既に格納済みのメールに対しては、何も行いません。
		'''
		##########################################################################
		if type( host ) is not str:
			raise TypeError( 'ホスト名({host})の型が不正です。'.format( host = str( host ) ) )
		if len( host ) < 1:
			raise TypeError( 'ホスト名({host})が空欄です。'.format( host = host ) )
		##########################################################################
		if host not in self.hostList:
			raise KeyError( 'ホスト名({host})が不正です。'.format( host = host  ) )
		##########################################################################
		if message is None:
			storeMessageCount = 0
			if len( self.email[ host ] ) < 1:
				self.getMail( host )
			for message in self.email[ host ]:
				if self.storeMessage( host, message ):
					storeMessageCount += 1
			return storeMessageCount
		##########################################################################
		elif type( message ) is not email.message.Message:
			raise KeyError( 'メッセージ({message})の形式が不正です。'.format( message = srt( message ) ) )
		##########################################################################
		try:
			# メッセージを未読状態にする
			message.replace_header( 'Status', 'U' )
		except:
			pass
		##########################################################################
		message_id = message.get('Message-ID')
		if self.hasImapMessageFromMessageId( host, message_id ):
			# 既に格納済みのメッセージなのでスルー。
			return False
		##########################################################################
		self.lmtp = smtplib.LMTP( self.config[ host ][ 'lmtp_host' ] )
		self.lmtp.send_message( message, to_addrs = self.config[ host ][ 'forward' ] )
		self.lmtp.quit()
		##########################################################################
		# メッセージID を格納済みリストに設定
		self.insertMessageIdList( host, message_id )
		##########################################################################
		return True
	##########################################################################
	def storeAllMessages( self, host = None ):
		'''host が指定されなかった場合、設定ファイルにある全ての POP サーバーに存在する全てのメールを取得し、IMAP サーバーに格納します。
		host が指定された場合、対象の POP サーバーに存在する全てのメールを取得し、IMAP サーバーに格納します。
		格納した件数を返します。
		指定できる POP サーバーは、設定ファイルに記載されているサーバーのみ有効です。
		また、既に格納済みのメールに対しては、何も行いません。
		'''
		##########################################################################
		storeMessageCount = 0
		if host is None:
			for host in self.hostList:
				storeMessageCount += self.storeMessage( host )
			return storeMessageCount
		##########################################################################
		elif type( host ) is not str:
			raise TypeError( 'ホスト名({host})の型が不正です。'.format( host = str( host ) ) )
		elif len( host ) < 1:
			raise TypeError( 'ホスト名({host})が空欄です。'.format( host = host ) )
		##########################################################################
		if host not in self.hostList:
			raise KeyError( 'ホスト名({host})が不正です。'.format( host = host  ) )
		##########################################################################
		return self.storeMessage( host )
	##########################################################################
