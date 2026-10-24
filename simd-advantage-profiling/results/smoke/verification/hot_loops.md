# Hot-loop excerpts (targeted disassembly)

Inner loop only (backward-branch body with the most packed work), truncated to 24 lines.

## `saxpy_f32` — `scalar`

```asm
    40: movss          (%r8,%rax,4),%xmm0
    46: mulss          %xmm1,%xmm0
    4a: addss          (%r9,%rax,4),%xmm0
    50: movss          %xmm0,(%r9,%rax,4)
    56: add            $0x1,%rax
    5a: cmp            %rax,%rcx
    5d: jne            40 <saxpy_f32+0x40>
```

## `saxpy_f32` — `scalar_native`

```asm
    40: vmovss         (%r8,%rax,4),%xmm0
    46: vfmadd213ss    (%r9,%rax,4),%xmm1,%xmm0
    4c: vmovss         %xmm0,(%r9,%rax,4)
    52: inc            %rax
    55: cmp            %rax,%rcx
    58: jne            40 <saxpy_f32+0x40>
```

## `saxpy_f32` — `sse2`

```asm
    40: movups         (%r8,%rax,1),%xmm0
    45: movups         (%r9,%rax,1),%xmm4
    4a: mulps          %xmm2,%xmm0
    4d: addps          %xmm4,%xmm0
    50: movups         %xmm0,(%r9,%rax,1)
    55: add            $0x10,%rax
    59: cmp            %r10,%rax
    5c: jne            40 <saxpy_f32+0x40>
```

## `saxpy_f32` — `avx2`

```asm
    40: vmovups        (%r8,%rax,1),%ymm0
    46: vfmadd213ps    (%r9,%rax,1),%ymm2,%ymm0
    4c: vmovups        %ymm0,(%r9,%rax,1)
    52: add            $0x20,%rax
    56: cmp            %rcx,%rax
    59: jne            40 <saxpy_f32+0x40>
```

## `saxpy_f32` — `native`

```asm
    40: vmovups        (%r8,%rax,1),%ymm0
    46: vfmadd213ps    (%r9,%rax,1),%ymm2,%ymm0
    4c: vmovups        %ymm0,(%r9,%rax,1)
    52: add            $0x20,%rax
    56: cmp            %rcx,%rax
    59: jne            40 <saxpy_f32+0x40>
```

## `dot_f32` — `scalar`

```asm
    c0: movss          (%rdx,%rax,4),%xmm0
    c5: mulss          (%r8,%rax,4),%xmm0
    cb: add            $0x1,%rax
    cf: addss          %xmm0,%xmm1
    d3: cmp            %rax,%rcx
    d6: jne            c0 <dot_f32+0x40>
```

## `dot_f32` — `scalar_native`

```asm
    c0: vmovss         (%rdx,%rax,4),%xmm0
    c5: vmulss         (%r8,%rax,4),%xmm0,%xmm0
    cb: inc            %rax
    ce: vaddss         %xmm0,%xmm1,%xmm1
    d2: cmp            %rax,%rcx
    d5: jne            c0 <dot_f32+0x40>
```

## `dot_f32` — `sse2`

```asm
   100: movups         (%rdx,%rax,1),%xmm1
   104: movups         (%r8,%rax,1),%xmm3
   109: add            $0x10,%rax
   10d: mulps          %xmm3,%xmm1
   110: addss          %xmm1,%xmm0
   114: movups         %xmm1,%xmm2
   117: shufps         $0x55,%xmm1,%xmm2
   11b: addss          %xmm2,%xmm0
   11f: movups         %xmm1,%xmm2
   122: unpckhps       %xmm1,%xmm2
   125: shufps         $0xff,%xmm1,%xmm1
   129: addss          %xmm2,%xmm0
   12d: addss          %xmm1,%xmm0
   131: cmp            %r10,%rax
   134: jne            100 <dot_f32+0x40>
```

## `dot_f32` — `avx2`

```asm
   140: vmovups        (%r8,%rax,1),%ymm1
   146: vmulps         (%rdx,%rax,1),%ymm1,%ymm1
   14b: add            $0x20,%rax
   14f: vaddss         %xmm1,%xmm0,%xmm0
   153: vshufps        $0x55,%xmm1,%xmm1,%xmm3
   158: vshufps        $0xff,%xmm1,%xmm1,%xmm2
   15d: vaddss         %xmm3,%xmm0,%xmm0
   161: vunpckhps      %xmm1,%xmm1,%xmm3
   165: vextractf128   $0x1,%ymm1,%xmm1
   16b: vaddss         %xmm3,%xmm0,%xmm0
   16f: vaddss         %xmm2,%xmm0,%xmm0
   173: vshufps        $0x55,%xmm1,%xmm1,%xmm2
   178: vaddss         %xmm1,%xmm0,%xmm0
   17c: vaddss         %xmm2,%xmm0,%xmm0
   180: vunpckhps      %xmm1,%xmm1,%xmm2
   184: vshufps        $0xff,%xmm1,%xmm1,%xmm1
   189: vaddss         %xmm2,%xmm0,%xmm0
   18d: vaddss         %xmm1,%xmm0,%xmm0
   191: cmp            %rax,%r10
   194: jne            140 <dot_f32+0x40>
```

## `dot_f32` — `native`

```asm
   140: vmovups        (%r8,%rcx,1),%ymm1
   146: vmulps         (%rdx,%rcx,1),%ymm1,%ymm1
   14b: add            $0x20,%rcx
   14f: vshufps        $0x55,%xmm1,%xmm1,%xmm3
   154: vshufps        $0xff,%xmm1,%xmm1,%xmm2
   159: vaddss         %xmm1,%xmm0,%xmm0
   15d: vaddss         %xmm3,%xmm0,%xmm0
   161: vunpckhps      %xmm1,%xmm1,%xmm3
   165: vextractf128   $0x1,%ymm1,%xmm1
   16b: vaddss         %xmm3,%xmm0,%xmm0
   16f: vaddss         %xmm2,%xmm0,%xmm0
   173: vshufps        $0x55,%xmm1,%xmm1,%xmm2
   178: vaddss         %xmm1,%xmm0,%xmm0
   17c: vaddss         %xmm2,%xmm0,%xmm0
   180: vunpckhps      %xmm1,%xmm1,%xmm2
   184: vshufps        $0xff,%xmm1,%xmm1,%xmm1
   189: vaddss         %xmm2,%xmm0,%xmm0
   18d: vaddss         %xmm1,%xmm0,%xmm0
   191: cmp            %rcx,%r10
   194: jne            140 <dot_f32+0x40>
```

## `dotsimd_f32` — `scalar`

```asm
   140: movss          (%rdx,%rax,4),%xmm0
   145: mulss          (%r8,%rax,4),%xmm0
   14b: add            $0x1,%rax
   14f: addss          %xmm0,%xmm1
   153: cmp            %rax,%rcx
   156: jne            140 <dotsimd_f32+0x40>
```

## `dotsimd_f32` — `scalar_native`

```asm
   140: vmovss         (%rdx,%rax,4),%xmm0
   145: vmulss         (%r8,%rax,4),%xmm0,%xmm0
   14b: inc            %rax
   14e: vaddss         %xmm0,%xmm1,%xmm1
   152: cmp            %rax,%rcx
   155: jne            140 <dotsimd_f32+0x40>
```

## `dotsimd_f32` — `sse2`

```asm
   200: movups         (%rdx,%rax,1),%xmm0
   204: movups         (%r8,%rax,1),%xmm2
   209: add            $0x10,%rax
   20d: mulps          %xmm2,%xmm0
   210: addps          %xmm0,%xmm1
   213: cmp            %r10,%rax
   216: jne            200 <dotsimd_f32+0x40>
```

## `dotsimd_f32` — `avx2`

```asm
   2c0: vmovups        (%r8,%rax,1),%ymm1
   2c6: vmulps         (%rcx,%rax,1),%ymm1,%ymm1
   2cb: add            $0x20,%rax
   2cf: vaddps         %ymm0,%ymm1,%ymm0
   2d3: cmp            %r10,%rax
   2d6: jne            2c0 <dotsimd_f32+0x40>
```

## `dotsimd_f32` — `native`

```asm
   2c0: vmovups        (%r8,%rax,1),%ymm1
   2c6: vmulps         (%rdx,%rax,1),%ymm1,%ymm1
   2cb: add            $0x20,%rax
   2cf: vaddps         %ymm0,%ymm1,%ymm0
   2d3: cmp            %r10,%rax
   2d6: jne            2c0 <dotsimd_f32+0x40>
```

## `dot_i32` — `scalar`

```asm
   7c0: mov            (%rdx,%rax,4),%r9d
   7c4: imul           (%r8,%rax,4),%r9d
   7c9: add            $0x1,%rax
   7cd: add            %r9d,%r10d
   7d0: cmp            %rax,%rcx
   7d3: jne            7c0 <dot_i32+0x40>
```

## `dot_i32` — `scalar_native`

```asm
   6c0: mov            (%rdx,%rax,4),%r9d
   6c4: imul           (%r8,%rax,4),%r9d
   6c9: inc            %rax
   6cc: add            %r9d,%r10d
   6cf: cmp            %rax,%rcx
   6d2: jne            6c0 <dot_i32+0x40>
```

## `dot_i32` — `sse2`

```asm
   a80: movdqu         (%rdx,%rax,1),%xmm0
   a85: movdqu         (%r8,%rax,1),%xmm2
   a8b: add            $0x10,%rax
   a8f: movdqu         %xmm0,%xmm1
   a93: psrlq          $0x20,%xmm0
   a98: pmuludq        %xmm2,%xmm1
   a9c: psrlq          $0x20,%xmm2
   aa1: pmuludq        %xmm2,%xmm0
   aa5: pshufd         $0x8,%xmm1,%xmm1
   aaa: pshufd         $0x8,%xmm0,%xmm0
   aaf: punpckldq      %xmm0,%xmm1
   ab3: paddd          %xmm1,%xmm3
   ab7: cmp            %r9,%rax
   aba: jne            a80 <dot_i32+0x40>
```

## `dot_i32` — `avx2`

```asm
   d00: vmovdqu        (%r8,%rax,1),%ymm0
   d06: vpmulld        (%r9,%rax,1),%ymm0,%ymm0
   d0c: add            $0x20,%rax
   d10: vpaddd         %ymm0,%ymm1,%ymm1
   d14: cmp            %rax,%rcx
   d17: jne            d00 <dot_i32+0x40>
```

## `dot_i32` — `native`

```asm
   d40: vmovdqu        (%r8,%rax,1),%ymm0
   d46: vpmulld        (%r9,%rax,1),%ymm0,%ymm0
   d4c: add            $0x20,%rax
   d50: vpaddd         %ymm0,%ymm1,%ymm1
   d54: cmp            %rax,%rcx
   d57: jne            d40 <dot_i32+0x40>
```

## `saxpy_s4_f32` — `scalar`

```asm
   c80: movss          (%r8,%rax,1),%xmm0
   c86: mulss          %xmm1,%xmm0
   c8a: addss          (%r9,%rax,1),%xmm0
   c90: movss          %xmm0,(%r9,%rax,1)
   c96: add            $0x10,%rax
   c9a: cmp            %rax,%rcx
   c9d: jne            c80 <saxpy_s4_f32+0x40>
```

## `saxpy_s4_f32` — `scalar_native`

```asm
   b80: vmovss         (%r8,%rax,1),%xmm0
   b86: vfmadd213ss    (%r9,%rax,1),%xmm1,%xmm0
   b8c: vmovss         %xmm0,(%r9,%rax,1)
   b92: add            $0x10,%rax
   b96: cmp            %rax,%rcx
   b99: jne            b80 <saxpy_s4_f32+0x40>
```

## `saxpy_s4_f32` — `sse2`

```asm
  1300: movups         0x10(%rdx),%xmm5
  1304: movups         (%rdx),%xmm0
  1307: add            $0x40,%rdx
  130b: add            $0x40,%rax
  130f: movups         -0x20(%rdx),%xmm2
  1313: movss          -0x10(%rdx),%xmm3
  1318: shufps         $0x88,%xmm5,%xmm0
  131c: movups         -0x30(%rax),%xmm5
  1320: shufps         $0x88,%xmm3,%xmm2
  1324: shufps         $0x88,%xmm2,%xmm0
  1328: mulps          %xmm4,%xmm0
  132b: movups         -0x40(%rax),%xmm2
  132f: movups         -0x20(%rax),%xmm3
  1333: shufps         $0x88,%xmm5,%xmm2
  1337: movss          -0x10(%rax),%xmm5
  133c: shufps         $0x88,%xmm5,%xmm3
  1340: shufps         $0x88,%xmm3,%xmm2
  1344: addps          %xmm2,%xmm0
  1347: movups         %xmm0,%xmm2
  134a: movss          %xmm0,-0x40(%rax)
  134f: shufps         $0x55,%xmm0,%xmm2
  1353: movss          %xmm2,-0x30(%rax)
  1358: movups         %xmm0,%xmm2
  135b: unpckhps       %xmm0,%xmm2
   ... (5 more instructions)
```

## `saxpy_s4_f32` — `avx2`

```asm
  1800: vpermd         (%rdx),%ymm4,%ymm0
  1805: vpermd         0x20(%rdx),%ymm3,%ymm2
  180b: sub            $0xffffffffffffff80,%rdx
  180f: sub            $0xffffffffffffff80,%rax
  1813: vpermd         -0x40(%rdx),%ymm4,%ymm5
  1819: vpermd         -0x40(%rax),%ymm4,%ymm7
  181f: vblendps       $0xf,%ymm0,%ymm2,%ymm2
  1825: vpermd         -0x20(%rdx),%ymm3,%ymm0
  182b: vpermd         %ymm2,%ymm4,%ymm2
  1830: vblendps       $0xf,%ymm5,%ymm0,%ymm0
  1836: vpermd         -0x60(%rax),%ymm3,%ymm5
  183c: vpermd         %ymm0,%ymm3,%ymm0
  1841: vblendps       $0xf,%ymm2,%ymm0,%ymm0
  1847: vpermd         -0x80(%rax),%ymm4,%ymm2
  184d: vblendps       $0xf,%ymm2,%ymm5,%ymm5
  1853: vpermd         -0x20(%rax),%ymm3,%ymm2
  1859: vpermd         %ymm5,%ymm4,%ymm5
  185e: vblendps       $0xf,%ymm7,%ymm2,%ymm2
  1864: vpermd         %ymm2,%ymm3,%ymm2
  1869: vblendps       $0xf,%ymm5,%ymm2,%ymm2
  186f: vfmadd132ps    %ymm1,%ymm2,%ymm0
  1874: vmovss         %xmm0,-0x80(%rax)
  1879: vextractps     $0x1,%xmm0,-0x70(%rax)
  1880: vextractps     $0x2,%xmm0,-0x60(%rax)
   ... (8 more instructions)
```

## `saxpy_s4_f32` — `native`

```asm
  1840: vpermd         (%rdx),%ymm4,%ymm0
  1845: vpermd         0x20(%rdx),%ymm3,%ymm2
  184b: sub            $0xffffffffffffff80,%rdx
  184f: sub            $0xffffffffffffff80,%rax
  1853: vpermd         -0x40(%rdx),%ymm4,%ymm5
  1859: vpermd         -0x40(%rax),%ymm4,%ymm6
  185f: vblendps       $0xf,%ymm0,%ymm2,%ymm2
  1865: vpermd         -0x20(%rdx),%ymm3,%ymm0
  186b: vpermd         %ymm2,%ymm4,%ymm2
  1870: vblendps       $0xf,%ymm5,%ymm0,%ymm0
  1876: vpermd         -0x60(%rax),%ymm3,%ymm5
  187c: vpermd         %ymm0,%ymm3,%ymm0
  1881: vblendps       $0xf,%ymm2,%ymm0,%ymm0
  1887: vpermd         -0x80(%rax),%ymm4,%ymm2
  188d: vblendps       $0xf,%ymm2,%ymm5,%ymm5
  1893: vpermd         -0x20(%rax),%ymm3,%ymm2
  1899: vpermd         %ymm5,%ymm4,%ymm5
  189e: vblendps       $0xf,%ymm6,%ymm2,%ymm2
  18a4: vpermd         %ymm2,%ymm3,%ymm2
  18a9: vblendps       $0xf,%ymm5,%ymm2,%ymm2
  18af: vfmadd132ps    %ymm1,%ymm2,%ymm0
  18b4: vmovss         %xmm0,-0x80(%rax)
  18b9: vextractps     $0x1,%xmm0,-0x70(%rax)
  18c0: vextractps     $0x2,%xmm0,-0x60(%rax)
   ... (8 more instructions)
```

## `saxpy_gather_f32` — `scalar`

```asm
   e00: mov            (%r8,%rax,4),%r10d
   e04: movss          (%r9,%r10,4),%xmm0
   e0a: mulss          %xmm1,%xmm0
   e0e: addss          (%rdx,%rax,4),%xmm0
   e13: movss          %xmm0,(%rdx,%rax,4)
   e18: add            $0x1,%rax
   e1c: cmp            %rax,%rcx
   e1f: jne            e00 <saxpy_gather_f32+0x40>
```

## `saxpy_gather_f32` — `scalar_native`

```asm
   d00: mov            (%r8,%rax,4),%r10d
   d04: vmovss         (%r9,%r10,4),%xmm0
   d0a: vfmadd213ss    (%rdx,%rax,4),%xmm1,%xmm0
   d10: vmovss         %xmm0,(%rdx,%rax,4)
   d15: inc            %rax
   d18: cmp            %rax,%rcx
   d1b: jne            d00 <saxpy_gather_f32+0x40>
```

## `saxpy_gather_f32` — `sse2`

```asm
  1540: lea            (%rbx,%rax,1),%rdx
  1544: movups         (%rcx,%rax,1),%xmm5
  1548: mov            (%rdx),%r10d
  154b: mov            0x4(%rdx),%r11d
  154f: mov            0x8(%rdx),%r8d
  1553: mov            0xc(%rdx),%edx
  1556: movss          (%r9,%r11,4),%xmm3
  155c: movss          (%r9,%rdx,4),%xmm0
  1562: movss          (%r9,%r8,4),%xmm2
  1568: unpcklps       %xmm0,%xmm2
  156b: movss          (%r9,%r10,4),%xmm0
  1571: unpcklps       %xmm3,%xmm0
  1574: movlhps        %xmm2,%xmm0
  1577: mulps          %xmm4,%xmm0
  157a: addps          %xmm5,%xmm0
  157d: movups         %xmm0,(%rcx,%rax,1)
  1581: add            $0x10,%rax
  1585: cmp            %rax,%rdi
  1588: jne            1540 <saxpy_gather_f32+0x40>
```

## `saxpy_gather_f32` — `avx2`

```asm
  1b80: lea            (%r8,%rax,1),%rdx
  1b84: mov            (%rdx),%r11d
  1b87: mov            0x4(%rdx),%r10d
  1b8b: mov            0x8(%rdx),%ebp
  1b8e: mov            0xc(%rdx),%edx
  1b91: vmovss         (%r9,%r11,4),%xmm0
  1b97: vinsertps      $0x10,(%r9,%r10,4),%xmm0,%xmm0
  1b9e: vmovss         (%r9,%rbp,4),%xmm2
  1ba4: vinsertps      $0x10,(%r9,%rdx,4),%xmm2,%xmm2
  1bab: vmovlhps       %xmm2,%xmm0,%xmm0
  1baf: vfmadd213ps    (%rcx,%rax,1),%xmm3,%xmm0
  1bb5: vmovups        %xmm0,(%rcx,%rax,1)
  1bba: add            $0x10,%rax
  1bbe: cmp            %rax,%rsi
  1bc1: jne            1b80 <saxpy_gather_f32+0x40>
```

## `saxpy_gather_f32` — `native`

```asm
  1e40: lea            (%r8,%rax,1),%rdx
  1e44: mov            (%rdx),%r11d
  1e47: mov            0x8(%rdx),%ebp
  1e4a: mov            0x4(%rdx),%r10d
  1e4e: mov            0xc(%rdx),%edx
  1e51: vmovss         (%r9,%rbp,4),%xmm2
  1e57: vmovss         (%r9,%r11,4),%xmm0
  1e5d: vinsertps      $0x10,(%r9,%rdx,4),%xmm2,%xmm2
  1e64: vinsertps      $0x10,(%r9,%r10,4),%xmm0,%xmm0
  1e6b: vmovlhps       %xmm2,%xmm0,%xmm0
  1e6f: vfmadd213ps    (%rcx,%rax,1),%xmm3,%xmm0
  1e75: vmovups        %xmm0,(%rcx,%rax,1)
  1e7a: add            $0x10,%rax
  1e7e: cmp            %rax,%rsi
  1e81: jne            1e40 <saxpy_gather_f32+0x40>
```

