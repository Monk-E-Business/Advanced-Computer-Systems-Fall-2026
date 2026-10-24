// bwkern.hpp - per-thread bandwidth / load-generator kernel.
#pragma once

#include "common.hpp"

enum class BwPat {
    Seq,     // contiguous sweep
    Stride,  // `gran` bytes every `stride` bytes
    Rand     // `gran` bytes at a random gran-aligned slot each access
};

struct BwCfg {
    size_t size = 0;      // bytes per thread
    BwPat pat = BwPat::Seq;
    size_t gran = 64;     // bytes touched per access (multiple of 8)
    size_t stride = 256;  // distance between access starts (Stride)
    int read_pct = 100;   // 100 = all reads, 0 = all writes, 70, 50, ...
    bool nt = false;      // non-temporal (streaming) stores for writes
    unsigned delay = 0;   // empty-loop iterations injected after each access
    PageMode pages = PageMode::k4K;
    bool init = true;     // false => skip first-touch init (pitfall experiment)
    uint64_t seed = 42;
};

struct BwState {
    const BwCfg *cfg = nullptr;
    Buffer buf;
    size_t pos = 0;
    uint64_t rng = 1;
    uint64_t acc = 0;
    size_t slot_mask = 0;
    int mixi = 0, period = 10;
    uint8_t mixpat[100] = {};
};

bool parse_bw_pat(const std::string &s, BwPat &out);
const char *bw_pat_name(BwPat p);

// Allocate + first-touch the thread's buffer. Call AFTER pinning so pages land
// on the local NUMA node (first-touch placement on both Linux and Windows).
int bw_state_init(BwState &s, const BwCfg &cfg, int tid);
void bw_state_free(BwState &s);

// Perform `accesses` accesses; returns bytes demanded (accesses * gran).
uint64_t bw_chunk(BwState &s, uint64_t accesses);
uint64_t bw_chunk_size(const BwCfg &cfg);              // ~256 KB of work per chunk
double bw_line_bytes_per_access(const BwCfg &cfg);     // whole-line traffic per access

// Correctness self-test of every code path against closed-form answers.
int bw_selftest();
