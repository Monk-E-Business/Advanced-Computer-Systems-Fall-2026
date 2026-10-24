#!/usr/bin/env bash
# Exp 7 - TLB-miss impact and huge pages.
#  (a) page-stride chase: one cache line per 4 KB page, random page order,
#      16 .. TLB_MAX_PAGES pages, for 4 KB vs 2 MB pages (Windows large pages / Linux THP).
#      The number of distinct LINES is small (pages x 64 B) while the number of
#      distinct PAGES grows, isolating TLB reach from cache capacity.
#  (b) kernels at page stride (512 doubles) and unit stride, 4 KB vs huge pages:
#      huge pages should help (a) and the page-stride kernel, and NOT the
#      unit-stride kernel (the negative case).
# Outputs: data/raw/tlb.csv, data/raw/kernels_tlb.csv
source "$(dirname "$0")/lib.sh"
show_config
new_csv "$RAW/tlb.csv" "$BIN/latency"
for pages in $(page_modes); do
    np=16
    while [ "$np" -le "$TLB_MAX_PAGES" ]; do
        run_counted "$BIN/latency" --size $(( np * 4096 )) --pattern page --page-size 4096 --pages "$pages" \
            --cpu "$CPU" --reps "$REPS" --ms "$MS" --perf --label tlb
        np=$(( np * 2 ))
    done
done

new_csv "$RAW/kernels_tlb.csv" "$BIN/kernels"
for pages in $(page_modes); do
    for k in mul saxpy; do
        for st in 1 512; do
            run_counted "$BIN/kernels" --kernel "$k" --size "$KERNEL_DRAM" --order stride --stride "$st" \
                --pages "$pages" --cpu "$CPU" --reps "$REPS" --ms "$MS" --perf --label tlb_kernel
        done
        run_counted "$BIN/kernels" --kernel "$k" --size "$KERNEL_DRAM" --order rand \
            --pages "$pages" --cpu "$CPU" --reps "$REPS" --ms "$MS" --perf --label tlb_kernel
    done
done
log "exp7 done"
