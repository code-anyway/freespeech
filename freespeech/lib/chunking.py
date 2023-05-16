import openai

from freespeech.types import Language


async def get_response(prompt) -> str:
    response = await openai.ChatCompletion.acreate(
        model="gpt-4",
        messages=[
            {
                "role": "system",
                "content": "Post production editor and writer for the President of Ukraine during war time.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )

    return response["choices"][0]["message"]["content"]  # type: ignore


async def get_chunks(text: str, lang: Language) -> str:
    prompt = f"""
You are given the speech transcript in the language with BCP-47 tag {lang}.
The transcript contains the phrases spoken and a time stamp for the beginning of each phrase. Each phrase contains one or more sentences.
Timestamps are optionally followed by a speaker name and a speech rate in parentheses.
Some sentences can be followed by # indicating a speech pause. Each # corresponds to a 0.2 seconds pause.

Your task is to read the transcript and concatenate phrases that are semantically close.
Make each phrase no longer than 20 seconds. If two sentences are closely related together, don't put # between them.
Otherwise you should add one or more # to indicate speech pauses where necessary.
Don't change the text, keep most of the time stamps, don't change them and don't add new ones.

The transcript is enclosed in ```

```{text}```
"""

    return await get_response(prompt)
