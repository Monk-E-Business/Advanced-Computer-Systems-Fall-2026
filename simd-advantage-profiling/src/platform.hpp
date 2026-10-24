// platform.hpp - the only OS-specific code: timer, aligned allocation, core pinning, topology.
// Builds with g++ on Windows (MSYS2 UCRT64 / MinGW-w64) and on Linux.
#pragma once
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>

#if defined(_WIN32)
#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0A00 // Windows 10+: GetLogicalProcessorInformationEx with EfficiencyClass
#endif
#include <malloc.h>
#include <windows.h>
#else
#include <sched.h>
#include <time.h>
#include <unistd.h>
#endif

#if defined(__x86_64__) || defined(__i386__)
#include <cpuid.h>
#endif

namespace plat {

// ---------------------------------------------------------------- timer
#if defined(_WIN32)
inline double now_sec() {  // QueryPerformanceCounter: invariant TSC-based, ~100 ns resolution
    static LARGE_INTEGER freq = [] { LARGE_INTEGER f; QueryPerformanceFrequency(&f); return f; }();
    LARGE_INTEGER t;
    QueryPerformanceCounter(&t);
    return (double)t.QuadPart / (double)freq.QuadPart;
}
inline double timer_resolution_ns() {
    LARGE_INTEGER f;
    QueryPerformanceFrequency(&f);
    return 1e9 / (double)f.QuadPart;
}
inline const char *timer_name() { return "QueryPerformanceCounter"; }
#else
inline double now_sec() {
    timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + 1e-9 * (double)ts.tv_nsec;
}
inline double timer_resolution_ns() {
    timespec r;
    clock_getres(CLOCK_MONOTONIC, &r);
    return 1e9 * (double)r.tv_sec + (double)r.tv_nsec;
}
inline const char *timer_name() { return "clock_gettime(CLOCK_MONOTONIC)"; }
#endif

// ---------------------------------------------------------------- aligned allocation
inline void *aligned_alloc_bytes(size_t bytes, size_t align) {
#if defined(_WIN32)
    void *p = _aligned_malloc(bytes, align);
#else
    void *p = nullptr;
    if (posix_memalign(&p, align, bytes) != 0) p = nullptr;
#endif
    if (!p) {
        std::fprintf(stderr, "allocation of %zu bytes failed\n", bytes);
        std::exit(3);
    }
    return p;
}
inline void aligned_free(void *p) {
#if defined(_WIN32)
    _aligned_free(p);
#else
    std::free(p);
#endif
}

// ---------------------------------------------------------------- pinning
// Pin the calling thread to one logical CPU. On Windows also raise the process to HIGH
// priority class so ordinary background work does not preempt the benchmark.
inline bool pin_to_cpu(int cpu) {
    if (cpu < 0) return true;
#if defined(_WIN32)
    if (cpu >= 64) return false; // single processor group only
    SetPriorityClass(GetCurrentProcess(), HIGH_PRIORITY_CLASS);
    return SetThreadAffinityMask(GetCurrentThread(), (DWORD_PTR)1 << cpu) != 0;
#elif defined(__linux__)
    cpu_set_t set;
    CPU_ZERO(&set);
    CPU_SET(cpu, &set);
    return sched_setaffinity(0, sizeof(set), &set) == 0;
#else
    return false;
#endif
}

// ---------------------------------------------------------------- CPU brand string
inline std::string cpu_brand() {
#if defined(__x86_64__) || defined(__i386__)
    unsigned r[12] = {0};
    unsigned a, b, c, d;
    if (__get_cpuid(0x80000000u, &a, &b, &c, &d) && a >= 0x80000004u) {
        for (unsigned i = 0; i < 3; i++) __get_cpuid(0x80000002u + i, &r[4 * i], &r[4 * i + 1], &r[4 * i + 2], &r[4 * i + 3]);
        std::string s(reinterpret_cast<const char *>(r), 48);
        s = s.c_str();
        size_t f = s.find_first_not_of(' ');
        return f == std::string::npos ? s : s.substr(f);
    }
#endif
    return "unknown";
}

#if defined(_WIN32)
// PROCESSOR_RELATIONSHIP is { BYTE Flags; BYTE EfficiencyClass; ... }. Older MinGW headers call the
// second byte Reserved[0], so read it by offset to compile with any header version.
inline int efficiency_class(const PROCESSOR_RELATIONSHIP &pr) {
    return reinterpret_cast<const BYTE *>(&pr)[1];
}
#endif

// ---------------------------------------------------------------- topology as JSON
// caches (bytes, per instance), logical CPUs, physical cores, SMT, hybrid core classes,
// and a suggested CPU to pin to (a high-performance core, not CPU 0, first thread of its core).
inline void print_topology_json() {
    unsigned long long l1d = 0, l2 = 0, l3 = 0;
    int logical = 0, cores = 0, smt = 0, max_class = 0, hybrid = 0, suggested = -1;
    std::string pcore_list;
#if defined(_WIN32)
    DWORD len = 0;
    GetLogicalProcessorInformationEx(RelationAll, nullptr, &len);
    char *buf = (char *)std::malloc(len);
    if (buf && GetLogicalProcessorInformationEx(RelationAll, (PSYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX)buf, &len)) {
        // pass 1: caches + highest efficiency class
        for (DWORD off = 0; off < len;) {
            auto *p = (PSYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX)(buf + off);
            if (p->Relationship == RelationCache) {
                const CACHE_RELATIONSHIP &cr = p->Cache;
                if (cr.Level == 1 && cr.Type == CacheData && !l1d) l1d = cr.CacheSize;
                if (cr.Level == 2 && !l2) l2 = cr.CacheSize;
                if (cr.Level == 3 && cr.CacheSize > l3) l3 = cr.CacheSize;
            } else if (p->Relationship == RelationProcessorCore) {
                if (efficiency_class(p->Processor) > max_class) max_class = efficiency_class(p->Processor);
            }
            off += p->Size;
        }
        // pass 2: cores, logical CPUs, SMT, list of CPUs on top-class cores
        for (DWORD off = 0; off < len;) {
            auto *p = (PSYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX)(buf + off);
            if (p->Relationship == RelationProcessorCore) {
                cores++;
                if (p->Processor.Flags & LTP_PC_SMT) smt = 1;
                if (efficiency_class(p->Processor) != max_class) hybrid = 1;
                KAFFINITY m = p->Processor.GroupMask[0].Mask;
                int first = -1;
                for (int b = 0; b < 64; b++)
                    if (m & ((KAFFINITY)1 << b)) {
                        logical++;
                        if (first < 0) first = b;
                    }
                if (efficiency_class(p->Processor) == max_class && first >= 0) {
                    if (!pcore_list.empty()) pcore_list += ",";
                    pcore_list += std::to_string(first);
                    if (first != 0) suggested = first; // keep the highest-numbered top-class core
                }
            }
            off += p->Size;
        }
    }
    std::free(buf);
    if (max_class == 0) hybrid = 0;
#else
    auto rd = [](const char *path) -> unsigned long long {
        FILE *f = std::fopen(path, "r");
        if (!f) return 0;
        char s[64] = {0};
        unsigned long long v = 0;
        if (std::fgets(s, sizeof s, f)) {
            char *end = nullptr;
            v = std::strtoull(s, &end, 10);
            if (end && (*end == 'K' || *end == 'k')) v *= 1024;
            if (end && (*end == 'M' || *end == 'm')) v *= 1024 * 1024;
        }
        std::fclose(f);
        return v;
    };
    char path[256];
    for (int i = 0; i < 8; i++) {
        std::snprintf(path, sizeof path, "/sys/devices/system/cpu/cpu0/cache/index%d/level", i);
        unsigned long long lvl = rd(path);
        if (!lvl) continue;
        std::snprintf(path, sizeof path, "/sys/devices/system/cpu/cpu0/cache/index%d/type", i);
        FILE *f = std::fopen(path, "r");
        char type[32] = {0};
        if (f) { if (!std::fgets(type, sizeof type, f)) type[0] = 0; std::fclose(f); }
        std::snprintf(path, sizeof path, "/sys/devices/system/cpu/cpu0/cache/index%d/size", i);
        unsigned long long sz = rd(path);
        if (lvl == 1 && type[0] == 'D') l1d = sz;
        if (lvl == 2) l2 = sz;
        if (lvl == 3) l3 = sz;
    }
    (void)max_class;
    logical = (int)sysconf(_SC_NPROCESSORS_ONLN);
    unsigned long long active = rd("/sys/devices/system/cpu/smt/active");
    smt = (int)active;
    cores = smt ? logical / 2 : logical;
    suggested = logical > 1 ? logical - 1 : 0;
#endif
    std::printf("{\"cpu_brand\": \"%s\", \"logical_cpus\": %d, \"physical_cores\": %d, \"smt\": %d, "
                "\"hybrid\": %d, \"top_class_cpus\": \"%s\", \"suggested_cpu\": %d, "
                "\"caches\": {\"L1d\": %llu, \"L2\": %llu, \"L3\": %llu}, "
                "\"timer\": \"%s\", \"timer_resolution_ns\": %.3f}\n",
                cpu_brand().c_str(), logical, cores, smt, hybrid, pcore_list.c_str(), suggested, l1d, l2, l3,
                timer_name(), timer_resolution_ns());
}

} // namespace plat
