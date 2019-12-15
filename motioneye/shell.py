
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

import code
import logging


def parse_options(parser, args):
    return parser.parse_args(args)


def main(parser, args):
    from motioneye import meyectl
    
    options = parse_options(parser, args)
    
    meyectl.configure_logging('shell', options.log_to_file)
    meyectl.configure_tornado()

    logging.debug('hello!')
    
    code.interact(local=locals())

    logging.debug('bye!')
