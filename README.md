# freespeech

[![PyPI](https://img.shields.io/pypi/v/freespeech.svg)](https://pypi.org/project/freespeech/)
[![Changelog](https://img.shields.io/github/v/release/astaff/freespeech?include_prereleases&label=changelog)](https://github.com/astaff/freespeech/releases)
[![Tests](https://github.com/astaff/freespeech/workflows/Test/badge.svg)](https://github.com/astaff/freespeech/actions?query=workflow%3ATest)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/astaff/freespeech/blob/master/LICENSE)

## Installation

Prerequisites:
* Docker
* Google Cloud Service Account Credentials (default: `./id/google-cloud-development-credentials.json`)


```bash
docker build -t freespeech .
```


## Usage

```
docker run -e GOOGLE_APPLICATION_CREDENTIALS="/root/freespeech/id/google-cloud-development-credentials.json" freespeech --help
```

## Development

### Environment

It is recommended to use VSCode's Dev Container extension and get a shell into container as a part of your development environment.

If your preferred workflow is different, you can get a shell with codebase mounted and application
credentials mounted by running the following command from the repository's root directory:

```bash
docker run -it \
    -e GOOGLE_APPLICATION_CREDENTIALS="/root/freespeech/id/google-cloud-development-credentials.json" \
    -v $(pwd):/root/freespeech \
    --entrypoint /bin/bash freespeech
```

### Common tasks

From project home directory in the container:
* To run locally: `pip install -e .`
* To test locally: `pip install -e ".[test]"`
* To run the tests: `pytest tests/` (or specific file or glob?).
