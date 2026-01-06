import sys
import math
import random
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Gio
import cairo

class FireOrb(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.example.fireorb",
                        flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.window = None
        self.drawing_area = None
        self.ticks = 0
        self.particles = []
        self.dragging = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        
        # Initialize fire particles
        for _ in range(150):
            self.particles.append({
                'angle': random.uniform(0, 2 * math.pi),
                'radius': random.uniform(0, 100),
                'speed': random.uniform(0.5, 2.0),
                'size': random.uniform(2, 8),
                'life': random.uniform(0, 1),
                'offset': random.uniform(0, 2 * math.pi)
            })
    
    def do_activate(self):
        if self.window:
            self.window.present()
            return
        
        self.window = Gtk.ApplicationWindow(application=self)
        self.window.set_title("Fire Orb")
        
        # Visual setup
        self.window.set_decorated(False)
        self.window.set_default_size(400, 400)
        
        screen = self.window.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.window.set_visual(visual)
        
        self.window.set_app_paintable(True)
        
        # Window properties
        self.window.set_keep_above(True)
        self.window.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        self.window.set_skip_taskbar_hint(True)
        self.window.set_skip_pager_hint(True)
        
        # Position at bottom center
        screen = Gdk.Screen.get_default()
        screen_width = screen.get_width()
        screen_height = screen.get_height()
        self.window.move((screen_width - 400) // 2, screen_height - 450)
        
        # Drawing area for fire animation
        self.drawing_area = Gtk.DrawingArea()
        self.drawing_area.set_size_request(400, 400)
        self.drawing_area.connect('draw', self.draw_fire)
        
        self.window.add(self.drawing_area)
        
        # Mouse events
        self.window.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | 
                              Gdk.EventMask.BUTTON_RELEASE_MASK |
                              Gdk.EventMask.POINTER_MOTION_MASK)
        
        self.window.connect('button-press-event', self.on_button_press)
        self.window.connect('button-release-event', self.on_button_release)
        self.window.connect('motion-notify-event', self.on_motion)
        self.window.connect('destroy', self.on_window_destroy)
        self.window.connect('realize', self.on_realize)
        
        self.window.show_all()
        
        # Animation loop - 60 FPS
        GLib.timeout_add(16, self.animate)

    def draw_fire(self, widget, cr):
        width = widget.get_allocated_width()
        height = widget.get_allocated_height()
        center_x = width / 2
        center_y = height / 2
        
        # Clear with transparency
        cr.set_source_rgba(0, 0, 0, 0)
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        
        # Draw fire particles
        for particle in self.particles:
            # Calculate position
            angle = particle['angle'] + self.ticks * particle['speed'] * 0.02
            radius = particle['radius'] * (1 - particle['life'] * 0.3)
            
            # Add flickering
            flicker = math.sin(self.ticks * 0.1 + particle['offset']) * 10
            x = center_x + math.cos(angle) * (radius + flicker)
            y = center_y + math.sin(angle) * (radius + flicker) - particle['life'] * 30
            
            # Color based on life and position
            if particle['life'] < 0.3:
                # White hot core
                r, g, b = 1.0, 1.0, 0.9
                alpha = 0.9 * (1 - particle['life'] / 0.3)
            elif particle['life'] < 0.6:
                # Yellow-orange
                r, g, b = 1.0, 0.8, 0.2
                alpha = 0.8
            else:
                # Red-orange edges
                r, g, b = 1.0, 0.3, 0.0
                alpha = 0.6 * (1 - (particle['life'] - 0.6) / 0.4)
            
            # Draw particle with glow
            for i in range(3):
                cr.set_source_rgba(r, g * (1 - i * 0.3), b, alpha * (1 - i * 0.3))
                cr.arc(x, y, particle['size'] * (1 + i), 0, 2 * math.pi)
                cr.fill()
            
            # Update particle
            particle['life'] = (particle['life'] + 0.01) % 1.0
            if particle['life'] < 0.01:
                particle['angle'] = random.uniform(0, 2 * math.pi)
                particle['radius'] = random.uniform(0, 100)
                particle['offset'] = random.uniform(0, 2 * math.pi)
        
        # Draw core glow layers
        pulse = (math.sin(self.ticks * 0.1) + 1) / 2
        
        # Outer glow
        gradient = cairo.RadialGradient(center_x, center_y, 0, 
                                       center_x, center_y, 120 + pulse * 30)
        gradient.add_color_stop_rgba(0, 1.0, 0.8, 0.4, 0.4)
        gradient.add_color_stop_rgba(0.3, 1.0, 0.5, 0.0, 0.3)
        gradient.add_color_stop_rgba(0.6, 1.0, 0.2, 0.0, 0.1)
        gradient.add_color_stop_rgba(1, 0.5, 0.0, 0.0, 0.0)
        cr.set_source(gradient)
        cr.arc(center_x, center_y, 120 + pulse * 30, 0, 2 * math.pi)
        cr.fill()
        
        # Middle layer
        gradient = cairo.RadialGradient(center_x, center_y, 0,
                                       center_x, center_y, 70 + pulse * 20)
        gradient.add_color_stop_rgba(0, 1.0, 1.0, 0.9, 0.6)
        gradient.add_color_stop_rgba(0.5, 1.0, 0.7, 0.2, 0.5)
        gradient.add_color_stop_rgba(1, 1.0, 0.3, 0.0, 0.0)
        cr.set_source(gradient)
        cr.arc(center_x, center_y, 70 + pulse * 20, 0, 2 * math.pi)
        cr.fill()
        
        # Hot core
        gradient = cairo.RadialGradient(center_x, center_y - 5, 0,
                                       center_x, center_y, 40 + pulse * 10)
        gradient.add_color_stop_rgba(0, 1.0, 1.0, 1.0, 0.9)
        gradient.add_color_stop_rgba(0.4, 1.0, 0.95, 0.7, 0.7)
        gradient.add_color_stop_rgba(1, 1.0, 0.6, 0.1, 0.0)
        cr.set_source(gradient)
        cr.arc(center_x, center_y, 40 + pulse * 10, 0, 2 * math.pi)
        cr.fill()
        
        return True

    def animate(self):
        if not self.window or not self.window.get_visible():
            return True
        
        self.ticks += 1
        
        # Force redraw
        if self.drawing_area:
            self.drawing_area.queue_draw()
        
        return True
    
    def on_button_press(self, widget, event):
        if event.button == 1:
            self.dragging = True
            self.drag_offset_x = event.x
            self.drag_offset_y = event.y
            return True
        return False
    
    def on_button_release(self, widget, event):
        if event.button == 1:
            self.dragging = False
        return False
    
    def on_motion(self, widget, event):
        if self.dragging:
            x = event.x_root - self.drag_offset_x
            y = event.y_root - self.drag_offset_y
            self.window.move(int(x), int(y))
        return False
    
    def on_window_destroy(self, window):
        self.quit()
    
    def on_realize(self, window):
        window.set_skip_taskbar_hint(True)
        window.set_skip_pager_hint(True)
        window.set_accept_focus(False)

app = FireOrb()
app.run(sys.argv)