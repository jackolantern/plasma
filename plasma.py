#!/usr/bin/env python
"""
A Plasma "Demo".
"""

import sys
import math
from multiprocessing import Process, Queue

from migen import If, Cat, Memory, Signal, Module, run_simulation, ClockDomain
from migen.fhdl import verilog


class Color6:
    """
    Six-bit Color
    """
    def __init__(self):
        self.r0 = Signal()
        self.r1 = Signal()
        self.g0 = Signal()
        self.g1 = Signal()
        self.b0 = Signal()
        self.b1 = Signal()

    def color(self, r0, r1, g0, g1, b0, b1):
        """
        Set the color of the current pixel.
        """
        return [
            self.r0.eq(r0),
            self.r1.eq(r1),
            self.g0.eq(g0),
            self.g1.eq(g1),
            self.b0.eq(b0),
            self.b1.eq(b1)
        ]

    def black(self):
        """
        Set the color to black.
        """
        return self.color(0, 0, 0, 0, 0, 0)


class VGA(Module):
    """
    VGA Module
    """
    hpixels = 800
    vlines = 521  ## vertical lines per frame
    hpulse = 96   ## hsync pulse length
    vpulse = 3    ## vsync pulse length
    hbp = 144     ## end of horizontal back porch
    hfp = 784     ## beginning of horizontal front porch
    vbp = 31      ## end of vertical back porch
    vfp = 511     ## beginning of vertical front porch
    ## active horizontal video is therefore: 784 - 144 = 640
    ## active vertical video is therefore: 511 - 31 = 480

    def __init__(self):
        self.hc = Signal(bits_sign=10)
        self.vc = Signal(bits_sign=10)
        self.hsync = Signal()
        self.vsync = Signal()
        self.color = Color6()

        self.comb += trinary(self.hc < VGA.hpulse, self.hsync.eq(0), self.hsync.eq(1))
        self.comb += trinary(self.vc < VGA.hpulse, self.vsync.eq(0), self.vsync.eq(1))

        self.sync += If(self.hc < VGA.hpixels - 1, [
            self.hc.eq(self.hc + 1)
        ]).Else([
            self.hc.eq(0),
            If(self.vc < VGA.vlines - 1, [
                self.vc.eq(self.vc + 1)
            ]).Else([
                self.vc.eq(0)
            ])
        ])


def calc_index(pos, sin, port, acc=True, zero=False):
    block = If(pos < 128, [
        port.adr.eq(pos),
        sin.eq(sin + port.dat_r) if acc else sin.eq(port.dat_r)
    ]).Elif(pos < 256, [
        port.adr.eq(127 - (pos - 128)),
        sin.eq(sin + port.dat_r) if acc else sin.eq(port.dat_r)
    ])
    if zero:
        block = block.Elif(pos == 256, [sin.eq(0)])
    block = block.Elif(pos < 512 - 128, [
        port.adr.eq(512 - 128 - pos),
        sin.eq(sin + port.dat_r) if acc else sin.eq(port.dat_r)
    ]).Else([
        port.adr.eq(512 - pos - 1),
        sin.eq(sin + port.dat_r) if acc else sin.eq(port.dat_r)
    ])
    return block


class Plasma(Module):
    """
    Plasma Module
    """
    def __init__(self, vga, sin_t, col_t):
        pos1 = Signal(bits_sign=9)
        pos3 = Signal(bits_sign=9)
        tpos1 = Signal(bits_sign=9)
        tpos2 = Signal(bits_sign=9)
        tpos3 = Signal(bits_sign=9)
        tpos4 = Signal(bits_sign=9)

        index = Signal(bits_sign=6)
        count = Signal()

        self.specials.col_t = Memory(4, 256, init=col_t)
        self.specials.sin_t = Memory(32, 512, init=sin_t)
        sin_p = self.sin_t.get_port(async_read=True)
        col_p = self.col_t.get_port(async_read=True)

        self.specials += sin_p
        self.specials += col_p
        self.ios = {sin_p.adr, sin_p.dat_r, col_p.adr, col_p.dat_r}

        sin = Signal(bits_sign=(32, True))

        self.sync += If(vga.hc < VGA.hpixels - 1, [
            If((vga.hc >= VGA.hbp) & (vga.hc < VGA.hfp), [
                tpos1.eq(tpos1 + 5),
                tpos2.eq(tpos2 + 3)
            ])
        ]).Else([
            If(vga.vc < VGA.vlines - 1, [
                If((vga.vc >= VGA.vbp) & (vga.vc < VGA.vfp), [
                    tpos1.eq(pos1 + 5),
                    tpos2.eq(3),
                    tpos3.eq(tpos3 + 1),
                    tpos4.eq(tpos4 + 3)
                ])
            ]).Else([
                pos1.eq(pos1 + 9),
                pos3.eq(pos3 + 8),
                tpos4.eq(0),
                tpos3.eq(0),
                count.eq(count + 1)
            ])
        ])

        self.sync += If((vga.vc >= VGA.vbp) & (vga.vc < VGA.vfp), [
            If((vga.hc >= VGA.hbp) & (vga.hc < VGA.hfp), [
                calc_index(tpos1, sin, sin_p, acc=False, zero=True),
                calc_index(tpos2, sin, sin_p),
                calc_index(tpos3, sin, sin_p),
                calc_index(tpos4, sin, sin_p),

                index.eq(sin >> 4),

                col_p.adr.eq(index),
                Cat(vga.color.g1, vga.color.g0, vga.color.r1, vga.color.r0).eq(col_p.dat_r)
            ]).Else(vga.color.black())
        ]).Else(vga.color.black())


class TestBench(Module):
    """
    TestBench Module
    """
    def __init__(self):
        sin_t = tuple(make_sin_t())
        col_t = make_color_t()

        self.vga = VGA()
        self.plasma = Plasma(self.vga, sin_t, col_t)
        self.submodules += self.vga
        self.submodules += self.plasma


def trinary(cond, ifTrue, ifFalse):
    """
    Convenience function faking a trinary operator.
    """
    return If(cond, [ifTrue]).Else([ifFalse])


def scale(c0, c1):
    """
    Scales 2 bit color to 8 bits.
    """
    return min((c0 * 3 * 64) + (c1 * 64), 255)


def shrinkify(n):
    """
    Shrinks 8 bit color to 2 bits.
    """
    if n < 4:
        return 0
    elif 64 < n and n < 128:
        return 1
    elif 128 < n and n < 128 + 64:
        return 2
    else:
        return 3


def make_sin_t():
    """
    Make a sin table.
    """
    for i in range(512):
        rad = (i * 0.703125) * 0.0174532
        value = math.floor(math.sin(rad) * 1024)
        yield value


def make_color_t():
    """
    Make a color table.
    """
    color = [0 for _ in range(256)]
    for i in range(64):
        color[i] = (shrinkify(i << 2) << 2) + shrinkify(255 - ((i << 2) + 1))
        color[i + 64] = (shrinkify(255) << 2) + shrinkify((i << 2) + 1)
        color[i + 128] = (shrinkify(255 - ((i << 2) + 1)) << 2) + shrinkify(255 - ((i << 2) + 1))
        color[i + 192] = shrinkify((i << 2) + 1)
    return color


def view():
    dut = TestBench()
    dut.clock_domains.cd_sys = ClockDomain("sys")

    def setup_view(q):
        import view
        v = view.Veiw(VGA.hpixels, VGA.vlines, VGA.hfp, VGA.hbp, VGA.vfp, VGA.vbp)
        v.run(q)

    q = Queue()
    p = Process(target=setup_view, args=(q,))
    p.start()

    def testbench():
        """
        Tesbench
        """
        step = 0
        line = []
        prev_vc = 0
        while True:
            hc = yield dut.vga.hc
            vc = yield dut.vga.vc
            r0 = yield dut.vga.color.r0
            r1 = yield dut.vga.color.r1
            g0 = yield dut.vga.color.g0
            g1 = yield dut.vga.color.g1
            assert hc == step % VGA.hpixels
            assert vc == (step // VGA.hpixels) % VGA.vlines
            if prev_vc != vc and line:
                q.put((vc, line))
                line = []
            line.append((scale(r0, r1), scale(g0, g1), 0))
            prev_vc = vc
            yield
            step += 1

    run_simulation(dut, testbench())


def simulate():
    dut = TestBench()
    dut.clock_domains.cd_sys = ClockDomain("sys")

    def testbench():
        """
        Tesbench
        """
        step = 0
        while True:
            hc = yield dut.vga.hc
            vc = yield dut.vga.vc
            r0 = yield dut.vga.color.r0
            r1 = yield dut.vga.color.r1
            g0 = yield dut.vga.color.g0
            g1 = yield dut.vga.color.g1
            assert hc == step % VGA.hpixels
            assert vc == (step // VGA.hpixels) % VGA.vlines
            yield
            step += 1

    run_simulation(dut, testbench(), vcd_name="vga.vcd")

if __name__ == '__main__':
    if len(sys.argv) == 1:
        print("USAGE:", sys.argv[0], "sim, dump, view")
        sys.exit(1)
    if sys.argv[1] == 'sim':
        print('SIMULATING...')
        simulate()
    elif sys.argv[1] == 'dump':
        print(verilog.convert(TestBench()))
    elif sys.argv[1] == 'view':
        view()
    else:
        print('<BLINK>COMMAND NOT FOUND.</BLINK>')
