import pytest
import subprocess
from freespeech import env


DATASTORE_CMD = (
    "gcloud beta emulators datastore start "
    f"--project {env.get_project_id()} "
    f"--no-store-on-disk "
)


@pytest.fixture
def datastore_env(monkeypatch):
    monkeypatch.setenv("DATASTORE_DATASET", env.get_project_id())
    monkeypatch.setenv("DATASTORE_EMULATOR_HOST", "localhost:8081")
    monkeypatch.setenv(
        "DATASTORE_EMULATOR_HOST_PATH",
        "localhost:8081/datastore")
    monkeypatch.setenv("DATASTORE_HOST", "http://localhost:8081")
    monkeypatch.setenv("DATASTORE_PROJECT_ID", env.get_project_id())


@pytest.fixture
def datastore_emulator(datastore_env):
    proc = subprocess.Popen(
        DATASTORE_CMD,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True
    )

    while (line := proc.stderr.readline()):
        print(line)
        if "Dev App Server is now running." in line.decode():
            break

    yield proc
    proc.stdout.close()
    proc.stderr.close()
    proc.terminate()
    proc.wait()
    # TODO (astaff): there definitely must be a way to do this nicer
    subprocess.run("killall java", shell=True)
