#!/usr/bin/python2
# -*- coding: utf-8 -*-
#
# Script to help dealing with bugzilla spam ...
# ... based on the Wine Staging patchupdate script.
#
# Copyright (C) 2014-2016 Sebastian Lackner
# Copyright (C) 2015 Michael Müller
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301, USA
#

import argparse
import ConfigParser
import os
import xmlrpclib

class config(object):
    path_config             = os.path.expanduser("~/.config/patchupdate.conf")

    bugtracker_url          = "https://bugs.winehq.org/xmlrpc.cgi"
    bugtracker_user         = None
    bugtracker_pass         = None

def mark_as_spam(bug_ids, force=False):
    bugtracker  = xmlrpclib.ServerProxy(config.bugtracker_url)
    bug_list = bugtracker.Bug.get(dict(ids=bug_ids))
    bug_list = bug_list['bugs']

    # In case someone else has already closed the bug, skip it.
    bug_list = [bug for bug in bug_list if bug['summary'] != 'spam' or
                                           bug['status'] not in ["RESOLVED", "CLOSED"] or
                                           bug['resolution'] != "INVALID"]

    if len(bug_list) == 0:
        print "Nothing to do!"
        return

    print ""
    print "If you proceed, the following bugs will be marked as spam:"
    print ""
    account_list = set()
    for bug in bug_list:
        print " #%d - \"%s\" - %s %s" % (bug['id'], bug['summary'], bug['status'], bug['resolution'])
        account_list.add(bug['creator'])
    print ""
    print "Also, the following user accounts will be disabled:"
    print ""
    for name in account_list:
        print " %s" % (name,)
    print ""

    if not force:
        while True:
            reply = raw_input("Do you want to proceed? [Y/N]: ").lower().strip()
            if len(reply) < 1: continue
            if reply[0] == "y": break
            if reply[0] == "n": raise KeyboardInterrupt
        print ""

    for name in account_list:
        print "Disabling account %s ..." % (name,)

        # Block the creator from doing more damage
        changes = { 'names'             : [bug['creator']],
                    'Bugzilla_login'    : config.bugtracker_user,
                    'Bugzilla_password' : config.bugtracker_pass,

                    'email_enabled'     : False,
                    'login_denied_text' : "This account has been suspended because of spam." }

        bugtracker.User.update(changes)

    for bug in bug_list:
        print "Resolving bug #%d - \"%s\" ..." % (bug['id'], bug['summary'])

        # Delete attachments
        attachments = bugtracker.Bug.attachments(dict(ids=[bug['id']]))
        attachments = attachments['bugs'][str(bug['id'])]
        if len(attachments):
            print "FIXME: Deleting attachments not implemented yet!"

        # Get list of comments which have to be marked as private
        comments = bugtracker.Bug.comments(dict(ids=[bug['id']]))
        comments = comments['bugs'][str(bug['id'])]["comments"]
        comment_is_private = dict([(str(comment["id"]), True) for comment in comments])

        # Now do the changes
        changes = { 'ids'               : bug['id'],
                    'Bugzilla_login'    : config.bugtracker_user,
                    'Bugzilla_password' : config.bugtracker_pass,

                    # Change the summary and hide the comments
                    'summary'           : "spam",
                    'comment_is_private': comment_is_private,

                    # Keep all the spam bugs in the Wine product
                    'product'           : "Wine",
                    'component'         : "-unknown",
                    'version'           : "unspecified",

                    # In case there are already people in CC remove them
                    'cc'                : { 'remove': bug['cc'] },

                    # Make sure it has severity normal
                    'severity'          : "normal",

                    # Close the bug report as invalid.
                    'comment'           : { 'body': "This bug has been resolved as INVALID because of spam.",
                                            'private': False },
                    'status'            : 'RESOLVED',
                    'resolution'        : 'INVALID' }

        bugtracker.Bug.update(changes)

    print ""

if __name__ == '__main__':

    config_parser = ConfigParser.ConfigParser()
    config_parser.read(config.path_config)

    try:
        config.bugtracker_user = config_parser.get('bugtracker', 'username')
        config.bugtracker_pass = config_parser.get('bugtracker', 'password')
    except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
        print ""
        print "ERROR: Please set up %s with your username/password." % (config.path_config,)
        print ""
        print "The file should look like this:"
        print "    [bugtracker]"
        print "    username=email@address.org"
        print "    password=yourpassword"
        print ""
        exit(1)

    parser = argparse.ArgumentParser(description='Delete bugzilla spam!')
    parser.add_argument('--force', action='store_true',
                        help='Do not ask for confirmation')
    parser.add_argument('bugids', metavar='ID', type=int, nargs='+',
                        help='Bugzilla IDs')

    args = parser.parse_args()
    mark_as_spam(args.bugids, args.force)
