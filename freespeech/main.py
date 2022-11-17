from fastapi import FastAPI

from freespeech.api import synthesize, transcribe, transcript, translate

app = FastAPI()


app.include_router(synthesize.router)
app.include_router(transcribe.router)
app.include_router(transcript.router)
app.include_router(translate.router)


