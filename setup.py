
# Always prefer setuptools over distutils
from setuptools import setup
# To use a consistent encoding
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='motioneye',

    version='0.25.2',

    description='motionEye server',
    long_description=long_description,

    url='https://bitbucket.org/ccrisan/motioneye/',

    author='Calin Crisan',
    author_email='ccrisan@gmail.com',

    license='GPLv3',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 3 - Beta',

        'Intended Audience :: End Users/Desktop',
        'Topic :: Multimedia :: Video',

        'License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)',

        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7'
    ],

    keywords='motion video surveillance frontend',

    packages=['motioneye'],

    install_requires=['tornado>=3.1', 'jinja2', 'pillow', 'pycurl'],

    package_data={
        'motioneye': [
            'static/*',
            'static/*/*',
            'templates/*'
        ]
    },

    data_files=[],

    entry_points={
        'console_scripts': [
            'motioneye=motioneye.motioneye:main',
        ],
    },
)

