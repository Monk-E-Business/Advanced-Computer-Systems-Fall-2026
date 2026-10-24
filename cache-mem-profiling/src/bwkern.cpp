// bwkern.cpp - see bwkern.hpp
#include "bwkern.hpp"

#include <atomic>
#include <cstring>

#if defined(__x86_64__)
#include <immintrin.h>
#endif

static inline void nt_store(uint64_t *p, uint64_t v) {
#if defined(__x86_64__)
    _mm_stream_si64((long long *)p, (long long)v);
#else
    *p = v;
#endif
}

bool parse_bw_pat(const std::string &s, BwPat &out) {
    if (s == "seq") out = BwPat::Seq;
    else if (s == "stride") out = BwPat::Stride;
    else if (s == "rand") out = BwPat::Rand;
    else return false;
    return true;
}

const char *bw_pat_name(BwPat p) {
    switch (p) {
    case BwPat::Seq: return "seq";
    case BwPat::Stride: return "stride";
    case BwPat::Rand: return "rand";
    }
    return "?";
}

// Hot loops. Four accumulators / varying store values keep the compiler from
// turning the write loop into memset (memset switches to non-temporal stores
// for large sizes, which would silently change what is measured).
static uint64_t sum_words(const uint64_t *p, size_t nw) {
    uint64_t a0 = 0, a1 = 0, a2 = 0, a3 = 0;
    size_t i = 0;
    for (; i + 4 <= nw; i += 4) {
        a0 += p[i];
        a1 += p[i + 1];
        a2 += p[i + 2];
        a3 += p[i + 3];
    }
    for (; i < nw; i++) a0 += p[i];
    return a0 + a1 + a2 + a3;
}

static void store_words(uint64_t *p, size_t nw, uint64_t v) {
    for (size_t i = 0; i < nw; i++) p[i] = v + i;
}

static void store_words_nt(uint64_t *p, size_t nw, uint64_t v) {
    for (size_t i = 0; i < nw; i++) nt_store(&p[i], v + i);
}

typedef uint64_t v4u __attribute__((vector_size(32), aligned(32)));

static inline void store_fence() { std::atomic_thread_fence(std::memory_order_seq_cst); }

int bw_state_init(BwState &s, const BwCfg &c, int tid) {
    s = BwState();
    s.cfg = &c;
    if (c.gran < 8 || c.gran % 8) {
        std::fprintf(stderr, "error: --gran must be a multiple of 8\n");
        return -1;
    }
    if (buffer_alloc(s.buf, c.size, c.pages, false, /*fallback=*/true)) return -1;
    if (c.init) {  // first touch from the owning (pinned) thread
        uint64_t *w = (uint64_t *)s.buf.p;
        size_t nw = c.size / 8;
        for (size_t i = 0; i < nw; i++) w[i] = i;
    }
    s.rng = (c.seed ? c.seed : 88172645463325252ULL) ^ ((uint64_t)(tid + 1) * 0x9E3779B97F4A7C15ULL);
    if (!s.rng) s.rng = 1;
    size_t slots = c.size / c.gran, p2 = 1;
    while (p2 * 2 <= slots) p2 *= 2;
    s.slot_mask = p2 - 1;
    // Within each period all reads come first, then all writes. A period of 10
    // (multiples of 10%) is short enough for the branch predictor to learn.
    s.period = (c.read_pct % 10 == 0) ? 10 : 100;
    int reads = c.read_pct * s.period / 100;
    for (int i = 0; i < s.period; i++) s.mixpat[i] = (i >= reads);
    return 0;
}

void bw_state_free(BwState &s) { buffer_free(s.buf); }

uint64_t bw_chunk_size(const BwCfg &c) {
    uint64_t n = (256 * 1024) / c.gran;
    if (c.pat != BwPat::Seq && n > 8192) n = 8192;
    if (c.delay) n = n / (1 + c.delay / 16);
    return n < 16 ? 16 : n;
}

double bw_line_bytes_per_access(const BwCfg &c) {
    size_t g_lines = ((c.gran + LINE_BYTES - 1) / LINE_BYTES) * LINE_BYTES;
    switch (c.pat) {
    case BwPat::Seq: return (double)c.gran;
    case BwPat::Stride: return c.stride < LINE_BYTES ? (double)c.stride : (double)g_lines;
    case BwPat::Rand: return (double)g_lines;
    }
    return (double)c.gran;
}

// Generic loop for strided / random / mixed / throttled traffic. State is
// copied into locals: the buffer and s.acc are both uint64_t, so otherwise the
// compiler must assume every store may alias the accumulator.
template <bool G64, bool DELAY>
static void generic_loop(BwState &s, uint64_t accesses) {
    const BwCfg &c = *s.cfg;
    char *base = s.buf.p;
    const size_t len = c.size, gran = c.gran, nw = gran / 8;
    const size_t step = (c.pat == BwPat::Seq) ? gran : c.stride;
    const bool rnd = (c.pat == BwPat::Rand), nt = c.nt;
    const int period = s.period;
    const size_t mask = s.slot_mask;
    const unsigned delay = c.delay;
    size_t pos = s.pos;
    uint64_t rng = s.rng, acc = s.acc;
    int mixi = s.mixi;
    v4u vacc = {0, 0, 0, 0};
    const v4u four = {4, 4, 4, 4};
    for (uint64_t a = 0; a < accesses; a++) {
        size_t off;
        if (rnd) {
            off = (size_t)(xorshift64(rng) & mask) * gran;
        } else {
            if (pos + gran > len) pos = 0;
            off = pos;
            pos += step;
        }
        uint64_t *p = (uint64_t *)(base + off);
        if (s.mixpat[mixi]) {
            uint64_t v = acc + a;
            if (G64 && !nt) {
                v4u lo = {v, v + 1, v + 2, v + 3};
                ((v4u *)p)[0] = lo;
                ((v4u *)p)[1] = lo + four;
            } else if (nt) {
                store_words_nt(p, nw, v);
            } else {
                store_words(p, nw, v);
            }
        } else {
            if (G64) vacc += ((const v4u *)p)[0] + ((const v4u *)p)[1];
            else acc += sum_words(p, nw);
        }
        if (++mixi == period) mixi = 0;
        if (DELAY)
            for (unsigned d = 0; d < delay; d++) __asm__ volatile("");
    }
    s.pos = pos;
    s.rng = rng;
    s.acc = acc + vacc[0] + vacc[1] + vacc[2] + vacc[3];
    s.mixi = mixi;
}

uint64_t bw_chunk(BwState &s, uint64_t accesses) {
    const BwCfg &c = *s.cfg;
    char *base = s.buf.p;
    size_t len = c.size;

    // Fast path: pure sequential read or write sweep.
    if (c.pat == BwPat::Seq && c.delay == 0 && (c.read_pct == 100 || c.read_pct == 0)) {
        uint64_t bytes = accesses * c.gran, done = 0;
        while (done < bytes) {
            size_t room = len - s.pos;
            size_t take = (bytes - done) < room ? (size_t)(bytes - done) : room;
            take &= ~(size_t)7;
            if (!take) {
                s.pos = 0;
                continue;
            }
            uint64_t *p = (uint64_t *)(base + s.pos);
            if (c.read_pct == 100) s.acc += sum_words(p, take / 8);
            else if (c.nt) store_words_nt(p, take / 8, s.acc++);
            else store_words(p, take / 8, s.acc++);
            s.pos += take;
            if (s.pos + 8 > len) s.pos = 0;
            done += take;
        }
        if (c.nt && c.read_pct == 0) store_fence();
        return bytes;
    }

    bool g64 = (c.gran == 64);
    if (c.delay == 0) g64 ? generic_loop<true, false>(s, accesses) : generic_loop<false, false>(s, accesses);
    else g64 ? generic_loop<true, true>(s, accesses) : generic_loop<false, true>(s, accesses);
    if (c.nt && c.read_pct < 100) store_fence();
    return accesses * c.gran;
}

// ---- self test ---------------------------------------------------------------
static int check(const char *what, bool ok) {
    std::fprintf(stderr, "  bw selftest %-50s %s\n", what, ok ? "OK" : "FAIL");
    return ok ? 0 : 1;
}

int bw_selftest() {
    int fails = 0;
    BwCfg c;
    c.size = 1 << 20;
    c.seed = 1;
    BwState s;
    uint64_t nw = c.size / 8, expect = nw * (nw - 1) / 2;  // sum of w[i] = i

    bw_state_init(s, c, 0);  // 1. fast sequential read path
    bw_chunk(s, c.size / c.gran);
    fails += check("seq read sum == n(n-1)/2 (fast path)", s.acc == expect);
    bw_state_free(s);

    c.delay = 1;  // 2. generic path reads the same bytes
    bw_state_init(s, c, 0);
    bw_chunk(s, c.size / c.gran);
    fails += check("seq read sum == n(n-1)/2 (generic path)", s.acc == expect);
    bw_state_free(s);
    c.delay = 0;

    c.pat = BwPat::Stride;  // 3. stride path touches one word every stride bytes
    c.gran = 8;
    c.stride = 256;
    bw_state_init(s, c, 0);
    uint64_t n_acc = c.size / c.stride, e3 = 0;
    for (uint64_t i = 0; i < n_acc; i++) e3 += i * (c.stride / 8);
    bw_chunk(s, n_acc);
    fails += check("stride-256 read sum matches closed form", s.acc == e3);
    bw_state_free(s);

    c.pat = BwPat::Seq;  // 4. write path
    c.gran = 64;
    c.read_pct = 0;
    bw_state_init(s, c, 0);
    bw_chunk(s, c.size / c.gran);
    uint64_t *w = (uint64_t *)s.buf.p;
    bool ok = true;
    for (uint64_t i = 0; i < nw; i++)
        if (w[i] != i) { ok = false; break; }
    fails += check("seq write stores expected values", ok);
    bw_state_free(s);

    c.nt = true;  // 5. non-temporal write path
    bw_state_init(s, c, 0);
    bw_chunk(s, c.size / c.gran);
    w = (uint64_t *)s.buf.p;
    ok = true;
    for (uint64_t i = 0; i < nw; i++)
        if (w[i] != i) { ok = false; break; }
    fails += check("non-temporal write stores expected values", ok);
    bw_state_free(s);
    c.nt = false;

    const int mixes[] = {70, 50};  // 6. read/write mixes are exact
    for (int m : mixes) {
        c.read_pct = m;
        c.pat = BwPat::Seq;
        bw_state_init(s, c, 0);
        int writes = 0;
        for (int i = 0; i < s.period; i++) writes += s.mixpat[i];
        char name[96];
        std::snprintf(name, sizeof name, "mix %d/%d write fraction exact", m, 100 - m);
        fails += check(name, writes * 100 == (100 - m) * s.period);
        bw_state_free(s);
        c.pat = BwPat::Stride;
        c.gran = 64;
        c.stride = 64;
        bw_state_init(s, c, 0);
        uint64_t *w0 = (uint64_t *)s.buf.p;
        bw_chunk(s, 1000);
        int changed = 0;
        for (int blk = 0; blk < 1000; blk++) changed += (w0[blk * 8 + 1] != (uint64_t)(blk * 8 + 1));
        std::snprintf(name, sizeof name, "mix %d/%d generic path writes %d of 1000 blocks", m, 100 - m, (100 - m) * 10);
        fails += check(name, changed == (100 - m) * 10);
        bw_state_free(s);
    }

    c.pat = BwPat::Rand;  // 7. random slots in bounds and aligned
    c.read_pct = 100;
    c.gran = 256;
    bw_state_init(s, c, 0);
    ok = true;
    uint64_t r = s.rng;
    for (int i = 0; i < 100000; i++) {
        size_t off = (size_t)(xorshift64(r) & s.slot_mask) * c.gran;
        if (off + c.gran > c.size || off % c.gran) { ok = false; break; }
    }
    fails += check("random offsets in bounds and aligned", ok);
    bw_state_free(s);
    return fails;
}
