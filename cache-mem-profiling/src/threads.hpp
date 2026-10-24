// threads.hpp - a reusable barrier (portable: std::mutex + condition_variable).
#pragma once

#include <condition_variable>
#include <cstddef>
#include <mutex>

class Barrier {
  public:
    explicit Barrier(size_t n) : n_(n), count_(n) {}
    void wait() {
        std::unique_lock<std::mutex> lk(m_);
        size_t gen = gen_;
        if (--count_ == 0) {
            gen_++;
            count_ = n_;
            cv_.notify_all();
        } else {
            cv_.wait(lk, [&] { return gen != gen_; });
        }
    }

  private:
    std::mutex m_;
    std::condition_variable cv_;
    size_t n_, count_, gen_ = 0;
};
