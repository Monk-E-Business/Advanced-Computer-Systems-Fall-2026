// ref_qd1.cpp - minimal, independent reference implementation of a QD=1
// storage latency benchmark, used to cross-check fio. Built with g++.
//
// No fio code and no async engine: one thread, unbuffered I/O, exactly one
// read or write outstanding at a time, each timed with std::chrono::steady_clock
// (QueryPerformanceCounter on Windows). If fio's QD=1 numbers disagree with
// this by more than a few percent, something in the fio setup is wrong.
//
//   Windows: CreateFile(FILE_FLAG_NO_BUFFERING) + ReadFile/WriteFile with an
//            OVERLAPPED offset on a synchronous handle (positional I/O).
//            This matches fio's direct=1 (no FILE_FLAG_WRITE_THROUGH either).
//   Linux:   open(O_DIRECT) + pread/pwrite.
//
// usage: ref_qd1 <path> <randread|randwrite|read|write> <bs_bytes> <span_bytes>
//                <seconds> [offset_bytes] [cpu]
// Prints one JSON object: IOPS, MB/s and latency percentiles in microseconds.

#include <algorithm>
#include <chrono>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#else
#include <cerrno>
#include <fcntl.h>
#include <sched.h>
#include <unistd.h>
#endif

namespace {

using Clock = std::chrono::steady_clock;

struct Rng {  // xorshift64*: fast, good enough for offsets and payload
  uint64_t s;
  uint64_t next() {
    uint64_t x = s;
    x ^= x >> 12; x ^= x << 25; x ^= x >> 27;
    s = x;
    return x * 0x2545F4914F6CDD1DULL;
  }
};

// Page-aligned buffer (unbuffered I/O requires sector-aligned memory).
class AlignedBuffer {
 public:
  explicit AlignedBuffer(size_t n) : n_(n) {
#ifdef _WIN32
    p_ = VirtualAlloc(nullptr, n, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
#else
    if (posix_memalign(&p_, 4096, n) != 0) p_ = nullptr;
#endif
  }
  ~AlignedBuffer() {
#ifdef _WIN32
    if (p_) VirtualFree(p_, 0, MEM_RELEASE);
#else
    free(p_);
#endif
  }
  AlignedBuffer(const AlignedBuffer&) = delete;
  AlignedBuffer& operator=(const AlignedBuffer&) = delete;
  void* data() const { return p_; }
  uint64_t* words() const { return static_cast<uint64_t*>(p_); }
  size_t size() const { return n_; }

 private:
  void* p_ = nullptr;
  size_t n_;
};

class DirectFile {
 public:
  DirectFile(const std::string& path, bool write) {
#ifdef _WIN32
    DWORD access = write ? (GENERIC_READ | GENERIC_WRITE) : GENERIC_READ;
    h_ = CreateFileA(path.c_str(), access, FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr,
                     OPEN_EXISTING, FILE_FLAG_NO_BUFFERING, nullptr);
    if (h_ == INVALID_HANDLE_VALUE) err_ = "CreateFile failed, error " + std::to_string(GetLastError());
#else
    fd_ = open(path.c_str(), (write ? O_WRONLY : O_RDONLY) | O_DIRECT);
    if (fd_ < 0) err_ = std::string("open: ") + strerror(errno);
#endif
  }
  ~DirectFile() {
#ifdef _WIN32
    if (h_ != INVALID_HANDLE_VALUE) CloseHandle(h_);
#else
    if (fd_ >= 0) close(fd_);
#endif
  }
  DirectFile(const DirectFile&) = delete;
  DirectFile& operator=(const DirectFile&) = delete;

  bool ok() const { return err_.empty(); }
  const std::string& error() const { return err_; }

  // Synchronous positional I/O. Returns bytes transferred, or -1.
  long long io(void* buf, size_t len, uint64_t off, bool write) {
#ifdef _WIN32
    OVERLAPPED ov{};
    ov.Offset = static_cast<DWORD>(off & 0xFFFFFFFFu);
    ov.OffsetHigh = static_cast<DWORD>(off >> 32);
    DWORD n = 0;
    BOOL r = write ? WriteFile(h_, buf, static_cast<DWORD>(len), &n, &ov)
                   : ReadFile(h_, buf, static_cast<DWORD>(len), &n, &ov);
    if (!r) { err_ = "I/O error " + std::to_string(GetLastError()); return -1; }
    return n;
#else
    ssize_t r = write ? pwrite(fd_, buf, len, static_cast<off_t>(off))
                      : pread(fd_, buf, len, static_cast<off_t>(off));
    if (r < 0) { err_ = std::string("I/O: ") + strerror(errno); return -1; }
    return r;
#endif
  }

 private:
  std::string err_;
#ifdef _WIN32
  HANDLE h_ = INVALID_HANDLE_VALUE;
#else
  int fd_ = -1;
#endif
};

void pin_to_cpu(int cpu) {
  if (cpu < 0) return;
#ifdef _WIN32
  SetThreadAffinityMask(GetCurrentThread(), DWORD_PTR(1) << cpu);
#else
  cpu_set_t set;
  CPU_ZERO(&set);
  CPU_SET(cpu, &set);
  sched_setaffinity(0, sizeof(set), &set);
#endif
}

// Nearest-rank percentile on sorted data (fio uses binned values; close enough).
double pct(const std::vector<double>& sorted, double p) {
  size_t idx = static_cast<size_t>(p / 100.0 * static_cast<double>(sorted.size()));
  if (idx >= sorted.size()) idx = sorted.size() - 1;
  return sorted[idx];
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 6) {
    std::fprintf(stderr,
                 "usage: %s <path> <randread|randwrite|read|write> <bs> <span> <seconds> [offset] [cpu]\n",
                 argv[0]);
    return 2;
  }
  const std::string path = argv[1], mode = argv[2];
  const size_t bs = std::strtoull(argv[3], nullptr, 10);
  const uint64_t span = std::strtoull(argv[4], nullptr, 10);
  const double seconds = std::atof(argv[5]);
  const uint64_t base = argc > 6 ? std::strtoull(argv[6], nullptr, 10) : 0;
  const int cpu = argc > 7 ? std::atoi(argv[7]) : -1;
  const bool is_write = mode.find("write") != std::string::npos;
  const bool is_rand = mode.rfind("rand", 0) == 0;
  if (bs == 0 || bs % 4096 != 0 || span < bs) {
    std::fprintf(stderr, "bad bs/span\n");
    return 2;
  }
  pin_to_cpu(cpu);

  DirectFile f(path, is_write);
  if (!f.ok()) { std::fprintf(stderr, "%s: %s\n", path.c_str(), f.error().c_str()); return 1; }
  AlignedBuffer buf(bs);
  if (!buf.data()) { std::fprintf(stderr, "buffer allocation failed\n"); return 1; }

  Rng rng{static_cast<uint64_t>(Clock::now().time_since_epoch().count()) | 1};
  for (size_t i = 0; i < bs / 8; ++i) buf.words()[i] = rng.next();  // incompressible payload

  const uint64_t nblocks = span / bs;
  std::vector<double> lat_us;
  lat_us.reserve(1u << 20);
  uint64_t seq_blk = 0, bytes = 0;
  const auto t_start = Clock::now();
  const auto t_end = t_start + std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double>(seconds));
  auto t = t_start;
  while (t < t_end) {
    const uint64_t blk = is_rand ? rng.next() % nblocks : (seq_blk++ % nblocks);
    const uint64_t off = base + blk * bs;
    if (is_write) buf.words()[0] = rng.next();  // keep every write unique
    const auto t0 = Clock::now();
    const long long r = f.io(buf.data(), bs, off, is_write);
    t = Clock::now();
    if (r != static_cast<long long>(bs)) {
      std::fprintf(stderr, "short/failed I/O at offset %" PRIu64 ": %lld (%s)\n", off, r, f.error().c_str());
      return 1;
    }
    lat_us.push_back(std::chrono::duration<double, std::micro>(t - t0).count());
    bytes += bs;
  }
  const double elapsed = std::chrono::duration<double>(t - t_start).count();
  double sum = 0;
  for (double v : lat_us) sum += v;
  std::sort(lat_us.begin(), lat_us.end());
  const size_t n = lat_us.size();
  std::printf(
      "{\"tool\": \"ref_qd1\", \"mode\": \"%s\", \"bs\": %zu, \"span\": %" PRIu64 ", \"ios\": %zu, "
      "\"elapsed_s\": %.3f, \"iops\": %.1f, \"MBps\": %.2f, \"lat_mean_us\": %.3f, \"lat_p50_us\": %.3f, "
      "\"lat_p95_us\": %.3f, \"lat_p99_us\": %.3f, \"lat_p999_us\": %.3f, \"lat_max_us\": %.3f}\n",
      mode.c_str(), bs, span, n, elapsed, n / elapsed, bytes / elapsed / 1e6, sum / n, pct(lat_us, 50),
      pct(lat_us, 95), pct(lat_us, 99), pct(lat_us, 99.9), lat_us.back());
  return 0;
}
