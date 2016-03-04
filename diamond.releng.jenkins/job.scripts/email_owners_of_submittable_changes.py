#!/usr/bin/env python3
###
### Requires Python 3
###

'''
Identify Gerrit changes that are ready to submit, and email the owners
'''

from email.message import EmailMessage
from email.headerregistry import Address
import datetime
import itertools
import json
import logging
import operator
import os
import os.path
import stat
import sys
import time
import urllib.request
import urllib.parse
import urllib.error

GERRIT_HOST = 'gerrit.diamond.ac.uk'
GERRIT_HTTP_PORT = ':8080'

# define module-wide logging
logger = logging.getLogger('email_owners_of_submittable_changes.py')  # global logger for this module
def setup_logging():
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S")
    # create console handler
    logging_console_handler = logging.StreamHandler()
    logging_console_handler.setFormatter(formatter)
    logger.addHandler(logging_console_handler)
    logger.setLevel(logging.INFO)
    # logger.setLevel(logging.DEBUG)


class SubmittableChangesProcessor():

    def __init__(self):
        setup_logging()
        self.logger = logger

        self.gerrit_url_base = 'http://' + GERRIT_HOST + GERRIT_HTTP_PORT + '/'  # when using the REST API, this is the base URL to use
        self.gerrit_url_browser = self.gerrit_url_base  # when generating links, this is the base URL to use
        self.use_digest_authentication = os.environ.get('GERRIT_USE_DIGEST_AUTHENTICATION', 'true').strip().lower() != 'false'

        if self.use_digest_authentication:
            self.logger.debug('Digest Authentication will be used to access the Gerrit REST API')
            # If the Gerrit REST API has been secured, then we need to use digest authentication.
            self.gerrit_url_base += 'a/'
            handler = urllib.request.HTTPDigestAuthHandler()
            handler.add_password('Gerrit Code Review', self.gerrit_url_base, *self.get_gerrit_http_username_password())
            opener = urllib.request.build_opener(handler)
            urllib.request.install_opener(opener)
        else:
            self.logger.debug('No authentication will be used to access the Gerrit REST API')

    @staticmethod
    def get_gerrit_http_username_password():
        ''' the token required to authenticate to Gerrit is stored in a file
            the file, in addition to comment and empty lines, contains a single line of the format
               username:password
        '''

        token_filename = os.path.abspath(os.path.expanduser('~/passwords/http-password_Gerrit_for-REST.txt'))
        assert os.path.isfile(token_filename)
        assert os.stat(token_filename).st_mode == stat.S_IRUSR + stat.S_IFREG  # permissions must be user-read + regular-file
        last_nonempty_line = ''
        with open(token_filename, 'r') as token_file:
            for line in token_file:  # standard OS terminator is converted to \n
                line = line.rstrip('\n')  # remove trailing newline
                if line:
                    last_nonempty_line = line
        if last_nonempty_line:
            return last_nonempty_line.split(':', 1)
        raise Exception('File %s appears empty' % token_filename)

    def gerrit_REST_api(self, relative_url, accept404=False):
        ''' Call the Jenkins REST API
        '''

        url = self.gerrit_url_base + relative_url
        request = urllib.request.Request(url, headers={'Accept': 'application/json', 'Accept-Charset': 'utf-8'})  # header specifies compact json, which is more efficient
        self.logger.debug('gerrit_REST_api retrieving: %s' % (url,))
        try:
            rest_json = urllib.request.urlopen(request).read()
        except (urllib.error.HTTPError) as err:
            if accept404 and (err.code == 404):
                self.logger.debug('Invalid response from Gerrit server reading %s: %s' % (url, err))
                return None
            self.logger.critical('Invalid response from Gerrit server reading %s: %s' % (url, err))
            return None
        gerrit_magic_prefix_line = b")]}'\n"
        if not rest_json[:len(gerrit_magic_prefix_line)] == gerrit_magic_prefix_line:
            self.logger.critical('Invalid response from Gerrit server reading %s: magic prefix line not found' % (url,))
            return None
        standard_json = json.loads(rest_json[len(gerrit_magic_prefix_line):].decode('utf-8'))  # strip off the magic prefix line returned by Gerrit
        # self.logger.debug(json.dumps(standard_json, indent=2))
        return standard_json

    def get_submittable_changes_from_gerrit(self):
        ''' Queries Gerrit to get a list of ChangeInfo records for the changes that can be submitted
        '''

        url = 'changes/?q=%s&o=CURRENT_REVISION&o=DETAILED_ACCOUNTS' % (urllib.parse.quote('is:open label:Code-Review+2 label:Verified+1 NOT label:Code-Review-2 NOT label:Verified-1'),)
        changeinfos = self.gerrit_REST_api(url)

        longest_string = {}
        longest_string['_number'] = max(itertools.chain((len(str(ci['_number'])) for ci in changeinfos), (len('Change'),)))
        longest_string['project'] = max(itertools.chain((len(ci['project']) for ci in changeinfos), (len('Project'),)))
        longest_string['branch']  = max(itertools.chain((len(ci['branch']) for ci in changeinfos), (len('Branch'),)))
        longest_string['owner']   = max(itertools.chain((len(ci['owner']['name']) for ci in changeinfos), (len('Owner'),)))

        format = ('%' + str(longest_string['_number']) + 's ' +
                  '%-' + str(longest_string['project']) + 's ' +
                  '%-' + str(longest_string['branch']) + 's ' +
                  '%-' + str(longest_string['owner']) + 's ' +
                  '%-16s ' +  # for the time last updated
                  '%s\n')  # for the subject

        emails = set()
        report = format % ('Change', 'Project', 'Branch', 'Owner', 'Updated', 'Subject')
        # use a sort key that transforms Firstname.Lastname@example.com to lastname.firstname
        for ci in sorted(changeinfos, key=lambda ci:
                         '.'.join(operator.itemgetter(2,0)(ci['owner']['email'].partition('@')[0].lower().partition('.'))) + 
                         os.path.basename(ci['project'])):  # there can be multiple changeinfos
            report += format % (ci['_number'], ci['project'], ci['branch'], ci['owner']['name'], ci['updated'][:16], ci['subject'])
            emails.add(ci['owner']['email'])

        self.emails = sorted(emails)
        self.report = report
        return

    def make_email(self):

        body = 'Below is a list of changes in Gerrit that have been verified and reviewed, but are still waiting for the change owner to submit them' + \
               ', as of ' + time.strftime("%a, %Y/%m/%d %H:%M:%S %Z") + '.\n'
        body += '''
PLEASE CONSIDER EITHER:
    Submit your change, it you still want it
    Abandon your change, if it is no longer required

'''
        body += self.report
        body += '\n<<end report>>\n'

        # we are going to create an email message with ASCII characters, so convert any non-ASCII ones
        # note that this is really a hack, we should be smarter about constructing an email message
        body = body.replace("’", "'").replace('“', '"').replace('”', '"')

        message = EmailMessage()
        message['Subject'] = 'Report on Gerrit changes waiting for the owner to submit'
        message['From'] = Address('Jenkins Build Server (Diamond Light Source)', 'gerrit-no-reply@diamond.ac.uk')
        message['List-Id'] = 'Gerrit awaiting submit <gerrit-awaiting-submit.jenkins.diamond.ac.uk>'
        # use a sort key that transforms Firstname.Lastname@example.com to lastname.firstname
        message['To'] = [Address(addr_spec=committer) for committer in sorted(
                            self.emails,
                            key=lambda email_addr: '.'.join(operator.itemgetter(2,0)(email_addr.partition('@')[0].lower().partition('.')))
                        ) if '@' in committer]
        message.set_content(body)

        email_expires_days = 5
        if email_expires_days:
            message['Expiry-Date'] = (datetime.datetime.utcnow() + datetime.timedelta(days=email_expires_days)).strftime("%a, %d %b %Y %H:%M:%S +0000")
        return message

if __name__ == '__main__':

    scp = SubmittableChangesProcessor()
    scp.get_submittable_changes_from_gerrit()
    print(scp.make_email())
    sys.exit(0)

