from distutils.core import setup

setup(
        name='lnsd',
        packages=['lns', 'lns.socks'],
        author='Adam Marchetti',
        version='0.1',
        description='LAN Naming System',
        author_email='adamnew123456@gmail.com',
        url='http://github.com/adamnew123456/lnsd',
        keywords=['lan', 'networking', 'naming'],
        classifiers = [
            "Programming Language :: Python :: 3",
            "Operating System :: POSIX :: Linux",
            "License :: OSI Approvied :: BSD License",
            "Intended Audience :: End Users",
            "Development Status :: 4 - Beta",
            "Topic :: System :: Networking",
            "Topic :: Utilities",
        ],
        long_description = """\
LAN Naming System - lnsd
========================

Provides a distributed naming system for use within LANs.
""")
