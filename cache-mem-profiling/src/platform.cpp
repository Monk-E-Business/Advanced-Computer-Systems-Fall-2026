// platform.cpp - see platform.hpp
#include "platform.hpp"

#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <set>
#include <thread>

#if defined(__x86_64__) || defined(__i386__)
#include <cpuid.h>
#include <x86intrin.h>
#define CMP_X86 1
#else
#define CMP_X86 0
#endif

#if CMP_WINDOWS
#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0A00
#endif
#include <windows.h>
#include <fcntl.h>
#include <io.h>
#include <psapi.h>
#include <ntsecapi.h>
#else
#include <cerrno>
#include <dirent.h>
#include <sched.h>
#include <sys/mman.h>
#include <unistd.h>
#endif

void stdio_binary() {
#if CMP_WINDOWS
    _setmode(_fileno(stdout), _O_BINARY);
    _setmode(_fileno(stderr), _O_BINARY);
#endif
}

double now_ns() {
    using namespace std::chrono;
    return (double)duration_cast<nanoseconds>(steady_clock::now().time_since_epoch()).count();
}

bool parse_pages(const std::string &s, PageMode &out) {
    if (s == "4k" || s == "4K") { out = PageMode::k4K; return true; }
    bool huge = (s == "thp" || s == "THP" || s == "large" || s == "hugetlb" || s == "2m" || s == "2M");
    if (!huge) return false;
#if CMP_WINDOWS
    out = PageMode::Large;
#else
    out = (s == "hugetlb" || s == "2m" || s == "2M") ? PageMode::HugeTLB : PageMode::THP;
#endif
    return true;
}

const char *pages_name(PageMode m) {
    switch (m) {
    case PageMode::k4K: return "4k";
    case PageMode::THP: return "thp";
    case PageMode::HugeTLB: return "hugetlb";
    case PageMode::Large: return "large";
    }
    return "?";
}

std::string cpu_list_string(const std::vector<int> &v0) {
    std::vector<int> v = v0;
    std::sort(v.begin(), v.end());
    std::string s;
    for (size_t i = 0; i < v.size();) {
        size_t j = i;
        while (j + 1 < v.size() && v[j + 1] == v[j] + 1) j++;
        if (!s.empty()) s += ",";
        s += std::to_string(v[i]);
        if (j > i) s += "-" + std::to_string(v[j]);
        i = j + 1;
    }
    return s;
}

// ---------------------------------------------------------------- CPU id ---
std::string cpu_vendor() {
#if CMP_X86
    unsigned a, b, c, d;
    if (!__get_cpuid(0, &a, &b, &c, &d)) return "unknown";
    char v[13];
    std::memcpy(v, &b, 4);
    std::memcpy(v + 4, &d, 4);
    std::memcpy(v + 8, &c, 4);
    v[12] = 0;
    return v;
#else
    return "unknown";
#endif
}

std::string cpu_brand() {
#if CMP_X86
    unsigned r[12];
    if (!__get_cpuid(0x80000004, &r[0], &r[1], &r[2], &r[3])) return "unknown";
    for (unsigned i = 0; i < 3; i++) __get_cpuid(0x80000002 + i, &r[4 * i], &r[4 * i + 1], &r[4 * i + 2], &r[4 * i + 3]);
    char s[49];
    std::memcpy(s, r, 48);
    s[48] = 0;
    std::string out = s;
    out.erase(0, out.find_first_not_of(' '));
    while (!out.empty() && (out.back() == ' ' || out.back() == '\0')) out.pop_back();
    return out;
#else
    return "unknown";
#endif
}

double tsc_ghz() {
#if CMP_X86
    double best = 0;
    for (int r = 0; r < 3; r++) {
        double t0 = now_ns();
        unsigned long long c0 = __rdtsc();
        while (now_ns() - t0 < 50e6) {}
        unsigned long long c1 = __rdtsc();
        double t1 = now_ns();
        double g = (double)(c1 - c0) / (t1 - t0);
        if (g > best) best = g;
    }
    return best;
#else
    return 0.0;
#endif
}

#if CMP_WINDOWS
// =========================================================== Windows ======
namespace {

struct GroupMap {
    std::vector<int> offset;  // first logical index of each processor group
    int total = 0;
    GroupMap() {
        WORD groups = GetActiveProcessorGroupCount();
        for (WORD g = 0; g < groups; g++) {
            offset.push_back(total);
            total += (int)GetActiveProcessorCount(g);
        }
    }
    bool locate(int cpu, WORD &group, int &bit) const {
        for (size_t g = 0; g < offset.size(); g++) {
            int n = (g + 1 < offset.size() ? offset[g + 1] : total) - offset[g];
            if (cpu >= offset[g] && cpu < offset[g] + n) {
                group = (WORD)g;
                bit = cpu - offset[g];
                return true;
            }
        }
        return false;
    }
    int index(WORD group, int bit) const { return group < offset.size() ? offset[group] + bit : -1; }
};

const GroupMap &groups() {
    static GroupMap m;
    return m;
}

std::vector<int> mask_cpus(const GROUP_AFFINITY &ga) {
    std::vector<int> v;
    for (int b = 0; b < 64; b++)
        if (ga.Mask & ((KAFFINITY)1 << b)) v.push_back(groups().index(ga.Group, b));
    return v;
}

std::string last_error_text(DWORD e) {
    char buf[512] = {0};
    FormatMessageA(FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS, nullptr, e, 0, buf, sizeof buf, nullptr);
    std::string s = buf;
    while (!s.empty() && (s.back() == '\n' || s.back() == '\r' || s.back() == '.')) s.pop_back();
    return s + " (error " + std::to_string(e) + ")";
}

std::vector<char> lpi(LOGICAL_PROCESSOR_RELATIONSHIP rel) {
    DWORD len = 0;
    GetLogicalProcessorInformationEx(rel, nullptr, &len);
    std::vector<char> buf(len);
    if (!len || !GetLogicalProcessorInformationEx(rel, (PSYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX)buf.data(), &len))
        buf.clear();
    return buf;
}

template <class F>
void for_each_lpi(LOGICAL_PROCESSOR_RELATIONSHIP rel, F f) {
    std::vector<char> buf = lpi(rel);
    for (size_t off = 0; off < buf.size();) {
        auto *e = (PSYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX)(buf.data() + off);
        if (e->Size == 0) break;
        f(e);
        off += e->Size;
    }
}

}  // namespace

int num_cpus() { return groups().total; }

int pin_self(int cpu) {
    if (cpu < 0) return 0;
    WORD g;
    int bit;
    if (!groups().locate(cpu, g, bit)) {
        std::fprintf(stderr, "warning: cpu %d does not exist (have %d)\n", cpu, groups().total);
        return -1;
    }
    GROUP_AFFINITY ga;
    std::memset(&ga, 0, sizeof ga);
    ga.Group = g;
    ga.Mask = (KAFFINITY)1 << bit;
    if (!SetThreadGroupAffinity(GetCurrentThread(), &ga, nullptr)) {
        std::fprintf(stderr, "warning: cannot pin to cpu %d: %s\n", cpu, last_error_text(GetLastError()).c_str());
        return -1;
    }
    PROCESSOR_NUMBER pn;
    pn.Group = g;
    pn.Number = (BYTE)bit;
    pn.Reserved = 0;
    SetThreadIdealProcessorEx(GetCurrentThread(), &pn, nullptr);
    SwitchToThread();  // let the scheduler migrate us now, not mid-measurement
    return 0;
}

int current_cpu() {
    PROCESSOR_NUMBER pn;
    GetCurrentProcessorNumberEx(&pn);
    return groups().index(pn.Group, pn.Number);
}

bool is_admin() {
    HANDLE tok;
    if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &tok)) return false;
    TOKEN_ELEVATION el;
    DWORD len = 0;
    bool r = GetTokenInformation(tok, TokenElevation, &el, sizeof el, &len) && el.TokenIsElevated;
    CloseHandle(tok);
    return r;
}

void maybe_raise_priority() {
    const char *p = std::getenv("CMP_PRIORITY");
    if (p && std::string(p) == "high") SetPriorityClass(GetCurrentProcess(), HIGH_PRIORITY_CLASS);
}

std::string os_name() {
    // RtlGetVersion is not affected by manifest-based version lies
    typedef LONG(WINAPI * RtlGetVersionFn)(PRTL_OSVERSIONINFOW);
    RTL_OSVERSIONINFOW v;
    std::memset(&v, 0, sizeof v);
    v.dwOSVersionInfoSize = sizeof v;
    HMODULE ntdll = GetModuleHandleA("ntdll.dll");
    auto fn = ntdll ? (RtlGetVersionFn)(void *)GetProcAddress(ntdll, "RtlGetVersion") : nullptr;
    if (fn) fn(&v);
    return "Windows " + std::to_string(v.dwMajorVersion) + "." + std::to_string(v.dwMinorVersion) + " build " +
           std::to_string(v.dwBuildNumber);
}

std::string enable_large_pages() {
    static int state = -1;  // -1 untried, 0 failed, 1 ok
    static std::string reason;
    if (state >= 0) return reason;
    HANDLE tok;
    if (!OpenProcessToken(GetCurrentProcess(), TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY, &tok)) {
        reason = "OpenProcessToken failed: " + last_error_text(GetLastError());
        state = 0;
        return reason;
    }
    TOKEN_PRIVILEGES tp;
    tp.PrivilegeCount = 1;
    tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED;
    LookupPrivilegeValueA(nullptr, "SeLockMemoryPrivilege", &tp.Privileges[0].Luid);
    BOOL ok = AdjustTokenPrivileges(tok, FALSE, &tp, 0, nullptr, nullptr);
    DWORD e = GetLastError();
    CloseHandle(tok);
    if (!ok || e == ERROR_NOT_ALL_ASSIGNED) {
        reason = "this account does not hold the 'Lock pages in memory' privilege. Run "
                 "'bin/sysinfo --grant-lock-pages' in an administrator MSYS2 terminal, then sign out and back "
                 "in (and use an administrator terminal for the experiments)";
        state = 0;
    } else if (GetLargePageMinimum() == 0) {
        reason = "the CPU/OS reports no large-page support";
        state = 0;
    } else {
        reason.clear();
        state = 1;
    }
    return reason;
}

std::string grant_lock_pages_right() {
    if (!is_admin()) return "must be run from an administrator terminal (right-click MSYS2 UCRT64 > Run as administrator)";
    HANDLE tok;
    if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &tok)) return "OpenProcessToken failed";
    DWORD len = 0;
    GetTokenInformation(tok, TokenUser, nullptr, 0, &len);
    std::vector<char> ub(len);
    if (!GetTokenInformation(tok, TokenUser, ub.data(), len, &len)) {
        CloseHandle(tok);
        return "GetTokenInformation(TokenUser) failed";
    }
    CloseHandle(tok);
    PSID sid = ((TOKEN_USER *)ub.data())->User.Sid;
    LSA_OBJECT_ATTRIBUTES oa;
    std::memset(&oa, 0, sizeof oa);
    LSA_HANDLE pol;
    NTSTATUS st = LsaOpenPolicy(nullptr, &oa, POLICY_CREATE_ACCOUNT | POLICY_LOOKUP_NAMES, &pol);
    if (st) return "LsaOpenPolicy failed: " + last_error_text(LsaNtStatusToWinError(st));
    wchar_t name[] = L"SeLockMemoryPrivilege";
    LSA_UNICODE_STRING right;
    right.Buffer = name;
    right.Length = (USHORT)(wcslen(name) * sizeof(wchar_t));
    right.MaximumLength = right.Length + sizeof(wchar_t);
    st = LsaAddAccountRights(pol, sid, &right, 1);
    LsaClose(pol);
    if (st) return "LsaAddAccountRights failed: " + last_error_text(LsaNtStatusToWinError(st));
    return "";
}

static int alloc_4k(Buffer &b, size_t len) {
    size_t rlen = (len + HUGE_2M - 1) & ~(HUGE_2M - 1);
    size_t mlen = rlen + HUGE_2M;
    void *m = VirtualAlloc(nullptr, mlen, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    if (!m) {
        std::fprintf(stderr, "error: VirtualAlloc(%zu bytes) failed: %s\n", mlen,
                     last_error_text(GetLastError()).c_str());
        return -1;
    }
    uintptr_t a = ((uintptr_t)m + HUGE_2M - 1) & ~(uintptr_t)(HUGE_2M - 1);
    b.map = m;
    b.maplen = mlen;
    b.p = (char *)a;
    b.len = len;
    return 0;
}

int buffer_alloc(Buffer &b, size_t len, PageMode mode, bool prefault, bool fallback) {
    b = Buffer();
    b.mode = mode;
    if (mode != PageMode::k4K) {
        b.mode = PageMode::Large;
        std::string why = enable_large_pages();
        void *m = nullptr;
        size_t rlen = 0;
        if (why.empty()) {
            size_t lpm = GetLargePageMinimum();
            rlen = (len + lpm - 1) / lpm * lpm;
            m = VirtualAlloc(nullptr, rlen, MEM_RESERVE | MEM_COMMIT | MEM_LARGE_PAGES, PAGE_READWRITE);
            if (!m) why = "VirtualAlloc(MEM_LARGE_PAGES, " + std::to_string(rlen) + " bytes) failed: " +
                          last_error_text(GetLastError());
        } else {
            why = "large pages unavailable: " + why;
        }
        if (!m) {
            if (fallback) {
                std::fprintf(stderr, "warning: %s\n         using 4 KB pages for this buffer instead (huge_kb=0 in the output)\n",
                             why.c_str());
                if (alloc_4k(b, len)) return -1;
            } else {
                std::fprintf(stderr, "error: %s\n", why.c_str());
                if (why.compare(0, 12, "VirtualAlloc") == 0)
                    std::fprintf(stderr,
                                 "       Large pages need physically contiguous free memory: reboot, close other programs,\n"
                                 "       and run the large-page experiments early, or reduce the sizes.\n");
                return -1;
            }
        } else {
            b.map = m;
            b.maplen = rlen;
            b.p = (char *)m;
            b.len = len;
        }
    } else if (alloc_4k(b, len)) {
        return -1;
    }
    if (prefault) std::memset(b.p, 0, len);
    return 0;
}

void buffer_free(Buffer &b) {
    if (b.map) VirtualFree(b.map, 0, MEM_RELEASE);
    b = Buffer();
}

long buffer_huge_kb(const Buffer &b) {
    // Sample one entry per 2 MB; each sample stands for 2 MB of the buffer.
    size_t n = (b.len + HUGE_2M - 1) / HUGE_2M;
    if (!n) return 0;
    std::vector<PSAPI_WORKING_SET_EX_INFORMATION> w(n);
    for (size_t i = 0; i < n; i++) w[i].VirtualAddress = b.p + i * HUGE_2M;
    if (!QueryWorkingSetEx(GetCurrentProcess(), w.data(), (DWORD)(n * sizeof(w[0])))) return -1;
    long kb = 0;
    for (size_t i = 0; i < n; i++)
        if (w[i].VirtualAttributes.Valid && w[i].VirtualAttributes.LargePage) kb += (long)(HUGE_2M / 1024);
    return kb;
}

std::vector<CpuInfo> cpu_topology() {
    std::vector<CpuInfo> v(num_cpus());
    for (int i = 0; i < (int)v.size(); i++) v[i] = {i, -1, 0, 0, 0};
    int core = 0;
    for_each_lpi(RelationProcessorCore, [&](PSYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX e) {
        // EfficiencyClass is the byte after Flags; read it by offset so this
        // also compiles against older MinGW headers that call it Reserved.
        int eff = reinterpret_cast<const BYTE *>(&e->Processor.Flags)[1];
        for (int g = 0; g < e->Processor.GroupCount; g++)
            for (int c : mask_cpus(e->Processor.GroupMask[g]))
                if (c >= 0 && c < (int)v.size()) {
                    v[c].core = core;
                    v[c].eff_class = eff;
                }
        core++;
    });
    int pkg = 0;
    for_each_lpi(RelationProcessorPackage, [&](PSYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX e) {
        for (int g = 0; g < e->Processor.GroupCount; g++)
            for (int c : mask_cpus(e->Processor.GroupMask[g]))
                if (c >= 0 && c < (int)v.size()) v[c].package = pkg;
        pkg++;
    });
    for_each_lpi(RelationNumaNode, [&](PSYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX e) {
        for (int c : mask_cpus(e->NumaNode.GroupMask))
            if (c >= 0 && c < (int)v.size()) v[c].node = (int)e->NumaNode.NodeNumber;
    });
    return v;
}

std::vector<CacheInfo> cpu_caches(int cpu) {
    std::vector<CacheInfo> out;
    WORD g;
    int bit;
    if (!groups().locate(cpu, g, bit)) return out;
    for_each_lpi(RelationCache, [&](PSYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX e) {
        const CACHE_RELATIONSHIP &c = e->Cache;
        if (c.GroupMask.Group != g || !(c.GroupMask.Mask & ((KAFFINITY)1 << bit))) return;
        const char *t = c.Type == CacheData ? "Data" : c.Type == CacheInstruction ? "Instruction"
                      : c.Type == CacheUnified ? "Unified" : "Trace";
        out.push_back({(int)c.Level, t, (size_t)c.CacheSize, (int)c.Associativity, (int)c.LineSize,
                       cpu_list_string(mask_cpus(c.GroupMask))});
    });
    std::sort(out.begin(), out.end(), [](const CacheInfo &a, const CacheInfo &b) {
        return a.level != b.level ? a.level < b.level : a.type < b.type;
    });
    return out;
}

#else
// ============================================================= Linux ======
int num_cpus() { return (int)sysconf(_SC_NPROCESSORS_ONLN); }

int pin_self(int cpu) {
    if (cpu < 0) return 0;
    cpu_set_t set;
    CPU_ZERO(&set);
    CPU_SET(cpu, &set);
    if (sched_setaffinity(0, sizeof set, &set) != 0) {
        std::fprintf(stderr, "warning: cannot pin to cpu %d: %s\n", cpu, std::strerror(errno));
        return -1;
    }
    return 0;
}

int current_cpu() { return sched_getcpu(); }
bool is_admin() { return geteuid() == 0; }
void maybe_raise_priority() {}

std::string os_name() {
    FILE *f = std::fopen("/proc/sys/kernel/osrelease", "r");
    char buf[128] = "?";
    if (f) {
        if (!std::fgets(buf, sizeof buf, f)) std::strcpy(buf, "?");
        std::fclose(f);
    }
    std::string s = buf;
    while (!s.empty() && s.back() == '\n') s.pop_back();
    return "Linux " + s;
}

std::string enable_large_pages() { return ""; }
std::string grant_lock_pages_right() { return "only needed on Windows"; }

int buffer_alloc(Buffer &b, size_t len, PageMode mode, bool prefault, bool fallback) {
    b = Buffer();
    if (mode == PageMode::Large) mode = PageMode::THP;
    b.mode = mode;
    size_t rlen = (len + HUGE_2M - 1) & ~(HUGE_2M - 1);
    void *hm = MAP_FAILED;
    if (mode == PageMode::HugeTLB) {
        int flags = MAP_PRIVATE | MAP_ANONYMOUS | MAP_HUGETLB;
#ifdef MAP_HUGE_2MB
        flags |= MAP_HUGE_2MB;
#endif
        hm = mmap(nullptr, rlen, PROT_READ | PROT_WRITE, flags, -1, 0);
        if (hm == MAP_FAILED && fallback)
            std::fprintf(stderr, "warning: MAP_HUGETLB mmap of %zu bytes failed (%s); using 4 KB pages instead\n",
                         rlen, std::strerror(errno));
    }
    if (mode == PageMode::HugeTLB && (hm != MAP_FAILED || !fallback)) {
        void *m = hm;
        if (m == MAP_FAILED) {
            std::fprintf(stderr,
                         "error: MAP_HUGETLB mmap of %zu bytes failed (%s).\n"
                         "       Reserve pages first, e.g. echo 1024 | sudo tee /proc/sys/vm/nr_hugepages\n",
                         rlen, std::strerror(errno));
            return -1;
        }
        b.map = m;
        b.maplen = rlen;
        b.p = (char *)m;
        b.len = len;
    } else {
        size_t mlen = rlen + HUGE_2M;
        void *m = mmap(nullptr, mlen, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        if (m == MAP_FAILED) {
            std::fprintf(stderr, "error: mmap of %zu bytes failed: %s\n", mlen, std::strerror(errno));
            return -1;
        }
        uintptr_t a = ((uintptr_t)m + HUGE_2M - 1) & ~(uintptr_t)(HUGE_2M - 1);
        b.map = m;
        b.maplen = mlen;
        b.p = (char *)a;
        b.len = len;
#if defined(MADV_HUGEPAGE) && defined(MADV_NOHUGEPAGE)
        // Without MADV_NOHUGEPAGE, THP=always would silently make "4k" runs huge.
        int advice = (mode == PageMode::k4K) ? MADV_NOHUGEPAGE : MADV_HUGEPAGE;
        if (mode == PageMode::HugeTLB) advice = MADV_NOHUGEPAGE;  // hugetlb fallback: really 4 KB
        if (madvise(b.p, rlen, advice) != 0)
            std::fprintf(stderr, "warning: madvise failed: %s\n", std::strerror(errno));
#endif
    }
    if (prefault) std::memset(b.p, 0, len);
    return 0;
}

void buffer_free(Buffer &b) {
    if (b.map) munmap(b.map, b.maplen);
    b = Buffer();
}

long buffer_huge_kb(const Buffer &b) {
    FILE *f = std::fopen("/proc/self/smaps", "r");
    if (!f) return -1;
    char line[512];
    uintptr_t lo = (uintptr_t)b.p, hi = lo + b.len;
    bool inside = false;
    long total = 0;
    while (std::fgets(line, sizeof line, f)) {
        unsigned long s, e;
        if (std::sscanf(line, "%lx-%lx ", &s, &e) == 2) {
            inside = (s < hi && e > lo);
            continue;
        }
        if (!inside) continue;
        long kb;
        if (std::sscanf(line, "AnonHugePages: %ld kB", &kb) == 1) total += kb;
        else if (std::sscanf(line, "Private_Hugetlb: %ld kB", &kb) == 1) total += kb;
        else if (std::sscanf(line, "Shared_Hugetlb: %ld kB", &kb) == 1) total += kb;
    }
    std::fclose(f);
    return total;
}

namespace {
std::string read_str(const std::string &path) {
    FILE *f = std::fopen(path.c_str(), "r");
    if (!f) return "";
    char buf[4096];
    std::string s;
    if (std::fgets(buf, sizeof buf, f)) s = buf;
    std::fclose(f);
    while (!s.empty() && (s.back() == '\n' || s.back() == ' ')) s.pop_back();
    return s;
}
long read_long(const std::string &path, long def) {
    std::string s = read_str(path);
    return s.empty() ? def : std::atol(s.c_str());
}
}  // namespace

std::vector<CpuInfo> cpu_topology() {
    std::vector<CpuInfo> v;
    std::map<std::pair<int, int>, int> core_ids;
    std::set<long> freqs;
    std::vector<long> fmax;
    int n = num_cpus();
    for (int c = 0; c < n; c++) {
        std::string d = "/sys/devices/system/cpu/cpu" + std::to_string(c);
        int pkg = (int)read_long(d + "/topology/physical_package_id", 0);
        int cid = (int)read_long(d + "/topology/core_id", c);
        auto key = std::make_pair(pkg, cid);
        if (!core_ids.count(key)) core_ids[key] = (int)core_ids.size();
        int node = 0;
        if (DIR *dir = opendir(d.c_str())) {
            while (dirent *e = readdir(dir))
                if (!std::strncmp(e->d_name, "node", 4) && e->d_name[4] >= '0' && e->d_name[4] <= '9')
                    node = std::atoi(e->d_name + 4);
            closedir(dir);
        }
        long f = read_long(d + "/cpufreq/cpuinfo_max_freq", 0);
        fmax.push_back(f);
        freqs.insert(f);
        v.push_back({c, core_ids[key], pkg, node, 0});
    }
    // rank distinct max frequencies -> efficiency class (hybrid CPUs)
    std::vector<long> fl(freqs.begin(), freqs.end());
    for (auto &ci : v) ci.eff_class = (int)(std::lower_bound(fl.begin(), fl.end(), fmax[ci.cpu]) - fl.begin());
    return v;
}

std::vector<CacheInfo> cpu_caches(int cpu) {
    std::vector<CacheInfo> out;
    for (int i = 0; i < 16; i++) {
        std::string d = "/sys/devices/system/cpu/cpu" + std::to_string(cpu) + "/cache/index" + std::to_string(i);
        std::string sz = read_str(d + "/size");
        if (sz.empty()) break;
        size_t bytes = (size_t)std::atol(sz.c_str());
        char u = sz.back();
        if (u == 'K') bytes *= 1024;
        else if (u == 'M') bytes *= 1024 * 1024;
        out.push_back({(int)read_long(d + "/level", 0), read_str(d + "/type"), bytes,
                       (int)read_long(d + "/ways_of_associativity", 0), (int)read_long(d + "/coherency_line_size", 64),
                       read_str(d + "/shared_cpu_list")});
    }
    return out;
}
#endif
