"""Scan filesystem for changes not committed to version control

When working on a version-controlled project on my hard drive, I often
flip over to another project to make a quick change.  By the end of the
day I have forgotten about that other change and only find it months
later when I enter that repository again.  I needed a way to be alerted
at the end of each day about any uncommitted changes sitting around on
my system.

Thus was born this "uncommitted" script: using by either your system
*locate(1)* command or by walking a filesystem tree on its own, it will
find version-controlled directories and print a report on the standard
output about any uncommitted changes still sitting on your drive.  By
running it from a *cron(8)* job you can make this notification routine.

Installing and running "uncommitted"
------------------------------------

You can install the latest version of "uncommitted" from the Python
Package Index with::

    $ pip install uncommitted

This should make the "uncommitted" shell command available to you,
placing it in the same directory as Python.  You can then run
"uncommitted" on a directory and its subdirectories by typing::

    $ uncommitted ~

Should you ever want a list of all repositories, and not just those with
uncommitted changes, you can use the "-v" verbose option::

    $ uncommitted -v ~

You can always get help by running "uncommitted" without arguments or
with the "-h" or "--help" options.

There is also support for using the *locate(1)* command to scan for
repositories, which lets "uncommitted" operate quickly even over very
large filesystems::

    $ uncommitted -l ~/devel

But be warned: because the *locate(1)* database is only updated once a
day on most systems, this will miss repositories which you have created
since its last run.  It also will not work at all if your home directory
is missing from the database because of permissions, encryption, or the
version of *locate(1)* that you have installed.  So do not trust the
output when using this option until you have verified by hand that it
can indeed see an uncommitted change that you leave somewhere
deliberately!

Supported VCs
-------------

At the moment, "uncommitted" supports:

* `Git`_ (.git directories)
* `Mercurial`_ (.hg directories)
* `Subversion`_ (.svn directories)

To operate, "uncommitted" requires the command-line tool for the
corresponding version-control system to be runnable from the shell.
Note that I am not opposed to someone contributing code to support
Bazaar, or other more obscure version control systems, if you want to
contribute additional detection and scanning routines.

Changelog
---------

**1.7** (2016 Oct 9)

- Report all un-pushed git commits, not only commits for the current branch.
- Add ``-L`` that follows symlinks while walking filesystem.
- Add ``-u`` that prints untracked files in git repositories.

**1.6** (2014 Feb 26)

- Show whether git commits need to be pushed.

**1.5** (2013 Oct 29)

- Fix Subversion support under Python 3.
- Add Subversion to the test suite.

**1.4** (2013 Oct 5)

- Made ``-w`` the default, not ``-l``.
- Add compatibility with Python 3.

**1.3** (2010 May 10)

- *Bugfix*: the Git command is "status" not "st".

**1.2** (2010 May 9)

- `Eapen`_ contributed code to support Git.

**1.1** (2010 April 24)

- *Bugfix:* changed *locate(1)* command line to use shell wildcards, since
  it does not support regular expressions under MacOS X.

- *Bugfix:* all repositories were being called "Subversion" repositories.

.. _Mercurial: http://mercurial.selenic.com/
.. _Subversion: http://subversion.tigris.org/
.. _Git: http://git-scm.com/
.. _Eapen: http://eapen.in

"""
__version__ = '1.7'
