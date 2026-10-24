# Hot-loop excerpts (targeted disassembly)

Inner loop only (backward-branch body with the most packed work), truncated to 24 lines.

## `saxpy_f32` — `scalar`

```asm
    10: movss          (%rsi,%rax,4),%xmm1
    15: mulss          %xmm0,%xmm1
    19: addss          (%rdx,%rax,4),%xmm1
    1e: movss          %xmm1,(%rdx,%rax,4)
    23: add            $0x1,%rax
    27: cmp            %rax,%rdi
    2a: jne            10 <saxpy_f32+0x10>
```

## `saxpy_f32` — `scalar_native`

```asm
    10: vmovss         (%rsi,%rax,4),%xmm1
    15: vfmadd213ss    (%rdx,%rax,4),%xmm0,%xmm1
    1b: vmovss         %xmm1,(%rdx,%rax,4)
    20: inc            %rax
    23: cmp            %rax,%rdi
    26: jne            10 <saxpy_f32+0x10>
```

## `saxpy_f32` — `sse2`

```asm
    38: movups         (%rcx,%rax,1),%xmm1
    3c: movups         (%rdx,%rax,1),%xmm3
    40: mulps          %xmm2,%xmm1
    43: addps          %xmm3,%xmm1
    46: movups         %xmm1,(%rdx,%rax,1)
    4a: add            $0x10,%rax
    4e: cmp            %rsi,%rax
    51: jne            38 <saxpy_f32+0x38>
```

## `saxpy_f32` — `avx2`

```asm
    30: vmovups        (%rcx,%rax,1),%ymm1
    35: vfmadd213ps    (%rdx,%rax,1),%ymm2,%ymm1
    3b: vmovups        %ymm1,(%rdx,%rax,1)
    40: add            $0x20,%rax
    44: cmp            %rsi,%rax
    47: jne            30 <saxpy_f32+0x30>
```

## `saxpy_f32` — `native`

```asm
    38: vmovups        (%r8,%rax,1),%ymm1
    3e: vfmadd213ps    (%rdx,%rax,1),%ymm2,%ymm1
    44: vmovups        %ymm1,(%rdx,%rax,1)
    49: add            $0x20,%rax
    4d: cmp            %rsi,%rax
    50: jne            38 <saxpy_f32+0x38>
```

## `saxpy_f32` — `avx512`

```asm
    38: vmovups        (%rcx,%rax,1),%zmm1
    3f: vfmadd213ps    (%rdx,%rax,1),%zmm2,%zmm1
    46: vmovups        %zmm1,(%rdx,%rax,1)
    4d: add            $0x40,%rax
    51: cmp            %rsi,%rax
    54: jne            38 <saxpy_f32+0x38>
```

## `dot_f32` — `scalar`

```asm
    40: movss          (%rsi,%rax,4),%xmm0
    45: mulss          (%rdx,%rax,4),%xmm0
    4a: add            $0x1,%rax
    4e: addss          %xmm0,%xmm1
    52: cmp            %rax,%rdi
    55: jne            40 <dot_f32+0x10>
```

## `dot_f32` — `scalar_native`

```asm
    60: vmovss         (%rsi,%rax,4),%xmm1
    65: vmovss         0x4(%rsi,%rax,4),%xmm2
    6b: vfmadd231ss    (%rdx,%rax,4),%xmm1,%xmm0
    71: vfmadd231ss    0x4(%rdx,%rax,4),%xmm2,%xmm0
    78: add            $0x2,%rax
    7c: cmp            %rax,%rdi
    7f: jne            60 <dot_f32+0x30>
```

## `dot_f32` — `sse2`

```asm
    e0: movups         (%rsi,%rax,1),%xmm1
    e4: movups         (%rdx,%rax,1),%xmm3
    e8: add            $0x10,%rax
    ec: mulps          %xmm3,%xmm1
    ef: addss          %xmm1,%xmm0
    f3: movaps         %xmm1,%xmm2
    f6: shufps         $0x55,%xmm1,%xmm2
    fa: addss          %xmm2,%xmm0
    fe: movaps         %xmm1,%xmm2
   101: unpckhps       %xmm1,%xmm2
   104: shufps         $0xff,%xmm1,%xmm1
   108: addss          %xmm2,%xmm0
   10c: addss          %xmm1,%xmm0
   110: cmp            %rcx,%rax
   113: jne            e0 <dot_f32+0x30>
```

## `dot_f32` — `avx2`

```asm
   130: vmovups        (%rcx,%rax,1),%ymm4
   135: vmulps         (%rdx,%rax,1),%ymm4,%ymm1
   13a: add            $0x20,%rax
   13e: vaddss         %xmm1,%xmm0,%xmm0
   142: vshufps        $0x55,%xmm1,%xmm1,%xmm3
   147: vshufps        $0xff,%xmm1,%xmm1,%xmm2
   14c: vaddss         %xmm3,%xmm0,%xmm0
   150: vunpckhps      %xmm1,%xmm1,%xmm3
   154: vextractf128   $0x1,%ymm1,%xmm1
   15a: vaddss         %xmm3,%xmm0,%xmm0
   15e: vaddss         %xmm2,%xmm0,%xmm0
   162: vshufps        $0x55,%xmm1,%xmm1,%xmm2
   167: vaddss         %xmm1,%xmm0,%xmm0
   16b: vaddss         %xmm2,%xmm0,%xmm0
   16f: vunpckhps      %xmm1,%xmm1,%xmm2
   173: vshufps        $0xff,%xmm1,%xmm1,%xmm1
   178: vaddss         %xmm2,%xmm0,%xmm0
   17c: vaddss         %xmm1,%xmm0,%xmm0
   180: cmp            %rax,%rsi
   183: jne            130 <dot_f32+0x30>
```

## `dot_f32` — `native`

```asm
   140: vmovups        (%rcx,%rsi,1),%ymm4
   145: vmulps         (%rdx,%rsi,1),%ymm4,%ymm1
   14a: add            $0x20,%rsi
   14e: vaddss         %xmm1,%xmm0,%xmm0
   152: vshufps        $0x55,%xmm1,%xmm1,%xmm3
   157: vshufps        $0xff,%xmm1,%xmm1,%xmm2
   15c: vaddss         %xmm3,%xmm0,%xmm0
   160: vunpckhps      %xmm1,%xmm1,%xmm3
   164: vaddss         %xmm3,%xmm0,%xmm0
   168: vaddss         %xmm2,%xmm0,%xmm0
   16c: vextractf32x4  $0x1,%ymm1,%xmm2
   173: vaddss         %xmm2,%xmm0,%xmm0
   177: valignd        $0x5,%ymm1,%ymm1,%ymm2
   17e: vaddss         %xmm2,%xmm0,%xmm0
   182: valignd        $0x6,%ymm1,%ymm1,%ymm2
   189: valignd        $0x7,%ymm1,%ymm1,%ymm1
   190: vaddss         %xmm2,%xmm0,%xmm0
   194: vaddss         %xmm1,%xmm0,%xmm0
   198: cmp            %rsi,%rdi
   19b: jne            140 <dot_f32+0x30>
```

## `dot_f32` — `avx512`

```asm
   1c0: vmovups        (%rsi,%rax,1),%zmm5
   1c7: vmulps         (%rdx,%rax,1),%zmm5,%zmm1
   1ce: add            $0x40,%rax
   1d2: vshufps        $0x55,%xmm1,%xmm1,%xmm4
   1d7: vshufps        $0xff,%xmm1,%xmm1,%xmm3
   1dc: valignd        $0x7,%ymm1,%ymm1,%ymm2
   1e3: vaddss         %xmm1,%xmm0,%xmm0
   1e7: vaddss         %xmm4,%xmm0,%xmm0
   1eb: vunpckhps      %xmm1,%xmm1,%xmm4
   1ef: vaddss         %xmm4,%xmm0,%xmm0
   1f3: vaddss         %xmm3,%xmm0,%xmm0
   1f7: vextractf32x4  $0x1,%ymm1,%xmm3
   1fe: vaddss         %xmm3,%xmm0,%xmm0
   202: valignd        $0x5,%ymm1,%ymm1,%ymm3
   209: vaddss         %xmm3,%xmm0,%xmm0
   20d: valignd        $0x6,%ymm1,%ymm1,%ymm3
   214: vextractf32x8  $0x1,%zmm1,%ymm1
   21b: vaddss         %xmm3,%xmm0,%xmm0
   21f: vshufps        $0x55,%xmm1,%xmm1,%xmm3
   224: vaddss         %xmm2,%xmm0,%xmm0
   228: vshufps        $0xff,%xmm1,%xmm1,%xmm2
   22d: vaddss         %xmm1,%xmm0,%xmm0
   231: vaddss         %xmm3,%xmm0,%xmm0
   235: vunpckhps      %xmm1,%xmm1,%xmm3
   ... (12 more instructions)
```

## `dotsimd_f32` — `scalar`

```asm
    80: movss          (%rsi,%rax,4),%xmm0
    85: mulss          (%rdx,%rax,4),%xmm0
    8a: add            $0x1,%rax
    8e: addss          %xmm0,%xmm1
    92: cmp            %rax,%rdi
    95: jne            80 <dotsimd_f32+0x10>
```

## `dotsimd_f32` — `scalar_native`

```asm
    c0: vmovss         (%rsi,%rax,4),%xmm1
    c5: vmovss         0x4(%rsi,%rax,4),%xmm2
    cb: vfmadd231ss    (%rdx,%rax,4),%xmm1,%xmm0
    d1: vfmadd231ss    0x4(%rdx,%rax,4),%xmm2,%xmm0
    d8: add            $0x2,%rax
    dc: cmp            %rax,%rdi
    df: jne            c0 <dotsimd_f32+0x30>
```

## `dotsimd_f32` — `sse2`

```asm
   1c8: movups         (%rsi,%rax,1),%xmm0
   1cc: movups         (%rdx,%rax,1),%xmm2
   1d0: add            $0x10,%rax
   1d4: mulps          %xmm2,%xmm0
   1d7: addps          %xmm0,%xmm1
   1da: cmp            %rax,%rdi
   1dd: jne            1c8 <dotsimd_f32+0x48>
```

## `dotsimd_f32` — `avx2`

```asm
   290: vmovups        (%rcx,%rax,1),%ymm2
   295: vmulps         (%rdx,%rax,1),%ymm2,%ymm0
   29a: add            $0x20,%rax
   29e: vaddps         %ymm0,%ymm1,%ymm1
   2a2: cmp            %rsi,%rax
   2a5: jne            290 <dotsimd_f32+0x50>
```

## `dotsimd_f32` — `native`

```asm
   2b0: vmovups        (%rcx,%rax,1),%ymm1
   2b5: vfmadd231ps    (%rdx,%rax,1),%ymm1,%ymm0
   2bb: add            $0x20,%rax
   2bf: cmp            %rax,%rsi
   2c2: jne            2b0 <dotsimd_f32+0x50>
```

## `dotsimd_f32` — `avx512`

```asm
   418: vmovups        (%rcx,%rax,1),%zmm1
   41f: vfmadd231ps    (%rdx,%rax,1),%zmm1,%zmm0
   426: add            $0x40,%rax
   42a: cmp            %rsi,%rax
   42d: jne            418 <dotsimd_f32+0x58>
```

## `dot_i32` — `scalar`

```asm
   3d0: mov            (%rsi,%rax,4),%ecx
   3d3: imul           (%rdx,%rax,4),%ecx
   3d7: add            $0x1,%rax
   3db: add            %ecx,%r8d
   3de: cmp            %rax,%rdi
   3e1: jne            3d0 <dot_i32+0x10>
```

## `dot_i32` — `scalar_native`

```asm
   400: mov            (%rsi,%rax,4),%ecx
   403: imul           (%rdx,%rax,4),%ecx
   407: inc            %rax
   40a: add            %ecx,%r8d
   40d: cmp            %rax,%rdi
   410: jne            400 <dot_i32+0x10>
```

## `dot_i32` — `sse2`

```asm
   810: movdqu         (%rcx,%rax,1),%xmm0
   815: movdqu         (%rdx,%rax,1),%xmm2
   81a: movdqu         (%rcx,%rax,1),%xmm1
   81f: movdqu         (%rdx,%rax,1),%xmm4
   824: add            $0x10,%rax
   828: psrlq          $0x20,%xmm0
   82d: psrlq          $0x20,%xmm2
   832: pmuludq        %xmm4,%xmm1
   836: pmuludq        %xmm2,%xmm0
   83a: pshufd         $0x8,%xmm1,%xmm1
   83f: pshufd         $0x8,%xmm0,%xmm0
   844: punpckldq      %xmm0,%xmm1
   848: paddd          %xmm1,%xmm3
   84c: cmp            %rsi,%rax
   84f: jne            810 <dot_i32+0x30>
```

## `dot_i32` — `avx2`

```asm
   b80: vmovdqu        (%rsi,%rax,1),%ymm3
   b85: vpmulld        (%rcx,%rax,1),%ymm3,%ymm0
   b8b: add            $0x20,%rax
   b8f: vpaddd         %ymm0,%ymm1,%ymm1
   b93: cmp            %rax,%rdx
   b96: jne            b80 <dot_i32+0x30>
```

## `dot_i32` — `native`

```asm
   b90: vmovdqu        (%rsi,%rax,1),%ymm3
   b95: vpmulld        (%rcx,%rax,1),%ymm3,%ymm0
   b9b: add            $0x20,%rax
   b9f: vpaddd         %ymm0,%ymm1,%ymm1
   ba3: cmp            %rax,%rdx
   ba6: jne            b90 <dot_i32+0x30>
```

## `dot_i32` — `avx512`

```asm
  1230: vmovdqu32      (%rsi,%rax,1),%zmm3
  1237: vpmulld        (%rcx,%rax,1),%zmm3,%zmm0
  123e: add            $0x40,%rax
  1242: vpaddd         %zmm0,%zmm1,%zmm1
  1248: cmp            %rax,%rdx
  124b: jne            1230 <dot_i32+0x30>
```

## `saxpy_s4_f32` — `scalar`

```asm
   650: movss          (%rsi,%rax,1),%xmm1
   655: mulss          %xmm0,%xmm1
   659: addss          (%rdx,%rax,1),%xmm1
   65e: movss          %xmm1,(%rdx,%rax,1)
   663: add            $0x10,%rax
   667: cmp            %rax,%rdi
   66a: jne            650 <saxpy_s4_f32+0x10>
```

## `saxpy_s4_f32` — `scalar_native`

```asm
   680: vmovss         (%rsi,%rax,1),%xmm1
   685: vfmadd213ss    (%rdx,%rax,1),%xmm0,%xmm1
   68b: vmovss         %xmm1,(%rdx,%rax,1)
   690: add            $0x10,%rax
   694: cmp            %rax,%rdi
   697: jne            680 <saxpy_s4_f32+0x10>
```

## `saxpy_s4_f32` — `sse2`

```asm
  1028: movups         0x10(%rdx),%xmm5
  102c: movups         (%rdx),%xmm0
  102f: add            $0x40,%rdx
  1033: add            $0x40,%rax
  1037: movups         -0x20(%rdx),%xmm1
  103b: movups         -0x10(%rdx),%xmm6
  103f: shufps         $0x88,%xmm5,%xmm0
  1043: movups         -0x30(%rax),%xmm7
  1047: movups         -0x20(%rax),%xmm2
  104b: shufps         $0x88,%xmm6,%xmm1
  104f: shufps         $0x88,%xmm1,%xmm0
  1053: mulps          %xmm4,%xmm0
  1056: movups         -0x40(%rax),%xmm1
  105a: movups         -0x10(%rax),%xmm5
  105e: shufps         $0x88,%xmm7,%xmm1
  1062: shufps         $0x88,%xmm5,%xmm2
  1066: shufps         $0x88,%xmm2,%xmm1
  106a: addps          %xmm1,%xmm0
  106d: movaps         %xmm0,%xmm1
  1070: movss          %xmm0,-0x40(%rax)
  1075: shufps         $0x55,%xmm0,%xmm1
  1079: movss          %xmm1,-0x30(%rax)
  107e: movaps         %xmm0,%xmm1
  1081: unpckhps       %xmm0,%xmm1
   ... (5 more instructions)
```

## `saxpy_s4_f32` — `avx2`

```asm
  15d0: vpermd         0x20(%rdx),%ymm2,%ymm1
  15d6: vpermd         (%rdx),%ymm3,%ymm0
  15db: sub            $0xffffffffffffff80,%rdx
  15df: sub            $0xffffffffffffff80,%rax
  15e3: vpermd         -0x20(%rdx),%ymm2,%ymm4
  15e9: vpermd         -0x20(%rax),%ymm2,%ymm7
  15ef: vblendps       $0xf0,%ymm1,%ymm0,%ymm0
  15f5: vpermd         -0x40(%rdx),%ymm3,%ymm1
  15fb: vpermd         %ymm0,%ymm3,%ymm0
  1600: vblendps       $0xf0,%ymm4,%ymm1,%ymm1
  1606: vpermd         -0x60(%rax),%ymm2,%ymm4
  160c: vpermd         %ymm1,%ymm2,%ymm1
  1611: vblendps       $0xf0,%ymm1,%ymm0,%ymm0
  1617: vpermd         -0x80(%rax),%ymm3,%ymm1
  161d: vblendps       $0xf0,%ymm4,%ymm1,%ymm1
  1623: vpermd         -0x40(%rax),%ymm3,%ymm4
  1629: vpermd         %ymm1,%ymm3,%ymm1
  162e: vblendps       $0xf0,%ymm7,%ymm4,%ymm4
  1634: vpermd         %ymm4,%ymm2,%ymm4
  1639: vblendps       $0xf0,%ymm4,%ymm1,%ymm1
  163f: vfmadd132ps    %ymm5,%ymm1,%ymm0
  1644: vmovss         %xmm0,-0x80(%rax)
  1649: vextractps     $0x1,%xmm0,-0x70(%rax)
  1650: vextractps     $0x2,%xmm0,-0x60(%rax)
   ... (8 more instructions)
```

## `saxpy_s4_f32` — `native`

```asm
  15c0: vmovups        (%rdx),%ymm1
  15c4: vmovups        0x40(%rdx),%ymm3
  15c9: sub            $0xffffffffffffff80,%rdx
  15cd: sub            $0xffffffffffffff80,%rax
  15d1: vmovups        -0x40(%rax),%ymm4
  15d6: vpermt2ps      -0x20(%rdx),%ymm2,%ymm3
  15dd: vpermt2ps      -0x60(%rdx),%ymm2,%ymm1
  15e4: vpermt2ps      %ymm3,%ymm2,%ymm1
  15ea: vmovups        -0x80(%rax),%ymm3
  15ef: vpermt2ps      -0x20(%rax),%ymm2,%ymm4
  15f6: vpermt2ps      -0x60(%rax),%ymm2,%ymm3
  15fd: vpermt2ps      %ymm4,%ymm2,%ymm3
  1603: vfmadd132ps    %ymm5,%ymm3,%ymm1
  1608: vextractf32x4  $0x1,%ymm1,%xmm3
  160f: vmovss         %xmm1,-0x80(%rax)
  1614: vextractps     $0x1,%xmm1,-0x70(%rax)
  161b: vextractps     $0x2,%xmm1,-0x60(%rax)
  1622: vextractps     $0x3,%xmm1,-0x50(%rax)
  1629: vmovss         %xmm3,-0x40(%rax)
  162e: valignd        $0x5,%ymm1,%ymm1,%ymm3
  1635: vmovss         %xmm3,-0x30(%rax)
  163a: valignd        $0x6,%ymm1,%ymm1,%ymm3
  1641: valignd        $0x7,%ymm1,%ymm1,%ymm1
  1648: vmovss         %xmm3,-0x20(%rax)
   ... (3 more instructions)
```

## `saxpy_s4_f32` — `avx512`

```asm
  2260: vmovups        (%rdx),%zmm0
  2266: vmovups        0x80(%rdx),%zmm1
  226d: add            $0x100,%rdx
  2274: add            $0x100,%rax
  227a: vmovups        -0x80(%rax),%zmm3
  2281: vpermt2ps      -0x40(%rdx),%zmm2,%zmm1
  2288: vpermt2ps      -0xc0(%rdx),%zmm2,%zmm0
  228f: vpermt2ps      %zmm1,%zmm2,%zmm0
  2295: vmovups        -0x100(%rax),%zmm1
  229c: vpermt2ps      -0x40(%rax),%zmm2,%zmm3
  22a3: vpermt2ps      -0xc0(%rax),%zmm2,%zmm1
  22aa: vpermt2ps      %zmm3,%zmm2,%zmm1
  22b0: vfmadd132ps    %zmm5,%zmm1,%zmm0
  22b6: vextractf32x4  $0x1,%ymm0,%xmm3
  22bd: vmovss         %xmm0,-0x100(%rax)
  22c5: vextractps     $0x1,%xmm0,-0xf0(%rax)
  22cf: vextractps     $0x2,%xmm0,-0xe0(%rax)
  22d9: valignd        $0x7,%ymm0,%ymm0,%ymm1
  22e0: vextractps     $0x3,%xmm0,-0xd0(%rax)
  22ea: vmovss         %xmm3,-0xc0(%rax)
  22f2: valignd        $0x5,%ymm0,%ymm0,%ymm3
  22f9: vmovss         %xmm1,-0x90(%rax)
  2301: vmovss         %xmm3,-0xb0(%rax)
  2309: valignd        $0x6,%ymm0,%ymm0,%ymm3
   ... (16 more instructions)
```

## `saxpy_gather_f32` — `scalar`

```asm
   6e0: mov            (%rsi,%rax,4),%edi
   6e3: movss          (%rdx,%rdi,4),%xmm1
   6e8: mulss          %xmm0,%xmm1
   6ec: addss          (%rcx,%rax,4),%xmm1
   6f1: movss          %xmm1,(%rcx,%rax,4)
   6f6: add            $0x1,%rax
   6fa: cmp            %rax,%r8
   6fd: jne            6e0 <saxpy_gather_f32+0x10>
```

## `saxpy_gather_f32` — `scalar_native`

```asm
   710: mov            (%rsi,%rax,4),%r8d
   714: vmovss         (%rdx,%r8,4),%xmm1
   71a: vfmadd213ss    (%rcx,%rax,4),%xmm0,%xmm1
   720: vmovss         %xmm1,(%rcx,%rax,4)
   725: inc            %rax
   728: cmp            %rax,%rdi
   72b: jne            710 <saxpy_gather_f32+0x10>
```

## `saxpy_gather_f32` — `sse2`

```asm
  11c0: lea            (%rdi,%rax,1),%rcx
  11c4: movups         (%rsi,%rax,1),%xmm5
  11c8: mov            (%rcx),%r9d
  11cb: mov            0x4(%rcx),%r10d
  11cf: mov            0x8(%rcx),%r11d
  11d3: mov            0xc(%rcx),%ecx
  11d6: movss          (%rdx,%r10,4),%xmm3
  11dc: movss          (%rdx,%rcx,4),%xmm1
  11e1: movss          (%rdx,%r11,4),%xmm2
  11e7: unpcklps       %xmm1,%xmm2
  11ea: movss          (%rdx,%r9,4),%xmm1
  11f0: unpcklps       %xmm3,%xmm1
  11f3: movlhps        %xmm2,%xmm1
  11f6: mulps          %xmm4,%xmm1
  11f9: addps          %xmm5,%xmm1
  11fc: movups         %xmm1,(%rsi,%rax,1)
  1200: add            $0x10,%rax
  1204: cmp            %rbx,%rax
  1207: jne            11c0 <saxpy_gather_f32+0x40>
```

## `saxpy_gather_f32` — `avx2`

```asm
  1ae8: lea            (%rsi,%rcx,1),%rdx
  1aec: mov            (%rdx),%r11d
  1aef: mov            0x4(%rdx),%r10d
  1af3: mov            0x8(%rdx),%r12d
  1af7: mov            0xc(%rdx),%ebx
  1afa: mov            0x10(%rdx),%r14d
  1afe: mov            0x14(%rdx),%r13d
  1b02: mov            0x18(%rdx),%r15d
  1b06: mov            0x1c(%rdx),%edx
  1b09: vmovss         (%rax,%r14,4),%xmm1
  1b0f: vinsertps      $0x10,(%rax,%r13,4),%xmm1,%xmm1
  1b16: vmovss         (%rax,%r15,4),%xmm0
  1b1c: vinsertps      $0x10,(%rax,%rdx,4),%xmm0,%xmm0
  1b23: vmovss         (%rax,%r12,4),%xmm2
  1b29: vinsertps      $0x10,(%rax,%rbx,4),%xmm2,%xmm2
  1b30: vmovlhps       %xmm0,%xmm1,%xmm1
  1b34: vmovss         (%rax,%r11,4),%xmm0
  1b3a: vinsertps      $0x10,(%rax,%r10,4),%xmm0,%xmm0
  1b41: vmovlhps       %xmm2,%xmm0,%xmm0
  1b45: vinsertf128    $0x1,%xmm1,%ymm0,%ymm0
  1b4b: vfmadd213ps    (%r8,%rcx,1),%ymm4,%ymm0
  1b51: vmovups        %ymm0,(%r8,%rcx,1)
  1b57: add            $0x20,%rcx
  1b5b: cmp            %rcx,%r9
   ... (1 more instructions)
```

## `saxpy_gather_f32` — `native`

```asm
  1a30: lea            (%rsi,%rcx,1),%rdx
  1a34: mov            0x10(%rdx),%r14d
  1a38: mov            0x18(%rdx),%r15d
  1a3c: mov            (%rdx),%r11d
  1a3f: mov            0x4(%rdx),%r10d
  1a43: mov            0x8(%rdx),%r12d
  1a47: mov            0xc(%rdx),%ebx
  1a4a: mov            0x14(%rdx),%r13d
  1a4e: vmovss         (%rax,%r15,4),%xmm2
  1a54: mov            0x1c(%rdx),%edx
  1a57: vmovss         (%rax,%r14,4),%xmm1
  1a5d: vmovss         (%rax,%r12,4),%xmm3
  1a63: vinsertps      $0x10,(%rax,%r13,4),%xmm1,%xmm1
  1a6a: vinsertps      $0x10,(%rax,%rdx,4),%xmm2,%xmm2
  1a71: vinsertps      $0x10,(%rax,%rbx,4),%xmm3,%xmm3
  1a78: vmovlhps       %xmm2,%xmm1,%xmm2
  1a7c: vmovss         (%rax,%r11,4),%xmm1
  1a82: vinsertps      $0x10,(%rax,%r10,4),%xmm1,%xmm1
  1a89: vmovlhps       %xmm3,%xmm1,%xmm1
  1a8d: vinsertf128    $0x1,%xmm2,%ymm1,%ymm1
  1a93: vfmadd213ps    (%r8,%rcx,1),%ymm4,%ymm1
  1a99: vmovups        %ymm1,(%r8,%rcx,1)
  1a9f: add            $0x20,%rcx
  1aa3: cmp            %rcx,%r9
   ... (1 more instructions)
```

## `saxpy_gather_f32` — `avx512`

```asm
  2e70: mov            -0x30(%rsp),%rax
  2e75: add            %rdx,%rax
  2e78: mov            (%rax),%ebx
  2e7a: mov            0x4(%rax),%edi
  2e7d: mov            0x8(%rax),%esi
  2e80: mov            0xc(%rax),%ecx
  2e83: mov            0x14(%rax),%r8d
  2e87: mov            0x30(%rax),%r12d
  2e8b: mov            %rbx,-0x8(%rsp)
  2e90: mov            0x38(%rax),%r13d
  2e94: mov            0x34(%rax),%ebx
  2e97: mov            %rdi,-0x10(%rsp)
  2e9c: mov            0x20(%rax),%r9d
  2ea0: mov            0x18(%rax),%edi
  2ea3: mov            %rsi,-0x18(%rsp)
  2ea8: mov            0x28(%rax),%r11d
  2eac: mov            0x1c(%rax),%esi
  2eaf: mov            %rcx,-0x20(%rsp)
  2eb4: mov            0x2c(%rax),%r10d
  2eb8: mov            0x10(%rax),%ecx
  2ebb: mov            %r8,-0x28(%rsp)
  2ec0: vmovss         (%r14,%r13,4),%xmm2
  2ec6: mov            0x24(%rax),%r8d
  2eca: vmovss         (%r14,%r12,4),%xmm0
   ... (32 more instructions)
```

