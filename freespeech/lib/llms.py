import openai

from freespeech import env


async def get_response(prompt: str, model="gpt-4") -> str:
    openai.api_key = env.get_openai_key()
    openai.organization = env.get_openai_organization()
    response = await openai.ChatCompletion.acreate(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "Post production editor and writer.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )

    return response["choices"][0]["message"]["content"]  # type: ignore
