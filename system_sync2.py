#!/usr/bin/env python
'''このモジュールは、システムの同期を行なう為に存在します。
このモジュールは、以下のクラスを含みます
system_sync

このモジュールは以下のパッケージを必要とします。
configparser
socket
mysql.connector
platform
subprocess
pexpect
magic
pathlib
zlib
pwd
grp
io
os
sys
re
netifaces
tempfile
datetime
errno
'''

import configparser
import socket
import mysql.connector
import platform
import subprocess
import pexpect
import magic
import pathlib
import zlib
import pwd
import grp
import io
import os
import sys
import re
import netifaces
import tempfile
import datetime
import errno
import getEtc
##########################################################################
class system_sync:
    ##########################################################################
    '''system_sync はシステムの同期を行なうクラスです
    このクラスは Linux / NUIX で動作します。'''
    ##########################################################################
    databaseDumpPath = '/root/forSlave.sql'
    databaseServerConfigPath = '/etc/my.cnf.d/mariadb-server.cnf'
    ##########################################################################
    expectTimeout = 180
    ##########################################################################
    passwordRegexpStr = '''((パスワード)|([Pp]assword))\s*:\s*'''
    sshKeyRegExpStr = '''[Yy]es/[Nn]o[^\?]+\?'''
    ##########################################################################
    isMasterSQL = "select count(*) as isMaster from machine where type = 'master' and name = %(host)s"
    isSlaveSQL  = "select count(*) as isSlave from machine where type = 'slave' and name = %(host)s"
    ##########################################################################
    machineInfoSQL  = 'select *, id as machine_id, name as host from machine where name = %(host)s'
    osInfoSQL   = 'select *, id as os_id from os where id = %(os_id)s'
    domainInfoSQL   = 'select *, id as domain_id from domain where id = %(domain_id)s'
    initializeInfoSQL   = 'select *, id as initialize_id from initialize where machine_id = %(machine_id)s'
    ##########################################################################
    machineInfoListSQL = 'select *, id as machine_id, name as host from machine order by type, id'
    ##########################################################################
    initializeListSQL = '''
        select
            machine.*,
            machine.id as machine_id,
            machine.name as host,
            if( initialize.package_installed is null, false, initialize.package_installed ) as package_installed,
            if( initialize.rsync_done is null, false, initialize.rsync_done ) as rsync_done,
            if( initialize.script_done is null, false, initialize.script_done ) as script_done,
            if( initialize.security_done is null, false, initialize.security_done ) as security_done,
            if( initialize.system_config_done is null, false, initialize.system_config_done ) as system_config_done
        from machine left outer join initialize
            on machine.id = initialize.id
        '''.strip()
    insertInitializeSQL = '''
        insert into initialize (
            machine_id,
            package_installed,
            rsync_done,
            script_done,
            security_done,
            database_done,
            command_done,
            system_config_done
            )
            values (
            %(machine_id)s,
            %(package_installed)s,
            %(rsync_done)s,
            %(script_done)s,
            %(security_done)s,
            %(database_done)s,
            %(command_done)s,
            %(system_config_done)s
            )
            on duplicate key update
                machine_id      = %(machine_id)s,
                package_installed   = %(package_installed)s,
                rsync_done      = %(rsync_done)s,
                script_done     = %(script_done)s,
                security_done       = %(security_done)s,
                database_done       = %(database_done)s,
                command_done        = %(command_done)s,
                system_config_done  = %(system_config_done)s
        '''.strip()
    ##########################################################################
    packageInfoSQL = 'select *, id as package_id, name as package, unit_name as unit from package where os_id = %(os_id)s order by priority, unit_name, id'
    packageInitializeListSQL = '''
        select
            package.*,
            package.unit_name as unit,
            package.id as package_id,
            package.name as package,
            machine.*,
            machine.name as host,
            machine.id as machine_id,
            if( package_initialize.initialized is null, false, package_initialize.initialized ) as initialized
        from package
        inner join machine
            on ( package.os_id = machine.os_id and machine.id = %(machine_id)s )
        left outer join package_initialize
            on ( package.id = package_initialize.package_id and package_initialize.machine_id = %(machine_id)s )
        order by package.priority, package.unit_name, package.id
        '''.strip()
    insertPackageInitializeSQL = '''
        insert into package_initialize (
                package_id,
                machine_id,
                initialized
            )
            values (
                %(package_id)s,
                %(machine_id)s,
                %(initialized)s
            )
            on duplicate key update
                package_id  = %(package_id)s,
                machine_id  = %(machine_id)s,
                initialized = %(initialized)s
        '''.strip()
    resetPackageInitializeSQL = '''
        update package_initialize
            set initialized = false
            where machine_id  = %(machine_id)s
        '''.strip()
    ##########################################################################
    scpCommandSQL = '''
        select * from command where type = 'scp' and on_time = 'anytime' and os_id = %(os_id)s
        '''.strip()
    ##########################################################################
    sshCommandSQL = '''
        select * from command where type = 'ssh' and on_time = 'anytime' and os_id = %(os_id)s
        '''.strip()
    ##########################################################################
    rsyncCommandSQL = '''
        select * from command where type = 'sync' and on_time = 'anytime' and os_id = %(os_id)s
        '''.strip()
    ##########################################################################
    securityInstallCommandSQL = '''
        select * from command where type = 'security-install' and on_time = 'anytime' and os_id = %(os_id)s
        '''.strip()
    ##########################################################################
    rsyncInitializeSQL = '''
        select distinct
            machine.*,
            machine.name as host,
            machine.id as machine_id,
            rsync.*,
            rsync.id as rsync_id,
            rsync.unit as unit_name,
            if( rsync_date.is_done is null, false, rsync_date.is_done ) as is_done,
            if( rsync_date.update_term_seconds is null, rsync.update_term_seconds, rsync_date.update_term_seconds ) as update_term_seconds
            from machine
            inner join rsync
                on ( machine.os_id = rsync.os_id and machine.id = %(machine_id)s )
            left outer join rsync_date
                on ( rsync.id = rsync_date.rsync_id )
            order by machine.id, rsync.priority, rsync.unit, rsync.id
        '''.strip()
    resetRsyncDateSQL = '''
        update rsync_date set is_done = false where ( rsync_date + update_term_seconds ) <= ( now() + 0 );
        '''.strip()
    resetInitializeSQL ='''
        update initialize, machine set initialize.rsync_done = true where initialize.machine_id = machine.id and machine.type = 'master'
        '''.strip()
    resetRsyncDateMachineSQL = '''
        update rsync_date set is_done = false where machine_id = %(machine_id)s;
        '''.strip()
    insertRsyncDateSQL = '''
        insert into rsync_date (
                rsync_id,
                machine_id,
                unit_name,
                update_term_seconds,
                is_done
            )
            values (
                %(rsync_id)s,
                %(machine_id)s,
                %(unit_name)s,
                %(update_term_seconds)s,
                %(is_done)s
            )
            on duplicate key update
                rsync_id        = %(rsync_id)s,
                machine_id      = %(machine_id)s,
                unit_name       = %(unit_name)s,
                update_term_seconds = %(update_term_seconds)s,
                is_done         = %(is_done)s
        '''.strip()
    ##########################################################################
    rsyncListSQL = '''
        select *, id as rsync_id from rsync where os_id = %(os_id)s and directory = %(directory)s
        '''.strip()
    ##########################################################################
    commandInitializeSQL = '''
        select
            command.*,
            command.id as command_id,
            command.unit as unit_name,
            machine.*,
            machine.name as host,
            machine.id as machine_id,
            if( initialize.command_done is null, false, initialize.command_done ) as command_done
            from command
            inner join machine
                on ( machine.os_id = command.os_id and command.type = 'initialize' and command.on_time in ( 'anytime', 'initialize' ) and unit is null and machine.id = %(machine_id)s )
            left outer join initialize
                on ( initialize.machine_id = machine.id and machine.id = %(machine_id)s )
            order by command.priority, command.id
        '''.strip()
    ##########################################################################
    commandUnitPreInitializeSQL = '''
        select
            command.*,
            command.id as command_id,
            command.unit as unit_name,
            machine.*,
            machine.name as host,
            machine.id as machine_id,
            if( initialize.command_done is null, false, initialize.command_done ) as command_done
            from command
            inner join machine
                on ( machine.os_id = command.os_id and command.type in ( 'initialize',  'security' ) and command.on_time in ( 'anytime', 'pre_install' ) and machine.id = %(machine_id)s and command.unit = %(unit_name)s )
            left outer join initialize
                on ( initialize.machine_id = machine.id and machine.id = %(machine_id)s )
            order by command.priority, command.unit, command.id
        '''.strip()
    ##########################################################################
    commandUnitInitializeSQL = '''
        select
            command.*,
            command.id as command_id,
            command.unit as unit_name,
            machine.*,
            machine.id as machine_id,
            machine.name as host,
            if( initialize.command_done is null, false, initialize.command_done ) as command_done
            from command
            inner join machine
                on ( machine.os_id = command.os_id and command.type in ( 'initialize',  'security' ) and command.on_time in ( 'anytime', 'after_install', 'pre_start' ) and machine.id = %(machine_id)s and command.unit = %(unit_name)s )
            left outer join initialize
                on ( initialize.machine_id = machine.id and machine.id = %(machine_id)s )
            order by command.priority, command.unit, command.on_time, command.id
        '''.strip()
    ##########################################################################
    commandUnitAfterStartSQL = '''
        select
            command.*,
            command.id as command_id,
            command.unit as unit_name,
            machine.*,
            machine.id as machine_id,
            machine.name as host,
            if( initialize.command_done is null, false, initialize.command_done ) as command_done
            from command
            inner join machine
                on ( machine.os_id = command.os_id and command.type in ( 'initialize',  'security', 'other' ) and command.on_time in ( 'after_start', 'finalize' ) and machine.id = %(machine_id)s and command.unit = %(unit_name)s )
            left outer join initialize
                on ( initialize.machine_id = machine.id and machine.id = %(machine_id)s )
            order by command.priority, command.unit, command.on_time, command.id
        '''.strip()
    ##########################################################################
    packageInstallCommandSQL = '''
        select
            command.*,
            command.id as command_id,
            command.unit as unit_name,
            machine.*,
            machine.name as host,
            machine.id as machine_id
            from command
            inner join machine
                on ( machine.os_id = command.os_id and command.type = 'package_install' and machine.id = %(machine_id)s )
            order by command.priority, command.unit, command.id
        '''.strip()
    packageCheckSQL = '''
        select
            package.*,
            package.name as package,
            package.unit_name as unit,
            package.id as package_id,
            machine.*,
            machine.name as host,
            machine.id as machine_id
            from package
            inner join machine
                on ( machine.os_id = package.os_id and package.name = %(package)s and machine.id = %(machine_id)s )
        '''.strip()
    unitEnableCommandSQL = '''
        select
            command.*,
            command.id as command_id,
            command.unit as unit_name,
            machine.*,
            machine.name as host,
            machine.id as machine_id
            from command
            inner join machine
                on ( machine.os_id = command.os_id and command.type = 'package_enable' and command.unit is null and machine.id = %(machine_id)s )
            order by command.priority, command.id
        '''.strip()
    unitDisableCommandSQL = '''
        select
            command.*,
            command.id as command_id,
            command.unit as unit_name,
            machine.*,
            machine.name as host,
            machine.id as machine_id
            from command
            inner join machine
                on ( machine.os_id = command.os_id and command.type = 'package_disable' and command.unit is null and machine.id = %(machine_id)s )
            order by command.priority, command.id
        '''.strip()
    unitStartCommandSQL = '''
        select
            command.*,
            command.id as command_id,
            command.unit as unit_name,
            machine.*,
            machine.name as host,
            machine.id as machine_id
            from command
            inner join machine
                on ( machine.os_id = command.os_id and command.type = 'package_restart' and command.unit is null and machine.id = %(machine_id)s )
            order by command.priority, command.id
        '''.strip()
    unitStopCommandSQL = '''
        select
            command.*,
            command.id as command_id,
            command.unit as unit_name,
            machine.*,
            machine.name as host,
            machine.id as machine_id
            from command
            inner join machine
                on ( machine.os_id = command.os_id and command.type = 'package_stop' and command.unit is null and machine.id = %(machine_id)s )
            order by command.priority, command.id
        '''.strip()
    unitRestartCommandSQL = '''
        select
            command.*,
            command.id as command_id,
            command.unit as unit_name,
            machine.*,
            machine.name as host,
            machine.id as machine_id
            from command
            inner join machine
                on ( machine.os_id = command.os_id and command.type = 'package_restart' and command.unit is null and machine.id = %(machine_id)s )
            order by command.priority, command.id
        '''.strip()
    unitReloadCommandSQL = '''
        select
            command.*,
            command.id as command_id,
            command.unit as unit_name,
            machine.*,
            machine.name as host,
            machine.id as machine_id
            from command
            inner join machine
                on ( machine.os_id = command.os_id and command.type = 'package_reload' and command.unit is null and machine.id = %(machine_id)s )
            order by command.priority, command.id
        '''.strip()
    ##########################################################################
    slaveSetupDatabaseSQL = '''
        select
            command.*,
            command.id as command_id,
            command.unit as unit_name,
            machine.*,
            machine.name as host,
            machine.id as machine_id
            from command
            inner join machine
                on ( machine.os_id = command.os_id and command.type = 'sql' and on_time = 'after_start' and command.unit is not null and command.unit = %(unit_name)s and machine.id = %(machine_id)s )
            order by command.priority, command.id
        '''.strip()
    ##########################################################################
    getSystemConfigTextSQL = '''
        select
            text_file.*,
            text_file.id as text_file_id,
            machine.*,
            machine.name as host,
            machine.id as machine_id
            from text_file
            inner join machine
                on ( machine.os_id = text_file.os_id and text_file.type = 'config' and text_file.unit is null and machine.id = %(machine_id)s )
        '''.strip()
    ##########################################################################
    getUnitTextSQL = '''
        select
            text_file.*,
            text_file.id as text_file_id,
            machine.*,
            machine.name as host,
            machine.id as machine_id
            from text_file
            inner join machine
                on ( machine.os_id = text_file.os_id and text_file.type = 'config' and text_file.unit = %(unit_name)s and machine.id = %(machine_id)s )
        '''.strip()
    ##########################################################################
    getSetupDatabaseTextSQL = '''
        select
            text_file.*,
            text_file.id as text_file_id,
            machine.*,
            machine.name as host,
            machine.id as machine_id
            from text_file
            inner join machine
                on ( machine.os_id = text_file.os_id and text_file.type = 'sql' and text_file.is_initialize_database is true and text_file.unit = %(unit_name)s and machine.id = %(machine_id)s )
        '''.strip()
    ##########################################################################
    getSystemConfigBinarySQL = '''
        select
            binary_file.*,
            binary_file.id as binary_file_id,
            machine.*,
            machine.name as host,
            machine.id as machine_id
            from binary_file
            inner join machine
                on ( machine.os_id = binary_file.os_id and binary_file.type = 'config' and binary_file.unit is null and machine.id = %(machine_id)s )
        '''.strip()
    ##########################################################################
    getUnitBinarySQL = '''
        select
            binary_file.*,
            binary_file.id as binary_file_id,
            machine.*,
            machine.name as host,
            machine.id as machine_id
            from binary_file
            inner join machine
                on ( machine.os_id = binary_file.os_id and ( binary_file.type = 'config' or binary_file.type = 'security' ) and binary_file.unit = %(unit_name)s and machine.id = %(machine_id)s )
        '''.strip()
    ##########################################################################
    insertTextFileSQL   = '''
        insert into text_file (
            os_id,
            at_least_versions,
            type,
            unit,
            path,
            data,
            mime_type,
            mime_encoding,
            mime_value,
            file_owner,
            file_group,
            file_mode,
            is_complessed,
            is_database_config,
            last_modify
            )
            values (
            %(os_id)s,
            %(at_least_versions)s,
            %(type)s,
            %(unit)s,
            %(path)s,
            %(data)s,
            %(mime_type)s,
            %(mime_encoding)s,
            %(mime_value)s,
            %(file_owner)s,
            %(file_group)s,
            %(file_mode)s,
            %(is_complessed)s,
            %(is_database_config)s,
            %(last_modify)s
            )
            on duplicate key update
                at_least_versions   = %(at_least_versions)s,
                type            = %(type)s,
                unit            = %(unit)s,
                data            = %(data)s,
                mime_type       = %(mime_type)s,
                mime_encoding       = %(mime_encoding)s,
                mime_value      = %(mime_value)s,
                file_owner      = %(file_owner)s,
                file_group      = %(file_group)s,
                file_mode       = %(file_mode)s,
                is_complessed       = %(is_complessed)s,
                is_database_config  = %(is_database_config)s,
                last_modify     = %(last_modify)s
        '''.strip()
    insertBinaryFileSQL = '''
        insert into binary_file (
            os_id,
            at_least_versions,
            type,
            unit,
            path,
            data,
            mime_type,
            mime_encoding,
            mime_value,
            file_owner,
            file_group,
            file_mode,
            is_complessed,
            last_modify
            )
            values (
            %(os_id)s,
            %(at_least_versions)s,
            %(type)s,
            %(unit)s,
            %(path)s,
            %(data)s,
            %(mime_type)s,
            %(mime_encoding)s,
            %(mime_value)s,
            %(file_owner)s,
            %(file_group)s,
            %(file_mode)s,
            %(is_complessed)s,
            %(last_modify)s
            )
            on duplicate key update
                at_least_versions   = %(at_least_versions)s,
                type            = %(type)s,
                unit            = %(unit)s,
                data            = %(data)s,
                mime_type       = %(mime_type)s,
                mime_encoding       = %(mime_encoding)s,
                mime_value      = %(mime_value)s,
                file_owner      = %(file_owner)s,
                file_group      = %(file_group)s,
                file_mode       = %(file_mode)s,
                is_complessed       = %(is_complessed)s,
                last_modify     = %(last_modify)s
        '''.strip()
    ##########################################################################
    getUnitNameSQL      = 'select distinct unit_name from package where unit_name is not null and os_id = %(os_id)s'
    ##########################################################################
    getTextFilesSQL     = 'select * from text_file where os_id = %(os_id)s'
    getBinaryFilesSQL   = 'select * from binary_file where os_id = %(os_id)s'
    ##########################################################################
    etcDir = getEtc.getEtc( 'system_sync' ).getTargetPath()
    configFile = etcDir.joinpath( 'system_sync.conf' )
    ##########################################################################
    def __init__( self, config_file=None ):
        '''このクラスは、同じサーバー何にある mariadb に接続し、同期を行います。'''
        ##########################################################################
        if config_file is None:
            self.config_file = str( system_sync.configFile )
        elif type( config_file ) is not str:
            raise TypeError( '設定ファイル({config_file})が文字列ではありません。'.format( config_file = str( config_file ) ) )
        elif len( config_file ) < 1:
            raise TypeError( '設定ファイル({config_file})が空文字列です。'.format( config_file = config_file ) )
        else:
            self.config_file = pathlib.Path( config_file ).resolve()
        ##########################################################################
        if not pathlib.Path( self.config_file ).exists():
            raise FileNotFoundError( '設定ファイル({config_file})が存在しません。'.format( config_file = self.config_file ) )
        elif not pathlib.Path( self.config_file ).is_file():
            raise FileNotFoundError( '設定ファイル({config_file})がファイルではありません。'.format( config_file = self.config_file ) )
        elif pathlib.Path( self.config_file ).stat().st_size < 1:
            raise KeyError( '設定ファイル({config_file})の中身が空です。'.format( config_file = self.config_file ) )
        ##########################################################################
        self.config = {}
        self.config = configparser.ConfigParser()
        self.config.read( self.config_file )
        self.default = self.config.defaults()
        self.sqlConfig = {}
        self.sqlMasterConfig = {}
        self.sqlSlaveConfig = {}
        self.databaseDump = {}
        self.sections = {}
        ##########################################################################
        self.allMachineInfo = []
        self.allInitializeInfo = []
        ##########################################################################
        floatPattern = re.compile( r'^-?\d+\.\d+$' )
        ##########################################################################
        for key in self.default.keys():
            value = self.default[ key ]
            if value.lower() in [ 'yes', 'true', 'on', 'no', 'false', 'off' ]:
                value = self.config['DEFAULT'].getboolean( key )
            elif value.isdigit():
                value = int( value )
            elif value.startswith('-') and value[1:].isdigit():
                value = int( value )
            elif floatPattern.search( value ):
                value = float( value )
            self.sqlConfig[ key ] = value
        ##########################################################################
        for section in self.config.sections():
            if section.lower() == 'master':
                for key in self.config[ section ].keys():
                    value = self.config[ section ][ key ]
                    if value.lower() in [ 'yes', 'true', 'on', 'no', 'false', 'off' ]:
                        value = self.config['DEFAULT'].getboolean( key )
                    elif value.isdigit():
                        value = int( value )
                    elif value.startswith('-') and value[1:].isdigit():
                        value = int( value )
                    elif floatPattern.search( value ):
                        value = float( value )
                    self.sqlMasterConfig[ key ] = value
            elif section.lower() == 'slave':
                for key in self.config[ section ].keys():
                    value = self.config[ section ][ key ]
                    if value.lower() in [ 'yes', 'true', 'on', 'no', 'false', 'off' ]:
                        value = self.config[ section ].getboolean( key )
                    elif value.isdigit():
                        value = int( value )
                    elif value.startswith('-') and value[1:].isdigit():
                        value = int( value )
                    elif floatPattern.search( value ):
                        value = float( value )
                    self.sqlSlaveConfig[ key ] = value
            elif section.lower() == 'mysqldumb':
                for key in self.config[ section ].keys():
                    value = self.config[ section ][ key ]
                    if value.lower() in [ 'yes', 'true', 'on', 'no', 'false', 'off' ]:
                        value = self.config[ section ].getboolean( key )
                    elif value.isdigit():
                        value = int( value )
                    elif value.startswith('-') and value[1:].isdigit():
                        value = int( value )
                    elif floatPattern.search( value ):
                        value = float( value )
                    self.databaseDump[ key ] = value
            else:
                self.sections[ section ] = {}
                for key in self.config[ section ].keys():
                    value = self.config[ section ][ key ]
                    if value.lower() in [ 'yes', 'true', 'on', 'no', 'false', 'off' ]:
                        value = self.config[ section ].getboolean( key )
                    elif value.isdigit():
                        value = int( value )
                    elif value.startswith('-') and value[1:].isdigit():
                        value = int( value )
                    elif floatPattern.search( value ):
                        value = float( value )
                    self.sections[ section ][ key ] = value
        ##########################################################################
        self.isMasterGetted = False
        self.isSlaveGetted = False
        self.isMasterValue = False
        self.isSlaveValue = False
        ##########################################################################
        self.platform = platform.system()
        self.os_name = self.platform
        self.os_vendor = self.platform
        self.os_type = self.platform
        self.os_version = platform.version()
        self.os_release = platform.release()
        self.os_edition = platform.platform()
        self.distribution = self.platform
        ##########################################################################
        if 'expect' not in self.sections:
            self.sections['expect'] = {}
            self.sections['expect']['timeout'] = system_sync.expectTimeout
        elif 'timeout' not in self.sections['expect']:
            self.sections['expect']['timeout'] = system_sync.expectTimeout
        elif type ( self.sections['expect'] ) is not int:
            self.sections['expect']['timeout'] = system_sync.expectTimeout
        elif self.sections['expect']['timeout'] < 1:
            self.sections['expect']['timeout'] = system_sync.expectTimeout
        ##########################################################################
        try:
            self.mysql_id =  pwd.getpwnam( 'mysql' ).pw_uid
            self.mysql_group_id = grp.getgrnam( 'mysql' ).gr_gid
        except:
            self.mysql_id = 0
            self.mysql_group_id = 0
        else:
            self.mysql_id = 0
            self.mysql_group_id = 0
        ##########################################################################
        if self.platform.lower() in ['linux', 'unix' ] :
            import distro
            self.os_name = distro.name()
            self.os_vendor = distro.name()
            self.distribution = distro.name()
            self.os_version = distro.version()
        elif self.platform.lower() in [ 'darwin', 'osx', 'mac' ] :
            self.os_name = 'OSX'
            self.os_vendor = 'Apple'
            self.distribution = 'Apple'
            self.platform = 'UNIX'
            self.os_version = platform.release()
        elif self.platform.lower() == 'windows' :
            self.os_name = self.platform + self.os_release
            self.distribution = 'Microsoft'
            self.os_vendor = 'Microsoft'
        ##########################################################################
        self.openConnect()
        ##########################################################################
        if self.isMaster():
            self.sqlMasterConfig[ 'host' ] = 'localhost'
            self.closeConnect()
            self.openConnect()
        else:
            del self.sqlMasterConfig[ 'unix_socket' ]
    ##########################################################################
    def __del__( self ):
        self.closeConnect()
    ##########################################################################
    def isMaster( self, needUpdate = False ):
        '''自機がマスターかどうかを返します。'''
        ##########################################################################
        if not hasattr( self, 'connector' ):
            self.openConnect()
        ##########################################################################
        if needUpdate or ( not self.isMasterGetted ) :
            self.cursor.execute( system_sync.isMasterSQL, { 'host': self.my_hostname } )
            for row in self.cursor.fetchall() :
                self.isMasterValue = ( int( row['isMaster'] ) > 0 )
                self.isMasterGetted = True
                break
        return ( self.isMasterValue );
    ##########################################################################
    def isSlave( self, needUpdate = False ):
        '''自機がスレイブかどうかを返します。'''
        ##########################################################################
        if not hasattr( self, 'connector' ):
            self.openConnect()
        ##########################################################################
        if needUpdate or ( not self.isSlaveGetted ) :
            self.cursor.execute( system_sync.isSlaveSQL, { 'host':  self.my_hostname } )
            for row in self.cursor.fetchall() :
                self.isSlaveValue = ( int( row['isSlave'] ) > 0 )
                self.isSlaveGetted = True
                break
        return ( self.isSlaveValue );
    ##########################################################################
    def closeConnect( self ):
        '''MariaDB への接続を解除します。'''
        if not hasattr( self, 'connector' ):
            return
        if self.connector.is_connected():
            self.connector.close()
    ##########################################################################
    def openConnect( self, connectType = 'default' ):
        '''指定された方法で MariaDB に接続します。'''
        ##########################################################################
        self.closeConnect()
        ##########################################################################
        if connectType == 'default' or not ( connectType.lower() == 'master' ):
            self.connector = mysql.connector.connect( **self.sqlSlaveConfig )
        else:
            self.connector = mysql.connector.connect( **self.sqlMasterConfig )
        ##########################################################################
        # SQL 文の名前置換では、prerared は使えない
        #self.cursor = self.connector.cursor( prepared = True )
        self.cursor = self.connector.cursor( dictionary = True )
        self.my_hostname = socket.gethostname()
        ##########################################################################
        self.getMachineInfo()
        self.getOsInfo()
        self.getDomainInfo()
        self.getInitializeInfo()
        ##########################################################################
    ##########################################################################
    def openConnectToMaster( self ):
        '''マスターサーバーへ接続します。'''
        if self.isMaster(): 
            return;
        else:
            self.openConnect( connectType = 'master' )
    ##########################################################################
    def ping( self, server, retryCount=1 ):
        '''指定されたマシンが接続可能かどうかを調べます。'''
        try:
            subprocess.run( [ 'ping', '-c', str( retryCount ), server ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL )
        except:
            return ( False )
        else:
            return ( True )
    ##########################################################################
    def getMachineInfo( self ):
        '''マシン情報を取得します。'''
        ##########################################################################
        if not hasattr( self, 'my_hostname' ):
            self.my_hostname = socket.gethostname()
        ##########################################################################
        if not hasattr( self, 'connector' ):
            self.openConnect()
        ##########################################################################
        self.cursor.execute( system_sync.machineInfoSQL, { 'host': self.my_hostname } )
        for row in self.cursor.fetchall() :
            self.machineInfo = row
        return ( self.machineInfo )
    ##########################################################################
    def getAllMachineInfo( self ):
        '''全てのマシン情報を取得します。'''
        ##########################################################################
        if not hasattr( self, 'my_hostname' ):
            self.my_hostname = socket.gethostname()
        ##########################################################################
        if not hasattr( self, 'connector' ):
            self.openConnect()
        ##########################################################################
        self.cursor.execute( system_sync.machineInfoListSQL  )
        self.allMachineInfo = self.cursor.fetchall()
        return ( self.allMachineInfo )
    ##########################################################################
    def getAllInitializeInfo( self ):
        '''全てのマシン初期化情報を取得します。'''
        ##########################################################################
        if not hasattr( self, 'my_hostname' ):
            self.my_hostname = socket.gethostname()
        ##########################################################################
        if not hasattr( self, 'connector' ):
            self.openConnect()
        ##########################################################################
        self.cursor.execute( system_sync.initializeListSQL )
        self.allInitializeInfo = self.cursor.fetchall()
        return ( self.allInitializeInfo )
    ##########################################################################
    def doCommand( self, machine_id, command, data = {}, sub_data = {} ):
        '''コマンドを実行します。'''
        ##########################################################################
        if not hasattr( self, 'connector' ):
            self.openConnect()
        ##########################################################################
        # 自マシン情報の取得
        ##########################################################################
        if not hasattr( self, 'machineInfo' ):
            self.getMachineInfo()
        ##########################################################################
        # 全マシン情報の取得
        ##########################################################################
        if not hasattr( self, 'allMachineInfo' ):
            self.getAllMachineInfo()
        elif len( self.allMachineInfo ) < 1:
            self.getAllMachineInfo()
        ##########################################################################
        # 対象マシン情報の取得
        ##########################################################################
        if type( machine_id ) is not int:
            raise TypeError( 'machine_id ({machine_id}) が有効ではではありません。'.format( machine_id = str( machine_id ) ) ) 
        elif machine_id < 1:
            raise KeyError( 'machine_id ({machine_id}) が有効ではではありません。'.format( machine_id = str( machine_id ) ) ) 
        targetMachineInfo = None
        for machine in self.allMachineInfo:
            if machine['id'] == machine_id:
                targetMachineInfo = machine
                break
        if targetMachineInfo is None:
            raise KeyError( 'machine_id ({machine_id}) が有効ではではありません。'.format( machine_id = str( machine_id ) ) ) 
        ##########################################################################
        if type( command ) is not dict:
            raise TypeError( 'command ({command}) が有効ではではありません。'.format( command = str( command ) ) ) 
        elif 'command' not in command:
            raise KeyError( 'command ({command}) が有効ではではありません。'.format( command = str( command ) ) ) 
        elif 'allow_error' not in command:
            raise KeyError( 'command ({command}) が有効ではではありません。'.format( command = str( command ) ) ) 
        elif 'is_shell_subprocess' not in command:
            raise KeyError( 'command ({command}) が有効ではではありません。'.format( command = str( command ) ) ) 
        ##########################################################################
        if type( data ) is not dict:
            raise TypeError( 'data ({data}) が有効ではではありません。'.format( data = str( data ) ) ) 
        ##########################################################################
        if type( sub_data ) is not dict:
            raise TypeError( 'sub_data ({sub_data}) が有効ではではありません。'.format( sub_data = str( sub_data ) ) ) 
        ##########################################################################
        patternStr = re.escape( '{') + '''(\w+)''' + re.escape( '}')
        pattern = re.compile( patternStr )
        ##########################################################################
        args = {}
        for match in pattern.finditer( command['command'] ):
            key = match.group(1)
            if key in data:
                args[ key ] = data[ key ]
            elif key in sub_data:
                args[ key ] = sub_data[ key ]
            elif key in targetMachineInfo:
                args[ key ] = targetMachineInfo[ key ]
            else:
                raise KeyError( 'command ({command}) の key ({key}) が有効ではではありません。'.format( command = command['command'], key = str( key ) ) ) 
        ##########################################################################
        if len( args ) < 1:
            commandStr = command['command']
        else:
            commandStr = command['command'].format( **args )
        ##########################################################################
        if self.machineInfo['id'] == machine_id:
            ##########################################################################
            # 自マシンで実行
            ##########################################################################
            commandList = commandStr.split( maxsplit = command['maxsplit'] )
            command['is_shell_subprocess'] = bool( command['is_shell_subprocess'] )
            result = subprocess.run( commandList, shell = command['is_shell_subprocess'] ).returncode == 0 or command['allow_error']
        else:
            ##########################################################################
            # ssh で実行
            ##########################################################################
            result = self.ssh( machine_id = machine_id, commandStr = commandStr ) or command['allow_error']
        ##########################################################################
        return result
    ##########################################################################
    def getPackageInitializeInfo( self, machine_id=None ):
        '''パッケージのマシン初期化情報を取得します。'''
        ##########################################################################
        if not hasattr( self, 'connector' ):
            self.openConnect()
        ##########################################################################
        if not hasattr( self, 'machineInfo' ):
            self.getMachineInfo()
        ##########################################################################
        # 全マシン情報の取得
        ##########################################################################
        if not hasattr( self, 'allMachineInfo' ):
            self.getAllMachineInfo()
        elif len( self.allMachineInfo ) < 1:
            self.getAllMachineInfo()
        ##########################################################################
        if machine_id is None:
            machine_id = self.machineInfo['id']
            os_id = self.machineInfo['os_id']
        elif type( machine_id ) is not int:
            raise TypeError( 'machine_id ({machine_id}) が有効ではではありません。'.format( machine_id = str( machine_id ) ) ) 
        elif machine_id < 1:
            raise KeyError( 'machine_id ({machine_id}) が有効ではではありません。'.format( machine_id = str( machine_id ) ) ) 
        ##########################################################################
        self.cursor.execute( system_sync.packageInitializeListSQL, { 'machine_id': machine_id } )
        packageInitializeList = self.cursor.fetchall()
        ##########################################################################
        packedPakageInitializeList = []
        for packageInitialize in packageInitializeList:
            packageInitialize['dpend_on_unit']  = bool( packageInitialize['dpend_on_unit'] )
            packageInitialize['need_enable']    = bool( packageInitialize['need_enable'] )
            packageInitialize['need_start']     = bool( packageInitialize['need_start'] )
            packageInitialize['initialized']    = bool( packageInitialize['initialized'] )
            if packageInitialize['unit_name'] is None:
                ##########################################################################
                # 単なるパッケージ
                ##########################################################################
                packedPakageInitializeList.append( packageInitialize )
                continue
            elif not packageInitialize['dpend_on_unit']:
                ##########################################################################
                # ユニットパッケージ
                ##########################################################################
                if 'sub_package' not in packageInitialize:
                    packageInitialize['sub_package'] = []
                if len( packedPakageInitializeList ) > 0:
                    if packedPakageInitializeList[-1]['unit_name'] != packageInitialize['unit_name']:
                        packedPakageInitializeList.append( packageInitialize )
                        continue
                    else:
                        print( 'WARNING : Duplicate unit ({unit})'.format( unit = packageInitialize['unit_name'] ), file = sys.stderr )
                        continue
                else:
                    packedPakageInitializeList.append( packageInitialize )
                    continue
            elif len( packedPakageInitializeList ) > 0:
                ##########################################################################
                # ユニット依存パッケージ
                ##########################################################################
                if packedPakageInitializeList[-1]['unit_name'] is None:
                    print( 'WARNING : ({name}) Parent unit ({unit}) NOT FOUND'.format( name = packageInitialize['name'], unit = packageInitialize['unit_name'] ), file = sys.stderr )
                    continue
                if 'sub_package' not in packedPakageInitializeList[-1]:
                    packedPakageInitializeList[-1]['sub_package'] = []
                if packedPakageInitializeList[-1]['unit_name'] == packageInitialize['unit_name']:
                    packedPakageInitializeList[-1]['sub_package'].append( packageInitialize )
                    continue
                else:
                    ##########################################################################
                    # パッケージ依存エラー
                    ##########################################################################
                    print( 'パッケージ依存エラー : WARNING : ({name}) Parent unit ({unit}) NOT FOUND'.format( name = packageInitialize['package'], unit = packageInitialize['unit_name'] ), file = sys.stderr )
                    continue
            else:
                ##########################################################################
                # 初回からのいきなりなユニット依存パッケージ
                ##########################################################################
                print( 'WARNING : ({name}) Parent unit ({unit}) NOT FOUND'.format( name = packageInitialize['package'], unit = packageInitialize['unit_name'] ), file = sys.stderr )
                continue
        ##########################################################################
        # 修了
        ##########################################################################
        return ( packedPakageInitializeList )
    ##########################################################################
    def getRsyncInitializeInfo( self, machine_id=None ):
        '''rsync のマシン初期化情報を取得します。'''
        ##########################################################################
        if not hasattr( self, 'connector' ):
            self.openConnect()
        ##########################################################################
        if not hasattr( self, 'machineInfo' ):
            self.getMachineInfo()
        ##########################################################################
        if not hasattr( self, 'allMachineInfo' ):
            self.getMachineInfo()
        ##########################################################################
        # マスター接続
        ##########################################################################
        if not hasattr( self, 'connector' ):
            self.openConnect( connectType = 'master' )
        else:
            self.openConnectToMaster()
        ##########################################################################
        # 全マシン情報の取得
        ##########################################################################
        if not hasattr( self, 'allMachineInfo' ):
            self.getAllMachineInfo()
        elif len( self.allMachineInfo ) < 1:
            self.getAllMachineInfo()
        ##########################################################################
        if machine_id is None:
            machine_id = self.machineInfo['id']
            os_id = self.machineInfo['os_id']
        elif type( machine_id ) is not int:
            raise KeyError( 'machine_id ({machine_id}) が有効ではではありません。'.format( machine_id = str( machine_id ) ) ) 
        elif machine_id < 1:
            raise KeyError( 'machine_id ({machine_id}) が有効ではではありません。'.format( machine_id = str( machine_id ) ) ) 
        ##########################################################################
        self.cursor.execute( system_sync.resetRsyncDateSQL )
        self.cursor.execute( system_sync.resetInitializeSQL )
        ##########################################################################
        self.cursor.execute( system_sync.rsyncInitializeSQL, { 'machine_id': machine_id } )
        lastRow = {}
        rowList = []
        for row in self.cursor.fetchall():
            if row == lastRow:
                continue
            lastRow = row
            rowList.append( row )
        return ( rowList )
    ##########################################################################
    def getCommandInitializeInfo( self, machine_id=None ):
        '''パッケージのマシン初期化情報を取得します。'''
        ##########################################################################
        if not hasattr( self, 'connector' ):
            self.openConnect()
        ##########################################################################
        if not hasattr( self, 'machineInfo' ):
            self.getMachineInfo()
        ##########################################################################
        # 全マシン情報の取得
        ##########################################################################
        if not hasattr( self, 'allMachineInfo' ):
            self.getAllMachineInfo()
        elif len( self.allMachineInfo ) < 1:
            self.getAllMachineInfo()
        ##########################################################################
        if machine_id is None:
            machine_id = self.machineInfo['id']
            os_id = self.machineInfo['os_id']
        elif type( machine_id ) is not int:
            raise KeyError( 'machine_id ({machine_id}) が有効ではではありません。'.format( machine_id = str( machine_id ) ) ) 
        elif machine_id < 1:
            raise KeyError( 'machine_id ({machine_id}) が有効ではではありません。'.format( machine_id = str( machine_id ) ) ) 
        ##########################################################################
        self.cursor.execute( system_sync.commandInitializeSQL, { 'machine_id': machine_id } )
        return ( self.cursor.fetchall() )
    ##########################################################################
    def initializeMachine( self, machine_id=None ):
        '''マシンを初期化します。'''
        ##########################################################################
        if not hasattr( self, 'connector' ):
            self.openConnect()
        ##########################################################################
        if not hasattr( self, 'machineInfo' ):
            self.getMachineInfo()
        ##########################################################################
        if not hasattr( self, 'allInitializeInfo' ):
            self.getAllInitializeInfo()
        elif len( self.allInitializeInfo ) < 1:
            self.getAllInitializeInfo()
        ##########################################################################
        # 全マシン情報の取得
        ##########################################################################
        if not hasattr( self, 'allMachineInfo' ):
            self.getAllMachineInfo()
        elif len( self.allMachineInfo ) < 1:
            self.getAllMachineInfo()
        ##########################################################################
        # 対象マシン情報の取得
        ##########################################################################
        if machine_id is None:
            machine_id = self.machineInfo['id']
            os_id = self.machineInfo['os_id']
            targetMachineInfo = self.machineInfo
        else:
            os_id = None
            for machine in self.allMachineInfo:
                if machine['id'] == machine_id:
                    targetMachineInfo = machine
                    os_id = machine['os_id']
                    break
            if os_id is None:
                raise KeyError( 'machine_id ({machine_id}) が有効ではではありません。'.format( machine_id = str( machine_id ) ) ) 
        ##########################################################################
        initialize = None
        for initialize in self.allInitializeInfo:
            if initialize['machine_id'] == machine_id:
                break
        if initialize is None:
                raise KeyError( 'machine_id ({machine_id}) が有効ではではありません。'.format( machine_id = str( machine_id ) ) ) 
        ##########################################################################
        self.cursor.execute( system_sync.resetRsyncDateSQL )
        self.cursor.execute( system_sync.resetInitializeSQL )
        ##########################################################################
        initialize['system_config_done'] = bool( initialize['system_config_done'] )
        if initialize['system_config_done']:
            ##########################################################################
            systemConfigFileList = self.getSystemConfigFile( machine_id )
            initialize['system_config_done'] = bool( self.writeToFile( systemConfigFileList ) )
            ##########################################################################
            initialize['system_config_done'] = self.doCommand( machine_id, initializeCommand, initialize )
        ##########################################################################
        rsyncInitializeList = self.getRsyncInitializeInfo( machine_id )
        initialize['rsync_done'] = bool( initialize['rsync_done'] )
        if self.isMaster():
            if targetMachineInfo['type'].lower() == 'master':
                initialize['rsync_done'] = True
                for rsyncInitialize in rsyncInitializeList:
                    self.cursor.execute( system_sync.insertRsyncDateSQL,
                        {
                        'rsync_id' : rsyncInitialize['rsync_id'],
                        'machine_id': machine_id,
                        'unit_name': rsyncInitialize['unit'],
                        'update_term_seconds': rsyncInitialize['update_term_seconds'],
                        'is_done': True
                        } )
            elif targetMachineInfo['type'].lower() == 'slave' and not initialize['rsync_done']:
                rsyncResult = True
                for rsyncInitialize in rsyncInitializeList:
                    if rsyncInitialize['unit'] is None:
                        if not self.rsync( machine_id, rsyncInitialize['directory'] ):
                            rsyncResult = False
                initialize['rsync_done'] = rsyncResult
        ##########################################################################
        packageInitializeList = self.getPackageInitializeInfo( machine_id )
        ##########################################################################
        for packageInitialize in packageInitializeList:
            packageInitialize['initialized'] = bool( packageInitialize['initialized'] )
            if packageInitialize['initialized']:
                continue
            ##########################################################################
            preUnitInitialize = True
            if packageInitialize['unit_name'] is not None:
                self.cursor.execute( system_sync.commandUnitPreInitializeSQL, { 'unit_name': packageInitialize['unit_name'], 'machine_id': machine_id } )
                commandUnitPreInitializeList = self.cursor.fetchall()
                for commandUnitPreInitialize in commandUnitPreInitializeList:
                    preUnitInitialize = self.doCommand( machine_id, commandUnitPreInitialize, commandUnitPreInitialize )
            ##########################################################################
            packageInitialize['initialized'] = self.installPackage( machine_id, packageInitialize['package'] ) and preUnitInitialize
            if 'sub_package' in packageInitialize and len( packageInitialize['sub_package'] ) > 0:
                for subPackage in packageInitialize['sub_package']:
                    packageInitialize['initialized'] = self.installPackage( machine_id, subPackage['package'] ) and packageInitialize['initialized']
            ##########################################################################
            if packageInitialize['initialized'] and packageInitialize['unit_name'] is not None:
                ##########################################################################
                if not self.doUnitCommand( machine_id, packageInitialize['unit_name'] ):
                    packageInitialize['initialized'] = False
                ##########################################################################
                textConfigList = self.getUnitText( machine_id, packageInitialize['unit_name'] )
                bonaryConfigList = self.getUnitBinary( machine_id, packageInitialize['unit_name'] )
                configFileList = textConfigList + bonaryConfigList
                if not self.writeToFile( configFileList ):
                    packageInitialize['initialized'] = False
                ##########################################################################
                for rsyncInitialize in rsyncInitializeList:
                    if rsyncInitialize['unit'] is None:
                        continue
                    elif rsyncInitialize['unit'] != packageInitialize['unit_name']:
                        continue
                    elif not self.rsync( machine_id, rsyncInitialize['directory'] ):
                        packageInitialize['initialized'] = False
                    else:
                        continue
                ##########################################################################
                if packageInitialize['initialized']:
                    packageInitialize['initialized'] = self.doUnitSatrt( packageInitialize )
            ##########################################################################
            self.cursor.execute( system_sync.insertPackageInitializeSQL, { 'package_id': packageInitialize['package_id'], 'machine_id': machine_id, 'initialized': packageInitialize['initialized'] } )
            if 'sub_package' in packageInitialize and len( packageInitialize['sub_package'] ) > 0:
                for subPackage in packageInitialize['sub_package']:
                    self.cursor.execute( system_sync.insertPackageInitializeSQL, { 'package_id': subPackage['package_id'], 'machine_id': machine_id, 'initialized': packageInitialize['initialized'] } )
        ##########################################################################
        return True
    ##########################################################################
    def resetPackageInitializeMachine( self, machine_id=None ):
        '''マシンの　package_initialize をリセットます。'''
        ##########################################################################
        if not hasattr( self, 'connector' ):
            self.openConnect()
        ##########################################################################
        if not hasattr( self, 'machineInfo' ):
            self.getMachineInfo()
        ##########################################################################
        if not hasattr( self, 'allInitializeInfo' ):
            self.getAllInitializeInfo()
        elif len( self.allInitializeInfo ) < 1:
            self.getAllInitializeInfo()
        ##########################################################################
        # 全マシン情報の取得
        ##########################################################################
        if not hasattr( self, 'allMachineInfo' ):
            self.getAllMachineInfo()
        elif len( self.allMachineInfo ) < 1:
            self.getAllMachineInfo()
        ##########################################################################
        # 対象マシン情報の取得
        ##########################################################################
        if machine_id is None:
            machine_id = self.machineInfo['id']
            os_id = self.machineInfo['os_id']
            targetMachineInfo = self.machineInfo
        else:
            os_id = None
            for machine in self.allMachineInfo:
                if machine['id'] == machine_id:
                    targetMachineInfo = machine
                    os_id = machine['os_id']
                    break
            if os_id is None:
                raise KeyError( 'machine_id ({machine_id}) が有効ではではありません。'.format( machine_id = str( machine_id ) ) ) 
        ##########################################################################
        self.cursor.execute( system_sync.resetPackageInitializeSQL, { 'machine_id': machine_id } )
        ##########################################################################
        return True
    ##########################################################################
    def resetRsyncDateMachine( self, machine_id=None ):
        '''マシンの rsync_date の is_done をリセットます。'''
        ##########################################################################
        if not hasattr( self, 'connector' ):
            self.openConnect()
        ##########################################################################
        if not hasattr( self, 'machineInfo' ):
            self.getMachineInfo()
        ##########################################################################
        if not hasattr( self, 'allInitializeInfo' ):
            self.getAllInitializeInfo()
        elif len( self.allInitializeInfo ) < 1:
            self.getAllInitializeInfo()
        ##########################################################################
        # 全マシン情報の取得
        ##########################################################################
        if not hasattr( self, 'allMachineInfo' ):
            self.getAllMachineInfo()
        elif len( self.allMachineInfo ) < 1:
            self.getAllMachineInfo()
        ##########################################################################
        # 対象マシン情報の取得
        ##########################################################################
        if machine_id is None:
            machine_id = self.machineInfo['id']
            os_id = self.machineInfo['os_id']
            targetMachineInfo = self.machineInfo
        else:
            os_id = None
            for machine in self.allMachineInfo:
                if machine['id'] == machine_id:
                    targetMachineInfo = machine
                    os_id = machine['os_id']
                    break
            if os_id is None:
                raise KeyError( 'machine_id ({machine_id}) が有効ではではありません。'.format( machine_id = str( machine_id ) ) ) 
        ##########################################################################
        self.cursor.execute( system_sync.resetRsyncDateMachineSQL, { 'machine_id': machine_id } )
        ##########################################################################
        return True
    ##########################################################################
    def dumpDatabase( self, machine_id ):
        '''データベースのスレイブ用のダンプファイル(SQL)を作成します。'''
        ##########################################################################
        if not self.isMaster():
            return False
        ##########################################################################
        # 全マシン情報の取得
        ##########################################################################
        if not hasattr( self, 'allMachineInfo' ):
            self.getAllMachineInfo()
        elif len( self.allMachineInfo ) < 1:
            self.getAllMachineInfo()
        ##########################################################################
        # 対象マシン情報の取得
        ##########################################################################
        if type( machine_id ) is not int:
            raise TypeError( 'machine_id ({machine_id}) が有効ではではありません。'.format( machine_id = str( machine_id ) ) ) 
        elif machine_id < 1:
            raise KeyError( 'machine_id ({machine_id}) が有効ではではありません。'.format( machine_id = str( machine_id ) ) ) 
        targetMachineInfo = None
        for machine in self.allMachineInfo:
            if machine['id'] == machine_id:
                targetMachineInfo = machine
                break
        if targetMachineInfo is None:
            raise KeyError( 'machine_id ({machine_id}) が有効ではではありません。'.format( machine_id = str( machine_id ) ) ) 
        ##########################################################################
        dumpAbsPath = pathlib.Path( system_sync.databaseDumpPath ).resolve()
        with dumpAbsPath.open( mode='w' ) as file:
            print( 'set global read_only = false;', file=file )
            print( 'STOP ALL SLAVES;', file=file )
            print( 'RESET SLAVE ALL;', file=file )
            ##########################################################################
            # DROP DATABASE
            ##########################################################################
            with subprocess.Popen( [ 'mariadb', '--user=' + self.databaseDump['user'], '--password=' + self.databaseDump['password'], '--batch', '--skip-column-names', '-e', 'show databases' ], stdout=subprocess.PIPE ) as databaseListProcess:
                for line in databaseListProcess.stdout.readlines():
                    line = line.decode( 'utf-8' ).strip()
                    if line == 'mysql' or line == 'mariadb' or line.endswith('_schema'):
                        continue
                    print( 'DROP DATABASE IF EXISTS ' + line + ';', file=file )
            ##########################################################################
            # DATABASE DUMP
            ##########################################################################
            with subprocess.Popen( [ 'mysqldump', '--user=' + self.databaseDump['user'], '--password=' + self.databaseDump['password'], '--all-databases', '--add-drop-database', '--add-drop-table', '--master-data', '--gtid', '--hex-blob', '--single-transaction', '--flush-privileges' ], stdout=subprocess.PIPE ) as databaseDumpProcess:
                for line in databaseDumpProcess.stdout.readlines():
                    strLine = line.decode( 'utf-8' )
                    if strLine.strip().lower().startswith( 'change master to' ):
                        continue
                    elif strLine.strip().lower().startswith( '-- set global gtid_slave_pos' ):
                        strLine = strLine[3:]
                    print( strLine, end='', file=file )
            ##########################################################################
            # SLAVE SETTING
            ##########################################################################
            slaveIdSettingSQL = '''
                SET GLOBAL server_id = %(server_id)s;
                SET GLOBAL gtid_domain_id = %(domain_id)s;
            '''.strip() % {
                'server_id': machine_id,
                'domain_id': targetMachineInfo['domain_id']
                }
            #print( slaveIdSettingSQL, file=file )
            ##########################################################################
            masterSQL = '''
                CHANGE MASTER '%(name)s' TO
                    MASTER_HOST     = '%(host)s',
                    MASTER_USER     = '%(user)s',
                    MASTER_PASSWORD = '%(password)s',
                    MASTER_USE_GTID = slave_pos;

            START SLAVE '%(name)s';
            '''.strip() % {
                'name': self.sections['slave_param']['master_host'],
                'host': self.sections['slave_param']['master_host'],
                'user': self.sections['slave_param']['master_user'],
                'password': self.sections['slave_param']['master_password']
                }
            print( masterSQL, file=file )
            ##########################################################################
            # FINISH
            ##########################################################################
            print( 'set global read_only = true;', file=file )
        ##########################################################################
        return True
    ##########################################################################
    def writeDatabaseServerConfig( self, machine_id=None, databaseServerConfigFile=None, writeDatabaseServerConfigPath=None, writeToFile=True ):
        '''データベースの設定ファイルを編集します。'''
        ##########################################################################
        if not hasattr( self, 'macchineInfo' ):
            self.getMachineInfo()
        ##########################################################################
        if not self.isMaster():
            raise KeyError( '({machine}) マスターサーバー以外から呼び出されました。'.format( machine = str( self.machineInfo ) ) )
        ##########################################################################
        if machine_id is None:
            machine_id = self.machineInfo['id']
        ##########################################################################
        # 全マシン情報の取得
        ##########################################################################
        if not hasattr( self, 'allMachineInfo' ):
            self.getAllMachineInfo()
        elif len( self.allMachineInfo ) < 1:
            self.getAllMachineInfo()
        ##########################################################################
        # 対象マシン情報の取得
        ##########################################################################
        targetMachine = None
        for targetMachine in self.allMachineInfo:
            if targetMachine['id'] == machine_id:
                break
        if targetMachine is None:
            raise KeyError( 'machine_id ({machine_id}) の値が正しくありません。'.format( machine_id = str( machine_id ) ) )
        ##########################################################################
        if databaseServerConfigFile is None:
            databaseServerConfigFile = system_sync.databaseServerConfigPath
        ##########################################################################
        if writeDatabaseServerConfigPath is None:
            writeDatabaseServerConfigPath = system_sync.databaseServerConfigPath
        ##########################################################################
        databaseServerConfigAbsPath = pathlib.Path( databaseServerConfigFile ).resolve()
        if not databaseServerConfigAbsPath.is_file():
            raise FileNotFoundError( '設定ファイル({config_file})が存在しません'.format( config_file = databaseServerConfigAbsPath ) )
        config = configparser.ConfigParser( allow_no_value=True )
        config.read( str( databaseServerConfigAbsPath ) )
        ##########################################################################
        serverSecsion = None
        ##########################################################################
        if config.has_section('mysqld'):
            serverSecsion = 'mysqld'
        elif config.has_section('mariadbd'):
            serverSecsion = 'mariadbd'
        elif config.has_section('mariadb'):
            serverSecsion = 'mariadb'
        elif config.has_section('server'):
            serverSecsion = 'server'
        else:
            raise KeyError( '設定ファイル({config_file})にサーバー設定がが存在しません'.format( config_file = databaseServerConfigAbsPath ) )
        ##########################################################################
        config[ serverSecsion ]['log_bin'] = 'on'
        config[ serverSecsion ]['gtid_domain_id'] = str( targetMachine['domain_id'] )
        config[ serverSecsion ]['server_id'] = str( targetMachine['id'] )
        config[ serverSecsion ]['log_basename'] = targetMachine['type'] + str( targetMachine['id'] )
        config[ serverSecsion ]['binlog_format'] = 'ROW'
        config[ serverSecsion ]['log_slave_updates'] = 'on'
        config[ serverSecsion ]['read_only'] = 'off' if targetMachine['type'] == 'master' else 'on'
        config[ serverSecsion ]['character-set-server'] = 'utf8'
        ##########################################################################
        config[ 'mariadb' ] = config[ serverSecsion ]
        ##########################################################################
        if writeToFile:
            if machine_id == self.machineInfo['id']:
                with databaseServerConfigAbsPath.open( mode = 'w' ) as file:
                    config.write( file )
                return True
            elif not self.ping( targetMachine['name'] ):
                # Target Machine is NOT ACTIVE
                return False
            else:
                ( fd, path ) = tempfile.mkstemp( suffix = '.cnf', text = True )
                with os.fdopen( fd, mode = 'w' ) as file:
                    config.write( file )
                pathlib.Path( path ).chmod( 0o644 )
                os.chown( path, self.mysql_id, self.mysql_group_id )
                result = self.scp( targetMachine['id'], path, str( writeDatabaseServerConfigPath ) )
                pathlib.Path( path ).unlink()
                return result
        else:
            stringFile = io.StringIO()
            config.write( stringFile )
            resultStr = stringFile.getvalue()
            stringFile.close()
            return resultStr
        ##########################################################################
        return False
    ##########################################################################
    def installPackage( self, machine_id, packageName ):
        '''パッケージをインストールします。'''
        ##########################################################################
        if type( machine_id ) is not int:
            raise TypeError( 'machine_id({machine_id})が整数ではありません。'.format( machine_id = str( machine_id ) ) )
        elif machine_id < 1:
            raise KeyError( 'machine_id({machine_id})が整数ではありません。'.format( machine_id = str( machine_id ) ) )
        elif type( packageName ) is not str:
            raise TypeError( 'packageName({packageName})が文字列ではありません。'.format( packageName = str( packageName ) ) )
        elif len( packageName ) < 1:
            raise TypeError( 'packageName({packageName})が空です。'.format( packageName = str( packageName ) ) )
        ##########################################################################
        # 全マシン初期化情報の取得
        ##########################################################################
        if not hasattr( self, 'allInitializeInfo' ):
            self.getAllInitializeInfo()
        elif len( self.allInitializeInfo ) < 1:
            self.getAllInitializeInfo()
        ##########################################################################
        # 全マシン情報の取得
        ##########################################################################
        if not hasattr( self, 'allMachineInfo' ):
            self.getAllMachineInfo()
        elif len( self.allMachineInfo ) < 1:
            self.getAllMachineInfo()
        ##########################################################################
        # 対象マシン情報の取得
        ##########################################################################
        targetMachine = None
        for targetMachine in self.allMachineInfo:
            if targetMachine['id'] == machine_id:
                break
        if targetMachine is None:
            raise KeyError( 'machine_id ({machine_id}) の値が正しくありません。'.format( machine_id = str( machine_id ) ) )
        ##########################################################################
        # 対象パッケージ情報の取得
        ##########################################################################
        self.cursor.execute( system_sync.packageCheckSQL, { 'package': packageName, 'machine_id': machine_id } )
        packageInfo = None
        for packageInfo in self.cursor.fetchall():
            pass
        if packageInfo is None:
            raise KeyError( '({packageName}) パッケージが見つかりません。'.format( packageName = str( packageName ) ) )
        ##########################################################################
        # パッケージインストールコマンドの取得
        ##########################################################################
        self.cursor.execute( system_sync.packageInstallCommandSQL, { 'machine_id': machine_id } )
        packageInstallCommand = None
        for packageInstallCommand in self.cursor.fetchall():
            pass
        if packageInstallCommand is None:
            raise KeyError( '({packageInstallCommand}) パッケージインストールコマンドが見つかりません。'.format( packageInstallCommand = str( packageInstallCommand ) ) )
        ##########################################################################
        # パッケージインストールコマンドの実行
        ##########################################################################
        return self.doCommand( machine_id, packageInstallCommand, packageInfo )
    ##########################################################################
    def doUnitCommand( self, machine_id, unit_name ):
        '''ユニット関連の初期化コマンドを実行します。'''
        ##########################################################################
        if type( machine_id ) is not int:
            raise TypeError( 'machine_id({machine_id})が整数ではありません。'.format( machine_id = str( machine_id ) ) )
        elif machine_id < 1:
            raise KeyError( 'machine_id({machine_id})が整数ではありません。'.format( machine_id = str( machine_id ) ) )
        elif type( unit_name ) is not str:
            raise TypeError( 'unit_name({unit_name})が文字列ではありません。'.format( unit_name = str( unit_name ) ) )
        elif len( unit_name ) < 1:
            raise TypeError( 'unit_name({unit_name})が空です。'.format( unit_name = str( unit_name ) ) )
        ##########################################################################
        # 全マシン情報の取得
        ##########################################################################
        if not hasattr( self, 'allMachineInfo' ):
            self.getAllMachineInfo()
        elif len( self.allMachineInfo ) < 1:
            self.getAllMachineInfo()
        ##########################################################################
        # 対象マシン情報の取得
        ##########################################################################
        targetMachine = None
        for targetMachine in self.allMachineInfo:
            if targetMachine['id'] == machine_id:
                break
        if targetMachine is None:
            raise KeyError( 'machine_id ({machine_id}) の値が正しくありません。'.format( machine_id = str( machine_id ) ) )
        ##########################################################################
        self.cursor.execute( system_sync.commandUnitInitializeSQL, { 'machine_id': machine_id, 'unit_name': unit_name } )
        commandUnitInitializeList = self.cursor.fetchall()
        ##########################################################################
        for commandUnitInitialize in commandUnitInitializeList:
            if not self.doCommand( machine_id, commandUnitInitialize, { 'unit_name': unit_name, 'unit': unit_name, 'machine_id': machine_id } ):
                return False
        ##########################################################################
        return True
    ##########################################################################
    def doUnitSatrt( self, package ):
        '''ユニットを開始します。'''
        ##########################################################################
        if type( package ) is not dict:
            raise TypeError( 'package({package})が辞書型ではありません。'.format( package = str( package ) ) )
        elif 'unit_name' not in package:
            raise TypeError( 'package({package})にユニット名がありません。'.format( package = str( package ) ) )
        elif package['unit_name'] is None:
            return True
        elif 'need_enable' not in package:
            raise TypeError( 'package({package})に need_enable がありません。'.format( package = str( package ) ) )
        elif 'need_start' not in package:
            raise TypeError( 'package({package})に need_start がありません。'.format( package = str( package ) ) )
        elif 'machine_id' not in package:
            raise TypeError( 'package({package})に machine_id がありません。'.format( package = str( package ) ) )
        elif 'package_id' not in package:
            raise TypeError( 'package({package})に package_id がありません。'.format( package = str( package ) ) )
        ##########################################################################
        # 全マシン情報の取得
        ##########################################################################
        if not hasattr( self, 'allMachineInfo' ):
            self.getAllMachineInfo()
        elif len( self.allMachineInfo ) < 1:
            self.getAllMachineInfo()
        ##########################################################################
        # 対象マシン情報の取得
        ##########################################################################
        machine_id = package['machine_id']
        targetMachine = None
        for targetMachine in self.allMachineInfo:
            if targetMachine['id'] == machine_id:
                break
        if targetMachine is None:
            raise KeyError( 'machine_id ({machine_id}) の値が正しくありません。'.format( machine_id = str( machine_id ) ) )
        ##########################################################################
        result = True
        ##########################################################################
        package['need_enable'] = bool( package['need_enable'] )
        if package['need_enable']:
            ##########################################################################
            # ユニット自動起動コマンドの取得
            ##########################################################################
            self.cursor.execute( system_sync.unitEnableCommandSQL, { 'machine_id': machine_id } )
            unitEnableCommandList = self.cursor.fetchall()
            unitEnableCommand = None
            for unitEnableCommand in unitEnableCommandList:
                pass
            if unitEnableCommand is None:
                raise KeyError( '({machine}) unit enable コマンドが見つかりません。'.format( machine = str( self.machineInfo ) ) )
            ##########################################################################
            # ユニット自動起動コマンドの実行
            ##########################################################################
            result = self.doCommand( machine_id, unitEnableCommand, { 'unit_name': package['unit_name'], 'unit': package['unit_name'], 'machine_id': machine_id } ) and result
        ##########################################################################
        package['need_start'] = bool( package['need_start'] )
        if package['need_start']:
            ##########################################################################
            # ユニット開始コマンドの取得
            ##########################################################################
            self.cursor.execute( system_sync.unitStartCommandSQL, { 'machine_id': machine_id } )
            unitStartCommandList = self.cursor.fetchall()
            unitStartCommand = None
            for unitStartCommand in unitStartCommandList:
                pass
            if unitStartCommand is None:
                raise KeyError( '({machine}) unit start コマンドが見つかりません。'.format( machine = str( self.machineInfo ) ) )
            ##########################################################################
            # ユニット開始コマンドの実行
            ##########################################################################
            result = self.doCommand( machine_id, unitStartCommand, { 'unit_name': package['unit_name'], 'unit': package['unit_name'], 'machine_id': machine_id } ) and result
            ##########################################################################
            # ユニット開始後コマンドの取得
            ##########################################################################
            self.cursor.execute( system_sync.commandUnitAfterStartSQL, { 'machine_id': machine_id, 'unit_name': package['unit_name'] } )
            unitAfterStartCommandList = self.cursor.fetchall()
            for unitAfterStartCommand in unitAfterStartCommandList:
                ##########################################################################
                # ユニット開始後コマンドの実行
                ##########################################################################
                result = self.doCommand( machine_id, unitAfterStartCommand, package ) and result
        ##########################################################################
        if package['unit_name'] in ( 'mariadb', 'mysqld' ) and targetMachine['type'].lower() == 'slave' and self.isMaster():
            ##########################################################################
            # データベースのダンプ SQL ファイルの作成
            # dump to system_sync.databaseDumpPath
            ##########################################################################
            result = self.dumpDatabase( machine_id ) and result
            if result:
                result = self.scp( machine_id, system_sync.databaseDumpPath, system_sync.databaseDumpPath )
            ##########################################################################
            # データベースのセットアップ用SQL取得
            ##########################################################################
            setupSqlList = self.getUnitText( machine_id = machine_id, unit = package['unit_name'], is_database_setup = True )
            setupSql = None
            for setupSql in setupSqlList:
                pass
            if setupSql is None:
                raise KeyError( '({machine}) {unit_name} データベースセットアップSQLが見つかりません。'.format( machine = str( self.machineInfo ), unit_name = package['unit_name'] ) )
            result = self.writeToFile( setupSqlList ) and result

            ##########################################################################
            # データベースのセットアップ用SQL実行コマンド取得
            ##########################################################################
            self.cursor.execute( system_sync.slaveSetupDatabaseSQL, { 'unit_name' : package['unit_name'], 'machine_id': machine_id } )
            slaveSetupCommandList = self.cursor.fetchall()
            for slaveSetupCommand in slaveSetupCommandList:
                slaveSetupCommand['allow_error'] = bool( slaveSetupCommand['allow_error'] )
                ##########################################################################
                # SQL ファイル使用コマンドのみ許可
                ##########################################################################
                if '{sql_file}' not in slaveSetupCommand['command']:
                    continue
                if slaveSetupCommand['allow_error']:
                    ##########################################################################
                    # セットアップSQLはエラーを許可
                    ##########################################################################
                    result = self.doCommand( machine_id, slaveSetupCommand, dict( self.config['sql'] ), { 'sql_file': setupSql['path'] } ) and result
                else:
                    ##########################################################################
                    # SQL ダンプ＆スレイブ設定
                    ##########################################################################
                    result = self.doCommand( machine_id, slaveSetupCommand, dict( self.config['sql'] ), { 'sql_file': system_sync.databaseDumpPath } ) and result
        ##########################################################################
        return result
    ##########################################################################
    def getSystemConfigFile( self, machine_id ):
        '''システム設定に関するファイルを取得します。'''
        ##########################################################################
        if type( machine_id ) is not int:
            raise TypeError( 'machine_id({machine_id})が整数ではありません。'.format( machine_id = str( machine_id ) ) )
        elif machine_id < 1:
            raise KeyError( 'machine_id({machine_id})が整数ではありません。'.format( machine_id = str( machine_id ) ) )
        ##########################################################################
        # 全マシン情報の取得
        ##########################################################################
        if not hasattr( self, 'allMachineInfo' ):
            self.getAllMachineInfo()
        elif len( self.allMachineInfo ) < 1:
            self.getAllMachineInfo()
        ##########################################################################
        # 対象マシン情報の取得
        ##########################################################################
        targetMachine = None
        for targetMachine in self.allMachineInfo:
            if targetMachine['id'] == machine_id:
                break
        if targetMachine is None:
            raise KeyError( 'machine_id ({machine_id}) の値が正しくありません。'.format( machine_id = str( machine_id ) ) )
        ##########################################################################
        self.cursor.execute( system_sync.getSystemConfigTextSQL, { 'machine_id': machine_id } )
        textFilesList = self.cursor.fetchall()
        ##########################################################################
        self.cursor.execute( system_sync.getSystemConfigBinarySQL, { 'machine_id': machine_id } )
        binaryFilesList = self.cursor.fetchall()
        ##########################################################################
        filesList = textFilesList + binaryFilesList
        ##########################################################################
        destFileList = []
        if self.isMaster():
            for dataFile in filesList:
                path = pathlib.Path( dataFile['path'] )
                isText = True if dataFile['mime_type'].lower().startswith('text') else False
                if not path.exists():
                    if dataFile['is_complessed']:
                        dataFile['data'] = zlib.decompress( bytes( dataFile['data'] ) ).decode( 'utf-8' )
                        dataFile['is_complessed'] = False
                    destFileList.append( dataFile )
                    continue
                elif dataFile['last_modify'] < datetime.datetime.fromtimestamp( path.stat().st_mtime ):
                    # 設定ファイルが更新されているのでアップロード
                    if isText:
                        self.uploadTextFile( filePath = dataFile['path'], unit = dataFile['unit'], isDatabaseConfig = dataFile['is_database_config'] )
                    else:
                        self.uploadBinaryFile( filePath = dataFile['path'], unit = dataFile['unit'], isDatabaseConfig = dataFile['is_database_config'] )
                    with path.open() as file:
                        dataFile['data'] = file.read()
                        dataFile['is_complessed'] = False
                elif dataFile['is_complessed']:
                    if isText:
                        dataFile['data'] = zlib.decompress( bytes( dataFile['data'] ) ).decode( 'utf-8' )
                    else:
                        dataFile['data'] = zlib.decompress( bytes( dataFile['data'] ) )
                    dataFile['is_complessed'] = False
                destFileList.append( dataFile )
            return destFileList
        else:
            for dataFile in filesList:
                isText = True if dataFile['mime_type'].lower().startswith('text') else False
                if dataFile['is_complessed']:
                    if isText:
                        dataFile['data'] = zlib.decompress( bytes( dataFile['data'] ) ).decode( 'utf-8' )
                    else:
                        dataFile['data'] = zlib.decompress( bytes( dataFile['data'] ) )
                    dataFile['is_complessed'] = False
                destFileList.append( dataFile )
            return destFileList
        ##########################################################################
        return []
    ##########################################################################
    def getUnitText( self, machine_id, unit, is_database_setup = False ):
        '''unit に関するテキストファイルを取得します。'''
        ##########################################################################
        if unit is None:
            return []
        elif type( unit ) is not str:
            raise TypeError( 'unit({unit})が文字列ではありません。'.format( unit = str( unit ) ) )
        elif len( unit ) < 1:
            return []
        ##########################################################################
        if type( machine_id ) is not int:
            raise TypeError( 'machine_id({machine_id})が整数ではありません。'.format( machine_id = str( machine_id ) ) )
        elif machine_id < 1:
            raise KeyError( 'machine_id({machine_id})が整数ではありません。'.format( machine_id = str( machine_id ) ) )
        ##########################################################################
        # 全マシン情報の取得
        ##########################################################################
        if not hasattr( self, 'allMachineInfo' ):
            self.getAllMachineInfo()
        elif len( self.allMachineInfo ) < 1:
            self.getAllMachineInfo()
        ##########################################################################
        # 対象マシン情報の取得
        ##########################################################################
        targetMachine = None
        for targetMachine in self.allMachineInfo:
            if targetMachine['id'] == machine_id:
                break
        if targetMachine is None:
            raise KeyError( 'machine_id ({machine_id}) の値が正しくありません。'.format( machine_id = str( machine_id ) ) )
        ##########################################################################
        if is_database_setup:
            self.cursor.execute( system_sync.getSetupDatabaseTextSQL, { 'unit_name': unit, 'machine_id': machine_id } )
        else:
            self.cursor.execute( system_sync.getUnitTextSQL, { 'unit_name': unit, 'machine_id': machine_id } )

        filesList = self.cursor.fetchall()
        destFileList = []
        if self.isMaster():
            for textFile in filesList:
                path = pathlib.Path( textFile['path'] )
                if not path.exists():
                    if textFile['is_complessed']:
                        textFile['data'] = zlib.decompress( bytes( textFile['data'] ) ).decode( 'utf-8' )
                        textFile['is_complessed'] = False
                    destFileList.append( textFile )
                    continue
                elif textFile['last_modify'] < datetime.datetime.fromtimestamp( path.stat().st_mtime ):
                    # 設定ファイルが更新されているのでアップロード
                    self.uploadTextFile( filePath = textFile['path'], unit = unit, isDatabaseConfig = textFile['is_database_config'] )
                    with path.open() as file:
                        textFile['data'] = file.read()
                        textFile['is_complessed'] = False
                elif textFile['is_complessed']:
                    textFile['data'] = zlib.decompress( bytes( textFile['data'] ) ).decode( 'utf-8' )
                    textFile['is_complessed'] = False
                destFileList.append( textFile )
            return destFileList
        else:
            for textFile in filesList:
                if textFile['is_complessed']:
                    textFile['data'] = zlib.decompress( bytes( textFile['data'] ) ).decode( 'utf-8' )
                    textFile['is_complessed'] = False
                destFileList.append( textFile )
            return destFileList
        ##########################################################################
        return []
    ##########################################################################
    def getUnitBinary( self, machine_id, unit ):
        '''unit に関するバイナリーファイルを取得します。'''
        ##########################################################################
        if unit is None:
            return []
        elif type( unit ) is not str:
            raise TypeError( 'unit({unit})が文字列ではありません。'.format( unit = str( unit ) ) )
        elif len( unit ) < 1:
            return []
        ##########################################################################
        if type( machine_id ) is not int:
            raise TypeError( 'machine_id({machine_id})が整数ではありません。'.format( machine_id = str( machine_id ) ) )
        elif machine_id < 1:
            raise KeyError( 'machine_id({machine_id})が整数ではありません。'.format( machine_id = str( machine_id ) ) )
        ##########################################################################
        # 全マシン情報の取得
        ##########################################################################
        if not hasattr( self, 'allMachineInfo' ):
            self.getAllMachineInfo()
        elif len( self.allMachineInfo ) < 1:
            self.getAllMachineInfo()
        ##########################################################################
        # 対象マシン情報の取得
        ##########################################################################
        targetMachine = None
        for targetMachine in self.allMachineInfo:
            if targetMachine['id'] == machine_id:
                break
        if targetMachine is None:
            raise KeyError( 'machine_id ({machine_id}) の値が正しくありません。'.format( machine_id = str( machine_id ) ) )
        ##########################################################################
        self.cursor.execute( system_sync.getUnitBinarySQL, { 'unit_name': unit, 'machine_id': machine_id } )
        filesList = self.cursor.fetchall()
        destFileList = []
        if self.isMaster():
            for binaryFile in filesList:
                path = pathlib.Path( binaryFile['path'] )
                if not path.exists():
                    if binaryFile['is_complessed']:
                        binaryFile['data'] = zlib.decompress( bytes( binaryFile['data'] ) )
                        binaryFile['is_complessed'] = False
                    destFileList.append( binaryFile )
                    continue
                elif binaryFile['last_modify'] < datetime.datetime.fromtimestamp( path.stat().st_mtime ):
                    # 設定ファイルが更新されているのでアップロード
                    self.uploadBinaryFile( filePath = binaryFile['path'], unit = unit  )
                    with path.open( mode = 'rb' ) as file:
                        binaryFile['data'] = file.read()
                        binaryFile['is_complessed'] = False
                elif binaryFile['is_complessed']:
                    binaryFile['data'] = zlib.decompress( bytes( binaryFile['data'] ) )
                    binaryFile['is_complessed'] = False
                destFileList.append( binaryFile )
            return destFileList
        else:
            for binaryFile in filesList:
                if binaryFile['is_complessed']:
                    binaryFile['data'] = zlib.decompress( bytes( binaryFile['data'] ) )
                    binaryFile['is_complessed'] = False
                destFileList.append( binaryFile )
            return destFileList
        ##########################################################################
        return []
    ##########################################################################
    def writeToFile( self, filesList ):
        '''ファイル情報をファイルに書き出します。'''
        ##########################################################################
        if type( filesList ) is not list:
            raise TypeError( 'filesList({filesList})がリストではありません。'.format( filesList = str( filesList ) ) )
        if len( filesList ) < 1:
            return True
        if type( filesList[0] ) is not dict:
            raise TypeError( 'filesList({filesList})がリストの中身が不正です。'.format( filesList = str( filesList ) ) )
        if 'machine_id' not in filesList[0]:
            raise KeyError( 'filesList({filesList})がリストが正しくありませんありません。'.format( filesList = str( filesList ) ) )
        ##########################################################################
        # 全マシン情報の取得
        ##########################################################################
        if not hasattr( self, 'allMachineInfo' ):
            self.getAllMachineInfo()
        elif len( self.allMachineInfo ) < 1:
            self.getAllMachineInfo()
        ##########################################################################
        result = True
        ##########################################################################
        for dataFile in filesList:
            ##########################################################################
            if 'machine_id' not in dataFile:
                raise KeyError( 'dataFile({dataFile})が正しくありませんありません。'.format( dataFile = str( dataFile ) ) )
            machine_id = dataFile['machine_id']
            ##########################################################################
            if 'mime_type' not in dataFile:
                raise KeyError( 'dataFile({dataFile})が正しくありませんありません。'.format( dataFile = str( dataFile ) ) )
            writeMode = 'w'
            if dataFile['mime_type'].lower().startswith( 'text' ):
                writeMode = 'wt'
            else:
                writeMode = 'wb'
            ##########################################################################
            # 対象マシン情報の取得
            ##########################################################################
            targetMachine = None
            for targetMachine in self.allMachineInfo:
                if targetMachine['id'] == machine_id:
                    break
            if targetMachine is None:
                raise KeyError( 'machine_id ({machine_id}) の値が正しくありません。'.format( machine_id = str( machine_id ) ) )
            ##########################################################################
            securityInstallCommand = None
            if dataFile['type'] == 'security':
                self.cursor.execute( system_sync.securityInstallCommandSQL, { 'os_id': targetMachine['os_id'] } )
                for securityInstallCommand in self.cursor.fetchall():
                    pass
                if securityInstallCommand is None:
                    raise KeyError( '({machine}) セキュリティインストールコマンドが見つかりません。'.format( machine = str( targetMachine ) ) )
            ##########################################################################
            if self.machineInfo['id'] == machine_id:
                path = pathlib.Path( dataFile['path'] )
                if not path.exists():
                    with path.open( mode = writeMode ) as file:
                        file.write( dataFile['data'] )
                    if 'is_database_config' in dataFile and dataFile['is_database_config'] and dataFile['mime_type'].lower().startswith( 'text' ):
                        # MySQL/MariaDB Server setting config-file update
                        result = self.writeDatabaseServerConfig( machine_id = machine_id, databaseServerConfigFile = dataFile['path'], writeDatabaseServerConfigPath = dataFile['path'] ) and result
                elif dataFile['last_modify'] > datetime.datetime.fromtimestamp( path.stat().st_mtime ):
                    path.chmod( dataFile['file_mode'] )
                    os.chown( path, pwd.getpwnam( dataFile['file_owner'] ).pw_uid, grp.getgrnam( dataFile['file_group'] ).gr_gid )
                    with path.open( mode = writeMode ) as file:
                        file.write( dataFile['data'] )
                    if 'is_database_config' in dataFile and dataFile['is_database_config'] and dataFile['mime_type'].lower().startswith( 'text' ):
                        # MySQL/MariaDB Server setting config-file update
                        result = self.writeDatabaseServerConfig( machine_id = machine_id, databaseServerConfigFile = dataFile['path'], writeDatabaseServerConfigPath = dataFile['path'] ) and result
                else:
                    securityInstallCommand = None
                    securityInstallCommandStr = None
                    securityInstallCommandList = None
                ##########################################################################
                if securityInstallCommand is not None:
                    if not self.doCimmand( machine_id, securityInstallCommand, dataFile ):
                        raise OSError( errno.EIO, '({command})セキュリティのインストールに失敗しました。'.format( command = securityInstallCommandStr ) )
                        return False
                ##########################################################################
            elif not self.ping( targetMachine['name'] ):
                raise OSError( errno.EHOSTUNREACH, 'ホスト({host})への接続ができません。'.format( host = targetMachine['name'] ) )
                return False
            else:
                ( fd, pathStr ) = tempfile.mkstemp( text = True )
                pathlib.Path( pathStr ).chmod( dataFile['file_mode'] )
                os.chown( pathStr, pwd.getpwnam( dataFile['file_owner'] ).pw_uid, grp.getgrnam( dataFile['file_group'] ).gr_gid )
                with os.fdopen( fd, mode = writeMode ) as file:
                    file.write( dataFile['data'] )
                if 'is_database_config' in dataFile and dataFile['is_database_config'] and dataFile['mime_type'].lower().startswith( 'text' ):
                    # MySQL/MariaDB Server setting config-file update
                    result = self.writeDatabaseServerConfig( machine_id = machine_id, databaseServerConfigFile = pathStr, writeDatabaseServerConfigPath = dataFile['path'] )
                else:
                    result = self.scp( targetMachine['id'], pathStr, str( dataFile['path'] ) )
                pathlib.Path( pathStr ).unlink()
                if not result:
                    raise OSError( errno.ECONNREFUSED, 'ホスト({host})への転送が失敗しました。'.format( host = targetMachine['name'] ) )
                    return False
                ##########################################################################
                if securityInstallCommand is not None:
                    if not self.doCimmand( machine_id, securityInstallCommand, dataFile ):
                        raise OSError( errno.EREMOTEIO, '({command})セキュリティのインストールに失敗しました。over ssh'.format( command = securityInstallCommandStr ) )
                        return False
                ##########################################################################
            ##########################################################################
        return result
    ##########################################################################
    def scp( self, machine_id, srcPath, destPath ):
        '''ファイルまたはディレクトリーをコピーします。'''
        ##########################################################################
        if not self.isMaster():
            return False
        if type( machine_id ) is not int:
            raise TypeError( 'machine_id({machine_id})が整数ではありません。'.format( machine_id = str( machine_id ) ) )
        elif machine_id < 1:
            raise KeyError( 'machine_id({machine_id})が整数ではありません。'.format( machine_id = str( machine_id ) ) )
        elif type( srcPath ) is not str:
            raise TypeError( 'srcPath({srcPath})が文字列ではありません。'.format( srcPath = str( srcPath ) ) )
        elif len( srcPath ) < 1:
            raise TypeError( 'srcPath({srcPath})が空です。'.format( srcPath = str( srcPath ) ) )
        elif type( destPath ) is not str:
            raise TypeError( 'destPath({destPath})が文字列ではありません。'.format( destPath = str( destPath ) ) )
        elif len( destPath ) < 1:
            raise TypeError( 'destPath({destPath})が空です。'.format( destPath = str( destPath ) ) )
        ##########################################################################
        # 全マシン情報の取得
        ##########################################################################
        if not hasattr( self, 'allMachineInfo' ):
            self.getAllMachineInfo()
        elif len( self.allMachineInfo ) < 1:
            self.getAllMachineInfo()
        ##########################################################################
        # 対象マシン情報の取得
        ##########################################################################
        targetMachine = None
        for targetMachine in self.allMachineInfo:
            if targetMachine['id'] == machine_id:
                break
        if targetMachine is None:
            raise KeyError( 'machine_id ({machine_id}) の値が正しくありません。'.format( machine_id = str( machine_id ) ) )
        ##########################################################################
        self.cursor.execute( system_sync.scpCommandSQL, { 'os_id': self.machineInfo['os_id'] } )
        command = None
        for command in self.cursor.fetchall():
            pass
        if command is None:
            raise KeyError( '({machine}) scp コマンドが見つかりません。'.format( machine = str( self.machineInfo ) ) )
        ##########################################################################
        scpStr = command['command'].format( src = srcPath, user = self.sections['scp']['user'], host = targetMachine['name'], dest = destPath )
        scp = pexpect.spawn( scpStr, encoding='utf-8' )
        while True:
            index = scp.expect( [ system_sync.passwordRegexpStr, system_sync.sshKeyRegExpStr, pexpect.EOF ], timeout = self.sections['expect']['timeout'] )
            if index == 0:
                scp.sendline( self.sections['scp']['password'] )
            elif index == 1:
                scp.sendline( 'yes' )
            elif index == 2:
                scp.close()
                return True if command['allow_error'] else scp.exitstatus == 0
        ##########################################################################
        return False
    ##########################################################################
    def ssh( self, machine_id, commandStr, useLocaclSubprocess=True ):
        '''ssh で対象マシンでコマンドを実行します。'''
        ##########################################################################
        if not self.isMaster():
            return False
        if type( machine_id ) is not int:
            raise TypeError( 'machine_id({machine_id})が整数ではありません。'.format( machine_id = str( machine_id ) ) )
        elif machine_id < 1:
            raise KeyError( 'machine_id({machine_id})が整数ではありません。'.format( machine_id = str( machine_id ) ) )
        elif type( commandStr ) is not str:
            raise TypeError( 'commandStr({commandStr})が文字列ではありません。'.format( commandStr = str( commandStr ) ) )
        elif len( commandStr ) < 1:
            raise TypeError( 'commandStr({commandStr})が空です。'.format( commandStr = str( commandStr ) ) )
        elif type( useLocaclSubprocess ) is not bool:
            raise TypeError( 'useLocaclSubprocess({useLocaclSubprocess})が Boolean ではありません。'.format( useLocaclSubprocess = str( useLocaclSubprocess ) ) )
        ##########################################################################
        # 全マシン情報の取得
        ##########################################################################
        if not hasattr( self, 'allMachineInfo' ):
            self.getAllMachineInfo()
        elif len( self.allMachineInfo ) < 1:
            self.getAllMachineInfo()
        ##########################################################################
        # 対象マシン情報の取得
        ##########################################################################
        targetMachine = None
        for targetMachine in self.allMachineInfo:
            if targetMachine['id'] == machine_id:
                break
        if targetMachine is None:
            raise KeyError( 'machine_id ({machine_id}) の値が正しくありません。'.format( machine_id = str( machine_id ) ) )
        ##########################################################################
        if useLocaclSubprocess is True and machine_id == self.machineInfo['id']:
            return subprocess.run( commandStr, shell = True ).returncode == 0
        ##########################################################################
        self.cursor.execute( system_sync.sshCommandSQL, { 'os_id': self.machineInfo['os_id'] } )
        command = None
        for command in self.cursor.fetchall():
            pass
        if command is None:
            raise KeyError( '({machine}) ssh コマンドが見つかりません。'.format( machine = str( self.machineInfo ) ) )
        ##########################################################################
        sshStr = command['command'].format( user = self.sections['ssh']['user'], host = targetMachine['name'], command = commandStr )
        sshList = sshStr.split( maxsplit = command['maxsplit'] )
        ssh = pexpect.spawn( sshList[0], sshList[1:], encoding='utf-8' )
        while True:
            index = ssh.expect( [ system_sync.passwordRegexpStr, system_sync.sshKeyRegExpStr, pexpect.EOF ], timeout = self.sections['expect']['timeout'] )
            if index == 0:
                ssh.sendline( self.sections['ssh']['password'] )
            elif index == 1:
                ssh.sendline( 'yes' )
            elif index == 2:
                ssh.close()
                return True if command['allow_error'] else ssh.exitstatus == 0
        ##########################################################################
        return False
    ##########################################################################
    def rsync( self, machine_id, pathStr ):
        '''rsync で対象マシンにコマンドを実行します。'''
        ##########################################################################
        if not self.isMaster():
            return False
        if type( machine_id ) is not int:
            raise TypeError( 'machine_id({machine_id})が整数ではありません。'.format( machine_id = str( machine_id ) ) )
        elif machine_id < 1:
            raise KeyError( 'machine_id({machine_id})が整数ではありません。'.format( machine_id = str( machine_id ) ) )
        elif type( pathStr ) is not str:
            raise TypeError( 'pathStr({pathStr})が文字列ではありません。'.format( pathStr = str( pathStr ) ) )
        elif len( pathStr ) < 1:
            raise TypeError( 'pathStr({pathStr})が空です。'.format( pathStr = str( pathStr ) ) )
        elif not pathlib.Path( pathStr ).exists():
            raise KeyError( 'pathStr({pathStr})が存在していません。'.format( pathStr = str( pathStr ) ) )
        ##########################################################################
        # 全マシン情報の取得
        ##########################################################################
        if not hasattr( self, 'allMachineInfo' ):
            self.getAllMachineInfo()
        elif len( self.allMachineInfo ) < 1:
            self.getAllMachineInfo()
        ##########################################################################
        # 対象マシン情報の取得
        ##########################################################################
        targetMachine = None
        for targetMachine in self.allMachineInfo:
            if targetMachine['id'] == machine_id:
                break
        if targetMachine is None:
            raise KeyError( 'machine_id ({machine_id}) の値が正しくありません。'.format( machine_id = str( machine_id ) ) )
        ##########################################################################
        self.cursor.execute( system_sync.rsyncCommandSQL, { 'os_id': self.machineInfo['os_id'] } )
        command = None
        for command in self.cursor.fetchall():
            pass
        if command is None:
            raise KeyError( '({machine}) rsync コマンドが見つかりません。'.format( machine = str( self.machineInfo ) ) )
        ##########################################################################
        rsyncStr = command['command'].format( src = pathStr, user = self.sections['rsync']['user'], host = targetMachine['name'], dest = pathStr )
        rsyncList = rsyncStr.split( maxsplit = command['maxsplit'] )
        rsync = pexpect.spawn( rsyncList[0], rsyncList[1:], encoding='utf-8' )
        while True:
            index = rsync.expect( [ system_sync.passwordRegexpStr, system_sync.sshKeyRegExpStr, pexpect.EOF ], self.sections['expect']['timeout'] )
            if index == 0:
                rsync.sendline( self.sections['rsync']['password'] )
            elif index == 1:
                rsync.sendline( 'yes' )
            elif index == 2:
                rsync.close()
                result = True if command['allow_error'] else rsync.exitstatus == 0
                if result:
                    self.cursor.execute( system_sync.rsyncListSQL, { 'os_id': self.machineInfo['os_id'], 'directory': pathStr } )
                    rsync = None
                    for rsync in self.cursor.fetchall():
                        pass
                    if rsync is None:
                        raise KeyError( '({pathStr}) ({os_id}) rsync 情報が見つかりません。'.format( pathStr = pathStr, os_id = self.machineInfo['os_id'] ) )
                    self.cursor.execute( system_sync.insertRsyncDateSQL,
                        {
                        'rsync_id' : rsync['id'],
                        'machine_id': machine_id,
                        'unit_name': rsync['unit'],
                        'update_term_seconds': rsync['update_term_seconds'],
                        'is_done': result
                        } )
                return result
        ##########################################################################
        return False
    ##########################################################################
    def getOsInfo( self ):
        '''OS 情報を取得します。'''
        ##########################################################################
        if not hasattr( self, 'connector' ):
            self.openConnect()
        ##########################################################################
        if not hasattr( self, 'machineInfo' ):
            self.getMachineInfo()
        ##########################################################################
        self.cursor.execute( system_sync.osInfoSQL, { 'os_id': self.machineInfo['os_id'] } )
        for row in self.cursor.fetchall():
            self.osInfo = row
        return ( self.osInfo )
    ##########################################################################
    def getDomainInfo( self ):
        '''ドメイン情報を取得します。'''
        ##########################################################################
        if not hasattr( self, 'connector' ):
            self.openConnect()
        ##########################################################################
        if not hasattr( self, 'machineInfo' ):
            self.getMachineInfo()
        ##########################################################################
        self.cursor.execute( system_sync.domainInfoSQL, { 'domain_id': self.machineInfo['domain_id'] } )
        for row in self.cursor.fetchall():
            self.domainInfo = row
        return ( self.domainInfo )
    ##########################################################################
    def getInitializeInfo( self ):
        '''初期化情報を取得します。'''
        ##########################################################################
        if not hasattr( self, 'connector' ):
            self.openConnect()
        ##########################################################################
        if not hasattr( self, 'machineInfo' ):
            self.getMachineInfo()
        ##########################################################################
        self.cursor.execute( system_sync.initializeInfoSQL, { 'machine_id': self.machineInfo['id'] } )
        for row in self.cursor.fetchall():
            self.initializeInfo = row
        return ( self.initializeInfo )
    ##########################################################################
    def uploadTextFile( self, filePath, unit = None, isDatabaseConfig = False ):
        '''テキストファイルをアップロードします。'''
        ##########################################################################
        # マスター接続
        ##########################################################################
        if not hasattr( self, 'connector' ):
            self.openConnect( connectType = 'master' )
        else:
            self.openConnectToMaster()
        ##########################################################################
        if not pathlib.Path( filePath ).exists():
            return ( -1 )
        if not pathlib.Path( filePath ).is_file():
            return ( -1 )
        if pathlib.Path( filePath ).is_symlink():
            return ( -1 )
        if pathlib.Path( filePath ).stat().st_size < 1:
            return ( -1 )

        try:
            ##########################################################################
            absPath = pathlib.Path( filePath ).resolve()
            orgData = absPath.read_bytes()
            absPathStr = str( absPath )
            fileMagic = magic.detect_from_filename( absPathStr )
            ##########################################################################
            mime_type = fileMagic.mime_type
            mime_encoding = fileMagic.encoding
            mime_value = fileMagic.name
            ##########################################################################
            type = 'other'
            if not fileMagic.mime_type.lower().startswith('text/'):
                return ( -1 )
            if 'script' in fileMagic.name.lower():
                type = 'script'
            elif absPathStr.endswith( ('.conf', '.cnf', '.ini', '.cfg', '.cf', '.xml' ) ):
                type = 'config'
            elif absPathStr.startswith( '/etc/' ):
                type = 'config'
            elif absPathStr.endswith( ('.sql' ) ):
                type = 'sql'
            elif 'se linux' in mime_value.lower():
                type = 'security'
            else:
                type = 'other'
            ##########################################################################
            file_owner  = pwd.getpwuid( absPath.stat().st_uid ).pw_name
            file_group  = grp.getgrgid( absPath.stat().st_gid ).gr_name
            file_mode   = absPath.stat().st_mode & 0o0777
            ##########################################################################
            # 対象データの圧縮
            ##########################################################################
            compressed_data = zlib.compress( orgData, 9 )
            ##########################################################################
            self.cursor.execute( system_sync.insertTextFileSQL,
                    {
                    'os_id':        self.machineInfo['os_id'],
                    'at_least_versions':    self.osInfo['version'],
                    'type':         type,
                    'unit':         unit,
                    'path':         absPathStr,
                    'data':         compressed_data,
                    'mime_type':        mime_type,
                    'mime_encoding':    mime_encoding,
                    'mime_value':       mime_value,
                    'file_owner':       file_owner,
                    'file_group':       file_group,
                    'file_mode':        file_mode,
                    'is_complessed':    True,
                    'is_database_config':   isDatabaseConfig,
                    'last_modify':      datetime.datetime.fromtimestamp( absPath.stat().st_mtime )
                    }
                )
            self.connector.commit()
            return ( self.cursor.lastrowid )
            ##########################################################################
        except:
            return ( -1 )
        ##########################################################################
        return ( -1 )
    ##########################################################################
    def uploadBinaryFile( self, filePath, unit = None ):
        '''バイナリーファイルをアップロードします。'''
        ##########################################################################
        # マスター接続
        ##########################################################################
        if not hasattr( self, 'connector' ):
            self.openConnect( connectType = 'master' )
        else:
            self.openConnectToMaster()
        ##########################################################################
        if not pathlib.Path( filePath ).exists():
            return ( -1 )
        if not pathlib.Path( filePath ).is_file():
            return ( -1 )
        if pathlib.Path( filePath ).is_symlink():
            return ( -1 )
        if pathlib.Path( filePath ).stat().st_size < 1:
            return ( -1 )

        try:
            ##########################################################################
            absPath = pathlib.Path( filePath ).resolve()
            orgData = absPath.read_bytes()
            absPathStr = str( absPath )
            fileMagic = magic.detect_from_filename( absPathStr )
            ##########################################################################
            mime_type = fileMagic.mime_type
            mime_encoding = fileMagic.encoding
            mime_value = fileMagic.name
            ##########################################################################
            is_compressed = True
            ##########################################################################
            type = 'other'
            if fileMagic.mime_type.lower().startswith('text/'):
                return ( -1 )
            if 'script' in fileMagic.name.lower():
                type = 'script'
            elif absPathStr.endswith( ('.conf', '.cnf', '.ini', '.cfg', 'cf', '.xml' ) ):
                type = 'config'
            elif absPathStr.startswith( '/etc/' ):
                type = 'config'
            elif 'se linux' in mime_value.lower():
                type = 'security'
            elif 'compressed' in mime_value.lower():
                is_compressed = False
                type = 'other'
            else:
                type = 'other'
            ##########################################################################
            file_owner  = pwd.getpwuid( absPath.stat().st_uid ).pw_name
            file_group  = grp.getgrgid( absPath.stat().st_gid ).gr_name
            file_mode   = absPath.stat().st_mode & 0o0777
            ##########################################################################
            if is_compressed:
                ##########################################################################
                # 対象データの圧縮
                ##########################################################################
                compressed_data = zlib.compress( orgData, 9 )
            else:
                compressed_data = orgData
            ##########################################################################
            self.cursor.execute( system_sync.insertBinaryFileSQL,
                    {
                    'os_id':        self.machineInfo['os_id'],
                    'at_least_versions':    self.osInfo['version'],
                    'type':         type,
                    'unit':         unit,
                    'path':         absPathStr,
                    'data':         compressed_data,
                    'mime_type':        mime_type,
                    'mime_encoding':    mime_encoding,
                    'mime_value':       mime_value,
                    'file_owner':       file_owner,
                    'file_group':       file_group,
                    'file_mode':        file_mode,
                    'is_complessed':    is_compressed,
                    'last_modify':      datetime.datetime.fromtimestamp( absPath.stat().st_mtime )
                    }
                )
            self.connector.commit()
            return ( self.cursor.lastrowid )
            ##########################################################################
        except:
            return ( -1 )
        ##########################################################################
        return ( -1 )
    ##########################################################################
    def downloadTextFiles( self ):
        '''全てのテキストファイルデータを取得します。'''
        ##########################################################################
        if not hasattr( self, 'connector' ):
            self.openConnect()
        ##########################################################################
        if not hasattr( self, 'machineInfo' ):
            self.getMachineInfo()
        ##########################################################################
        self.cursor.execute( system_sync.getTextFilesSQL, { 'os_id': self.machineInfo['os_id'] } )
        ##########################################################################
        rows = []
        for row in self.cursor.fetchall():
            if row['is_complessed']:
                ##########################################################################
                # 対象データの解凍
                ##########################################################################
                row['data'] = zlib.decompress( bytes( row['data'] ) ).decode()
            else:
                ##########################################################################
                # 対象データのデコード（文字列化）
                ##########################################################################
                row['data'] = row['data'].decode()
            rows.append( row )
        return ( rows )
    ##########################################################################
    def downloadBinaryFiles( self ):
        '''全てのバイナリーファイルデータを取得します。'''
        ##########################################################################
        if not hasattr( self, 'connector' ):
            self.openConnect()
        ##########################################################################
        if not hasattr( self, 'machineInfo' ):
            self.getMachineInfo()
        ##########################################################################
        self.cursor.execute( system_sync.getBinaryFilesSQL, { 'os_id': self.machineInfo['os_id'] } )
        ##########################################################################
        rows = []
        for row in self.cursor.fetchall():
            if row['is_complessed']:
                ##########################################################################
                # 対象データの解凍
                ##########################################################################
                row['data'] = zlib.decompress( row['data'] )
            rows.append( row )
        return ( rows )
    ##########################################################################
    def getUnitNames( self ):
        '''全てのバイナリーファイルデータを取得します。'''
        ##########################################################################
        if not hasattr( self, 'connector' ):
            self.openConnect()
        ##########################################################################
        if not hasattr( self, 'machineInfo' ):
            self.getMachineInfo()
        ##########################################################################
        self.cursor.execute( system_sync.getUnitNameSQL, { 'os_id': self.machineInfo['os_id'] } )
        ##########################################################################
        rows = []
        for row in self.cursor.fetchall():
            rows.append( row['unit_name'] )
        return ( rows )
    ##########################################################################
##########################################################################
__all__ = [ 'system_sync' ]
