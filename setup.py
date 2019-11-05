#!/usr/bin/env python
# Author: Girardon <ggirardon@gmail.com>
# Last Change: Nov 05, 2019

"""
Setup script for the `perf_moon` package.

**python setup.py install**
  Install from the working directory into the current Python environment.

**python setup.py sdist**
  Build a source distribution archive.

**python setup.py bdist_wheel**
  Build a wheel distribution archive.
"""

import codecs
import os
import re

from setuptools import find_packages, setup


def get_contents(*args):
    with codecs.open(get_absolute_path(*args), 'r', 'UTF-8') as handle:
        return handle.read()


def get_version(*args):
    contents = get_contents(*args)
    metadata = dict(re.findall('__([a-z]+)__ = [\'"]([^\'"]+)', contents))
    return metadata['version']


def get_requirements(*args):
    requirements = set()
    with open(get_absolute_path(*args)) as handle:
        for line in handle:
            line = re.sub(r'^#.*|\s#.*', '', line)
            if line and not line.isspace():
                requirements.add(re.sub(r'\s+', '', line))
    return sorted(requirements)


def get_absolute_path(*args):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), *args)


setup(
    name='perf-moon',
    version=get_version('perf_moon', '__init__.py'),
    description="Monitor and control Apache web server workers from Python",
    long_description=get_contents('README.rst'),
    url='https://perf-moon.readthedocs.io',
    author="Peter Odding",
    author_email='peter@peterodding.com',
    license='MIT',
    packages=find_packages(),
    test_suite='perf_moon.tests',
    install_requires=get_requirements('requirements.txt'),
    tests_require=get_requirements('requirements-tests.txt'),
    entry_points=dict(console_scripts=[
        'perf-moon = perf_moon.cli:main',
    ]),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Internet :: WWW/HTTP :: HTTP Servers',
        'Topic :: Software Development',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Systems Administration',
        'Topic :: Terminals',
        'Topic :: Utilities',
    ])
