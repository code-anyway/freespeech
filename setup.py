import os

from setuptools import setup

VERSION = "0.2"


def get_long_description():
    with open(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.md"),
        encoding="utf8",
    ) as fp:
        return fp.read()


setup(
    name="freespeech",
    description="null",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    author="Artyom Astafurov",
    url="https://github.com/astaff/freespeech",
    project_urls={
        "Issues": "https://github.com/astaff/freespeech/issues",
        "CI": "https://github.com/astaff/freespeech/actions",
        "Changelog": "https://github.com/astaff/freespeech/releases",
    },
    license="Apache License, Version 2.0",
    version=VERSION,
    packages=[
        "freespeech",
        "freespeech.lib",
        "freespeech.lib.storage",
        "freespeech.api",
    ],
    entry_points="""
        [console_scripts]
        freespeech=freespeech.cli:cli
    """,
    install_requires=[
        "aiohttp",
        "click",
        "ffmpeg-python",
        # TODO (astaff): update/remove after https://github.com/pytube/pytube/pull/1282
        # is merged/released
        "pytube @ git+https://github.com/kinshuk-h/pytube.git@72075dddb2153bde89a8de9eb8def91d41da3655#egg=pytube-12.0.1",  # noqa E501
        "google-cloud-texttospeech",
        "google-cloud-translate",
        "google-cloud-storage",
        "google-cloud-speech",
        "google-cloud-logging",
        "google-cloud-firestore",
        "google-api-python-client",
        "google-auth",
        "google-auth-oauthlib",
        "google-auth-httplib2",
        "requests",
        "types-requests",
    ],
    extras_require={
        "test": [
            "pytest",
            "pytest-aiohttp",
            "pytest-asyncio",
            "pytest-xdist",
            "requests-mock",
            "black",
            "isort",
            "coverage",
        ]
    },
    python_requires=">=3.10",
)
