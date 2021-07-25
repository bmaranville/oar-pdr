"""
Provide functionality for the Public Data Repository
"""
import os
from abc import ABCMeta, abstractmethod, abstractproperty

from .constants import *

try:
    from .version import __version__
except ImportError:
    __version__ = "(unset)"

def _get_platform_profile_name():
    """
    determine the name of the platform environment that the PDR system is 
    running within.  This name is used to retrieve configuration data 
    appropriate for the platform.  

    Currently, this name is passed in via the OAR_PLATFORM_PROFILE environment
    variable.
    """
    return os.environ.get('OAR_PLATFORM_PROFILE', 'unknown')

platform_profile = _get_platform_profile_name()

class SystemInfoMixin(object):
    """
    a mixin for getting information about the current system that a class is 
    a part of.  
    """
    __metaclass__ = ABCMeta

    @property
    def system_name(self):
        return ""

    @property
    def system_abbrev(self):
        return ""

    @property
    def subsystem_name(self):
        return ""

    @property
    def subsystem_abbrev(self):
        return ""

    @abstractproperty
    def system_version(self):
        return __version__

_PDRSYSNAME = "Public Data Repository"
_PDRSYSABBREV = "PDR"
_PDRSUBSYSNAME = _PDRSYSNAME
_PDRSUBSYSABBREV = _PDRSYSABBREV

class PDRSystem(SystemInfoMixin):
    """
    a mixin providing static information about the PDR system.  

    In addition to providing system information, one can determine if a class 
    instance--namely, an Exception--is part of a particular system by calling 
    `isinstance(inst, PDRSystem)`.
    """

    @property 
    def system_version(self):
        return __version__

    @property
    def system_name(self): return _PDRSYSNAME
    @property
    def system_abbrev(self): return _PDRSYSABBREV
    @property
    def subsystem_name(self): return _PDRSUBSYSNAME
    @property
    def subsystem_abbrev(self): return _PDRSUBSYSABBREV
    
def find_jq_lib(config=None):
    """
    return the directory containing the jq libraries
    """
    from .exceptions import ConfigurationException
    
    def assert_exists(dir, ctxt=""):
        if not os.path.exists(dir):
            msg = "{0}directory does not exist: {1}".format(ctxt, dir)
            raise ConfigurationException(msg)

    # check local configuration
    if config and 'jq_lib' in config:
        assert_exists(config['jq_lib'], "config param 'jq_lib' ")
        return config['jq_lib']
            
    # check environment variable
    if 'OAR_JQ_LIB' in os.environ:
        assert_exists(os.environ['OAR_JQ_LIB'], "env var OAR_JQ_LIB ")
        return os.environ['OAR_JQ_LIB']

    # look relative to a base directory
    if 'OAR_HOME' in os.environ:
        # this is normally an installation directory (where lib/jq is our
        # directory) but we also allow it to be the source directory
        assert_exists(os.environ['OAR_HOME'], "env var OAR_HOME ")
        basedir = os.environ['OAR_HOME']
        candidates = [os.path.join(basedir, 'lib', 'jq'),
                      os.path.join(basedir, 'jq')]
    else:
        # guess some locations based on the location of the executing code.
        # The code might be coming from an installation, build, or source
        # directory.
        import nistoar
        basedir = os.path.dirname(os.path.dirname(os.path.dirname(
                                            os.path.abspath(nistoar.__file__))))
        candidates = [os.path.join(basedir, 'jq')]
        basedir = os.path.dirname(os.path.dirname(basedir))
        candidates.append(os.path.join(basedir, 'jq'))
        candidates.append(os.path.join(basedir, 'oar-metadata', 'jq'))
        
    for dir in candidates:
        if os.path.exists(dir):
            return dir
        
    return None

def_jq_libdir = find_jq_lib()

def find_merge_etc(config=None):
    """
    return the directory containing the merge rules
    """
    from .exceptions import ConfigurationException
    
    def assert_exists(dir, ctxt=""):
        if not os.path.exists(dir):
            msg = "{0}directory does not exist: {1}".format(ctxt, dir)
            raise ConfigurationException(msg)

    # check local configuration
    if config and 'merge_rules_lib' in config:
        assert_exists(config['merge_rules_lib'],
                      "config param 'merge_rules_lib' ")
        return config['merge_rules_lib']
            
    # check environment variable
    if 'OAR_MERGE_ETC' in os.environ:
        assert_exists(os.environ['OAR_MERGE_ETC'], "env var OAR_MERGE_ETC ")
        return os.environ['OAR_MERGE_ETC']

    # look relative to a base directory
    if 'OAR_HOME' in os.environ:
        # this is normally an installation directory (where lib/jq is our
        # directory) but we also allow it to be the source directory
        assert_exists(os.environ['OAR_HOME'], "env var OAR_HOME ")
        basedir = os.environ['OAR_HOME']
        candidates = [os.path.join(basedir, 'etc', 'merge')]

    else:
        # guess some locations based on the location of the executing code.
        # The code might be coming from an installation, build, or source
        # directory.
        import nistoar
        basedir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
                                            os.path.abspath(nistoar.__file__)))))
        candidates = [os.path.join(basedir, 'etc', 'merge')]
        candidates.append(os.path.join(basedir, 'oar-metadata', 'etc', 'merge'))
        basedir = os.path.dirname(basedir)
        candidates.append(os.path.join(basedir, 'oar-metadata', 'etc', 'merge'))
        candidates.append(os.path.join(basedir, 'etc', 'merge'))

    for dir in candidates:
        if os.path.exists(dir):
            return dir
        
    return None

def_merge_etcdir = find_merge_etc()

def find_etc_dir(config=None):
    """
    return the path to the etc directory containing miscellaneous OAR files
    """
    from .exceptions import ConfigurationException
    
    def assert_exists(dir, ctxt=""):
        if not os.path.exists(dir):
            msg = "{0}directory does not exist: {1}".format(ctxt, dir)
            raise ConfigurationException(msg)

    # check local configuration
    if config and 'etc_lib' in config:
        assert_exists(config['etc_lib'],
                      "config param 'etc_lib' ")
        return config['etc_lib']

    # look relative to a base directory
    if 'OAR_HOME' in os.environ:
        # this is might be the install base or the source base directory;
        # either way, etc, is a subdirectory.
        assert_exists(os.environ['OAR_HOME'], "env var OAR_HOME ")
        basedir = os.environ['OAR_HOME']
        candidates = [os.path.join(basedir, 'etc')]

    else:
        # guess some locations based on the location of the executing code.
        # The code might be coming from an installation, build, or source
        # directory.
        import nistoar
        basedir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
                                            os.path.abspath(nistoar.__file__)))))
        candidates = [os.path.join(basedir, 'etc'),
                      os.path.join(os.path.dirname(basedir), 'etc')]
    
    for dir in candidates:
        if os.path.exists(dir):
            return dir
        
    return None

def_etc_dir = find_etc_dir()

def find_schema_dir(config=None):
    """
    return the directory containing the NERDm schema files
    """
    from .exceptions import ConfigurationException
    
    def assert_exists(dir, ctxt=""):
        if not os.path.exists(dir):
            msg = "{0}directory does not exist: {1}".format(ctxt, dir)
            raise ConfigurationException(msg)

    # check local configuration
    if config and 'nerdm_schemas_dir' in config:
        assert_exists(config['nerdm_schemas_dir'],
                      "config param 'nerdm_schemas_dir' ")
        return config['nerdm_schemas_dir']
            
    # check environment variable
    if 'OAR_SCHEMA_DIR' in os.environ:
        assert_exists(os.environ['OAR_SCHEMA_DIR'],
                      "env var OAR_SCHEMA_DIR ")
        return os.environ['OAR_SCHEMA_DIR']

    # look relative to a base directory
    if 'OAR_HOME' in os.environ:
        # this is normally an installation directory (where etc/schemas is our
        # directory) but we also allow it to be the source directory
        assert_exists(os.environ['OAR_HOME'], "env var OAR_HOME ")
        basedir = os.environ['OAR_HOME']
        candidates = [os.path.join(basedir, 'etc', 'schemas')]

    else:
        # guess some locations based on the location of the executing code.
        # The code might be coming from an installation, build, or source
        # directory.
        import nistoar
        candidates = []

        # assume library has been installed; library is rooted at {root}/lib/python,
        basedir = os.path.dirname(                       # {root}
                  os.path.dirname(                       # lib
                  os.path.dirname(                       # python
                  os.path.dirname(                       # nistoar
                  os.path.abspath(nistoar.__file__)))))  # __init__.py

        # and the schema dir is {root}/etc/schemas o
        candidates.append(os.path.join(basedir, 'etc', 'schemas'))

        # assume library has been built within the source code directory at {root}/python/build/lib*
        basedir = os.path.dirname(                       # {root}
                  os.path.dirname(                       # python
                  os.path.dirname(                       # build
                  os.path.dirname(                       # lib.*
                  os.path.dirname(                       # nistoar
                  os.path.abspath(nistoar.__file__)))))) # __init__.py

        # then the schema would be under {root}/oar-metadata/model
        candidates.append(os.path.join(basedir, 'oar-metadata', 'model'))

        # assume library being used from its source code location
        basedir = os.path.dirname(                      # {root}
                  os.path.dirname(                      # python
                  os.path.dirname(                      # nistoar
                  os.path.abspath(nistoar.__file__))))  # __init__.py

        # and is under {root}/oar-metadata/model
        candidates.append(os.path.join(basedir, 'oar-metadata', 'model'))

    for dir in candidates:
        if os.path.exists(dir):
            return dir
        
    return None

def_schema_dir = find_schema_dir()

