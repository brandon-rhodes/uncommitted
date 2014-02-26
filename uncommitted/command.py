"""The 'uncommitted' command-line tool itself."""

import os
import re
import sys
from optparse import OptionParser
from subprocess import CalledProcessError, check_output

USAGE = '''usage: %prog [options] path [path...]

  Checks the status of all git, Subversion, and Mercurial repositories
  beneath the paths given on the command line.  Any repositories with
  uncommitted or unpushed changes are printed to standard out, along
  with the status of the files inside.'''

class ErrorCannotLocate(Exception):
    """Signal that we cannot successfully run the locate(1) binary."""

globchar = re.compile(r'([][*?])')

def run(command, **kw):
    """Run `command`, catch any exception, and return lines of output."""
    try:
        output = check_output(command, **kw)
    except CalledProcessError:
        return []
    return output.decode().splitlines()

def escape(s):
    """Escape the characters special to locate(1) globbing."""
    return globchar.sub(r'\\\1', s)

def find_repositories_with_locate(path):
    """Use locate to return a sequence of (directory, dotdir) pairs."""
    command = ['locate', '-0']
    for dotdir in DOTDIRS:
        # Escaping the slash (using '\/' rather than '/') is an
        # important signal to locate(1) that these glob patterns are
        # supposed to match the full path, so that things like
        # '.hgignore' files do not show up in the result.
        command.append(r'%s\/%s' % (escape(path), escape(dotdir)))
        command.append(r'%s\/*/%s' % (escape(path), escape(dotdir)))
    try:
        paths = check_output(command).strip('\0').split('\0')
    except CalledProcessError:
        return []
    return [ os.path.split(p) for p in paths
             if not os.path.islink(p) and os.path.isdir(p) ]

def find_repositories_by_walking(path):
    """Walk a tree and return a sequence of (directory, dotdir) pairs."""
    repos = []
    for dirpath, dirnames, filenames in os.walk(path):
        for dotdir in set(dirnames) & DOTDIRS:
            repos.append((dirpath, dotdir))
    return repos

def status_mercurial(path, ignore_set):
    """Return text lines describing the status of a Mercurial repository."""
    lines = run(['hg', '--config', 'extensions.color=!', 'st'], cwd=path)
    return [ ' ' + l for l in lines if not l.startswith('?') ]

def status_git(path, ignore_set):
    """Return text lines describing the status of a Git repository."""
    lines = run(('git', 'status', '-s', '-b'), cwd=path)
    return [ l for l in lines
             if not l.startswith('?')
                and (not l.startswith('##')) or ('ahead' in l)]

def status_subversion(path, ignore_set):
    """Return text lines describing the status of a Subversion repository."""
    if path in ignore_set:
        return
    keepers = []
    for line in run(['svn', 'st', '-v'], cwd=path):
        if not line.strip():
            continue
        if line.startswith('Performing') or line[0] in 'X?':
            continue
        status = line[:8]
        filename = line[8:].split(None, 3)[-1]
        ignore_set.add(os.path.join(path, filename))
        if status.strip():
            keepers.append(' ' + status + filename)
    return keepers

SYSTEMS = {
    '.git': ('Git', status_git),
    '.hg': ('Mercurial', status_mercurial),
    '.svn': ('Subversion', status_subversion),
    }
DOTDIRS = set(SYSTEMS)

def scan(repos, verbose):
    """Given a repository list [(path, vcsname), ...], scan each of them."""
    ignore_set = set()
    for directory, dotdir in repos:
        vcsname, get_status = SYSTEMS[dotdir]
        lines = get_status(directory, ignore_set)
        if lines is None:  # signal that we should ignore this one
            continue
        if lines or verbose:
            print('{} - {}'.format(directory, vcsname))
            for line in lines:
                print(line)
            print('')

def main():
    parser = OptionParser(usage=USAGE)
    parser.add_option('-l', '--locate', dest='use_locate', action='store_true',
        help='use locate(1) to find repositories (instead of walking)')
    parser.add_option('-v', '--verbose', action='store_true',
        help='print every repository whether changed or not')
    parser.add_option('-w', '--walk', dest='use_walk', action='store_true',
        help='manually walk file tree to find repositories (the default)')
    (options, args) = parser.parse_args()

    if not args:
        parser.print_help()
        exit(2)

    if options.use_locate and options.use_walk:
        sys.stderr.write('Error: you cannot specify both "-l" and "-w"\n')
        exit(2)

    if options.use_locate:
        find_repos = find_repositories_with_locate
    else:
        find_repos = find_repositories_by_walking

    repos = set()

    for path in args:
        path = os.path.abspath(path)
        if not os.path.isdir(path):
            sys.stderr.write('Error: not a directory: %s\n' % (path,))
            continue
        repos.update(find_repos(path))

    repos = sorted(repos)
    scan(repos, options.verbose)
