from __future__ import print_function
import os
import sys
import shutil
import urllib.parse as urlparse
from pathlib import Path
import subprocess
from conda.exports import download, hashsum_file
import stat


def set_chmod(file_name):
    # Do a simple chmod +x for a file within python
    st = os.stat(file_name)
    os.chmod(file_name, st.st_mode | stat.S_IXOTH)


def create_dir(new_dir):
    try:
        os.makedirs(new_dir)
    except FileExistsError:
        pass


def copy_files(src, dst):
    try:
        if (os.path.isfile(src)):
            set_chmod(src)
            shutil.copy(src, dst)
    except FileExistsError:
        pass


config = {}
versions = ["9.2"]
for v in versions:
    config[v] = {"linux": {}, "windows": {}, "osx": {}}


cu_92 = config["9.2"]
cu_92["base_url"] = "https://developer.nvidia.com/compute/cuda/9.2/Prod2/"
cu_92["installers_url_ext"] = "local_installers/"
cu_92["patch_url_ext"] = ""
cu_92["md5_url"] = "http://developer.download.nvidia.com/compute/cuda/9.2/Prod2/docs/sidebar/md5sum.txt"

cu_92['libdevice_versions'] = ['10']

cu_92['linux'] = {'blob': 'cuda_9.2.148_396.37_linux',
                  'patches': [],
                  }

cu_92['windows'] = {'blob': 'cuda_9.2.148_windows',
                    'patches': [],
                    'NvToolsExtPath':
                    os.path.join('c:' + os.sep, 'Program Files',
                                 'NVIDIA Corporation', 'NVToolsExt', 'bin')
                    }

cu_92['osx'] = {'blob': 'cuda_9.2.148_mac',
                'patches': [],
                }


class Extractor(object):
    """Extractor base class, platform specific extractors should inherit
    from this class.
    """
    libdir = {'linux': 'lib',
              'osx': 'lib',
              'windows': 'DLLs', }

    def __init__(self, version, name, build_num, ver_config, platform_config):
        """Initialise an instance:
        Arguments:
          version - CUDA version string
          ver_config - the configuration for this CUDA version
          platform_config - the configuration for this platform
        """
        self.cu_name = name
        self.cu_buildnum = build_num
        self.cu_version = version
        self.md5_url = ver_config["md5_url"]
        self.base_url = ver_config["base_url"]
        self.patch_url_text = ver_config["patch_url_ext"]
        self.installers_url_ext = ver_config["installers_url_ext"]
        self.cu_blob = platform_config['blob']
        self.config = {"version": version, **ver_config}
        self.conda_prefix = os.environ.get('CONDA_PREFIX')
        self.prefix = os.environ["PREFIX"]
        self.src_dir = Path(self.conda_prefix) / 'pkgs' / self.cu_name
        try:
            os.makedirs(self.src_dir)

        except FileExistsError:
            pass

        self.output_dir = os.path.join(self.prefix, self.libdir[getplatform()])
        self.symlinks = getplatform() == "linux"
        self.debug_install_path = os.environ.get('DEBUG_INSTALLER_PATH')

    def create_activate_and_deactivate_scripts(self):
        activate_dir_path = Path(self.conda_prefix) / \
            'etc' / 'conda' / 'activate.d'
        deactivate_dir_path = Path(
            self.conda_prefix) / 'etc' / 'conda' / 'deactivate.d'

        try:
            os.makedirs(activate_dir_path)
            os.makedirs(deactivate_dir_path)

        except FileExistsError:
            pass

        # Copy cudatoolkit-dev-activate and cudatoolkit-dev-deactivate
        # to activate.d and deactivate.d directories

        scripts_dir = Path(self.prefix) / 'scripts'
        activate_scripts_dir = scripts_dir / 'activate.d'
        deactivate_scripts_dir = scripts_dir / 'deactivate.d'

        activate_scripts_list = [
            "cudatoolkit-dev-activate.sh",
            "cudatoolkit-dev-activate.bat"]
        for file_name in activate_scripts_list:
            file_full_path = activate_scripts_dir / file_name
            shutil.copy(file_full_path, activate_dir_path)

        deactivate_scripts_list = [
            "cudatoolkit-dev-deactivate.sh",
            "cudatoolkit-dev-deactivate.bat"]

        for file_name in deactivate_scripts_list:
            file_full_path = deactivate_scripts_dir / file_name
            shutil.copy(file_full_path, deactivate_dir_path)

    def download_blobs(self):
        """Downloads the binary blobs to the $SRC_DIR
        """
        dl_url = urlparse.urljoin(self.base_url, self.installers_url_ext)
        dl_url = urlparse.urljoin(dl_url, self.cu_blob)
        dl_path = os.path.join(self.src_dir, self.cu_blob)
        if not self.debug_install_path:
            print("downloading %s to %s" % (dl_url, dl_path))
            download(dl_url, dl_path)

        else:
            existing_file = os.path.join(self.debug_install_path, self.cu_blob)
            print("DEBUG: copying %s to %s" % (existing_file, dl_path))
            shutil.copy(existing_file, dl_path)

    def check_md5(self):
        """Checks the md5sums of the downloaded binaries
        """
        md5file = self.md5_url.split("/")[-1]
        path = os.path.join(self.src_dir, md5file)
        download(self.md5_url, path)

        # compute hash of blob
        blob_path = os.path.join(self.src_dir, self.cu_blob)
        md5sum = hashsum_file(blob_path, 'md5')

        # get checksums
        with open(path, 'r') as f:
            checksums = [x.strip().split() for x in f.read().splitlines() if x]

        # check md5 and filename match up
        check_dict = {x[0]: x[1] for x in checksums}
        assert check_dict[md5sum].startswith(self.cu_blob[:-7])

    def extract(self, *args):
        """The method to extract files from the cuda binary blobs.
        Platform specific extractors must implement.
        """
        raise RuntimeError("Must implement")


    def cleanup(self):
        """The method to delete unnecessary files after
        the installation process.
        """
        blob_path = os.path.join(self.src_dir, self.cu_blob)
        if os.path.exists(blob_path):
            os.remove(blob_path)

        else:
            pass


class WindowsExtractor(Extractor):
    """The windows extractor
    """

    def extract(self):
        print("Extracting on Windows.....")
        runfile = os.path.join(self.src_dir, self.cu_blob)
        cmd = ['7za', 'x', '-o%s' %
               str(self.src_dir), runfile]
        try:
            subprocess.check_call(cmd)
        except subprocess.CalledProcessError as e:
            print("ERROR: Couldn't install Cudatoolkit: \
                   {reason}".format(reason=e))


class LinuxExtractor(Extractor):
    """The Linux Extractor
    """

    def extract(self):
        print("Extracting on Linux")
        runfile = os.path.join(self.src_dir, self.cu_blob)
        os.chmod(runfile, 0o777)
        cmd = [runfile, '--silent', '--toolkit',
               '--toolkitpath', str(self.src_dir), '--override']
        try:
            subprocess.check_call(cmd)
        except subprocess.CalledProcessError as e:
            print("ERROR: Couldn't install Cudatoolkit: \
                   {reason}".format(reason=e))


class OsxExtractor(Extractor):
    """The osx Extractor
    """

    def _hdiutil_mount(self, temp_dir, file_name, install_dir):
        """Function to mount osx dmg images, extracts the files
           from an image into store and ensure they are
           unmounted on exit.
        """
        # open
        cmd = ['hdiutil', 'attach', '-mountpoint', temp_dir, file_name]
        subprocess.check_call(cmd)
        # find tar.gz files
        cmd = ['find', temp_dir, '-name', '"*.tar.gz"', '-exec', 'tar',
               'xvf', '{}', '--directory', install_dir, "\\", ";"]
        subprocess.check_call(cmd)
        # close
        subprocess.check_call(['hdiutil', 'detach', temp_dir])

    def extract(self):
        runfile = os.path.join(self.src_dir, self.cu_blob)
        extract_store_name = 'tmpstore'
        extract_store = os.path.join(self.src_dir, extract_store_name)
        os.mkdir(extract_store)
        self._hdiutil_mount(extract_store, runfile, self.src_dir)


def getplatform():
    plt = sys.platform
    if plt.startswith("linux"):
        return "linux"
    elif plt.startswith("win"):
        return "windows"
    elif plt.startswith("darwin"):
        return "osx"
    else:
        raise RuntimeError("Unknown platform")


dispatcher = {
    "linux": LinuxExtractor,
    "windows": WindowsExtractor,
    "osx": OsxExtractor, }


def _main():

    print("Running Post installation")

    # package version decl must match cuda release version
    cu_version = os.environ['PKG_VERSION']
    cu_name = os.environ['PKG_NAME']
    cu_buildnum = os.environ['PKG_BUILDNUM']

    # get an extractor
    plat = getplatform()
    extractor_impl = dispatcher[plat]
    version_cfg = config[cu_version]
    extractor = extractor_impl(
        cu_version,
        cu_name,
        cu_buildnum,
        version_cfg,
        version_cfg[plat])

    # create activate and deactivate scripts
    extractor.create_activate_and_deactivate_scripts()

    # download binaries
    extractor.download_blobs()

    # check md5sum
    extractor.check_md5()

    # Extract
    extractor.extract()

    # Cleanup
    extractor.cleanup()


if __name__ == "__main__":
    _main()
