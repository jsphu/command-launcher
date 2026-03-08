# command-launcher

A lightweight, transparent, and minimalist command-line/application launcher GUI written in Python 3 using Gtk+ 3. It provides a quick way to execute commands and see their output via desktop notifications.

## Highlights

- **Minimalist Design:** Transparent UI with no window decorations for a clean look.
- **Instant Access:** Can be launched via keyboard shortcuts (when mapped in your desktop environment).
- **Bash Integration:** Executes commands in a full Bash environment, supporting pipes and logic.
- **Alias Support:** Automatically tries to source `~/.bash_aliases` if a command is not found in the standard path.
- **Desktop Notifications:** Uses `notify-send` to display command output or error messages.
- **Flexible Timeouts:** Configurable default timeout with a whitelist for long-running commands.
- **Interactive UI:** 
    - **Draggable:** Click and drag anywhere to move the window.
    - **Quick Close:** Close with `Esc` or `Ctrl+C`.
- **Special Command Modifiers:**
    - `#`: Appending one or more `#` symbols to a command exponentially increases its timeout.
    - `€`: Appending a `€` symbol silences timeout error notifications.

## Installation

Ensure you have the required dependencies:

```bash
# Ubuntu/Debian
sudo apt install python3-gi python3-yaml libnotify-bin

# Arch Linux
sudo pacman -S python-gobject python-yaml libnotify
```

Install the package using `pip` or your preferred Python package manager:

```bash
pip install .
```

## Usage

Simply run `command-launcher` from your terminal or bind it to a keyboard shortcut.

```bash
command-launcher
```

### Passing Arguments
You can pre-fill the launcher with a command by passing it as an argument:

```bash
command-launcher "ls -la"
```

### Keyboard Shortcuts
Within the launcher:
- **Enter**: Run the entered command.
- **Escape**: Close the launcher.
- **Ctrl+C**: Close the launcher.

##  Configuration

The launcher searches for `config.yaml` in the following locations:
1. `~/.config/command_launcher/config.yaml`
2. Current working directory
3. Project root

### Example `config.yaml`

```yaml
default_timeout: 30
whitelist:
  "git push": 60     # Adds 60 seconds to the default timeout
  "long-task": null  # No timeout (infinite)
  "backup": 120
```

##  License

See the project files for licensing information.
