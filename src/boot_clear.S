.syntax unified
.arm
.section .text.boot_clear,"ax"
.global bss_end_original
.type bss_end_original,%function
bss_end_original:
    ldr r2, 1f
    bx lr
1:  .word 0x0218e300

.thumb
.align 2
.section .text.native_hit_test,"ax"
.global native_hit_test
.type native_hit_test,%function
.thumb_func
native_hit_test:
    /* Original 0x02039b8c..0x02039b93, none PC-relative. */
    push {r4,r5,r6,r7,lr}
    sub sp, #0x14
    str r0, [sp]
    movs r0, r2
    ldr r3, 2f
    bx r3
.align 2
2:  .word 0x02039b95
