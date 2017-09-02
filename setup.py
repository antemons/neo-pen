#!/usr/bin/env python

from setuptools import setup

setup(
    name='neopen',
    version='0.1',
    description='Download the digital ink from a Neo spartpen N2',
    author='Daniel Vorberg',
    author_email='dv@pks.mpg.de',
    packages=['neopen'],
    package_dir={'neopen': 'neopen'},
    #url='https://github.com/',
    entry_points={
      'console_scripts': [
          'neo-pen = neopen.__main__:main'
      ]
    },   
    install_requires=[
        'cairocffi',
        ],
    zip_safe=True,
    long_description=""" """)
