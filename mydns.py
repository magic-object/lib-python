#!/usr/bin/env python
if __name__ == "__main__" :
	import system_sync
	import configparser

	MYDNS_CONF = '/usr/local/etc/mydns/mydns.conf'

	# 設定ファイルの読み込み
	config = configparser.ConfigParser()
	config.read(MYDNS_CONF)

	user = config['DEFAULT']['user']
	password = config['DEFAULT']['password']

	sys_sync = system_sync.system_sync()

	if sys_sync.isSlave() :
		exit( 0 )

	import requests
	
	res = requests.get( 'http://www.mydns.jp/login.html', auth=( user, password ) )
	if res.status_code >= 200 and res.status_code < 300 :
		exit( 0 )

	exit( res.status_code )
