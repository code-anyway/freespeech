# Inspired by: https://github.com/huggingface/transformers/blob/main/Makefile
.PHONY: test quality style typecheck data docs

check_dirs := tests freespeech

test:
	coverage run -m pytest -n auto --dist=loadfile -s -vv ./tests

typecheck:
	python -m mypy --install-types --non-interactive $(check_dirs)

docs:
	mkdocs build

quality:
	black --check $(check_dirs)
	isort --check-only $(check_dirs)
	flake8 $(check_dirs)

style:
	black $(check_dirs)
	isort $(check_dirs)
