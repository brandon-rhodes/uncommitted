"""Test whether `uncommitted` works."""

import os
import re
import pytest
import shutil
import sys
import tempfile
import uncommitted.command
from subprocess import check_call
from textwrap import dedent

if sys.version_info.major > 2:
    from io import StringIO
else:
    from StringIO import StringIO

@pytest.fixture(scope='module')
def tempdir():
    """Temporary directory in which all tests will run."""
    tempdir = tempfile.mkdtemp(prefix='uncommitted-test')
    yield tempdir
    shutil.rmtree(tempdir)

@pytest.fixture(scope='module')
def cc(tempdir):
    """Wrapper around `check_call` that sets $HOME to a temp directory."""
    def helper(*args, **kwargs):
        # Let's use tempdir as home folder so we don't touch the user's config
        # files (e.g. ~/.gitconfig):
        if 'env' not in kwargs:
            kwargs['env'] = {}
        kwargs['env']['HOME'] = tempdir
        check_call(*args, **kwargs)
    return helper

@pytest.fixture(scope='module')
def git_identity(cc):
    """Sets the global `user.*` git config entries."""
    cc(['git', 'config', '--global', 'user.email', 'you@example.com'])
    cc(['git', 'config', '--global', 'user.name', 'Your Name'])

filename = 'maxim.txt'

maxim = dedent("""\
    A complex system that works
    is invariably found to have evolved
    from a simple system that worked.
    """)

more_maxim = dedent("""\
    The inverse proposition also appears to be true:
    A complex system designed from scratch
    never works and cannot be made to work.
    """)

even_more_maxim = dedent("""\
    You have to start over,
    beginning with a working simple system.
    """)

@pytest.fixture(scope='module')
def checkouts(git_identity, tempdir, cc):
    """Clean (i.e. everything committed) and dirty (i.e. with uncommitted
    changes) repositories (Git, Mercurial and Subversion).
    They will be created in a subdirectory of `tempdir`, whose path will be
    returned."""
    checkouts_dir = os.path.join(tempdir, 'checkouts')
    os.mkdir(checkouts_dir)

    for system in 'git', 'hg', 'svn':
        for state in 'clean', 'dirty':
            d = os.path.join(checkouts_dir, system + '-' + state)

            # Create the repo:
            if system == 'svn':
                repo = d + '-repo'
                repo_url = 'file://' + repo.replace(os.sep, '/')
                cc(['svnadmin', 'create', repo])
                cc(['svn', 'co', repo_url, d])
            else:
                os.mkdir(d)
                cc([system, 'init', '.'], cwd=d)

            # Initial commit to the master branch:
            file_to_edit = os.path.join(d, filename)
            with open(file_to_edit, 'w') as f:
                f.write(maxim)
            cc([system, 'add', filename], cwd=d)
            cc([system, 'commit', '-m', 'Add a maxim'], cwd=d)

            # Another commit to the master branch:
            if system != 'svn':
                with open(file_to_edit, 'a') as f:
                    f.write(more_maxim)
                cc([system, 'add', filename], cwd=d)
                cc([system, 'commit', '-m', 'Add more maxim'], cwd=d)

            # Make the master branch dirty:
            if state == 'dirty':
                with open(file_to_edit, 'a') as f:
                    f.write(even_more_maxim)

    return checkouts_dir

@pytest.fixture(scope='module')
def clones(git_identity, tempdir, checkouts, cc):
    """Clones of the checkouts (original repositories) used to test detection
    of unpushed changes.
    They will be created in a subdirectory of `tempdir`, whose path will be
    returned."""
    clones_dir = os.path.join(tempdir, 'clones')
    os.mkdir(clones_dir)

    system = 'git'
    remote = os.path.join(checkouts, system + '-clean')

    # Create a clone which we won't touch:
    cc([system, 'clone', remote, system + '-virgin'], cwd=clones_dir)

    # Create a more complex clone in which we will create all kinds of
    # behind/ahead branches:
    complex_clone_name = system + '-complex'
    cc([system, 'clone', remote, complex_clone_name], cwd=clones_dir)
    complex_clone_dir = os.path.join(clones_dir, complex_clone_name)

    for behind in False, True:
        for ahead in False, True:
            # Create a local branch:
            local_branch = ('behind' if behind else 'not-behind') + \
                           ('-ahead' if ahead else '-not-ahead')
            cc([system, 'checkout', '-b', local_branch, 'origin/master'],
               cwd=complex_clone_dir)

            # Make the branch out of date:
            if behind:
                cc([system, 'reset', '--hard', 'HEAD~1'], cwd=complex_clone_dir)
            if ahead:
                file_to_edit = os.path.join(complex_clone_dir,
                                            filename)
                with open(file_to_edit, 'a') as f:
                    f.write(even_more_maxim)
                cc([system, 'add', filename], cwd=complex_clone_dir)
                cc([system, 'commit', '-m', 'Even more maxim'],
                   cwd=complex_clone_dir)

    cc([system, 'checkout', 'not-behind-ahead'], cwd=complex_clone_dir)

    return clones_dir

def run(*args):
    """Runs uncommitted with the given arguments, returning stdout."""
    sys.argv[:] = args
    sys.argv.insert(0, 'uncommitted')
    io = StringIO()
    stdout = sys.stdout
    try:
        sys.stdout = io
        uncommitted.command.main()
    finally:
        sys.stdout = stdout
    return io.getvalue()

def test_uncommitted(checkouts):
    """Do we detect repositories having uncommitted changes?"""
    actual_output = run(checkouts)

    # All dirty checkouts and only them:
    expected_output = dedent("""\
        {path}/git-dirty - Git
         M {filename}

        {path}/hg-dirty - Mercurial
         M {filename}

        {path}/svn-dirty - Subversion
         M       {filename}

        """).format(path=checkouts, filename=filename)

    assert actual_output == expected_output

def test_unpushed_current_branch(clones):
    """Do we detect when the current branch has unpushed changes?"""
    actual_output = run(clones)

    # Only the clone for which the current branch is ahead:
    expected_output = dedent("""\
        {path}/git-complex - Git
        ## not-behind-ahead...origin/master [ahead 1]

        """).format(path=clones)

    assert actual_output == expected_output

def test_unpushed_other_branches(clones, cc):
    """Do we detect a non-checked-out with unpushed changes?"""
    complex_clone_dir = os.path.join(clones, 'git-complex')
    try:
        # Especially for this test, check out a branch which is up-to-date:
        cc(['git', 'checkout', 'master'], cwd=complex_clone_dir)
        actual_output = run(clones)
    finally:
        cc(['git', 'checkout', 'not-behind-ahead'], cwd=complex_clone_dir)

    # All ahead branches and only them:
    expected_output_regex = re.compile(dedent("""\
        ^{path}/git-complex - Git
          behind-ahead         .* \[ahead 1, behind 1\] Even more maxim
          not-behind-ahead     .* \[ahead 1\] Even more maxim

        $""").format(path=clones))

    assert expected_output_regex.match(actual_output) is not None
