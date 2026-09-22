PYTHON ?= python3
PYTHONPATH := src
PYTHONDONTWRITEBYTECODE ?= 1

.PHONY: help setup check status data-audit train evaluate export-coreml check-ios check-data evaluate-field

help:
	@printf '%s\n' \
		'Olivar Vision commands:' \
		'  make setup         Verify local phase-0 environment without network.' \
		'  make check         Run local tests and structure checks without private data.' \
		'  make status        Print live project status from README.md.' \
		'  make data-audit    Future phase: dataset audit; currently fails explicitly.' \
		'  make train         Future phase: train baseline model; currently fails explicitly.' \
		'  make evaluate      Future phase: evaluate sealed splits; currently fails explicitly.' \
		'  make export-coreml Future phase: convert and compare Core ML model; currently fails explicitly.' \
		'  make check-ios     Future phase: build/test iOS app; currently fails explicitly.'

setup:
	@PYTHONDONTWRITEBYTECODE=$(PYTHONDONTWRITEBYTECODE) $(PYTHON) scripts/setup.py

check:
	@PYTHONPATH=$(PYTHONPATH) PYTHONDONTWRITEBYTECODE=$(PYTHONDONTWRITEBYTECODE) $(PYTHON) -m unittest discover -s tests -p 'test_*.py'
	@PYTHONPATH=$(PYTHONPATH) PYTHONDONTWRITEBYTECODE=$(PYTHONDONTWRITEBYTECODE) $(PYTHON) scripts/validate_dataset_manifest.py configs/datasets.json
	@PYTHONPATH=$(PYTHONPATH) PYTHONDONTWRITEBYTECODE=$(PYTHONDONTWRITEBYTECODE) $(PYTHON) scripts/check_structure.py

status:
	@PYTHONPATH=$(PYTHONPATH) PYTHONDONTWRITEBYTECODE=$(PYTHONDONTWRITEBYTECODE) $(PYTHON) scripts/status.py README.md

data-audit train evaluate export-coreml check-ios check-data evaluate-field:
	@printf '%s\n' 'ERROR: $@ belongs to a future phase and is not implemented yet.' >&2
	@printf '%s\n' 'Do not treat this command as validated until its phase adds real checks.' >&2
	@exit 2
