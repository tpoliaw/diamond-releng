#! /bin/sh
# -*- mode: python; coding: utf-8 -*-

###
### Python Eclipse Workspace MAnager
### platform-independent script to manage development of Eclipse-based products such as GDA and Dawn
###

# This file is used as both a shell script and as a Python script.

""":"
# This part is run by the shell.  It looks for an appropriate Python
# interpreter then uses it to re-exec this script. Note that dls-python
# is a python install at Diamond Light Source which includes pygelf.
# If not available, use whatever python is found on the system path.

if type dls-python >/dev/null 2>/dev/null; then
  exec dls-python "$0" "$@"
elif type python2 >/dev/null 2>/dev/null; then
  exec python2 "$0" "$@"
elif type python >/dev/null 2>/dev/null; then
  exec python "$0" "$@"
else
  echo 1>&2 "No usable Python interpreter was found!"
  exit 1
fi

" """

# The rest of the file is run by the Python interpreter.
from __future__ import absolute_import, division, print_function, unicode_literals

import ConfigParser
import datetime
import errno
import filecmp
import fnmatch
import getpass
try:
    import grp
except ImportError:
    pass  # grp not available on Windows
import logging
import optparse
import os
import platform
try:
    import pwd
except ImportError:
    pass  # pwd not available on Windows
import re
import shlex
import socket
import StringIO
import stat
import subprocess
import sys
import tarfile
import time
import urllib
import urllib2
import xml.etree.ElementTree as ET
from xml.parsers.expat import ExpatError
import zipfile

GRAYLOG_SERVER = 'graylog2.diamond.ac.uk'
GRAYLOG_PORT   = 12251

COMPONENT_ABBREVIATIONS = [] # tuples of (abbreviation, actual component name to use, category)

# keep entries if they are used in ANY active release, even if they have been removed in master
COMPONENT_ABBREVIATIONS.append(('dawnvanilla', 'org.dawnsci.base.site', 'dawn'))
COMPONENT_ABBREVIATIONS.append(('dawndiamond', 'uk.ac.diamond.dawn.site', 'dawn'))

COMPONENT_ABBREVIATIONS.append(('example-client', 'uk.ac.gda.example.site', 'gda'))
COMPONENT_ABBREVIATIONS.append(('k11-client', 'uk.ac.diamond.daq.beamline.k11.site', 'gda'))
COMPONENT_ABBREVIATIONS.append(('p45-client', 'uk.ac.diamond.daq.beamline.p45.site', 'gda'))
COMPONENT_ABBREVIATIONS.append(('p99-client', 'uk.ac.diamond.daq.beamline.p99.site', 'gda'))
COMPONENT_ABBREVIATIONS.append(('imca-cat-client', 'gov.anl.aps.beamline.imca-cat.site', 'gda'))
for beamline in ('b07', 'b07-1', 'b16', 'b18', 'b21', 'b24',
                 'i02', 'i02-1', 'i02-2', 'i03', 'i04', 'i04-1',
                 'i05', 'i05-1', 'i06', 'i06_1', 'i07', 'i08', 'i08-1', 'i09', 'i09-1', 'i09-2',
                 'i10', 'i11', 'i11-1', 'i12', 'i13', 'i13-1','i13i', 'i13j', 'i14', 'i15', 'i15-1', 'i16', 'i18', 'i19-1', 'i19-2',
                 'i20', 'i20_1', 'i20-1', 'i21', 'i22', 'i23', 'i24', 'k11', 'lab11',
                 ):
    COMPONENT_ABBREVIATIONS.append((beamline + '-client', 'uk.ac.gda.beamline.' + beamline + '.site', 'gda'))
for serverabbrev in ('server', 'gdaserver', 'gda-server', 'gdaservers', 'gda-servers'):
    COMPONENT_ABBREVIATIONS.append((serverabbrev, 'uk.ac.diamond.daq.server.site', 'gda'))
COMPONENT_ABBREVIATIONS.append(('all-dls', ('all-dls-configs', 'all-dls-clients', 'uk.ac.diamond.daq.server.site', 'gda-orphan-projects'), 'gda'))

# A category+version is one way of specifying a specific CQuery (version can default to "master")
# Caution: categories must never be the same as any component name or component abbreviation
COMPONENT_CATEGORIES = (
    # category, version, CQuery, template, version_synonyms, allowable java versions (or None, for not specified) (first in list is preferred)
    ('gda', 'diad', 'gda-diad.cquery', 'v3.4', ('diad',), ('1.8.0',)),
    ('gda', 'master', 'gda-master.cquery', 'v3.4', ('master', '9.master', 'v9.master'), ('1.8.0',)),
    ('gda', 'v9.10', 'gda-v9.10.cquery', 'v3.4', ('v9.10', '9.10', '910'), ('1.8.0',)),
    ('gda', 'v9.9', 'gda-v9.9.cquery', 'v3.4', ('v9.9', '9.9', '99'), ('1.8.0',)),
    ('gda', 'v9.8', 'gda-v9.8.cquery', 'v3.3', ('v9.8', '9.8', '98'), ('1.8.0',)),
    ('gda', 'v9.7', 'gda-v9.7.cquery', 'v3.3', ('v9.7', '9.7', '97'), ('1.8.0',)),
    ('gda', 'v9.6', 'gda-v9.6.cquery', 'v3.3', ('v9.6', '9.6', '96'), ('1.8.0',)),
    ('gda', 'v9.5', 'gda-v9.5.cquery', 'v3.3', ('v9.5', '9.5', '95'), ('1.8.0',)),
    ('dawn', 'master', 'dawn-master.cquery', 'v3.4', ('master', '2.master', 'v2.master'), ('1.8.0',)),
    ('dawn', 'v2.11', 'dawn-v2.11.cquery', 'v3.4', ('v2.11', '2.11'), ('1.8.0',)),
    ('dawn', 'v2.10', 'dawn-v2.10.cquery', 'v3.4', ('v2.10', '2.10'), ('1.8.0',)),
    ('dawn', 'v2.9', 'dawn-v2.9.cquery', 'v3.3', ('v2.9', '2.9'), ('1.8.0',)),
    ('dawn', 'v2.8', 'dawn-v2.8.cquery', 'v3.3', ('v2.8', '2.8'), ('1.8.0',)),
    ('dawn', 'v2.7', 'dawn-v2.7.cquery', 'v3.3', ('v2.7', '2.7'), ('1.8.0',)),
    ('dawn', 'v2.6', 'dawn-v2.6.cquery', 'v3.3', ('v2.6', '2.6'), ('1.8.0',)),
    )

CATEGORIES_AVAILABLE = []  # dedupe COMPONENT_CATEGORIES while preserving order
for c in COMPONENT_CATEGORIES:
    if c[0] not in CATEGORIES_AVAILABLE:
        CATEGORIES_AVAILABLE.append(c[0])

# template names must be of the form vx.y
for c in COMPONENT_CATEGORIES:
    assert c[3].startswith('v')
    assert c[3].count('.') == 1

VERSIONS_AVAILABLE = set()  # dedupe version_synonyms
for c in COMPONENT_CATEGORIES:
    for v in c[4]:
        VERSIONS_AVAILABLE.add(v)

for abbrev, actual, cat in COMPONENT_ABBREVIATIONS:
    assert abbrev not in CATEGORIES_AVAILABLE, 'Component abbreviation "%s" is the same as a category' % (abbrev,)
    assert cat in CATEGORIES_AVAILABLE, 'Component abbreviation "%s" is defined with an invalid category: "%s"' % (abbrev, cat)
    assert abbrev not in VERSIONS_AVAILABLE, 'Component abbreviation "%s" is the same as a version' % (abbrev,)

for cat in CATEGORIES_AVAILABLE:
    assert cat not in VERSIONS_AVAILABLE, 'Category "%s" is the same as a version' % (cat,)

INVALID_COMPONENTS = (  # tuple of (component name pattern, (applicable versions pattern), error message) 
    ('^all-dls-config$', ('^(master|v9\.[98765432])$'), 'all-dls-config no longer exists in GDA 9.2+; see Jira DAQ-328'),
    ('^all-mx-config$', ('^(master|v9\.[98765432])$'), 'all-mx-config no longer exists in GDA 9.2+; see Jira DAQ-328'),
    ('^all-dls-configs$', ('^(v?8\..+|v9\.[01])$'), 'all-dls-configs only applies to GDA 9.2+'),
    ('^all-dls-clients$', ('^(v?8\..+|v9\.[01])$'), 'all-dls-clients only applies to GDA 9.2+'),
    ('^all-dls$', ('^(v?8\..+|v9\.[01])$'), 'all-dls only applies to GDA 9.2+'),
    )

# For newer CQueries, we specify -Declipse.p2.mirrors=false so that the DLS mirror of eclipse.org p2 sites (alfred.diamond.ac.uk) is used
# Older CQueries do not use the local DLS mirror, so we should not specify that property
CQUERY_PATTERNS_TO_SKIP_p2_mirrors_false = (
    '^dawn-v2\.[01]\.cquery$',
    '^gda-v9\.[01]\..*cquery$',
    )

# the template name for master is the default template
for c in COMPONENT_CATEGORIES:
    if c[1] == 'master':
        DEFAULT_TEMPLATE = c[3]
        break
assert DEFAULT_TEMPLATE   # must have been set

PLATFORMS_AVAILABLE =  (
    # os/ws/arch, acceptable abbreviations
    ('linux,gtk,x86_64', ('linux,gtk,x86_64', 'linux64')),
    ('macosx,cocoa,x86_64', ('macosx,cocoa,x86_64', 'macosx64', 'mac64',)),
    ('win32,win32,x86_64', ('win32,win32,x86_64', 'win64', 'windows64',)),
    )

DLS_BUCKMINSTER_URI = 'https://alfred.diamond.ac.uk/buckminster/'  # default, can be overidden by --dls-buckminster-uri option (e.g. file:///path)

JGIT_ERROR_PATTERNS = ( # JGit error messages that identify an intermittent network problem causing a checkout failure (the affected repository is only sometimes identified)
    ('org\.eclipse\.jgit\.api\.errors\.TransportException: (\S+\.git):', 1),  # 1 = first match group is the repository
    ('org\.eclipse\.jgit\.api\.errors\.TransportException: (Connection reset|Short read of block\.)', 'Network error'),  # text = no specific repository identified
    ('org\.eclipse\.jgit\.api\.errors\.TransportException: \S+://\S+/([^ /\t\n\r\f\v]+\.git): unknown host', 1),  # 1 = first match group is the repository
    ('org\.eclipse\.jgit\.api\.errors\.InvalidRemoteException: Invalid remote: origin', 'Network error'),  # text = no specific repository identified
    ('org\.apache\.http\.conn\.HttpHostConnectException: Connection to .+ refused', 'Connection refused'),  # text = no specific repository identified
    ('java\.net\.ConnectException: Connection (refused|timed out)', 'Network error'),  # text = no specific repository identified
    ('java\.net\.SocketTimeoutException: Read timed out', 'Network error'),  # text = no specific repository identified
    ('HttpComponents connection error response code (500|502|503)', 'Server error'),  # text = no specific repository identified
    ('ERROR:? +No repository found at https://alfred\.diamond\.ac\.uk/', 'Server error'),  # text = no specific repository identified
    ('org\.eclipse\.equinox\.p2\.core\.ProvisionException: No repository found at', 'Network error'),  # text = no specific repository identified
    )

PROJECT_ERROR_PATTERNS = ( # Error messages that identify an error reported by Buckminster
    ('ERROR\s+\[\d+\]\s:\sError connecting project (\S+),', 1),  # 1 = first match group is the project
    )

BUCKMINSTER_BUG_ERROR_PATTERNS = ( # Error messages that identify an intermittent Buckminster bug
    ('ERROR\s+\[\d+\]\s:\sjava\.lang\.ArrayIndexOutOfBoundsException: -1', 'Buckminster intermittent bug - try rerunning'),  # https://bugs.eclipse.org/bugs/show_bug.cgi?id=372470
    ('ERROR\s+\[\d+\]\s:\sConnecting Git team provider failed\. See log for details\.', 'Buckminster intermittent failure - try rerunning'),
    ('ERROR\s+\[\d+\]\s:\sjava\.lang\.IllegalStateException: Preference node ".+" has been removed.', 'Buckminster intermittent failure - try rerunning'),
    )

COMPILE_ERROR_DUE_TO_BUCKMINSTER_BUG_PATTERNS = ( # Error messages that identify a compile error caused by a prior intermittent Buckminster bug
    # compile error caused by earlier materialize bug that silently fails to import some project into the workspace
    ("Bundle 'uk.ac.gda.(api|core)' cannot be resolved", 'Compile errors due to earlier intermittent materialize bug (uk.ac.gda.api/core not recognised)'),
    )

SYSTEM_PROBLEM_ERROR_PATTERNS = ( # Error messages that identify a problem with the environment; e.g. resource depletion
    ('java\.lang\.OutOfMemoryError: unable to create new native thread', 'System problem - out of threads'),  # sometimes occurs in Jenkins
    )

OUTPUT_LINES_TO_SUPPRESS = (
    "INFO:  importproxysettings\n",
    "WARN:  There are no proxy settings to import.\n",
    'SLF4J: Failed to load class "org.slf4j.impl.StaticLoggerBinder".\n',
    "SLF4J: Defaulting to no-operation (NOP) logger implementation\n",
    "SLF4J: See http://www.slf4j.org/codes.html#StaticLoggerBinder for further details.\n"  # once last item seen in the output, we stop scanning for matches
    )

GERRIT_REPOSITORIES = {
    # repository                     url_part:     Gerrit URL (after prefix)
    #                                keep_origin:  if current repo origin is not Gerrit, don't change it to point to Gerrit (Gerrit version had repo history rewritten)
    #                                must_use_ssh: Must use SSH (repo is not public, hence anonymous access via HTTPS not available)
    'daq-platform.git'           : {'url_part': 'daq/daq-platform.git'},
    'dawn-commandserver.git'     : {'url_part': 'scisoft/dawn-commandserver.git'},
    'dawn-common.git'            : {'url_part': 'scisoft/dawn-common.git'},
    'dawn-doc.git'               : {'url_part': 'scisoft/dawn-doc.git'},
    'dawn-hdf.git'               : {'url_part': 'scisoft/dawn-hdf.git'},
    'dawn-mx.git'                : {'url_part': 'scisoft/dawn-mx.git'},
    'dawn-third.git'             : {'url_part': 'scisoft/dawn-third.git'},
    'dawn-ui.git'                : {'url_part': 'scisoft/dawn-ui.git'},
    'dawnsci.git'                : {'url_part': 'scisoft/dawnsci.git',
                                    'keep_origin': True},
    'diamond-cpython.git'        : {'url_part': 'diamond/diamond-cpython.git'},
    'diamond-jacorb.git'         : {'url_part': 'diamond/diamond-jacorb.git'},
    'diamond-jython.git'         : {'url_part': 'diamond/diamond-jython.git'},
    'diamond-miniconda.git'      : {'url_part': 'diamond/diamond-miniconda.git'},
    'diamond-springframework.git': {'url_part': 'diamond/diamond-springframework.git'},
    'Opt-ID.git'                 : {'url_part': 'diamond/Opt-ID.git'},
    'scanning.git'               : {'url_part': 'eclipse/scanning.git'},
    'gda-bimorph.git'            : {'url_part': 'gda/gda-bimorph.git'},
    'gda-common.git'             : {'url_part': 'gda/gda-common.git'},
    'gda-common-rcp.git'         : {'url_part': 'gda/gda-common-rcp.git'},
    'gda-core.git'               : {'url_part': 'gda/gda-core.git'},
    'gda-devices.git'            : {'url_part': 'gda/gda-devices.git'},
    'gda-devices-cirrus.git'     : {'url_part': 'gda/gda-devices-cirrus.git'},
    'gda-devices-mythen.git'     : {'url_part': 'gda/gda-devices-mythen.git'},
    'gda-devices-pco.git'        : {'url_part': 'gda/gda-devices-pco.git'},
    'gda-devices-peem.git'       : {'url_part': 'gda/gda-devices-peem.git'},
    'gda-devices-pixium.git'     : {'url_part': 'gda/gda-devices-pixium.git'},
    'gda-devices-prosilica.git'  : {'url_part': 'gda/gda-devices-prosilica.git'},
    'gda-diamond.git'            : {'url_part': 'gda/gda-diamond.git'},
    'gda-dls-beamlines-i19.git'  : {'url_part': 'gda/gda-dls-beamlines-i19.git'},
    'gda-dls-beamlines-xas.git'  : {'url_part': 'gda/gda-dls-beamlines-xas.git'},
    'gda-dls-excalibur.git'      : {'url_part': 'gda/gda-dls-excalibur.git'},
    'gda-epics.git'              : {'url_part': 'gda/gda-epics.git'},
    'gda-hrpd.git'               : {'url_part': 'gda/gda-hrpd.git'},
    'gda-imca-cat.git'           : {'url_part': 'gda/gda-imca-cat.git'},
    'gda-legacy.git'             : {'url_part': 'gda/gda-legacy.git'},
    'gda-mt.git'                 : {'url_part': 'gda/gda-mt.git',
                                    'must_use_ssh': True,
                                    'keep_origin': True},
    'gda-mx.git'                 : {'url_part': 'gda/gda-mx.git',
                                    'must_use_ssh': True},
    'gda-nexus.git'              : {'url_part': 'gda/gda-nexus.git'},
    'gda-pes.git'                : {'url_part': 'gda/gda-pes.git'},
    'gda-tango.git'              : {'url_part': 'gda/gda-tango.git'},
    'gda-tomography.git'         : {'url_part': 'gda/gda-tomography.git'},
    'gda-video.git'              : {'url_part': 'gda/gda-video.git'},
    'gda-xas-core.git'           : {'url_part': 'gda/gda-xas-core.git'},
    'gphl-abstract-beamline.git' : {'url_part': 'gphl/gphl-abstract-beamline.git',
                                    'must_use_ssh': True},
    'gphl-astra.git'             : {'url_part': 'gphl/gphl-astra.git',
                                    'must_use_ssh': True},
    'gphl-sdcp-common.git'       : {'url_part': 'gphl/gphl-sdcp-common.git',
                                    'must_use_ssh': True},
    'scisoft-2ddpr.git'          : {'url_part': 'scisoft/scisoft-2ddpr.git'},
    'scisoft-cbflib.git'         : {'url_part': 'scisoft/scisoft-cbflib.git'},
    'scisoft-core.git'           : {'url_part': 'scisoft/scisoft-core.git'},
    'scisoft-peema.git'          : {'url_part': 'scisoft/scisoft-peema.git',
                                    'must_use_ssh': True},
    'scisoft-ptychography.git'   : {'url_part': 'scisoft/scisoft-ptychography.git',
                                    'must_use_ssh': True},
    'scisoft-spectroscopy.git'   : {'url_part': 'scisoft/scisoft-spectroscopy.git',
                                    'must_use_ssh': True},
    'scisoft-ui.git'             : {'url_part': 'scisoft/scisoft-ui.git'},
    'scisoft-ws.git'             : {'url_part': 'scisoft/scisoft-ws.git',
                                    'must_use_ssh': True},
    'richbeans.git'              : {'url_part': 'richbeans.git'},
    'wychwood.git'               : {'url_part': 'gda/wychwood.git'},
    }

GERRIT_URI_HTTPS = 'https://gerrit.diamond.ac.uk/'      # typically used for anonymous clone (we use SSH for authenticated clone)
GERRIT_URI_SSH   = 'ssh://gerrit.diamond.ac.uk:29418/'  # used for authenticated clone and push

class GitConfigParser(ConfigParser.RawConfigParser):
    """ Subclass of the regular ConfigParser that handles the leading tab characters in .git/config files """
    def readgit(self, filename):
        with open(filename, 'r') as config_file:
            text = config_file.read()
        self.readfp(StringIO.StringIO(text.replace('\t', '')), filename)

class PewmaException(Exception):
    """ Exception class to handle case when the setup does not support the requested operation. """
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return self.value

###############################################################################
#  Main class                                                                 #
###############################################################################

class PewmaManager(object):

    def __init__(self):
        self.system = platform.system()
        self.isLinux = self.system == 'Linux'
        self.isWindows = self.system == 'Windows'
        # string describing the current platform in PLATFORMS_AVAILABLE syntax
        self.platform = {'Linuxx86_64': 'linux,gtk,x86_64',
                         'Darwin86_64': 'macosx,cocoa,x86_64',
                         'Windowsx86_64': 'win32,win32,x86_64',
                         }['%s%s' % (self.system, platform.machine())]
        self.java_inspected = False
        self.java_default_tmpdir = None
        self.java_version_current = None
        self.valid_java_versions = None
        self.executable_locations = {}

        # when running at DLS, we might want to set the Linux group to "dls_dasc" on directories that we create
        self.group_dls_dasc_gid = None  # the numeric group id for group dls_dasc
        if self.isLinux:
            self.user_euid = os.geteuid()                                  # effective running user id
            try:
                self.user_uname = pwd.getpwuid(self.user_euid).pw_name     # effective running user name
            except (KeyError) as e:
                self.user_uname = '?'
            try:
                self.group_dls_dasc_gid = grp.getgrnam('dls_dasc').gr_gid  # the numeric group id for group dls_dasc
            except (KeyError) as e:
                pass  # group name 

        self.valid_actions_with_help = (
            # 1st item in tuple is the action verb
            # 2nd item in tuple is the action special handler (either "ant" or None)
            # 3rd item in tuple is a boolean, set to True if the elapsed time for this action is to be logged to Graylog
            # 4rd item in tuple is a tuple of help text lines
            ('setup', None, False,
                ('setup [<category> [<version>] | <cquery>]',
                 'Set up a new workspace, with the target platform defined, but otherwise empty',
                 '(parameters are the same as for the "materialize" action)',
                 )),
            ('materialize', None, True,
                ('materialize {<component> ...} [<category> [<version>] | <cquery>]',
                 'Materialize component(s) and their dependencies into a new or existing workspace',
                 'Category can be one of "%s"' % '/'.join(CATEGORIES_AVAILABLE),
                 'Version defaults to master',
                 'CQuery is only required if you don\'t want to use Category or Category+Version',
                 )),
            ('add-diamond-cpython', None, True,
                ('add-diamond-cpython {<platform> ...}',
                 'Add diamond-cpython install files to DAWN\'s uk.ac.diamond.cpython.<platform> project(s)',
                 'Platform can be something like linux64/mac64/win64/all (defaults to current platform)',
                 )),
            ('print-workspace-path', None, False,
                ('print-workspace-path',
                 'Prints the workspace directory path (explicit or determined)',
                 )),
            ('get-branches-expected', None, False,
                ('get-branches-expected <component> [<category> [<version>] | <cquery>]',
                 'Determine the CQuery to use, and return from it a list of repositories and branches',
                 )),
            ('gerrit-config', None, False, ('gerrit-config', 'Switch applicable repositories to origin Gerrit and configure for Eclipse',)),
            ('git', None, True, ('git <command>', 'Issue "git <command>" for all git clones (escape any quotes in the command with a \\)',)),
            ('clean', None, True, ('clean', 'Clean the workspace',)),
            ('bmclean', None, True, ('bmclean <site>', 'Clean previous buckminster output',)),
            ('build', None, True, ('build', '[alias for buildthorough]',)),
            ('buildthorough', None, True, ('buildthorough', 'Build the workspace (do full build if first incremental build fails)',)),
            ('buildinc', None, True, ('buildinc', 'Build the workspace (incremental build)',)),
            ('target', None, False, ('target', 'List target definitions known in the workspace',)),
            ('target', None, False, ('target path/to/name.target', 'Set the target platform for the workspace',)),
            ('sites', None, False, ('sites', 'List the available site projects in the workspace',)),
            ('site.p2', None, True,
                ('site.p2 <site>',
                 'Build the workspace and an Eclipse p2 site',
                 'Site can be omitted if there is just one site project, and abbreviated in most other cases',
                )),
            ('site.p2.zip', None, True,
                ('site.p2.zip <site>',
                 'Build the workspace and an Eclipse p2 site, then zip the p2 site',
                 'Site can be omitted if there is just one site project, and abbreviated in most other cases',
                )),
            ('product', None, True,
                ('product <site> [ <platform> ... ]',
                 'Build the workspace and an Eclipse product',
                 'Site can be omitted if there is just one site project, and abbreviated in most other cases',
                 'Platform can be something like linux64/mac64/win64/all (defaults to current platform)',
                )),
            ('product.zip', None, True,
                ('product.zip <site> [ <platform> ... ]',
                 'Build the workspace and an Eclipse product, then zip the product',
                )),
            ('tests-clean', self._iterate_ant, False, ('tests-clean', 'Delete test output and results files from JUnit/JyUnit tests',)),
            ('junit-tests', self._iterate_ant, True, ('junit-tests', 'Run Java JUnit tests for all (or selected) projects',)),
            ('jyunit-tests', self._iterate_ant, True, ('jyunit-tests', 'Runs JyUnit tests for all (or selected) projects',)),
            ('all-tests', self._iterate_ant, True, ('all-tests', 'Runs both Java and JyUnit tests for all (or selected) projects',)),
            ('corba-make-jar', self._iterate_ant, False, ('corba-make-jar', '(Re)generate the corba .jar(s) in all or selected projects',)),
            ('corba-validate-jar', self._iterate_ant, False, ('corba-validate-jar', 'Check that the corba .jar(s) in all or selected plugins match the source',)),
            ('corba-clean', self._iterate_ant, False, ('corba-clean', 'Remove temporary files from workspace left over from corba-make-jar',)),
            ('dummy', self._iterate_ant, False, ()),
            ('developer-test', None, False, ()),
            )

        self.valid_actions = dict((action, (handler, attempt_graylog)) for (action, handler, attempt_graylog, _) in self.valid_actions_with_help)

    def setup_standard_logging(self):
        # create logger with console handler, and formatter to match
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(1)
        console_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S")
        self.logging_console_handler = logging.StreamHandler()
        self.logging_console_handler.setFormatter(console_formatter)
        self.logger.addHandler(self.logging_console_handler)

    def setup_graylog_logging(self):
        # create logger with Graylog handler, and formatter to match
        # we use a separate logger, rather than an additional handler on the standard logger
        if self.options.no_graylog:
            return False  # command line option said not to write to Graylog
        if not socket.getfqdn().endswith('.diamond.ac.uk'):
            return False  # not at Diamond Light Source
        try:
            from pkg_resources import require
            require('pygelf')
            from pygelf import GelfUdpHandler
        except:
            return False  # pygelf not installed in the version of Python we are running

        self.logger_graylog = logging.getLogger(__name__ + '-graylog')
        self.logger_graylog.setLevel(1)
        graylog_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S")
        action_index = sys.argv.index(self.action)
        self.logging_graylog_handler = GelfUdpHandler(
            host = GRAYLOG_SERVER,
            port = GRAYLOG_PORT,
            _application_name = 'pewma',
            _username = getpass.getuser(),
            _workspace_loc = self.workspace_loc,
            _pewma_options = ' '.join(sys.argv[1:action_index]),
            _pewma_action = '%s %s' % (self.action, ' '.join(self.arguments)),
            include_extra_fields = True)
        self.logging_graylog_handler.setFormatter(graylog_formatter)
        self.logger_graylog.addHandler(self.logging_graylog_handler)
        self.logger.debug('Performance data will be logged to Graylog')
        return True

    def _get_full_uri(self, part):
        return self.options.dls_buckminster_uri.strip('/') + '/' + part

    def _determine_workspace_location_when_not_specified(self):
        # If the caller does not specify the workspace location, work one out, using the following tests in order:
        # (1) if there is no current directory, do not set a default
        # (2) if the current directory, or any or its parents, is an Eclipse workspace, make that the default
        #     (if the current directory, or any or its parents, is named .*_git, ignore the _git part)
        #     (if the current directory, or any or its parents, contains both .metadata and a workspace or workspace_git, abandon)
        # (3) if the current directory is called "workspace", and is empty, make it the default
        # (4) if the current directory is called "workspace", and is not empty, do not set a default
        # (5) if the current directory contains a subdirectory called "workspace" that is an Eclipse workspace, make that the default
        # (6) if the current directory contains a subdirectory called "workspace" that is empty, make that the default
        # (7) if the current directory contains a subdirectory called "workspace", do not set a default
        # (8) if the current directory does not contain a subdirectory called "workspace", use new directory <cwd>/workspace as the default
        # (9) Don't have a default workspace location
        # Note: this is not called if the user explicitly specified -w/--workspace on the command line

        try:
            candidate = cwd = os.getcwd()
        except (OSError) as e:
            # Case 1 - no current directory
            self.logger.warn('Current working directory invalid')
        else:
            while candidate != os.path.dirname(candidate):  # if we are not at the filesystem root (this is a platform independent check)
                if not candidate.endswith('_git'):
                    self.workspace_loc = (os.path.isdir( os.path.join( candidate, '.metadata')) and candidate or None)
                else:
                    self.workspace_loc = (os.path.isdir( os.path.join( candidate[:-4], '.metadata')) and candidate[:-4] or None)
                if self.workspace_loc:
                    # Case 2 - current directory, or a parent, is an Eclipse workspace
                    if os.path.exists( os.path.join(self.workspace_loc, 'workspace')):
                        self.logger.error('Both .metadata/ and workspace/ exist within ' + self.workspace_loc)
                        self.workspace_loc = None
                    elif os.path.exists( os.path.join(self.workspace_loc, 'workspace_git')):
                        self.logger.error('Both .metadata/ and workspace_git/ exist within ' + self.workspace_loc)
                        self.workspace_loc = None
                    break
                candidate = os.path.dirname(candidate)
            else:
                if (os.path.basename(cwd) == 'workspace'):
                    # Case 3; Case 4 - current directory is named "workspace"
                    if not os.listdir(cwd):
                        # Case 3 - current directory is named "workspace" and is empty
                        self.workspace_loc = cwd
                    else:
                        pass  # Case 4 - current directory is named "workspace" and is not empty
                else:
                    candidate = os.path.join(cwd, 'workspace')
                    if os.path.isdir(candidate):
                        # Case 5; Case 6; Case 7; Case 8 - current directory contains a subdirectory "workspace"
                        if os.path.isdir( os.path.join( candidate, '.metadata')):
                            self.workspace_loc = candidate  # Case 5 - subdirectory "workspace" is an Eclipse workspace
                        elif not os.listdir(candidate):
                            self.workspace_loc = candidate  # Case 6 - subdirectory "workspace" is empty
                        else:
                            pass #  Case 7 - subdirectory "workspace" is not empty
                    else:
                        # Case 8 - subdirectory "workspace" does not exist
                        self.workspace_loc = candidate

        if not self.workspace_loc:
            raise PewmaException('ERROR: the "--workspace" option must be specified. ' +
                                 os.path.basename(sys.argv[0]) +
                                ' could not determine what workspace to use (based on the current directory).')
        assert os.path.isabs(self.workspace_loc)


    def define_parser(self):
        """ Define all the command line options and how they are handled. """

        self.parser = optparse.OptionParser(usage="usage: %prog [options] action [arguments ...]", add_help_option=False,
            description="For more information, see the Infrastructure guide at https://alfred.diamond.ac.uk/documentation/")
        self.parser.disable_interspersed_args()
        self.parser.formatter.help_position = self.parser.formatter.max_help_position = 46  # improve look of help
        if 'COLUMNS' not in os.environ:  # typically this is not passed from the shell to the child process (Python)
            self.parser.formatter.width = 120  # so avoid the default of 80 and assume a wider terminal (improve look of help)

        group = optparse.OptionGroup(self.parser, "Workspace options")
        group.add_option('-w', '--workspace', dest='workspace', type='string', metavar='<dir>', default=None,
                               help='Workspace location')
        group.add_option('--delete', dest='delete', action='store_true', default=False,
                               help='First completely delete current workspace/ and workspace_git/')
        group.add_option('--recreate', dest='recreate', action='store_true', default=False,
                               help='First completely delete current workspace/, but keep any workspace_git/')
        group.add_option('--tp-recreate', dest='tp_recreate', action='store_true', default=False,
                               help='First completely delete current tp/, but keep everything else')
        self.parser.add_option_group(group)

        group = optparse.OptionGroup(self.parser, "Materialize options")
        group.add_option('--dls-buckminster-uri', dest='dls_buckminster_uri', metavar='URI',
                         default=DLS_BUCKMINSTER_URI,
                         help=optparse.SUPPRESS_HELP)
        if self.isLinux:
            group.add_option('--directories.groupname', dest='directories_groupname', type='string', metavar='<groupname>',
                             default='dls_dasc' if self.group_dls_dasc_gid else None,
                             help='Linux group to set on directories that are created (default: %default)')
        group.add_option('-l', '--location', dest='download_location', choices=('diamond', 'public'), metavar='<location>',
                         help='Download location ("diamond" or "public")')
        group.add_option('--maxParallelMaterializations', dest='maxParallelMaterializations', type='int', metavar='<value>',
                         help='Override Buckminster default')
        group.add_option('--maxParallelResolutions', dest='maxParallelResolutions', type='int', metavar='<value>',
                         help='Override Buckminster default')
        group.add_option('--prepare-jenkins-build-description-on-error',
                         dest='prepare_jenkins_build_description_on_error', action='store_true', default=False,
                         help=optparse.SUPPRESS_HELP)
        group.add_option('--sjvc', '--skip-java-version-check',
                         dest='skip_java_version_check', action='store_true', default=False,
                         help=optparse.SUPPRESS_HELP)
        self.parser.add_option_group(group)

        group = optparse.OptionGroup(self.parser, "Get-branches-expected options")
        group.add_option('--cquery.branches.file', dest='cquery_branches_file', type='string', metavar='<path>',
                               default='cquery-branches-file.txt',
                               help='Report file, relative to current directory if not absolute (default: %default)')
        self.parser.add_option_group(group)

        group = optparse.OptionGroup(self.parser, "Build/Product options")
        group.add_option('--scw', '--suppress-compile-warnings', dest='suppress_compile_warnings', action='store_true', default=False,
                               help='Don\'t print compiler warnings')
        group.add_option('--assume-build', dest='assume_build', action='store_true', default=False, help='Skip explicit build when running "site.p2" or "product" actions')
        group.add_option('--recreate-symlink', dest='recreate_symlink', action='store_true', default=False,
                               help='Create or update the "client" or "server" symlink to the built product (linux64 only)')
        group.add_option('--buckminster.properties.file', dest='buckminster_properties_file', type='string', metavar='<path>',
                         help='Properties file, relative to site project if not absolute (default: filenames looked for in order: buckminster.properties, buckminster.beamline.properties)')
        group.add_option('--buckminster.root.prefix', dest='buckminster_root_prefix', type='string', metavar='<path>',
                         help='Prefix for buckminster.output.root and buckminster.temp.root properties')
        self.parser.add_option_group(group)

        group = optparse.OptionGroup(self.parser, "Test/Corba options")
        group.add_option('--include', dest='project_includes', action='append', metavar='<pattern>,<pattern>,...', default=[],
                               help='Only process project names matching one or more of the glob patterns')
        group.add_option('--exclude', dest='project_excludes', action='append', metavar='<pattern>,<pattern>,...', default=[],
                               help='Do not process project names matching any of the glob patterns')
        default_GDALargeTestFilesLocation = '/dls_sw/dasc/GDALargeTestFiles/'  # location at Diamond
        if not os.path.isdir(default_GDALargeTestFilesLocation):
            default_GDALargeTestFilesLocation=""
        group.add_option("--GDALargeTestFilesLocation", dest="GDALargeTestFilesLocation", type="string", metavar=" ", default=default_GDALargeTestFilesLocation,
                         help="Default: %default")
        self.parser.add_option_group(group)

        group = optparse.OptionGroup(self.parser, "General options")
        group.add_option('-D', dest='system_property', action='append', metavar='key=value', default=[],
                               help='Pass a system property to Buckminster or Ant')
        group.add_option('-J', dest='jvmargs', action='append', metavar='jvmarg', default=[],
                               help='Pass an additional JVM argument')
        group.add_option('-h', '--help', dest='help', action='store_true', default=False, help='Show help information and exit')
        group.add_option('-n', '--dry-run', dest='dry_run', action='store_true', default=False,
                               help='Log the actions to be done, but don\'t actually do them')
        group.add_option('--workspace-must-exist', dest='workspace_must_exist', action='store_true', default=False,
                               help='Fail if the workspace directory does not already exist')
        group.add_option('--workspace-must-not-exist', dest='workspace_must_not_exist', action='store_true', default=False,
                               help='Fail if the workspace directory already exists')
        group.add_option('-s', '--script-file', dest='script_file', type='string', metavar='<path>',
                               default='pewma-script.txt',
                               help='Script file, relative to workspace (default: %default)')
        group.add_option('-q', '--quiet', dest='quiet', action='store_true', default=False, help='Be less verbose')
        group.add_option('-Y', '--answer-yes', dest='answer_yes', action='store_true', default=False, help='No interactive prompts (assume YES if appropriate)')
        group.add_option('-N', '--answer-no', dest='answer_no', action='store_true', default=False, help='No interactive prompts (assume NO if appropriate)')
        group.add_option('--log-level', dest='log_level', type='choice', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], metavar='<level>',
                               default='INFO', help='Logging level (default: %default)')
        group.add_option('--debug-options-file', dest='debug_options_file', type='string', metavar='<path>',
                               help='File containing debug options for Buckminster')
        group.add_option('-g', '--no-graylog', dest='no_graylog', action='store_true', default=False, help='Never log to DLS Graylog, even if available')
        self.parser.add_option_group(group)

        group = optparse.OptionGroup(self.parser, "Git options (when using the git subcommand)")
        group.add_option('-p', '--prefix', dest='repo_prefix', action='store_true', default=False, help='Prefix first line of git command output with the repo directory name')
        group.add_option('--gerrit-only', dest='gerrit_only', action='store_true', default=False, help='Apply git command only to Gerrit-based repositories')
        group.add_option('--non-gerrit-only', dest='non_gerrit_only', action='store_true', default=False, help='Apply git command to only to non-Gerrit-based repositories')
        group.add_option('--repo-include', dest='repo_includes', type='string', metavar='<pattern>,<pattern>,...', default="",
                               help='Only process repository names matching one or more of the glob patterns')
        group.add_option('--repo-exclude', dest='repo_excludes', type='string', metavar='<pattern>,<pattern>,...', default="",
                               help='Do not process repository names matching any of the glob patterns')
        group.add_option('--max-git-output', dest='max_git_output', type='int', metavar='<value>', default=30000,
                               help='Maximum characters git output per repository (0=unlimited)')
        self.parser.add_option_group(group)


    def setup_workspace(self):
        # create the workspace if it doesn't exist, initialise the workspace if it is not set up
        # note: only applies to workspace, not workspace_git

        if self.options.delete or self.options.recreate:
            assert self.action in ('setup', 'materialize')
            self.delete_directory(self.workspace_loc, "workspace directory")
            if self.options.delete:
                self.delete_directory(self.workspace_git_loc, "workspace_git directory")
        elif self.options.tp_recreate:
            assert self.action == 'materialize'
            self.delete_directory(os.path.join(self.workspace_loc, "tp"), "tp directory")

        need_to_create_workspace = True
        if os.path.isdir(self.workspace_loc):
            metadata_exists = os.path.exists( os.path.join(self.workspace_loc, '.metadata'))
            if metadata_exists and not os.path.isdir(os.path.join(self.workspace_loc, '.metadata', '.plugins')):
                raise PewmaException('ERROR: Workspace already exists but is corrupt (invalid .metadata/), please delete: "%s"' % (self.workspace_loc,))
            tp_exists = os.path.exists( os.path.join(self.workspace_loc, 'tp'))
            if tp_exists and not os.path.isfile(os.path.join(self.workspace_loc, 'tp', '.project')):
                raise PewmaException('ERROR: Workspace already exists but is corrupt (invalid tp/), please delete: "%s"' % (self.workspace_loc,))

            if metadata_exists:
                need_to_create_workspace = False
                if not (tp_exists or self.options.tp_recreate):
                    raise PewmaException('ERROR: Workspace already exists but tp/ does not exist, and --tp-recreate not specified for: "%s"' % (os.path.join(self.workspace_loc, 'tp'),))
                self.logger.info('Workspace already exists "%s"' % (self.workspace_loc,))
        else:
            self.logger.info('%sCreating workspace directory "%s"' % (self.log_prefix, self.workspace_loc,))
            if not self.options.dry_run:
                os.makedirs(self.workspace_loc)
                self._set_linux_group(self.workspace_loc)

        if self.workspace_git_loc and os.path.isdir(self.workspace_git_loc):
            git_count_at_start = len(self._get_git_directories())
            if git_count_at_start:
                self.logger.info('Using %s existing .git repositories (which will not be updated) found in "%s"' % (git_count_at_start, self.workspace_git_loc,))
            self._set_linux_group(self.workspace_git_loc)
        else:
            self.logger.info('%sCreating workspace_git directory "%s"' % (self.log_prefix, self.workspace_git_loc,))
            if not self.options.dry_run:
                os.mkdir(self.workspace_git_loc)
                self._set_linux_group(self.workspace_git_loc)

        if need_to_create_workspace or (not tp_exists):
            template_zip = os.path.join( self.workspace_loc, self.template_name )
            self.download_workspace_template(self._get_full_uri('templates/' + self.template_name), template_zip)
            if need_to_create_workspace:
                self.unzip_workspace_template(template_zip, None, self.workspace_loc)
            else:
                self.unzip_workspace_template(template_zip, 'tp/', self.workspace_loc)
            self.logger.info('%sDeleting "%s"' % (self.log_prefix, template_zip,))
            if not self.options.dry_run:
                os.remove(template_zip)


    def add_cquery_to_history(self, cquery_to_use):
        ''' remember the CQuery used, for future "File --> Open a Component Query" in the IDE
        '''

        if self.options.dry_run:
            return
        org_eclipse_buckminster_ui_prefs_loc = os.path.join(self.workspace_loc, '.metadata', '.plugins',
          'org.eclipse.core.runtime', '.settings', 'org.eclipse.buckminster.ui.prefs')
        cquery_to_add = self._get_full_uri('base/' + cquery_to_use).replace(':', '\:')  # note the escaped : as per Eclipse's file format
        if not os.path.exists(org_eclipse_buckminster_ui_prefs_loc):
            # create a new org.eclipse.buckminster.ui.prefs file with the CQuery history
            with open(org_eclipse_buckminster_ui_prefs_loc, 'w') as oebup_file:
                oebup_file.write('eclipse.preferences.version=1\n')
                oebup_file.write('lastCQueryURLs=%s\n' % (cquery_to_add,))
        else:
            # update the existing org.eclipse.buckminster.ui.prefs file with the CQuery history
            replacement_lines = []
            lastCQueryURLs_found = False
            file_rewrite_required = False
            with open(org_eclipse_buckminster_ui_prefs_loc, 'r') as oebup_file:
                for line in oebup_file.readlines():
                    if not line.startswith('lastCQueryURLs='):
                        replacement_lines += line
                    else:
                        lastCQueryURLs_found = True
                        if line.startswith('lastCQueryURLs=' + cquery_to_add):
                            # the current CQuery is the same as the previous most-recent, so the CQuery history remains unchanged 
                            replacement_lines += line
                        else:
                            # the current CQuery is different from the previous most-recent, so update the CQuery history
                            replacement = line.replace(';' + cquery_to_add, '')
                            replacement = 'lastCQueryURLs=%s' % (cquery_to_add,) + ';' + replacement[len('lastCQueryURLs='):]
                            replacement_lines += replacement
                            file_rewrite_required = True
            if not lastCQueryURLs_found:
                replacement_contents += 'lastCQueryURLs=%s\n' % (cquery_to_add,)
                file_rewrite_required = True
            if file_rewrite_required:
                if not self.options.dry_run:
                    with open(org_eclipse_buckminster_ui_prefs_loc, 'w') as oebup_file:
                        for line in replacement_lines:
                            oebup_file.write(line)
                self.logger.debug('%sUpdated "%s" with CQuery %s' % (self.log_prefix, org_eclipse_buckminster_ui_prefs_loc, cquery_to_use))


    def _add_string_substitution_variable_to_workspace(self, variable_name, variable_value, variable_description=None):
        ''' Save a string in "Window --> Preferences --> Run/Debug --> String Substitution"
            If variable_value 'is None' (n.b. not the same as '') , delete the entry
            If variable_description 'is None' (n.b. not the same as '') , don't change any existing description
        '''
        self.logger.debug('Setting %s=%s %s' % (variable_name, variable_value, variable_description))
        assert variable_name
        if self.options.dry_run:
            return

        org_eclipse_core_variables_prefs_loc = os.path.join(self.workspace_loc, '.metadata', '.plugins',
          'org.eclipse.core.runtime', '.settings', 'org.eclipse.core.variables.prefs')
        if not os.path.exists(org_eclipse_core_variables_prefs_loc):
            if variable_value is None:
                return
            replacement_lines = ['eclipse.preferences.version=1\n',
                                 r'org.eclipse.core.variables.valueVariables=<?xml version\="1.0" encoding\="UTF-8" standalone\="no"?>\n' +
                                 r'<valueVariables>\n' +
                                 r'<valueVariable description\="' + variable_description +
                                 r'" name\="' + variable_name +
                                 r'" readOnly\="false" value\="' + variable_value +
                                 r'"/>\n' +
                                 r'</valueVariables>\n' + '\n'
                                ]
            file_rewrite_required = True
        else:
            match_existing = (
                r'^(?P<start>org\.eclipse\.core\.variables\.valueVariables=.+?<valueVariables>.+?)' +
                r'<valueVariable description\\="(?P<description>.*?)" ' +
                r'name\\="' + variable_name + r'" ' +
                r'readOnly\\="(?P<readonly>.*?)" ' +
                r'value\\="(?P<value>.*?)"/>\\n' +
                r'(?P<finish>.*</valueVariables>.*?)$')
            match_not_existing = (
                r'^(?P<start>org\.eclipse\.core\.variables\.valueVariables=.+?<valueVariables>.+?)' +
                r'(?P<finish></valueVariables>.*?)$')
            replacement_lines = []
            file_rewrite_required = False
            with open(org_eclipse_core_variables_prefs_loc, 'r') as oecvp_file:
                for line in oecvp_file:
                    if not line.startswith('org.eclipse.core.variables.valueVariables='):
                        replacement_lines.append(line)
                        continue

                    m = re.match(match_existing, line)
                    if m:
                        if m.group('value') == variable_value:
                            if (variable_description is None) or (m.group('description') == variable_description):
                                break  # nothing changed, and don't need to look at any more lines 
                        # the value and/or the description has changed
                        replacement = (m.group('start') +
                                       r'<valueVariable description\="' + m.group('description') + '" ' +
                                       r'name\="' + variable_name + r'" ' +
                                       r'readOnly\="' + m.group('readonly') + r'" ' +
                                       r'value\="' + variable_value + r'"/>\n' +
                                       m.group('finish') + '\n')
                    else:
                        m = re.match(match_not_existing, line)
                        if m:
                            replacement = (m.group('start') +
                                           r'<valueVariable description\="' + variable_description + '" ' +
                                           r'name\="' + variable_name + r'" ' +
                                           r'readOnly\="false" ' +
                                           r'value\="' + variable_value + r'"/>\n' +
                                           m.group('finish') + '\n')
                        else:
                            raise PewmaException('%sInternal error matching "%s"' % (self.log_prefix, line))
                    self.logger.log(5, line)
                    self.logger.log(5, replacement)
                    replacement_lines.append(replacement)
                    file_rewrite_required = True

        if file_rewrite_required:
            if not self.options.dry_run:
                with open(org_eclipse_core_variables_prefs_loc, 'w') as oecvp_file:
                    for line in replacement_lines:
                        oecvp_file.write(line)
            self.logger.debug('%sUpdated %s with "%s=%s" %s' %
                             (self.log_prefix, org_eclipse_core_variables_prefs_loc, variable_name, variable_value, variable_description))


    def delete_directory(self, directory, description):
        if directory and os.path.isdir(directory):
            if self.options.answer_no:
                raise PewmaException('%sWill not delete directory "%s". Abandoning.' % (self.log_prefix, directory))
            if not (self.options.answer_yes or
                   (os.environ.get('USER') == 'dlshudson') or  # we are Jenkins
                   (all([os.environ.get(var) for var in ('BUILD_CAUSE', 'BUILD_URL', 'JENKINS_HOME')]))  # if all these envvars exist, assume we are Jenkins
                   ):
                # prompt to make sure the user really wants this directory deleted
                response = raw_input('$$ %sDelete "%s" [y/n(default)]: ' % (self.log_prefix, directory)).strip().lower()
                if not response.startswith('y'):
                    raise PewmaException('Will not delete directory. Abandoning.')
            cwd = os.getcwd()
            if cwd and os.path.realpath(cwd) == os.path.realpath(directory):
                raise PewmaException('Cannot delete current directory. Abandoning.')
            self.logger.info('%sDeleting %s "%s"' % (self.log_prefix, description, directory,))
            if self.options.dry_run:
                return
            # shutil.rmtree(directory)  # does not work under Windows if there are read-only files in the directory, such as.svn\all-wcprops
            if self.isLinux:
                retcode = subprocess.call(('rm', '-rf', directory), shell=False)
            elif self.isWindows:
                retcode = subprocess.call(('rmdir', '/s', '/q', directory), shell=True)
            else:
                self.logger.error('Could not delete directory: platform "%s" not recognised' % (self.system,))
                retcode = 1
            if retcode:
                raise PewmaException('Error deleting directory "%s". Abandoning.' % (directory,))


    def download_workspace_template(self, source, destination):
        if self.options.dry_run:
            self.logger.info('%sDownloading "%s" to "%s"' % (self.log_prefix, source, destination))
            return

        # open the URL
        try:
            resp = urllib2.urlopen(source, timeout=30)
        except (urllib2.URLError, urllib2.HTTPError, socket.timeout) as e:
            self.logger.error('Error downloading from "%s": %s' % (source, str(e)))
            if self.options.prepare_jenkins_build_description_on_error:
                text = 'append-build-description: Failure downloading template workspace (probable network issue)'
                print(text)
            raise PewmaException('ERROR: Workspace template download failed (network or proxy error, possibly transient): please retry')

        # read the data (small enough to do in one chunk)
        self.logger.info('Downloading %s bytes from "%s" to "%s"' % (resp.info().get('content-length', '<unknown>'), resp.geturl(), destination))
        try:
            templatedata = resp.read()
        except Exception as e:
            self.logger.error('Error downloading from "%s": %s' % (source, str(e)))
            if self.options.prepare_jenkins_build_description_on_error:
                text = 'append-build-description: Failure downloading template workspace (probable network issue)'
                print(text)
            raise PewmaException('ERROR: Workspace template download failed (network or proxy error, possibly transient): please retry')
        finally:
            try:
                resp.close()
            except:
                pass

        # write the data
        with open(destination, "wb") as template:
            template.write(templatedata)


    def unzip_workspace_template(self, template_zip, member_prefix, unzipdir):
        self.logger.info('%sUnzipping "%s (%s)" to "%s"' %
                         (self.log_prefix, template_zip, member_prefix + '*' if member_prefix else '', unzipdir))
        if self.options.dry_run:
            return
        template = zipfile.ZipFile(template_zip, 'r')
        self.logger.debug('Comment in zip file "%s"' % (template.comment,))
        if not member_prefix:
            template.extractall(unzipdir)
        else:
            members_to_extract = [m for m in template.namelist() if m.startswith(member_prefix)]
            self.logger.info('Items to extract from template: %s' % (members_to_extract,))
            template.extractall(unzipdir, members_to_extract)
        template.close()


    def set_available_sites(self):
        """ Sets self.available_sites, a dictionary of {site name: project path} entries,
            for all .site projects in the workspace_git directory,
            provided they have been imported into the Eclipse workspace
        """

        # we cache self.available_sites and never recompute
        if hasattr(self, 'available_sites'):
            return

        # first get the names of site projects that have been imported into in the workspace
        site_projects_imported = set()
        site_projects_imported_dir = os.path.join(self.workspace_loc, '.metadata', '.plugins', 'org.eclipse.core.resources', '.projects')
        if os.path.isdir(site_projects_imported_dir):
            for project_name in os.listdir(site_projects_imported_dir):
                if project_name.endswith('.site'):
                    site_projects_imported.add(project_name)

        sites = {}
        if site_projects_imported and self.workspace_git_loc:
            # .site projects can be up to three directory levels below the git materialize directory
            for level1 in os.listdir(self.workspace_git_loc):
                level1_dir = os.path.join(self.workspace_git_loc, level1)
                if os.path.isdir(level1_dir):
                    for level2 in os.listdir(level1_dir):
                        level2_dir = os.path.join(level1_dir, level2)
                        if os.path.isdir(level2_dir):
                            if level2 in site_projects_imported and os.path.exists( os.path.join(level2_dir, 'feature.xml')):
                                sites[level2] = level2_dir
                            else:
                                for level3 in os.listdir(level2_dir):
                                    level3_dir = os.path.join(level2_dir, level3)
                                    if os.path.isdir(level3_dir):
                                        if level3 in site_projects_imported and os.path.exists( os.path.join(level3_dir, 'feature.xml')):
                                            sites[level3] = level3_dir

        self.available_sites = sites


    def set_all_matching_sites(self, site_name_part=None):
        """ Sets self.all_matching_sites, a sorted list of site names,
            for all .site projects that have site_name_part as a substring
        """

        # we cache self.all_matching_sites and only recompute if site_name_part changes
        if hasattr(self, 'all_matching_sites') and hasattr(self, 'all_matching_sites_name_part') and (self.all_matching_sites_name_part == site_name_part):
            return

        self.set_available_sites()
        if site_name_part:
            all_matching_sites = sorted(s for s in self.available_sites if site_name_part in s)
        else:
            all_matching_sites = sorted(self.available_sites)
        self.all_matching_sites_name_part = site_name_part
        self.all_matching_sites = all_matching_sites


    def set_site_name(self, site_name_part=None, must_exist=True):
        """ Sets self.site_name, a single site name that has site_name_part as a substring
            Raise an exception if not exactly one match
        """

        if hasattr(self, 'site_name') and hasattr(self, 'site_name_name_part') and (self.site_name_name_part == site_name_part):
            return

        self.set_all_matching_sites(site_name_part)
        if len(self.all_matching_sites) == 1:
            self.site_name_name_part = site_name_part
            self.site_name = self.all_matching_sites[0]
            return
        if self.all_matching_sites:
            if site_name_part:
                raise PewmaException('ERROR: More than 1 .site project matches substring "%s" %s, try a longer substring' % (site_name_part, tuple(self.all_matching_sites)))
            else:
                raise PewmaException('ERROR: More than 1 .site project available, you must specify which is required, from: %s' % (tuple(self.all_matching_sites),))
        elif must_exist:
            if site_name_part:
                raise PewmaException('ERROR: No .site project matching substring "%s" found in %s' % (site_name_part, self.all_matching_sites))
            else:
                raise PewmaException('ERROR: No .site project in workspace')


    def validate_glob_patterns(self, include_patterns, exclude_patterns, err_msg_prefix):
        """ There can be multiple in/exclude_patterns, each of which is a comma-separated list of glob patterns
        """
        for glob_pattern_list in (include_patterns, exclude_patterns):
            for glob_patterns in glob_pattern_list:
                for pattern in glob_patterns.split(","):
                    if not pattern:
                        raise PewmaException('ERROR: %s contains an empty plugin pattern' % (err_msg_prefix,))
                    if pattern.startswith("-") or ("=" in pattern):
                        # catch a possible error in command line construction
                        raise PewmaException('ERROR: %s contains an invalid plugin pattern "%s"' % (err_msg_prefix, pattern))


    def set_all_imported_projects_with_releng_ant(self):
        """ Finds all the projects in the self.workspace_git_loc directory, provided
            - they contain a releng.ant file
            - they have been imported into the workspace
            Result is a dictionary of {plugin-name: relative/path/to/plugin} (the path is relative to self.workspace_git_loc)
        """

        projects_imported_dir = os.path.join(self.workspace_loc, '.metadata', '.plugins', 'org.eclipse.core.resources', '.projects')
        projects_imported = set()
        if os.path.isdir(projects_imported_dir):
            for project_name in os.listdir(projects_imported_dir):
                if os.path.isdir(os.path.join(projects_imported_dir, project_name)):
                    projects_imported.add(project_name)

        project_names_paths = {}
        for root, dirs, files in os.walk(self.workspace_git_loc):
            for d in dirs[:]:
                if d.startswith('.') or d.endswith(('.feature', '.site')):
                    dirs.remove(d)
            if 'releng.ant' in files:
                dirs[:] = []  # projects are not normally nested inside other projects, so no need to look beneath this directory
                if os.path.basename(root) in projects_imported:  # only include this project if it was imported into the workspace
                    if os.path.basename(root).startswith('org.eclipse.scanning') and ('/daq-eclipse.git/' in root):
                        continue # ignore org.eclipse.scanning projects in the old (un-imported) location (daq-eclipse.git); the imported version is in scanning.git
                    if os.path.basename(root) in project_names_paths:  # we have seen this project before
                        raise PewmaException('ERROR: releng.ant for project "%s" found in 2 locations: "%s/", "%s/"' %
                                             (os.path.basename(root),
                                              os.path.relpath(root, self.workspace_git_loc),
                                              project_names_paths[os.path.basename(root)]))
                    project_names_paths[os.path.basename(root)] = os.path.relpath(root, self.workspace_git_loc)
        self.all_imported_projects_with_releng_ant = project_names_paths


    def get_items_matching_glob_patterns(self, items, patterns):
        """ Finds all items that match the specified glob pattern(s)
        """
        matching_items = []
        for p in patterns.split(","):
            matching_items.extend(fnmatch.filter(items, p))
        return sorted( set(matching_items) )


    def get_selected_imported_projects_with_releng_ant(self):
        """ Finds all the project names that match the specified glob patterns (combination of --include and --exclude).
            If neither --include nor --exclude specified, return the empty string
        """

        self.set_all_imported_projects_with_releng_ant()

        if self.options.project_includes or self.options.project_excludes:
            if self.options.project_includes:
                included_projects = []
                for inc_patterns in self.options.project_includes:
                        included_projects += self.get_items_matching_glob_patterns(list(self.all_imported_projects_with_releng_ant.keys()), inc_patterns)
            else:
                included_projects = self.all_imported_projects_with_releng_ant

            excluded_projects = []
            for exc_patterns in self.options.project_excludes:
                excluded_projects += self.get_items_matching_glob_patterns(list(self.all_imported_projects_with_releng_ant.keys()), exc_patterns)

            selected_projects = sorted(set(included_projects) - set(excluded_projects))

            if not selected_projects:
                raise PewmaException("ERROR: no imported projects matching --include=%s --exclude=%s found" % (self.options.project_includes, self.options.project_excludes))

        else:
            selected_projects = sorted(self.all_imported_projects_with_releng_ant.keys())

        self.logger.info('%sSelected: %s projects' % (self.log_prefix, len(selected_projects)))
        return "-Dplugin_list=\"%s\"" % '|'.join([self.all_imported_projects_with_releng_ant[pname] for pname in selected_projects])

    def set_buckminster_properties_path(self, site_name=None):
        """ Sets self.buckminster_properties_path, the absolute path to the buckminster properties file in the specified site
        """

        if self.options.buckminster_properties_file:
            buckminster_properties_path = os.path.expanduser(self.options.buckminster_properties_file)
            if not os.path.isabs(buckminster_properties_path):
                buckminster_properties_path = os.path.abspath(os.path.join(self.available_sites[site_name], self.options.buckminster_properties_file))
            if not os.path.isfile(buckminster_properties_path):
                raise PewmaException('ERROR: Properties file "%s" does not exist' % (buckminster_properties_path,))
            self.buckminster_properties_path = buckminster_properties_path
        else:
            buckminster_properties_paths = [os.path.abspath(os.path.join(self.available_sites[site_name], buckminster_properties_file))
                                            for buckminster_properties_file in ('buckminster.properties', 'buckminster.beamline.properties')]
            for buckminster_properties_path in buckminster_properties_paths:
                if os.path.isfile(buckminster_properties_path):
                        self.buckminster_properties_path = buckminster_properties_path
                        break
            else:
                raise PewmaException('ERROR: Neither properties file "%s" exists' % (buckminster_properties_paths,))

###############################################################################
#  Actions                                                                    #
###############################################################################

    def _set_linux_group(self, directory):
        """ Optionally, change the Linux group (like chgrp) and permission (like chmod g+rwxs o+rx)
            on a directory. Done if option --directories.groupname set (or defaults, at DLS).
            Can only be done if the user running the script is the directory owner (or root)
        """

        if (not self.isLinux) or (not self.options.directories_groupname):
            return
        assert directory and os.path.isabs(directory)
        assert self.gid_new

        dirowner_uid = os.stat(directory).st_uid                 # current directory owner id
        try:
            dirowner_uname = pwd.getpwuid(dirowner_uid).pw_name  # current directory owner name
        except (KeyError) as e:
            dirowner_uname = '?'
        gid_old = os.stat(directory).st_gid                      # current directory group id
        try:
            grname_old = grp.getgrgid(gid_old).gr_name           # current directory group name
        except (KeyError) as e:
            grname_old = '?'
        imode_old  = stat.S_IMODE(os.stat(directory).st_mode)    # existing directory permission bits
        imode_new = imode_old | stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP | stat.S_ISGID | stat.S_IROTH | stat.S_IXOTH

        is_directory_owner = self.user_euid in [dirowner_uid, 0]  # an effective uid of 0 indicates root
        is_in_new_group = self.gid_new in os.getgroups()  # the file owner must be a member of the new file group 

        if grname_old != self.options.directories_groupname:
            self.logger.info('Changing owning group from %s (%s) to %s (%s) on %s' %
                             (grname_old, gid_old,
                              self.options.directories_groupname, self.gid_new,
                              directory))
            if not is_directory_owner:
                self.logger.warn('Cannot change owning group: current user %s (%s) is not directory owner %s (%s)' %
                                 (self.user_uname, self.user_euid,
                                  dirowner_uname, dirowner_uid,))
            if not is_in_new_group:
                self.logger.warn('Cannot change owning group: current user %s (%s) is not in new group %s (%s)' %
                                 (self.user_uname, self.user_euid,
                                  self.options.directories_groupname, self.gid_new,))
            else:
                try:
                    os.chown(directory, -1, self.gid_new)
                except Exception as e:
                    self.logger.error('chown failed: %s' % (e,))

        if imode_old != imode_new:
            self.logger.info('Changing permissions from 0x%04o to 0x%04o on %s' % (imode_old, imode_new, directory))
            if is_directory_owner:
                try:
                    os.chmod(directory, imode_new)
                except Exception as e:
                    self.logger.error('chmod failed: %s' % (e,))
            else:
                self.logger.warn('Cannot change permissions: current user %s (%s) is not directory owner %s (%s)' %
                                 (self.user_uname, self.user_euid,
                                  dirowner_uname, dirowner_uid,))


    def action_setup(self):
        """ Processes command: setup [<category> [<version>] | <cquery>]
        """

        if len(self.arguments) > 2:
            raise PewmaException('ERROR: setup command has too many arguments')

        (category_to_use, version_to_use, cquery_to_use, template_to_use) = self._parse_category_version_cquery(self.arguments)
        if category_to_use and version_to_use:
            (cquery_to_use, template_to_use, self.valid_java_versions) = self._get_category_version_translation(category_to_use, version_to_use)
        if template_to_use:
            self.template_name = 'template_workspace_%s.zip' % (template_to_use,)

        self.setup_workspace()

        if cquery_to_use:
            self.add_cquery_to_history(cquery_to_use)
        return


    def action_print_workspace_path(self):
        """ Processes command: print-workspace-path
        """

        assert self.workspace_loc
        print(self.workspace_loc)
        return


    def action_get_branches_expected(self):
        """ Processes command: get-branches-expected <component> [<category> [<version>] | <cquery>]
        """

        (_, _, _, cquery_to_use, _) = self._interpret_components_category_version_cquery()
        source = self._get_full_uri('base/' + cquery_to_use)
        if self.options.dry_run:
            self.logger.info('%sDownloading "%s"' % (self.log_prefix, source))
            return

        # open the URL
        try:
            resp = urllib2.urlopen(source, timeout=30)
        except (urllib2.URLError, urllib2.HTTPError, socket.timeout) as e:
            self.logger.error('Error downloading from "%s": %s' % (source, str(e)))
            if self.options.prepare_jenkins_build_description_on_error:
                text = 'append-build-description: Failure downloading CQuery (probable network issue)'
                print(text)
            raise PewmaException('ERROR: CQuery download failed (network or proxy error, possibly transient): please retry')

        # read the data (it's small enough to do in one chunk)
        self.logger.info('Downloading %s bytes from "%s"' % (resp.info().get('content-length', '<unknown>'), resp.geturl()))
        try:
            cquerydata = resp.read()
        except Exception as e:
            self.logger.error('Error downloading from "%s": %s' % (source, str(e)))
            if self.options.prepare_jenkins_build_description_on_error:
                text = 'append-build-description: Failure downloading CQuery (probable network issue)'
                print(text)
            raise PewmaException('ERROR: CQuery download failed (network or proxy error, possibly transient): please retry')
        finally:
            try:
                resp.close()
            except:
                pass

        # process all repositories in advisor nodes
        root = ET.fromstring(cquerydata)
        repos_branches = {}

        cquery_namespace = "{http://www.eclipse.org/buckminster/CQuery-1.0}"
        # we want all advisor nodes with a <documentation> sub-element
        # Python 2.7+ only: for advisorNode in root.findall('{0}advisorNode[{0}documentation]'.format(cquery_namespace)):  # all advisor nodes with a <documentation> sub-element
        for advisorNode in root.findall('{0}advisorNode'.format(cquery_namespace)):  # all advisor nodes
            if advisorNode.find('{0}documentation'.format(cquery_namespace)) is None:
                continue
            documentation = advisorNode.find('{0}documentation'.format(cquery_namespace)).text.splitlines()[0]
            if not documentation.endswith('.git repository branch'):
                continue
            repository = documentation[:-len('.git repository branch')]

            # determine whether repository is not to be used
            useMaterializationFalse = advisorNode.get('useMaterialization') == 'false'
            useTargetPlatformFalse = advisorNode.get('useTargetPlatform') == 'false'
            useWorkspaceFalse = advisorNode.get('useWorkspace') == 'false'
            disallowPropertyTrue = False
            disallow_key = None
            for property in advisorNode.findall('{0}property'.format(cquery_namespace)):
                if property.get('key', '') == 'disallow.repo.{0}'.format(repository):
                    disallowPropertyTrue = True
                    disallow_key = bool(property.get('value', ''))
                    break
            # print(repository, useMaterializationFalse, useTargetPlatformFalse, useWorkspaceFalse, disallowPropertyTrue, disallow_key)
            if all((useMaterializationFalse, useTargetPlatformFalse, useWorkspaceFalse, disallowPropertyTrue, disallow_key)):
                # repo not allowed in this CQuery
                continue
            if any((useMaterializationFalse, useWorkspaceFalse, disallowPropertyTrue)):
                raise ValueError('Repository "{0}" has mismatched settings (useMaterializationFalse, useWorkspaceFalse, disallowPropertyTrue) = {1} ({2})'.format(repository, (useMaterializationFalse, useWorkspaceFalse), location))

            branchTagPath = advisorNode.get('branchTagPath', None)
            repos_branches[repository] = branchTagPath or 'master'  # if repo defined multiple times, use the last specified branch

        cquery_branches_path = os.path.abspath(os.path.expanduser(self.options.cquery_branches_file))
        self.logger.info('Writing expected branches to "%s"' % (cquery_branches_path,))
        with open(cquery_branches_path, 'w') as expected_branches_file:
            expected_branches_file.write('### File generated ' + time.strftime("%a, %Y/%m/%d %H:%M:%S %z") +
                          ' (' + os.environ.get('BUILD_URL','$BUILD_URL:missing') + ')\n')
            expected_branches_file.write('# branches as specified by cquery=%s\n' % (cquery_to_use,))
            for repo in sorted(repos_branches):
                expected_branches_file.write('%s=%s\n' % (repo, repos_branches[repo]))


    def action_materialize(self):
        """ Processes command: materialize <component> [<category> [<version>] | <cquery>]
        """

        (components_to_use, category_to_use, version_to_use, cquery_to_use, template_to_use) = self._interpret_components_category_version_cquery()
        if not components_to_use:
            raise PewmaException('ERROR: materialize command requires the name of the component to materialize')

        # create the workspace if required
        self.template_name = 'template_workspace_%s.zip' % (template_to_use,)
        exit_code = self.setup_workspace()
        if exit_code:
            self.logger.info('Abandoning materialize: workspace setup failed')
            return exit_code

        # set jvmarg -Declipse.p2.mirrors=false, unless the value has already been set, or unless the CQuery is an old one
        assert cquery_to_use
        for skip_pattern in CQUERY_PATTERNS_TO_SKIP_p2_mirrors_false:
            if re.match(skip_pattern, cquery_to_use):
                break
        else:
            for jvmarg in self.options.jvmargs:
                if 'eclipse.p2.mirrors=' in jvmarg:
                    break
            else:
                self.options.jvmargs.extend(('-Declipse.p2.mirrors=false',))

        import_commands = ''
        for component in components_to_use:
            import_commands += 'import -Dcomponent=%s ' % (component,)
            if self.options.download_location:
                import_commands += '-Ddownload.location.common=%s ' % (self.options.download_location,)
            for keyval in self.options.system_property:
                import_commands += '-D%s ' % (keyval,)
            import_commands += self._get_full_uri('base/' + cquery_to_use) + '\n'
        self.logger.info('%sWriting buckminster commands to "%s"' % (self.log_prefix, self.script_file_path,))
        if not self.options.dry_run:
            with open(self.script_file_path, 'w') as script_file:
                script_file.write('### File generated ' + time.strftime("%a, %Y/%m/%d %H:%M:%S %z") +
                                  ' (' + os.environ.get('BUILD_URL','$BUILD_URL:missing') + ')\n')
                script_file.write('importproxysettings\n')  # will import proxy settings from Java system properties
                # set preferences
                if self.options.maxParallelMaterializations:
                    script_file.write('setpref maxParallelMaterializations=%s\n' % (self.options.maxParallelMaterializations,))
                if self.options.maxParallelResolutions:
                    script_file.write('setpref maxParallelResolutions=%s\n' % (self.options.maxParallelResolutions,))
                script_file.write(import_commands)

        if self.isWindows:
            script_file_path_to_pass = '"%s"' % (self.script_file_path,)
        else:
            script_file_path_to_pass = self.script_file_path

        # get buckminster to run the materialize(s)
        rc = self.run_buckminster_in_subprocess(('--scriptfile', script_file_path_to_pass), scan_for_materialize_errors=True, scan_compile_messages=False)

        self.add_cquery_to_history(cquery_to_use)
        for component in components_to_use:
            if component.endswith('-config') and (not component.startswith(('all-', 'core-', 'dls-', 'mt-', 'mx-'))):
                self._add_string_substitution_variable_to_workspace(
                  'GDA_instance_config_name',
                  component,
                  'Project name of GDA instance config')
        self._add_string_substitution_variable_to_workspace(
          'GDA_WORKSPACE_PARENT',
          os.path.join( os.path.abspath(os.path.join(self.workspace_loc, '..')), ''),  # final '' is to make sure the path ends in a /
          'Location of workspace parent directory')

        rc = max(rc, self.action_gerrit_config(check_arguments=False) or 0)

        return rc


    def _interpret_components_category_version_cquery(self):
        """ Processes this part of the arguments: {<component> ...} [<category> [<version>] | <cquery>]
            (on behalf of "materialize" and "get_branches_expected" commands)
        """

        if len(self.arguments) < 1:
            raise PewmaException('ERROR: %s command has too few arguments' % (self.action,))

        # go through the arguments, and find where the component list ends, which is immediately before the (optional) category/version/cquery
        # we rely on the fact that no component will ever have the same name as a category name
        components_to_use_raw = []
        category_version_cquery = []
        for index, item in enumerate(self.arguments):
            if (item in CATEGORIES_AVAILABLE) or (item in VERSIONS_AVAILABLE) or item.endswith('.cquery'):
                components_to_use_raw = self.arguments[:index]
                category_version_cquery = self.arguments[index:]
                break
        else:
            components_to_use_raw = self.arguments
            category_version_cquery = []

        # interpret any (category / category+version / cquery) arguments
        (category_to_use, version_to_use, cquery_to_use, template_to_use) = self._parse_category_version_cquery(category_version_cquery)

        for component in components_to_use_raw:
            for (invalid_component_pattern, applicable_versions, error_message) in INVALID_COMPONENTS:
                if re.match(applicable_versions, version_to_use):
                    if re.match(invalid_component_pattern, component):
                        raise PewmaException('ERROR: ' + error_message)

        # translate any abbreviated component names to the real component name, and make sure they are all in the same category
        category_implied = set()
        components_to_use_translated = []
        for component_to_use in components_to_use_raw:
            for abbrev, actual, cat in COMPONENT_ABBREVIATIONS:
                if component_to_use == abbrev:
                    if isinstance(actual, basestring):
                        components_to_use_translated.append(actual)  # replacement is a single item
                        self.logger.info('%sTranslated "%s" --> component "%s" in category %s' % (self.log_prefix, abbrev, actual, cat))
                    else:
                        components_to_use_translated.extend(actual)  # replacement is a tuple of items
                        self.logger.info('%sTranslated "%s" --> components %s in category %s' % (self.log_prefix, abbrev, tuple(str(a) for a in actual), cat))
                    category_implied.add(cat)
                    break
            else:
                # component name is specified verbatim
                components_to_use_translated.append(component_to_use)
                if component_to_use.endswith(('-config', '-configs', '-clients')) or component_to_use.startswith(('gda','uk.ac.gda.')):
                    category_implied.add('gda')  # must be a GDA project

        # dedupe components_to_use_translated (preserves order; efficiency doesn't matter since list short)
        components_to_use = []
        for c in components_to_use_translated:
            if c not in components_to_use:
                components_to_use.append(c)
            else:
                self.logger.info('%sComponent "%s" appears in materialize list multiple times - duplicates removed' % (self.log_prefix, c))
        if components_to_use_raw != components_to_use:
            self.logger.info('%sComponent(s) to materialize: %s' % (self.log_prefix, tuple(str(c) for c in components_to_use)))

        if len(category_implied) > 1:
            raise PewmaException('ERROR: the %s components you want to materialize %s come from more than 1 category: %s' %
                                 (len(components_to_use), components_to_use, [c for c in category_implied]))

        category_implied = tuple(category_implied)
        category_implied = (category_implied and category_implied[0]) or None

        if not category_to_use:
            category_to_use = category_implied
        elif category_implied and (category_implied != category_to_use):
            # if a component abbreviation was provided, it implies a category. If a category was also specified, it must match the implied category
            raise PewmaException('ERROR: components %s are not consistent with category "%s"' % (components_to_use, category_to_use,))

        if not (category_to_use or cquery_to_use):
            raise PewmaException('ERROR: the category is missing (can be one of %s)' % ('/'.join(CATEGORIES_AVAILABLE)))

        if category_to_use and version_to_use:
            (cquery_to_use_translation, template_to_use, self.valid_java_versions) = self._get_category_version_translation(category_to_use, version_to_use)
            if not cquery_to_use:
                cquery_to_use = cquery_to_use_translation

        assert template_to_use and cquery_to_use

        return (components_to_use, category_to_use, version_to_use, cquery_to_use, template_to_use)


    def _parse_category_version_cquery(self, arguments_part):
        """ Processes this part of the arguments: [ [<category> ] [<version>] | <cquery>]
            (on behalf of "setup" and "materialize" commands)
        """

        category_to_use = None
        version_to_use = 'master'
        cquery_to_use = None
        template_to_use = DEFAULT_TEMPLATE

        # interpret any (category / category version / version / cquery) arguments
        if arguments_part:
            category_or_version_or_cquery = arguments_part[0]
            if category_or_version_or_cquery.endswith('.cquery'):
                cquery_to_use = category_or_version_or_cquery
                if len(arguments_part) > 1:
                    raise PewmaException('ERROR: No other options can follow the CQuery')
                for c, v, q, t, s, j in [cc for cc in COMPONENT_CATEGORIES if cc[2] == cquery_to_use]:
                    template_to_use = t
                    break
            elif category_or_version_or_cquery in CATEGORIES_AVAILABLE:
                category_to_use = category_or_version_or_cquery
                if len(arguments_part) > 1:
                    version = arguments_part[1].lower()
                    for c, v, q, t, s, j in [cc for cc in COMPONENT_CATEGORIES if cc[0] == category_to_use]:
                        if version in s:
                            version_to_use = v
                            break
                    else:
                        raise PewmaException('ERROR: category "%s" does not have a version "%s"' % (category_to_use, version))
                    if len(arguments_part) > 2:
                        raise PewmaException('ERROR: unexpected additional parameters found "%s"' % (arguments_part[2:],))
            elif category_or_version_or_cquery.lower() in VERSIONS_AVAILABLE:
                version = category_or_version_or_cquery.lower()
                for c, v, q, t, s, j in [cc for cc in COMPONENT_CATEGORIES]:
                    if version in s:
                        version_to_use = v
                        break
                else:
                    assert False  # should always match
                if len(arguments_part) > 1:
                    raise PewmaException('ERROR: unexpected additional parameters found "%s"' % (arguments_part[1:],))
            else:
                assert False, 'Internal error in _parse_category_version_cquery: "%s"' % (category_or_version_or_cquery,)

        return (category_to_use, version_to_use, cquery_to_use, template_to_use)


    def _get_category_version_translation(self, category, version):
        """ Given a category and version, determine (on behalf of "setup" and "materialize" commands)
                the CQuery to use
                the template version to use
                the allowable java versions
        """

        assert category and version
        matching_list = [cc for cc in COMPONENT_CATEGORIES if cc[0] == category and cc[1] == version]
        assert len(matching_list) == 1
        return [matching_list[0][2], matching_list[0][3], matching_list[0][5]]


    def action_add_diamond_cpython(self):
        """ Processes command: add-diamond-cpython [ <platform> ... ]
        """
        platforms = set()
        for arg in self.arguments:
            if arg == 'all':
                for (p, _) in PLATFORMS_AVAILABLE:
                    platforms.add(p)
            else:
                for (p, a) in PLATFORMS_AVAILABLE:
                    if arg in a:
                        platforms.add(p)
                        break
                else:
                    raise PewmaException('ERROR: "%s" was not recognised as a platform name' % (arg,))
        if not platforms:
            platforms = [self.platform]

        for p in sorted(platforms):
            self._add_diamond_cpython(p)

    def _add_diamond_cpython(self, pform, must_not_already_exist=True):
        """ Processes command: add-diamond-cpython <platform>
            (for a single platform only)
        """
        assert pform in [p[0] for p in PLATFORMS_AVAILABLE]

        # workspace_git/diamond-cpython.git should already exist
        diamond_cpython_git_loc = os.path.join(self.workspace_git_loc, 'diamond-cpython.git')
        if not os.path.isdir(diamond_cpython_git_loc):
            raise PewmaException('ERROR: Can\'t "add-diamond-cpython", because "%s" does not exist' % (diamond_cpython_git_loc,))

        cpython_platform_loc = os.path.join(
            diamond_cpython_git_loc,
            'uk.ac.diamond.cpython.%s.%s' % tuple(pform.split(',')[0:3:2]))  # transform platform: linux,gtk,x86_64 --> linux.x86_64
        if not os.path.isdir(cpython_platform_loc):
            raise PewmaException('ERROR: Can\'t "add-diamond-cpython", because "%s" does not exist' % (cpython_platform_loc,))
        for item in os.listdir(cpython_platform_loc):
            if item.startswith('cpython'):  # currently, the directory is called cpython2.7, but the version might change
                cpython_loc = os.path.join(cpython_platform_loc, item)
                if must_not_already_exist:
                    raise PewmaException('ERROR: Attempted "add-diamond-cpython", but "%s" already exists' % (cpython_loc,))
                else:
                    self.logger.info('Skipped "add-diamond-cpython": "%s" already exists' % (cpython_loc,))
                    return
                break

        # the cpythonn.n directory does not exist, so untar to create it
        lines = open(os.path.join(cpython_platform_loc, 'install_files_loc.txt'), 'r').read().splitlines()
        for line in lines:
            if line.startswith('#'):
                continue
            if line.startswith('/'):
                tarfile_loc = line
                if not os.path.isfile(tarfile_loc):
                    continue
                break
            elif line.startswith('https://'):
                self.logger.info('%sDownloading "%s"' % (self.log_prefix, line))
                if not self.options.dry_run:
                    tarfile_loc, headers = urllib.urlretrieve(line)
                    self.logger.info('Downloaded to "%s"' % (tarfile_loc,))
            else:
                raise PewmaException('ERROR: Unrecognised syntax in "%s": "%s"' % (install_files_file_loc, line))
        if self.options.dry_run:
            return
        tar_file_size = os.stat(tarfile_loc).st_size
        if tar_file_size < 400000000:
            raise PewmaException('ERROR: File to untar too small (possibly corrupt) "%s" (%s bytes)' % (tarfile_loc, '{0:,d}'.format(tar_file_size)))

        self.logger.info('Extracting "%s" (%s bytes) into "%s"' % (tarfile_loc, '{0:,d}'.format(tar_file_size), cpython_platform_loc))
        with tarfile.open(tarfile_loc, 'r:bz2') as tar_file:
            # guard against possible path traversal attack if tar file has been compromised 
            for name in tar_file.getnames():
                if (not name.startswith('cpython')) or ('..' in name) or ('.\.' in name):
                    raise PewmaException('ERROR: Possible path traversal attack: found "%s" in %s' % (name, tarfile_loc))
            tar_file.extractall(cpython_platform_loc)


    def _get_git_directories(self):
        """ Returns a list of (repo_name, absolute path to repository) of all Git repositories
        """

        if (not self.workspace_git_loc) or (not os.path.isdir(self.workspace_git_loc)):
            return []

        git_directories = []
        for root, dirs, files in os.walk(self.workspace_git_loc):
            if os.path.basename(root) == '.git':
                raise PewmaException('ERROR: _get_git_directories attempted to recurse into a .git directory: %s' % (root,))
            if os.path.basename(root).startswith('.'):
                # don't recurse into hidden directories
                self.logger.debug('%sSkipping: %s' % (self.log_prefix, root))
                dirs[:] = []
                continue
            if '.git' in dirs:
                # if this directory is the top level of a git checkout, remember it
                git_directories.append((os.path.basename(root), os.path.join(self.workspace_git_loc, root)))
                dirs[:] = []  # do not recurse into this directory
        assert len(git_directories) == len(set(git_directories))  # should be no duplicates

        return git_directories


    def action_gerrit_config(self, check_arguments=True):
        """ Processes command: gerrit-config
        """

        NOT_REQUIRED, DONE, FAILED = list(range(3))  # possible status for various configure actions
        assert NOT_REQUIRED < DONE                   # )
        assert DONE < FAILED                         # ) we record the highest status, which must therefore be FAILED

        if check_arguments and self.arguments:
            raise PewmaException('ERROR: gerrit-config command does not take any arguments')

        self.logger.info('%sLooking for repositories that need switching to Gerrit, and/or configuring for EGit/JGit and git' % (self.log_prefix,))
        rc = 0  # return code, will be 0 or 1

        git_directories = self._get_git_directories()
        if not git_directories:
            self.logger.info('%sSkipped: %s' % (self.log_prefix, self.workspace_loc + '_git (does not contain any repositories)'))
            return rc
        repo_names = [repo_name for (repo_name, _) in git_directories]
        prefix= "%%%is: " % max([len(r) for r in repo_names]) if self.options.repo_prefix else ""

        if self.options.repo_includes:
            repos_included = self.get_items_matching_glob_patterns(repo_names, self.options.repo_includes)
        else:
            repos_included = repo_names
        if self.options.repo_excludes:
            repos_excluded = self.get_items_matching_glob_patterns(repo_names, self.options.repo_excludes)
        else:
            repos_excluded = []
        selected_repos = sorted(set(repos_included) - set(repos_excluded))

        for (repo_name, git_dir) in sorted(git_directories):
            if repo_name not in GERRIT_REPOSITORIES:
                # self.logger.debug('%sSkipped: not in Gerrit: %s' % (self.log_prefix, git_dir))
                continue
            if repo_name not in selected_repos:
                self.logger.debug('%sSkipped: does not satisfy --repo-include/--repo-exclude: %s' % (self.log_prefix, git_dir))
                continue
            config_file_loc = os.path.join(git_dir, '.git', 'config')
            if not os.path.isfile(config_file_loc):
                self.logger.error('%sSkipped: %s should exist, but does not' % (self.log_prefix, config_file_loc))
                rc = 1  # when we're finished, exit with return code 1 to indicate an error
                continue

            #####################################################
            # parse and potentially update the .git/config file #
            #####################################################
            config = GitConfigParser()
            config.readgit(config_file_loc)
            try:
                origin_url = config.get('remote "origin"', 'url')
            except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
                self.logger.warn('%sSkipped: no [remote "origin"]: %s' % (self.log_prefix, config_file_loc))
                continue

            # origin_url can be ssh or https. ssh might or might not include a username. server might be gerrit or gerritbeta
            # examples:
            # ssh://mwebber@gerritbeta.diamond.ac.uk:29418/gda/gda-core.git
            # ssh://gerrit.diamond.ac.uk:29418/gda/gda-core.git
            # https://gerrit.diamond.ac.uk:29418/gda/gda-core.git

            # get the current branch (so we can set up the push branch correctly)
            # the HEAD file contains one line which looks like "ref: refs/heads/gda-9.8" (probably)
            HEAD_file_loc = os.path.join(git_dir, '.git', 'HEAD')
            if not os.path.isfile(HEAD_file_loc):
                self.logger.error('%sSkipped: %s should exist, but does not' % (self.log_prefix, HEAD_file_loc))
                rc = 1  # when we're finished, exit with return code 1 to indicate an error
                continue
            current_branch = 'master'  # in case of problems parsing HEAD file
            with open(HEAD_file_loc, 'r') as HEAD_file:
                for line in HEAD_file:
                    current_branch = (line.rsplit('/')[-1] or 'master').strip()  # strip() to get rid of newline
                    break

            gerrit_repo_details = GERRIT_REPOSITORIES[repo_name]
            gerrit_repo_url_path = gerrit_repo_details['url_part']

            # this repo might have been cloned before the repo was moved to Gerrit
            # In that case, change the upstream to point to Gerrit (unless keep_origin == True)
            if all(g not in origin_url for g in ('gerrit.diamond.ac.uk', 'gerritbeta.diamond.ac.uk')):
                if gerrit_repo_details.get('keep_origin'):
                    if repo_name in ('dawnsci.git', 'gda-mt.git'):
                        if (current_branch.startswith(('gda-9.8', 'gda-9.7', 'gda-9.6', 'gda-9.5', 'gda-9.4', 'gda-9.3', 'gda-9.2', 'gda-9.1', 'gda-9.0', 'dawn-'))
                            or
                            ((repo_name == 'gda-mt.git') and current_branch.startswith(('gda-9.9',)))):
                            self.logger.info('%sSkipped: did not change remote origin to Gerrit, since old branch (%s) can use pre-Gerrit remote: %s' % (self.log_prefix, current_branch, git_dir))
                        else:
                            self.logger.error('%sSkipped: unable to change remote origin to Gerrit, requires a fresh clone: %s' % (self.log_prefix, git_dir))
                            rc = 1
                        continue
                    else:
                        raise PewmaException('ERROR: internal bug: keep_origin not handled for ' + repo_name)
                if gerrit_repo_details.get('must_use_ssh'):
                    gerrit_repo_url_pull = GERRIT_URI_SSH + gerrit_repo_url_path
                else:
                    gerrit_repo_url_pull = GERRIT_URI_HTTPS + gerrit_repo_url_path  # the default scheme for all repos unless they are private, and need SSH
                config_changes = [
                # section         , option          , name                   , required_value                   , action_if_already_exists
                ('remote "origin"', 'url'           , 'remote.origin.url'    , gerrit_repo_url_pull             , 'replace'),]

                # set push URL
                gerrit_repo_url_push = GERRIT_URI_SSH + gerrit_repo_url_path  # push is always authenticated, i.e. SSH

            else:
                config_changes = []
                # set push URL
                if origin_url.startswith('ssh://'):
                    gerrit_repo_url_push = origin_url
                elif origin_url.startswith('https://'):
                    origin_url_parts = origin_url[8:].split('/',1)
                    gerrit_repo_url_push = 'ssh://' + origin_url_parts[0] + ':29418/' + origin_url_parts[1]  # works for both gerrit and gerritbeta
                else:
                    raise PewmaException('ERROR: internal bug: ' + repo_name + ' has unrecognised URI scheme in ' + origin_url)

            config_changes.extend((
                # section         , option          , name                   , required_value                   , action_if_already_exists
                ('gerrit'         , 'createchangeid', 'gerrit.createchangeid', 'true'                           , 'replace'),
                ('remote "origin"', 'fetch'         , 'remote.origin.fetch'  , 'refs/notes/*:refs/notes/*'      , 'append'),
                ('remote "origin"', 'pushurl'       , 'remote.origin.pushurl', gerrit_repo_url_push             , 'append'),
                ('remote "origin"', 'push'          , 'remote.origin.push'   , 'HEAD:refs/for/' + current_branch, 'keep'),
                ('merge'          , 'log'           , 'merge.log'            , '50'                             , 'replace'),
                # the following 2 options commented out, since command line git works correctly,
                # however JGit does not support pull.ff (see https://bugs.eclipse.org/bugs/show_bug.cgi?id=474174)
                ### ('merge'          , 'ff'            , 'merge.ff'             , 'false'                          , True),  # merges from branches should not fast-forward
                ### # NB: if you have merge.ff=false, you also need pull.ff=true, so that you do not get a merge commit on every pull!
                ### ('pull'           , 'ff'            , 'pull.ff'              , 'true'                           , True),  # pulls should fast-forward if possible
                ),)

            git_config_commands = []
            for (section, option, name, required_value, action_if_already_exists) in config_changes:
                self.logger.debug('%sProcessing: %s in: %s' % (self.log_prefix, (section, option, name, required_value, action_if_already_exists), git_dir))
                try:
                    option_value = config.get(section, option)
                    self.logger.debug('%sGot: %s=%s' % (self.log_prefix, option, option_value))

                except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
                    git_config_commands.append('git config -f %s %s %s' % (config_file_loc, name, required_value))

                else:
                    if option_value != required_value:
                        if action_if_already_exists == 'append':
                            git_config_commands.append('git config -f %s --add %s %s' % (config_file_loc, name, required_value))
                        elif action_if_already_exists == 'replace':
                            git_config_commands.append('git config -f %s %s %s' % (config_file_loc, name, required_value))
                        else:
                            self.logger.log(5, '%sSkipped: already have %s=%s in: %s' % (self.log_prefix, name, option_value, git_dir))
                    else:
                        self.logger.log(5, '%sSkipped: already have %s=%s in: %s' % (self.log_prefix, name, required_value, git_dir))

            repo_status = {'switched_remote_to_gerrit': NOT_REQUIRED, 'configured_for_eclipse': NOT_REQUIRED, 'hook_added': NOT_REQUIRED}

            for command in git_config_commands:
                self.logger.debug('%sRunning: %s' % (self.log_prefix, command))
                action_type = 'switched_remote_to_gerrit' if 'remote.origin.url' in command else 'configured_for_eclipse'
                status = DONE  # for dry run, pretend the operation succeeded
                if not self.options.dry_run:
                    try:
                        if not self.isWindows:
                            retcode = subprocess.call(shlex.split(str(command)), shell=False)
                        else:
                            retcode = subprocess.call(command, shell=True)
                    except (OSError,) as e:
                        if e.errno == errno.ENOENT:
                            possible_cause = ' (does the "git" command exist?)'
                        else:
                            possible_cause = ''
                        self.logger.error('%sError "%s" %s' % (self.log_prefix, e, possible_cause))
                        status = FAILED
                    else:
                        if retcode:
                            self.logger.error('%sError rc=%s attempting "%s"' % (self.log_prefix, retcode, command))
                            status = FAILED
                repo_status[action_type] = max(repo_status[action_type], status)  # FAILED is the highest status, since we want to know if _any_ failed

            #############################################################################
            # get the commit hook, for people who use command line Git rather than EGit #
            #############################################################################

            hooks_loc = os.path.join(git_dir, '.git', 'hooks')
            hooks_commit_msg_loc = os.path.join(hooks_loc, 'commit-msg')
            if os.path.exists(hooks_commit_msg_loc):
                self.logger.debug('%scommit-msg hook already set up: %s' % (self.log_prefix, hooks_commit_msg_loc))
            else:
                if not os.path.isdir(hooks_loc):
                    self.logger.info('%screating repository hooks directory: %s' % (self.log_prefix, hooks_loc))
                    os.mkdir(hooks_loc, 0775)
                commit_hook = self.gerrit_commit_hook()
                if not self.options.dry_run:
                    with open(hooks_commit_msg_loc, 'w') as commit_msg_file:
                        commit_msg_file.write(commit_hook)
                    os.chmod(hooks_commit_msg_loc, 0o775)  # rwxrwxr-x
                self.logger.debug('%scommit-msg hook copied to: %s' % (self.log_prefix, hooks_commit_msg_loc))
                repo_status['hook_added'] = DONE

            if all(status == NOT_REQUIRED for status in list(repo_status.values())):
                self.logger.debug('%sSkipped: already switched to Gerrit; configured for EGit/JGit and git: %s' % (self.log_prefix, git_dir))
            else:
                for (action, message) in (('switched_remote_to_gerrit', 'switch remote.origin.url to Gerrit'),
                                          ('configured_for_eclipse'   , 'configure repository for EGit/JGit'),
                                          ('hook_added'               , 'add Gerrit commit-msg hook for git'),
                                         ):
                    if repo_status[action] == NOT_REQUIRED:
                        self.logger.debug('%sDone previously: %s: %s' % (self.log_prefix, message, git_dir))
                    elif repo_status[action] == DONE:
                        self.logger.info('%sDone: %s: %s' % (self.log_prefix, message, git_dir))
                    elif repo_status[action] == FAILED:
                        self.logger.error('%sFailed: %s: %s' % (self.log_prefix, message, git_dir))
                        rc = 1

        return rc

    def action_git(self):
        """ Processes command: git <command>
        """

        if len(self.arguments) < 1:
            raise PewmaException('ERROR: git command has too few arguments')

        git_directories = self._get_git_directories()
        if not git_directories:
            self.logger.info('%sSkipped: %s' % (self.log_prefix, self.workspace_loc + '_git (does not contain any repositories)'))
            return
        repo_names = [repo_name for (repo_name, _) in git_directories]
        prefix= "%%%is: " % max([len(r) for r in repo_names]) if self.options.repo_prefix else ""

        if self.options.repo_includes:
            repos_included = self.get_items_matching_glob_patterns(repo_names, self.options.repo_includes)
        else:
            repos_included = repo_names
        if self.options.repo_excludes:
            repos_excluded = self.get_items_matching_glob_patterns(repo_names, self.options.repo_excludes)
        else:
            repos_excluded = []
        selected_repos = sorted(set(repos_included) - set(repos_excluded))

        return_code_count = {}  # dictionary with key=return_code, value=repositories it occurred in
        for (repo_name, git_dir) in sorted(git_directories):
            if self.options.non_gerrit_only:
                if repo_name in GERRIT_REPOSITORIES:
                    self.logger.debug('%sSkipped: is Gerrit, but --non-gerrit-only specified: %s' % (self.log_prefix, git_dir))
                    continue
            if self.options.gerrit_only:
                if repo_name not in GERRIT_REPOSITORIES:
                    self.logger.debug('%sSkipped: is not Gerrit, but --gerrit-only specified: %s' % (self.log_prefix, git_dir))
                    continue
            if repo_name not in selected_repos:
                self.logger.debug('%sSkipped: does not satisfy --repo-include/--repo-exclude: %s' % (self.log_prefix, git_dir))
                continue

            git_command = 'git ' + ' '.join(self.arguments)
            if (git_command.strip() in ('git pull', 'git fetch')) or git_command.startswith(('git pull ', 'git fetch ')):
                # don't attempt a "git pull" or "git fetch" if no upstream defined
                has_remote = False
                config_path = os.path.join(git_dir, '.git', 'config')
                if os.path.isfile(config_path):
                    with open(config_path, 'r' ) as config:
                        for line in config:
                            if '[remote ' in line:
                                has_remote = True
                                break
                if not has_remote:
                    self.logger.warn('%sSkipped: %s in %s (NO REMOTE DEFINED)' % (self.log_prefix, git_command, git_dir))
                    continue

            retcode = self._one_git_repo(git_command, git_dir, prefix)
            if not self.options.quiet:
                print()  # empty line after each repo to make the output more human-readable
            if retcode in return_code_count:
                return_code_count[retcode].append(repo_name)
            else:
                return_code_count[retcode] = [repo_name]

        log_msg = '%s"%s" got ' % (self.log_prefix, git_command)
        for rc in sorted(return_code_count.keys()):
            log_msg += 'rc=%s (%s repo%s%s), ' % (
                        rc,
                        len(return_code_count[rc]),
                        's' if len(return_code_count[rc]) != 1 else '',
                        '' if rc == 0 else ': ' + ', '.join(sorted(return_code_count[rc])),  # use of .join to avoid u'...' in output
                        )
            max_rc = rc
        if log_msg.endswith(', '):
            log_msg = log_msg[:-2]
        self.logger.log(logging.ERROR if max_rc else logging.INFO if not self.options.quiet else logging.DEBUG, log_msg)
        return max_rc


    def _one_git_repo(self, command, directory, prefix):
        if not self.options.quiet:
            self.logger.info('%sRunning: %s in %s' % (self.log_prefix, command, directory))

        if not self.options.dry_run:
            sys.stdout.flush()
            sys.stderr.flush()
            try:
                # set environment variables to pass to git command extensions
                os.environ['PEWMA_PY_WORKSPACE_GIT_LOC'] = self.workspace_git_loc
                if sys.stdin.encoding is not None:
                    os.environ['PEWMA_PY_COMMAND'] = command.encode(sys.stdin.encoding)
                    os.environ['PEWMA_PY_DIRECTORY'] = directory.encode(sys.stdin.encoding)
                else:
                    os.environ['PEWMA_PY_COMMAND'] = str(command)
                    os.environ['PEWMA_PY_DIRECTORY'] = str(directory)
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, cwd=directory)
                out, err = process.communicate()
                out, err = out.rstrip(), err.rstrip()
                retcode = process.returncode
            except OSError:
                raise PewmaException('ERROR: "%s" failed in %s: %s' % (command, directory, sys.exc_info()[1],))

            if self.options.repo_prefix:
                if len(out)!=0 or len(err)!=0:
                    print(prefix % os.path.basename(directory).strip(), end='')
                    try:
                        if ((len(out) and len(err)) or              # if both out and err
                            (('\n' in out) or ('\r' in out)) or     # if out is multiline
                            (('\n' in err) or ('\r' in err))):      # if err is multiline
                            print("...")                            # start it on a new line
                    except UnicodeDecodeError:
                        if (len(out)>100) or (len(err)>100):
                            print("...")                            # start it on a new line
            if err:
                print(err, file=sys.stderr)
            if out:
                if self.options.max_git_output > 0:
                    print(out[0:self.options.max_git_output])
                    if len(out) > self.options.max_git_output:
                        print('... truncated "', command, '" in ',os.path.basename(directory).strip(), ' ...', sep='')
                else:
                    print(out)
            sys.stderr.flush()
            sys.stdout.flush()
            if retcode:
                self.logger.error('Return Code: %s running: %s in %s'% (retcode, command, directory))
            else:
                self.logger.debug('Return Code: %s' % (retcode,))
            return retcode


    def action_clean(self):
        """ Processes command: clean
        """
        return self.run_buckminster_in_subprocess(('clean',), scan_for_materialize_errors=False, scan_compile_messages=False)


    def action_bmclean(self):
        """ Processes command: bmclean
        """

        if len(self.arguments) > 1:
            raise PewmaException('ERROR: bmclean command has too many arguments')

        self.set_site_name(self.arguments and self.arguments[0])
        self.set_buckminster_properties_path(self.site_name)
        self.logger.info('buckminster output for site "%s" will be cleaned' % (self.site_name,))

        self.logger.info('Writing buckminster commands to "%s"' % (self.script_file_path,))
        properties_text = '-P%s ' % (self.buckminster_properties_path,)
        for keyval in self.options.system_property:
            properties_text += '-D%s ' % (keyval,)
        if self.options.buckminster_root_prefix:
            properties_text += '-Dbuckminster.root.prefix=%s ' % (os.path.abspath(self.options.buckminster_root_prefix),)
        with open(self.script_file_path, 'w') as script_file:
            script_file.write('### File generated ' + time.strftime("%a, %Y/%m/%d %H:%M:%S %z") +
                              ' (' + os.environ.get('BUILD_URL','$BUILD_URL:missing') + ')\n')
            script_file.write('importproxysettings\n')  # will import proxy settings from Java system properties
            script_file.write('perform ' + properties_text)
            script_file.write('-Dtarget.os=* -Dtarget.ws=* -Dtarget.arch=* ')
            script_file.write('%(site_name)s#buckminster.clean\n' % {'site_name': self.site_name})

        if self.isWindows:
            script_file_path_to_pass = '"%s"' % (self.script_file_path,)
        else:
            script_file_path_to_pass = self.script_file_path
        return self.run_buckminster_in_subprocess(('--scriptfile', script_file_path_to_pass), scan_for_materialize_errors=False, scan_compile_messages=False)


    def action_buildthorough(self):
        return self._action_build(thorough=True)
    def action_buildinc(self):
        return self._action_build(thorough=False)
    def action_build(self):
        return self._action_build(thorough=True)

    def _action_build(self, thorough):
        """ Processes command: build
        """

        self.logger.info('Writing buckminster commands to "%s"' % (self.script_file_path,))
        with open(self.script_file_path, 'w') as script_file:
            script_file.write('### File generated ' + time.strftime("%a, %Y/%m/%d %H:%M:%S %z") +
                              ' (' + os.environ.get('BUILD_URL','$BUILD_URL:missing') + ')\n')
            script_file.write('importproxysettings\n')  # will import proxy settings from Java system properties
            if thorough:
                script_file.write('build --thorough\n')
            else:
                script_file.write('build\n')

        # if the workspace has a settings file specifically for Eclipse Mars (which is what Buckminster is), use that.
        mars_settings_file_status = self._switch_mars_settings_file_in()
        if mars_settings_file_status > 1:
            return mars_settings_file_status

        if self.isWindows:
            script_file_path_to_pass = '"%s"' % (self.script_file_path,)
        else:
            script_file_path_to_pass = self.script_file_path
        bm_exit_code =  self.run_buckminster_in_subprocess(('--scriptfile', script_file_path_to_pass), scan_for_materialize_errors=False, scan_compile_messages=True)

        if mars_settings_file_status:
            return self._switch_mars_settings_file_out() or bm_exit_code
        else:
            return bm_exit_code


    def _switch_mars_settings_file_in(self):
        """ If the workspace has a settings file specifically for Eclipse Mars (which is what Buckminster is), use that. See DAQ-1511.
            The code attempts to cope with a previous run having abended at some point.
            Returns:
                False  - settings were not switched in
                True   - settings were switched in (and hence should be switched out after the action is complete)
                2      - a non-zero return code indicating an error
        """

        settings_dir = os.path.join(self.workspace_loc, '.metadata', '.plugins', 'org.eclipse.core.runtime', '.settings')
        if not os.path.isdir(settings_dir):
            return False  # don't need to restore settings after action completes
        pde_settings_default = os.path.join(settings_dir, 'org.eclipse.pde.prefs')
        pde_settings_MARS = os.path.join(settings_dir, 'org.eclipse.pde.prefs.MARS')
        pde_settings_original = os.path.join(settings_dir, 'org.eclipse.pde.prefs.ORIGINAL')
        if not os.path.isfile(pde_settings_MARS):
            return False  # don't need to restore settings after action completes

        # rename org.eclipse.pde.prefs --> org.eclipse.pde.prefs.ORIGINAL
        if os.path.isfile(pde_settings_default):
            if not os.path.isfile(pde_settings_original):
                try:
                    self.logger.info('Renaming "%s" to "%s"' % (pde_settings_default, pde_settings_original))
                    os.rename(pde_settings_default, pde_settings_original)
                except (OSError) as e:
                     self.logger.critical('Error renaming "%s" to "%s"' % (pde_settings_default, pde_settings_original))
                     return 2
            else:
                if filecmp.cmp(pde_settings_default, pde_settings_original, shallow=False):
                    self.logger.info('Removing "%s"' % (pde_settings_default,))
                    os.remove(pde_settings_default)
                else:
                    self.logger.critical('Error renaming "%s" to "%s": latter already exists' % (pde_settings_default, pde_settings_original))
                    return 2
        # rename org.eclipse.pde.prefs.MARS --> org.eclipse.pde.prefs
        try:
            self.logger.info('Renaming "%s" to "%s"' % (pde_settings_MARS, pde_settings_default))
            os.rename(pde_settings_MARS, pde_settings_default)
        except (OSError) as e:
            self.logger.critical('Error renaming "%s" to "%s"' % (pde_settings_MARS, pde_settings_default))
            return 2
        return True


    def _switch_mars_settings_file_out(self):
        settings_dir = os.path.join(self.workspace_loc, '.metadata', '.plugins', 'org.eclipse.core.runtime', '.settings')
        if not os.path.isdir(settings_dir):
            return 0
        pde_settings_default = os.path.join(settings_dir, 'org.eclipse.pde.prefs')
        pde_settings_MARS = os.path.join(settings_dir, 'org.eclipse.pde.prefs.MARS')
        pde_settings_original = os.path.join(settings_dir, 'org.eclipse.pde.prefs.ORIGINAL')

        # rename org.eclipse.pde.prefs --> org.eclipse.pde.prefs.MARS
        try:
            self.logger.info('Renaming "%s" to "%s"' % (pde_settings_default, pde_settings_MARS))
            os.rename(pde_settings_default, pde_settings_MARS)
        except (OSError) as e:
             self.logger.critical('Error renaming "%s" to "%s"' % (pde_settings_default, pde_settings_MARS))
             return 2
        # rename org.eclipse.pde.prefs --> org.eclipse.pde.prefs.MARS
        try:
            self.logger.info('Renaming "%s" to "%s"' % (pde_settings_original, pde_settings_default))
            os.rename(pde_settings_original, pde_settings_default)
        except (OSError) as e:
             self.logger.critical('Error renaming "%s" to "%s"' % (pde_settings_original, pde_settings_default))
             return 2
        return 0


    def action_target(self):
        """ Processes command: target [ path/to/name.target ]
        """

        if not self.arguments:
            return self.run_buckminster_in_subprocess(('listtargetdefinitions',), scan_for_materialize_errors=False, scan_compile_messages=False)

        if len(self.arguments) > 1:
            raise PewmaException('ERROR: target command has too many arguments')

        target = self.arguments[0]
        if not target.endswith( '.target' ):
            raise PewmaException('ERROR: target "%s" is not a valid target name (it must end with .target)' % (target,))

        if os.path.isabs(target):
            path = os.path.realpath(os.path.abspath(target))
            if not path.startswith( self.workspace_loc + os.sep ):
                raise PewmaException('ERROR: target "%s" is not within the workspace ("%s")' % (path, self.workspace_loc))
        else:
            path = os.path.realpath(os.path.abspath(os.path.join(self.workspace_loc, target)))
        if not os.path.isfile(path):
            raise PewmaException('ERROR: target file "%s" ("%s") does not exist' % (target, path))

        return self.run_buckminster_in_subprocess(('importtargetdefinition', '--active',
                                                   path[len(self.workspace_loc)+1:]), scan_for_materialize_errors=False, scan_compile_messages=False)  # +1 for os.sep


    def action_sites(self):
        sites = self.set_available_sites()
        self.logger.info('Available sites in %s: %s' % (self.workspace_git_loc, sorted(self.available_sites) or '<none>'))


    def action_site_p2(self):
        return self._action_site_p2_or_action_site_p2_zip(action_zip=False)
    def action_site_p2_zip(self):
        return self._action_site_p2_or_action_site_p2_zip(action_zip=True)

    def _action_site_p2_or_action_site_p2_zip(self, action_zip):
        """ Processes command: site.p2 [ <site> ]
                           or: site.p2.zip [ <site> ]
        """

        if len(self.arguments) > 1:
            raise PewmaException('ERROR: site.p2%s command has too many arguments' % ('', '.zip')[action_zip])

        self.set_site_name(self.arguments and self.arguments[0])
        self.set_buckminster_properties_path(self.site_name)
        self.logger.info('p2 site "%s" will be built' % (self.site_name,))

        self.logger.info('Writing buckminster commands to "%s"' % (self.script_file_path,))
        properties_text = '-P%s ' % (self.buckminster_properties_path,)
        for keyval in self.options.system_property:
            properties_text += '-D%s ' % (keyval,)
        if self.options.buckminster_root_prefix:
            properties_text += '-Dbuckminster.root.prefix=%s ' % (os.path.abspath(self.options.buckminster_root_prefix),)
        with open(self.script_file_path, 'w') as script_file:
            script_file.write('### File generated ' + time.strftime("%a, %Y/%m/%d %H:%M:%S %z") +
                              ' (' + os.environ.get('BUILD_URL','$BUILD_URL:missing') + ')\n')
            script_file.write('importproxysettings\n')  # will import proxy settings from Java system properties
            if not self.options.assume_build:
                script_file.write('build --thorough\n')
            script_file.write('perform ' + properties_text)
            script_file.write('-Dtarget.os=* -Dtarget.ws=* -Dtarget.arch=* %(site_name)s#site.p2%(zip_action)s\n' %
                              {'site_name': self.site_name, 'zip_action': ('', '.zip')[action_zip]})

        if self.isWindows:
            script_file_path_to_pass = '"%s"' % (self.script_file_path,)
        else:
            script_file_path_to_pass = self.script_file_path
        return self.run_buckminster_in_subprocess(('--scriptfile', script_file_path_to_pass), scan_for_materialize_errors=False)


    def action_product(self):
        return self._product_or_product_zip(action_zip=False)
    def action_product_zip(self):
        return self._product_or_product_zip(action_zip=True)

    def _product_or_product_zip(self, action_zip):
        """ Processes command: product [ <site> ] [ <platform> ... ]
                           or: product.zip [ <site> ] [ <platform> ... ]
        """

        self.set_available_sites()
        platforms = set()
        all_platforms_specified = False

        for (index, arg) in enumerate(self.arguments):
            # interpret any site / platform arguments, recognising that all arguments are optional
            if index == 0:
                self.set_site_name(arg, must_exist=False)
            if (index != 0) or (not hasattr(self, 'site_name')) or (not self.site_name):
                if arg == 'all':
                    all_platforms_specified = True
                    for (p, _) in PLATFORMS_AVAILABLE:
                        platforms.add(p)
                else:
                    for (p, a) in PLATFORMS_AVAILABLE:
                        if arg in a:
                            platforms.add(p)
                            break
                    else:
                        raise PewmaException('ERROR: "%s" was not recognised as either a site (in %s), or as a platform name' % (arg, self.workspace_git_loc))

        if not hasattr(self, 'site_name') or not self.site_name:
            self.set_site_name(None)
        if platforms:
            platforms = sorted(platforms)
        else:
            platforms = [self.platform]  # platforms will be the current platform

        self.logger.info('Product "%s" will be built for %d platform%s: %s' % (self.site_name, len(platforms), ('', 's')[bool(len(platforms)>1)], platforms))

        # Special handling for the case where we are building the server product
        # This is sometimes done in parallel (e.g. someone is setting up multiple GDAs from one machine)
        # Explicitly set buckminster.root.prefix to a name that will be unique
        # (If the IDE is used, that continues to use the default from the properties file)
        # We don't do this for clients, as we don't expect them to have parallel product exports for the same client on the same machine
        if not self.options.buckminster_root_prefix:
            if (self.site_name == 'uk.ac.diamond.daq.server.site') and self.isLinux:
                self.options.buckminster_root_prefix = '/tmp/uk.ac.diamond.daq.server.site_' + self.start_time.strftime('%Y%m%d_%H%M%S.%f')

        self.set_buckminster_properties_path(self.site_name)
        self.logger.info('Writing buckminster commands to "%s"' % (self.script_file_path,))
        properties_text = '-P%s ' % (self.buckminster_properties_path,)
        for keyval in self.options.system_property:
            properties_text += '-D%s ' % (keyval,)
        if self.options.buckminster_root_prefix:
            properties_text += '-Dbuckminster.root.prefix=%s ' % (os.path.abspath(self.options.buckminster_root_prefix),)
        with open(self.script_file_path, 'w') as script_file:
            script_file.write('### File generated ' + time.strftime("%a, %Y/%m/%d %H:%M:%S %z") +
                              ' (' + os.environ.get('BUILD_URL','$BUILD_URL:missing') + ')\n')
            script_file.write('importproxysettings\n')  # will import proxy settings from Java system properties
            if not self.options.assume_build:
                script_file.write('build --thorough\n')
            script_file.write('perform ' + properties_text)
            script_file.write('-Dtarget.os=* -Dtarget.ws=* -Dtarget.arch=* ')
            for p in platforms:
                perform_options = {'action': 'create.product.zip' if action_zip else 'create.product', 'withsymlink': '', 'site_name': self.site_name,
                                   'os': p.split(',')[0], 'ws': p.split(',')[1], 'arch': p.split(',')[2]}
                if self.options.recreate_symlink and (p == 'linux,gtk,x86_64') and not action_zip:
                    perform_options['withsymlink'] = '-with.symlink'
                script_file.write(' %(site_name)s#%(action)s-%(os)s.%(ws)s.%(arch)s%(withsymlink)s' % perform_options)
            script_file.write('\n')

        # if the workspace has a settings file specifically for Eclipse Mars (which is what Buckminster is), use that.
        mars_settings_file_status = self._switch_mars_settings_file_in()
        if mars_settings_file_status > 1:
            return mars_settings_file_status

        if self.isWindows:
            script_file_path_to_pass = '"%s"' % (self.script_file_path,)
        else:
            script_file_path_to_pass = self.script_file_path

        bm_exit_code =  self.run_buckminster_in_subprocess(('--scriptfile', script_file_path_to_pass), scan_for_materialize_errors=False)

        if mars_settings_file_status:
            return self._switch_mars_settings_file_out() or bm_exit_code
        else:
            return bm_exit_code


    def _iterate_ant(self, target):
        """ Processes using an ant target
        """

        selected_projects = self.get_selected_imported_projects_with_releng_ant()
        return self.run_ant_in_subprocess((selected_projects, target))


    def action_developer_test(self):
        """ Available for testing during development
        """

        pass

###############################################################################
#  Run Buckminster                                                            #
###############################################################################

    def report_executable_location(self, executable_name):
        """ Determines the path to an executable (used when no version number is available)
            Writes the path to the log
            Returns the path string
        """

        if executable_name in self.executable_locations:
            return self.executable_locations[executable_name]
        loc = None
        if self.isLinux:
            # "which" command only available on Linux
            try:
                whichrun = subprocess.Popen(('which', '-a', executable_name), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                (stdout, stderr) = whichrun.communicate(None)
                if not whichrun.returncode:
                    loc = stdout.strip()
            except:
                pass
        if loc:
            self.logger.info('%s%s install that will be used: %s' % (self.log_prefix, executable_name, loc))
        else:
            self.logger.warn('%s%s install to be used could not be determined' % (self.log_prefix, executable_name))
        self.executable_locations[executable_name] = loc
        return loc


    def report_and_check_java_version(self):
        """ Determines the Java version number, something like 1.7.0_17
            Writes the version number to the log (if it has not already been written)
            Returns the version number string
        """

        if not self.java_inspected:
            try:
                javarun = subprocess.Popen(('java', '-XshowSettings:properties', '-version'), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)  #  java -version writes to stderr
                (stdout, stderr) = javarun.communicate(None)
                if not javarun.returncode:
                    for line in stdout.splitlines():
                        line = line.strip()
                        if line.startswith('java.io.tmpdir = '):
                            self.java_default_tmpdir = line[len('java.io.tmpdir = '):]
                            continue
                        if line.startswith('java version "'):
                            self.java_version_current = line[len('java version "'):].partition('"')[0]
                            if self.java_default_tmpdir:
                                break  # we've found both items we were looking for
            except:
                pass
            if self.java_version_current:
                self.logger.info('%sJava version that will be used: %s' % (self.log_prefix, self.java_version_current))
            else:
                self.logger.warn('%sJava version to use could not be determined' % (self.log_prefix,))
            if self.java_default_tmpdir:
                self.logger.debug('%sJava default java.io.tmpdir: %s' % (self.log_prefix, self.java_default_tmpdir))
            else:
                self.logger.warn('%sJava default java.io.tmpdir could not be determined' % (self.log_prefix,))
            self.java_inspected = True

        if not self.options.skip_java_version_check:
            if self.java_version_current and self.valid_java_versions:  # if we know the java version, and the acceptable versions
                for acceptable_version in self.valid_java_versions:
                    if self.java_version_current.startswith(acceptable_version):
                        break
                else:
                    raise PewmaException('ERROR: current java version is %s, but must start with one of %s' %
                                         (self.java_version_current, self.valid_java_versions,))

        return self.java_version_current


    def determine_java_io_tmpdir(self):
        """ If the environment variable "JENKINS_java_io_tmpdir_alternative" was specified,
            determine the amount of free space there, and use that for java.io.tmpdir if
            there's more free space than the default location.
        """

        java_io_tmpdir_alternative = os.environ.get('JENKINS_java_io_tmpdir_alternative')  # specified in the Jenkins agent configuration
        if (not java_io_tmpdir_alternative) or (not self.java_default_tmpdir):
            return

        # determine free space in alternative location
        try:
            statvfs = os.statvfs(java_io_tmpdir_alternative)
        except OSError:
            return
        alternative_free = (statvfs.f_frsize * statvfs.f_bavail) // 1024  # the number of free 1K blocks on the volume
        if alternative_free < 4*1024*1024:  # look for at least 4GB free
            return

        # an alternative was specified, and it has at least 4GB free
        # determine free space in default location 
        try:
            statvfs = os.statvfs(self.java_default_tmpdir)
        except OSError:
            return
        default_free = (statvfs.f_frsize * statvfs.f_bavail) // 1024  # the number of free 1K blocks on the volume

        if alternative_free <= default_free:
            return

        new_tmpdir = os.path.join(java_io_tmpdir_alternative, datetime.datetime.today().strftime("%Y%m%d_%H%M%S_") + os.environ.get('BUILD_TAG', ''))
        try:
            os.mkdir(new_tmpdir)
        except:
            return
        return new_tmpdir


    def Xvfb_display_number_calculate(self):
        """ Tests are sometimes run without a GUI (X-Server), e.g. when running in a Jenkins slave started from the command line.
            However, certain tests require a GUI. The answer is to start a simulated X-server, using Xvfb (X virtual frame buffer) and attach it to a $DISPLAY.
            If more than one test job is run in parallel, each job should get its own Xvfb simulated display.
            This routine simply determines what the display number should be.
        """

        if "linux" in platform.system().lower():
            if os.environ.get("EXECUTOR_NUMBER"):
                jenkins_executor = os.environ.get("EXECUTOR_NUMBER")
                try:
                    return 9123 + int(jenkins_executor) + 1
                except (ValueError, TypeError):
                    return 9123
            else:
                try:
                    return 9200 + int(("00%s" % os.getpid())[-2:])  # base on last 2 digits of PID
                except (ValueError, TypeError):
                    return 9223
        else:
            return None


    def run_buckminster_in_subprocess(self, buckminster_args, scan_for_materialize_errors=True, scan_compile_messages=True):
        """ Generates and runs the buckminster command
            scan_for_materialize_errors/scan_compile_messages are just an optimisation; set to False if not materializing/building
        """

        self.report_executable_location('buckminster')
        self.report_and_check_java_version()

        buckminster_command = ['buckminster']
        if self.options.debug_options_file:
            buckminster_command.extend(('-debug', self.options.debug_options_file))
        buckminster_command.extend(('-application', 'org.eclipse.buckminster.cmdline.headless'))
        buckminster_command.extend(('--loglevel', self.options.log_level.upper()))
        buckminster_command.extend(('-data', self.workspace_loc))  # do not quote the workspace name (it should not contain blanks)
        buckminster_command.extend(buckminster_args)

        vmargs_to_add = []
        # For Buckminster 4.5, need to specify UseSplitVerifier: see https://bugs.eclipse.org/bugs/show_bug.cgi?id=471115
        # Always specify UseSplitVerifier unless we are sure that this is not Buckminster 4.5
        possibly_bucky_4point5_plus = True
        if self.executable_locations['buckminster']:
            for old_version in ('/dls_sw/apps/buckminster/64/4.4-', '/dls_sw/apps/buckminster/64/4.3-'):
                if old_version in self.executable_locations['buckminster']:
                    possibly_bucky_4point5_plus = False
                    break
        if possibly_bucky_4point5_plus:
            vmargs_to_add.append('-noverify')
        # if debugging memory allocation, add this parameter: '-XX:+PrintFlagsFinal'
        if not self.isWindows:  # these extra options need to be removed on my Windows XP 32-bit / Java 1.7.0_25 machine
            vmargs_to_add.extend(('-Xms768m', '-Xmx1536m', '-XX:+UseG1GC', '-XX:MaxGCPauseMillis=1000'))
        if self.java_proxy_system_properties:
            vmargs_to_add.extend(self.java_proxy_system_properties)
        for jvmarg in self.options.jvmargs:
            if jvmarg.startswith(('osgi.configuration.area', 'osgi.user.area', 'equinox.statechange.timeout')):
                # fix up arguments that are missing the leading "-D"
                vmargs_to_add.extend(('"-D%s" ' % (jvmarg,),))
            else:
                vmargs_to_add.extend(('"%s" ' % (jvmarg,),))
        if vmargs_to_add:
            buckminster_command.append('-vmargs')
            buckminster_command.extend(vmargs_to_add)

        buckminster_command = ' '.join(buckminster_command)
        self.logger.info('%sRunning: %s' % (self.log_prefix, buckminster_command))
        try:
            scriptfile_index = buckminster_args.index('--scriptfile')
        except ValueError:
            pass  # no script file
        else:
            script_file_path_to_pass = buckminster_args[scriptfile_index+1]
            script_file_path_to_pass = script_file_path_to_pass.strip()  # remove leading whitespace
            if self.isWindows:
                assert script_file_path_to_pass.startswith('"')
                trailing_quote_index = script_file_path_to_pass.find('"', 2)
                assert trailing_quote_index != -1
                script_file_path_to_pass = script_file_path_to_pass[1:trailing_quote_index]  # remove surrounding quotes used on Windows
            if not self.options.dry_run:  # script file will not have been written if dry run
                with open(script_file_path_to_pass) as script_file:
                    for line in script_file.readlines():
                        self.logger.debug('%s(script file): %s' % (self.log_prefix, line))

        system_problems = []
        jgit_errors_repos = []
        jgit_errors_general = []
        project_error_projects = []
        buckminster_bugs = []
        compile_error_bugs = []  # compile errors caused by Buckminster bugs
        compile_errors_seen = False  # regular compile errors
        if not self.options.dry_run:
            sys.stdout.flush()
            sys.stderr.flush()
            retcode = 2  # assume failure, we'll set to 0 if success
            try:
                process = subprocess.Popen(buckminster_command, bufsize=1, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
                last_text_to_suppress = OUTPUT_LINES_TO_SUPPRESS[-1]
                seen_last_text_to_suppress = False  # optimisation to avoid looking for OUTPUT_LINES_TO_SUPPRESS once we've seen them all
                for line in iter(process.stdout.readline, b''):
                    # sometimes there are system problems
                    # sometimes JGit gets intermittent failures (network?) when cloning a repository
                    # sometimes Buckminster detects an error in the projects
                    # sometimes Buckminster hits an intermittent bug
                    for (error_pattern, error_summary) in SYSTEM_PROBLEM_ERROR_PATTERNS:
                        system_problem = re.search(error_pattern, line)
                        if system_problem:
                            system_problems.append(error_summary)
                    if scan_for_materialize_errors:
                        for (error_pattern, error_summary) in JGIT_ERROR_PATTERNS:
                            jgit_error = re.search(error_pattern, line)
                            if jgit_error:
                                if isinstance(error_summary, int):
                                    jgit_errors_repos.append(os.path.basename(jgit_error.group(error_summary)))
                                else:
                                    jgit_errors_general.append(error_summary)
                        for (error_pattern, error_summary) in PROJECT_ERROR_PATTERNS:
                            project_error = re.search(error_pattern, line)
                            if project_error:
                                try:
                                    project_error_projects.append(project_error.group(error_summary))
                                except:
                                    project_error_projects.append('<unknown>')
                        for (error_pattern, error_summary) in BUCKMINSTER_BUG_ERROR_PATTERNS:
                            buckminster_bug = re.search(error_pattern, line)
                            if buckminster_bug:
                                buckminster_bugs.append(error_summary)
                    try:
                        if self.options.suppress_compile_warnings and line[0:len('Warning: file ')] == 'Warning: file ':
                            continue  # finished with this line of output
                    except UnicodeDecodeError:
                        pass
                    if scan_compile_messages:
                        for (error_pattern, error_summary) in COMPILE_ERROR_DUE_TO_BUCKMINSTER_BUG_PATTERNS:
                            compile_error_bug = re.search(error_pattern, line)
                            if compile_error_bug:
                                compile_error_bugs.append(error_summary)
                                break
                        else:
                            try:
                                if line[0:len('Error: file ')] == 'Error: file ':
                                    compile_errors_seen = True
                            except UnicodeDecodeError:
                                pass
                    if seen_last_text_to_suppress:
                        print(line, end='')  # don't add an extra newline
                    else:
                        # Hack: if line contains non-ASCII characters, then "if line == x:" will emit the following warning:
                        # UnicodeWarning: Unicode equal comparison failed to convert both arguments to Unicode - interpreting them as being unequal
                        # So, test explicitly whether a line contains non-ASCII characters, and hand that ourselves
                        try:
                            unicode(line)
                        except UnicodeDecodeError:
                            print(line, end='')  # don't add an extra newline
                        else:
                            for x in OUTPUT_LINES_TO_SUPPRESS:
                                if line == x:
                                    if line == last_text_to_suppress:
                                        seen_last_text_to_suppress = True
                                    break
                            else:
                                print(line, end='')  # don't add an extra newline
                process.communicate() # close p.stdout, wait for the subprocess to exit                
                retcode = process.returncode
            except OSError:
                raise PewmaException('ERROR: Buckminster failed: %s' % (sys.exc_info()[1],))
            sys.stdout.flush()
            sys.stderr.flush()
            if retcode:
                self.logger.error('Buckminster return Code: %s' % (retcode,))
            else:
                self.logger.debug('Buckminster return Code: %s' % (retcode,))
        else:
            retcode = 0

        if any((system_problems, jgit_errors_repos, jgit_errors_general, project_error_projects, buckminster_bugs, compile_error_bugs)):
            retcode = max(int(retcode), 2)
            for error_summary in set(system_problems):  # Use set, since multiple errors could have the same text, and only need logging once
                self.logger.error(error_summary)
            for repo in jgit_errors_repos:
                self.logger.error('Failure cloning ' + repo + ' (probable network issue): you MUST delete the partial clone before retrying')
            for error_summary in set(jgit_errors_general):  # Use set, since multiple errors could have the same text, and only need logging once
                self.logger.error(error_summary + ' (probable network issue): you should probably delete the workspace before retrying')
            for project in set(project_error_projects):  # Use set, since multiple errors could have the same text, and only need logging once
                self.logger.error('Failure importing ' +  project + ' (might be invalid project metadata): take a careful look at the error details before retrying')
            for error_summary in set(buckminster_bugs):  # Use set, since multiple errors could have the same text, and only need logging once
                self.logger.error(error_summary)
            for error_summary in set(compile_error_bugs):  # Use set, since multiple errors could have the same text, and only need logging once
                self.logger.error(error_summary)
            if self.options.prepare_jenkins_build_description_on_error:
                if system_problems:
                    text = system_problems[0]
                elif jgit_errors_repos:
                    text = 'Failure cloning '
                    if len(jgit_errors_repos) == 1:
                        text += jgit_errors_repos[0]
                    else:
                        text += str(len(jgit_errors_repos)) + ' repositories'
                    text += ' (probable network issue)'
                elif jgit_errors_general:
                    text = 'Failure (probable network issue)'
                elif project_error_projects:
                    text = 'Failure importing '
                    if len(project_error_projects) == 1:
                        text += project_error_projects[0]
                    else:
                        text += str(len(project_error_projects)) + ' projects'
                    text += ' (bad project metadata, or intermittent Buckminster bug)'
                elif buckminster_bugs:
                    text = 'Failure (intermittent Buckminster bug)'
                elif compile_error_bugs:
                    text = 'Failure - compile errors, probably due to earlier intermittent Buckminster bug'
                if self.options.prepare_jenkins_build_description_on_error:
                    print('append-build-description: ' + text)
        elif compile_errors_seen and self.options.prepare_jenkins_build_description_on_error:
            print('append-build-description: Failure - compile errors')
        return retcode


    def run_ant_in_subprocess(self, ant_args):
        """ Generates and runs the ant command
        """

        self.report_executable_location('ant')
        self.report_and_check_java_version()

        ant_command = ['ant']
        ant_command.extend(("-nouserlib",))    # Run ant without using the jar files from ${user.home}/.ant/lib
        ant_command.extend(("-noclasspath",))  # Run ant without using CLASSPATH (avoids putting jars from ANT_HOME/lib on the classpath)
        ant_command.extend(("-logger", "org.apache.tools.ant.NoBannerLogger"))
        ant_driver_parent_possible = ('gda-core.git/diamond.releng.tools.gda', 'scisoft-core.git/diamond.releng.tools.dawn', 'diamond-releng.git/diamond.releng.tools')
        for ant_driver_parent in ant_driver_parent_possible:
            ant_driver_loc = os.path.join(self.workspace_git_loc, ant_driver_parent, 'ant-headless', 'ant-driver.ant')
            if os.path.isfile(ant_driver_loc):
                break
        else:
            raise PewmaException('ERROR: Could not find ant-headless/ant-driver.ant under any of %s/%s\n' % (self.workspace_git_loc, ant_driver_parent_possible,))
        ant_command.extend(('-buildfile', ant_driver_loc))

        # pass through GDALargeTestFilesLocation
        loc = self.options.GDALargeTestFilesLocation and self.options.GDALargeTestFilesLocation.strip()
        if loc:
            loc = os.path.expanduser(loc)
            if os.path.isdir(loc):
                if self.options.GDALargeTestFilesLocation.strip().endswith(os.sep):
                    ant_command.extend(("-DGDALargeTestFilesLocation=%s" % (loc,),))
                else:
                    ant_command.extend(("-DGDALargeTestFilesLocation=%s%s" % (loc, os.sep),))
            else:
                raise PewmaException('ERROR: --GDALargeTestFilesLocation=%s does not exist. If any tests require this, they will fail.\n' % (loc,))

        display_number = self.Xvfb_display_number_calculate()
        if display_number:
            ant_command.extend(("-DXvfb-display-number=%s" % display_number,))  # used by diamond.releng.tools/ant-headless/test-common.ant

        new_tmpdir = self.determine_java_io_tmpdir()
        if new_tmpdir:
            ant_command.extend(("-Djava.io.tmpdir=" + new_tmpdir,))

        for keyval in self.options.system_property:
            ant_command.extend(("-D%s " % (keyval,),))

        ant_command.extend(ant_args)

        ant_command = ' '.join(ant_command)
        self.logger.info('%sRunning: %s' % (self.log_prefix, ant_command))

        if not self.options.dry_run:
            sys.stdout.flush()
            sys.stderr.flush()
            try:
                process = subprocess.Popen(ant_command, bufsize=1, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
                for line in iter(process.stdout.readline, b''):
                    print(line, end='')  # don't add an extra newline
                process.communicate() # close p.stdout, wait for the subprocess to exit                
                retcode = process.returncode
            except OSError:
                raise PewmaException('ERROR: Ant failed: %s' % (sys.exc_info()[1],))
            sys.stdout.flush()
            sys.stderr.flush()
            if retcode:
                self.logger.error('Return Code: %s' % (retcode,))
            else:
                self.logger.debug('Return Code: %s' % (retcode,))

            if new_tmpdir:
                try:
                    os.rmdir(new_tmpdir)  # remove the directory if it's empty (i.e. if we never used it)
                except OSError:
                    pass

            return retcode


    def gerrit_commit_hook(self):
        """ Returns a string containing the Gerrit commit hook (which adds a ChangeId to a commit)
        """

        # we cache the commit_hook and never re-fetch it from the Gerrit server
        if hasattr(self, '_gerrit_commit_hook'):
            return self._gerrit_commit_hook

        commit_hook_url = GERRIT_URI_HTTPS + 'tools/hooks/commit-msg'
        try:
            resp = urllib2.urlopen(commit_hook_url, timeout=30)
        except (urllib2.URLError, urllib2.HTTPError, socket.timeout) as e:
            self.logger.error('Error downloading from "%s": %s' % (commit_hook_url, str(e)))
            if self.options.prepare_jenkins_build_description_on_error:
                text = 'append-build-description: Failure downloading Gerrit commit hook (probable network issue)'
                print(text)
            raise PewmaException('ERROR: Gerrit commit hook download failed (network or proxy error, possibly transient): please retry')

        # read the data (it's small enough to do in one chunk)
        self.logger.debug('Downloading %s bytes from "%s"' % (resp.info().get('content-length', '<unknown>'), resp.geturl()))
        try:
            commit_hook = resp.read()
        except Exception as e:
            self.logger.error('Error downloading from "%s": %s' % (commit_hook_url, str(e)))
            if self.options.prepare_jenkins_build_description_on_error:
                text = 'append-build-description: Failure downloading Gerrit commit hook (probable network issue)'
                print(text)
            raise PewmaException('ERROR: Gerrit commit hook download failed (network or proxy error, possibly transient): please retry')
        finally:
            try:
                resp.close()
            except:
                pass

        self._gerrit_commit_hook = commit_hook
        return self._gerrit_commit_hook

###############################################################################
#  Main driver                                                                #
###############################################################################

    def main(self):
        """ Process any command line arguments and run program.
            sys.argv[0] == the directory the script is running from.
            sys.argv[1:] == build options and parameters. """

        if (sys.version < "2.6") or (sys.version >= "3"):
            raise PewmaException("ERROR: This script must be run using Python 2.6 or higher.")
        try:
            if not len(sys.argv):
                raise TypeError
        except TypeError:
            raise PewmaException("ERROR: PewmaManager.main() called with incorrect argument")

        # process command line arguments (prompt if necessary):
        self.define_parser()
        (self.options, positional_arguments) = self.parser.parse_args()
        # print help if requested, or if no arguments
        if self.options.help or not positional_arguments:
            self.parser.print_help()
            print('\nActions and Arguments:')
            for (_, _, _, help) in self.valid_actions_with_help:
                if help:
                     print('    %s' % (help[0]))
                     for line in help[1:]:
                        print('      %s' % (line,))
            return
        self.setup_standard_logging()

        if sys.stdin.encoding is not None:
            positional_arguments = [item.decode(sys.stdin.encoding) for item in positional_arguments]  # in case any unicode characters in input string
        self.action = positional_arguments[0]
        self.arguments = positional_arguments[1:]

        # set the logging level and text for this program's logging
        self.log_prefix = ("", "(DRY_RUN) ")[self.options.dry_run]
        self.logging_console_handler.setLevel( logging._levelNames[self.options.log_level.upper()] )
        if self.action == 'print-workspace-path': self.options.quiet = True  #  the output of print-workspace-path is used in scripts, so be quiet

        # validation of options and action
        self.validate_glob_patterns(self.options.project_includes, self.options.project_excludes, '--include or --exclude')
        self.validate_glob_patterns(self.options.repo_includes, self.options.repo_excludes, '--repo-include or --repo-exclude')
        if sum((self.options.delete, self.options.recreate, self.options.tp_recreate)) > 1:
            raise PewmaException('ERROR: you can specify at most one of --delete, --recreate and --tp-recreate')
        if self.options.gerrit_only and self.options.non_gerrit_only:
            raise PewmaException('ERROR: you can specify at most one of --gerrit-only and --non-gerrit-only')
        if (self.action not in list(self.valid_actions.keys())):
            raise PewmaException('ERROR: action "%s" unrecognised (try --help)' % (self.action,))
        if self.options.delete and self.action not in ('setup', 'materialize'):
            raise PewmaException('ERROR: the --delete option cannot be specified with action "%s"' % (self.action))
        if self.options.recreate and self.action not in ('setup', 'materialize'):
            raise PewmaException('ERROR: the --recreate option cannot be specified with action "%s"' % (self.action))
        if self.options.tp_recreate and self.action != 'materialize':
            raise PewmaException('ERROR: the --tp-recreate option cannot be specified with action "%s", only with "materialize"' % (self.action))
        if self.options.system_property:
            if any((keyval.find('=') == -1) for keyval in self.options.system_property):
                raise PewmaException('ERROR: the -D option must specify a property and value as "key=value"')
        if self.options.debug_options_file:
            self.options.debug_options_file = os.path.abspath(self.options.debug_options_file)
            if not os.path.isfile(self.options.debug_options_file):
                raise PewmaException('ERROR: --debug-options-file is not valid: "%s"' % (self.options.debug_options_file,))

        # determine and validate workspace
        if self.options.workspace:
            self.workspace_loc = os.path.realpath(os.path.abspath(os.path.expanduser(self.options.workspace)))
            log_msg = '%s"--workspace" specified as "%s"' % (self.log_prefix, self.workspace_loc,)
        elif self.action != 'get-branches-expected':
            self._determine_workspace_location_when_not_specified()
            log_msg = '%s"--workspace" defaulted to "%s"' % (self.log_prefix, self.workspace_loc,)
        else:
            self.workspace_loc = None

        if self.workspace_loc:  # will be set, unless (self.action == 'get-branches-expected')
            self.logger.log(logging.INFO if not self.options.quiet else logging.DEBUG, log_msg)
            if ' ' in self.workspace_loc:
                raise PewmaException('ERROR: the "--workspace" directory must not contain blanks')
            if self.workspace_loc.endswith('_git'):
                raise PewmaException('ERROR: the "--workspace" directory must not end with "_git"')
            # if the workspace location was specified, check that it's not inside an existing workspace
            candidate = os.path.dirname(self.workspace_loc)
            while candidate != os.path.dirname(candidate):  # if we are not at the filesystem root (this is a platform independent check)
                if not candidate.endswith('_git'):
                    parent_workspace = (os.path.isdir( os.path.join( candidate, '.metadata')) and candidate)
                else:
                    parent_workspace = (os.path.isdir( os.path.join( candidate[:-4], '.metadata')) and candidate[:-4])
                if parent_workspace:
                    raise PewmaException('ERROR: specified workspace location is inside what looks like another workspace (something containing a .metadata/) at "' + parent_workspace + '"')
                candidate = os.path.dirname(candidate)
            self.workspace_git_loc = self.workspace_loc + '_git'
        elif (self.action != 'get-branches-expected') or any((self.options.workspace_must_exist, self.options.workspace_must_not_exist)):
            raise PewmaException('ERROR: the "--workspace" option must be specified. ' +
                                 os.path.basename(sys.argv[0]) +
                                ' could not determine what workspace to use (based on the current directory).')

        if self.options.workspace_must_exist and (not os.path.isdir(self.workspace_loc)):
            raise PewmaException('ERROR: --workspace-must-exist specified, but workspace does not exist: ' + self.workspace_loc)
        if self.options.workspace_must_not_exist and os.path.isdir(self.workspace_loc):
            raise PewmaException('ERROR: --workspace-must-not-exist specified, but workspace exists: ' + self.workspace_loc)

        # validate --directories_groupname
        if self.isLinux:
            if self.options.directories_groupname == 'dls_dasc' and self.group_dls_dasc_gid:
                self.gid_new = self.group_dls_dasc_gid  # the numeric group id for group dls_dasc
            elif self.options.directories_groupname:
                try:
                    self.gid_new = grp.getgrnam(self.options.directories_groupname).gr_gid  # the numeric group id for the group
                except (KeyError) as e:
                    raise PewmaException('ERROR: Linux group ' + self.options.directories_groupname + ' does not exist')

        # delete previous workspace as required
        if any((self.options.delete, self.options.recreate, self.options.tp_recreate)):
            # Check that the workspace location (specified by the user, or by default) is not obviously wrong.
            # A common mistake is to specify the workspace as a point higher in the directory tree than was actually intended.
            # If we proceed in that case, we would end up deleting files that the user actually expected to be kept.
            # So, if the specified workspace directory contains a workspace within it, or some git repositories,
            # we should abandon without deleting anything.
            if os.path.isdir(self.workspace_loc):
                for root, dirs, files in os.walk(self.workspace_loc):
                    if root == os.path.join(self.workspace_loc, '.recommenders', 'snipmatch', 'repositories'):  # don't worry about git repositories inside here
                        dirs[:] = []
                        continue
                    if any((# if there is any directory called "workspace" BELOW the workspace directory, it's probably wrong
                            'workspace' in dirs,
                            # .metadata ok immediately below specified workspace directory, but not any deeper
                            '.metadata' in dirs and root != self.workspace_loc,
                            # if there is any directory called "*_git" BELOW the workspace directory, it's probably wrong
                            [d for d in dirs if d.endswith('_git')],
                            # if there is any directory called ".git" BELOW the workspace directory, it's probably wrong
                            '.git' in dirs,
                            )):
                        error_message = ('ERROR: You asked for workspace "' + self.workspace_loc +
                                        '" to be deleted, but it contains a workspace or git repositories within it')
                        if root != self.workspace_loc:
                            error_message += ' (in ' + root + ')'
                        raise PewmaException(error_message + '. Abandoning.')

        # convert proxy settings (as specified in environment variables) into Java system properties
        self.java_proxy_system_properties = []
        for env_name in ('http_proxy', 'https_proxy'):
            for variant in (env_name, env_name.upper()):
                setting = os.environ.get(variant,'').strip()
                if setting:
                    protocol = env_name.split('_')[0]
                    host, port = setting.rsplit(':', 1)
                    self.java_proxy_system_properties.extend(('"-D%s.proxyHost=%s"' % (protocol, host), '"-D%s.proxyPort=%s"' % (protocol, port)))
        setting = os.environ.get('no_proxy','').strip()
        if setting:
            self.java_proxy_system_properties.append('"-Dhttp.nonProxyHosts=%s"' % (setting,),)
            self.logger.debug('Note: Experiments suggest that no_proxy is ignored by Buckminster')

        # get some file locations (even though they might not be needed)
        if self.workspace_loc:
            self.script_file_path = os.path.expanduser(self.options.script_file)
            if not os.path.isabs(self.script_file_path):
               self.script_file_path = os.path.abspath(os.path.join(self.workspace_loc, self.script_file_path))

        # invoke function to perform the requested action
        self.start_time = datetime.datetime.now()
        (action_handler, attempt_graylog) = self.valid_actions[self.action]
        use_graylog = attempt_graylog and self.setup_graylog_logging()  # returns True if graylog logging actually available 
        if action_handler:
            exit_code = action_handler(target=self.action)
        else:
            exit_code = getattr(self, 'action_'+self.action.replace('.', '_').replace('-', '_'))()

        if (not self.options.quiet) or use_graylog:
            end_time = datetime.datetime.now()
            run_time = end_time - self.start_time
            seconds = (run_time.days * 86400) + run_time.seconds
            hours, remainder = divmod(seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            final_message = '%sRun time was %02d:%02d:%02d [%s]' % (self.log_prefix, hours, minutes, seconds, self.action)
            if exit_code:
                final_message += ' (Return code: %s)' % (exit_code,)
            if (not self.options.quiet) or exit_code:
                self.logger.log(logging.ERROR if exit_code else logging.INFO, final_message)
            if use_graylog:
                extra_fields = {'elapsed_time': run_time.seconds}
                jenkins_build_tag = os.environ.get('BUILD_TAG', None)
                jenkins_build_url = os.environ.get('BUILD_URL', None)
                if jenkins_build_tag and jenkins_build_url:
                    extra_fields['jenkins_build_tag'] = jenkins_build_tag
                    extra_fields['jenkins_build_url'] = jenkins_build_url
                self.logger_graylog.log(logging.ERROR if exit_code else logging.INFO, final_message, extra = extra_fields)
        return exit_code

###############################################################################
# Command line processing                                                     #
###############################################################################

if __name__ == '__main__':
    pewma = PewmaManager()
    try:
        sys.exit(pewma.main())
    except PewmaException as e:
        print(e)
        sys.exit(3)
    except KeyboardInterrupt:
        if len(sys.argv) > 1:
            print("\nOperation (%s) interrupted and will be abandoned." % ' '.join(sys.argv[1:]))
        else:
            print("\nOperation interrupted and will be abandoned")
        sys.exit(3)

