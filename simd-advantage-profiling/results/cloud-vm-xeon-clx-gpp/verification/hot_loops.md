# Hot-loop excerpts (targeted disassembly)

Inner loop only (backward-branch body with the most packed work), truncated to 24 lines.

## `saxpy_f32` — `scalar`

```asm
    40: movss          (%rsi,%rax,4),%xmm1
    45: mulss          %xmm0,%xmm1
    49: addss          (%rdx,%rax,4),%xmm1
    4e: movss          %xmm1,(%rdx,%rax,4)
    53: add            $0x1,%rax
    57: cmp            %rax,%rdi
    5a: jne            40 <saxpy_f32+0x40>
```

## `saxpy_f32` — `scalar_native`

```asm
    40: vmovss         (%rsi,%rax,4),%xmm1
    45: vfmadd213ss    (%rdx,%rax,4),%xmm0,%xmm1
    4b: vmovss         %xmm1,(%rdx,%rax,4)
    50: inc            %rax
    53: cmp            %rax,%rdi
    56: jne            40 <saxpy_f32+0x40>
```

## `saxpy_f32` — `sse2`

```asm
    40: movups         (%rcx,%rax,1),%xmm1
    44: movups         (%rdx,%rax,1),%xmm3
    48: mulps          %xmm2,%xmm1
    4b: addps          %xmm3,%xmm1
    4e: movups         %xmm1,(%rdx,%rax,1)
    52: add            $0x10,%rax
    56: cmp            %rsi,%rax
    59: jne            40 <saxpy_f32+0x40>
```

## `saxpy_f32` — `avx2`

```asm
    40: vmovups        (%rcx,%rax,1),%ymm1
    45: vfmadd213ps    (%rdx,%rax,1),%ymm2,%ymm1
    4b: vmovups        %ymm1,(%rdx,%rax,1)
    50: add            $0x20,%rax
    54: cmp            %rsi,%rax
    57: jne            40 <saxpy_f32+0x40>
```

## `saxpy_f32` — `native`

```asm
    40: vmovups        (%r8,%rax,1),%ymm1
    46: vfmadd213ps    (%rdx,%rax,1),%ymm2,%ymm1
    4c: vmovups        %ymm1,(%rdx,%rax,1)
    51: add            $0x20,%rax
    55: cmp            %rsi,%rax
    58: jne            40 <saxpy_f32+0x40>
```

## `saxpy_f32` — `avx512`

```asm
    40: vmovups        (%rcx,%rax,1),%zmm1
    47: vfmadd213ps    (%rdx,%rax,1),%zmm2,%zmm1
    4e: vmovups        %zmm1,(%rdx,%rax,1)
    55: add            $0x40,%rax
    59: cmp            %rsi,%rax
    5c: jne            40 <saxpy_f32+0x40>
```

## `dot_f32` — `scalar`

```asm
    c0: movss          (%rsi,%rax,4),%xmm0
    c5: mulss          (%rdx,%rax,4),%xmm0
    ca: add            $0x1,%rax
    ce: addss          %xmm0,%xmm1
    d2: cmp            %rax,%rdi
    d5: jne            c0 <dot_f32+0x40>
```

## `dot_f32` — `scalar_native`

```asm
    c0: vmovss         (%rsi,%rax,4),%xmm1
    c5: vmovss         0x4(%rsi,%rax,4),%xmm2
    cb: vfmadd231ss    (%rdx,%rax,4),%xmm1,%xmm0
    d1: vfmadd231ss    0x4(%rdx,%rax,4),%xmm2,%xmm0
    d8: add            $0x2,%rax
    dc: cmp            %rax,%rdi
    df: jne            c0 <dot_f32+0x40>
```

## `dot_f32` — `sse2`

```asm
   100: movups         (%rsi,%rax,1),%xmm1
   104: movups         (%rdx,%rax,1),%xmm3
   108: add            $0x10,%rax
   10c: mulps          %xmm3,%xmm1
   10f: addss          %xmm1,%xmm0
   113: movaps         %xmm1,%xmm2
   116: shufps         $0x55,%xmm1,%xmm2
   11a: addss          %xmm2,%xmm0
   11e: movaps         %xmm1,%xmm2
   121: unpckhps       %xmm1,%xmm2
   124: shufps         $0xff,%xmm1,%xmm1
   128: addss          %xmm2,%xmm0
   12c: addss          %xmm1,%xmm0
   130: cmp            %rcx,%rax
   133: jne            100 <dot_f32+0x40>
```

## `dot_f32` — `avx2`

```asm
   180: vmovups        (%rcx,%rax,1),%ymm4
   185: vmulps         (%rdx,%rax,1),%ymm4,%ymm1
   18a: add            $0x20,%rax
   18e: vaddss         %xmm1,%xmm0,%xmm0
   192: vshufps        $0x55,%xmm1,%xmm1,%xmm3
   197: vshufps        $0xff,%xmm1,%xmm1,%xmm2
   19c: vaddss         %xmm3,%xmm0,%xmm0
   1a0: vunpckhps      %xmm1,%xmm1,%xmm3
   1a4: vextractf128   $0x1,%ymm1,%xmm1
   1aa: vaddss         %xmm3,%xmm0,%xmm0
   1ae: vaddss         %xmm2,%xmm0,%xmm0
   1b2: vshufps        $0x55,%xmm1,%xmm1,%xmm2
   1b7: vaddss         %xmm1,%xmm0,%xmm0
   1bb: vaddss         %xmm2,%xmm0,%xmm0
   1bf: vunpckhps      %xmm1,%xmm1,%xmm2
   1c3: vshufps        $0xff,%xmm1,%xmm1,%xmm1
   1c8: vaddss         %xmm2,%xmm0,%xmm0
   1cc: vaddss         %xmm1,%xmm0,%xmm0
   1d0: cmp            %rax,%rsi
   1d3: jne            180 <dot_f32+0x40>
```

## `dot_f32` — `native`

```asm
   180: vmovups        (%rcx,%rsi,1),%ymm4
   185: vmulps         (%rdx,%rsi,1),%ymm4,%ymm1
   18a: add            $0x20,%rsi
   18e: vaddss         %xmm1,%xmm0,%xmm0
   192: vshufps        $0x55,%xmm1,%xmm1,%xmm3
   197: vshufps        $0xff,%xmm1,%xmm1,%xmm2
   19c: vaddss         %xmm3,%xmm0,%xmm0
   1a0: vunpckhps      %xmm1,%xmm1,%xmm3
   1a4: vaddss         %xmm3,%xmm0,%xmm0
   1a8: vaddss         %xmm2,%xmm0,%xmm0
   1ac: vextractf32x4  $0x1,%ymm1,%xmm2
   1b3: vaddss         %xmm2,%xmm0,%xmm0
   1b7: valignd        $0x5,%ymm1,%ymm1,%ymm2
   1be: vaddss         %xmm2,%xmm0,%xmm0
   1c2: valignd        $0x6,%ymm1,%ymm1,%ymm2
   1c9: valignd        $0x7,%ymm1,%ymm1,%ymm1
   1d0: vaddss         %xmm2,%xmm0,%xmm0
   1d4: vaddss         %xmm1,%xmm0,%xmm0
   1d8: cmp            %rsi,%rdi
   1db: jne            180 <dot_f32+0x40>
```

## `dot_f32` — `avx512`

```asm
   200: vmovups        (%rsi,%rax,1),%zmm5
   207: vmulps         (%rdx,%rax,1),%zmm5,%zmm1
   20e: add            $0x40,%rax
   212: vshufps        $0x55,%xmm1,%xmm1,%xmm4
   217: vshufps        $0xff,%xmm1,%xmm1,%xmm3
   21c: valignd        $0x7,%ymm1,%ymm1,%ymm2
   223: vaddss         %xmm1,%xmm0,%xmm0
   227: vaddss         %xmm4,%xmm0,%xmm0
   22b: vunpckhps      %xmm1,%xmm1,%xmm4
   22f: vaddss         %xmm4,%xmm0,%xmm0
   233: vaddss         %xmm3,%xmm0,%xmm0
   237: vextractf32x4  $0x1,%ymm1,%xmm3
   23e: vaddss         %xmm3,%xmm0,%xmm0
   242: valignd        $0x5,%ymm1,%ymm1,%ymm3
   249: vaddss         %xmm3,%xmm0,%xmm0
   24d: valignd        $0x6,%ymm1,%ymm1,%ymm3
   254: vextractf32x8  $0x1,%zmm1,%ymm1
   25b: vaddss         %xmm3,%xmm0,%xmm0
   25f: vshufps        $0x55,%xmm1,%xmm1,%xmm3
   264: vaddss         %xmm2,%xmm0,%xmm0
   268: vshufps        $0xff,%xmm1,%xmm1,%xmm2
   26d: vaddss         %xmm1,%xmm0,%xmm0
   271: vaddss         %xmm3,%xmm0,%xmm0
   275: vunpckhps      %xmm1,%xmm1,%xmm3
   ... (12 more instructions)
```

## `dotsimd_f32` — `scalar`

```asm
   140: movss          (%rsi,%rax,4),%xmm0
   145: mulss          (%rdx,%rax,4),%xmm0
   14a: add            $0x1,%rax
   14e: addss          %xmm0,%xmm1
   152: cmp            %rax,%rdi
   155: jne            140 <dotsimd_f32+0x40>
```

## `dotsimd_f32` — `scalar_native`

```asm
   140: vmovss         (%rsi,%rax,4),%xmm1
   145: vmovss         0x4(%rsi,%rax,4),%xmm2
   14b: vfmadd231ss    (%rdx,%rax,4),%xmm1,%xmm0
   151: vfmadd231ss    0x4(%rdx,%rax,4),%xmm2,%xmm0
   158: add            $0x2,%rax
   15c: cmp            %rax,%rdi
   15f: jne            140 <dotsimd_f32+0x40>
```

## `dotsimd_f32` — `sse2`

```asm
   240: movups         (%rsi,%rax,1),%xmm0
   244: movups         (%rdx,%rax,1),%xmm2
   248: add            $0x10,%rax
   24c: mulps          %xmm2,%xmm0
   24f: addps          %xmm0,%xmm1
   252: cmp            %rax,%rdi
   255: jne            240 <dotsimd_f32+0x80>
```

## `dotsimd_f32` — `avx2`

```asm
   340: vmovups        (%rcx,%rax,1),%ymm2
   345: vmulps         (%rdx,%rax,1),%ymm2,%ymm0
   34a: add            $0x20,%rax
   34e: vaddps         %ymm0,%ymm1,%ymm1
   352: cmp            %rsi,%rax
   355: jne            340 <dotsimd_f32+0x80>
```

## `dotsimd_f32` — `native`

```asm
   340: vmovups        (%rcx,%rax,1),%ymm1
   345: vfmadd231ps    (%rdx,%rax,1),%ymm1,%ymm0
   34b: add            $0x20,%rax
   34f: cmp            %rax,%rsi
   352: jne            340 <dotsimd_f32+0x80>
```

## `dotsimd_f32` — `avx512`

```asm
   480: vmovups        (%rcx,%rax,1),%zmm1
   487: vfmadd231ps    (%rdx,%rax,1),%zmm1,%zmm0
   48e: add            $0x40,%rax
   492: cmp            %rsi,%rax
   495: jne            480 <dotsimd_f32+0x80>
```

## `dot_i32` — `scalar`

```asm
   700: mov            (%rsi,%rax,4),%ecx
   703: imul           (%rdx,%rax,4),%ecx
   707: add            $0x1,%rax
   70b: add            %ecx,%r8d
   70e: cmp            %rax,%rdi
   711: jne            700 <dot_i32+0x40>
```

## `dot_i32` — `scalar_native`

```asm
   640: mov            (%rsi,%rax,4),%ecx
   643: imul           (%rdx,%rax,4),%ecx
   647: inc            %rax
   64a: add            %ecx,%r8d
   64d: cmp            %rax,%rdi
   650: jne            640 <dot_i32+0x40>
```

## `dot_i32` — `sse2`

```asm
   a00: movdqu         (%rcx,%rax,1),%xmm0
   a05: movdqu         (%rdx,%rax,1),%xmm2
   a0a: movdqu         (%rcx,%rax,1),%xmm1
   a0f: movdqu         (%rdx,%rax,1),%xmm4
   a14: add            $0x10,%rax
   a18: psrlq          $0x20,%xmm0
   a1d: psrlq          $0x20,%xmm2
   a22: pmuludq        %xmm4,%xmm1
   a26: pmuludq        %xmm2,%xmm0
   a2a: pshufd         $0x8,%xmm1,%xmm1
   a2f: pshufd         $0x8,%xmm0,%xmm0
   a34: punpckldq      %xmm0,%xmm1
   a38: paddd          %xmm1,%xmm3
   a3c: cmp            %rsi,%rax
   a3f: jne            a00 <dot_i32+0x40>
```

## `dot_i32` — `avx2`

```asm
   dc0: vmovdqu        (%rsi,%rax,1),%ymm3
   dc5: vpmulld        (%rcx,%rax,1),%ymm3,%ymm0
   dcb: add            $0x20,%rax
   dcf: vpaddd         %ymm0,%ymm1,%ymm1
   dd3: cmp            %rax,%rdx
   dd6: jne            dc0 <dot_i32+0x40>
```

## `dot_i32` — `native`

```asm
   d40: vmovdqu        (%rsi,%rax,1),%ymm3
   d45: vpmulld        (%rcx,%rax,1),%ymm3,%ymm0
   d4b: add            $0x20,%rax
   d4f: vpaddd         %ymm0,%ymm1,%ymm1
   d53: cmp            %rax,%rdx
   d56: jne            d40 <dot_i32+0x40>
```

## `dot_i32` — `avx512`

```asm
  1440: vmovdqu32      (%rsi,%rax,1),%zmm3
  1447: vpmulld        (%rcx,%rax,1),%zmm3,%zmm0
  144e: add            $0x40,%rax
  1452: vpaddd         %zmm0,%zmm1,%zmm1
  1458: cmp            %rax,%rdx
  145b: jne            1440 <dot_i32+0x40>
```

## `saxpy_s4_f32` — `scalar`

```asm
   bc0: movss          (%rsi,%rax,1),%xmm1
   bc5: mulss          %xmm0,%xmm1
   bc9: addss          (%rdx,%rax,1),%xmm1
   bce: movss          %xmm1,(%rdx,%rax,1)
   bd3: add            $0x10,%rax
   bd7: cmp            %rax,%rdi
   bda: jne            bc0 <saxpy_s4_f32+0x40>
```

## `saxpy_s4_f32` — `scalar_native`

```asm
   b00: vmovss         (%rsi,%rax,1),%xmm1
   b05: vfmadd213ss    (%rdx,%rax,1),%xmm0,%xmm1
   b0b: vmovss         %xmm1,(%rdx,%rax,1)
   b10: add            $0x10,%rax
   b14: cmp            %rax,%rdi
   b17: jne            b00 <saxpy_s4_f32+0x40>
```

## `saxpy_s4_f32` — `sse2`

```asm
  13c0: movups         0x10(%rdx),%xmm5
  13c4: movups         (%rdx),%xmm0
  13c7: add            $0x40,%rdx
  13cb: add            $0x40,%rax
  13cf: movups         -0x20(%rdx),%xmm1
  13d3: movups         -0x10(%rdx),%xmm6
  13d7: shufps         $0x88,%xmm5,%xmm0
  13db: movups         -0x30(%rax),%xmm7
  13df: movups         -0x20(%rax),%xmm2
  13e3: shufps         $0x88,%xmm6,%xmm1
  13e7: shufps         $0x88,%xmm1,%xmm0
  13eb: mulps          %xmm4,%xmm0
  13ee: movups         -0x40(%rax),%xmm1
  13f2: movups         -0x10(%rax),%xmm5
  13f6: shufps         $0x88,%xmm7,%xmm1
  13fa: shufps         $0x88,%xmm5,%xmm2
  13fe: shufps         $0x88,%xmm2,%xmm1
  1402: addps          %xmm1,%xmm0
  1405: movaps         %xmm0,%xmm1
  1408: movss          %xmm0,-0x40(%rax)
  140d: shufps         $0x55,%xmm0,%xmm1
  1411: movss          %xmm1,-0x30(%rax)
  1416: movaps         %xmm0,%xmm1
  1419: unpckhps       %xmm0,%xmm1
   ... (5 more instructions)
```

## `saxpy_s4_f32` — `avx2`

```asm
  1a40: vpermd         0x20(%rdx),%ymm2,%ymm1
  1a46: vpermd         (%rdx),%ymm3,%ymm0
  1a4b: sub            $0xffffffffffffff80,%rdx
  1a4f: sub            $0xffffffffffffff80,%rax
  1a53: vpermd         -0x20(%rdx),%ymm2,%ymm4
  1a59: vpermd         -0x20(%rax),%ymm2,%ymm7
  1a5f: vblendps       $0xf0,%ymm1,%ymm0,%ymm0
  1a65: vpermd         -0x40(%rdx),%ymm3,%ymm1
  1a6b: vpermd         %ymm0,%ymm3,%ymm0
  1a70: vblendps       $0xf0,%ymm4,%ymm1,%ymm1
  1a76: vpermd         -0x60(%rax),%ymm2,%ymm4
  1a7c: vpermd         %ymm1,%ymm2,%ymm1
  1a81: vblendps       $0xf0,%ymm1,%ymm0,%ymm0
  1a87: vpermd         -0x80(%rax),%ymm3,%ymm1
  1a8d: vblendps       $0xf0,%ymm4,%ymm1,%ymm1
  1a93: vpermd         -0x40(%rax),%ymm3,%ymm4
  1a99: vpermd         %ymm1,%ymm3,%ymm1
  1a9e: vblendps       $0xf0,%ymm7,%ymm4,%ymm4
  1aa4: vpermd         %ymm4,%ymm2,%ymm4
  1aa9: vblendps       $0xf0,%ymm4,%ymm1,%ymm1
  1aaf: vfmadd132ps    %ymm5,%ymm1,%ymm0
  1ab4: vmovss         %xmm0,-0x80(%rax)
  1ab9: vextractps     $0x1,%xmm0,-0x70(%rax)
  1ac0: vextractps     $0x2,%xmm0,-0x60(%rax)
   ... (8 more instructions)
```

## `saxpy_s4_f32` — `native`

```asm
  1940: vmovups        (%rdx),%ymm1
  1944: vmovups        0x40(%rdx),%ymm3
  1949: sub            $0xffffffffffffff80,%rdx
  194d: sub            $0xffffffffffffff80,%rax
  1951: vmovups        -0x40(%rax),%ymm4
  1956: vpermt2ps      -0x20(%rdx),%ymm2,%ymm3
  195d: vpermt2ps      -0x60(%rdx),%ymm2,%ymm1
  1964: vpermt2ps      %ymm3,%ymm2,%ymm1
  196a: vmovups        -0x80(%rax),%ymm3
  196f: vpermt2ps      -0x20(%rax),%ymm2,%ymm4
  1976: vpermt2ps      -0x60(%rax),%ymm2,%ymm3
  197d: vpermt2ps      %ymm4,%ymm2,%ymm3
  1983: vfmadd132ps    %ymm5,%ymm3,%ymm1
  1988: vextractf32x4  $0x1,%ymm1,%xmm3
  198f: vmovss         %xmm1,-0x80(%rax)
  1994: vextractps     $0x1,%xmm1,-0x70(%rax)
  199b: vextractps     $0x2,%xmm1,-0x60(%rax)
  19a2: vextractps     $0x3,%xmm1,-0x50(%rax)
  19a9: vmovss         %xmm3,-0x40(%rax)
  19ae: valignd        $0x5,%ymm1,%ymm1,%ymm3
  19b5: vmovss         %xmm3,-0x30(%rax)
  19ba: valignd        $0x6,%ymm1,%ymm1,%ymm3
  19c1: valignd        $0x7,%ymm1,%ymm1,%ymm1
  19c8: vmovss         %xmm3,-0x20(%rax)
   ... (3 more instructions)
```

## `saxpy_s4_f32` — `avx512`

```asm
  2680: vmovups        (%rdx),%zmm0
  2686: vmovups        0x80(%rdx),%zmm1
  268d: add            $0x100,%rdx
  2694: add            $0x100,%rax
  269a: vmovups        -0x80(%rax),%zmm3
  26a1: vpermt2ps      -0x40(%rdx),%zmm2,%zmm1
  26a8: vpermt2ps      -0xc0(%rdx),%zmm2,%zmm0
  26af: vpermt2ps      %zmm1,%zmm2,%zmm0
  26b5: vmovups        -0x100(%rax),%zmm1
  26bc: vpermt2ps      -0x40(%rax),%zmm2,%zmm3
  26c3: vpermt2ps      -0xc0(%rax),%zmm2,%zmm1
  26ca: vpermt2ps      %zmm3,%zmm2,%zmm1
  26d0: vfmadd132ps    %zmm5,%zmm1,%zmm0
  26d6: vextractf32x4  $0x1,%ymm0,%xmm3
  26dd: vmovss         %xmm0,-0x100(%rax)
  26e5: vextractps     $0x1,%xmm0,-0xf0(%rax)
  26ef: vextractps     $0x2,%xmm0,-0xe0(%rax)
  26f9: valignd        $0x7,%ymm0,%ymm0,%ymm1
  2700: vextractps     $0x3,%xmm0,-0xd0(%rax)
  270a: vmovss         %xmm3,-0xc0(%rax)
  2712: valignd        $0x5,%ymm0,%ymm0,%ymm3
  2719: vmovss         %xmm1,-0x90(%rax)
  2721: vmovss         %xmm3,-0xb0(%rax)
  2729: valignd        $0x6,%ymm0,%ymm0,%ymm3
   ... (16 more instructions)
```

## `saxpy_gather_f32` — `scalar`

```asm
   d40: mov            (%rsi,%rax,4),%edi
   d43: movss          (%rdx,%rdi,4),%xmm1
   d48: mulss          %xmm0,%xmm1
   d4c: addss          (%rcx,%rax,4),%xmm1
   d51: movss          %xmm1,(%rcx,%rax,4)
   d56: add            $0x1,%rax
   d5a: cmp            %rax,%r8
   d5d: jne            d40 <saxpy_gather_f32+0x40>
```

## `saxpy_gather_f32` — `scalar_native`

```asm
   c80: mov            (%rsi,%rax,4),%r8d
   c84: vmovss         (%rdx,%r8,4),%xmm1
   c8a: vfmadd213ss    (%rcx,%rax,4),%xmm0,%xmm1
   c90: vmovss         %xmm1,(%rcx,%rax,4)
   c95: inc            %rax
   c98: cmp            %rax,%rdi
   c9b: jne            c80 <saxpy_gather_f32+0x40>
```

## `saxpy_gather_f32` — `sse2`

```asm
  1600: lea            (%rdi,%rax,1),%rcx
  1604: movups         (%rsi,%rax,1),%xmm5
  1608: mov            (%rcx),%r9d
  160b: mov            0x4(%rcx),%r10d
  160f: mov            0x8(%rcx),%r11d
  1613: mov            0xc(%rcx),%ecx
  1616: movss          (%rdx,%r10,4),%xmm3
  161c: movss          (%rdx,%rcx,4),%xmm1
  1621: movss          (%rdx,%r11,4),%xmm2
  1627: unpcklps       %xmm1,%xmm2
  162a: movss          (%rdx,%r9,4),%xmm1
  1630: unpcklps       %xmm3,%xmm1
  1633: movlhps        %xmm2,%xmm1
  1636: mulps          %xmm4,%xmm1
  1639: addps          %xmm5,%xmm1
  163c: movups         %xmm1,(%rsi,%rax,1)
  1640: add            $0x10,%rax
  1644: cmp            %rbx,%rax
  1647: jne            1600 <saxpy_gather_f32+0x40>
```

## `saxpy_gather_f32` — `avx2`

```asm
  2000: lea            (%rsi,%rcx,1),%rdx
  2004: mov            (%rdx),%r11d
  2007: mov            0x4(%rdx),%r10d
  200b: mov            0x8(%rdx),%r12d
  200f: mov            0xc(%rdx),%ebx
  2012: mov            0x10(%rdx),%r14d
  2016: mov            0x14(%rdx),%r13d
  201a: mov            0x18(%rdx),%r15d
  201e: mov            0x1c(%rdx),%edx
  2021: vmovss         (%rax,%r14,4),%xmm1
  2027: vinsertps      $0x10,(%rax,%r13,4),%xmm1,%xmm1
  202e: vmovss         (%rax,%r15,4),%xmm0
  2034: vinsertps      $0x10,(%rax,%rdx,4),%xmm0,%xmm0
  203b: vmovss         (%rax,%r12,4),%xmm2
  2041: vinsertps      $0x10,(%rax,%rbx,4),%xmm2,%xmm2
  2048: vmovlhps       %xmm0,%xmm1,%xmm1
  204c: vmovss         (%rax,%r11,4),%xmm0
  2052: vinsertps      $0x10,(%rax,%r10,4),%xmm0,%xmm0
  2059: vmovlhps       %xmm2,%xmm0,%xmm0
  205d: vinsertf128    $0x1,%xmm1,%ymm0,%ymm0
  2063: vfmadd213ps    (%r8,%rcx,1),%ymm4,%ymm0
  2069: vmovups        %ymm0,(%r8,%rcx,1)
  206f: add            $0x20,%rcx
  2073: cmp            %rcx,%r9
   ... (1 more instructions)
```

## `saxpy_gather_f32` — `native`

```asm
  1e80: lea            (%rsi,%rcx,1),%rdx
  1e84: mov            0x10(%rdx),%r14d
  1e88: mov            0x18(%rdx),%r15d
  1e8c: mov            (%rdx),%r11d
  1e8f: mov            0x4(%rdx),%r10d
  1e93: mov            0x8(%rdx),%r12d
  1e97: mov            0xc(%rdx),%ebx
  1e9a: mov            0x14(%rdx),%r13d
  1e9e: vmovss         (%rax,%r15,4),%xmm2
  1ea4: mov            0x1c(%rdx),%edx
  1ea7: vmovss         (%rax,%r14,4),%xmm1
  1ead: vmovss         (%rax,%r12,4),%xmm3
  1eb3: vinsertps      $0x10,(%rax,%r13,4),%xmm1,%xmm1
  1eba: vinsertps      $0x10,(%rax,%rdx,4),%xmm2,%xmm2
  1ec1: vinsertps      $0x10,(%rax,%rbx,4),%xmm3,%xmm3
  1ec8: vmovlhps       %xmm2,%xmm1,%xmm2
  1ecc: vmovss         (%rax,%r11,4),%xmm1
  1ed2: vinsertps      $0x10,(%rax,%r10,4),%xmm1,%xmm1
  1ed9: vmovlhps       %xmm3,%xmm1,%xmm1
  1edd: vinsertf128    $0x1,%xmm2,%ymm1,%ymm1
  1ee3: vfmadd213ps    (%r8,%rcx,1),%ymm4,%ymm1
  1ee9: vmovups        %ymm1,(%r8,%rcx,1)
  1eef: add            $0x20,%rcx
  1ef3: cmp            %rcx,%r9
   ... (1 more instructions)
```

## `saxpy_gather_f32` — `avx512`

```asm
  3340: mov            -0x30(%rsp),%rax
  3345: add            %rdx,%rax
  3348: mov            (%rax),%ebx
  334a: mov            0x4(%rax),%edi
  334d: mov            0x8(%rax),%esi
  3350: mov            0xc(%rax),%ecx
  3353: mov            0x14(%rax),%r8d
  3357: mov            0x30(%rax),%r12d
  335b: mov            %rbx,-0x8(%rsp)
  3360: mov            0x38(%rax),%r13d
  3364: mov            0x34(%rax),%ebx
  3367: mov            %rdi,-0x10(%rsp)
  336c: mov            0x20(%rax),%r9d
  3370: mov            0x18(%rax),%edi
  3373: mov            %rsi,-0x18(%rsp)
  3378: mov            0x28(%rax),%r11d
  337c: mov            0x1c(%rax),%esi
  337f: mov            %rcx,-0x20(%rsp)
  3384: mov            0x2c(%rax),%r10d
  3388: mov            0x10(%rax),%ecx
  338b: mov            %r8,-0x28(%rsp)
  3390: vmovss         (%r14,%r13,4),%xmm2
  3396: mov            0x24(%rax),%r8d
  339a: vmovss         (%r14,%r12,4),%xmm0
   ... (32 more instructions)
```

