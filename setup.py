
import os.path

from codecs import open
from setuptools import setup

import motioneye


here = os.path.abspath(os.path.dirname(__file__))
name = 'motioneye'
version = motioneye.VERSION

with open(os.path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()


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
            'templates/*'
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
    }
)
