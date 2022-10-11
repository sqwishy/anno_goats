import os
from setuptools import setup


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(
    name="anno_goats",
    version="0.1.0",  # Keep in sync with __init__.py
    author="sqwishy",
    author_email="somebody@froghat.ca",
    description=(),
    license="GPLv3",
    packages=["anno_goats"],
    package_data={},
    long_description=read("README.md"),
    classifiers=[],
    install_requires=["PySide6","lxml"],
    entry_points={
        "console_scripts": [
            "anno-goats=anno_goats.__main__:main",
            "anno-goats-ui=anno_goats.ui.__main__:main",
        ],
    },
)
