# Validation — run_20261023_215950

Summary: {'PASS': 514, 'FAIL': 62, 'expected-fail': 29, 'WARN': 22}

## V1 integrity (crc32c verify)

| item          | value   | expected   | status   |
|:--------------|:--------|:-----------|:---------|
| verify_crc32c | error=0 | error=0    | PASS     |

## V2 fio vs reference (QD1)

| item                           | value                                                      | expected    | status   |
|:-------------------------------|:-----------------------------------------------------------|:------------|:---------|
| randread 4k rep1 [windowsaio]  | lat 95.2 vs 106.3 us (-10.5%); IOPS 10401 vs 9403 (+10.6%) | within ±10% | WARN     |
| randread 4k rep2 [windowsaio]  | lat 110.2 vs 110.0 us (+0.1%); IOPS 8994 vs 9084 (-1.0%)   | within ±10% | PASS     |
| randread 4k rep3 [windowsaio]  | lat 98.5 vs 116.4 us (-15.4%); IOPS 10054 vs 8584 (+17.1%) | within ±10% | WARN     |
| randwrite 4k rep1 [windowsaio] | lat 32.2 vs 27.1 us (+18.6%); IOPS 30018 vs 36757 (-18.3%) | within ±20% | PASS     |
| randwrite 4k rep2 [windowsaio] | lat 36.6 vs 27.3 us (+34.2%); IOPS 26447 vs 36543 (-27.6%) | within ±20% | WARN     |
| randwrite 4k rep3 [windowsaio] | lat 33.8 vs 25.8 us (+31.2%); IOPS 28638 vs 38729 (-26.1%) | within ±20% | WARN     |
| read 128k rep1 [windowsaio]    | lat 185.2 vs 206.9 us (-10.5%); IOPS 5369 vs 4832 (+11.1%) | within ±10% | WARN     |
| read 128k rep2 [windowsaio]    | lat 129.4 vs 150.7 us (-14.1%); IOPS 7671 vs 6634 (+15.6%) | within ±10% | WARN     |
| read 128k rep3 [windowsaio]    | lat 159.2 vs 155.2 us (+2.6%); IOPS 6242 vs 6443 (-3.1%)   | within ±10% | PASS     |
| write 128k rep1 [windowsaio]   | lat 176.9 vs 138.2 us (+28.0%); IOPS 5479 vs 7233 (-24.3%) | within ±20% | WARN     |
| write 128k rep2 [windowsaio]   | lat 210.8 vs 197.3 us (+6.8%); IOPS 4620 vs 5066 (-8.8%)   | within ±20% | PASS     |
| write 128k rep3 [windowsaio]   | lat 191.0 vs 157.8 us (+21.1%); IOPS 5082 vs 6334 (-19.8%) | within ±20% | WARN     |

## V3 dd unbuffered seq read

| item          | value                          | expected    | status   |
|:--------------|:-------------------------------|:------------|:---------|
| read 128k QD1 | fio 842 vs dd 881 MB/s (-4.3%) | within ±15% | PASS     |

## V4 Little's law

220 of 306 runs PASS; non-passing rows:

| item                                     | value                            | expected    | status        |
|:-----------------------------------------|:---------------------------------|:------------|:--------------|
| bs_sweep/randread_16k rep1               | IOPS×W = 26.34 vs QD 32 (-18%)   | within ±15% | WARN          |
| bs_sweep/randread_16k rep2               | IOPS×W = 26.59 vs QD 32 (-17%)   | within ±15% | WARN          |
| bs_sweep/randread_16k rep3               | IOPS×W = 26.02 vs QD 32 (-19%)   | within ±15% | WARN          |
| bs_sweep/randread_4k rep1                | IOPS×W = 20.07 vs QD 32 (-37%)   | within ±15% | FAIL          |
| bs_sweep/randread_4k rep2                | IOPS×W = 20.10 vs QD 32 (-37%)   | within ±15% | FAIL          |
| bs_sweep/randread_4k rep3                | IOPS×W = 20.10 vs QD 32 (-37%)   | within ±15% | FAIL          |
| bs_sweep/randwrite_4k rep1               | IOPS×W = 17.89 vs QD 32 (-44%)   | within ±15% | FAIL          |
| bs_sweep/randwrite_4k rep2               | IOPS×W = 20.10 vs QD 32 (-37%)   | within ±15% | FAIL          |
| bs_sweep/randwrite_4k rep3               | IOPS×W = 20.96 vs QD 32 (-35%)   | within ±15% | FAIL          |
| bs_sweep/read_16k rep1                   | IOPS×W = 22.04 vs QD 32 (-31%)   | within ±15% | FAIL          |
| bs_sweep/read_16k rep2                   | IOPS×W = 23.18 vs QD 32 (-28%)   | within ±15% | WARN          |
| bs_sweep/read_16k rep3                   | IOPS×W = 22.02 vs QD 32 (-31%)   | within ±15% | FAIL          |
| bs_sweep/read_4k rep1                    | IOPS×W = 19.27 vs QD 32 (-40%)   | within ±15% | FAIL          |
| bs_sweep/read_4k rep2                    | IOPS×W = 19.36 vs QD 32 (-40%)   | within ±15% | FAIL          |
| bs_sweep/read_4k rep3                    | IOPS×W = 19.24 vs QD 32 (-40%)   | within ±15% | FAIL          |
| bs_sweep/write_16k rep1                  | IOPS×W = 23.60 vs QD 32 (-26%)   | within ±15% | WARN          |
| bs_sweep/write_4k rep1                   | IOPS×W = 16.98 vs QD 32 (-47%)   | within ±15% | FAIL          |
| bs_sweep/write_4k rep2                   | IOPS×W = 17.12 vs QD 32 (-47%)   | within ±15% | FAIL          |
| bs_sweep/write_4k rep3                   | IOPS×W = 18.04 vs QD 32 (-44%)   | within ±15% | FAIL          |
| misleading/B1_sync_iodepth32 rep1        | IOPS×W = 0.99 vs QD 32 (-97%)    | within ±15% | expected-fail |
| misleading/B1_sync_iodepth32 rep2        | IOPS×W = 0.99 vs QD 32 (-97%)    | within ±15% | expected-fail |
| misleading/B1_sync_iodepth32 rep3        | IOPS×W = 0.99 vs QD 32 (-97%)    | within ±15% | expected-fail |
| misleading/B2_async_iodepth32 rep1       | IOPS×W = 20.49 vs QD 32 (-36%)   | within ±15% | expected-fail |
| misleading/B2_async_iodepth32 rep3       | IOPS×W = 20.05 vs QD 32 (-37%)   | within ±15% | expected-fail |
| misleading/B3_async_iodepth32_nj4 rep1   | IOPS×W = 88.39 vs QD 32 (+176%)  | within ±15% | expected-fail |
| misleading/B3_async_iodepth32_nj4 rep2   | IOPS×W = 89.47 vs QD 32 (+180%)  | within ±15% | expected-fail |
| misleading/B3_async_iodepth32_nj4 rep3   | IOPS×W = 87.61 vs QD 32 (+174%)  | within ±15% | expected-fail |
| misleading/C_unwritten_read rep1         | IOPS×W = 16.69 vs QD 32 (-48%)   | within ±15% | expected-fail |
| misleading/C_unwritten_read rep2         | IOPS×W = 16.69 vs QD 32 (-48%)   | within ±15% | expected-fail |
| misleading/C_unwritten_read rep3         | IOPS×W = 16.70 vs QD 32 (-48%)   | within ±15% | expected-fail |
| misleading/C_written_read rep1           | IOPS×W = 19.40 vs QD 32 (-39%)   | within ±15% | expected-fail |
| misleading/C_written_read rep2           | IOPS×W = 19.41 vs QD 32 (-39%)   | within ±15% | expected-fail |
| misleading/C_written_read rep3           | IOPS×W = 19.39 vs QD 32 (-39%)   | within ±15% | expected-fail |
| mix_sweep/r0_4k rep1                     | IOPS×W = 17.36 vs QD 32 (-46%)   | within ±15% | FAIL          |
| mix_sweep/r0_4k rep2                     | IOPS×W = 18.97 vs QD 32 (-41%)   | within ±15% | FAIL          |
| mix_sweep/r0_4k rep3                     | IOPS×W = 18.09 vs QD 32 (-43%)   | within ±15% | FAIL          |
| mix_sweep/r100_4k rep1                   | IOPS×W = 20.01 vs QD 32 (-37%)   | within ±15% | FAIL          |
| mix_sweep/r100_4k rep2                   | IOPS×W = 20.55 vs QD 32 (-36%)   | within ±15% | FAIL          |
| mix_sweep/r100_4k rep3                   | IOPS×W = 20.29 vs QD 32 (-37%)   | within ±15% | FAIL          |
| mix_sweep/r50_4k rep1                    | IOPS×W = 21.28 vs QD 32 (-34%)   | within ±15% | FAIL          |
| mix_sweep/r50_4k rep2                    | IOPS×W = 22.50 vs QD 32 (-30%)   | within ±15% | WARN          |
| mix_sweep/r50_4k rep3                    | IOPS×W = 22.29 vs QD 32 (-30%)   | within ±15% | FAIL          |
| mix_sweep/r70_4k rep1                    | IOPS×W = 23.12 vs QD 32 (-28%)   | within ±15% | WARN          |
| mix_sweep/r70_4k rep2                    | IOPS×W = 22.82 vs QD 32 (-29%)   | within ±15% | WARN          |
| mix_sweep/r70_4k rep3                    | IOPS×W = 20.44 vs QD 32 (-36%)   | within ±15% | FAIL          |
| peak/randread_4k_peak rep1               | IOPS×W = 156.33 vs QD 256 (-39%) | within ±15% | FAIL          |
| peak/randread_4k_peak rep2               | IOPS×W = 149.81 vs QD 256 (-41%) | within ±15% | FAIL          |
| peak/randread_4k_peak rep3               | IOPS×W = 157.78 vs QD 256 (-38%) | within ±15% | FAIL          |
| qd_sweep/randread_4k_nj1_qd128 rep1      | IOPS×W = 68.54 vs QD 128 (-46%)  | within ±15% | FAIL          |
| qd_sweep/randread_4k_nj1_qd128 rep2      | IOPS×W = 68.59 vs QD 128 (-46%)  | within ±15% | FAIL          |
| qd_sweep/randread_4k_nj1_qd128 rep3      | IOPS×W = 68.06 vs QD 128 (-47%)  | within ±15% | FAIL          |
| qd_sweep/randread_4k_nj1_qd16 rep1       | IOPS×W = 12.17 vs QD 16 (-24%)   | within ±15% | WARN          |
| qd_sweep/randread_4k_nj1_qd16 rep2       | IOPS×W = 12.43 vs QD 16 (-22%)   | within ±15% | WARN          |
| qd_sweep/randread_4k_nj1_qd16 rep3       | IOPS×W = 11.91 vs QD 16 (-26%)   | within ±15% | WARN          |
| qd_sweep/randread_4k_nj1_qd256 rep1      | IOPS×W = 131.81 vs QD 256 (-49%) | within ±15% | FAIL          |
| qd_sweep/randread_4k_nj1_qd256 rep2      | IOPS×W = 133.19 vs QD 256 (-48%) | within ±15% | FAIL          |
| qd_sweep/randread_4k_nj1_qd256 rep3      | IOPS×W = 132.86 vs QD 256 (-48%) | within ±15% | FAIL          |
| qd_sweep/randread_4k_nj1_qd32 rep1       | IOPS×W = 20.21 vs QD 32 (-37%)   | within ±15% | FAIL          |
| qd_sweep/randread_4k_nj1_qd32 rep2       | IOPS×W = 20.36 vs QD 32 (-36%)   | within ±15% | FAIL          |
| qd_sweep/randread_4k_nj1_qd32 rep3       | IOPS×W = 20.52 vs QD 32 (-36%)   | within ±15% | FAIL          |
| qd_sweep/randread_4k_nj1_qd64 rep1       | IOPS×W = 36.77 vs QD 64 (-43%)   | within ±15% | FAIL          |
| qd_sweep/randread_4k_nj1_qd64 rep2       | IOPS×W = 36.08 vs QD 64 (-44%)   | within ±15% | FAIL          |
| qd_sweep/randread_4k_nj1_qd64 rep3       | IOPS×W = 36.32 vs QD 64 (-43%)   | within ±15% | FAIL          |
| qd_sweep/randread_4k_nj4_qd128 rep1      | IOPS×W = 91.10 vs QD 128 (-29%)  | within ±15% | WARN          |
| qd_sweep/randread_4k_nj4_qd128 rep2      | IOPS×W = 86.63 vs QD 128 (-32%)  | within ±15% | FAIL          |
| qd_sweep/randread_4k_nj4_qd128 rep3      | IOPS×W = 87.00 vs QD 128 (-32%)  | within ±15% | FAIL          |
| qd_sweep/randread_4k_nj4_qd256 rep1      | IOPS×W = 156.79 vs QD 256 (-39%) | within ±15% | FAIL          |
| qd_sweep/randread_4k_nj4_qd256 rep2      | IOPS×W = 158.50 vs QD 256 (-38%) | within ±15% | FAIL          |
| qd_sweep/randread_4k_nj4_qd256 rep3      | IOPS×W = 151.15 vs QD 256 (-41%) | within ±15% | FAIL          |
| qd_sweep/randread_4k_nj4_qd64 rep1       | IOPS×W = 52.46 vs QD 64 (-18%)   | within ±15% | WARN          |
| qd_sweep/randread_4k_nj4_qd64 rep2       | IOPS×W = 53.47 vs QD 64 (-16%)   | within ±15% | WARN          |
| working_set/randread_4k_ws16G_qd32 rep1  | IOPS×W = 19.36 vs QD 32 (-39%)   | within ±15% | FAIL          |
| working_set/randread_4k_ws16G_qd32 rep2  | IOPS×W = 19.46 vs QD 32 (-39%)   | within ±15% | FAIL          |
| working_set/randread_4k_ws16G_qd32 rep3  | IOPS×W = 19.49 vs QD 32 (-39%)   | within ±15% | FAIL          |
| working_set/randread_4k_ws1G_qd32 rep1   | IOPS×W = 19.45 vs QD 32 (-39%)   | within ±15% | FAIL          |
| working_set/randread_4k_ws1G_qd32 rep2   | IOPS×W = 19.37 vs QD 32 (-39%)   | within ±15% | FAIL          |
| working_set/randread_4k_ws1G_qd32 rep3   | IOPS×W = 19.48 vs QD 32 (-39%)   | within ±15% | FAIL          |
| working_set/randread_4k_ws32G_qd32 rep1  | IOPS×W = 19.43 vs QD 32 (-39%)   | within ±15% | FAIL          |
| working_set/randread_4k_ws32G_qd32 rep2  | IOPS×W = 19.43 vs QD 32 (-39%)   | within ±15% | FAIL          |
| working_set/randread_4k_ws32G_qd32 rep3  | IOPS×W = 19.39 vs QD 32 (-39%)   | within ±15% | FAIL          |
| working_set/randread_4k_ws4G_qd32 rep1   | IOPS×W = 19.45 vs QD 32 (-39%)   | within ±15% | FAIL          |
| working_set/randread_4k_ws4G_qd32 rep2   | IOPS×W = 19.37 vs QD 32 (-39%)   | within ±15% | FAIL          |
| working_set/randread_4k_ws4G_qd32 rep3   | IOPS×W = 19.48 vs QD 32 (-39%)   | within ±15% | FAIL          |
| working_set/randread_4k_wsFULL_qd32 rep1 | IOPS×W = 20.54 vs QD 32 (-36%)   | within ±15% | FAIL          |
| working_set/randread_4k_wsFULL_qd32 rep2 | IOPS×W = 20.05 vs QD 32 (-37%)   | within ±15% | FAIL          |
| working_set/randread_4k_wsFULL_qd32 rep3 | IOPS×W = 20.12 vs QD 32 (-37%)   | within ±15% | FAIL          |

## V5 device bytes (OS counters)

287 of 306 runs PASS; non-passing rows:

| item                                 | value                    | expected   | status        |
|:-------------------------------------|:-------------------------|:-----------|:--------------|
| baseline_qd1/write_128k rep1         | device/fio bytes = 1.52  | 0.90–1.51  | FAIL          |
| baseline_qd1/write_128k rep2         | device/fio bytes = 1.59  | 0.90–1.51  | FAIL          |
| bs_sweep/write_32k rep3              | device/fio bytes = 1.90  | 0.90–1.51  | FAIL          |
| bs_sweep/write_512k rep3             | device/fio bytes = 1.52  | 0.90–1.51  | FAIL          |
| misleading/A_buffered_read_cold rep1 | device/fio bytes = 0.15  | 0.90–1.51  | expected-fail |
| misleading/A_buffered_read_cold rep2 | device/fio bytes = 0.15  | 0.90–1.51  | expected-fail |
| misleading/A_buffered_read_cold rep3 | device/fio bytes = 0.15  | 0.90–1.51  | expected-fail |
| misleading/A_buffered_read_warm rep1 | device/fio bytes = 0.00  | 0.90–1.51  | expected-fail |
| misleading/A_buffered_read_warm rep2 | device/fio bytes = 0.00  | 0.90–1.51  | expected-fail |
| misleading/A_buffered_read_warm rep3 | device/fio bytes = 0.00  | 0.90–1.51  | expected-fail |
| misleading/A_buffered_write rep1     | device/fio bytes = 0.11  | 0.90–1.51  | expected-fail |
| misleading/A_buffered_write rep2     | device/fio bytes = 0.11  | 0.90–1.51  | expected-fail |
| misleading/A_buffered_write rep3     | device/fio bytes = 0.10  | 0.90–1.51  | expected-fail |
| misleading/C_unwritten_read rep1     | device/fio bytes = 0.00  | 0.90–1.51  | expected-fail |
| misleading/C_unwritten_read rep2     | device/fio bytes = 0.00  | 0.90–1.51  | expected-fail |
| misleading/C_unwritten_read rep3     | device/fio bytes = 0.00  | 0.90–1.51  | expected-fail |
| misleading/D_unwritten_write rep1    | device/fio bytes = 64.98 | 0.90–1.30  | expected-fail |
| misleading/D_unwritten_write rep2    | device/fio bytes = 65.00 | 0.90–1.30  | expected-fail |
| misleading/D_unwritten_write rep3    | device/fio bytes = 64.96 | 0.90–1.30  | expected-fail |

## V6 interface ceiling

| item               | value                       | expected   | status   |
|:-------------------|:----------------------------|:-----------|:---------|
| bs_sweep/read_512k | 2.49 GB/s vs link 3.94 GB/s | ≤ ceiling  | PASS     |

