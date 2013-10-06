from distutils.core import setup
from textwrap import dedent
import uncommitted

description, long_description = uncommitted.__doc__.split('\n', 1)

setup(
    name='uncommitted',
    version=uncommitted.__version__,
    description=description,
    long_description=long_description.lstrip(),
    author='Brandon Rhodes',
    author_email='brandon@rhodesmill.org',
    url='http://github.com/brandon/uncommitted/',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
        'Topic :: Software Development :: Version Control',
        'Topic :: Utilities',
        ],
    packages=['uncommitted'],
    entry_points=dedent("""
        [console_scripts]
        uncommitted = uncommitted.command:main
        """),
    )
