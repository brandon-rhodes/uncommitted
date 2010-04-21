"""The 'uncommitted' command-line tool itself."""

import os
import sys
from subprocess import Popen, PIPE

def scan(dirpath, ignore_files):
    subdirs = []

    # Build a list of subdirectories.  Along the way, detect whether
    # this directory is a repository, and if so output its status.

    for name in sorted(os.listdir(dirpath)):
        path = os.path.join(dirpath, name)
        if os.path.islink(path):
            continue
        if not os.path.isdir(path):
            continue

        # The presence of a Mercurial directory means we should ask
        # whether any files are modified within this repository.

        if name == '.hg':
            process = Popen(('hg', 'st'), stdout=PIPE, cwd=dirpath)
            st = process.stdout.read()
            lines = [ l for l in st.splitlines() if not l.startswith('?') ]
            if lines:
                print dirpath, '- Mercurial'
                for line in lines:
                    print line
                print
            continue

        # The presence of a Subversion directory gives us two tasks: not
        # only will we need to report whether any files beneath this
        # working directory have been modified, but we will have to know
        # to ignore the sub-directories that Subversion will include
        # recursively in its report - hence why we make "st" verbose.
        # (Why not just skip everything beneath the directory?  Because
        # sometimes people check out unrelated Subversion or Mercurial
        # repositories deep inside a Subversion working tree.)

        if name == '.svn':
            if dirpath in ignore_files:
                continue
            process = Popen(('svn', 'st', '-v'), stdout=PIPE, cwd=dirpath)
            output = process.stdout.read()
            keepers = []
            for line in output.splitlines():
                if not line.strip():
                    continue
                if line.startswith('Performing') or line[0] in 'X?':
                    continue
                status = line[:8]
                filename = line[8:].split(None, 3)[-1]
                ignore_files.add(os.path.join(dirpath, filename))
                if status.strip():
                    keepers.append(status + filename)
            if keepers:
                print dirpath, '- Subversion'
                for line in keepers:
                    print line
                print
            continue
        subdirs.append(path)

    # Scan all subdirectories.

    for subdir in subdirs:
        scan(subdir, ignore_files)

def main():
    for path in sys.argv[1:]:
        scan(path, set())
