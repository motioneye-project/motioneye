#!/usr/bin/env python
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

from nacl import encoding, public, pwhash, secret, utils
import argparse
import datetime
import getpass
import os
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--memlimit", type=int, metavar="int", help="Maximum amount of memory in bytes to use for key decryption")
parser.add_argument("--directory", metavar="/etc/motioneye", help="Directory to write keys to; Public key must be present in the motioneye config directory for encryption to work")

used_encoder = encoding.RawEncoder

kdf = pwhash.argon2i.kdf
salt = utils.random(pwhash.argon2i.SALTBYTES)
ops = pwhash.argon2i.OPSLIMIT_SENSITIVE

def encrypt_key(mem, key):
    password = getpass.getpass()

    derivated_password = kdf(secret.SecretBox.KEY_SIZE, password, salt, opslimit=ops, memlimit=mem)

    secret_box = secret.SecretBox(derivated_password)
    encrypted_private_key = secret_box.encrypt(key)
    return encrypted_private_key

def write_private_key(outfile, salt, encrypted_key, mem):
    with open(outfile, 'wb') as out_file:
        out_file.write(salt)
        out_file.write(encrypted_key)
        out_file.write(str(mem))

def write_public_key(outfile, public_key):
    with open(outfile, 'wb') as out_file:
        out_file.write(public_key)

def backup_key_files(private_key_location, public_key_location):
    now = datetime.datetime.now()
    now = now.strftime("_%Y-%m-%d_%H_%M_%S")
    backup_private_key_location = os.path.join(private_key_location + now)
    backup_public_key_location = os.path.join(public_key_location + now)

    if os.path.isfile(private_key_location):
        os.rename(private_key_location, backup_private_key_location)
        print ("Existing private key {0} was backuped to {1}".format(private_key_location, backup_private_key_location))

    if os.path.isfile(public_key_location):
        os.rename(public_key_location, backup_public_key_location)
        print ("Existing public key {0} was backuped to {1}".format(public_key_location, backup_public_key_location))


def generate_key_pair(mem, private_key_location, public_key_location):
    backup_key_files(private_key_location, public_key_location)

    private_key = public.PrivateKey.generate()

    encoded_private_key = private_key.encode(encoder=used_encoder)
    encoded_public_key = private_key.public_key.encode(encoder=used_encoder)

    encrypted_private_key = encrypt_key(mem, encoded_private_key)

    write_private_key(private_key_location, salt, encrypted_private_key, mem)
    write_public_key(public_key_location, encoded_public_key)

    print('IMPORTANT: Backup the newly generated private key at {0} immediately. If you lose it, you will not be able to decrypt your files.'.format(private_key_location))

def main():
    args = parser.parse_args()
    if args.memlimit:
        if args.memlimit >= 8192:
            mem = args.memlimit
            print ("Using custom memory limit of {0}".format(mem))
        else:
            sys.exit("ERROR: memlimit must be at least 8192 bytes")
    else:
        mem = pwhash.argon2i.MEMLIMIT_SENSITIVE
        print ("Using default memory limit of {0}".format(mem))

    if args.directory:
        if os.path.exists(args.directory):
            directory = args.directory
            print ("Using specified directory {0} as output directory".format(directory))
        else:
            sys.exit("ERROR: Specified output directory {0} does not exist".format(args.directory))
    else:
        directory = os.getcwd()
        print ("No output directory specified. Using current directory {0} as output directory.".format(directory))

    public_key_location = os.path.join(directory, 'public.key')
    private_key_location = os.path.join(directory, 'private.key')

    generate_key_pair(mem, private_key_location, public_key_location)

if __name__ == "__main__":
    main()
