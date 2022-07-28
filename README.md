# freespeech

[![PyPI](https://img.shields.io/pypi/v/freespeech.svg)](https://pypi.org/project/freespeech/)
[![Changelog](https://img.shields.io/github/v/release/astaff/freespeech?include_prereleases&label=changelog)](https://github.com/astaff/freespeech/releases)
[![Tests](https://github.com/astaff/freespeech/workflows/Test/badge.svg)](https://github.com/astaff/freespeech/actions?query=workflow%3ATest)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/astaff/freespeech/blob/master/LICENSE)

## Installation

Prerequisites:

* Docker
* Google Cloud Service Account Credentials (
  default: `./id/google-cloud-development-credentials.json`)

```bash
docker build -t freespeech .
```

## Usage

```bash
docker run -it \
    -e GOOGLE_APPLICATION_CREDENTIALS="/root/id/test-service-credentials.json" \
    -e AZURE_REGION="CHANGE: region for example eastus," \
    -e AZURE_SUBSCRIPTION_KEY="CHANGE: subscription key" \
    -e NOTION_TOKEN="Notion-integration-token" \
    -e FREESPEECH_STORAGE_BUCKET="freespeech-tests" \
    -v $(pwd)/id:/root/id \
freespeech --help
```

## Development

### Environment

It is recommended to use VSCode's Dev Container extension and get a shell into container
as a part of your development
environment.

You are expected to set:

* `GOOGLE_APPLICATION_CREDENTIALS`
* `NOTION_TOKEN`
* `FREESPEECH_STORAGE_BUCKET`
* `AZURE_REGION` and `AZURE_SUBSCRIPTION_KEY` to use Microsoft TTS service
* `AZURE_CONVERSATIONS_TOKEN`
* `DEEPGRAM_TOKEN`
* `TELEGRAM_WEBHOOK_URL` and `TELEGRAM_BOT_TOKEN` - see Telegram section below

For example:

```shell
# TODO: come up with an opinionated way of managing such configs locally
export GOOGLE_APPLICATION_CREDENTIALS=$(pwd)/id/test-service-credentials.json
export NOTION_TOKEN="Notion-integration-token"
export AZURE_REGION="CHANGE: region for example eastus,"
export AZURE_SUBSCRIPTION_KEY="CHANGE: subscription key"
```

If your preferred workflow is different, you can get shell access into a container with
your local working directory
mounted:

```bash
docker run -it \
    -e GOOGLE_APPLICATION_CREDENTIALS="/workspace/freespeech/id/test-service-credentials.json" \
    -e NOTION_TOKEN="Notion-integration-token" \
    -e FREESPEECH_STORAGE_BUCKET="freespeech-tests" \
    -e AZURE_REGION="CHANGE: region for example eastus," \
    -e AZURE_SUBSCRIPTION_KEY="CHANGE: subscription key" \
    -v $(pwd):/workspace/freespeech \
    --workdir="/workspace/freespeech" \
    --entrypoint /bin/bash freespeech
```

### Common tasks

From project home directory in the container:

- To run locally: `pip install -e .` and `freespeech --help`
- To test locally: `pip install -e ".[test]"`
- To run the tests: `make test`
- To generate training data: `make data`
- To build docs locally: `pip install -e ".[docs]" && make docs`

### Cloud

#### Azure

Currently, text-to-speech from Azure is used. In order to get a working environment, one
needs to:

1. Have a Microsoft Azure account. https://azure.microsoft.com/en-us/free/ to get
   started
2. Create a Speech resource in certain Azure region
   https://ms.portal.azure.com/#create/Microsoft.CognitiveServicesSpeechServices
3. Obtain values for `AZURE_REGION` and `AZURE_SUBSCRIPTION_KEY` required by the app
   [link to guide](https://docs.microsoft.com/en-us/azure/cognitive-services/cognitive-services-apis-create-account#get-the-keys-for-your-resource)

General quickstart guide:
https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/get-started-speech-to-text

### Telegram

Service is available as a chatbot. You would need to create a chat bot via
https://t.me/BotFather (and hence obtain `TELEGRAM_BOT_TOKEN` to set env). Please also
**disable** privacy mode for bot since we want to react to plain mentions in groups.
This can be done in BotFather settings for your bot via telegram itself.

`TELEGRAM_WEBHOOK_URL` should also be set. This should be a publicly accessible URL
pointing to the webhook. Telegram would push messages to this URL. Typically this would
look like `http://address.tld:8080/tg_webhook` when ran with `start-telegram`
on `address.tld` host.

You can use [ngrok](https://ngrok.com) to forward local port from development machine 
to a public address.
