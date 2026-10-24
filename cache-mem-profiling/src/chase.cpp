// chase.cpp - see chase.hpp
#include "chase.hpp"

#include <vector>

bool parse_chase_pat(const std::string &s, ChasePat &out) {
    if (s == "seq") out = ChasePat::Seq;
    else if (s == "rand") out = ChasePat::Rand;
    else if (s == "page") out = ChasePat::Page;
    else return false;
    return true;
}

const char *chase_pat_name(ChasePat p) {
    switch (p) {
    case ChasePat::Seq: return "seq";
    case ChasePat::Rand: return "rand";
    case ChasePat::Page: return "page";
    }
    return "?";
}

static inline size_t node_off(size_t idx, size_t unit, bool page_mode, size_t page) {
    size_t off = idx * unit;
    if (page_mode) {
        // deterministic pseudo-random line inside the page: spreads nodes over
        // cache sets so the TLB test is not also a set-conflict test
        uint64_t h = (uint64_t)idx * 0x9E3779B97F4A7C15ULL;
        h ^= h >> 29;
        off += (size_t)(h % (page / LINE_BYTES)) * LINE_BYTES;
    }
    return off;
}

size_t chain_build(char *buf, size_t len, ChasePat pat, size_t stride, size_t page, uint64_t seed, void **start) {
    bool page_mode = (pat == ChasePat::Page);
    size_t unit = page_mode ? page : stride;
    if (unit < sizeof(void *) || (page_mode && page < LINE_BYTES)) return 0;
    size_t n = len / unit;
    if (n < 2 || n > 0xFFFFFFFFULL) return 0;

    std::vector<uint32_t> perm(n);
    for (size_t i = 0; i < n; i++) perm[i] = (uint32_t)i;
    if (pat != ChasePat::Seq) {  // Fisher-Yates shuffle of the visiting order
        uint64_t s = seed ? seed : 0x9E3779B97F4A7C15ULL;
        for (size_t i = n - 1; i > 0; i--) {
            size_t j = (size_t)(xorshift64(s) % (i + 1));
            std::swap(perm[i], perm[j]);
        }
    }
    // Linking perm[i] -> perm[i+1] (mod n) yields ONE cycle through all nodes.
    for (size_t i = 0; i < n; i++) {
        char *a = buf + node_off(perm[i], unit, page_mode, page);
        char *b = buf + node_off(perm[(i + 1) % n], unit, page_mode, page);
        *(void **)a = b;
    }
    *start = buf + node_off(perm[0], unit, page_mode, page);
    return n;
}

int chain_walk(void *start, size_t nodes, const char *buf, size_t len, int k, void **pos) {
    void *p = start;
    int next = 0;
    for (size_t i = 0; i < nodes; i++) {
        while (k > 0 && next < k && i == (size_t)((double)nodes * next / k)) pos[next++] = p;
        p = *(void **)p;
        if ((const char *)p < buf || (const char *)p >= buf + len) return -1;
        // First return to start exactly at `nodes` hops proves all visited
        // nodes are distinct (functional graph).
        if (p == start && i + 1 < nodes) return -2;
    }
    return (p == start) ? 0 : -3;
}

template <int K>
static void chase_k(void **st, uint64_t hops) {
    void *p[K];
    for (int j = 0; j < K; j++) p[j] = st[j];
    for (uint64_t i = 0; i < hops; i += 4) {
        for (int j = 0; j < K; j++) p[j] = *(void **)p[j];
        for (int j = 0; j < K; j++) p[j] = *(void **)p[j];
        for (int j = 0; j < K; j++) p[j] = *(void **)p[j];
        for (int j = 0; j < K; j++) p[j] = *(void **)p[j];
    }
    for (int j = 0; j < K; j++) st[j] = p[j];
}

bool chase_k_supported(int k) {
    switch (k) {
    case 1: case 2: case 3: case 4: case 5: case 6: case 7: case 8:
    case 10: case 12: case 14: case 16: case 20: case 24: case 28: case 32:
        return true;
    default:
        return false;
    }
}

uint64_t chase_run(void **pos, int k, uint64_t hops) {
    hops = (hops + 3) & ~(uint64_t)3;
    switch (k) {
    case 1: chase_k<1>(pos, hops); break;
    case 2: chase_k<2>(pos, hops); break;
    case 3: chase_k<3>(pos, hops); break;
    case 4: chase_k<4>(pos, hops); break;
    case 5: chase_k<5>(pos, hops); break;
    case 6: chase_k<6>(pos, hops); break;
    case 7: chase_k<7>(pos, hops); break;
    case 8: chase_k<8>(pos, hops); break;
    case 10: chase_k<10>(pos, hops); break;
    case 12: chase_k<12>(pos, hops); break;
    case 14: chase_k<14>(pos, hops); break;
    case 16: chase_k<16>(pos, hops); break;
    case 20: chase_k<20>(pos, hops); break;
    case 24: chase_k<24>(pos, hops); break;
    case 28: chase_k<28>(pos, hops); break;
    case 32: chase_k<32>(pos, hops); break;
    default: return 0;
    }
    return hops;
}
