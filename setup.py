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
        "freespeech.lib.tasks",
        "freespeech.api",
        "freespeech.client",
    ],
    entry_points="""
        [console_scripts]
        freespeech=freespeech.cli:cli
    """,
    install_requires=[
        "aiohttp",
        "aiogram",
        "azure-ai-language-conversations",
        "azure-storage-blob",
        "click",
        "deepgram-sdk",
        "ffmpeg-python",
        # TODO (astaff): update/remove after https://github.com/pytube/pytube/pull/1282
        # is merged/released,
        "pytube @ git+https://github.com/brilliant-ember/pytube.git@a3c96b92a517d7e2978a45112cbf11993271c010#egg=pytube-12.0.1",  # noqa E501
        "google-cloud-texttospeech",
        "google-cloud-translate",
        "google-cloud-storage",
        "google-cloud-speech",
        "google-cloud-tasks",
        "google-cloud-logging",
        "google-cloud-firestore",
        "azure-cognitiveservices-speech",
        "google-api-python-client",
        "google-auth",
        "google-auth-oauthlib",
        "google-auth-httplib2",
        "hypothesis",
        "pydantic",
        "requests",
        "types-requests",
    ],
    extras_require={
        "docs": [
            "markdown-include",
            "mdx_truly_sane_lists",
            "mkdocs",
            "mkdocs-autorefs",
            "mkdocs-exclude",
            "mkdocs-material",
            "mkdocstrings-python",
        ],
        "test": [
            "coverage",
            "pytest",
            "pytest-aiohttp",
            "pytest-asyncio",
            "pytest-xdist",
            "requests-mock",
            "black",
            "isort",
            "coverage",
            "flake8",
            "mypy"
        ]
    },
    python_requires=">=3.10",
)
