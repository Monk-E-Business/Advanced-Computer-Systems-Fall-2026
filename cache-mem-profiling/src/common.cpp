// common.cpp - see common.hpp
#include "common.hpp"

#include <cctype>
#include <cerrno>
#include <cmath>
#include <cstdlib>
#include <cstring>

#if !CMP_WINDOWS && defined(__linux__)
#include <linux/perf_event.h>
#include <sys/ioctl.h>
#include <sys/syscall.h>
#include <unistd.h>
#define CMP_PERF 1
#else
#define CMP_PERF 0
#endif

volatile uint64_t g_sink;

size_t parse_size(const std::string &s) {
    char *end;
    double v = std::strtod(s.c_str(), &end);
    while (*end == ' ') end++;
    switch (std::toupper((unsigned char)*end)) {
    case 'K': v *= 1024.0; break;
    case 'M': v *= 1024.0 * 1024.0; break;
    case 'G': v *= 1024.0 * 1024.0 * 1024.0; break;
    default: break;
    }
    return (size_t)v;
}

std::vector<int> parse_cpulist(const std::string &s) {
    std::vector<int> out;
    if (s.empty() || s == "none") return out;
    const char *p = s.c_str();
    while (*p) {
        char *e;
        long a = std::strtol(p, &e, 10);
        if (e == p) break;
        long b = a;
        if (*e == '-') {
            p = e + 1;
            b = std::strtol(p, &e, 10);
        }
        for (long c = a; c <= b; c++) out.push_back((int)c);
        p = e;
        if (*p == ',') p++;
    }
    return out;
}

#if defined(__x86_64__) || defined(__i386__)
#define ADD1(x) __asm__ volatile("add %0, %0" : "+r"(x) : : "cc")
#elif defined(__aarch64__)
#define ADD1(x) __asm__ volatile("add %0, %0, %0" : "+r"(x))
#endif

double calibrate_ghz() {
#ifdef ADD1
    const long iters = 2000000;  // x 20 dependent adds
    double best = 0.0;
    uint64_t x = 1;
    for (int r = 0; r < 7; r++) {
        double t0 = now_ns();
        for (long i = 0; i < iters; i++) {
            ADD1(x); ADD1(x); ADD1(x); ADD1(x); ADD1(x); ADD1(x); ADD1(x); ADD1(x); ADD1(x); ADD1(x);
            ADD1(x); ADD1(x); ADD1(x); ADD1(x); ADD1(x); ADD1(x); ADD1(x); ADD1(x); ADD1(x); ADD1(x);
        }
        double t1 = now_ns();
        double g = (double)iters * 20.0 / (t1 - t0);
        if (g > best) best = g;
    }
    g_sink += x;
    return best;
#else
    return 0.0;
#endif
}

// ---- Args ---------------------------------------------------------------------
Args::Args(int argc, char **argv, const std::vector<Spec> &specs, const char *usage)
    : usage_(usage), prog_(argc ? argv[0] : "prog") {
    stdio_binary();  // every program parses Args first, so this covers all of them
    for (int i = 1; i < argc; i++) {
        std::string a = argv[i];
        if (a.rfind("--", 0) != 0) fail("unexpected argument '" + a + "'");
        std::string name = a.substr(2), val;
        size_t eq = name.find('=');
        bool inline_val = eq != std::string::npos;
        if (inline_val) {
            val = name.substr(eq + 1);
            name = name.substr(0, eq);
        }
        const Spec *sp = nullptr;
        for (const auto &s : specs)
            if (name == s.name) sp = &s;
        if (!sp) fail("unknown option --" + name);
        if (sp->takes_value && !inline_val) {
            if (i + 1 >= argc) fail("--" + name + " needs a value");
            val = argv[++i];
        }
        vals_[name] = sp->takes_value ? val : "1";
    }
}

std::string Args::str(const char *n, const std::string &d) const {
    auto it = vals_.find(n);
    return it == vals_.end() ? d : it->second;
}
long long Args::num(const char *n, long long d) const {
    auto it = vals_.find(n);
    return it == vals_.end() ? d : std::strtoll(it->second.c_str(), nullptr, 0);
}
double Args::real(const char *n, double d) const {
    auto it = vals_.find(n);
    return it == vals_.end() ? d : std::strtod(it->second.c_str(), nullptr);
}
size_t Args::size(const char *n, size_t d) const {
    auto it = vals_.find(n);
    return it == vals_.end() ? d : parse_size(it->second);
}
void Args::fail(const std::string &msg) const {
    if (!msg.empty()) std::fprintf(stderr, "error: %s\n", msg.c_str());
    std::fprintf(stderr, "usage: %s %s", prog_.c_str(), usage_.c_str());
    std::exit(2);
}

static const double g_proc_t0 = now_ns();  // set during static initialisation

void write_meta(const Args &a, double ghz) {
    if (!a.has("meta")) return;
    FILE *f = std::fopen(a.str("meta").c_str(), "wb");
    if (!f) return;
    std::fprintf(f, "total_ns,ghz\n%.0f,%.4f\n", now_ns() - g_proc_t0, ghz);
    std::fclose(f);
}

FILE *open_output(const Args &a) {
    if (!a.has("out")) return stdout;
    FILE *f = std::fopen(a.str("out").c_str(), "ab");
    if (!f) {
        std::fprintf(stderr, "error: cannot open %s for append\n", a.str("out").c_str());
        std::exit(1);
    }
    return f;
}

// ---- counters -------------------------------------------------------------------
const char *perf_names[NPERF] = {"cycles", "instructions", "l1d_miss", "llc_ref", "llc_miss", "dtlb_ref", "dtlb_miss"};

#if CMP_PERF
static int perf_open1(uint32_t type, uint64_t config) {
    perf_event_attr a;
    std::memset(&a, 0, sizeof a);
    a.size = sizeof a;
    a.type = type;
    a.config = config;
    a.disabled = 1;
    a.exclude_kernel = 1;  // works with perf_event_paranoid <= 2
    a.exclude_hv = 1;
    a.read_format = PERF_FORMAT_TOTAL_TIME_ENABLED | PERF_FORMAT_TOTAL_TIME_RUNNING;
    return (int)syscall(SYS_perf_event_open, &a, 0, -1, -1, 0);
}
static uint64_t cache_cfg(uint64_t c, uint64_t op, uint64_t res) { return c | (op << 8) | (res << 16); }

void Perf::init() {
    const uint32_t t[NPERF] = {PERF_TYPE_HARDWARE, PERF_TYPE_HARDWARE, PERF_TYPE_HW_CACHE, PERF_TYPE_HW_CACHE,
                               PERF_TYPE_HW_CACHE, PERF_TYPE_HW_CACHE, PERF_TYPE_HW_CACHE};
    const uint64_t c[NPERF] = {
        PERF_COUNT_HW_CPU_CYCLES,
        PERF_COUNT_HW_INSTRUCTIONS,
        cache_cfg(PERF_COUNT_HW_CACHE_L1D, PERF_COUNT_HW_CACHE_OP_READ, PERF_COUNT_HW_CACHE_RESULT_MISS),
        cache_cfg(PERF_COUNT_HW_CACHE_LL, PERF_COUNT_HW_CACHE_OP_READ, PERF_COUNT_HW_CACHE_RESULT_ACCESS),
        cache_cfg(PERF_COUNT_HW_CACHE_LL, PERF_COUNT_HW_CACHE_OP_READ, PERF_COUNT_HW_CACHE_RESULT_MISS),
        cache_cfg(PERF_COUNT_HW_CACHE_DTLB, PERF_COUNT_HW_CACHE_OP_READ, PERF_COUNT_HW_CACHE_RESULT_ACCESS),
        cache_cfg(PERF_COUNT_HW_CACHE_DTLB, PERF_COUNT_HW_CACHE_OP_READ, PERF_COUNT_HW_CACHE_RESULT_MISS),
    };
    int err = 0;
    for (int i = 0; i < NPERF; i++) {
        fd_[i] = perf_open1(t[i], c[i]);
        if (fd_[i] >= 0) enabled_ = true;
        else err = errno;
    }
    if (!enabled_)
        std::fprintf(stderr,
                     "warning: perf_event_open unavailable (%s). Counters will be NaN.\n"
                     "         Try: sudo sysctl kernel.perf_event_paranoid=1 (VMs often expose no PMU).\n",
                     std::strerror(err));
}
void Perf::start() {
    for (int i = 0; i < NPERF; i++)
        if (fd_[i] >= 0) {
            ioctl(fd_[i], PERF_EVENT_IOC_RESET, 0);
            ioctl(fd_[i], PERF_EVENT_IOC_ENABLE, 0);
        }
}
void Perf::stop() {
    for (int i = 0; i < NPERF; i++)
        if (fd_[i] >= 0) ioctl(fd_[i], PERF_EVENT_IOC_DISABLE, 0);
}
void Perf::read(double out[NPERF]) {
    for (int i = 0; i < NPERF; i++) {
        out[i] = NAN;
        if (fd_[i] < 0) continue;
        struct { uint64_t v, en, run; } r;
        if (::read(fd_[i], &r, sizeof r) == (ssize_t)sizeof r && r.run > 0)
            out[i] = (double)r.v * ((double)r.en / (double)r.run);
    }
}
Perf::~Perf() {
    for (int i = 0; i < NPERF; i++)
        if (fd_[i] >= 0) close(fd_[i]);
}
#else
// Windows: no user-space PMU API. scripts/lib.sh wraps runs with AMD uProf
// (AMDuProfPcm) and fills these columns from its event dump instead.
void Perf::init() {}
void Perf::start() {}
void Perf::stop() {}
void Perf::read(double out[NPERF]) {
    for (int i = 0; i < NPERF; i++) out[i] = NAN;
}
Perf::~Perf() {}
#endif

void perf_print_header(FILE *f) {
    for (int i = 0; i < NPERF; i++) std::fprintf(f, ",%s", perf_names[i]);
}
void perf_print_values(FILE *f, const double v[NPERF]) {
    for (int i = 0; i < NPERF; i++) {
        if (std::isnan(v[i])) std::fprintf(f, ",nan");
        else std::fprintf(f, ",%.0f", v[i]);
    }
}
void perf_print_empty(FILE *f) {
    for (int i = 0; i < NPERF; i++) std::fprintf(f, ",nan");
}
