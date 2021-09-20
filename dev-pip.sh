#!/bin/bash

target=/opt/nuitka-python27

3to2 -f annotations -w --no-diffs Lib/pip.py
3to2 -f annotations -w --no-diffs Lib/__np__.py

sudo cp Lib/pip.py Lib/__np__.py $target/lib/

# mv Lib/pip.py.bak Lib/pip.py
mv Lib/__np__.py.bak Lib/__np__.py

