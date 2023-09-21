#!/usr/bin/env python
if __name__ == "__main__" :
	import system_sync

	sys_sync = system_sync.system_sync()

	if sys_sync.isSlave() :
		exit( 0 )

	import requests
	
	res = requests.get( 'http://www.mydns.jp/login.html', auth=( 'mydns882809', 'iER7fp4EAPX' ) )
	if res.status_code >= 200 and res.status_code < 300 :
		exit( 0 )

	exit( res.status_code )
