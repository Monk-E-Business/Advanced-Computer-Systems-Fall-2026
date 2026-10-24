// sysinfo.cpp - portable system information for the scripts (MSYS2 has no
// lscpu or /sys). One mode per invocation:
//   --topology            CSV: cpu,core,package,node,eff_class (one row per logical CPU)
//   --caches N            CSV: level,type,size_bytes,ways,line,shared_cpu_list for CPU N
//   --brand | --vendor | --os | --tsc-ghz | --ncpus
//   --is-admin            prints 1 or 0
//   --large-pages-check   prints "ok" (exit 0) or the reason (exit 1); Windows tries a real allocation
//   --grant-lock-pages    Windows: give this user the "Lock pages in memory" right (admin terminal)
//   --summary             human-readable overview
#include <cstdio>
#include <string>

#include "common.hpp"

static const char *USAGE =
    "--topology | --caches N | --brand | --vendor | --os | --tsc-ghz | --ncpus | --is-admin |\n"
    "       --large-pages-check | --grant-lock-pages | --summary\n";

static void print_topology(FILE *f) {
    std::fprintf(f, "cpu,core,package,node,eff_class\n");
    for (const auto &c : cpu_topology()) std::fprintf(f, "%d,%d,%d,%d,%d\n", c.cpu, c.core, c.package, c.node, c.eff_class);
}

static void print_caches(FILE *f, int cpu) {
    std::fprintf(f, "level,type,size_bytes,ways,line,shared_cpu_list\n");
    for (const auto &c : cpu_caches(cpu))
        std::fprintf(f, "%d,%s,%zu,%d,%d,\"%s\"\n", c.level, c.type.c_str(), c.size, c.ways, c.line, c.shared.c_str());
}

static int large_pages_check(bool quiet) {
#if CMP_WINDOWS
    Buffer b;
    std::string why = enable_large_pages();
    if (why.empty()) {
        if (buffer_alloc(b, HUGE_2M * 4, PageMode::Large, true) == 0) {
            long kb = buffer_huge_kb(b);
            buffer_free(b);
            if (!quiet) std::printf("ok (8 MiB test allocation, %ld kB confirmed as large pages)\n", kb);
            return 0;
        }
        why = "allocation failed (see message above)";
    }
    if (!quiet) std::printf("%s\n", why.c_str());
    return 1;
#else
    FILE *f = std::fopen("/sys/kernel/mm/transparent_hugepage/enabled", "r");
    char buf[128] = "";
    if (f) {
        if (!std::fgets(buf, sizeof buf, f)) buf[0] = 0;
        std::fclose(f);
    }
    std::string s = buf;
    bool ok = s.find("[always]") != std::string::npos || s.find("[madvise]") != std::string::npos;
    if (!quiet) std::printf("%s\n", ok ? "ok (THP)" : "THP disabled");
    return ok ? 0 : 1;
#endif
}

int main(int argc, char **argv) {
    Args a(argc, argv,
           {{"topology", false}, {"caches", true}, {"brand", false}, {"vendor", false}, {"os", false},
            {"tsc-ghz", false}, {"ncpus", false}, {"is-admin", false}, {"large-pages-check", false},
            {"grant-lock-pages", false}, {"summary", false}},
           USAGE);
    if (a.has("topology")) print_topology(stdout);
    else if (a.has("caches")) print_caches(stdout, (int)a.num("caches", 0));
    else if (a.has("brand")) std::printf("%s\n", cpu_brand().c_str());
    else if (a.has("vendor")) std::printf("%s\n", cpu_vendor().c_str());
    else if (a.has("os")) std::printf("%s\n", os_name().c_str());
    else if (a.has("tsc-ghz")) std::printf("%.3f\n", tsc_ghz());
    else if (a.has("ncpus")) std::printf("%d\n", num_cpus());
    else if (a.has("is-admin")) std::printf("%d\n", is_admin() ? 1 : 0);
    else if (a.has("large-pages-check")) return large_pages_check(false);
    else if (a.has("grant-lock-pages")) {
        std::string e = grant_lock_pages_right();
        if (!e.empty()) {
            std::fprintf(stderr, "error: %s\n", e.c_str());
            return 1;
        }
        std::printf("Granted 'Lock pages in memory' to the current user.\n"
                    "Sign out of Windows and back in (or reboot) for it to take effect.\n");
    } else if (a.has("summary")) {
        auto topo = cpu_topology();
        int cores = 0, maxeff = 0;
        for (auto &c : topo) {
            if (c.core + 1 > cores) cores = c.core + 1;
            if (c.eff_class > maxeff) maxeff = c.eff_class;
        }
        std::printf("CPU:        %s (%s)\n", cpu_brand().c_str(), cpu_vendor().c_str());
        std::printf("OS:         %s\n", os_name().c_str());
        std::printf("Logical:    %d CPUs on %d physical cores (SMT %s)\n", (int)topo.size(), cores,
                    (int)topo.size() > cores ? "on" : "off/none");
        std::printf("Core types: %s\n", maxeff > 0 ? "hybrid (several efficiency classes)" : "uniform");
        std::printf("TSC rate:   %.3f GHz (~ nominal/base clock)\n", tsc_ghz());
        std::printf("Admin:      %s\n", is_admin() ? "yes" : "no");
        std::printf("Large pages: ");
        std::fflush(stdout);
        large_pages_check(false);
        std::printf("Caches of CPU 0:\n");
        for (auto &c : cpu_caches(0))
            std::printf("  L%d %-11s %8zu KiB  %2d-way  %d B lines  shared with CPUs %s\n", c.level, c.type.c_str(),
                        c.size / 1024, c.ways, c.line, c.shared.c_str());
    } else {
        a.fail();
    }
    return 0;
}
