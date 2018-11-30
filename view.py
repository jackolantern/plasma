import pyglet

class Veiw:
    def __init__(self, hpixels, vlines, hfp, hbp, vfp, vbp):
        self.hfp = hfp
        self.hbp = hbp
        self.vfp = vfp
        self.vbp = vbp
        self.vlines = vlines
        self.hpixels = hpixels
        self.image = pyglet.image.ImageData(hpixels, vlines, format='RGB', data='\x00\x00\x00' * self.hpixels * self.vlines)

    def run(self, source):
        window = pyglet.window.Window(width=self.hpixels, height=self.vlines)

        def update(dx):
            while not source.empty():
                y, line = source.get(False)
                line = ((chr(r), chr(g), chr(b)) for (r, g, b) in line)
                line = [''.join(x) for x in line]
                line = ''.join(line)
                self.draw_line(self.vlines - y, line)

        @window.event
        def on_draw():
            window.clear()
            self.image.get_image_data().blit(0, 0)

        pyglet.clock.schedule_interval(update, 0.001)
        pyglet.app.run()

    def draw_line(self, n, line):
        data = self.image.get_data(format='RGB', pitch=self.image.pitch)
        pre, post = data[:n * 3 * self.hpixels], data[(n + 1) * 3 * self.hpixels:]
        self.image.set_data(format='RGB', data=pre + line + post, pitch=self.image.pitch)

