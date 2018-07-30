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

from nacl import encoding, public

import config
import logging
import os
import re
import settings

public_key_location = os.path.join(settings.CONF_PATH, 'public.key')
private_key_location = os.path.join(settings.CONF_PATH, 'private.key')
used_encoder = encoding.RawEncoder

def read_public_key(public_key_location):
    with open(public_key_location, 'rb') as key_file:
            public_key = key_file.read()
    return public.PublicKey(public_key, encoder=used_encoder)

def read_media_file(infile):
    with open(infile, 'rb') as in_file:
        data = in_file.read()
        outfile = re.sub(r'(\.[a-zA-Z0-9]*$)', r'\1.crypt', infile)
    return data, outfile

def write_file(outfile, data):
    with open(outfile, 'wb') as out_file:
        out_file.write(data)
    return outfile

def sealed_box(public_key, data):
    box = public.SealedBox(public_key)
    return box.encrypt(data)

def remove_source_file(input_file, camera_id):
    camera_config = config.get_camera(camera_id)
    if camera_config['@cloud_encryption_remove_unencrypted']:
        logging.debug('Deleting unencrypted source file {0}'.format(input_file))
        os.remove(input_file)

def encrypt(input_file, camera_id):
    try:
        data, outfile = read_media_file(input_file)
        public_key = read_public_key(public_key_location)
        encrypted = sealed_box(public_key, data)
        outfile = write_file(outfile, encrypted)
        logging.debug('Successfully encrypted {0} to {1}'.format(input_file, outfile))
        remove_source_file(input_file, camera_id)
        return outfile
    except:
        camera_config = config.get_camera(camera_id)
        if camera_config['@cloud_encryption_upload_fails']:
            logging.error('Encryption of file {0} failed. Uploading unencrypted file'.format(input_file))
            return input_file
        else:
            logging.error('Encryption of file {0} failed. Not uploading unencrypted file'.format(input_file))
            return None
