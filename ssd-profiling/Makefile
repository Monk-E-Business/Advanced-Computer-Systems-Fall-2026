# Top-level entry points. `make help` for the list.
# Windows: run from the MSYS2 *UCRT64* shell (g++ = mingw-w64-ucrt-x86_64-gcc).
SHELL    := bash
CXX      ?= g++
CXXFLAGS ?= -O2 -std=c++17 -Wall -Wextra
export PYTHONUTF8 := 1

ifeq ($(OS),Windows_NT)
  EXE      := .exe
  LDFLAGS  += -static
  TOOLS    := bin/ref_qd1.exe bin/winstat.exe
else
  EXE      :=
  TOOLS    := bin/ref_qd1
endif

.PHONY: help build sysinfo prepare validate baseline bs mix qd peak tail ws steady misleading \
        experiments all analyze smoke

help:
	@echo "make build       compile the g++ tools: bin/ref_qd1$(EXE)$(if $(EXE), and bin/winstat.exe)"
	@echo "make smoke       QUICK=1 end-to-end pipeline test (~5 min, meaningless numbers)"
	@echo "make all         full pipeline: sysinfo, prepare, validate, every experiment, analysis"
	@echo "make analyze     parse raw fio JSON -> data/processed, plots/, docs/results_tables.md"
	@echo "individual: sysinfo prepare validate baseline bs mix qd peak tail ws misleading steady"

bin/ref_qd1$(EXE): src/ref_qd1.cpp
	@mkdir -p bin
	$(CXX) $(CXXFLAGS) -o $@ $< $(LDFLAGS)

bin/winstat.exe: src/winstat.cpp
	@mkdir -p bin
	$(CXX) $(CXXFLAGS) -o $@ $< $(LDFLAGS) -ladvapi32

build: $(TOOLS)

sysinfo:    build ; scripts/collect_sysinfo.sh
prepare:    build ; scripts/prepare_target.sh
validate:   build ; scripts/validate.sh
baseline:   build ; scripts/exp_baseline.sh
bs:         build ; scripts/exp_bs_sweep.sh
mix:        build ; scripts/exp_mix_sweep.sh
qd:         build ; scripts/exp_qd_sweep.sh
peak:       build ; scripts/exp_peak.sh
tail:       build ; scripts/exp_tail.sh
ws:         build ; scripts/exp_working_set.sh
misleading: build ; scripts/exp_misleading.sh
steady:     build ; scripts/exp_steady_state.sh

experiments: baseline bs mix qd peak tail ws misleading steady
all: build ; scripts/run_all.sh

analyze:
	python3 analysis/parse_fio.py
	python3 analysis/validate.py
	python3 analysis/plot.py

smoke: build ; QUICK=1 scripts/run_all.sh
