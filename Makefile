PYTHON ?= python3
PYTHONPATH := src
PYTHONDONTWRITEBYTECODE ?= 1

.PHONY: help setup check status data-audit lidar-process lidar-compare lidar-geometry lidar-geometry-compare biomass-estimate check-apple-toolchain check-lidar-swift check-ios train evaluate export-coreml check-data evaluate-field

help:
	@printf '%s\n' \
		'Olivar Vision commands:' \
		'  make setup         Verify the local environment without network.' \
		'  make check         Run local tests and structure checks without private data.' \
		'  make status        Print live project status from README.md.' \
		'  make data-audit    Audit an authorized local dataset root; never downloads data.' \
		'  make lidar-process Process SESSION as a private L1 capture; never overwrites results.' \
		'  make lidar-compare Compare LEFT and RIGHT repetitions into OUTPUT.' \
		'  make lidar-geometry Measure isolated tree geometry from SESSION into OUTPUT.' \
		'  make lidar-geometry-compare Compare LEFT and RIGHT geometry reports.' \
		'  make biomass-estimate Calculate an experimental estimate from INPUT into OUTPUT.' \
		'  make check-apple-toolchain Diagnose Xcode selection before any iOS build.' \
		'  make check-lidar-swift Compile and test the cross-platform Swift package.' \
		'  make check-ios     Compile the LiDAR host app for an iOS simulator; requires full Xcode.' \
		'  make train         Future phase: train baseline model; currently fails explicitly.' \
		'  make evaluate      Future phase: evaluate sealed splits; currently fails explicitly.' \
		'  make export-coreml Future phase: convert and compare Core ML model; currently fails explicitly.'

setup:
	@PYTHONDONTWRITEBYTECODE=$(PYTHONDONTWRITEBYTECODE) $(PYTHON) scripts/setup.py

check:
	@PYTHONPATH=$(PYTHONPATH) PYTHONDONTWRITEBYTECODE=$(PYTHONDONTWRITEBYTECODE) $(PYTHON) -m unittest discover -s tests -p 'test_*.py'
	@PYTHONPATH=$(PYTHONPATH) PYTHONDONTWRITEBYTECODE=$(PYTHONDONTWRITEBYTECODE) $(PYTHON) scripts/validate_dataset_manifest.py configs/datasets.json
	@PYTHONPATH=$(PYTHONPATH) PYTHONDONTWRITEBYTECODE=$(PYTHONDONTWRITEBYTECODE) $(PYTHON) scripts/check_structure.py

status:
	@PYTHONPATH=$(PYTHONPATH) PYTHONDONTWRITEBYTECODE=$(PYTHONDONTWRITEBYTECODE) $(PYTHON) scripts/status.py README.md

data-audit:
	@PYTHONPATH=$(PYTHONPATH) PYTHONDONTWRITEBYTECODE=$(PYTHONDONTWRITEBYTECODE) $(PYTHON) scripts/data_audit.py

lidar-process:
	@test -n "$(SESSION)" || (printf '%s\n' 'ERROR: set SESSION=/private/session/path.' >&2; exit 2)
	@PYTHONPATH=$(PYTHONPATH) PYTHONDONTWRITEBYTECODE=$(PYTHONDONTWRITEBYTECODE) $(PYTHON) scripts/lidar_session.py process "$(SESSION)"

lidar-compare:
	@test -n "$(LEFT)" -a -n "$(RIGHT)" -a -n "$(OUTPUT)" || (printf '%s\n' 'ERROR: set LEFT=..., RIGHT=..., and OUTPUT=....' >&2; exit 2)
	@PYTHONPATH=$(PYTHONPATH) PYTHONDONTWRITEBYTECODE=$(PYTHONDONTWRITEBYTECODE) $(PYTHON) scripts/lidar_session.py compare "$(LEFT)" "$(RIGHT)" --output "$(OUTPUT)"

lidar-geometry:
	@test -n "$(SESSION)" -a -n "$(OUTPUT)" -a -n "$(VERTICAL_COVERAGE)" || (printf '%s\n' 'ERROR: set SESSION=..., OUTPUT=..., VERTICAL_COVERAGE=..., and optionally GROUND_Y_M=....' >&2; exit 2)
	@PYTHONPATH=$(PYTHONPATH) PYTHONDONTWRITEBYTECODE=$(PYTHONDONTWRITEBYTECODE) $(PYTHON) scripts/olive_metrics.py geometry "$(SESSION)" --output "$(OUTPUT)" --vertical-coverage "$(VERTICAL_COVERAGE)" $(if $(filter 1 true yes,$(TREE_ISOLATED)),--tree-isolated,) $(if $(GROUND_Y_M),--ground-y-m "$(GROUND_Y_M)",)

lidar-geometry-compare:
	@test -n "$(LEFT)" -a -n "$(RIGHT)" -a -n "$(OUTPUT)" || (printf '%s\n' 'ERROR: set LEFT=..., RIGHT=..., and OUTPUT=....' >&2; exit 2)
	@PYTHONPATH=$(PYTHONPATH) PYTHONDONTWRITEBYTECODE=$(PYTHONDONTWRITEBYTECODE) $(PYTHON) scripts/olive_metrics.py geometry-compare "$(LEFT)" "$(RIGHT)" --output "$(OUTPUT)"

biomass-estimate:
	@test -n "$(INPUT)" -a -n "$(OUTPUT)" || (printf '%s\n' 'ERROR: set INPUT=/path/input.json and OUTPUT=/path/new-output.json.' >&2; exit 2)
	@PYTHONPATH=$(PYTHONPATH) PYTHONDONTWRITEBYTECODE=$(PYTHONDONTWRITEBYTECODE) $(PYTHON) scripts/olive_metrics.py estimate "$(INPUT)" --output "$(OUTPUT)"

check-apple-toolchain:
	@PYTHONDONTWRITEBYTECODE=$(PYTHONDONTWRITEBYTECODE) $(PYTHON) scripts/check_apple_toolchain.py

check-lidar-swift: check-apple-toolchain
	@swift test --package-path ios/OlivarLidarCapture --scratch-path /tmp/olivar-lidar-swift-build

check-ios: check-apple-toolchain
	@xcodebuild -project ios/OlivarVisionLidarApp/OlivarVisionLidarApp.xcodeproj -scheme OlivarVisionLidarApp -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/olivar-lidar-derived-data CODE_SIGNING_ALLOWED=NO build

train evaluate export-coreml check-data evaluate-field:
	@printf '%s\n' 'ERROR: $@ belongs to a future phase and is not implemented yet.' >&2
	@printf '%s\n' 'Do not treat this command as validated until its phase adds real checks.' >&2
	@exit 2
