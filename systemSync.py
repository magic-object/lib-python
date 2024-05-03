#!/usr/bin/env python
'''このプログラムは system_sync を操作します。
'''
import system_sync
import os
import sys
import re
import readline
import magic
import pathlib

##########################################################################
class system_sync_output:
    ##########################################################################
    '''system_sync_output は system_sync の処理を行うクラスです
    このクラスは Linux / NUIX で動作します。'''
    ##########################################################################
    def __init__( self ):
        '''system_sync_output は system_sync の処理を行うクラスです'''
        ##########################################################################
        self.sys_sync = system_sync.system_sync()
        ##########################################################################
    ##########################################################################
    def __del__( self ):
        pass
    ##########################################################################
    def clear( self ):
        print( "\033[2J" )
    ##########################################################################
    def printAll( self, index ):

        if index == 'machineInfo':
            print( '--------------------------------------------------' )
            for key in self.sys_sync.machineInfo.keys():
                print( key + ' : ' + str( self.sys_sync.machineInfo[ key ] ) )
            print( '--------------------------------------------------' )
        elif index == 'osInfo':
            print( '--------------------------------------------------' )
            for key in self.sys_sync.osInfo.keys():
                print( key + ' : ' + str( self.sys_sync.osInfo[ key ] ) )
            print( '--------------------------------------------------' )
        elif index == 'domainInfo':
            print( '--------------------------------------------------' )
            for key in self.sys_sync.domainInfo.keys():
                print( key + ' : ' + str( self.sys_sync.domainInfo[ key ] ) )
            print( '--------------------------------------------------' )
        elif index == 'unitNames':
            print( '--------------------------------------------------' )
            for unit_name in self.sys_sync.getUnitNames():
                print( unit_name )
            print( '--------------------------------------------------' )
    ##########################################################################
    def completer( self, text, state ):
        options = [x for x in self.tmpArray if x.startswith(text)]
        try:
            return options[state]
        except IndexError:
            return None
    ##########################################################################
    def inputList( self, array, prompt=None ):
        self.tmpArray = array
        readline.set_completer( self.completer )
        readline.parse_and_bind( 'tab: complete' )

        retbuf = input( prompt )

        readline.set_completer( None )

        return retbuf
    ##########################################################################
##########################################################################
if __name__ == "__main__" :

    if 0 != os.getuid():
        print( 'root 以外では動作しません。', file=sys.stderr )
        exit( 1 )
     
    sys_sync_out = system_sync_output()

    if not sys_sync_out.sys_sync.isMaster():
        print( 'Master マシン以外では動作しません。', file=sys.stderr )
        exit( 1 )
     
    args = sys.argv
    if 1 < len( args ):
        ##########################################################################
        if not pathlib.Path( args[1] ).exists():
            print( 'ファイルが見つかりません。: ' + args[1], file=sys.stderr )
            exit( 1 )
        elif not pathlib.Path( args[1] ).is_file():
            print( 'ファイルではありません。: ' + args[1], file=sys.stderr )
            exit( 1 )
        elif pathlib.Path( args[1] ).is_symlink():
            print( 'シンボリックファイルは師弟出来ません。: ' + args[1], file=sys.stderr )
            exit( 1 )
        ##########################################################################
        filePath = args[1]
        ##########################################################################
        absPath = pathlib.Path( filePath ).resolve()
        absPathStr = str( absPath )
        fileMagic = magic.detect_from_filename( absPathStr )
        ##########################################################################
        mime_type = fileMagic.mime_type
        mime_encoding = fileMagic.encoding
        mime_value = fileMagic.name
        ##########################################################################
        if not input( '次のファイルをアップロードしますか？ (' + mime_type +') ' + absPathStr + ' : y/n : ' ).lower().startswith( 'y' ):
            print( '中止しました。' )
            exit( 0 )
        ##########################################################################
        unitList = sys_sync_out.sys_sync.getUnitNames()
        unit_name = sys_sync_out.inputList( unitList, 'ユニット名を入力してください : ' )
        if unit_name == '':
            unit_name = None
        elif unit_name not in unitList:
            print( '不正なユニットが指定されました。', file=sys.stderr )
            exit( 1 )
        ##########################################################################
        if not fileMagic.mime_type.lower().startswith('text/'):
            print( 'Binary File' )
            sys_sync_out.sys_sync.uploadBinaryFile( absPathStr, unit_name )
        else:
            sys_sync_out.sys_sync.uploadTextFile( absPathStr, unit_name )
            print( 'Text File' )
        ##########################################################################
        exit( 0 )
        ##########################################################################



    sys_sync_out.clear()

    print( 'このプログラムは system_sync を操作します。' + "\n" )

    comPair = {}
    comPair['1'] = 'machineInfo'
    comPair['2'] = 'osInfo'
    comPair['3'] = 'domainInfo'
    comPair['4'] = 'unitNames'
    comPair['5'] = 'rsync'
    comPair['6'] = 'initializeMachine'
    comPair['7'] = 'restRsyncDateMachine'
    comPair['8'] = 'restPackageInitialized'
    comPair['9'] = 'restDatabaseSlaveSetup'

    prompt = '選択してください ('
    for key in comPair.keys():
        prompt += ' ' + key + ':' + comPair[ key ]
    prompt += ' q:quit ) : '

    command = ''

    while command not in [ 'q', 'quit', 'exit', 'end' ]:
        ##########################################################################
        command = input( prompt ).strip().lower()
        ##########################################################################
        if command == '9': ### restDatabaseSlaveSetup
            ##########################################################################
            allMachineInfo = sys_sync_out.sys_sync.getAllMachineInfo()
            allMachines = []
            for row in allMachineInfo:
                allMachines.append( row['name'] )
            ##########################################################################
            name = sys_sync_out.inputList( allMachines, 'マシン名を入力してください : ' )
            if name not in allMachines:
                print( '不正なマシン名が指定されました。', file=sys.stderr )
                exit( 1 )
            ##########################################################################
            machine = {}
            machine_id = -1
            for machine in allMachineInfo:
                if name == machine['name']:
                    machine_id = machine['machine_id']
                    break
            ##########################################################################
            if sys_sync_out.sys_sync.setupDatabaseSlave( machine_id ):
                print( '成功しました。' )
                exit( 0 )
            else:
                print( 'データベースのセットアップに失敗しました。', file=sys.stderr )
                exit( 1 )
        ##########################################################################
        if command == '8': ### resetRsyncDateMachine
            ##########################################################################
            allMachineInfo = sys_sync_out.sys_sync.getAllMachineInfo()
            allMachines = []
            for row in allMachineInfo:
                allMachines.append( row['name'] )
            ##########################################################################
            name = sys_sync_out.inputList( allMachines, 'マシン名を入力してください : ' )
            if name not in allMachines:
                print( '不正なマシン名が指定されました。', file=sys.stderr )
                exit( 1 )
            ##########################################################################
            machine = {}
            machine_id = -1
            for machine in allMachineInfo:
                if name == machine['name']:
                    machine_id = machine['machine_id']
                    break
            ##########################################################################
            if not sys_sync_out.sys_sync.resetRsyncDateMachine( machine_id ):
                print( '失敗しました。', file=sys.stderr )
                exit( 1 )
            print( '成功しました。' )
            ##########################################################################
            exit( 0 )
        ##########################################################################
        if command == '7': ### resetPackageInitializeMachine
            ##########################################################################
            allMachineInfo = sys_sync_out.sys_sync.getAllMachineInfo()
            allMachines = []
            for row in allMachineInfo:
                allMachines.append( row['name'] )
            ##########################################################################
            name = sys_sync_out.inputList( allMachines, 'マシン名を入力してください : ' )
            if name not in allMachines:
                print( '不正なマシン名が指定されました。', file=sys.stderr )
                exit( 1 )
            ##########################################################################
            machine = {}
            machine_id = -1
            for machine in allMachineInfo:
                if name == machine['name']:
                    machine_id = machine['machine_id']
                    break
            ##########################################################################
            if not sys_sync_out.sys_sync.resetPackageInitializeMachine( machine_id ):
                print( '失敗しました。', file=sys.stderr )
                exit( 1 )
            print( '成功しました。' )
            ##########################################################################
            exit( 0 )
        ##########################################################################
        if command == '6': ### initializeMachine
            ##########################################################################
            allMachineInfo = sys_sync_out.sys_sync.getAllMachineInfo()
            allMachines = []
            for row in allMachineInfo:
                allMachines.append( row['name'] )
            ##########################################################################
            name = sys_sync_out.inputList( allMachines, 'マシン名を入力してください : ' )
            if name not in allMachines:
                print( '不正なマシン名が指定されました。', file=sys.stderr )
                exit( 1 )
            ##########################################################################
            machine = {}
            machine_id = -1
            for machine in allMachineInfo:
                if name == machine['name']:
                    machine_id = machine['machine_id']
                    break
            ##########################################################################
            if not sys_sync_out.sys_sync.initializeMachine( machine_id ):
                print( '失敗しました。', file=sys.stderr )
                exit( 1 )
            print( '成功しました。' )
            ##########################################################################
            exit( 0 )
        ##########################################################################
        elif command == '5': ### rsync
            ##########################################################################
            allMachineInfo = sys_sync_out.sys_sync.getAllMachineInfo()
            allMachines = []
            for row in allMachineInfo:
                allMachines.append( row['name'] )
            ##########################################################################
            name = sys_sync_out.inputList( allMachines, 'マシン名を入力してください : ' )
            if name not in allMachines:
                print( '不正なマシン名が指定されました。', file=sys.stderr )
                exit( 1 )
            ##########################################################################
            machine = {}
            machine_id = -1
            for machine in allMachineInfo:
                if name == machine['name']:
                    machine_id = machine['machine_id']
                    break
            ##########################################################################
            rsyncInitializeList = sys_sync_out.sys_sync.getRsyncInitializeInfo( machine_id )
            print( '--------------------------------------------------' )
            directries = {}
            for rsyncInitialize in rsyncInitializeList:
                if machine_id != rsyncInitialize['machine_id']:
                    continue
                directries[ str( rsyncInitialize['id']  ) ] = rsyncInitialize['directory']
                print( str( rsyncInitialize['id'] ) + ' : ' + rsyncInitialize['directory'] )
            print( '--------------------------------------------------' )
            command = input( '選択して下さい。 : ' ).lower().strip()
            if command not in directries:
                print( '不正な番号が指定されました。', file=sys.stderr )
                exit( 1 )
            directory = directries[ command ]
            ##########################################################################
            if not sys_sync_out.sys_sync.rsync( machine_id, directory ):
                print( '失敗しました。', file=sys.stderr )
                exit( 1 )
            print( '成功しました。' )
            ##########################################################################
            exit( 0 )
        ##########################################################################
        elif command in comPair:
            sys_sync_out.printAll( comPair[ command ] )
        ##########################################################################

    exit( 0 )
##########################################################################
