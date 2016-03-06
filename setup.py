
import os.path

from codecs import open
from setuptools import setup
from setuptools.command.sdist import sdist

import motioneye


here = os.path.abspath(os.path.dirname(__file__))
name = 'motioneye'
version = motioneye.VERSION

with open(os.path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()


class SdistCommand(sdist):
    def make_release_tree(self, base_dir, files):
        sdist.make_release_tree(self, base_dir, files)
        self.apply_patches(base_dir)
        
    def apply_patches(self, base_dir):
        dropbox_keys_file = os.path.join(os.getcwd(), base_dir, 'extra', 'dropbox.keys')
        if os.path.exists(dropbox_keys_file):
            g = {}
            execfile(dropbox_keys_file, g)
            upload_services_file = os.path.join(os.getcwd(), base_dir, 'motioneye', 'uploadservices.py')
            if os.system("sed -i 's/dropbox_client_id_placeholder/%s/' %s" % (g['CLIENT_ID'], upload_services_file)):
                raise Exception('failed to patch uploadservices.py')
            if os.system("sed -i 's/dropbox_client_secret_placeholder/%s/' %s" % (g['CLIENT_SECRET'], upload_services_file)):
                raise Exception('failed to patch uploadservices.py')


setup(
    name=name,
    version=version,

    description='motionEye server',
    long_description=long_description,

    url='https://github.com/ccrisan/motioneye/',

    author='Calin Crisan',
    author_email='ccrisan@gmail.com',

    license='GPLv3',

    classifiers=[
        'Development Status :: 4 - Beta',

        'Intended Audience :: End Users/Desktop',
        'Topic :: Multimedia :: Video',

        'License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)',

        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7'
    ],

    keywords='motion video surveillance frontend',

    packages=['motioneye'],

    install_requires=['tornado>=3.1', 'jinja2', 'pillow', 'pycurl'],

    package_data={
        'motioneye': [
            'static/*.*',
            'static/*/*',
            'templates/*',
            'scripts/*'
        ]
    },

    data_files=[
        (os.path.join('share/%s' % name, root), [os.path.join(root, f) for f in files])
                for (root, dirs, files) in os.walk('extra')
    ],

    entry_points={
        'console_scripts': [
            'meyectl=motioneye.meyectl:main',
        ],
    },
    
    cmdclass={
        'sdist': SdistCommand
    }
)
