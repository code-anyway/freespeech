# Tutorial

## Overview

In this tutorial we are going to walk you through the steps necessary to produce an editable
machine transcription in Google Docs, translate it, and synthesize a high-quality dub, using freespeech library.

Here are the steps involved:

* Install freespeech.
* Establish client session.
* Load transcript from subtitles.
* Translate.
* Save/Load to/from Google Docs.
* Synthesize speech and create a dub.

## Install freespeech

```shell
pip install freespeech
```

## Create Client Session

Using API token, create client session.

Please contact <hello@freespeechnow.ai> for early access.

```python
from freespeech.client import client, transcript

session = client.create(key="your-api-token")
```

## Load Transcript from Subtitles

Generate `Transcript` from `"Subtitles"` for YouTube [video](https://www.youtube.com/watch?v=ALaTm6VzTBw) in
English language (`"en-US"`).

```python
task = await transcript.load(
    source="https://www.youtube.com/watch?v=ALaTm6VzTBw",
    method="Subtitles",
    lang="en-US",
    session=session,
)
result = await tasks.future(task)
```

## Translate

Translate `Transcript` from English to Portuguese (`"pt-PT"`).

```python
task = await transcript.translate(
    transcript=result,
    lang="pt-PT"
)
result = await tasks.future(task)
```

## Save to Google Docs

```python
task = await transcript.save(
    transcript=result,
    method="Google",
)
gdocs_url = await tasks.future(task)
```

## Load from Google Docs

```python
task = await transcript.load(
    source=gdocs_url,
    method="Google",
    lang="pt-PT"
)
result = await tasks.future(task)
```

## Synthesize and Dub

```python
task = await transcript.synthesize(
    transcript=result
)
result = await tasks.future(task)
```