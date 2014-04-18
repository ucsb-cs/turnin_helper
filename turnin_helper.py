#!/usr/bin/env python
from __future__ import print_function
import csv
import os
import pwd
import re
import smtplib
import sys
from optparse import OptionParser, OptionGroup

__version__ = '0.2'
DISPLAY_WARNINGS = True
FORCE = False
YES = ['yes', 'y', '1']
QUIT = ['quit', 'q']


"""Grading Script for automatically unpacking the newest turnins
   Written By: Bryce Boe (bboe at cs)
   Date: 2009/01/27

   Last Update: 2014/04/18
"""


def calci_test(args):
    """Custom test function for CS160 Proj0 Grading

    When turnin_helper is invoked with the argument --test-function=calci_test
    this function is called once for each submission. Prior to the call to this
    function python changes directories to the base of the extracted files
    for the submission.
    """

    """
    os.system('diff -u ../../calci.cpp calci/calci.cpp > calci.diff')
    return
    """

    proj = os.path.basename(os.getcwd())
    if args and proj not in args:
        return

    print('Testing: {}'.format(proj))

    tests_dir = '../../TESTS/'
    os.system('rm -f line_numbers')

    for test in sorted(os.listdir(tests_dir)):
        test_input = os.path.join(tests_dir, test)
        if not os.path.isfile(test_input):
            continue
        stdout = 'stdout-{}'.format(test)
        stderr = 'stderr-{}'.format(test)
        ret = os.system('calci/calci < {} > {} 2> {}'
                        .format(test_input, stdout, stderr))
        if ret and 'bad' not in test:
            print('\tFailed {}'.format(test))
            last = open(stdout).readlines()[-1]
            sys.stdout.write('\t\t {}'.format(last))
        elif not ret and 'bad' in test:
            print('\tFailed {}'.format(test))
        elif 'valid' in test:
            ret = os.system('dot -Tps {} > {}.ps'.format(stdout, test))
            if ret:
                print(ret)
        elif 'bad' in test:
            os.system('echo {} >> line_numbers'.format(stdout))
            os.system('tail -n 1 {} >> line_numbers'.format(stdout))
            os.remove(stdout)
        if os.path.getsize(stderr) == 0:
            os.remove(stderr)


def exit_error(msg):
    print(msg)
    sys.exit(1)


def warning(msg):
    if DISPLAY_WARNINGS:
        sys.stderr.write('Warning: {}\n'.format(msg))


def verify(msg):
    test_input = raw_input('{} '.format(msg)).lower()
    if input in QUIT:
        exit_error('Aborted')
    return test_input in YES


def get_latest_turnin_list(proj_dir, extension):
    """Builds a list of all the most recent submissions."""

    # Intentionally doesn't handle names with hyphens (-) followed by numbers
    submit_re = re.compile('([A-Za-z0-9_.]+([A-Za-z_.-]*))(-(\d)+)?.{}'
                           .format(extension))
    submissions = [x for x in os.listdir(proj_dir) if extension in x]
    if not submissions:
        exit_error('No files in {} with extension {}'
                   .format(proj_dir, extension))

    # Build unique user submission list, with most recent count
    unique_users = {}
    for submission in submissions:
        try:
            user, _, _, submit_count = submit_re.match(submission).groups()
        except AttributeError:
            sys.stderr.write('Warning: Failed to handle: {}\n'
                             .format(submission))

        submit_count = int(submit_count) if submit_count else 0
        if user in unique_users:
            unique_users[user] = max(unique_users[user], submit_count)
        else:
            unique_users[user] = submit_count

    latest_submissions = []
    for user, submit_count in unique_users.items():
        extra = '-{}'.format(submit_count) if submit_count > 0 else ''
        latest_submissions.append('{}{}'.format(user, extra))
    return sorted(latest_submissions)


def extract_submissions(proj_dir, work_dir, extension, submit_list):
    """Unpacks all files passed in as a list here"""
    if not os.path.isdir(work_dir):
        if not FORCE:
            if not verify('Are you sure you want to create {}?'
                          .format(work_dir)):
                exit_error('Aborted')
        os.mkdir(work_dir)

    for submit in submit_list:
        print('Unpacking: {}'.format(submit))
        extract_dir = os.path.join(work_dir, submit)
        compressed = os.path.join(proj_dir, '{}.{}'
                                  .format(submit, extension))
        if os.path.isdir(extract_dir):
            if not FORCE:
                if not verify('Are you sure you want to overwrite {}?'
                              .format(extract_dir)):
                    continue
        else:
            os.mkdir(extract_dir)
        extract_log = os.path.join(extract_dir, 'extract_log')
        os.system('tar -xvzf {} -C {} > {}'.format(compressed, extract_dir,
                                                   extract_log))


def make(work_dir, make_dir, makefile, target, submit_list):
    if not os.path.isdir(work_dir):
        exit_error('work_dir does not exist. Extract first')

    """Runs make for each submission"""
    makefile = '-f {}'.format(makefile) if makefile else ''
    target = target if target else ''
    make_cmd = 'make {} -C {{}} {} > {{}}'.format(makefile, target)

    for submit in submit_list:
        print('Making: {}'.format(submit))
        submit_dir = os.path.join(work_dir, submit, make_dir)
        make_log = os.path.join(work_dir, submit, 'make_log')

        if not os.path.isdir(submit_dir):
            print('Cannot build: submit_dir does not exist')
        else:
            os.system(make_cmd.format(submit_dir, make_log))


def email_grades(proj_dir, work_dir, from_email, bcc, submit_list):
    def append_at_cs(email):
        if '@' not in email:
            return email + '@cs.ucsb.edu'
        return email

    # Fix up
    from_email = append_at_cs(from_email)
    if not bcc:
        bcc = []
    for i in range(len(bcc)):
        bcc[i] = append_at_cs(bcc[i])

    # Make connection
    smtp = smtplib.SMTP()
    smtp.connect('localhost')

    # Get Generic Message
    generic_grade = ''
    generic = os.path.join(work_dir, 'GRADE')
    if not os.path.isfile(generic):
        if not FORCE:
            if not verify(' '.join(['There is no generic GRADE file, are you',
                                    'sure you want to send emails?'])):
                return
    else:
        generic_grade = open(generic).read().strip()

    user_re = re.compile('(\w+)(-(\d)+)?')
    for submit in submit_list:
        user_grade = os.path.join(work_dir, submit, 'GRADE')
        if not os.path.isfile(user_grade):
            print('No GRADE file for {}'.format(submit))
            continue
        grade = open(user_grade).read().strip()

        user_email = append_at_cs(user_re.match(submit).group(1))
        to_list = [user_email] + bcc

        msg = 'To: {}\nSubject: {} Grade\n\n{}\n\n{}'.format(
            user_email, os.path.basename(proj_dir), grade, generic_grade)
        smtp.sendmail(from_email, to_list, msg)
    smtp.quit()


def purge_files(work_dir, submit_list):
    """Deletes directories with submit name in work_dir"""
    if not os.path.isdir(work_dir):
        exit_error('work_dir does not exist')
        return

    if not FORCE:
        if not verify('Are you sure you want to delete user folders?'):
            return

    for user in submit_list:
        user_dir = os.path.join(work_dir, user)
        if os.path.isdir(user_dir):
            print('Deleting: {}'.format(user))
            os.system('rm -rf {}'.format(os.path.join(work_dir, user)))
        else:
            warning('{} does not exist'.format(user_dir))

    if not os.listdir(work_dir):
        if not FORCE:
            if not verify('{} is empty. Do you want to delete?'
                          .format(work_dir)):
                return
        os.rmdir(work_dir)


def run_test_function(work_dir, test_function, submit_list, args):
    if not os.path.isdir(work_dir):
        exit_error('work_dir does not exist. Extract first')

    if test_function not in globals():
        exit_error('Aborting: No function named {}'.format(test_function))

    for submit in submit_list:
        os.chdir(os.path.join(work_dir, submit))
        globals()[test_function](args)


def generate_csv(proj_dir, work_dir, submit_list):
    csv_filename = './{}.csv'.format(proj_dir.split('/')[-1])
    if os.path.exists(csv_filename):
        if not verify('Are you sure you want to clobber the pre-existing '
                      'csv file?'):
            return
    with open(csv_filename, 'w') as csv_file:
        writer = csv.writer(csv_file, delimiter=',', quotechar='"',
                            quoting=csv.QUOTE_MINIMAL)
        writer.writerow(('Firstname', 'Lastname', 'Username', 'Grading'))
        for item in submit_list:
            username = item if '-' not in item else item.split('-')[0]
            fullname = pwd.getpwnam(username).pw_gecos
            firstname = fullname.split()[0]
            lastname = fullname.split()[-1]
            grade_path = os.path.join(work_dir, item, 'GRADE')
            grading = ''
            if os.path.isfile(grade_path):
                with open(grade_path) as grade_file:
                    grading = grade_file.read().strip()
            writer.writerow((firstname, lastname, username, grading))


if __name__ == '__main__':
    # Setup and configure options parser
    usage = 'Usage: %prog [options] proj_dir'
    description = """\
In attempt to save himself time (or so he thought) Bryce Boe embarked on a
journey of semi-great proportions. It started with a simple python file to
extract the newest submission of each student after a project deadline. Soon
later the journey was extended to run make in each of these extracted
directories. Pushing through fatigue, Bryce's journey continued with the
auto execution of certain commands. Upon realizing that more time was probably
spent on this journey rather than the actual grading of the programs Bryce
decided to make it all worthwhile. The journey again was extended to allow for
confirmation of actions and of course making the script as portable as
possible.

"""
    parser = OptionParser(usage=usage, description=description,
                          version='%prog {}'.format(__version__))
    parser.add_option('-l', '--list', action='store_true', default=False,
                      help='list found submissions (default: %default)')
    parser.add_option('-x', '--extract', action='store_true', default=False,
                      help=' '.join(['extract students\' most recent',
                                     'submission (default: %default)']))
    parser.add_option('-m', '--make', action='store_true', default=False,
                      help='run make for each user (default: %default)')
    parser.add_option('--email', metavar='FROM', default=False,
                      help=' '.join(['email grades to students. The email is',
                                     'constructed from a GRADE file in each',
                                     'student\'s work-dir subfolder, plus a',
                                     'generic grade file in the root of the',
                                     'working directory.']))
    parser.add_option('--test-function', metavar='FUNC',
                      help=' '.join(['if specified, this is a python function',
                                     'to call from the directory created for',
                                     'each submission']))
    parser.add_option('--purge', action='store_true', default=False,
                      help=' '.join(['delete extracted user folders and their',
                                     'contents (default: %default)']))
    parser.add_option('--csv', action='store_true', default=False,
                      help='''generate the file (turnin_helper_directory).csv \
in this program\'s directory containing the student\'s first name, last name, \
csil username, and GRADE file contents. This refers to a GRADE file in each \
student's work-dir subfolder''')

    group = OptionGroup(parser, 'Configuration Options')
    group.add_option('--work-dir', metavar='DIR', default='.',
                     help='directory to perform work in (default: %default)')
    group.add_option('--make-dir', metavar='DIR', default='.',
                     help=' '.join(['directory within submission to run make',
                                    '(default: %default)']))
    group.add_option('--makefile', metavar='FILE',
                     help=' '.join(['relative or absolute path to the',
                                    'makefile to use with make (default:'
                                    'student\'s submitted makefile)']))
    group.add_option('--target', metavar='TARGET',
                     help='make target to call')
    group.add_option('--bcc', metavar='EMAIL', action='append',
                     help='email address to bcc - can list multiple times')
    group.add_option('--extension', metavar='EXT', default='tar.Z',
                     help='extension of submitted files (default: %default)')
    group.add_option('-W', '--no-warn', action='store_true', default=False,
                     help='suppress warning messages')
    group.add_option('-f', '--force', action='store_true', default=False,
                     help='answer yes to all verification questions')
    parser.add_option_group(group)

    # Run options parser and verify required command line arguments
    options, args = parser.parse_args()
    if len(args) == 0:
        parser.error('Must provide turnin_directory')

    if options.no_warn:
        DISPLAY_WARNINGS = False
    if options.force:
        FORCE = True

    # Verify supplied paths
    proj_dir = os.path.join(os.getcwd(), args[0]).rstrip('/')
    if not os.path.isdir(proj_dir):
        exit_error('{} does not exist'.format(proj_dir))
    elif not os.path.isfile(os.path.join(proj_dir, 'LOGFILE')):
        warning('proj_dir does not appear to be valid. Reason: No LOGFILE')

    work_dir = os.path.join(os.getcwd(), options.work_dir)
    submit_list = get_latest_turnin_list(proj_dir, options.extension)

    if options.list:
        for user in submit_list:
            print(user)
    if options.extract:
        extract_submissions(proj_dir, work_dir, options.extension, submit_list)
    if options.make:
        if options.makefile:
            makefile = os.path.join(os.getcwd(), options.makefile)
            if not os.path.isfile(makefile):
                exit_error('Makefile ({}) does not exist'.format(makefile))
        else:
            warning('Using student supplied makefiles')
            makefile = None
        make(work_dir, options.make_dir, makefile, options.target, submit_list)
    if options.email:
        email_grades(proj_dir, work_dir, options.email, options.bcc,
                     submit_list)
    if options.purge:
        purge_files(work_dir, submit_list)
    if options.test_function:
        run_test_function(work_dir, options.test_function, submit_list,
                          args[1:])
    if options.csv:
        generate_csv(proj_dir, work_dir, submit_list)
