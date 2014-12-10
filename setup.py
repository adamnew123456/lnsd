from setuptools import setup

setup(
        name='lnsd',
        packages=['lns', 'lns.socks'],
        entry_points = {
            'console_scripts':
                ['lnsd = lns.lnsd:main', 'lns-query = lns.query:main']
        },
        author='Adam Marchetti',
        version='0.4',
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
# LAN Naming System - lnsd

Provides a distributed naming system for use within LANs, along with a SOCKS
server to make accessing hosts easier.
""")
