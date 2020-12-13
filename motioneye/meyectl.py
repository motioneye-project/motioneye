#!/usr/bin/env python3
# coding: utf-8

# Copyright (c) 2013 Calin Crisan
# This file is part of motionEye.
#
# motionEye is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import logging
import os.path
import pipes
import sys
import locale
import gettext

# ŝarĝante tradukojn
locale.setlocale(locale.LC_ALL, '')
lingvo = 'eo'
traduction = None
pathname=os.path.dirname(__file__)
try:
  gettext.find('motioneye',pathname+'/locale')
  traduction = gettext.translation('motioneye',pathname+'/locale')
  traduction.install();
except:
  traduction = gettext
  gettext.install('motioneye')

file = gettext.find('motioneye', pathname+'/locale')
if file:
  lgrpath = len(pathname)
  lingvo = file[lgrpath+8:lgrpath+10]
else:
  lingvo = 'eo'
#logging.info(_('lingvo : ') + lingvo)
    
# make sure motioneye is on python path
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motioneye import settings

_LOG_FILE = 'motioneye.log'


def find_command(command):
    if command == 'relayevent':
        relayevent_sh = os.path.join(os.path.dirname(__file__), 'scripts/relayevent.sh')

        cmd = relayevent_sh + ' "%s"' % (settings.config_file or '')

    else:
        cmd = __file__
        cmd = sys.executable + ' ' + cmd
        cmd = cmd.replace('-b', '')  # remove server-specific options
        cmd += ' %s ' % command
        cmd += ' '.join([pipes.quote(arg) for arg in sys.argv[2:]
                         if arg not in ['-b']])

    return cmd


def load_settings():
    # parse common command line arguments

    config_file = None
    debug = False

    for i in range(1, len(sys.argv)):
        arg = sys.argv[i]
        next_arg = i < len(sys.argv) - 1 and sys.argv[i + 1]
        if arg == '-c':
            config_file = next_arg

        elif arg == '-d':
            debug = True

    conf_path_given = [False]
    run_path_given = [False]
    log_path_given = [False]
    media_path_given = [False]

    # parse the config file, if given

    def parse_conf_line(line):
        line = line.strip()
        if not line or line.startswith('#'):
            return

        parts = line.split(' ', 1)
        if len(parts) != 2:
            raise Exception('invalid configuration line: %s' % line)

        name, value = parts
        upper_name = name.upper().replace('-', '_')

        if hasattr(settings, upper_name):
            curr_value = getattr(settings, upper_name)

            if upper_name == 'LOG_LEVEL':
                if value == 'quiet':
                    value = 100

                else:
                    value = getattr(logging, value.upper(), logging.DEBUG)

            elif value.lower() == 'true':
                value = True

            elif value.lower() == 'false':
                value = False

            elif isinstance(curr_value, int):
                value = int(value)

            elif isinstance(curr_value, float):
                value = float(value)

            if upper_name == 'CONF_PATH':
                conf_path_given[0] = True

            elif upper_name == 'RUN_PATH':
                run_path_given[0] = True

            elif upper_name == 'LOG_PATH':
                log_path_given[0] = True

            elif upper_name == 'MEDIA_PATH':
                media_path_given[0] = True

            setattr(settings, upper_name, value)

        else:
            logging.warning('unknown configuration option: %s' % name)

    if config_file:
        try:
            with open(config_file) as f:
                for line in f:
                    parse_conf_line(line)

        except Exception as e:
            logging.fatal('failed to read settings from "%s": %s' % (config_file, e))
            sys.exit(-1)

        # use the config file directory as base dir
        # if not specified otherwise in the config file
        base_dir = os.path.dirname(config_file)
        settings.config_file = config_file

        if not conf_path_given[0]:
            settings.CONF_PATH = base_dir

        if not run_path_given[0]:
            settings.RUN_PATH = base_dir

        if not log_path_given[0]:
            settings.LOG_PATH = base_dir

        if not media_path_given[0]:
            settings.MEDIA_PATH = base_dir

    else:
        logging.info('no configuration file given, using built-in defaults')

    if debug:
        settings.LOG_LEVEL = logging.DEBUG


def configure_logging(cmd, log_to_file=False):
    sys.stderr.write('configure_logging cmd %s: %s\n' % (cmd,log_to_file))
    if log_to_file or cmd != 'motioneye':
        fmt = '%(asctime)s: [{cmd}] %(levelname)8s: %(message)s'.format(cmd=cmd)

    else:
        fmt = '%(levelname)8s: %(message)s'.format(cmd=cmd)

    for h in logging.getLogger().handlers:
        logging.getLogger().removeHandler(h)

    try:
        if log_to_file:
            log_file = os.path.join(settings.LOG_PATH, _LOG_FILE)

        else:
            log_file = None

        sys.stderr.write('configure logging to file: %s\n' % log_file)
        logging.basicConfig(filename=log_file, level=settings.LOG_LEVEL,
                            format=fmt, datefmt='%Y-%m-%d %H:%M:%S')

    except Exception as e:
        sys.stderr.write('failed to configure logging: %s\n' % e)
        sys.exit(-1)

    logging.getLogger('tornado').setLevel(logging.WARN)
    logging.getLogger('oauth2client').setLevel(logging.WARN)


def configure_tornado():
    from tornado.httpclient import AsyncHTTPClient

    AsyncHTTPClient.configure('tornado.curl_httpclient.CurlAsyncHTTPClient', max_clients=16)


def make_arg_parser(command=None):
    if command:
        usage = description = epilog = None

    else:
        usage = '%(prog)s [command] [-c CONFIG_FILE] [-d] [-h] [-l] [-v] [command options...]\n\n'

        description = 'available commands:\n'
        description += '  startserver\n'
        description += '  stopserver\n'
        description += '  sendmail\n'
        description += '  sendtelegram\n'
        description += '  webhook\n'
        description += '  shell\n\n'

        epilog = 'type "%(prog)s [command] -h" for help on a specific command\n\n'

    parser = argparse.ArgumentParser(prog='meyectl%s' % ((' ' + command) if command else ''), usage=usage,
                                     description=description, epilog=epilog, add_help=False,
                                     formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('-c', help='use a config file instead of built-in defaults', type=str, dest='config_file')
    parser.add_argument('-d', help='enable debugging, overriding log level from config file', action='store_true',
                        dest='debug')
    parser.add_argument('-h', help='print this help and exit', action='help', default=argparse.SUPPRESS)
    parser.add_argument('-l', help='log to file instead of standard error', action='store_true', dest='log_to_file')
    parser.add_argument('-v', help='print program version and exit', action='version', default=argparse.SUPPRESS)

    return parser


def print_usage_and_exit(code):
    parser = make_arg_parser()
    parser.print_help(sys.stderr)

    sys.exit(code)


def print_version_and_exit():
    import motioneye

    sys.stderr.write('motionEye %s\n' % motioneye.VERSION)
    sys.exit()


def main():
    for a in sys.argv:
        if a == '-v':
            print_version_and_exit()

    if len(sys.argv) < 2 or sys.argv[1] == '-h':
        print_usage_and_exit(0)

    load_settings()

    command = sys.argv[1]
    arg_parser = make_arg_parser(command)

    if command in ('startserver', 'stopserver'):
        from motioneye import server
        server.main(arg_parser, sys.argv[2:], command[:-6])

    elif command == 'sendmail':
        from motioneye import sendmail
        sendmail.main(arg_parser, sys.argv[2:])
    elif command == 'sendtelegram':
        from motioneye import sendtelegram
        sendtelegram.main(arg_parser, sys.argv[2:])
    elif command == 'webhook':
        from motioneye import webhook
        webhook.main(arg_parser, sys.argv[2:])

    elif command == 'shell':
        from motioneye import shell
        shell.main(arg_parser, sys.argv[2:])

    else:
        sys.stderr.write('unknown command "%s"\n\n' % command)
        print_usage_and_exit(-1)


if __name__ == '__main__':
    main()
