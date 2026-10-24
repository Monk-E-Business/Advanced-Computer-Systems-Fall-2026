# Build the cache/memory profiling suite with G++.
#
#   Windows (MSYS2 UCRT64 terminal):  make        -> bin/*.exe (statically linked)
#   Linux:                            make
#   make test                         correctness checks (scripts/validate.sh)
#   make clean
#
# Cross-compiling Windows binaries from Linux (used to test this repo):
#   make TARGET=windows CXX=x86_64-w64-mingw32-g++-posix
CXX ?= g++
OPT ?= -O2 -march=native

ifeq ($(OS),Windows_NT)
TARGET ?= windows
else
TARGET ?= linux
endif

CXXFLAGS ?= $(OPT) -std=c++17 -Wall -Wextra -Wno-unused-parameter
LDLIBS :=

ifeq ($(TARGET),windows)
EXE := .exe
# -muse-unaligned-vector-move: GCC on Windows cannot guarantee 32/64-byte stack
# alignment, so AVX/AVX-512 spills with aligned moves can crash
# (GCC bug 54412). This assembler option makes all such moves unaligned.
CXXFLAGS += -Wa,-muse-unaligned-vector-move -D_WIN32_WINNT=0x0A00
# static: the .exe files run without MSYS2's DLLs on PATH (e.g. under AMD uProf)
LDFLAGS += -static
LDLIBS += -ladvapi32 -lpsapi
else
EXE :=
CXXFLAGS += -pthread
LDLIBS += -pthread
endif

BIN := bin
SRC := src
COMMON := $(SRC)/platform.cpp $(SRC)/common.cpp
HDRS := $(wildcard $(SRC)/*.hpp)
PROGS := $(BIN)/latency$(EXE) $(BIN)/bandwidth$(EXE) $(BIN)/loaded$(EXE) $(BIN)/kernels$(EXE) $(BIN)/sysinfo$(EXE)

all: $(PROGS) $(BIN)/BUILD_INFO

$(BIN):
	mkdir -p $(BIN)

$(BIN)/latency$(EXE): $(SRC)/latency.cpp $(SRC)/chase.cpp $(COMMON) $(HDRS) | $(BIN)
	$(CXX) $(CXXFLAGS) $(LDFLAGS) -o $@ $(SRC)/latency.cpp $(SRC)/chase.cpp $(COMMON) $(LDLIBS)

$(BIN)/bandwidth$(EXE): $(SRC)/bandwidth.cpp $(SRC)/bwkern.cpp $(COMMON) $(HDRS) | $(BIN)
	$(CXX) $(CXXFLAGS) $(LDFLAGS) -o $@ $(SRC)/bandwidth.cpp $(SRC)/bwkern.cpp $(COMMON) $(LDLIBS)

$(BIN)/loaded$(EXE): $(SRC)/loaded.cpp $(SRC)/bwkern.cpp $(SRC)/chase.cpp $(COMMON) $(HDRS) | $(BIN)
	$(CXX) $(CXXFLAGS) $(LDFLAGS) -o $@ $(SRC)/loaded.cpp $(SRC)/bwkern.cpp $(SRC)/chase.cpp $(COMMON) $(LDLIBS)

$(BIN)/kernels$(EXE): $(SRC)/kernels.cpp $(COMMON) $(HDRS) | $(BIN)
	$(CXX) $(CXXFLAGS) $(LDFLAGS) -o $@ $(SRC)/kernels.cpp $(COMMON) $(LDLIBS)

$(BIN)/sysinfo$(EXE): $(SRC)/sysinfo.cpp $(COMMON) $(HDRS) | $(BIN)
	$(CXX) $(CXXFLAGS) $(LDFLAGS) -o $@ $(SRC)/sysinfo.cpp $(COMMON) $(LDLIBS)

# Record exactly how the binaries were built (part of measurement discipline).
$(BIN)/BUILD_INFO: $(PROGS)
	@{ echo "date: $$(date -Iseconds)"; echo "target: $(TARGET)"; echo "cxx: $(CXX)"; \
	   $(CXX) --version | head -1; echo "cxxflags: $(CXXFLAGS)"; echo "ldflags: $(LDFLAGS)"; \
	   echo "git: $$(git rev-parse --short HEAD 2>/dev/null || echo none)"; } > $@

test: all
	./scripts/validate.sh

clean:
	rm -rf $(BIN)

.PHONY: all test clean
