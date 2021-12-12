from __future__ import print_function

import glob
import os
import sys
import re
import shutil
import contextlib

def getDependencyInstallDir():
    import sysconfig
    return os.path.join(sysconfig.get_config_var('prefix'), 'dependency_libs')

def getToolsInstallDir():
    import sysconfig
    return os.path.join(sysconfig.get_config_var('prefix'), 'build_tools')

def getEnableStyleCode(style):
    if style == "pink":
        style = "\033[95m"
    elif style == "blue":
        style = "\033[94m"
    elif style == "green":
        style = "\033[92m"
    elif style == "yellow":
        style = "\033[93m"
    elif style == "red":
        style = "\033[91m"
    elif style == "bold":
        style = "\033[1m"
    elif style == "underline":
        style = "\033[4m"
    else:
        style = None

    return style


_enabled_ansi = False


def _enableAnsi():
    # singleton, pylint: disable=global-statement
    global _enabled_ansi
    if not _enabled_ansi:

        # Only necessary on Windows, as a side effect of this, ANSI colors get enabled
        # for the terminal and never deactivated, so we are free to use them after
        # this.
        if os.name == "nt":
            os.system("")

        _enabled_ansi = True


def getDisableStyleCode():
    return "\033[0m"


def my_print(*args, **kwargs):
    """Make sure we flush after every print.

    Not even the "-u" option does more than that and this is easy enough.

    Use kwarg style=[option] to print in a style listed below
    """

    file_output = kwargs.get("file", sys.stdout)
    is_atty = file_output.isatty()

    if "style" in kwargs:
        style = kwargs["style"]
        del kwargs["style"]

        if "end" in kwargs:
            end = kwargs["end"]
            del kwargs["end"]
        else:
            end = "\n"

        if style is not None and is_atty:
            enable_style = getEnableStyleCode(style)

            if enable_style is None:
                raise ValueError(
                    "%r is an invalid value for keyword argument style" % style
                )

            _enableAnsi()

            print(enable_style, end="", **kwargs)

        print(*args, end=end, **kwargs)

        if style is not None and is_atty:
            print(getDisableStyleCode(), end="", **kwargs)
    else:
        print(*args, **kwargs)

    # Flush the output.
    file_output.flush()


@contextlib.contextmanager
def TemporaryDirectory():
    import tempfile

    dirpath = tempfile.mkdtemp()
    yield dirpath
    shutil.rmtree(dirpath)

class NoSuchURL(Exception):
    pass

def download_file(url, destination):
    if str is bytes:
        from urllib2 import urlopen, HTTPError
    else:
        from urllib.request import urlopen, HTTPError

    try:
        my_print("Attempting to download '%s'." % url, style="blue")

        with contextlib.closing(urlopen(url)) as fp:
            if 'content-disposition' in fp.headers and 'filename=' in fp.headers['content-disposition']:
                destination_file = os.path.join(destination, fp.headers['content-disposition'].split('filename=')[-1])
            else:
                destination_file = os.path.join(destination, os.path.basename(fp.geturl()))

            parent_dir = os.path.dirname(destination_file)
            if not os.path.exists(parent_dir):
                os.makedirs(parent_dir)

            with open(destination_file, 'wb') as out_file:
                bs = 1024*8
                while True:
                    block = fp.read(bs)
                    if not block:
                        break
                    out_file.write(block)

    except HTTPError as e:
        if e.code == 404:
            raise NoSuchURL(url)
        else:
            raise

    return destination_file


def extract_archive(archive_file, destination=None):
    if destination is None:
        destination = os.path.splitext(archive_file)[0]
        if destination.endswith('.tar'):
            destination = destination[:-4]
    shutil.unpack_archive(archive_file, destination)
    return destination


def download_extract(url, destination):
    with TemporaryDirectory() as dir:
        downloaded_file = download_file(url, dir)
        extract_archive(downloaded_file, destination)


def get_compiler_module():
    compile_module_name = "distutils._msvccompiler" if os.name == "nt" else "distutils.unixccompiler"

    __import__(compile_module_name)
    return sys.modules[compile_module_name]


def get_vs_version():
    compiler_module = get_compiler_module()
    platform = compiler_module.get_platform()
    vc_env = compiler_module._get_vc_env(compiler_module.PLAT_TO_VCVARS[platform])
    return float(vc_env.get('visualstudioversion'))


def get_platform():
    compiler_module = get_compiler_module()
    return compiler_module.get_platform()


def find_compiler_exe(exe):
    compiler_module = get_compiler_module()
    platform = compiler_module.get_platform()
    vc_env = compiler_module._get_vc_env(compiler_module.PLAT_TO_VCVARS[platform])
    paths = vc_env.get('path', '').split(os.pathsep)
    return compiler_module._find_exe(exe, paths)


def setup_compiler_env():
    compiler_module = get_compiler_module()

    if os.name == "nt":
        platform = compiler_module.get_platform()
        vc_env = compiler_module._get_vc_env(compiler_module.PLAT_TO_VCVARS[platform])
        os.environ.update(vc_env)


def run_with_output(*args, **kwargs):
    import subprocess

    stdin = kwargs.pop("stdin", None)
    assert not kwargs

    p = subprocess.Popen(args, universal_newlines=True, stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    output = ""
    for line in p.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        output += line
    p.wait()
    if p.returncode != 0:
        raise subprocess.CalledProcessError(p.returncode, args, output)
    return output


def run_compiler_exe(exe, *args):
    return run_with_output(find_compiler_exe(exe), *args)


def msbuild(*args):
    return run_compiler_exe("msbuild.exe", *args)


def nmake(*args):
    return run_compiler_exe("nmake.exe", *args)


def install_files(dst, *files):
    if not os.path.isdir(dst):
        os.makedirs(dst, exist_ok=True)
    for file_glob in files:
        for file in glob.glob(file_glob):
            if os.path.isdir(file):
                shutil.copytree(file, os.path.join(dst, os.path.basename(file)))
            else:
                shutil.copy(file, os.path.join(dst, os.path.basename(file)))


def install_dep_include(dependency_name, *files):
    dependency_location = os.path.join(getDependencyInstallDir(), dependency_name, 'include')
    install_files(dependency_location, *files)


def install_dep_libs(dependency_name, *files):
    dependency_location = os.path.join(getDependencyInstallDir(), dependency_name, 'libs')
    install_files(dependency_location, *files)


def install_build_tool(tool_name, *files):
    dependency_location = os.path.join(getToolsInstallDir(), tool_name)
    install_files(dependency_location, *files)


def find_build_tool_exe(tool_name, exe):
    if os.name == "nt":
        return glob.glob(os.path.join(BUILD_TOOLS_INSTALL_DIR, tool_name, exe))[0]
    else:
        return tool_name


def run_build_tool_exe(tool_name, exe, *args, **kwargs):
    return run_with_output(find_build_tool_exe(tool_name, exe), *args, **kwargs)


def apply_patch(patch_file, directory):
    """ Apply a patch file to a directory. """
    with open(patch_file, "rb") as stdin:
        run_build_tool_exe("patch", "patch.exe" if os.name=="nt" else "patch", "-d", directory, "-p", "1", stdin=stdin)

def find_dep_include(dep_name):
    return os.path.join(getDependencyInstallDir(), dep_name, 'include')


def find_dep_libs(dep_name):
    return os.path.join(getDependencyInstallDir(), dep_name, 'libs')


def prepend_to_file(file, prepend_str):
    output = prepend_str
    with open(file, 'r') as f:
        output += f.read()
    with open(file, 'w') as f:
        f.write(output)


def is_file_binary(file_path):
    textchars = bytearray({7,8,9,10,12,13,27} | set(range(0x20, 0x100)) - {0x7f})
    with open(file_path, 'rb') as f:
        return bool(f.read(1024).translate(None, textchars))


def auto_patch_MD_MT(folder):
    for dname, dirs, files in os.walk(folder):
        for fname in files:
            fpath = os.path.join(dname, fname)
            if '.git' in fpath or '.svn' in fpath:
                continue

            if fname.endswith('CMakeLists.txt'):
                with open(fpath, 'r') as f:
                    s = f.read()
                s2 = s.replace("/MD", "/MT")
                s2 = s2.replace("-MD", "-MT")
                s2 = re.sub(r"cmake_minimum_required *\( *VERSION [0-9\.]+ *\)", "cmake_minimum_required(VERSION 3.15)", s2, flags=re.IGNORECASE)
                s2 = re.sub(r"cmake_policy\(VERSION [0-9\.]+\)", "", s2, flags=re.IGNORECASE)
                if s != s2:
                    my_print("Fixed up file: %s" % fpath, style="blue")
                    with open(fpath, "w") as f:
                        f.write(s2)
            elif not is_file_binary(fpath):
                with open(fpath, 'r') as f:
                    s = f.read()
                s2 = s.replace("/MD", "/MT")
                s2 = s2.replace("-MD", "-MT")
                if s != s2:
                    my_print("Fixed up file: %s" % fpath, style="blue")
                    with open(fpath, "w") as f:
                        f.write(s2)


def auto_patch_Cython_memcpy(folder):
    # TODO: Have a generic implementation, maybe in nuitka.utils for this
    for dname, dirs, files in os.walk(folder):
        for fname in files:
            fpath = os.path.join(dname, fname)
            if '.git' in fpath or '.svn' in fpath:
                continue

            # TODO: Probably unnecessary
            if fname.endswith('.cc'):
                with open(fpath, 'r') as f:
                    s = f.read()
                s2 = s.replace('"-Wl,-wrap,memcpy"',"")

                if s != s2:
                    my_print("Removed Cython config: %s" % fpath, style="blue")
                    with open(fpath, "w") as f:
                        f.write(s2)


            if fname == "setup.py":
                with open(fpath, 'r') as f:
                    s = f.read()
                s2 = s.replace("-Wl,-wrap,memcpy", "")

                if s != s2:
                    my_print("Removed memcpy wrapper config: %s" % fpath, style="blue")
                    with open(fpath, "w") as f:
                        f.write(s2)


def shall_link_statically(name):
    import fnmatch

    static_pattern = os.environ.get("NUITKA_PYTHON_STATIC_PATTERN")
    if not static_pattern or not fnmatch.fnmatch(name, static_pattern):
        return False

    return True

def write_linker_json(result_path, libraries, library_dirs, runtime_library_dirs, extra_args):
    import json

    with open(result_path + '.link.json', 'w') as f:
        json.dump({
            'libraries': libraries,
            'library_dirs': library_dirs,
            'runtime_library_dirs': runtime_library_dirs,
            'extra_postargs': extra_args}, f)