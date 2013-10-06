"""Test whether `uncommitted` works."""

import os
import shutil
import sys
import tempfile
import uncommitted.command
from os.path import join
from subprocess import check_call
from textwrap import dedent

if sys.version_info.major > 2:
    from io import StringIO
else:
    from StringIO import StringIO

def create_checkouts(tempdir):
    cc = check_call
    for system in 'git', 'hg': #, 'svn':
        for state in 'clean', 'dirty':
            d = join(tempdir, system + '-' + state)
            os.mkdir(d)
            with open(join(d, 'maxim.txt'), 'w') as f:
                f.write(maxim)
            cc([system, 'init', '.'], cwd=d)
            cc([system, 'add', 'maxim.txt'], cwd=d)
            cc([system, 'ci', '-m', 'Add a maxim'], cwd=d)
            if state == 'dirty':
                with open(join(d, 'maxim.txt'), 'a') as f:
                    f.write(more_maxim)

def test_uncommitted():
    tempdir = tempfile.mkdtemp(prefix='uncommitted-test')
    try:
        create_checkouts(tempdir)
        sys.argv[:] = ['uncommitted', tempdir]
        io = StringIO()
        stdout = sys.stdout
        try:
            sys.stdout = io
            uncommitted.command.main()
        finally:
            sys.stdout = stdout
        result = io.getvalue()
    finally:
        shutil.rmtree(tempdir)
    assert result == expected.format(tempdir=tempdir)

expected = dedent("""\
    {tempdir}/git-dirty - Git
     M maxim.txt

    {tempdir}/hg-dirty - Mercurial
    M maxim.txt

    """)

maxim = dedent("""\
    A complex system that works
    is invariably found to have evolved
    from a simple system that worked.
    The inverse proposition also appears to be true:
    A complex system designed from scratch
    never works and cannot be made to work.
    """)

more_maxim = dedent("""\
    You have to start over,
    beginning with a working simple system.
    """)

if __name__ == '__main__':
    test_uncommitted()
