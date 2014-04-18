## Example Usage

Note that for each of these examples, SAMPLE_PROJ is the directory where the
student submissions are tarballed to. working is the directory selected for the
submissions to be extracted to.

### See help information

    ./turnin_helper.py --help

### Extract sample project(s) to current directory (the default)

    ./turnin_helper.py -x SAMPLE_PROJ

* Note the addition of the `bboe-1` directory (most recent bboe submission)
* Note the `extract_log` file added to the current directory

### Extract sample project(s) to `working` directory

    ./turnin_helper.py -x SAMPLE_PROJ --work-dir=working

Must answer yes to the confirmation question

### Compile already extracted project(s) in "working" directory

    ./turnin_helper.py -m SAMPLE_PROJ --work-dir=working

Note the `make_log` file created inside the project directories(s).

__Warning__: Running student submitted makefiles can be dangerous as they can
execute something like `rm -rf ~` which will delete everything in the executing
account's home directory. I recommend not allowing students to make
modifications to the makefile and providing a known clean makefile via the
`--makefile` option.

### Clean up (delete) project(s) in "working" directory

    ./turnin_helper.py --work-dir=working --purge SAMPLE_PROJ

Note that this will only delete directories and their contents which correspond
to the directories created via extraction. If the working directory happens to
be empty after all the project directories have been deleted then a
confirmation will appear asking if you'd like to delete the working directory.

### Extract and run `make clean` on sample project(s) in "working" directory

    ./turnin_helper.py -m SAMPLE_PROJ --work-dir=working --target=clean

### Generate a csv "SAMPLE_PROJ.csv" with grade information by student

    ./turnin_helper.py --csv SAMPLE_PROJ --work-dir=working

The csv will be stored in the `work-dir` and contain columns for student first
names, last names, usernames, and GRADE file contents. GRADE files are
described later in this document.


## Batch emailing students their grades

Once a project has been extracted a grade emails can be sent to all the
students in one simple proceedure. There are a couple of features here:

 * In each student's project directory a GRADE file can be created. If a
   project has a GRADE file in it, when invoking the `--email` function that
   student will be sent an email containing the contents of this file. Emails
   are constructed from the student's username@cs.ucsb.edu. Conversely students
   without a GRADE file will not receive an email (a warning will be output).
 * In the working directory a generic GRADE file can be created. This will be
   be appended to the individial message a student receives. The contents of
   this file are useful for generic information about the project's grading.

### Example proceedure for emailing me (bboe) with the sample project

    # Extract the submission
    ./turnin_helper.py -x SAMPLE_PROJ --work-dir=working
    # Create a generic message about the grading of the project
    echo "Generic info about SAMPLE_PROJ" > working/GRADE
    # Create a student-specific message indicating the grade on the project
    echo "BBOE specific info regarding SAMPLE_PROJ" > working/bboe-1/GRADE
    # Email the results from the account bboe
    ./turnin_helper.py --email=bboe SAMPLE_PROJ/ --work-dir=working

The email I receive looks like:

    From: Bryce Boe <bboe@cs.ucsb.edu>
    Received: from csil.cs.ucsb.edu (localhost [127.0.0.1])
    	  by csil.cs.ucsb.edu (8.14.3/8.14.3) with ESMTP id n9F51GkM023424
    	  for <bboe@cs.ucsb.edu>; Wed, 14 Oct 2009 22:01:16 -0700
    Date: Wed, 14 Oct 2009 22:01:16 -0700
    To: bboe@cs.ucsb.edu
    Subject: SAMPLE_PROJ Grade

    BBOE specific info regarding SAMPLE_PROJ

    Generic info about SAMPLE_PROJ
