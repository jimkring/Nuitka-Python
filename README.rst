This is Nuitka-Python
=====================

This is a fork of CPython, that is called Nuitka-Python, and diverges in various
ways from the original.

Our immediate goals are:

[x] Windows: Add static linking (performance and lock down)
[x] Windows: Reenable Windows 7 support (because why not)
[x] LTO linking on Windows and Linux (performance and deployment size)
[x] Automatic patches for packages built from pip
[ ] Support all major packages and provide upstream guidance.

Installation
============

Currently, you have to build Nuitka-Python from source code. It is questionable
if deploying binaries makes sense, as you will have to compile from source code
everything else that is installed afterwards, and the ``python.exe`` will be
self-modifying with pip installs.

Use the following command in the root of a Nuitka-Python repository checkout:

.. code:: sh

    build.bat -x64

This produces a portable Python installation in the ``output`` folder. It has a
``pip`` and ``setuptools``, but not ``wheel`` out of the box. Nuitka-Python
supports these all of these though, with differences to standard CPython that
make it essentially always compile from source. Esp. the architecture of
Nuitka-Python will be different, so binary wheels uploaded to PyPI cannot be
installed, which will make it fallback to compiling from source.

The ``output`` folder can be moved freely, even to other machines. When you
install via ``python.exe -m pip`` however, it will be self-modifying the
``python.exe`` to include the newly installed packages with static linking.

Developer Information
=====================

This is for users, who want to contribute a package patch. Right now,
this is a scratchpad of commands used to do that.

.. code:: sh

    # Tool to do the download, so far it didn't matter which python
    # we are using for these commands, I was doing it for 2.7 with
    # no issue for numpy. The tool may not support it anymore though.
    python3.9 -m pip install pip-download

    # Important to use "--no-binary=:all:" as we do not want wheels,
    # but source code. Nuitka-Python doesn't yet enforce this, but
    # it might one day. Notice, that "--no-deps" seems to not avoid
    # installation of the requirements.
    python3.9 -m pip download --no-binary=:all: --no-deps numpy==1.16.1

    # apt-get install atool if need be
    atool -x numpy-1.16.1.zip

    # Now enter, and immediately put everything under git control, we
    # of course have to ignore .gitignore files, therefore "-f" when
    # adding things. This git repo will not be long lived though, we
    # will only create a patch out of it.
    cd numpy-1.16.1
    git init -b nuitka-python && git add -f . && git commit -m "Upstream Source"

    # If there is a pre-existing patch, apply it. The patch name should
    # follow some consistency, but currently does not.
    patch -p1 <../../repos/Nuitka-Python-packages/packages/np27-linux/numpy/numpy-static-patch.patch

    # Now edit, make sure to only have one commit, amend or rebase if necessary against --root
    # and squash all commits into one.
    git commit -m "Nuitka-Python changes to allow static linking." -a

    git format-patch HEAD^ --stdout >../../repos/Nuitka-Python-packages/packages/np27-linux/numpy/numpy-static-patch.patch

Copyright and License Information
---------------------------------

Copyright (c) 2021 Nuitka Organsisation contributors. All rights reserved.

Copyright (c) 2001-2021 Python Software Foundation.  All rights reserved.

Copyright (c) 2000 BeOpen.com.  All rights reserved.

Copyright (c) 1995-2001 Corporation for National Research Initiatives.  All
rights reserved.

Copyright (c) 1991-1995 Stichting Mathematisch Centrum.  All rights reserved.

See the file "LICENSE" for information on the history of this software, terms &
conditions for usage, and a DISCLAIMER OF ALL WARRANTIES.

This Python distribution contains *no* GNU General Public License (GPL) code,
so it may be used in proprietary projects.  There are interfaces to some GNU
code but these are entirely optional.

All trademarks referenced herein are property of their respective holders.
