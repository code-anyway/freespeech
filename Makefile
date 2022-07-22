# Inspired by: https://github.com/huggingface/transformers/blob/main/Makefile
.PHONY: test quality style typecheck data

check_dirs := tests freespeech

test:
	python -m pytest -n auto --dist=loadfile -s -vv ./tests

typecheck:
	python -m mypy --install-types --non-interactive $(check_dirs)

quality:
	black --check $(check_dirs)
	isort --check-only $(check_dirs)
	flake8 $(check_dirs)

style:
	black $(check_dirs)
	isort $(check_dirs)

data:
	mkdir -p data
	python -c "from freespeech.lib import chat; import json; print(json.dumps(chat.generate_training_data(intents=['dub', 'translate', 'transcribe'], sample_sizes=[100, 100, 100]), indent=4))" > data/chat.json