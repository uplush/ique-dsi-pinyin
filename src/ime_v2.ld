ENTRY(pinyin_hook)
SECTIONS {
 . = 0x01ff8400;
 .text : { *(.text*) *(.rodata*) }
 . = ALIGN(4);
 __bss_start = .;
 .bss : { *(.bss*) *(COMMON) }
 __bss_end = .;
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment) *(.note*) }
}
ASSERT(__bss_end < 0x01ffff00, "IME code and state exceed the ITCM allowance")
