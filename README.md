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

```bash
docker run -it \
    -e GOOGLE_APPLICATION_CREDENTIALS="/root/id/test-service-credentials.json" \
    -e NOTION_TOKEN="Notion-integration-token" \
    -v $(pwd)/id:/root/id \
freespeech --help
```

## Development

### Environment

It is recommended to use VSCode's Dev Container extension and get a shell into container as a part of your development environment.

You are expected to set `GOOGLE_APPLICATION_CREDENTIALS` and `NOTION_TOKEN`.

For example:
```shell
export GOOGLE_APPLICATION_CREDENTIALS=$(pwd)/id/test-service-credentials.json
export NOTION_TOKEN="Notion-integration-token"
```

If your preferred workflow is different, you can get shell access into a container with your local working directory mounted:

```bash
docker run -it \
    -e GOOGLE_APPLICATION_CREDENTIALS="/workspace/freespeech/id/test-service-credentials.json" \
    -e NOTION_TOKEN="Notion-integration-token" \
    -v $(pwd):/workspace/freespeech \
    --workdir="/workspace/freespeech" \
    --entrypoint /bin/bash freespeech
```

### Common tasks

From project home directory in the container:
* To run locally: `pip install -e .` and `freespeech --help`
* To test locally: `pip install -e ".[test]"`
* To run the tests: `make test`.
