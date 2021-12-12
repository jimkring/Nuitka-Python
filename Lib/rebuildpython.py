from __future__ import print_function

import sys
import os
import shutil
import subprocess
import distutils
import distutils.ccompiler
import sysconfig
import json
import tempfile
import fnmatch

MOVEFILE_DELAY_UNTIL_REBOOT = 4

def find_files(directory, pattern):
    for root, dirs, files in os.walk(directory):
        for basename in files:
            if fnmatch.fnmatch(basename, pattern):
                filename = os.path.join(root, basename)
                yield filename

def run_rebuild():
    installDir = os.path.dirname(sys.executable)

    # Make sure we have the same compiler as used originally.
    cc_config_var = sysconfig.get_config_var("CC").split()[0]
    if "CC" in os.environ and os.environ["CC"] != cc_config_var:
        print("Overriding CC variable to Nuitka-Python used '%s' ..." % cc_config_var)
    os.environ["CC"] = cc_config_var

    cxx_config_var = sysconfig.get_config_var("CXX").split()[0]
    if "CXX" in os.environ and os.environ["CXX"] != cxx_config_var:
        print("Overriding CXX variable to Nuitka-Python used '%s' ..." % cxx_config_var)
    os.environ["CXX"] = cxx_config_var

    compiler = distutils.ccompiler.new_compiler(verbose=5)
    #compiler.initialize()

    foundLibs = {}
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
    link_libs = ['m']

    library_dirs = [sysconfig.get_config_var('prefix'), sysconfig.get_config_var('LIBDEST')]

    # Scrape all available libs from the libs directory. We will let the linker worry about filtering out extra symbols.
    for file in find_files(sysconfig.get_config_var('LIBDEST'), '*.a'):
        link_libs.append(file)

    for _name, path in foundLibs.items():
        link_libs += [path]

        if os.path.isfile(path + '.link.json'):
            with open(path + '.link.json', 'r') as f:
                linkData = json.load(f)
                print(linkData)
                link_libs += linkData['libraries']
                library_dirs += [os.path.join(os.path.dirname(path), x) for x in linkData['library_dirs']]

    link_libs = list(set(link_libs))
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

    compiler.link_executable(
        objects = [os.path.join(build_dir, 'python.o')],
        output_progname='python',
        output_dir=build_dir,
        libraries=link_libs,
        library_dirs=library_dirs,
        extra_postargs=["-lm", "-pthread", "-lutil", "-ldl"] + sysconfig.get_config_var("LDFLAGS").split() + sysconfig.get_config_var("CFLAGS").split()
    )

    # Replace running interpreter by moving current version to a temp file, then deleting it. This
    # is to avoid Windows locks
    interpreter_path = sys.executable
    tmp = tempfile.NamedTemporaryFile(delete=False, dir=os.path.dirname(sys.executable))
    tmp.close()
    os.unlink(tmp.name)
    os.rename(sys.executable, tmp.name)
    os.unlink(tmp.name)

    os.rename(os.path.join(build_dir, 'python'), interpreter_path)

    with open(os.path.join(sysconfig.get_config_var('prefix'), 'link.json'), 'w') as f:
        json.dump({
            'include_dirs': include_dirs,
            'macros': macros,
            'libraries': link_libs,
            'library_dirs': library_dirs
        }, f)


if __name__ == '__main__':
    run_rebuild()