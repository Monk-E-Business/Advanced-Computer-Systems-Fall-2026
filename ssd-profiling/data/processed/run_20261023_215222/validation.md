# Validation — run_20261023_215222

Summary: {'PASS': 104, 'FAIL': 17, 'expected-fail': 10, 'WARN': 2}

## V1 integrity (crc32c verify)

| item          | value   | expected   | status   |
|:--------------|:--------|:-----------|:---------|
| verify_crc32c | error=0 | error=0    | PASS     |

## V2 fio vs reference (QD1)

| item                           | value                                                      | expected    | status   |
|:-------------------------------|:-----------------------------------------------------------|:------------|:---------|
| randread 4k rep1 [windowsaio]  | lat 73.3 vs 73.6 us (-0.4%); IOPS 13509 vs 13581 (-0.5%)   | within ±10% | PASS     |
| randwrite 4k rep1 [windowsaio] | lat 27.5 vs 23.6 us (+16.6%); IOPS 35156 vs 42257 (-16.8%) | within ±20% | PASS     |
| read 128k rep1 [windowsaio]    | lat 175.1 vs 213.5 us (-18.0%); IOPS 5682 vs 4681 (+21.4%) | within ±10% | WARN     |
| write 128k rep1 [windowsaio]   | lat 73.4 vs 76.9 us (-4.6%); IOPS 12715 vs 12992 (-2.1%)   | within ±20% | PASS     |

## V3 dd unbuffered seq read

| item          | value                            | expected    | status   |
|:--------------|:---------------------------------|:------------|:---------|
| read 128k QD1 | fio 745 vs dd 1510 MB/s (-50.7%) | within ±15% | FAIL     |

## V4 Little's law

41 of 63 runs PASS; non-passing rows:

| item                                     | value                            | expected    | status        |
|:-----------------------------------------|:---------------------------------|:------------|:--------------|
| bs_sweep/randread_4k rep1                | IOPS×W = 18.65 vs QD 32 (-42%)   | within ±15% | FAIL          |
| bs_sweep/randwrite_4k rep1               | IOPS×W = 16.95 vs QD 32 (-47%)   | within ±15% | FAIL          |
| bs_sweep/read_4k rep1                    | IOPS×W = 18.24 vs QD 32 (-43%)   | within ±15% | FAIL          |
| bs_sweep/write_4k rep1                   | IOPS×W = 16.87 vs QD 32 (-47%)   | within ±15% | FAIL          |
| misleading/B1_sync_iodepth32 rep1        | IOPS×W = 0.98 vs QD 32 (-97%)    | within ±15% | expected-fail |
| misleading/B2_async_iodepth32 rep1       | IOPS×W = 25.56 vs QD 32 (-20%)   | within ±15% | expected-fail |
| misleading/B3_async_iodepth32_nj4 rep1   | IOPS×W = 82.39 vs QD 32 (+157%)  | within ±15% | expected-fail |
| misleading/C_unwritten_read rep1         | IOPS×W = 16.72 vs QD 32 (-48%)   | within ±15% | expected-fail |
| misleading/C_written_read rep1           | IOPS×W = 19.14 vs QD 32 (-40%)   | within ±15% | expected-fail |
| mix_sweep/r0_4k rep1                     | IOPS×W = 17.97 vs QD 32 (-44%)   | within ±15% | FAIL          |
| mix_sweep/r100_4k rep1                   | IOPS×W = 18.62 vs QD 32 (-42%)   | within ±15% | FAIL          |
| mix_sweep/r50_4k rep1                    | IOPS×W = 17.90 vs QD 32 (-44%)   | within ±15% | FAIL          |
| peak/randread_4k_peak rep1               | IOPS×W = 144.75 vs QD 256 (-43%) | within ±15% | FAIL          |
| peak/randwrite_4k_peak rep1              | IOPS×W = 79.57 vs QD 128 (-38%)  | within ±15% | FAIL          |
| qd_sweep/randread_4k_nj1_qd16 rep1       | IOPS×W = 10.70 vs QD 16 (-33%)   | within ±15% | FAIL          |
| qd_sweep/randread_4k_nj1_qd64 rep1       | IOPS×W = 34.53 vs QD 64 (-46%)   | within ±15% | FAIL          |
| qd_sweep/randread_4k_nj4_qd64 rep1       | IOPS×W = 41.21 vs QD 64 (-36%)   | within ±15% | FAIL          |
| qd_sweep/randwrite_4k_nj4_qd16 rep1      | IOPS×W = 12.32 vs QD 16 (-23%)   | within ±15% | WARN          |
| qd_sweep/randwrite_4k_nj4_qd64 rep1      | IOPS×W = 43.00 vs QD 64 (-33%)   | within ±15% | FAIL          |
| working_set/randread_4k_ws256M_qd32 rep1 | IOPS×W = 19.15 vs QD 32 (-40%)   | within ±15% | FAIL          |
| working_set/randread_4k_ws64M_qd32 rep1  | IOPS×W = 18.58 vs QD 32 (-42%)   | within ±15% | FAIL          |
| working_set/randread_4k_wsFULL_qd32 rep1 | IOPS×W = 18.99 vs QD 32 (-41%)   | within ±15% | FAIL          |

## V5 device bytes (OS counters)

58 of 63 runs PASS; non-passing rows:

| item                                 | value                   | expected   | status        |
|:-------------------------------------|:------------------------|:-----------|:--------------|
| misleading/A_buffered_read_cold rep1 | device/fio bytes = 0.12 | 0.90–1.30  | expected-fail |
| misleading/A_buffered_read_warm rep1 | device/fio bytes = 0.00 | 0.90–1.30  | expected-fail |
| misleading/A_buffered_write rep1     | device/fio bytes = 0.00 | 0.90–1.30  | expected-fail |
| misleading/C_unwritten_read rep1     | device/fio bytes = 0.00 | 0.90–1.30  | expected-fail |
| misleading/D_unwritten_write rep1    | device/fio bytes = 5.00 | 0.90–1.30  | expected-fail |

## V6 interface ceiling

| item              | value                       | expected   | status   |
|:------------------|:----------------------------|:-----------|:---------|
| bs_sweep/read_64k | 3.70 GB/s vs link 3.94 GB/s | ≤ ceiling  | PASS     |

