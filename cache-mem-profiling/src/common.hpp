// common.hpp - option parsing, size parsing, RNG, clock calibration, and
// in-process hardware counters (Linux perf_event_open; on Windows counters are
// collected externally with AMD uProf by scripts/lib.sh, so they print NaN here).
#pragma once

#include <cstdint>
#include <cstdio>
#include <map>
#include <string>
#include <vector>

#include "platform.hpp"

size_t parse_size(const std::string &s);                 // "64K", "1.5M", "1G", bytes
std::vector<int> parse_cpulist(const std::string &s);    // "0,2,4-7"; "none" => {}

inline uint64_t xorshift64(uint64_t &s) {
    uint64_t x = s;
    x ^= x << 13;
    x ^= x >> 7;
    x ^= x << 17;
    s = x;
    return x;
}

extern volatile uint64_t g_sink;

// Effective core clock in GHz from a chain of dependent register-register adds
// (1 cycle each). Register-register on purpose: Golden Cove and later fold
// dependent add-immediate chains at rename and would over-report ~4-5x.
double calibrate_ghz();

// ---- options ---------------------------------------------------------------
// Minimal long-option parser: --name value | --name=value | --flag
class Args {
  public:
    struct Spec {
        const char *name;
        bool takes_value;
    };
    Args(int argc, char **argv, const std::vector<Spec> &specs, const char *usage);
    bool has(const char *name) const { return vals_.count(name) > 0; }
    std::string str(const char *name, const std::string &def = "") const;
    long long num(const char *name, long long def) const;
    double real(const char *name, double def) const;
    size_t size(const char *name, size_t def) const;
    [[noreturn]] void fail(const std::string &msg = "") const;

  private:
    std::map<std::string, std::string> vals_;
    std::string usage_, prog_;
};

// All benchmarks print CSV rows to stdout, or append them to --out FILE (used
// when an external profiler wraps the run and also writes to the console).
FILE *open_output(const Args &a);

// --meta FILE: write "total_ns,ghz" for the whole process (start of main's static
// init to now) so an external sampling profiler's coverage can be checked:
// expected busy cycles = total_ns * ghz (single-threaded, pinned, always busy).
void write_meta(const Args &a, double ghz);

// ---- hardware counters -------------------------------------------------------
constexpr int NPERF = 7;
extern const char *perf_names[NPERF];

class Perf {
  public:
    void init();      // counts the calling thread, user space only
    void start();
    void stop();
    void read(double out[NPERF]);  // multiplex-scaled; NaN if unavailable
    ~Perf();

  private:
    int fd_[NPERF] = {-1, -1, -1, -1, -1, -1, -1};
    bool enabled_ = false;
};

void perf_print_header(FILE *f);
void perf_print_values(FILE *f, const double v[NPERF]);
void perf_print_empty(FILE *f);
