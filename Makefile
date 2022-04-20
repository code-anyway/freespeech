# Inspired by: https://github.com/huggingface/transformers/blob/main/Makefile
.PHONY: test quality style typecheck

check_dirs := tests freespeech

test:
	python -m pytest -n auto --dist=loadfile -s -vv ./tests/

typecheck:
	python -m mypy $(check_dirs)

quality:
	black --check $(check_dirs)
	isort --check-only $(check_dirs)
	flake8 $(check_dirs)

style:
	black $(check_dirs)
	isort $(check_dirs)
