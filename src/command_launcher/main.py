import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk
import subprocess
import os
import re
import sys
import select
import tempfile
import yaml
from types import NoneType

class TransparentCommandLauncher(Gtk.Window):
    def __init__(self, prefix_command: str = ""):
        super().__init__()

        # Common Variables
        self.timeout = 30  # Default timeout in seconds
        self.whitelist = {} # Default empty whitelist
        self.load_config()
        self.prefix_command = prefix_command
        self.silencer = False

        self.set_title("Run")
        win_width, win_height = 400, 100
        self.set_default_size(win_width, win_height)

        self.set_decorated(False)
        self.set_opacity(0.75)

        self.set_visual(self.get_screen().get_rgba_visual())
        self.set_app_paintable(True)
        self.set_keep_above(True)
        
        # Wayland positioning - center on screen
        self.set_position(Gtk.WindowPosition.CENTER_ALWAYS)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        
        # Connect to realize signal to manually center after window is created
        self.connect('realize', self.on_realize)
        self.connect('key-press-event', self.on_key_press)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)

        self.add(box)

        self.event_box = Gtk.EventBox()
        input_holder = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)

        if self.prefix_command:
            prefix_label = Gtk.Label(label=prefix_command)
            prefix_label.set_padding(5, 0)
            input_holder.pack_start(prefix_label, False, False, 0)


        self.entry = Gtk.Entry()
        self.entry.set_alignment(0.5)
        self.entry.set_hexpand(True)
        self.entry.set_placeholder_text("Enter a command")
        self.entry.connect("activate", self.run_command)

        context = self.entry.get_style_context()
        state = Gtk.StateFlags.NORMAL
        entry_bg_color = context.get_background_color(state)

        input_holder.override_background_color(state, entry_bg_color)
        self.event_box.add(input_holder)

        self.event_box.connect("button-press-event", self.on_button_press)

        input_holder.pack_start(self.entry, True, True, 0)

        outer_frame = Gtk.Frame()
        outer_frame.set_shadow_type(Gtk.ShadowType.IN)
        outer_frame.add(self.event_box)

        box.pack_start(outer_frame, False, False, 0)

    def load_config(self):
        """ Loads configuration from a yaml file. """
        # Search for config in user directory first, then root directory of the repository, then local directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_paths = [
            os.path.expanduser("~/.config/command_launcher/config.yaml"),
            os.path.join(os.getcwd(), "config.yaml"),
            os.path.join(os.path.abspath(os.path.join(script_dir, "..", "..")), "config.yaml"),
            os.path.join(script_dir, "config.yaml"),
        ]

        for path in config_paths:
            if os.path.exists(path):
                try:
                    with open(path, 'r') as f:
                        config = yaml.safe_load(f)
                        if config:
                            self.timeout = config.get('default_timeout', self.timeout)
                            self.whitelist = config.get('whitelist', self.whitelist)
                            break
                except Exception as e:
                    print(f"Error loading config from {path}: {e}")

    def get_specific_timeout_for_command(self, cmd):
        t = self.timeout
        for command, timeout in self.whitelist.items():
            if command in cmd:
                if isinstance(timeout, int):
                    t += timeout # increment timeout if in whitelist
                elif isinstance(timeout, NoneType):
                    return None # indefinite timeout == no timeout
                else:
                    continue
        return t

    def on_button_press(self, widget, event):
        if event.button == 1:
            self.begin_move_drag(
                event.button,
                int(event.x_root),
                int(event.y_root),
                event.time
            )
            return True
        return False

    def on_key_press(self, widget, event):
        if (
            event.state & Gdk.ModifierType.CONTROL_MASK
        ) and (
            event.keyval == Gdk.KEY_c or event.keyval == Gdk.KEY_C
        ):
            Gtk.main_quit()
            return True

        if event.keyval == Gdk.KEY_Escape:
            Gtk.main_quit()
            return True

        return False

    def on_realize(self, widget):
        # Get the display and monitor info
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor()
        if monitor is None:
            monitor = display.get_monitor(0)
        
        geometry = monitor.get_geometry()
        scale = monitor.get_scale_factor()
        
        # Calculate center position
        monitor_width = geometry.width / scale
        monitor_height = geometry.height / scale
        
        win_width, win_height = self.get_size()
        x = (monitor_width - win_width) / 2
        y = (monitor_height - win_height) / 2
        
        # Try to move the window (may not work on all Wayland compositors)
        self.move(int(x), int(y))

    def NotifySuccess(self,cmd, out):
        subprocess.run([
            'notify-send', cmd, out,
            '-a', 'commander',
            '-i', 'terminal'
        ], check=True)

    def NotifyFailure(self, cmd, e):
        subprocess.run([
            'notify-send', f"Error: {cmd}", str(e),
            '-a', 'commander',
            '-i', 'error'
        ], check=True)

    def Bash(self, cmd):
        with tempfile.NamedTemporaryFile(mode='w+', delete=True) as tmp:
            fullcmd = f"set -o pipefail; {{ {cmd} ; }} ; echo \"${{PIPESTATUS[@]}}\" > {tmp.name}"
            proc = subprocess.Popen(
                fullcmd,
                shell=True,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
                preexec_fn=os.setpgrp,
                executable='/bin/bash',
                text=True
            )
            try:
                out, error = proc.communicate(timeout=self.timeout)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(proc.pid), 15)
                out, error = "", f"Command timed out. Exceeded limit of {self.timeout} seconds."

            tmp.seek(0)
            __pipestatus = tmp.read().strip()
            pipestatus = __pipestatus.split()
            returncode = int(max(pipestatus, key=int)) # if there are multiple errors get the highest one
        return out, error, returncode

    def BashRC(self, cmd):
        from pty import openpty
        master_fd, slave_fd = openpty()
        proc = subprocess.Popen(
            f'bash -ic "source ~/.bash_aliases; {cmd}"',
            shell=True,
            stdin=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            preexec_fn=os.setpgrp,
            text=True
        )
        os.close(slave_fd)
        try:
            out, error = proc.communicate(timeout=self.timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            out, error = "", f"Command timed out. Exceeded limit of {self.timeout} seconds."
        out, error = self.suppress_warning(out, error)
        return self.sanitize_output(out), self.sanitize_output(error)

    def suppress_warning(self, output, error):
        bash_warning = re.compile(
            r'bash: cannot set terminal process group \([^)]+\): Inappropriate ioctl for device\s*'
            r'bash: no job control in this shell'
        )
        clean_out = bash_warning.sub('', output).strip()
        clean_err = bash_warning.sub('', error).strip()
        return clean_out, clean_err

    def is_timeout_warning(self, error):
        timeout_warning = re.compile(
                r'Command timed out\. Exceeded limit of .+ seconds\.'
        )
        if timeout_warning.match(error) and self.silencer:
            return True
        return False

    def sanitize_output(self, output):
        output = output.replace('-', '–')
        ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
        output = ansi_escape.sub(' ', output)
        return ''.join(c for c in ''.join(f"{p:<50}" for p in output.split('\n')) if c.isprintable()).strip()

    def increase_timeout_with_symbols(self, cmd):
        count = len(re.findall(r'#', cmd)) + 1
        self.timeout = self.timeout ** count
        return cmd.replace('#', '')

    def silence_timeout_error_with_symbols(self, cmd):
        all_euros = re.findall(r'€', cmd)
        if len(all_euros) >= 1:
            return cmd.replace('€', ''), True
        return cmd, False

    def hide_app(self):
        self.hide()

        while Gtk.events_pending():
            Gtk.main_iteration()

    def run_command(self, _):
        prefix_cmd = self.prefix_command
        given_cmd = self.entry.get_text()
        cmd = prefix_cmd + " " + given_cmd if prefix_cmd else given_cmd
        if cmd:
            self.hide_app()

            cmd = self.increase_timeout_with_symbols(cmd)
            cmd, is_silenced = self.silence_timeout_error_with_symbols(cmd)
            self.silencer = is_silenced
            self.timeout = self.get_specific_timeout_for_command(cmd)
            try:
                out, error, returncode = self.Bash(cmd)
                if out or (out == '' and error == ''):
                    if out == "None":
                        exit()
                    self.NotifySuccess(cmd, out)
                elif error:
                    if returncode == 127:
                        output, err = self.BashRC(cmd)
                        if output or error == '':
                            # if output == "None":
                            #     exit()
                            self.NotifySuccess(cmd, output)
                        elif err != '':
                            if self.is_timeout_warning(err):
                                exit()
                            self.NotifyFailure(cmd, err)
                        # else:
                        #     exit()
                    else:
                        if self.is_timeout_warning(error):
                            exit()
                        self.NotifyFailure(cmd, error)
            except Exception as e:
                self.NotifyFailure("execute failure", e)
        # self.NotifyFailure("No command found", "")
        exit()

def get_input():
    parts = []
    # We use .read() only if we know data is being piped in
    if not sys.stdin.isatty():
        # select ensures we don't hang if the pipe is empty
        if select.select([sys.stdin], [], [], 0.0)[0]:
            parts.append(sys.stdin.read().strip())

    if len(sys.argv) > 1:
        parts.append(" ".join(sys.argv[1:]))

    return " ".join(parts).strip()

def main():
    win = TransparentCommandLauncher(prefix_command=get_input())
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()

if __name__ == "__main__":
    main()
