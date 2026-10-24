// chase.hpp - pointer-chasing chains for latency and memory-level-parallelism tests.
#pragma once

#include "common.hpp"

enum class ChasePat {
    Seq,   // node i -> node i+1, nodes `stride` bytes apart (prefetcher-friendly)
    Rand,  // random single cycle over all nodes (defeats prefetchers)
    Page   // one node per page at a random line offset, random page order (TLB)
};

bool parse_chase_pat(const std::string &s, ChasePat &out);
const char *chase_pat_name(ChasePat p);

// Writes a closed pointer chain into buf. Returns the node count (0 on error);
// *start = first node.
size_t chain_build(char *buf, size_t len, ChasePat pat, size_t stride, size_t page, uint64_t seed, void **start);

// Walks the whole chain once (warm-up + validation): one cycle of exactly
// `nodes` distinct nodes inside buf. If k > 0, fills pos[0..k-1] with nodes
// evenly spaced along the cycle (start points of k independent chains).
// Returns 0 if valid.
int chain_walk(void *start, size_t nodes, const char *buf, size_t len, int k, void **pos);

// Advances k independent chains by `hops` dependent loads each. Returns hops
// actually done per chain (rounded up to 4), 0 if k unsupported.
uint64_t chase_run(void **pos, int k, uint64_t hops);
bool chase_k_supported(int k);
