"""The 'uncommitted' command-line tool itself."""

import os
import re
import sys
from optparse import OptionParser
from subprocess import Popen, PIPE

USAGE = '''usage: %prog [options] path [path...]

  Checks the status of all Subversion and Mercurial repositories beneath the
  paths given on the command line.  Any repositories with uncommitted changes
  are printed to standard out, along with the status of the files inside.'''

class ErrorCannotLocate(Exception):
    """Signal that we cannot successfully run the locate(1) binary."""

def find_repositories_with_locate(path):
    """Use locate to return a sequence of (path, vcsname) pairs."""
    dotdirs = [ re.escape(dotdir) for dotdir in DOTDIRS ]
    regex = r'%s/(.+/)?(%s)$' % (re.escape(path), '|'.join(dotdirs))
    process = Popen(('locate', '-0', '--regex', regex), stdout=PIPE)
    paths = process.stdout.read().strip('\0').split('\0')
    return [ (os.path.dirname(p), DOTDIRS[os.path.basename(p)]) for p in paths
             if not os.path.islink(p) and os.path.isdir(p) ]

def find_repositories_by_walking(path):
    """Walk a tree and return a sequence of (path, vcsname) pairs."""
    repos = []
    DOTDIRS_items = DOTDIRS.items()
    for dirpath, dirnames, filenames in os.walk(path):
        for dotdir, vcsname in DOTDIRS_items:
            if dotdir in dirnames:
                repos.append((dirpath, vcsname))
    return repos

def status_mercurial(path, ignore_set):
    """Return text lines describing the status of a Mercurial repository."""
    process = Popen(('hg', 'st'), stdout=PIPE, cwd=path)
    st = process.stdout.read()
    lines = [ l for l in st.splitlines() if not l.startswith('?') ]
    return lines

def status_subversion(path, ignore_set):
    """Return text lines describing the status of a Subversion repository."""
    if path in ignore_set:
        return
    process = Popen(('svn', 'st', '-v'), stdout=PIPE, cwd=path)
    output = process.stdout.read()
    keepers = []
    for line in output.splitlines():
        if not line.strip():
            continue
        if line.startswith('Performing') or line[0] in 'X?':
            continue
        status = line[:8]
        filename = line[8:].split(None, 3)[-1]
        ignore_set.add(os.path.join(path, filename))
        if status.strip():
            keepers.append(status + filename)
    return keepers

DOTDIRS = {'.hg': 'Mercurial', '.svn': 'Subversion'}
STATUS_FUNCTIONS = {'Mercurial': status_mercurial,
                    'Subversion': status_subversion}

def scan(repos, verbose):
    """Given a repository list [(path, vcsname), ...], scan each of them."""
    ignore_set = set()
    for path, vcsname in repos:
        get_status = STATUS_FUNCTIONS[vcsname]
        lines = get_status(path, ignore_set)
        if lines is None:  # signal that we should ignore this one
            continue
        if lines or verbose:
            print path, '- Subversion'
            for line in lines:
                print line
            print

def main():
    parser = OptionParser(usage=USAGE)
    parser.add_option('-l', '--locate', dest='use_locate', action='store_true',
                      help='use locate(1) to find repositories')
    parser.add_option('-v', '--verbose', action='store_true',
                      help='print every repository whether changed or not')
    parser.add_option('-w', '--walk', dest='use_walk', action='store_true',
                      help='manually walk file tree to find repositories')
    (options, args) = parser.parse_args()

    if not args:
        parser.print_help()
        exit(2)

    if options.use_locate and options.use_walk:
        sys.stderr.write('Error: you cannot specify both "-l" and "-w"\n')
        exit(2)

    if options.use_walk:
        find_repos = find_repositories_by_walking
    else:
        find_repos = find_repositories_with_locate

    repos = set()

    for path in args:
        path = os.path.abspath(path)
        if not os.path.isdir(path):
            sys.stderr.write('Error: not a directory: %s\n' % (path,))
            continue
        repos.update(find_repos(path))

    repos = sorted(repos)
    scan(repos, options.verbose)
