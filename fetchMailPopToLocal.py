#!/usr/bin/env python
if __name__ == "__main__" :
	import pathlib

	pitFileName = pathlib.Path( __file__ ).stem + '.pid'
	pidFilePath = pathlib.Path( '/run/' ).joinpath( pitFileName )
	if pidFilePath.exists():
		exit( 0 )

	import system_sync

	sys_sync = system_sync.system_sync()

	if sys_sync.isSlave() :
		exit( 0 )

	import os
	import pop3_lmtp

	try:
		with pidFilePath.open( mode = 'wt' ) as file:
			print( os.getpid(), file = file )

		pop_lmtp = pop3_lmtp.pop3_lmtp()
		pop_lmtp.storeAllMessages()
	except:
		pidFilePath.unlink( missing_ok = True )
		exit( 1 )

	pidFilePath.unlink( missing_ok = True )

	exit( 0 )

