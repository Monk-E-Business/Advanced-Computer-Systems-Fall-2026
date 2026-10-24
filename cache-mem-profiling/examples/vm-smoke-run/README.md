# Example output: QUICK smoke run on a Linux cloud VM (NOT results for the report)

Produced while developing the suite: G++ build, 2-vCPU KVM guest (Intel Xeon, no PMU exposed),
`QUICK=1 MAX_WSS=512M CHASE_DRAM=512M DRAM_SIZE=256M`, 2 repetitions per point, so the 95% CIs
are wide and a shared host adds noise. It shows what each figure and `summary.md` look like.
Your Windows/AMD run will differ: large pages instead of THP, uProf counters, AMD cache sizes.

Things it happens to show:
- **An honest anomaly the sanity checks caught:** the VM reports a 33 MiB L3, but latency is
  already at DRAM level by ~6 MiB (fig1). The guest does not really get that L3 (it is shared
  with other tenants), so the "L1<L2<LLC<DRAM" check FAILs with LLC ≈ DRAM. On real hardware,
  an L3 plateau appears between L2 and DRAM.
- Prefetchers hiding latency for sequential strides (fig2), useful vs. moved bytes for sparse
  access (fig3), the knee of the loaded-latency curve (fig6).
- Counter panels are empty because the VM hides the PMU.
