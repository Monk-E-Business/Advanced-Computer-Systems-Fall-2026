// platform.hpp - the only place that differs between Windows (MSYS2/MinGW-w64)
// and Linux: timing, CPU pinning, page-size-aware allocation, huge-page
// verification, privileges and CPU topology.
#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

constexpr size_t LINE_BYTES = 64;
constexpr size_t HUGE_2M = 2UL * 1024 * 1024;

#if defined(_WIN32)
#define CMP_WINDOWS 1
#else
#define CMP_WINDOWS 0
#endif

// 4k     : normal pages (on Linux THP is explicitly disabled for the buffer)
// thp    : Linux transparent huge pages via madvise(MADV_HUGEPAGE)
// hugetlb: Linux hugetlbfs (MAP_HUGETLB), needs reserved pages
// large  : Windows large pages (VirtualAlloc MEM_LARGE_PAGES), needs the
//          "Lock pages in memory" privilege.
// parse_pages() maps any huge-page name to the variant this OS supports, so
// scripts can say "--pages large" (or thp) on both systems.
enum class PageMode { k4K, THP, HugeTLB, Large };

bool parse_pages(const std::string &s, PageMode &out);
const char *pages_name(PageMode m);

struct Buffer {
    void *map = nullptr;   // base returned by the OS
    size_t maplen = 0;
    char *p = nullptr;     // 2 MB aligned usable pointer
    size_t len = 0;        // usable length requested
    PageMode mode = PageMode::k4K;
};

// Allocates len bytes, 2 MB aligned. If prefault, every byte is written once
// so page faults are never timed. Returns 0 on success.
// fallback=true: if huge/large pages cannot be had, warn and use 4 KB pages
// instead of failing (b.mode keeps the requested mode; buffer_huge_kb() shows
// what was really mapped). Used for load-generator / bandwidth buffers only;
// latency and kernel buffers fail so a mislabelled measurement is never made.
int buffer_alloc(Buffer &b, size_t len, PageMode mode, bool prefault, bool fallback = false);
void buffer_free(Buffer &b);
// kB of the buffer actually backed by huge/large pages (-1 if unknown).
// Linux: /proc/self/smaps. Windows: QueryWorkingSetEx.
long buffer_huge_kb(const Buffer &b);

// Windows: switch stdout/stderr to binary mode so CSV lines end in "\n", not
// "\r\n" (a stray \r breaks every comparison in the bash scripts).
void stdio_binary();

double now_ns();
int pin_self(int cpu);       // cpu < 0 => leave affinity alone; 0 on success
int current_cpu();
int num_cpus();
bool is_admin();
// Environment variable CMP_PRIORITY=high raises the process priority (Windows:
// HIGH_PRIORITY_CLASS) - the closest Windows has to an isolated core.
void maybe_raise_priority();
std::string os_name();

// Large-page support (Windows): enable SeLockMemoryPrivilege in this process.
// Returns empty string on success, otherwise a human-readable reason.
std::string enable_large_pages();
// Grant SeLockMemoryPrivilege to the current user (Windows, needs admin).
std::string grant_lock_pages_right();

struct CpuInfo {
    int cpu;        // logical CPU index used by --cpu / --cpus
    int core;       // physical core id (SMT siblings share it)
    int package;
    int node;       // NUMA node
    int eff_class;  // 0 = slowest core type; higher = faster (hybrid CPUs)
};
std::vector<CpuInfo> cpu_topology();

struct CacheInfo {
    int level;
    std::string type;   // Data, Instruction, Unified
    size_t size;
    int ways;
    int line;
    std::string shared; // "0-1,8-9"
};
std::vector<CacheInfo> cpu_caches(int cpu);

std::string cpu_brand();
std::string cpu_vendor();
double tsc_ghz();     // invariant TSC rate ~ nominal/base clock (x86)
std::string cpu_list_string(const std::vector<int> &cpus);
