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
        "deepl",
        "azure-storage-blob",
        "click",
        "deepgram-sdk",
        "discord.py",
        "fastapi[all]",
        "ffmpeg-python",
        "librosa",
        # TODO (astaff): update/remove after https://github.com/pytube/pytube/pull/1282
        # is merged/released,
        "librosa",
        "google-cloud-texttospeech",
        "google-cloud-translate",
        "google-cloud-storage",
        "google-cloud-speech",
        "google-cloud-tasks",
        "google-cloud-logging",
        "google-cloud-firestore",
        "google-api-python-client",
        "google-auth",
        "google-auth-oauthlib",
        "google-auth-httplib2",
        "pydantic",
        "pytz",
        "requests",
        "soundfile",
        "spacy",
        *[
            f"{lang}_core_web_sm @ https://github.com/explosion/spacy-models/releases/download/{lang}_core_web_sm-3.4.0/{lang}_core_web_sm-3.4.0.tar.gz"  # noqa E501
            for lang in ("en",)
        ],
        *[
            f"{lang}_core_news_sm @ https://github.com/explosion/spacy-models/releases/download/{lang}_core_news_sm-3.4.0/{lang}_core_news_sm-3.4.0.tar.gz"  # noqa E501
            for lang in ("es", "uk", "pt", "ru", "de", "fr", "sv", "it", "fi")
        ],
        "streamlit",
        "telethon",
        "types-requests",
        "spacy",
        "yt-dlp",
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
            "mypy",
        ],
    },
    python_requires=">=3.10",
)
