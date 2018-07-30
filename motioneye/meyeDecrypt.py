#!/usr/bin/env python

from nacl import encoding, public, pwhash, secret, utils

import argparse
import os
import re
import sys
import getpass

parser = argparse.ArgumentParser()
parser.add_argument("-k", metavar="/path/to/private.key", help="Private key to use")
parser.add_argument("--directory", metavar="/path/to/mediafiles.mp4.crypt", help="Decrypt all files ending with .crypt in this directory")
parser.add_argument("--file", metavar="/path/to/mediafile.mp4.crypt", help="Decrypt only the specified file")


kdf = pwhash.argon2i.kdf
ops = pwhash.argon2i.OPSLIMIT_SENSITIVE

def decrypt_key(private_key):
    password = getpass.getpass()

    with open (private_key, 'r') as in_file:
        salt = in_file.read(16)
        in_file.seek(16)
        encrypted = in_file.read(72)
        in_file.seek(88)
        mem = int(in_file.read())

    key = kdf(secret.SecretBox.KEY_SIZE, password, salt,
               opslimit=ops, memlimit=mem)
    box = secret.SecretBox(key)

    loaded_private_key = box.decrypt(encrypted)

    loaded_private_key = public.PrivateKey(loaded_private_key, encoder=encoding.RawEncoder)

    return loaded_private_key


def decrypt_files_in_dir(loaded_private_key, directory):
    for file in os.listdir(directory):
        if file.endswith(".crypt"):
            try:
                file = os.path.join(os.path.abspath(directory), file)

                outfile = re.sub('\.crypt$', '', file)

                with open(file, 'rb') as in_file:
                    data = in_file.read()

                    box = public.SealedBox(loaded_private_key)

                    decrypted = box.decrypt(data)

                    with open(outfile, 'wb') as out_file:
                        out_file.write(decrypted)

                        print ("Decrypted {0} to {1}".format(file, outfile))
            except:
                print ("Failed to decrypt {0}".format(file))

def decrypt_file(loaded_private_key, file):
    if file.endswith(".crypt"):

        file = os.path.abspath(file)

        outfile = re.sub('\.crypt$', '', file)

        with open(file, 'rb') as in_file:
            data = in_file.read()

        box = public.SealedBox(loaded_private_key)

        decrypted = box.decrypt(data)

        with open(outfile, 'wb') as out_file:
            out_file.write(decrypted)

        print ("Decrypted {0} to {1}".format(file, outfile))

if __name__ == "__main__":
    args = parser.parse_args()

    loaded_private_key = decrypt_key(args.k)

    if args.directory:
        decrypt_files_in_dir(loaded_private_key, args.directory)

    if args.file:
        decrypt_file(loaded_private_key, args.file)
