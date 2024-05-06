#!/usr/bin/env python3
import setuptools

with open("README.md") as fh:
    long_description = fh.read()

with open("requirements.txt") as fh:
    install_requires = fh.read().splitlines()

setuptools.setup(
    name="spacecat",
    version="0.4.0",
    description="A self hostable modular Discord bot.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://gitlab.com/Mizarc/spacecat-discord-bot",
    author="Mizarc",
    author_email="mizarc@protonmail.com",
    license="Apache License 2.0",
    packages=setuptools.find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: Apache Software License",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Environment :: Console",
        "Topic :: Communications :: Chat",
    ],
    python_requires=">=3.11",
    install_requires=install_requires,
)
