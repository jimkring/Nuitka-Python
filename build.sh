#!/bin/bash

set -e
set -x

# Install Debian dependencies.
# TODO: Support Fedora/CentOS/etc. as well.
sudo apt-get install -y build-essential checkinstall libreadline-gplv2-dev libncursesw5-dev libssl-dev libsqlite3-dev tk-dev libgdbm-dev libc6-dev libbz2-dev

# Have this as a standard path. We are not yet relocatable, but that will come hopefully.
target=/opt/nuitka-python27

# These tests are flaky and cause hangs with PGO.
rm -f Lib/test/test_ftplib.py
rm -f Lib/test/test_poplib.py
rm -f Lib/test/test_smtplib.py
rm -f Lib/test/test_ssl.py

# The UCS4 has best compatibility with wheels on PyPI it seems.
./configure --prefix=$target --disable-shared --enable-ipv6 --enable-unicode=ucs4 \
  --enable-optimizations --with-computed-gotos --with-fpectl \
  CC=gcc CFLAGS="-g" LDFLAGS="-g -Xlinker -export-dynamic -rdynamic -Wl,-z,relro" && make LDFLAGS="-g -Xlinker -export-dynamic -rdynamic"

# Delayed installation, to avoid having it not there for testing purposes
# while compiling, which is slow due to PGO.
sudo rm -rf $target && sudo make install

# Make sure to have pip installed, might even remove it afterwards, Debian
# e.g. doesn't include it.
sudo $target/bin/python -m ensurepip
