#!/bin/bash

target=/opt/nuitka-python27

sudo cp Lib/pip.py $target/lib/python2.7/
sudo cp Lib/__np__/*.py $target/lib/python2.7/__np__


