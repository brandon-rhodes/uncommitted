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

globchar = re.compile(br'([][*?])')
git_submodule = re.compile(br'^[-+U ]*\S+ (.*) \([^)]*\)$')
linesep = os.linesep.encode('ascii')

def output(thing):
    """Replacement for print() that outputs bytes."""
    os.write(1, thing + linesep)

def run(command, **kw):
    """Run `command`, catch any exception, and return lines of output."""
    # Windows low-level subprocess API wants str for current working
    # directory.
    if sys.platform == 'win32':
        _cwd = kw.get('cwd', None)
        if _cwd is not None:
            kw['cwd'] = _cwd.decode()
    try:
        # In Python 3, iterating over bytes yield integers, so we call
        # `splitlines()` to force Python 3 to give us lines instead.
        return check_output(command, **kw).splitlines()
    except CalledProcessError:
        return ()
    except FileNotFoundError:
        print("The {} binary was not found. Skipping directory {}.\n"
              .format(command[0], kw['cwd'].decode("UTF-8")))
        return ()

def escape(s):
    """Escape the characters special to locate(1) globbing."""
    return globchar.sub(br'\\\1', s)

def find_repositories_with_locate(path):
    """Use locate to return a sequence of (directory, dotdir) pairs."""
    command = [b'locate', b'-0']
    for dotdir in DOTDIRS:
        # Escaping the slash (using '\/' rather than '/') is an
        # important signal to locate(1) that these glob patterns are
        # supposed to match the full path, so that things like
        # '.hgignore' files do not show up in the result.
        command.append(br'%s\/%s' % (escape(path), escape(dotdir)))
        command.append(br'%s\/*/%s' % (escape(path), escape(dotdir)))
    try:
        paths = check_output(command).strip(b'\0').split(b'\0')
    except CalledProcessError:
        return []
    return [os.path.split(p) for p in paths
            if not os.path.islink(p) and os.path.isdir(p)]

def find_repositories_by_walking_without_following_symlinks(path):
    """Walk a tree and return a sequence of (directory, dotdir) pairs."""
    repos = []
    for dirpath, dirnames, filenames in os.walk(path, followlinks=False):
        for dotdir in set(dirnames) & DOTDIRS:
            repos.append((dirpath, dotdir))
    return repos

def find_repositories_by_walking_and_following_symlinks(path):
    """Walk a tree and return a sequence of (directory, dotdir) pairs."""
    repos = []

    # This is for detecting symlink loops and escaping them. This is similar to
    # http://stackoverflow.com/questions/36977259/avoiding-infinite-recursion-with-os-walk/36977656#36977656
    def inode(path):
        stats = os.stat(path)
        return stats.st_dev, stats.st_ino
    seen_inodes = {inode(path)}

    for dirpath, dirnames, filenames in os.walk(path, followlinks=True):
        inodes = [inode(os.path.join(dirpath, p)) for p in dirnames]
        dirnames[:] = [p for p, i in zip(dirnames, inodes)
                       if not i in seen_inodes]
        seen_inodes.update(inodes)

        for dotdir in set(dirnames) & DOTDIRS:
            repos.append((dirpath, dotdir))
    return repos

def status_mercurial(path, ignore_set, options):
    """Run hg status.

    Returns a 2-element tuple:
    * Text lines describing the status of the repository.
    * Empty sequence of subrepos, since hg does not support them.
    """
    lines = run(['hg', '--config', 'extensions.color=!', 'st'], cwd=path)
    subrepos = ()
    return [b' ' + l for l in lines if not l.startswith(b'?')], subrepos

def status_git(path, ignore_set, options):
    """Run git status.

    Returns a 2-element tuple:
    * Text lines describing the status of the repository.
    * List of subrepository paths, relative to the repository itself.
    """
    # Check whether current branch is dirty:
    lines = [l for l in run(('git', 'status', '-s', '-b'), cwd=path)
             if (options.untracked or not l.startswith(b'?'))
             and not l.startswith(b'##')]

    # Check all branches for unpushed commits:
    lines += [l for l in run(('git', 'branch', '-v'), cwd=path)
              if (b' [ahead ' in l)]

    # Check for non-tracking branches:
    if options.non_tracking:
        lines += [l for l in run(('git', 'for-each-ref',
                                  '--format=[%(refname:short)]%(upstream)',
                                   'refs/heads'), cwd=path)
                  if l.endswith(b']')]

    if options.stash:
        lines += [l for l in run(('git', 'stash', 'list'), cwd=path)]

    discovered_submodules = []
    for l in run(('git', 'submodule', 'status'), cwd=path):
        match = git_submodule.search(l)
        if match:
            discovered_submodules.append(match.group(1))

    return lines, discovered_submodules

def status_subversion(path, ignore_set, options):
    """Run svn status.

    Returns a 2-element tuple:
    * Text lines describing the status of the repository.
    * Empty sequence of subrepos, since svn does not support them.
    """
    subrepos = ()
    if path in ignore_set:
        return None, subrepos
    keepers = []
    for line in run(['svn', 'st', '-v'], cwd=path):
        if not line.strip():
            continue
        if line.startswith(b'Performing') or line[0] in b'X?':
            continue
        status = line[:8]
        ignored_states = options.ignore_svn_states
        if ignored_states and status.strip() in ignored_states:
            continue
        filename = line[8:].split(None, 3)[-1]
        ignore_set.add(os.path.join(path, filename))
        if status.strip():
            keepers.append(b' ' + status + filename)
    return keepers, subrepos

SYSTEMS = {
    b'.git': (b'Git', status_git),
    b'.hg': (b'Mercurial', status_mercurial),
    b'.svn': (b'Subversion', status_subversion),
    }
DOTDIRS = set(SYSTEMS)

def scan(repos, options):
    """Given a repository list [(path, vcsname), ...], scan each of them."""
    ignore_set = set()
    repos = repos[::-1]  # Create a queue we can push and pop from
    while repos:
        directory, dotdir = repos.pop()
        ignore_this = any(pat in directory for pat in options.ignore_patterns)
        if ignore_this:
            if options.verbose:
                output(b'Ignoring repo: %s' % directory)
                output(b'')
            continue

        vcsname, get_status = SYSTEMS[dotdir]
        lines, subrepos = get_status(directory, ignore_set, options)

        # We want to tackle subrepos immediately after their repository,
        # so we put them at the front of the queue.
        subrepos = [(os.path.join(directory, r), dotdir) for r in subrepos]
        repos.extend(reversed(subrepos))

        if lines is None:  # signal that we should ignore this one
            continue
        if lines or options.verbose:
            output(b'%s - %s' % (directory, vcsname))
            for line in lines:
                output(line)
            output(b'')

def main():
    parser = OptionParser(usage=USAGE)
    parser.add_option('-l', '--locate', dest='use_locate', action='store_true',
        help='use locate(1) to find repositories (instead of walking)')
    parser.add_option('-v', '--verbose', action='store_true',
        help='print every repository whether changed or not')
    parser.add_option('-w', '--walk', dest='use_walk', action='store_true',
        help='manually walk file tree to find repositories (the default)')
    parser.add_option('-L', dest='follow_symlinks', action='store_true',
        help='follow symbolic links when walking file tree')
    parser.add_option('-n', '--non-tracking', action='store_true',
        help='print non-tracking branches (git only)')
    parser.add_option('-u', '--untracked', action='store_true',
        help='print untracked files (git only)')
    parser.add_option('-s', '--stash', action='store_true',
        help='print stash (git only)')
    parser.add_option('-I', dest='ignore_patterns', action='append',
        default=[],
        help='ignore any directory paths that contain the specified string')
    parser.add_option(
        '--ignore-svn-states',
        help='ignore SVN states given as a string of status codes (SVN only)')

    (options, args) = parser.parse_args()

    if not args:
        parser.print_help()
        exit(2)

    if options.use_locate and (options.use_walk or options.follow_symlinks):
        sys.stderr.write(
            'Error: you cannot use "-l" together with "-w" or "-L"\n')
        exit(2)

    if options.use_locate:
        find_repos = find_repositories_with_locate
    elif options.follow_symlinks:
        find_repos = find_repositories_by_walking_and_following_symlinks
    else:
        find_repos = find_repositories_by_walking_without_following_symlinks

    if sys.version_info[0] >= 3:
        # Turn string arguments back into their original bytes.
        fix = os.fsencode
        args = [fix(s) for s in args]
        options.ignore_patterns = [fix(s) for s in options.ignore_patterns]
        if options.ignore_svn_states is not None:
            options.ignore_svn_states = [
                fix(s) for s in options.ignore_svn_states
            ]

    repos = set()

    for path in args:
        path = os.path.abspath(path)
        if not os.path.isdir(path):
            sys.stderr.write('Error: not a directory: %s\n' % (path,))
            continue
        repos.update(find_repos(path))

    repos = sorted(repos)
    scan(repos, options)
