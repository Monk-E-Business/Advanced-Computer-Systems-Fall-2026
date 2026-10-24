# Optional convenience wrappers (MSYS2: pacman -S make). Everything real lives in scripts/.
CXX ?= g++
PY  ?= python3
RUN ?= $(lastword $(sort $(wildcard results/*/)))

.PHONY: all build test verify run quick analyze plots clean
all: run
build:   ; CXX=$(CXX) bash scripts/build.sh
test:    build ; bash scripts/test.sh
verify:  build ; $(PY) scripts/verify_vectorization.py build/verification
run:     ; CXX=$(CXX) bash scripts/run_all.sh
quick:   ; CXX=$(CXX) bash scripts/run_all.sh --quick
analyze: ; $(PY) scripts/analyze.py $(RUN)
plots:   analyze ; $(PY) scripts/plot.py $(RUN)
clean:   ; rm -rf build
