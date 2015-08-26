#!/usr/bin/env python
from __future__ import absolute_import, division, print_function, unicode_literals

###
### Python Eclipse Workspace MAnager
### platform-independent script to manage development of Eclipse-based products such as GDA and Dawn
###

import ConfigParser
import datetime
import fnmatch
import logging
import optparse
import os
import platform
import re
import shlex
import socket
import StringIO
import subprocess
import sys
import time
import urllib2
import urlparse
import zipfile

COMPONENT_ABBREVIATIONS = [] # tuples of (abbreviation, category, actual component name to use)

for gda_config in (
    'example',                                          # GDA example
    'id18',                                             # APS
    'bm26', 'bm26a',                                    # Dubble at ESRF
    'lpd',                                              # Rutherford
    'all-dls', 'all-mt', 'all-mx',                      # Diamond
    'b16', 'b18', 'b21', 'b23', 'b24', 'dls', 'excalibur',
    'i02', 'i03', 'i04', 'i04-1', 'i05', 'i05-1', 'i06', 'i07', 'i08', 'i09', 'i09-1', 'i09-2',
    'i10', 'i11', 'i11-1', 'i12', 'i13i', 'i13j', 'i14', 'i15', 'i16', 'i18',
    'i19', 'i19-1', 'i19-2', 'i20', 'i20-1', 'i22', 'i23', 'i24', 'lab11', 'mt', 'mx', 'ncdsim'):
    COMPONENT_ABBREVIATIONS.append((gda_config, 'gda', gda_config+'-config'))  # recognise name without -config suffix
    COMPONENT_ABBREVIATIONS.append((gda_config+'-config', 'gda', gda_config+'-config'))  # recognise name with -config suffix

for gda_config in ():
    COMPONENT_ABBREVIATIONS.append((gda_config, 'gda', 'uk.ac.gda.beamline.' + gda_config + '.site'))  # no config project for these beamlines
COMPONENT_ABBREVIATIONS.append(('logpanel', 'gda', ' uk.ac.gda.client.logpanel.site'))
COMPONENT_ABBREVIATIONS.append(('gda-training', 'gda-training', 'gda-training-config'))
COMPONENT_ABBREVIATIONS.append(('sda', 'sda', 'uk.ac.diamond.sda.site'))
COMPONENT_ABBREVIATIONS.append(('dsx', 'ida', 'uk.ac.diamond.dsx.site'))
COMPONENT_ABBREVIATIONS.append(('wychwood', 'ida', 'uk.ac.diamond.dsx.site'))
COMPONENT_ABBREVIATIONS.append(('idabuilder', 'ida', 'uk.ac.diamond.ida.product.site'))
COMPONENT_ABBREVIATIONS.append(('idareport', 'ida', 'uk.ac.diamond.ida.report.site'))
COMPONENT_ABBREVIATIONS.append(('dawnvanilla', 'dawn', 'org.dawnsci.base.site'))
COMPONENT_ABBREVIATIONS.append(('dawndiamond', 'dawn', 'uk.ac.diamond.dawn.site'))
COMPONENT_ABBREVIATIONS.append(('testfiles', 'gda', 'GDALargeTestFiles'))

COMPONENT_CATEGORIES = (
    # category, version, CQuery, template, version_synonyms
    ('gda', 'master', 'gda-master.cquery', 'v2.10', ('master', 'trunk')),
    ('gda', 'masterhplc', 'gda-masterhplc.cquery', 'v2.9', ('masterhplc', 'hplc')),
    ('gda', 'v8.48', 'gda-v8.48.cquery', 'v2.9', ('v8.48', '8.48', '848')),
    ('gda', 'v8.46', 'gda-v8.46.cquery', 'v2.9', ('v8.46', '8.46', '846')),
    ('gda', 'v8.44', 'gda-v8.44.cquery', 'v2.9', ('v8.44', '8.44', '844')),
    ('gda', 'v8.42', 'gda-v8.42.cquery', 'v2.6', ('v8.42', '8.42', '842')),
    ('gda', 'v8.41-xas', 'gda-v8.41-xas.cquery', 'v2.6', ('v8.41-xas', '8.41-xas', '841xas')),
    ('gda', 'v8.40', 'gda-v8.40.cquery', 'v2.6', ('v8.40', '8.40', '840')),
    ('gda', 'v8.39', 'gda-v8.39.cquery', 'v2.6', ('v8.39', '8.39', '839')),
    ('gda', 'v8.38', 'gda-v8.38.cquery', 'v2.6', ('v8.38', '8.38', '838')),
    ('gda', 'v8.36', 'gda-v8.36.cquery', 'v2.5', ('v8.36', '8.36', '836')),
    ('gda', 'v8.34', 'gda-v8.34.cquery', 'v2.4', ('v8.34', '8.34', '834')),
    ('gda', 'v8.32', 'gda-v8.32.cquery', 'v2.4', ('v8.32', '8.32', '832')),
    ('gda', 'v8.30', 'gda-v8.30.cquery', 'v2.4', ('v8.30', '8.30', '830')),
    ('gda', 'v8.30-lnls', 'gda-v8.30-lnls.cquery', 'v2.4', ('v8.30-lnls', '8.30-lnls', '830-lnls')),
    ('gda', 'v8.28', 'gda-v8.28.cquery', 'v2.4', ('v8.28', '8.28', '828')),
    ('gda', 'v8.26', 'gda-v8.26.cquery', 'v2.3', ('v8.26', '8.26', '826')),
    ('gda', 'v8.24', 'gda-v8.24.cquery', 'v2.3', ('v8.24', '8.24', '824')),
    ('gda', 'v8.22', 'gda-v8.22.cquery', 'v2.2', ('v8.22', '8.22', '822')),
    ('gda', 'v8.20', 'gda-v8.20.cquery', 'v2.2', ('v8.20', '8.20', '820')),
    ('gda', 'v8.18', 'gda-v8.18.cquery', 'v1.0', ('v8.18', '8.18', '818')),
    ('ida', 'master', 'ida-master.cquery', 'v2.8', ('master', 'trunk')),
    ('ida', 'v2.20', 'ida-v2.20.cquery', 'v2.4', ('v2.20', '2.20', '220')),
    ('ida', 'v2.19', 'ida-v2.19.cquery', 'v2.3', ('v2.19', '2.19', '219')),
    ('ida', 'v2.18', 'ida-v2.18.cquery', 'v2.3', ('v2.18', '2.18', '218')),
    ('ida', 'v2.17', 'ida-v2.17.cquery', 'v2.2', ('v2.17', '2.17', '217')),
    ('dawn', 'master', 'dawn-master.cquery', 'v2.10', ('master', 'trunk')),
    ('dawn', '1.9', 'dawn-v1.9.cquery', 'v2.9', ('v1.9', '1.9')),
    ('dawn', '1.8', 'dawn-v1.8.cquery', 'v2.9', ('v1.8', '1.8')),
    ('dawn', '1.7.1', 'dawn-v1.7.1.cquery', 'v2.7', ('v1.7.1', '1.7.1', '171')),
    ('dawn', '1.7', 'dawn-v1.7.cquery', 'v2.7', ('v1.7', '1.7')),
    ('dawn', '1.6', 'dawn-v1.6.cquery', 'v2.6', ('v1.6', '1.6')),
    ('dawn', '1.5', 'dawn-v1.5.cquery', 'v2.6', ('v1.5', '1.5')),
    ('dawn', '1.4.1', 'dawn-v1.4.1.cquery', 'v2.5', ('v1.4.1', '1.4.1')),
    ('dawn', '1.4', 'dawn-v1.4.cquery', 'v2.5', ('v1.4', '1.4')),
    ('dawn', 'v1.0', 'dawn-v1.0.cquery', 'v2.3', ('v1.0', '1.0')),
    ('none', 'master', 'master.cquery', 'v2.3', ('master', 'trunk')),
    ('training', 'master', 'training-trunk.cquery', 'v2.0', ('master', 'trunk')),
    ('training', 'v8.16', 'training-v8.16.cquery', 'v2.0', ('v8.16', '8.16', '816')),
    ('gda-training', 'v8.18', 'gda-training-v8.18.cquery', 'v1.0', ('v8.18', '8.18', '818')),
    )

CATEGORIES_AVAILABLE = []  # dedupe COMPONENT_CATEGORIES while preserving order
for c in COMPONENT_CATEGORIES:
    if c[0] not in CATEGORIES_AVAILABLE:
        CATEGORIES_AVAILABLE.append(c[0])
TEMPLATES_AVAILABLE = sorted(set(c[3] for c in COMPONENT_CATEGORIES))
DEFAULT_TEMPLATE = TEMPLATES_AVAILABLE[-1]  # the most recent

PLATFORMS_AVAILABLE =  (
    # os/ws/arch, acceptable abbreviations
    ('linux,gtk,x86', ('linux,gtk,x86', 'linux32')),
    ('linux,gtk,x86_64', ('linux,gtk,x86_64', 'linux64')),
    ('win32,win32,x86', ('win32,win32,x86', 'win32', 'windows32',)),
    ('win32,win32,x86_64', ('win32,win32,x86_64', 'win64', 'windows64',)),
    ('macosx,cocoa,x86', ('macosx,cocoa,x86', 'macosx32', 'mac32',)),
    ('macosx,cocoa,x86_64', ('macosx,cocoa,x86_64', 'macosx64', 'mac64',)),
    )

TEMPLATE_URI_PARENT = 'http://www.opengda.org/buckminster/templates/'
CQUERY_URI_PARENT = 'http://www.opengda.org/buckminster/base/'

JGIT_ERROR_PATTERNS = ( # JGit error messages that identify an intermittent network problem causing a checkout failure (the affected repository is only sometimes identified)
    ('org\.eclipse\.jgit\.api\.errors\.TransportException: (\S+\.git):\s*($|Connection refused|Connection timed out|verify: false)', 1),  # 1 = first match group is the repository
    ('org\.eclipse\.jgit\.api\.errors\.TransportException: (Connection reset|Short read of block\.)', 'Network error'),  # text = no specifc repository identified
    ('org\.eclipse\.jgit\.api\.errors\.TransportException: \S+://\S+/([^ /\t\n\r\f\v]+\.git): unknown host', 1),  # 1 = first match group is the repository
    ('org\.apache\.http\.conn\.HttpHostConnectException: Connection to .+ refused', 'Connection refused'),  # text = no specifc repository identified
    ('java.net.ConnectException: Connection timed out', 'Network error'),  # text = no specifc repository identified
    ('HttpComponents connection error response code (500|502|503)', 'Server error'),  # text = no specifc repository identified
    ('ERROR:? +No repository found at http://www\.opengda\.org/', 'Server error'),  # text = no specifc repository identified
    )

BUCKMINSTER_BUG_ERROR_PATTERNS = ( # Error messages that identify an intermittent Buckminster bug
    ('ERROR\s+\[\d+\]\s:\sjava\.lang\.ArrayIndexOutOfBoundsException: -1', 'Buckminster intermittent bug - try rerunning'),  # https://bugs.eclipse.org/bugs/show_bug.cgi?id=372470
    )

GERRIT_REPOSITORIES = (
    # repositories whose origin can be switched to Gerrit when gerrit-config is run
    'gda-core.git',
    'gda-dls-beamlines-xas.git',
    'gda-epics.git',
    'gda-pes.git',
    'gda-xas-core.git',
    'training-gerrit-1.git',
    )
GERRIT_SCHEME = 'ssh'
GERRIT_SCHEME_ANON = 'http'
GERRIT_NETLOC = 'gerrit.diamond.ac.uk:29418'
GERRIT_NETLOC_ANON = 'gerrit.diamond.ac.uk:8080'

class GitConfigParser(ConfigParser.SafeConfigParser):
    """ Subclass of the regular SafeConfigParser that handles the leading tab characters in .git/config files """
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
        # Set up logger
        self.logger = logging.getLogger("Pewma")
        self.logger.setLevel(1)

        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S")
        # create console handler
        self.logging_console_handler = logging.StreamHandler()
        self.logging_console_handler.setFormatter(formatter)
        self.logger.addHandler(self.logging_console_handler)

        self.system = platform.system()
        self.isLinux = self.system == 'Linux'
        self.isWindows = self.system == 'Windows'
        self.java_version_current = None
        self.executable_locations = {}

        self.valid_actions_with_help = (
            # 1st item in tuple is the action verb
            # 2nd item in tuple is the action special handler (either "ant" or None)
            # 3rd item in tuple is a tuple of help text lines
            ('setup', None,
                ('setup [<category> [<version>] | <cquery>]',
                 'Set up a new workspace, with the target platform defined, but otherwise empty',
                 '(parameters are the same as for the "materialize" action)',
                 )),
            ('materialize', None,
                ('materialize <component> [<category> [<version>] | <cquery>]',
                 'Materialize a component and its dependencies into a new or existing workspace',
                 'Component can be abbreviated in many cases (eg just the beamline name is sufficient)',
                 'Category can be one of "%s"' % '/'.join(CATEGORIES_AVAILABLE),
                 'Version defaults to master',
                 'CQuery is only required if you need to override the computed value',
                 )),
            ('gerrit-config', None, ('gerrit-config', 'Switch applicable repositories to origin Gerrit and configure for Eclipse',)),
            ('git', None, ('git <command>', 'Issue "git <command>" for all git clones',)),
            ('clean', None, ('clean', 'Clean the workspace',)),
            ('bmclean', None, ('bmclean <site>', 'Clean previous buckminster output',)),
            ('build', None, ('build', '[alias for buildthorough]',)),
            ('buildthorough', None, ('buildthorough', 'Build the workspace (do full build if first incremental build fails)',)),
            ('buildinc', None, ('buildinc', 'Build the workspace (incremental build)',)),
            ('target', None, ('target', 'List target definitions known in the workspace',)),
            ('target', None, ('target path/to/name.target', 'Set the target platform for the workspace',)),
            ('sites', None, ('sites', 'List the available site projects in the workspace',)),
            ('site.p2', None,
                ('site.p2 <site>',
                 'Build the workspace and an Eclipse p2 site',
                 'Site can be omitted if there is just one site project, and abbreviated in most other cases',
                )),
            ('site.p2.zip', None,
                ('site.p2.zip <site>',
                 'Build the workspace and an Eclipse p2 site, then zip the p2 site',
                 'Site can be omitted if there is just one site project, and abbreviated in most other cases',
                )),
            ('product', None,
                ('product <site> [ <platform> ... ]',
                 'Build the workspace and an Eclipse product',
                 'Site can be omitted if there is just one site project, and abbreviated in most other cases',
                 'Platform can be something like linux32/linux64/win32/all (defaults to current platform)',
                )),
            ('product.zip', None,
                ('product.zip <site> [ <platform> ... ]',
                 'Build the workspace and an Eclipse product, then zip the product',
                )),
            ('tests-clean', self._iterate_ant, ('tests-clean', 'Delete test output and results files from JUnit/JyUnit tests',)),
            ('junit-tests', self._iterate_ant, ('junit-tests', 'Run Java JUnit tests for all (or selected) projects',)),
            ('jyunit-tests', self._iterate_ant, ('jyunit-tests', 'Runs JyUnit tests for all (or selected) projects',)),
            ('all-tests', self._iterate_ant, ('all-tests', 'Runs both Java and JyUnit tests for all (or selected) projects',)),
            ('corba-make-jar', self._iterate_ant, ('corba-make-jar', '(Re)generate the corba .jar(s) in all or selected projects',)),
            ('corba-validate-jar', self._iterate_ant, ('corba-validate-jar', 'Check that the corba .jar(s) in all or selected plugins match the source',)),
            ('corba-clean', self._iterate_ant, ('corba-clean', 'Remove temporary files from workspace left over from corba-make-jar',)),
            ('dummy', self._iterate_ant, ()),
            )

        self.valid_actions = dict((action, handler) for (action, handler, help) in self.valid_actions_with_help)

        # if the current directory, or any or its parents, is a workspace, make that the default workspace
        # otherwise, if the directory the script is being run from is within a workspace, make that the default workspace
        self.workspace_loc = None
        candidate = os.getcwd()
        while candidate != os.path.dirname(candidate):  # if we are not at the filesystem root (this is a platform independent check)
            if not candidate.endswith('_git'):
                self.workspace_loc = (os.path.isdir( os.path.join( candidate, '.metadata')) and candidate)
            else:
                self.workspace_loc = (os.path.isdir( os.path.join( candidate[:-4], '.metadata')) and candidate[:-4])
            if self.workspace_loc:
                break
            candidate = os.path.dirname(candidate)


    def define_parser(self):
        """ Define all the command line options and how they are handled. """

        self.parser = optparse.OptionParser(usage="usage: %prog [options] action [arguments ...]", add_help_option=False,
            description="For more information, see the Infrastructure guide at http://www.opengda.org/documentation/")
        self.parser.disable_interspersed_args()
        self.parser.formatter.help_position = self.parser.formatter.max_help_position = 46  # improve look of help
        if 'COLUMNS' not in os.environ:  # typically this is not passed from the shell to the child process (Python)
            self.parser.formatter.width = 120  # so avoid the default of 80 and assume a wider terminal (improve look of help)

        group = optparse.OptionGroup(self.parser, "Workspace options")
        group.add_option('-w', '--workspace', dest='workspace', type='string', metavar='<dir>', default=self.workspace_loc,
                               help='Workspace location (default: ' + (self.workspace_loc or "(None)") + ')')
        group.add_option('--delete', dest='delete', action='store_true', default=False,
                               help='First completely delete current workspace/ and workspace_git/')
        group.add_option('--recreate', dest='recreate', action='store_true', default=False,
                               help='First completely delete current workspace/, but keep any workspace_git/')
        self.parser.add_option_group(group)

        group = optparse.OptionGroup(self.parser, "Materialize options")
        group.add_option('-l', '--location', dest='download_location', choices=('diamond', 'public'), metavar='<location>',
                         help='Download location ("diamond" or "public")')
        group.add_option('-k', '--keyring', dest='keyring', type='string', metavar='<path>',
                         help='Keyring file (for subversion authentication)')
        group.add_option('--materialize.properties.file', dest='materialize_properties_file', type='string', metavar='<path>',
                               default='materialize-properties.txt',
                               help='Properties file, relative to workspace if not absolute (default: %default)')
        group.add_option('--maxParallelMaterializations', dest='maxParallelMaterializations', type='int', metavar='<value>',
                         help='Override Buckminster default')
        group.add_option('--maxParallelResolutions', dest='maxParallelResolutions', type='int', metavar='<value>',
                         help='Override Buckminster default')
        group.add_option('--prepare-jenkins-build-description-on-materialize-error', dest='prepare_jenkins_build_description_on_materialize_error', action='store_true', default=False,
                 help=optparse.SUPPRESS_HELP)
        self.parser.add_option_group(group)

        group = optparse.OptionGroup(self.parser, "Build/Product options")
        group.add_option('--scw', '--suppress-compile-warnings', dest='suppress_compile_warnings', action='store_true', default=False,
                               help='Don\'t print compiler warnings')
        group.add_option('--assume-build', dest='assume_build', action='store_true', default=False, help='Skip explicit build when running "site.p2" or "product" actions')
        group.add_option('--recreate-symlink', dest='recreate_symlink', action='store_true', default=False,
                               help='Create or update the "client" symlink to the built product (linux64 only)')
        group.add_option('--buckminster.properties.file', dest='buckminster_properties_file', type='string', metavar='<path>',
                         help='Properties file, relative to site project if not absolute (default: filenames looked for in order: buckminster.properties, buckminster.beamline.properties)')
        group.add_option('--buckminster.root.prefix', dest='buckminster_root_prefix', type='string', metavar='<path>',
                         help='Prefix for buckminster.output.root and buckminster.temp.root properties')
        self.parser.add_option_group(group)

        group = optparse.OptionGroup(self.parser, "Test/Corba options")
        group.add_option('--include', dest='plugin_includes', type='string', metavar='<pattern>,<pattern>,...', default="",
                               help='Only process plugin names matching one or more of the glob patterns')
        group.add_option('--exclude', dest='plugin_excludes', type='string', metavar='<pattern>,<pattern>,...', default="",
                               help='Do not process plugin names matching any of the glob patterns')
        default_GDALargeTestFilesLocation = '/dls_sw/dasc/GDALargeTestFiles/'  # location at Diamond
        if not os.path.isdir(default_GDALargeTestFilesLocation):
            default_GDALargeTestFilesLocation=""
        group.add_option("--GDALargeTestFilesLocation", dest="GDALargeTestFilesLocation", type="string", metavar=" ", default=default_GDALargeTestFilesLocation,
                         help="Default: %default")
        self.parser.add_option_group(group)

        group = optparse.OptionGroup(self.parser, "General options")
        group.add_option('-D', dest='system_property', action='append', metavar='key=value',
                               help='Pass a system property to Buckminster or Ant')
        group.add_option('-J', dest='jvmargs', action='append', metavar='key=value',
                               help='Pass an additional JVM argument')
        group.add_option('-h', '--help', dest='help', action='store_true', default=False, help='Show help information and exit')
        group.add_option('-n', '--dry-run', dest='dry_run', action='store_true', default=False,
                               help='Log the actions to be done, but don\'t actually do them')
        group.add_option('-s', '--script-file', dest='script_file', type='string', metavar='<path>',
                               default='pewma-script.txt',
                               help='Script file, relative to workspace if not absolute (default: %default)')
        group.add_option('-q', '--quiet', dest='log_level', action='store_const', const='WARNING', help='Shortcut for --log-level=WARNING')
        group.add_option('--log-level', dest='log_level', type='choice', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], metavar='<level>',
                               default='INFO', help='Logging level (default: %default)')
        group.add_option('--skip-proxy-setup', dest='skip_proxy_setup', action='store_true', default=False, help='Don\'t define any proxy settings')
        self.parser.add_option_group(group)

        group = optparse.OptionGroup(self.parser, "Git options")
        group.add_option('-p', '--prefix', dest='repo_prefix', action='store_true', default=False, help='Prefix first line of git command output with the repo directory name.')
        self.parser.add_option_group(group)


    def setup_workspace(self):
        # create the workspace if it doesn't exist, initialise the workspace if it is not set up

        expand_template_required = True
        if os.path.isdir(self.workspace_loc):
            metadata_exists = os.path.exists( os.path.join(self.workspace_loc, '.metadata'))
            if metadata_exists and not os.path.isdir(os.path.join(self.workspace_loc, '.metadata', '.plugins')):
                raise PewmaException('Workspace already exists but is corrupt (invalid .metadata/), please delete: "%s"' % (self.workspace_loc,))
            tp_exists = os.path.exists( os.path.join(self.workspace_loc, 'tp'))
            if tp_exists and not os.path.isfile(os.path.join(self.workspace_loc, 'tp', '.project')):
                raise PewmaException('Workspace already exists but is corrupt (invalid tp/), please delete: "%s"' % (self.workspace_loc,))
            if metadata_exists != tp_exists:
                raise PewmaException('Workspace already exists but is corrupt (only one of .metadata/ and tp/ exist), please delete: "%s"' % (self.workspace_loc,))
            if metadata_exists and tp_exists:
                self.logger.info('Workspace already exists "%s"' % (self.workspace_loc,))
                expand_template_required = False
        else:
            self.logger.info('%sCreating workspace directory "%s"' % (self.log_prefix, self.workspace_loc,))
            if not self.options.dry_run:
                os.makedirs(self.workspace_loc)

        if self.workspace_git_loc and os.path.isdir(self.workspace_git_loc):
            git_count_at_start = len(self._get_git_directories())
            if git_count_at_start:
                self.logger.info('Using %s existing .git repositories (which will not be updated) found in "%s"' % (git_count_at_start, self.workspace_git_loc,))

        if expand_template_required:
            template_zip = os.path.join( self.workspace_loc, self.template_name )
            self.download_workspace_template(TEMPLATE_URI_PARENT + self.template_name, template_zip)
            self.unzip_workspace_template(template_zip, None, self.workspace_loc)
            self.logger.info('%sDeleting "%s"' % (self.log_prefix, template_zip,))
            if not self.options.dry_run:
                os.remove(template_zip)
            return self.run_buckminster_in_subprocess(('clean',))  # for some reason this must be done


    def add_cquery_to_history(self, cquery_to_use):
        ''' remember the CQuery used, for future "File --> Open a Component Query" in the IDE
        '''

        org_eclipse_buckminster_ui_prefs_loc = os.path.join(self.workspace_loc, '.metadata', '.plugins',
          'org.eclipse.core.runtime', '.settings', 'org.eclipse.buckminster.ui.prefs')
        cquery_to_add = CQUERY_URI_PARENT.replace(':', '\:') + cquery_to_use  # note the escaped : as per Eclipse's file format
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


    def add_config_to_strings(self, component_name):
        ''' Save the instance config used in "Window --> Preferences --> Run/Debug --> String Substitution"
            This is referenced in the launchers for GDA servers etc.
        '''

        if component_name.startswith(('all-', 'core-', 'dls-', 'mt-', 'mx-')) or not component_name.endswith('-config'):
            return  # component name is not an instance config, so don't save it 

        org_eclipse_core_variables_prefs_loc = os.path.join(self.workspace_loc, '.metadata', '.plugins',
          'org.eclipse.core.runtime', '.settings', 'org.eclipse.core.variables.prefs')
        if os.path.exists(org_eclipse_core_variables_prefs_loc):
            # there should already be an existing org.eclipse.core.variables.prefs file (it exists in the template workspace)
            replacement_lines = []
            variable_found = False
            file_rewrite_required = False
            with open(org_eclipse_core_variables_prefs_loc, 'r') as oecvp_file:
                for line in oecvp_file.readlines():
                    if not line.startswith('org.eclipse.core.variables.valueVariables='):
                        replacement_lines += line
                    else:
                        m = re.match(r'^org\.eclipse\.core\.variables\.valueVariables=(.+?)<valueVariables>(.+?)<valueVariable(.*?) name\\="GDA_instance_config_name"(.*?) value\\="([^"]+?)"(.*?)/>(.*)$', line)
                        if m:
                            assert not (variable_found or file_rewrite_required)
                            variable_found = True
                            if m.group(5) == component_name:
                                # the new GDA_instance_config_name is the same as the current one, so nothing needs to be changed
                                break 
                            else:
                                # the new GDA_instance_config_name is different from the current one, so update with the new value
                                replacement = 'org.eclipse.core.variables.valueVariables=%s<valueVariables>%s<valueVariable%s name\="GDA_instance_config_name"%s value\="%s"%s/>%s\n' % (
                                  m.group(1), m.group(2), m.group(3), m.group(4), component_name, m.group(6), m.group(7))
                                self.logger.log(5, line)
                                self.logger.log(5, replacement)
                                replacement_lines += replacement
                                file_rewrite_required = True
            if file_rewrite_required:
                if not self.options.dry_run:
                    with open(org_eclipse_core_variables_prefs_loc, 'w') as oecvp_file:
                        for line in replacement_lines:
                            oecvp_file.write(line)
                self.logger.debug('%sUpdated "%s" with %s' % (self.log_prefix, org_eclipse_core_variables_prefs_loc, component_name))


    def delete_directory(self, directory, description):
        if directory and os.path.isdir(directory):
            self.logger.info('%sDeleting %s "%s"' % (self.log_prefix, description, directory,))
            if not self.options.dry_run:
                # shutil.rmtree(directory)  # does not work under Windows of there are read-only files in the directory, such as.svn\all-wcprops
                if self.isLinux:
                    retcode = subprocess.call(('rm', '-rf', directory), shell=False)
                elif self.isWindows:
                    retcode = subprocess.call(('rmdir', '/s', '/q', directory), shell=True)
                else:
                    self.logger.error('Could not delete directory: platform "%s" not recognised' % (self.system,))


    def download_workspace_template(self, source, destination):
        if self.options.dry_run:
            self.logger.info('%sDownloading "%s" to "%s"' % (self.log_prefix, source, destination))
            return

        # open the URL
        try:
            resp = urllib2.urlopen(source, timeout=30)
        except (urllib2.URLError, urllib2.HTTPError, socket.timeout) as e:
            self.logger.error('Error downloading from "%s": %s' % (source, str(e)))
            if self.options.prepare_jenkins_build_description_on_materialize_error:
                text = 'set-build-description: Failure downloading template workspace (probable network issue)'
                print(text)
            raise PewmaException('Workspace template download failed (network error, proxy failure, or proxy not set): please retry')

        # read the data (small enough to do in one chunk)
        self.logger.info('Downloading %s bytes from "%s" to "%s"' % (resp.info().get('content-length', '<unknown>'), resp.geturl(), destination))
        try:
            templatedata = resp.read()
        except Exception as e:
            self.logger.error('Error downloading from "%s": %s' % (source, str(e)))
            if self.options.prepare_jenkins_build_description_on_materialize_error:
                text = 'set-build-description: Failure downloading template workspace (probable network issue)'
                print(text)
            raise PewmaException('Workspace template download failed (network error, proxy failure, or proxy not set): please retry')
        finally:
            try:
                resp.close()
            except:
                pass

        # write the data
        with open(destination, "wb") as template:
            template.write(templatedata)


    def unzip_workspace_template(self, template_zip, member, unzipdir):
        self.logger.info('%sUnzipping "%s%s" to "%s"' % (self.log_prefix, template_zip, '/' +
            member if member else '', unzipdir))  ### requires python 2.6+, Diamond RH5 requires "module load python"
        if self.options.dry_run:
            return
        template = zipfile.ZipFile(template_zip, 'r')
        self.logger.debug('Comment in zip file "%s"' % (template.comment,))
        if not member:
            template.extractall(unzipdir)
        else:
            template.extract(member, unzipdir)
        template.close()


    def set_available_sites(self):
        """ Sets self.available_sites, a dictionary of {site name: project path} entries,
            for all .site projects in the workspace or workspace_git directories
        """

        # we cache self.available_sites and never recompute
        if hasattr(self, 'available_sites'):
            return

        sites = {}
        for parent_dir in [os.path.join(self.workspace_loc, 'sites'), os.path.join(self.workspace_loc, 'features')]:
            # .site projects will be exactly one directory level below the sites/ or features/ directory
            if os.path.isdir(parent_dir):
                for site_dir in os.listdir(parent_dir):
                    if site_dir.endswith('.site') and os.path.exists( os.path.join(parent_dir, site_dir, 'feature.xml')):
                        sites[site_dir] = os.path.join(parent_dir, site_dir)
        if self.workspace_git_loc:
            # .site projects can be up to three directory levels below the git materialize directory
            for level1 in os.listdir(self.workspace_git_loc):
                level1_dir = os.path.join(self.workspace_git_loc, level1)
                if os.path.isdir(level1_dir):
                    for level2 in os.listdir(level1_dir):
                        level2_dir = os.path.join(level1_dir, level2)
                        if os.path.isdir(level2_dir):
                            if level2.endswith('.site') and os.path.exists( os.path.join(level2_dir, 'feature.xml')):
                                sites[level2] = level2_dir
                            else:
                                for level3 in os.listdir(level2_dir):
                                    level3_dir = os.path.join(level2_dir, level3)
                                    if os.path.isdir(level3_dir):
                                        if level3.endswith('.site') and os.path.exists( os.path.join(level3_dir, 'feature.xml')):
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


    def validate_plugin_patterns(self):
        for glob_patterns in (self.options.plugin_includes, self.options.plugin_excludes):
            if glob_patterns:
                for pattern in glob_patterns.split(","):
                    if not pattern:
                        raise PewmaException("ERROR: --include or --exclude contains an empty plugin pattern")
                    if pattern.startswith("-") or ("=" in pattern):
                        # catch a possible error in command line construction
                        raise PewmaException("ERROR: --include or --exclude contains an invalid plugin pattern \"%s\"" % (p,))


    def set_all_plugins_with_releng_ant(self):
        """ Finds all the plugins in the self.workspace_git_loc directory, provided they contain a releng.ant file plus compiled code.
            Result is a dictionary of {plugin-name: relative/path/to/plugin} (the path is relative to self.workspace_git_loc)
        """

        plugin_names_paths = {}
        for root, dirs, files in os.walk(self.workspace_git_loc):
            for d in dirs[:]:
                if d.startswith('.') or d.endswith(('.feature', '.site')):
                    dirs.remove(d)
            if 'releng.ant' in files:
                dirs[:] = []  # plugins are never nested inside plugins, so no need to look beneath this directory
                bin_dir_path = os.path.join(root, 'classes' if os.path.basename(root) == 'uk.ac.gda.core' else 'bin')
                if os.path.isdir(bin_dir_path):
                    # only include this plugin if it contains compiled code (in case the filesystem contains a repo, but the workspace did not import all the projects)
                    for proot, pdirs, pfiles in os.walk(bin_dir_path):
                        for d in pdirs[:]:
                            if d.startswith('.'):
                                pdirs.remove(d)
                        if [f for f in pfiles if not f.startswith('.')]:  # if any non-hidden file in the bin_dir_path directory
                            # return plugin path relative to the parent directory, and plugin name (these will be the same for the subversion plugins)
                            assert os.path.basename(root) not in plugin_names_paths
                            plugin_names_paths[os.path.basename(root)] = os.path.relpath(root, self.workspace_git_loc)
                            break
        self.all_plugins_with_releng_ant = plugin_names_paths


    def get_matching_plugins_with_releng_ant(self, glob_patterns):
        """ Finds all the plugin names that match the specified glob patterns (either --include or --exclude).
        """
        matching_paths_names = []

        for p in glob_patterns.split(","):
            matching_paths_names.extend(fnmatch.filter(self.all_plugins_with_releng_ant.keys(), p))
        return sorted( set(matching_paths_names) )


    def get_selected_plugins_with_releng_ant(self):
        """ Finds all the plugin names that match the specified glob patterns (combination of --include and --exclude).
            If neither --include nor --exclude specified, return the empty string
        """

        if self.options.plugin_includes or self.options.plugin_excludes:
            self.set_all_plugins_with_releng_ant()

            if self.options.plugin_includes:
                included_plugins = self.get_matching_plugins_with_releng_ant(self.options.plugin_includes)
            else:
                included_plugins = self.all_plugins_with_releng_ant

            if self.options.plugin_excludes:
                excluded_plugins = self.get_matching_plugins_with_releng_ant(self.options.plugin_excludes)
            else:
                excluded_plugins = []

            selected_plugins = sorted(set(included_plugins) - set(excluded_plugins))

            if not selected_plugins:
                raise PewmaException("ERROR: no compiled plugins matching --include=%s --exclude=%s found" % (self.options.plugin_includes, self.options.plugin_excludes))
            return "-Dplugin_list=\"%s\"" % '|'.join([self.all_plugins_with_releng_ant[pname] for pname in selected_plugins])

        return ""


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

    def action_setup(self):
        """ Processes command: setup [<category> [<version>] | <cquery>]
        """

        if len(self.arguments) > 2:
            raise PewmaException('ERROR: setup command has too many arguments')

        (category_to_use, version_to_use, cquery_to_use, template_to_use) = self._interpret_context(self.arguments)

        if category_to_use and version_to_use:
            cquery_to_use = self._get_cquery_for_category_version(category_to_use, version_to_use)
            template_to_use = self._get_template_for_category_version(category_to_use, version_to_use)
        if template_to_use:
            self.template_name = 'template_workspace_%s.zip' % (template_to_use,)

        self.setup_workspace()

        if cquery_to_use:
            self.add_cquery_to_history(cquery_to_use)

        return


    def action_materialize(self):
        """ Processes command: materialize <component> [<category> [<version>] | <cquery>]
        """

        if len(self.arguments) < 1:
            raise PewmaException('ERROR: materialize command has too few arguments')
        if len(self.arguments) > 3:
            raise PewmaException('ERROR: materialize command has too many arguments')

        # translate an abbreviated component name to the real component name
        component_to_use = self.arguments[0]
        for abbrev, cat, actual in COMPONENT_ABBREVIATIONS:
            if component_to_use == abbrev:
                component_to_use = actual
                category_implied = cat
                break
        else:
            category_implied = None  # component name is specified verbatim

        # interpret any (category / category version / cquery) arguments
        (category_to_use, version_to_use, cquery_to_use, template_to_use) = self._interpret_context(self.arguments[1:])

        if not category_to_use:
            category_to_use = category_implied
        elif category_implied and (category_implied != category_to_use):
            # if a component abbreviation was provided, it implies a category. If a category was also specified, it must match the implied category 
            raise PewmaException('ERROR: component "%s" is not consistent with category "%s"' % (component_to_use, category_to_use,))

        if not (category_to_use or cquery_to_use):
            raise PewmaException('ERROR: the category for component "%s" is missing (can be one of %s)' % (component_to_use, '/'.join(CATEGORIES_AVAILABLE)))

        if category_to_use and version_to_use:
            if not cquery_to_use:
                cquery_to_use = self._get_cquery_for_category_version(category_to_use, version_to_use)
            template_to_use = self._get_template_for_category_version(category_to_use, version_to_use)

        assert template_to_use and cquery_to_use

        # create the workspace if required
        self.template_name = 'template_workspace_%s.zip' % (template_to_use,)
        exit_code = self.setup_workspace()
        if exit_code:
            self.logger.info('Abandoning materialize: workspace setup failed')
            return exit_code

        self.logger.info('Writing buckminster materialize properties to "%s"' % (self.materialize_properties_path,))
        with open(self.materialize_properties_path, 'w') as properties_file:
            properties_file.write('component=%s\n' % (component_to_use,))
            if self.options.download_location:
                properties_file.write('download.location.common=%s\n' % (self.options.download_location,))

        self.logger.info('Writing buckminster commands to "%s"' % (self.script_file_path,))
        properties_text = '-P%s ' % (self.materialize_properties_path.replace('\\', '/'),)  # convert \ to / in path on Windows (avoiding \ as escape character)
        for keyval in self.options.system_property:
            properties_text += '-D%s ' % (keyval,)
        with open(self.script_file_path, 'w') as script_file:
            if not self.options.skip_proxy_setup:
                script_file.write('importproxysettings\n')  # will import proxy settings from Java system properties
            # set preferences
            if self.options.maxParallelMaterializations:
                script_file.write('setpref maxParallelMaterializations=%s\n' % (self.options.maxParallelMaterializations,))
            if self.options.maxParallelResolutions:
                script_file.write('setpref maxParallelResolutions=%s\n' % (self.options.maxParallelResolutions,))
            script_file.write('import ' + properties_text)
            script_file.write(CQUERY_URI_PARENT + cquery_to_use + '\n')

        if self.isWindows:
            script_file_path_to_pass = '"%s"' % (self.script_file_path,)
        else:
            script_file_path_to_pass = self.script_file_path

        # get buckminster to run the materialize
        (rc, jgit_errors_repos, jgit_errors_general, buckminster_bugs) = self.run_buckminster_in_subprocess(('--scriptfile', script_file_path_to_pass), return_Buckminster_errors=True)
        # sometimes JGit gets intermittent failures (network?) when cloning a repository
        # sometimes Buckminster hits an intermittent bug
        if any((jgit_errors_repos, jgit_errors_general, buckminster_bugs)):
            rc = max(int(rc), 2)
            for repo in jgit_errors_repos:
                self.logger.error('Failure cloning ' + repo + ' (probable network issue): you MUST delete the partial clone before retrying')
            for error_summary in set(jgit_errors_general):  # Use set, since multiple errors coukd have the same text, and only need logging once
                self.logger.error(error_summary + ' (probable network issue): you should probably delete the workspace before retrying')
            for error_summary in set(buckminster_bugs):  # Use set, since multiple errors coukd have the same text, and only need logging once
                self.logger.error(error_summary)
            if self.options.prepare_jenkins_build_description_on_materialize_error:
                if jgit_errors_repos:
                    text = 'set-build-description: Failure cloning '
                    if len(jgit_errors_repos) == 1:
                        text += jgit_errors_repos[0]
                    else:
                        text += str(len(jgit_errors_repos)) + ' repositories'
                    text += ' (probable network issue)'
                elif jgit_errors_general:
                    text = 'set-build-description: Failure (probable network issue)'
                else:
                    text = 'set-build-description: Failure (intermittent Buckminster bug)'
                print(text)

        self.add_cquery_to_history(cquery_to_use)
        self.add_config_to_strings(component_to_use)

        rc = max(rc, self.action_gerrit_config(check_arguments=False) or 0)

        return rc


    def _interpret_context(self, arguments_part):
        """ Processes this part of the arguments: [<category> [<version>] | <cquery>]
            (on behalf of "setup" and "materialize" commands)
        """

        category_to_use = None
        version_to_use = 'master'
        cquery_to_use = None
        template_to_use = DEFAULT_TEMPLATE

        # interpret any (category / category version / cquery) arguments
        if arguments_part:
            category_or_cquery = arguments_part[0]
            if category_or_cquery.endswith('.cquery'):
                cquery_to_use = category_or_cquery
                if len(arguments_part) > 1:
                    raise PewmaException('ERROR: No other options can follow the CQuery')
                for c, v, q, t, s in [cc for cc in COMPONENT_CATEGORIES if cc[2] == cquery_to_use]:
                    template_to_use = t
                    break
            elif category_or_cquery in CATEGORIES_AVAILABLE:
                category_to_use = category_or_cquery
                if len(arguments_part) > 1:
                    version = arguments_part[1].lower()
                    for c, v, q, t, s in [cc for cc in COMPONENT_CATEGORIES if cc[0] == category_to_use]:
                        if version in s:
                            version_to_use = v
                            break
                    else:
                        raise PewmaException('ERROR: category "%s" is not consistent with version "%s"' % (category_to_use, version))
            else:
                raise PewmaException('ERROR: "%s" is neither a category nor a CQuery' % (category_or_cquery,))

        return (category_to_use, version_to_use, cquery_to_use, template_to_use)


    def _get_cquery_for_category_version(self, category, version):
        """ Given a category and version, determine the CQuery that should be used
            (on behalf of "setup" and "materialize" commands)
        """

        assert category and version
        cquery_to_use_list = [cc[2] for cc in COMPONENT_CATEGORIES if cc[0] == category and cc[1] == version]
        assert len(cquery_to_use_list) == 1
        return cquery_to_use_list[0]


    def _get_template_for_category_version(self, category, version):
        """ Given a category and version, determine the template that should be used
            (on behalf of "setup" and "materialize" commands)
        """

        assert category and version
        template_to_use_list = [cc[3] for cc in COMPONENT_CATEGORIES if cc[0] == category and cc[1] == version]
        assert len(template_to_use_list) == 1
        return template_to_use_list[0]


    def _get_git_directories(self):
        """ Returns a list of the absolute path to all Git repositories
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
                git_directories.append(os.path.join(self.workspace_git_loc, root))
                dirs[:] = []  # do not recurse into this directory
        assert len(git_directories) == len(set(git_directories))  # should be no duplicates

        return git_directories


    def action_gerrit_config(self, check_arguments=True):
        """ Processes command: gerrit-config
        """

        NOT_REQUIRED, DONE, FAILED = list(range(3))  # possible status for various configure actions
        assert NOT_REQUIRED < DONE 
        assert DONE < FAILED                   # we record the highest status, which must therefore be FAILED

        if check_arguments and self.arguments:
            raise PewmaException('ERROR: gerrit-config command does not take any arguments')

        self.logger.info('%sLooking for repositories that need switching to Gerrit, and/or configuring for EGit/JGit and git' % (self.log_prefix,))

        git_directories = self._get_git_directories()

        if not git_directories:
            self.logger.info('%sSkipped: %s' % (self.log_prefix, self.workspace_loc + '_git (does not contain any repositories)'))
            return

        prefix= "%%%is: " % max([len(os.path.basename(x)) for x in git_directories]) if self.options.repo_prefix else ""

        for git_dir in sorted(git_directories):
            if os.path.basename(git_dir) not in GERRIT_REPOSITORIES:
                self.logger.debug('%sSkipped: not in Gerrit: %s' % (self.log_prefix, git_dir))
                continue
            config_file_loc = os.path.join(git_dir, '.git', 'config')
            if not os.path.isfile(config_file_loc):
                self.logger.error('%sSkipped: %s should exist, but does not' % (self.log_prefix, config_file_loc))
                continue

            #####################################################
            # parse and potentially update the .git/config file #
            #####################################################
            config = GitConfigParser()
            config.readgit(config_file_loc)
            # we only need to process repositories that are Gerrit repos
            try:
                origin_url = config.get('remote "origin"', 'url')
            except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
                self.logger.warn('%sSkipped: no [remote "origin"]: %s' % (self.log_prefix, config_file_loc))
                continue

            # get the current branch (so we can set up the push branch correctly)
            # the HEAD file contains one line which looks like "ref: refs/heads/gda-8.44" (probably)
            HEAD_file_loc = os.path.join(git_dir, '.git', 'HEAD')
            if not os.path.isfile(HEAD_file_loc):
                self.logger.error('%sSkipped: %s should exist, but does not' % (self.log_prefix, HEAD_file_loc))
                continue
            current_branch = 'master'  # in case of problems parsing HEAD file
            with open(HEAD_file_loc, 'r') as HEAD_file:
                for line in HEAD_file:
                    current_branch = line.rsplit('/')[-1] or 'master'
                    break

            git_config_commands = []
            new_url = urlparse.urlunsplit((GERRIT_SCHEME, GERRIT_NETLOC) + urlparse.urlsplit(origin_url)[2:])
            if urlparse.urlunsplit((GERRIT_SCHEME_ANON, GERRIT_NETLOC_ANON, '', '', '')) in origin_url:
                config_changes = ()  # if already pointing at Gerrit, but with anonymous checkout, leave the origin unchanged
            else:
                config_changes = (
                    ('remote "origin"', 'url'                 , 'remote.origin.url'    , new_url                    , True),)

            config_changes += (
                # section         , option                    , name                   , required_value             , use_replace
                ('gerrit'         , 'createchangeid'          , 'gerrit.createchangeid', 'true'                     , True),
                ('remote "origin"', 'fetch'                   , 'remote.origin.fetch'  , 'refs/notes/*:refs/notes/*', False),
                ('remote "origin"', 'pushurl'                 , 'remote.origin.pushurl', new_url                    , False),
                ('remote "origin"', 'push'                    , 'remote.origin.push'   , 'HEAD:refs/for/master'     , False))

            for (section, option, name, required_value, use_replace) in config_changes:
                self.logger.debug('%sGetting: %s' % (self.log_prefix, (section, option, name, required_value, use_replace)))
                try:
                    option_value = config.get(section, option)
                    self.logger.debug('%sGot: %s' % (self.log_prefix, option_value))
                    # I think at one point there was an issue with repeated keys in .git/config (which ConfigParser does not handle). Debugging statements left in
                    option_value_plural = config.items(section)
                    self.logger.debug('%sMany: %s' % (self.log_prefix, option_value_plural))

                except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
                    option_value = None

                if option_value != required_value:
                    if use_replace:
                        git_config_commands.append('git config -f %s %s %s' % (config_file_loc, name, required_value))
                    else:
                        git_config_commands.append('git config -f %s --add %s %s' % (config_file_loc, name, required_value))
                else:
                    self.logger.log(5, '%sSkipped: already have %s=%s in: %s' % (self.log_prefix, name, required_value, git_dir))

            repo_status = {'switched_remote_to_gerrit': NOT_REQUIRED, 'configured_for_eclipse': NOT_REQUIRED, 'hook_added': NOT_REQUIRED}

            for command in git_config_commands:
                self.logger.debug('%sRunning: %s' % (self.log_prefix, command))
                action_type = 'switched_remote_to_gerrit' if 'remote.origin.url' in command else 'configured_for_eclipse'
                status = DONE  # for dry run, pretend the operation succeeded
                if not self.options.dry_run:
                    retcode = subprocess.call(shlex.split(str(command)), shell=False)
                    if retcode:
                        self.logger.error('%sFAILED: rc=%s' % (self.log_prefix, retcode))
                        status = FAILED
                repo_status[action_type] = max(repo_status[action_type], status)  # FAILED is the highest status, sicne we want to know if _any_ failed

            #############################################################################
            # get the commit hook, for people who use command line Git rather than EGit #
            #############################################################################

            hooks_commit_msg_loc = os.path.join(git_dir, '.git', 'hooks', 'commit-msg')
            if os.path.exists(hooks_commit_msg_loc):
                self.logger.debug('%scommit-msg hook already set up: %s' % (self.log_prefix, hooks_commit_msg_loc))
            else:
                commit_hook = self.gerrit_commit_hook()
                if not self.options.dry_run:
                    with open(hooks_commit_msg_loc, 'w') as commit_msg_file:
                        commit_msg_file.write(commit_hook)
                    os.chmod(hooks_commit_msg_loc, 0o775)  # rwxrwxr-x
                self.logger.debug('%scommit-msg hook copied to: %s' % (self.log_prefix, hooks_commit_msg_loc))
                repo_status['hook_added'] = DONE

            if all(status == NOT_REQUIRED for status in repo_status.values()):
                self.logger.info('%sSkipped: already switched to Gerrit; configured for EGit/JGit and git: %s' % (self.log_prefix, git_dir))
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


    def action_git(self):
        """ Processes command: git <command>
        """

        if len(self.arguments) < 1:
            raise PewmaException('ERROR: git command has too few arguments')

        git_directories = self._get_git_directories()

        if not git_directories:
            self.logger.info('%sSkipped: %s' % (self.log_prefix, self.workspace_loc + '_git (does not contain any repositories)'))
            return

        prefix= "%%%is: " % max([len(os.path.basename(x)) for x in git_directories]) if self.options.repo_prefix else ""

        max_retcode = 0
        for git_dir in sorted(git_directories):
            git_command = 'git ' + ' '.join(self.arguments)

            if git_command.strip() == 'git pull':
                has_remote = False
                config_path = os.path.join(git_dir, '.git', 'config')
                if os.path.isfile(config_path):
                    with open(config_path, 'r' ) as config:
                        for line in config:
                            if '[remote ' in line:
                                has_remote = True
                                break
                if not has_remote:
                    self.logger.info('%sSkipped: %s in %s (NO REMOTE DEFINED)' % (self.log_prefix, git_command, git_dir))
                    continue

            retcode = self.action_one_git_repo(git_command, git_dir, prefix)
            max_retcode = max(max_retcode, retcode)

        return max_retcode


    def action_one_git_repo(self, command, directory, prefix):
        self.logger.info('%sRunning: %s in %s' % (self.log_prefix, command, directory))

        if not self.options.dry_run:
            sys.stdout.flush()
            sys.stderr.flush()
            try:
                # set environment variables to pass to git command extensions 
                os.environ['PEWMA_PY_WORKSPACE_GIT_LOC'] = self.workspace_git_loc
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
                    if '\n' in out or '\r' in out:  # if out is multiline
                        print("...")                # start it on a new line
                    elif '\n' in err or '\r' in err:  # if err is multiline
                        print("...")                  # start it on a new line
                if len(err)!=0:
                    print(err, file=sys.stderr)
                if len(out)!=0:
                    print(out)
            else:
                print(err, file=sys.stderr)
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
        return self.run_buckminster_in_subprocess(('clean',))


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
            if not self.options.skip_proxy_setup:
                script_file.write('importproxysettings\n')  # will import proxy settings from Java system properties
            script_file.write('perform ' + properties_text)
            script_file.write('-Dtarget.os=* -Dtarget.ws=* -Dtarget.arch=* ')
            script_file.write('%(site_name)s#buckminster.clean\n' % {'site_name': self.site_name})

        if self.isWindows:
            script_file_path_to_pass = '"%s"' % (self.script_file_path,)
        else:
            script_file_path_to_pass = self.script_file_path
        return self.run_buckminster_in_subprocess(('--scriptfile', script_file_path_to_pass))


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
            if not self.options.skip_proxy_setup:
                script_file.write('importproxysettings\n')  # will import proxy settings from Java system properties
            if thorough:
                script_file.write('build --thorough\n')
            else:
                script_file.write('build\n')

        if self.isWindows:
            script_file_path_to_pass = '"%s"' % (self.script_file_path,)
        else:
            script_file_path_to_pass = self.script_file_path
        return self.run_buckminster_in_subprocess(('--scriptfile', script_file_path_to_pass))


    def action_target(self):
        """ Processes command: target [ path/to/name.target ]
        """

        if not self.arguments:
            return self.run_buckminster_in_subprocess(('listtargetdefinitions',))

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

        return self.run_buckminster_in_subprocess(('importtargetdefinition', '--active', path[len(self.workspace_loc)+1:]))  # +1 for os.sep


    def action_sites(self):
        sites = self.set_available_sites()
        self.logger.info('Available sites in %s%s: %s' % (self.workspace_loc, ('', '[_git]')[bool(self.workspace_git_loc)], sorted(self.available_sites) or '<none>'))


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
            if not self.options.skip_proxy_setup:
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
        return self.run_buckminster_in_subprocess(('--scriptfile', script_file_path_to_pass))


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
                    for (p, a) in PLATFORMS_AVAILABLE:
                        platforms.add(p)
                else:
                    for (p, a) in PLATFORMS_AVAILABLE:
                        if arg in a:
                            platforms.add(p)
                            break
                    else:
                        raise PewmaException('ERROR: "%s" was not recognised as either a site (in %s<_git>), or as a platform name' % (arg, self.workspace_loc))

        if not hasattr(self, 'site_name') or not self.site_name:
            self.set_site_name(None)
        if platforms:
            platforms = sorted(platforms)
        else:
            platforms = [{'Linuxi686': 'linux,gtk,x86', 'Linuxx86_64': 'linux,gtk,x86_64', 'Windowsx86': 'win32,win32,x86', 'Windowsx86_64': 'win32,win32,x86_64'}.get('%s%s' % (self.system, platform.machine()))]

        # determine what edition the cspex for the .site project is (newest to oldest):
        # (5) Removed the 'create.product-macosx.cocoa.x86' and 'create.product.zip-macosx.cocoa.x86' actions (retained x86_64)    [GDA 8.46+]
        # (4) Added a 'create.product-linux.gtk.x86_64-with.symlink' action                                                        [GDA 8.44+]
        # (3) a separate action for each platform (create.product-<os>.<ws>.<arch>), and a separate zip action for each platform   [GDA 8.30+]
        # (2) a separate action for each platform (create.product-<os>.<ws>.<arch>), but no separate zip action for each platform  [GDA 8.30+]
        # (1) a single action for all platforms (create.product)                                                                   [GDA 8.28-]

        cspex_file_path = os.path.abspath(os.path.join(self.available_sites[self.site_name], 'buckminster.cspex'))
        mac32_available = False                        # if False, version 5+
        linux64_with_symlink_action_available = False  # if True, version 4+
        zip_actions_available = False                  # if True, version 3+
        per_platform_actions_available = False         # if True, version 2+
        with open(cspex_file_path, 'r') as cspex_file:
            for line in cspex_file:
                if '"create.product-macosx.cocoa.x86"' in line:  # "s so that we don't mactch on create.product-macosx.cocoa.x86_64
                    mac32_available = True
                if 'create.product-linux.gtk.x86_64-with.symlink' in line:
                    linux64_with_symlink_action_available = True
                if 'create.product-linux.gtk.x86_64' in line:
                    per_platform_actions_available = True
                if 'create.product.zip-linux.gtk.x86_64' in line:
                    zip_actions_available = True
                if all((mac32_available, linux64_with_symlink_action_available, per_platform_actions_available, zip_actions_available)):
                    break

        if action_zip and not zip_actions_available:
            raise PewmaException('ERROR: product.zip is not available for "%s"' % (self.site_name,))
        if self.options.recreate_symlink and not linux64_with_symlink_action_available:
            raise PewmaException('ERROR: --recreate-symlink is not available for "%s"' % (self.site_name,))
        if ('macosx,cocoa,x86' in platforms) and not mac32_available:
            if all_platforms_specified:
                platforms.remove('macosx,cocoa,x86')  #  platform "all" was specified, so removed macos 32-bit platform  from the auto-added list  
            else:
                raise PewmaException('ERROR: MacOSX 32-bit cannot be build for "%s"' % (self.site_name,))

        self.logger.info('Product "%s" will be built for %d platform%s: %s' % (self.site_name, len(platforms), ('', 's')[bool(len(platforms)>1)], platforms))

        self.set_buckminster_properties_path(self.site_name)
        self.logger.info('Writing buckminster commands to "%s"' % (self.script_file_path,))
        properties_text = '-P%s ' % (self.buckminster_properties_path,)
        for keyval in self.options.system_property:
            properties_text += '-D%s ' % (keyval,)
        if self.options.buckminster_root_prefix:
            properties_text += '-Dbuckminster.root.prefix=%s ' % (os.path.abspath(self.options.buckminster_root_prefix),)
        with open(self.script_file_path, 'w') as script_file:
            if not self.options.skip_proxy_setup:
                script_file.write('importproxysettings\n')  # will import proxy settings from Java system properties
            if not self.options.assume_build:
                script_file.write('build --thorough\n')
            script_file.write('perform ' + properties_text)
            script_file.write('-Dtarget.os=* -Dtarget.ws=* -Dtarget.arch=* ')
            if per_platform_actions_available:
                for p in platforms:
                    perform_options = {'action': 'create.product.zip' if action_zip else 'create.product', 'withsymlink': '', 'site_name': self.site_name,
                                       'os': p.split(',')[0], 'ws': p.split(',')[1], 'arch': p.split(',')[2]}
                    if self.options.recreate_symlink and (p == 'linux,gtk,x86_64') and not action_zip:
                        perform_options['withsymlink'] = '-with.symlink'
                    script_file.write(' %(site_name)s#%(action)s-%(os)s.%(ws)s.%(arch)s%(withsymlink)s' % perform_options)
                script_file.write('\n')
            else:
                script_file.write('%(site_name)s#site.p2\n' % {'site_name': self.site_name})
                for p in platforms:
                    perform_options = {'site_name': self.site_name, 'os': p.split(',')[0], 'ws': p.split(',')[1], 'arch': p.split(',')[2]}
                    script_file.write('perform ' + properties_text)
                    script_file.write('-Dtarget.os=%(os)s -Dtarget.ws=%(ws)s -Dtarget.arch=%(arch)s %(site_name)s#create.product\n' % perform_options)

        if self.isWindows:
            script_file_path_to_pass = '"%s"' % (self.script_file_path,)
        else:
            script_file_path_to_pass = self.script_file_path
        return self.run_buckminster_in_subprocess(('--scriptfile', script_file_path_to_pass))


    def _iterate_ant(self, target):
        """ Processes using an ant target
        """

        selected_plugins = self.get_selected_plugins_with_releng_ant()  # might be an empty string to indicate all
        return self.run_ant_in_subprocess((selected_plugins, target))


###############################################################################
#  Run Buckminster                                                            #
###############################################################################

    def report_executable_location(self, executable_name):
        """ Determines the path to an executable (used when no version nubmer is available)
            Writes the path to the log
            Returns the path string
        """

        if executable_name in self.executable_locations:
            return self.executable_locations[executable_name]
        if not self.isLinux:
            return None  # "which" command only available on Linux
        loc = None
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


    def report_java_version(self):
        """ Determines the Java version number, something like 1.7.0_17
            Writes the version number to the log
            Returns the version number string
        """

        if self.java_version_current:
            return self.java_version_current
        try:
            javarun = subprocess.Popen(('java', '-version'), stderr=subprocess.PIPE)  #  java -version writes to stderr
            (stdout, stderr) = javarun.communicate(None)
            if not javarun.returncode:
                if stderr.startswith('java version "'):
                    self.java_version_current = stderr[len('java version "'):].partition('"')[0]
        except:
            pass
        if self.java_version_current:
            self.logger.info('%sJava version that will be used: %s' % (self.log_prefix, self.java_version_current))
        else:
            self.logger.warn('%sJava version to use could not be determined' % (self.log_prefix,))
        return self.java_version_current


    def run_buckminster_in_subprocess(self, buckminster_args, return_Buckminster_errors=False):
        """ Generates and runs the buckminster command
            If return_Buckminster_errors, then returns a list of repositories that had errors when attempting to clone (for materialize)
        """

        self.report_executable_location('buckminster')
        self.report_java_version()

        buckminster_command = ['buckminster']

        if self.options.keyring:
            buckminster_command.extend(('-keyring', '"%s"' % (self.options.keyring,)))  # quote in case of embedded blanks or special characters
        buckminster_command.extend(('-application', 'org.eclipse.buckminster.cmdline.headless'))
        buckminster_command.extend(('--loglevel', self.options.log_level.upper()))
        buckminster_command.extend(('-data', self.workspace_loc))  # do not quote the workspace name (it should not contain blanks)
        buckminster_command.extend(buckminster_args)

        vmargs_to_add = []
        # For Buckminster 4.5, need to specify UseSplitVerifier: see https://bugs.eclipse.org/bugs/show_bug.cgi?id=471115
        # Always specify UseSplitVerifier unless we are sure that this in not Buckminster 4.5
        if not any(old_version in (self.executable_locations['buckminster'] or ()) for old_version in ('/dls_sw/apps/buckminster/64/4.4-', '/dls_sw/apps/buckminster/64/4.3-')):
            if self.java_version_current and self.java_version_current.startswith('1.7'):
                vmargs_to_add.append('-XX:-UseSplitVerifier')  # UseSplitVerifier exists in Java 7, but was removed in Java 8
            else:
                vmargs_to_add.append('-noverify')
        # if debugging memory allocation, add this parameter: '-XX:+PrintFlagsFinal'
        if not self.isWindows:  # these extra options need to be removed on my Windows XP 32-bit / Java 1.7.0_25 machine
            vmargs_to_add.extend(('-Xms768m', '-Xmx1536m', '-XX:+UseG1GC', '-XX:MaxGCPauseMillis=1000'))
        if self.java_proxy_system_properties:
            vmargs_to_add.extend(self.java_proxy_system_properties)
        for keyval in self.options.jvmargs:
            vmargs_to_add.extend(('-D%s ' % (keyval,),))
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
            with open(script_file_path_to_pass) as script_file:
                for line in script_file.readlines():
                    self.logger.debug('%s(script file): %s' % (self.log_prefix, line))

        jgit_errors_repos = []
        jgit_errors_general = []
        buckminster_bugs = []
        if not self.options.dry_run:
            sys.stdout.flush()
            sys.stderr.flush()
            try:
                process = subprocess.Popen(buckminster_command, bufsize=1, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
                for line in iter(process.stdout.readline, b''):
                    if return_Buckminster_errors:
                        for (error_pattern, error_summary) in JGIT_ERROR_PATTERNS:
                            jgit_error = re.search(error_pattern, line)
                            if jgit_error:
                                if isinstance(error_summary, int):
                                    jgit_errors_repos.append(os.path.basename(jgit_error.group(error_summary)))
                                else:
                                    jgit_errors_general.append(error_summary)
                        for (error_pattern, error_summary) in BUCKMINSTER_BUG_ERROR_PATTERNS:
                            buckminster_bug = re.search(error_pattern, line)
                            if buckminster_bug:
                                buckminster_bugs.append(error_summary)
                    if not (self.options.suppress_compile_warnings and line.startswith('Warning: file ')):
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

        if return_Buckminster_errors:
            return (retcode, jgit_errors_repos, jgit_errors_general, buckminster_bugs)
        else:
            return retcode


    def run_ant_in_subprocess(self, ant_args):
        """ Generates and runs the ant command
        """

        self.report_executable_location('ant')
        self.report_java_version()

        ant_command = ['ant']
        ant_command.extend(("-logger", "org.apache.tools.ant.NoBannerLogger"))
        ant_command.extend(('-buildfile', os.path.join(self.workspace_git_loc, 'diamond-releng.git/diamond.releng.tools/ant-headless/ant-driver.ant')))

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
            return retcode


    def gerrit_commit_hook(self):
        """ Returns a string containing the Gerrit commit hook (which adds a ChangeId to a commit)
        """

        # we cache the commit_hook and never refetch it from the Gerrit server
        if hasattr(self, '_gerrit_commit_hook'):
            return self._gerrit_commit_hook

        commit_hook_url = urlparse.urlunparse((GERRIT_SCHEME_ANON, GERRIT_NETLOC_ANON, '/tools/hooks/commit-msg', '', '', ''))
        # open the URL
        try:
            resp = urllib2.urlopen(commit_hook_url, timeout=30)
        except (urllib2.URLError, urllib2.HTTPError, socket.timeout) as e:
            self.logger.error('Error downloading from "%s": %s' % (commit_hook_url, str(e)))
            if self.options.prepare_jenkins_build_description_on_materialize_error:
                text = 'set-build-description: Failure downloading Gerrit commit hook (probable network issue)'
                print(text)
            raise PewmaException('Gerrit commit hook download failed (network error, proxy failure, or proxy not set): please retry')

        # read the data (small enough to do in one chunk)
        self.logger.debug('Downloading %s bytes from "%s"' % (resp.info().get('content-length', '<unknown>'), resp.geturl()))
        try:
            commit_hook = resp.read()
        except Exception as e:
            self.logger.error('Error downloading from "%s": %s' % (commit_hook_url, str(e)))
            if self.options.prepare_jenkins_build_description_on_materialize_error:
                text = 'set-build-description: Failure downloading Gerrit commit hook (probable network issue)'
                print(text)
            raise PewmaException('Gerrit commit hook download failed (network error, proxy failure, or proxy not set): please retry')
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

    def main(self, call_args):
        """ Process any command line arguments and run program.
            call_args[0] == the directory the script is running from.
            call_args[1:] == build options and parameters. """

        if (sys.version < "2.6") or (sys.version >= "3"):
            raise PewmaException("ERROR: This script must be run using Python 2.6 or higher.")
        try:
            if not len(call_args):
                raise TypeError
        except TypeError:
            raise PewmaException("ERROR: PewmaManager.main() called with incorrect argument.")

        start_time = datetime.datetime.now()

        # process command line arguments (prompt if necessary):
        self.define_parser()
        (self.options, positional_arguments) = self.parser.parse_args(call_args[1:])

        # print help if requested, or if no arguments
        if self.options.help or not positional_arguments:
            self.parser.print_help()
            print('\nActions and Arguments:')
            for (_, _, help) in self.valid_actions_with_help:
                if help:
                     print('    %s' % (help[0]))
                     for line in help[1:]:
                        print('      %s' % (line,))
            return

        self.action = positional_arguments[0]
        self.arguments = positional_arguments[1:]

        # set the logging level and text for this program's logging
        self.log_prefix = ("", "(DRY_RUN) ")[self.options.dry_run]
        self.logging_console_handler.setLevel( logging._levelNames[self.options.log_level.upper()] )

        # validation of options and action
        self.validate_plugin_patterns()
        if self.options.delete and self.options.recreate:
            raise PewmaException('ERROR: you can specify at most one of --delete and --recreate')
        if (self.action not in list(self.valid_actions.keys())):
            raise PewmaException('ERROR: action "%s" unrecognised (try --help)' % (self.action,))
        if self.options.keyring:
            self.options.keyring = os.path.realpath(os.path.abspath(os.path.expanduser(self.options.keyring)))
            if ((os.path.sep + '.ssh' + os.path.sep) in self.options.keyring) or self.options.keyring.endswith(('id_rsa', 'id_rsa.pub')):
                raise PewmaException('ERROR: --keyring "%s" appears to be an ssh key. This is **WRONG**, it should be an Eclipse keyring.' % (self.options.keyring,))
            if not os.path.isfile(self.options.keyring):
                # sometimes, for reasons unknown, we temporarily can't see the file
                self.logger.warn('--keyring "%s" is not a valid filename, will look again in 2 seconds' % (self.options.keyring,))
                time.sleep(2)
                if not os.path.isfile(self.options.keyring):
                    raise PewmaException('ERROR: --keyring "%s" is not a valid filename' % (self.options.keyring,))
            if not os.access(self.options.keyring, os.R_OK):
                # sometimes, for reasons unknown, we temporarily can't read the file
                self.logger.warn('current user does not have read access to --keyring "%s", will look again in 2 seconds' % (self.options.keyring,))
                time.sleep(2)
                if not os.access(self.options.keyring, os.R_OK):
                    raise PewmaException('ERROR: current user does not have read access to --keyring "%s"' % (self.options.keyring,))
        if self.options.delete and self.action not in ('setup', 'materialize'):
            raise PewmaException('ERROR: the --delete option cannot be specified with action "%s"' % (self.action))
        if self.options.recreate and self.action not in ('setup', 'materialize'):
            raise PewmaException('ERROR: the --recreate option cannot be specified with action "%s"' % (self.action))
        if self.options.system_property:
            if any((keyval.find('=') == -1) for keyval in self.options.system_property):
                raise PewmaException('ERROR: the -D option must specify a property and value as "key=value"')
        else:
            self.options.system_property = []  # use [] rather than None so we can iterate over it
        if not self.options.jvmargs:
            self.options.jvmargs = []  # use [] rather than None so we can iterate over it

        # validate workspace
        if self.options.workspace:
            if ' ' in self.options.workspace:
                raise PewmaException('ERROR: the "--workspace" directory must not contain blanks')
            if self.options.workspace.endswith('_git'):
                raise PewmaException('ERROR: the "--workspace" directory must not end with "_git"')
            self.workspace_loc = os.path.realpath(os.path.abspath(os.path.expanduser(self.options.workspace)))
            # if the workspace location was specified, check that it's not inside an existing workspace
            candidate = os.path.dirname(self.workspace_loc)
            while candidate != os.path.dirname(candidate):  # if we are not at the filesystem root (this is a platform independent check)
                if not candidate.endswith('_git'):
                    parent_workspace = (os.path.isdir( os.path.join( candidate, '.metadata')) and candidate)
                else:
                    parent_workspace = (os.path.isdir( os.path.join( candidate[:-4], '.metadata')) and candidate[:-4])
                if parent_workspace:
                    raise PewmaException('ERROR: the workspace you specified ("' + self.workspace_loc + '") is inside what looks like another workspace ("' + parent_workspace + '")')
                candidate = os.path.dirname(candidate)
        elif not self.workspace_loc:
            raise PewmaException('ERROR: the "--workspace" option must be specified, unless you run this script from an existing workspace')
        self.workspace_git_loc = self.workspace_loc + '_git'

        # delete previous workspace as required
        if self.options.delete or self.options.recreate:
            self.delete_directory(self.workspace_loc, "workspace directory")
            if self.options.delete:
                self.delete_directory(self.workspace_git_loc, "workspace_git directory")

        # Proxy handling is a bit of a mess. Python and Buckminster (java) can potentially access network resources, and they handle proxy settings differently.
        # The technique used here seems to work (meaning it uses the procy when it is supposed to, and not when it isn't).
        # Don't mess around with it; thungs that look like they should work, don't.
        # The only way to know if this is doing the right thing is to test with a network tracong tool such as wireshark. 
        if self.options.skip_proxy_setup:
            for env_name in ('http_proxy', 'https_proxy', 'no_proxy'):
                log_text = 'Using existing %s/%s = ' % (env_name, env_name.upper())
                for variant in (env_name, env_name.upper()):
                    if variant not in os.environ:
                        log_text += '(unset)'
                    else:
                        log_text += os.environ[variant]
                    log_text += '/'
                self.logger.debug(log_text[:-1])  # drop trailing /
            self.logger.debug('Note: Experiments suggest that no_proxy is ignored by Buckminster')
            self.java_proxy_system_properties = ()
        else:
            fqdn = socket.getfqdn()
            if fqdn.endswith('.diamond.ac.uk'):
                proxy_value = 'wwwcache.rl.ac.uk:8080'
                no_proxy_value = 'dasc-git.diamond.ac.uk,dawn.diamond.ac.uk,gerrit.diamond.ac.uk,jenkins.diamond.ac.uk,svn.diamond.ac.uk,172.16.0.0/12,localhost,127.*,[::1]'
                self.java_proxy_system_properties = (
                    '-Dhttp.proxyHost=wwwcache.rl.ac.uk', '-Dhttp.proxyPort=8080',  # http://docs.oracle.com/javase/8/docs/api/java/net/doc-files/net-properties.html
                    '-Dhttps.proxyHost=wwwcache.rl.ac.uk', '-Dhttps.proxyPort=8080',
                    # please see Jira DASCTEST-317 for a discussion of proxy bypass specification
                    '-Dhttp.nonProxyHosts="dasc-git.diamond.ac.uk\|dawn.diamond.ac.uk\|gerrit.diamond.ac.uk\|jenkins.diamond.ac.uk\|svn.diamond.ac.uk\|172.16.0.0/12\|localhost\|127.*\|[::1]"',  # applies to https as well
                    )
            elif fqdn.endswith('.esrf.fr'):
                proxy_value = 'proxy.esrf.fr:3128'
                no_proxy_value = '127.0.0.1,localhost'
                self.java_proxy_system_properties = (
                    '-Dhttp.proxyHost=proxy.esrf.fr', '-Dhttp.proxyPort=3128',  # http://docs.oracle.com/javase/8/docs/api/java/net/doc-files/net-properties.html
                    '-Dhttps.proxyHost=proxy.esrf.fr', '-Dhttps.proxyPort=3128',
                    '-Dhttp.nonProxyHosts="localhost\|127.*\|[::1]"',  # applies to https as well
                    )
            else:
                proxy_value = ''
                no_proxy_value = ''
                self.java_proxy_system_properties = ()
            for env_name, env_value in (('http_proxy', 'http://'+proxy_value if proxy_value else ''),
                                        ('https_proxy', 'https://'+proxy_value if proxy_value else ''),
                                        ('no_proxy', no_proxy_value)):
                if env_name not in os.environ:
                    old_value = None  # indicates unset
                else:
                    old_value = os.environ[env_name].strip()
                if env_value:
                    if old_value:
                        self.logger.debug('Setting %s=%s (previously: %s)' % (env_name, env_value, old_value))
                    elif old_value is None:
                        self.logger.debug('Setting %s=%s (previously unset)' % (env_name, env_value,))
                    else:
                        self.logger.debug('Setting %s=%s (previously null)' % (env_name, env_value,))
                    os.environ[env_name] = env_value
                    env_name_upper = env_name.upper()
                    if env_name_upper in os.environ:
                        old_value = os.environ[env_name_upper].strip()
                        if old_value and (old_value != env_value):
                            self.logger.debug('Unsetting %s (previously: %s)' % (env_name_upper, old_value,))
                            del os.environ[env_name_upper]
                else:
                    if old_value:
                        self.logger.debug('No new value found for %s (left as: %s)' % (env_name, old_value))
                    elif old_value is None:
                        self.logger.debug('No new value found for %s (left unset)' % (env_name,))
                    else:
                        self.logger.debug('No new value found for %s (left null)' % (env_name,))

        # get some file locations (even though they might not be needed) 
        self.script_file_path = os.path.expanduser(self.options.script_file)
        if not os.path.isabs(self.script_file_path):
           self.script_file_path = os.path.abspath(os.path.join(self.workspace_loc, self.script_file_path))
        self.materialize_properties_path = os.path.expanduser(self.options.materialize_properties_file)
        if not os.path.isabs(self.materialize_properties_path):
           self.materialize_properties_path = os.path.abspath(os.path.join(self.workspace_loc, self.materialize_properties_path))

        # invoke funtion to perform the requested action
        action_handler = self.valid_actions[self.action]
        if action_handler:
            exit_code = action_handler(target=self.action)
        else:
            exit_code = getattr(self, 'action_'+self.action.replace('.', '_').replace('-', '_'))()

        end_time = datetime.datetime.now()
        run_time = end_time - start_time
        seconds = (run_time.days * 86400) + run_time.seconds
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        self.logger.info('%sTotal run time was %02d:%02d:%02d' % (self.log_prefix, hours, minutes, seconds))
        return exit_code

###############################################################################
# Command line processing                                                     #
###############################################################################

if __name__ == '__main__':
    pewma = PewmaManager()
    try:
        sys.exit(pewma.main(sys.argv))
    except PewmaException as e:
        print(e)
        sys.exit(3)
    except KeyboardInterrupt:
        if len(sys.argv) > 1:
            print("\nOperation (%s) interrupted and will be abandoned." % ' '.join(sys.argv[1:]))
        else:
            print("\nOperation interrupted and will be abandoned")
        sys.exit(3)

