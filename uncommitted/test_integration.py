"""Test whether `uncommitted` works."""

import os
import re
import pytest
import shutil
import stat
import sys
import tempfile
import textwrap
import uncommitted.command
from subprocess import check_call, call


def correct_path_on_windows(path):
    if sys.platform == 'win32':
        path = str.replace(path, "\\", "\\\\")
        sep = os.sep + os.sep
    else:
        sep = os.sep
    return path, sep


def dedent(b, **substitutions):
    b = textwrap.dedent(b).replace('/', os.sep).encode('utf-8')
    for name, value in substitutions.items():
        b = b.replace(b'{%s}' % name.encode('utf-8'), value.encode('utf-8'))
    return b

def handle_remove_read_only(func, path, exc_info):
    """
    Error handler for ``shutil.rmtree``.

    If the error is due to an access error (read only file)
    it attempts to add write permission and then retries.

    If the error is for another reason it re-raises the error.

    Credit : http://www.voidspace.org.uk/downloads/pathutils.py
    Copyright Michael Foord 2004
    Released subject to the BSD License

    Usage : ``shutil.rmtree(path, onerror=onerror)``
    """
    if not os.access(path, os.W_OK):
        # Is the error an access error ?
        os.chmod(path, stat.S_IWUSR)
        func(path)
    else:
        raise


@pytest.fixture(scope='module')
def tempdir():
    """Temporary directory in which all tests will run."""
    tempdir = tempfile.mkdtemp(prefix='uncommitted-test')
    yield tempdir
    shutil.rmtree(tempdir, onerror=handle_remove_read_only)

@pytest.fixture(scope='module')
def cc(tempdir):
    """Wrapper around `check_call` that sets $HOME to a temp directory."""
    def helper(*args, **kwargs):
        # Let's use tempdir as home folder so we don't touch the user's config
        # files (e.g. ~/.gitconfig):
        if 'env' not in kwargs:
            kwargs['env'] = os.environ.copy()
        kwargs['env']['HOME'] = tempdir
        check_call(*args, **kwargs)
    return helper


@pytest.fixture(scope='module')
def hg_identity():
    """Sets the ui.username command line option."""
    return ['--config', 'ui.username=dummy']


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
def checkouts(git_identity, hg_identity, tempdir, cc):
    """Clean (i.e. everything committed) and dirty (i.e. with uncommitted
    changes) repositories (Git, Mercurial and Subversion).
    They will be created in a subdirectory of `tempdir`, whose path will be
    returned."""
    checkouts_dir = os.path.join(tempdir, 'checkouts')
    os.mkdir(checkouts_dir)

    for system in 'git', 'hg', 'svn':
        for state in 'clean', 'dirty', 'ignore':
            d = os.path.join(checkouts_dir, system + '-' + state)

            # Create the repo:
            if system == 'svn':
                repo = d + '-repo'
                repo_url = 'file:///' + repo.replace(os.sep, '/')
                cc(['svnadmin', 'create', repo])
                cc(['svn', 'co', repo_url, d])
            else:
                os.mkdir(d)
                cc([system, 'init', '.'], cwd=d)

            # Initial commit to the master branch:
            file_to_edit = os.path.join(d, filename)
            with open(file_to_edit, 'wb') as f:
                f.write(maxim)
            cc([system, 'add', filename], cwd=d)
            if system == 'hg':
                cc([system] + hg_identity + ['commit', '-m', 'Add a maxim'], cwd=d)
            else:
                cc([system, 'commit', '-m', 'Add a maxim'], cwd=d)

            # Another commit to the master branch:
            if system != 'svn':
                with open(file_to_edit, 'ab') as f:
                    f.write(more_maxim)
                cc([system, 'add', filename], cwd=d)
                if system == 'hg':
                    cc([system] + hg_identity + ['commit', '-m', 'Add more maxim'], cwd=d)
                else:
                    cc([system, 'commit', '-m', 'Add more maxim'], cwd=d)

            # Make the master branch dirty:
            if state == 'dirty' or state == 'ignore':
                with open(file_to_edit, 'ab') as f:
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
                with open(file_to_edit, 'ab') as f:
                    f.write(even_more_maxim)
                cc([system, 'add', filename], cwd=complex_clone_dir)
                cc([system, 'commit', '-m', 'Even more maxim'],
                   cwd=complex_clone_dir)

    cc([system, 'checkout', 'not-behind-ahead'], cwd=complex_clone_dir)

    return clones_dir

@pytest.fixture(scope='module')
def repo_with_submodules(git_identity, tempdir, checkouts, cc):
    """Repository with a submodule used to test detection of non-tracking
    branches in submodules.
    Will be created in a subdirectory of `tempdir`, whose path will be
    returned."""
    # Create a new repository:
    d = os.path.join(tempdir, 'with-submodules')
    os.mkdir(d)
    system = 'git'
    cc([system, 'init'], cwd=d)

    # Add various submodules that will challenge our ability to parse
    # the submodule directory names out of git's output.
    for suffix in ' (parens)', ' (open paren', ' close paren)':
        submodule_name = system + suffix
        remote = os.path.join(checkouts, system + '-clean')
        cc([system, 'submodule', 'add', '-f', remote, submodule_name], cwd=d)
        cc([system, 'commit', '-m', 'Initial commit with submodule.'], cwd=d)

        # Create a non-tracking branch in the submodule:
        submodule_dir = os.path.join(d, submodule_name)
        cc([system, 'checkout', '-b', 'non-tracking'], cwd=submodule_dir)

    return d

def run(*args):
    """Runs uncommitted with the given arguments, returning stdout."""
    sys.argv[:] = args
    sys.argv.insert(0, 'uncommitted')
    original = uncommitted.command.output
    outputs = []
    try:
        uncommitted.command.output = outputs.append
        uncommitted.command.main()
    finally:
        uncommitted.command.output = original
    outputs.append(b'')         # so join() will add a terminal linefeed
    return b'\n'.join(outputs)

def test_uncommitted(checkouts):
    """Do we detect repositories having uncommitted changes?"""
    actual_output = run(checkouts)

    # All dirty checkouts and only them:
    expected_output = dedent("""\
        {path}/git-dirty - Git
         M {filename}

        {path}/git-ignore - Git
         M {filename}

        {path}/hg-dirty - Mercurial
         M {filename}

        {path}/hg-ignore - Mercurial
         M {filename}

        {path}/svn-dirty - Subversion
         M       {filename}

        {path}/svn-ignore - Subversion
         M       {filename}

        """, path=checkouts, filename=filename)

    assert actual_output == expected_output

def test_uncommitted_ignore_one(checkouts):
    """Does -I correctly ignore directories?"""
    actual_output = run('-I', 't-ignore', checkouts)

    # All dirty checkouts and only them:
    expected_output = dedent("""\
        {path}/git-dirty - Git
         M {filename}

        {path}/hg-dirty - Mercurial
         M {filename}

        {path}/hg-ignore - Mercurial
         M {filename}

        {path}/svn-dirty - Subversion
         M       {filename}

        {path}/svn-ignore - Subversion
         M       {filename}

        """, path=checkouts, filename=filename)

    assert actual_output == expected_output

def test_uncommitted_ignore_two_verbose(checkouts):
    """Can -I be offered twice?"""
    actual_output = run('-I', 't-ignore', '-I', 'g-ignore', '-v', checkouts)

    # All dirty checkouts and only them:
    expected_output = dedent("""\
        {path}/git-clean - Git

        {path}/git-dirty - Git
         M {filename}

        Ignoring repo: {path}/git-ignore

        {path}/hg-clean - Mercurial

        {path}/hg-dirty - Mercurial
         M {filename}

        Ignoring repo: {path}/hg-ignore

        {path}/svn-clean - Subversion

        {path}/svn-dirty - Subversion
         M       {filename}

        {path}/svn-ignore - Subversion
         M       {filename}

        """, path=checkouts, filename=filename)

    assert actual_output == expected_output

def test_unpushed(clones):
    """Do we detect when any branch (checked out or not) has unpushed
    changes?"""
    actual_output = run(clones)

    clones, sep = correct_path_on_windows(clones)

    # All ahead branches and only them (the checked-out branch is marked with a
    # star):
    expected_output_regex = re.compile(dedent("""\
        ^{path}{sep}git-complex - Git
          behind-ahead         .* \[ahead 1, behind 1\] Even more maxim
        \* not-behind-ahead     .* \[ahead 1\] Even more maxim

        $""", path=clones, sep=sep))

    assert expected_output_regex.match(actual_output) is not None

def test_non_tracking(checkouts):
    """Do we detect non-tracking branches?"""
    clean_git_repo = os.path.join(checkouts, 'git-clean')
    actual_output = run(clean_git_repo, '-n')

    # The 'master' branch isn't tracking any remote:
    expected_output = dedent("""\
        {path} - Git
        [master]

        """, path=clean_git_repo)

    assert actual_output == expected_output

def test_untracked(checkouts):
    """Do we detect untracked files?"""
    system = 'git'
    repo_with_new_file = os.path.join(checkouts, system + '-clean')
    new_filename = 'newfile.txt'
    new_file_path = os.path.join(repo_with_new_file, new_filename)
    try:
        # Especially for this test, create a new file:
        open(new_file_path, 'ab').close()
        actual_output = run(repo_with_new_file, '-u')
    finally:
        os.remove(new_file_path)

    expected_output = dedent("""\
        {path} - Git
        ?? {filename}

        """, path=repo_with_new_file, filename=new_filename)

    assert actual_output == expected_output

def test_stash(checkouts, cc):
    """Do we detect stashed commits?"""
    system = 'git'
    dirty_repo = os.path.join(checkouts, system + '-dirty')
    try:
        # Especially for this test, stash the changes:
        cc([system, 'stash'], cwd=dirty_repo)
        actual_output = run(dirty_repo, '-s')
    finally:
        cc([system, 'stash', 'pop'], cwd=dirty_repo)

    dirty_repo, _ = correct_path_on_windows(dirty_repo)

    expected_output_regex = re.compile(dedent("""\
        ^{path} - Git
        stash@\{0\}: WIP on master: .* Add more maxim

        $""", path=dirty_repo))
    print(actual_output)
    assert expected_output_regex.match(actual_output) is not None

def test_verbose(checkouts):
    """Do we list clean repos in verbose mode as well?"""
    system = 'git'
    clean_repo = os.path.join(checkouts, system + '-clean')
    actual_output = run(clean_repo, '--verbose')

    # The clean repository:
    expected_output = dedent("""\
        {path} - Git

        """, path=clean_repo)

    assert actual_output == expected_output

def test_follow_symlinks(checkouts):
    """Do we follow symlinks?"""
    system = 'git'
    repo_with_symlink = os.path.join(checkouts, system + '-clean')
    pointed_repo = os.path.join(checkouts, system + '-dirty')
    symlink = os.path.join(repo_with_symlink, 'symlink')
    try:
        # Especially for this test, create a symlink to `git-dirty` from within
        # `git-clean`:
        if sys.platform == 'win32':
            call(['mklink', '/J', symlink, pointed_repo],
                 shell=True)
        else:
            os.symlink(pointed_repo, symlink)

        actual_output = run(repo_with_symlink, '-L')
    finally:
        os.unlink(symlink)

    # Only the pointed dirty repo, as the pointing repo remained clean (the
    # symlink is just an untracked file):
    expected_output = dedent("""\
        {path} - Git
         M {filename}

        """, path=symlink, filename=filename)

    assert actual_output == expected_output

def test_submodules(repo_with_submodules):
    """Do we inspect submodules?"""
    actual_output = run(repo_with_submodules, '-n')

    # The repo's `master` and the submodule's `non-tracking` branches aren't
    # tracking any remote branch, but the submodule masters are:
    expected_output = dedent("""\
        {path} - Git
        [master]

        {path}/git (open paren - Git
        [non-tracking]

        {path}/git (parens) - Git
        [non-tracking]

        {path}/git close paren) - Git
        [non-tracking]

        """, path=repo_with_submodules)

    assert actual_output == expected_output

@pytest.fixture(scope='module')
def svn_locked(tempdir, cc):
    """SVN repo containing a locked file.
    It will be created in a subdirectory of `tempdir`, whose path will be
    returned."""
    locked = os.path.join(tempdir, 'svn' + '-' + 'locked')

    # Create the locally locked repo:
    repo = locked + '-repo'
    repo_url = 'file:///' + repo.replace(os.sep, '/')
    cc(['svnadmin', 'create', repo])
    cc(['svn', 'co', repo_url, locked])

    file_to_lock = os.path.join(locked, filename)

    # Make the repo contain a locked file:
    with open(file_to_lock, 'ab') as f:
        f.write(maxim)

    cc(['svn', 'add', file_to_lock],
       cwd=locked)
    cc(['svn', 'commit', file_to_lock, '-m', 'add file to be locked'],
       cwd=locked)
    cc(['svn', 'lock', file_to_lock, '-m', 'lock file'], cwd=locked)

    return locked

def test_svn_lock_ignored(svn_locked):
    """Do we omit locked files when `--ignore-svn-states` contains `K`?"""
    actual_output = run('--ignore-svn-states', 'K', svn_locked)

    # All dirty checkouts and only them:
    expected_output = b""
    assert actual_output == expected_output

def test_svn_lock_detected(svn_locked):
    """Do we detect svn repository having locked state?"""
    actual_output = run(svn_locked)
    expected_output = dedent("""\
            {path} - Subversion
                  K  {filename}

            """, path=svn_locked, filename=filename)

    assert actual_output == expected_output

def test_symlink_loop(checkouts):
    """Do we detect symlink loops and stop walking them gracefully?"""
    system = 'git'
    repo_with_symlink = os.path.join(checkouts, system + '-clean')
    symlink = os.path.join(repo_with_symlink, 'symlink')
    try:
        # Especially for this test, create a symlink loop:
        if sys.platform == 'win32':
            call(['mklink', '/J', symlink, repo_with_symlink],
                 shell=True)
        else:
            os.symlink(repo_with_symlink, symlink)

        actual_output = run(repo_with_symlink, '-L', '--verbose')
    finally:
        os.unlink(symlink)

    # The repo should appear only once (not 30+ times):
    expected_output = dedent("""\
        {path} - Git

        """, path=repo_with_symlink)

    assert actual_output == expected_output
