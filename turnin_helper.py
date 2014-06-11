#!/usr/bin/env python

"""Grading Script for automatically unpacking submissions created by turnin.

Written By: Bryce Boe (bboe at cs)
Date: 2009/01/27

Last Update: 2014/04/18

"""

from __future__ import print_function
import csv
import os
import pwd
import re
import shutil
import smtplib
import subprocess
import sys
from optparse import OptionParser, OptionGroup

__version__ = '0.2'
DISPLAY_WARNINGS = True
FORCE = False
USER_RE = re.compile('(\w+)(-(\d)+)?')


def sample_test_function(args):
    """A sample test function that creates a the student-specific grade file.

    When turnin_helper is invoked with the argument
    --test-function=sample_test_function this function is called once for each
    submission. Prior to calling this function python changes directories to
    the base of the extracted files for the submission.

    This function in particular simply assigns a score based on whether or not
    the Make process was successful.

    """
    passed = os.path.exists('some_proj')  # The file Make should produce
    with open('GRADE', 'w') as fp:
        fp.write('SCORE: {}\n'.format(int(passed)))


def exit_error(message):
    """Output the message to stdout and exit with status code 1."""
    print('Abort: {}'.format(message))
    sys.exit(1)


def warning(message):
    """If warnings are to be shown, output message to stderr."""
    if DISPLAY_WARNINGS:
        sys.stderr.write('Warning: {}\n'.format(message))


def verify(prompt):
    """Return whether or not the user accepted the prompt.

    The prompt is skipped if `--force` was provided.
    Exit the program if the user replies with a quit response.

    """
    if FORCE:
        return True
    sys.stdout.write('{}: '.format(prompt))
    sys.stdout.flush()
    response = sys.stdin.readline().strip().lower()
    if response in ('quit', 'q'):
        exit_error('user requested quit')
    return response in ('yes', 'y', '1')


def get_latest_turnin_list(proj_dir, extension):
    """Return a list of all the most recent submissions."""
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
    """Extract all submissions in submit_list to work_dir."""
    if not os.path.isdir(work_dir):
        if not verify('Are you sure you want to create {}?'.format(work_dir)):
            exit_error('nothing to do')
        os.mkdir(work_dir)

    for submit in submit_list:
        print('Unpacking: {}'.format(submit))
        extract_dir = os.path.join(work_dir, submit)
        src = os.path.join(proj_dir, '{}.{}'.format(submit, extension))
        if os.path.isdir(extract_dir):
            if not verify('Are you sure you want to overwrite {}?'
                          .format(extract_dir)):
                continue
        else:
            os.mkdir(extract_dir)
        extract_log = os.path.join(extract_dir, 'extract_log')
        with open(extract_log, 'w') as fp:
            if subprocess.call(['tar', '-xvzf', src, '-C', extract_dir],
                               stdout=fp, stderr=fp) != 0:
                exit_error('Extract failed on {}'.format(submit))


def make(work_dir, make_dir, makefile, target, submit_list):
    """Run make using target for all submissions in submit_list."""
    if not os.path.isdir(work_dir):
        exit_error('work_dir does not exist. Extract first')

    args = ['make', '-C', None]  # args[2] will be replaced
    if makefile:
        args.extend(['-f', makefile])
    if target:
        args.append(target)
    for submit in submit_list:
        submit_dir = os.path.join(work_dir, submit, make_dir)
        if not os.path.isdir(submit_dir):
            print('Cannot build: {} does not exist'.format(submit_dir))
            continue
        print('Making: {}'.format(submit))
        args[2] = submit_dir
        with open(os.path.join(work_dir, submit, 'make_log'), 'w') as fp:
            if subprocess.call(args, stdout=fp, stderr=fp) != 0:
                warning('Make failed for {}'.format(submit))


def email_grades(proj_dir, work_dir, from_email, bcc, submit_list):
    """Email all students in submit_list the contents of the GRADE files.

    Students whose project directory does not contain a grade file will be
    skipped.

    The student's grade fill is concatenated with the projects grade file.

    """
    def append_at_cs(email):
        return email if '@' in email else email + '@cs.ucsb.edu'

    # Normalize email accounts
    from_email = append_at_cs(from_email)
    if bcc is None:
        bcc = []
    else:
        bcc = [append_at_cs(x) for x in bcc]

    # Make connection
    smtp = smtplib.SMTP()
    smtp.connect('localhost')

    # Get Generic Message
    generic_grade = ''
    generic = os.path.join(work_dir, 'GRADE')
    if not os.path.isfile(generic):
        if not verify('There is no generic GRADE file, are you '
                      'sure you want to send emails?'):
            return
    else:
        with open(generic) as fp:
            generic_grade = fp.read().strip()

    for submit in submit_list:
        user_grade = os.path.join(work_dir, submit, 'GRADE')
        if not os.path.isfile(user_grade):
            warning('No GRADE file for {}'.format(submit))
            continue
        with open(user_grade) as fp:
            grade = fp.read().strip()

        user_email = append_at_cs(USER_RE.match(submit).group(1))
        to_list = [user_email] + bcc

        msg = 'To: {}\nSubject: {} Grade\n\n{}\n\n{}'.format(
            user_email, os.path.basename(proj_dir), grade, generic_grade)
        smtp.sendmail(from_email, to_list, msg)
    smtp.quit()


def purge_files(work_dir, submit_list):
    """Remove directories in work_dir matching names in submit_list."""
    if not os.path.isdir(work_dir):
        exit_error('work_dir does not exist. Nothing to do.')
        return
    if not verify('Are you sure you want to delete user directories?'):
        return

    for submit in submit_list:
        submit_dir = os.path.join(work_dir, submit)
        if os.path.isdir(submit_dir):
            print('Deleting: {}'.format(submit))
            shutil.rmtree(submit_dir)
        else:
            warning('{} does not exist'.format(submit_dir))

    if not os.listdir(work_dir):
        if not verify('{} is empty. Do you want to delete?'.format(work_dir)):
            return
        os.rmdir(work_dir)


def run_test_function(work_dir, test_function, submit_list, args):
    """Execute test_function for each submission in submit_list.

    Change into the submission directory for each submission before the call.

    """
    if not os.path.isdir(work_dir):
        exit_error('work_dir does not exist. Extract first')

    if test_function not in globals():
        exit_error('No function named {}'.format(test_function))

    old_pwd = os.getcwd()
    for submit in submit_list:
        print('Testing {}'.format(submit))
        os.chdir(os.path.join(work_dir, submit))
        globals()[test_function](args)
    os.chdir(old_pwd)


def generate_csv(proj_dir, work_dir, submit_list):
    """Create a csv containing the names and grade information."""
    csv_filename = os.path.join(work_dir,
                                '{}.csv'.format(os.path.basename(proj_dir)))
    if os.path.exists(csv_filename):
        if not verify('Are you sure you want to clobber the pre-existing '
                      'csv file?'):
            return
    with open(csv_filename, 'w') as csv_file:
        writer = csv.writer(csv_file, delimiter=',', quotechar='"',
                            quoting=csv.QUOTE_MINIMAL)
        writer.writerow(('First Name', 'Last Name', 'User Name', 'Grading'))
        for item in submit_list:
            username = USER_RE.match(item).group(1)
            name_parts = pwd.getpwnam(username).pw_gecos.split()
            # Assume single-word lastnames
            firstname = ' '.join(name_parts[:-1])
            lastname = name_parts[-1]
            grade_path = os.path.join(work_dir, item, 'GRADE')
            grading = ''
            if os.path.isfile(grade_path):
                with open(grade_path) as fp:
                    grading = fp.read().strip()
            writer.writerow((firstname, lastname, username, grading))


if __name__ == '__main__':
    print('Note: Please consider using https://submit.cs.ucsb.edu for future '
          'assignments.\n')
    # Setup and configure options parser
    usage = 'Usage: %prog [options] PROJ_DIR'
    parser = OptionParser(usage=usage, version='%prog {}'.format(__version__))
    parser.add_option('-l', '--list', action='store_true', default=False,
                      help='list found submissions (default: %default)')
    parser.add_option('-x', '--extract', action='store_true', default=False,
                      help=('extract students\' most recent submission '
                            '(default: %default)'))
    parser.add_option('-m', '--make', action='store_true', default=False,
                      help='run make for each user (default: %default)')
    parser.add_option('-c', '--csv', action='store_true', default=False,
                      help=('generate a csv file PROJ_DIR.csv in the working '
                            'directory containing the student\'s first name, '
                            'last name, csil username, and GRADE file '
                            'contents.'))
    parser.add_option('--email', metavar='FROM', default=False,
                      help=('email grades to students from FROM. The email is '
                            'constructed from a GRADE file in each student\'s '
                            'working subdirectory, plus a generic grade file '
                            'in the root of the working directory.'))
    parser.add_option('--purge', action='store_true', default=False,
                      help=('delete extracted user directories and their '
                            'contents (default: %default)'))
    parser.add_option('--test-function', metavar='FUNC',
                      help=('if specified, this is a python function to call '
                            'from the directory created for each submission'))

    group = OptionGroup(parser, 'Configuration Options')
    group.add_option('--work-dir', metavar='DIR', default='.',
                     help='directory to perform work in (default: %default)')
    group.add_option('--make-dir', metavar='DIR', default='.',
                     help=('directory within submission to run make (default: '
                           '%default)'))
    group.add_option('--makefile', metavar='FILE',
                     help=('relative or absolute path to the makefile to use '
                           'with make (default: student\'s submitted '
                           'makefile)'))
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
    if len(args) >= 2:
        parser.error('This application is not designed to work with multiple turnin_directory paths')

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
            if not verify('Are you sure you want to use the students\' '
                          'Makefiles?'):
                exit_error('cannot run make')
            makefile = None
        make(work_dir, options.make_dir, makefile, options.target, submit_list)
    if options.test_function:
        run_test_function(work_dir, options.test_function, submit_list,
                          args[1:])
    if options.email:
        email_grades(proj_dir, work_dir, options.email, options.bcc,
                     submit_list)
    if options.csv:
        generate_csv(proj_dir, work_dir, submit_list)
    if options.purge:
        purge_files(work_dir, submit_list)
