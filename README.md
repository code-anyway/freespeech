# freespeech

## Installation

### Prerequisites:

* Ffmpeg
* (Optional) Docker

### Clone the Repo

```shell
gh repo clone astaff/freespeech
cd freespeech
```
or
```shell
git clone https://github.com/astaff/freespeech.git
cd freespeech
```

### Setup the Credentials

1. Copy `.env` file into `/`
2. `mkdir id` and copy credentials (Google, etc) to `id/`

### Setup Git hooks
Run `bin/copy_hooks.sh`

### Common tasks

From project home directory:

- To run locally: `pip install -e .` and `freespeech --help`
- To test locally: `pip install -e ".[test]"`
- To run the tests: `make test`
- To generate training data: `make data`
- To build docs locally: `pip install -e ".[docs]" && make docs`

## Cloud Info

### Azure

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


### Google

TBD

## Telegram

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
