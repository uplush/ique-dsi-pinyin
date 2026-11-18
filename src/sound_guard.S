/* iQue DSi Sound input worker: skip only the sound tick until its object exists.
 * Reference assembly for the validated HNKC version, placed at 0x0201133c.
 * This is an application-side compatibility workaround, not an emulator timing fix.
 */
.syntax unified
.arm
.section .text
.global sound_input_tick
sound_input_tick:
    push {r3, lr}
    mov r3, r0
    ldr r0, object_pointer
    ldr r0, [r0]
    cmp r0, #0
    popeq {r3, pc}
    ldr r2, [r3, #0x148]
    mov r1, #0x30
    mla r3, r2, r1, r3
    ldr r3, [r3, #0x110]
    cmp r3, #0
    pop {r3, lr}
    bne 0x0205fb1c
    b 0x0205f9c4
    nop
object_pointer:
    .word 0x020ece48
