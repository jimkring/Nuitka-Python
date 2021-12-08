from __future__ import print_function

import io
import sys
import os
import pkgutil
import shutil
import subprocess
import distutils
import distutils.ccompiler
import modulefinder
from distutils.sysconfig import get_config_var
import sysconfig
import json
import tempfile
import ctypes
import copy
import fnmatch

MOVEFILE_DELAY_UNTIL_REBOOT = 4

def find_files(directory, pattern):
    for root, dirs, files in os.walk(directory):
        for basename in files:
            if fnmatch.fnmatch(basename, pattern):
                filename = os.path.join(root, basename)
                yield filename

def run_rebuild():
    initial_sys_path = copy.deepcopy(sys.path)

    installDir = os.path.dirname(sys.executable)

    foundLibs = {}

    compiler = distutils.ccompiler.new_compiler(verbose=5)
    #compiler.initialize()

    checkedLibs = set()

    # Scan sys.path for any more lingering static libs.
    for path in reversed(sys.path):
        if path == installDir:
            continue
        for file in find_files(path, '*.a'):
            if file in checkedLibs:
                continue

            _, filename = os.path.split(file)

            if not filename.startswith("lib") or file.endswith(sysconfig.get_config_var("LIBRARY")):
                continue
            checkedLibs.add(file)
            functions = [x.decode('ascii').split(' ')[-1] for x in
                             subprocess.check_output(['nm', file]).split(os.linesep.encode('ascii'))]
            initFunctions = [x for x in functions if x.startswith('init')]

            # If this lib has a PyInit function, we should link it in.
            if initFunctions:
                relativePath = os.path.relpath(file, path)
                if 'site-packages' in relativePath:
                    continue
                relativePath = relativePath.replace('.a', '')
                dirpath, filename = os.path.split(relativePath)
                filename = filename[3:]
                relativePath = dirpath.replace('\\', '.').replace('/', '.') + '.' + filename
                print(relativePath, file)
                foundLibs[relativePath] = file

    print('Scanning for any additional libs to link...')

    # Start with the libs needed for a base interpreter.
    linkLibs = ['m']  #['advapi32', 'shell32', 'ole32', 'oleaut32', 'kernel32', 'user32', 'gdi32', 'winspool', 'comdlg32', 'uuid', 'odbc32', 'odbccp32', 'shlwapi', 'ws2_32', 'version', 'libssl', 'libcrypto', 'tcl86t', 'tk86t', 'Crypt32', 'Iphlpapi', 'msi', 'Rpcrt4', 'Cabinet', 'winmm']

    library_dirs = [sysconfig.get_config_var('prefix'), sysconfig.get_config_var('LIBDEST')]

    # Scrape all available libs from the libs directory. We will let the linker worry about filtering out extra symbols.
    for file in find_files(sysconfig.get_config_var('LIBDEST'), '*.a'):
        linkLibs.append(file)

    for name, path in foundLibs.items():
        linkLibs += [path]

        if os.path.isfile(path + '.link.json'):
            with open(path + '.link.json', 'r') as f:
                linkData = json.load(f)
                print(linkData)
                linkLibs += linkData['libraries']
                library_dirs += [os.path.join(os.path.dirname(path), x) for x in linkData['library_dirs']]

    linkLibs = list(set(linkLibs))
    library_dirs = list(set(library_dirs))

    print("Generating interpreter sources...")

    staticinitheader = """/* Minimal main program -- everything is loaded from the library */

#include "Python.h"

#ifdef __FreeBSD__
#include <fenv.h>
#endif

"""

    for key, value in foundLibs.items():
        functions = [x.decode('ascii').split(' ')[-1] for x in
                     subprocess.check_output(['nm', value]).split(os.linesep.encode('ascii'))]
        initFunctions = [x for x in functions if x.startswith('init')]
        if not initFunctions:
            print("Init not found!", key, value)
            continue
        if "init" + key.split(".")[-1] in initFunctions:
            initFunction = "init" + key.split(".")[-1]
        else:
            initFunction = initFunctions[-1]
        staticinitheader += "	extern  void " + initFunction + "(void);\n"


    staticinitheader += """

int
main(int argc, char **argv)
{
"""

    for key, value in foundLibs.items():
        functions = [x.decode('ascii').split(' ')[-1] for x in
                     subprocess.check_output(['nm', value]).split(os.linesep.encode('ascii'))]
        initFunctions = [x for x in functions if x.startswith('init')]
        if not initFunctions:
            continue
        if "init" + key.split(".")[-1] in initFunctions:
            initFunction = "init" + key.split(".")[-1]
        else:
            initFunction = initFunctions[-1]
        staticinitheader += "	PyImport_AppendInittab(\"" + key + "\", " + initFunction + ");\n"

    staticinitheader += """
	/* 754 requires that FP exceptions run in "no stop" mode by default,
	 * and until C vendors implement C99's ways to control FP exceptions,
	 * Python requires non-stop mode.  Alas, some platforms enable FP
	 * exceptions by default.  Here we disable them.
	 */
#ifdef __FreeBSD__
	fedisableexcept(FE_OVERFLOW);
#endif
	return Py_Main(argc, argv);
}

"""

    with open(os.path.join(sysconfig.get_config_var('prefix'), 'python.c'), 'w') as f:
        f.write(staticinitheader)

    print('Compiling new interpreter...')

    build_dir = os.path.join(sysconfig.get_config_var('prefix'), 'interpreter_build')

    if os.path.isdir(build_dir):
        shutil.rmtree(build_dir)

    include_dirs = [sysconfig.get_config_var('INCLUDEPY')]
    macros = [('Py_BUILD_CORE', None)]

    os.chdir(sysconfig.get_config_var('prefix'))

    compiler.compile(["python.c"], output_dir=build_dir, include_dirs=include_dirs, macros=macros)

    compiler.link_executable([os.path.join(build_dir, 'python.o')], 'python', output_dir=build_dir, libraries=linkLibs, library_dirs=library_dirs, extra_postargs=["-lm", "-pthread", "-lopenblas", "-lutil", "-ldl"])

    # Replace running interpreter by moving current version to a temp file, then marking it for deletion.
    interpreter_path = sys.executable
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.close()
    os.unlink(tmp.name)
    os.rename(sys.executable, tmp.name)
    os.unlink(tmp.name)
    #ctypes.windll.kernel32.MoveFileExW(tmp.name, None, MOVEFILE_DELAY_UNTIL_REBOOT)

    os.rename(os.path.join(build_dir, 'python'), interpreter_path)

    with open(os.path.join(sysconfig.get_config_var('prefix'), 'link.json'), 'w') as f:
        json.dump({
            'include_dirs': include_dirs,
            'macros': macros,
            'libraries': linkLibs,
            'library_dirs': library_dirs
        }, f)

    sys.path = initial_sys_path


if __name__ == '__main__':
    run_rebuild()