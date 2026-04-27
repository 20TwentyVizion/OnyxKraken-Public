"""App Catalog — templates for apps Onyx can build on demand.

Each template defines the app's name, icon, description, category,
and capabilities. When a user clicks "Build" on an unbuilt template,
it triggers the ToolForge flow to generate the app code via LLM.
"""

from dataclasses import dataclass


@dataclass
class AppTemplate:
    """A buildable app template."""
    name: str               # safe name e.g. "timer"
    display_name: str       # e.g. "Timer"
    icon: str               # emoji icon
    description: str        # what it does
    category: str           # Productivity, Utilities, Creative, Dev Tools, Games
    capabilities: list      # what interactions Onyx can perform on it
    build_prompt: str       # detailed prompt for the LLM to build this app


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

CATEGORIES = [
    "Productivity",
    "Utilities",
    "Creative",
    "Dev Tools",
    "Games",
]

CATEGORY_ICONS = {
    "Productivity": "📋",
    "Utilities": "🔧",
    "Creative": "🎨",
    "Dev Tools": "⚙️",
    "Games": "🎮",
}

# ---------------------------------------------------------------------------
# App Templates
# ---------------------------------------------------------------------------

APP_TEMPLATES: list[AppTemplate] = [
    # ── Productivity ──────────────────────────────────────────────────
    AppTemplate(
        name="timer",
        display_name="Timer",
        icon="⏱️",
        description="Countdown timer with lap tracking and alarm notification.",
        category="Productivity",
        capabilities=["countdown", "lap tracking", "alarm"],
        build_prompt=(
            "Build a Timer app with: countdown timer (user enters minutes/seconds), "
            "start/pause/reset buttons, lap tracking list, alarm sound (winsound.Beep) "
            "when timer hits zero. Dark theme #0a0e16, cyan accents #00d4ff. "
            "Large digital display for remaining time. Keyboard shortcuts: Space=start/pause, R=reset."
        ),
    ),
    AppTemplate(
        name="todo_list",
        display_name="To-Do List",
        icon="✅",
        description="Task manager with priorities, save to JSON, check/delete tasks.",
        category="Productivity",
        capabilities=["add tasks", "check tasks", "delete tasks", "priority levels"],
        build_prompt=(
            "Build a To-Do List app with: add/check/delete tasks, priority levels (high/medium/low) "
            "shown with color coding, save/load to JSON file, drag to reorder. "
            "Dark theme #0a0e16, cyan accents. Keyboard: Enter=add, Delete=remove checked."
        ),
    ),
    AppTemplate(
        name="pomodoro",
        display_name="Pomodoro Timer",
        icon="🍅",
        description="Work/break cycles (25/5 min) with session tracking and notifications.",
        category="Productivity",
        capabilities=["pomodoro cycles", "session tracking", "notifications"],
        build_prompt=(
            "Build a Pomodoro Timer with: 25min work / 5min break cycles, long break every 4 cycles, "
            "session counter, start/pause/skip buttons, winsound.Beep notification on transition. "
            "Visual progress ring or bar. Dark theme #0a0e16, red accent for work, green for break."
        ),
    ),
    AppTemplate(
        name="sticky_notes",
        display_name="Sticky Notes",
        icon="📝",
        description="Multiple floating note windows with color coding and auto-save.",
        category="Productivity",
        capabilities=["create notes", "color coding", "auto-save"],
        build_prompt=(
            "Build a Sticky Notes app: main window lists notes, '+' button creates new floating "
            "Toplevel note windows. Each note has title, text area, color picker (6 dark theme colors). "
            "Auto-save all notes to JSON. Notes are always-on-top. Dark theme."
        ),
    ),
    AppTemplate(
        name="clipboard_manager",
        display_name="Clipboard Manager",
        icon="📋",
        description="History of copied items with click to re-copy and search.",
        category="Productivity",
        capabilities=["clipboard history", "search", "re-copy"],
        build_prompt=(
            "Build a Clipboard Manager: monitors clipboard changes (poll every 500ms using "
            "root.clipboard_get()), stores history in a scrollable list, click any item to re-copy. "
            "Search/filter bar at top. Max 100 entries. Dark theme #0a0e16, cyan accents."
        ),
    ),
    AppTemplate(
        name="quick_launcher",
        display_name="Quick Launcher",
        icon="🚀",
        description="Searchable list of apps and files, keyboard shortcut to open.",
        category="Productivity",
        capabilities=["search apps", "launch apps", "keyboard shortcuts"],
        build_prompt=(
            "Build a Quick Launcher: scans Start Menu and Desktop for .lnk files, shows searchable "
            "list. Type to filter, Enter to launch selected, arrow keys to navigate. "
            "Compact window, always-on-top. Dark theme #0a0e16. Uses subprocess.Popen + os.startfile."
        ),
    ),
    AppTemplate(
        name="markdown_previewer",
        display_name="Markdown Previewer",
        icon="📄",
        description="Edit pane + rendered preview side by side with live update.",
        category="Productivity",
        capabilities=["markdown editing", "live preview", "file I/O"],
        build_prompt=(
            "Build a Markdown Previewer: split pane — left is text editor, right is rendered preview "
            "using tkinter Text widget with tag-based formatting (bold, italic, headers, code blocks, "
            "lists). Live update on keystroke. Open/Save .md files. Dark theme #0a0e16."
        ),
    ),

    # ── Utilities ─────────────────────────────────────────────────────
    AppTemplate(
        name="unit_converter",
        display_name="Unit Converter",
        icon="📐",
        description="Convert length, weight, temperature, and more with instant results.",
        category="Utilities",
        capabilities=["unit conversion", "multiple categories"],
        build_prompt=(
            "Build a Unit Converter with tabs/dropdown for categories: Length (m/ft/in/cm/km/mi), "
            "Weight (kg/lb/oz/g), Temperature (C/F/K), Volume (L/gal/cup/mL), Speed (mph/kmh/ms). "
            "Two input fields with instant bidirectional conversion. Dark theme #0a0e16."
        ),
    ),
    AppTemplate(
        name="color_picker",
        display_name="Color Picker",
        icon="🎨",
        description="HSL/RGB/hex sliders with large preview and copy to clipboard.",
        category="Utilities",
        capabilities=["color selection", "copy hex/rgb", "sliders"],
        build_prompt=(
            "Build a Color Picker with: RGB sliders (0-255), HSL sliders, hex input field, "
            "large color preview square, copy hex/rgb to clipboard buttons. "
            "Show complementary color. Dark theme #0a0e16, dynamic preview."
        ),
    ),
    AppTemplate(
        name="json_viewer",
        display_name="JSON Viewer",
        icon="🗂️",
        description="Tree view of JSON files with expand/collapse and value editing.",
        category="Utilities",
        capabilities=["JSON parsing", "tree view", "file I/O"],
        build_prompt=(
            "Build a JSON Viewer/Editor: open JSON files, display as expandable tree using "
            "tkinter Treeview widget. Click to expand/collapse. Double-click values to edit. "
            "Save modified JSON. Syntax-colored values (strings=green, numbers=cyan, bools=yellow). "
            "Dark theme #0a0e16."
        ),
    ),
    AppTemplate(
        name="file_renamer",
        display_name="File Renamer",
        icon="📁",
        description="Batch rename files with patterns, prefix, suffix, and regex.",
        category="Utilities",
        capabilities=["batch rename", "regex", "file operations"],
        build_prompt=(
            "Build a File Renamer: select folder, show file list with preview of new names. "
            "Options: add prefix/suffix, find & replace, regex, numbering (001, 002...), "
            "change extension. Preview before applying. Undo last rename. Dark theme #0a0e16."
        ),
    ),
    AppTemplate(
        name="system_monitor",
        display_name="System Monitor",
        icon="📊",
        description="Live CPU, RAM, and disk usage with graphs.",
        category="Utilities",
        capabilities=["system monitoring", "live graphs"],
        build_prompt=(
            "Build a System Monitor: show CPU %, RAM %, Disk % using psutil. "
            "Live updating bar charts or line graphs drawn on Canvas. Update every 1s. "
            "Show numeric values + process count. Dark theme #0a0e16, cyan/green/orange bars."
        ),
    ),
    AppTemplate(
        name="password_generator",
        display_name="Password Generator",
        icon="🔑",
        description="Generate strong passwords with configurable length and character sets.",
        category="Utilities",
        capabilities=["password generation", "copy to clipboard"],
        build_prompt=(
            "Build a Password Generator: length slider (8-64), checkboxes for uppercase, "
            "lowercase, numbers, symbols. Generate button, large display of password, "
            "copy to clipboard button, password strength indicator bar. "
            "Generate 5 passwords at once. Dark theme #0a0e16."
        ),
    ),

    # ── Creative / Fun ────────────────────────────────────────────────
    AppTemplate(
        name="drawing_pad",
        display_name="Drawing Pad",
        icon="🖌️",
        description="Freehand drawing canvas with colors, brush sizes, and save as PNG.",
        category="Creative",
        capabilities=["freehand drawing", "color selection", "save image"],
        build_prompt=(
            "Build a Drawing Pad: Canvas for freehand drawing with mouse. "
            "Color palette (8 colors + custom), brush size slider (1-20px), "
            "eraser tool, clear canvas, save as PNG using PIL or PostScript. "
            "Undo last stroke (store stroke history). Dark theme #0a0e16."
        ),
    ),
    AppTemplate(
        name="pixel_art",
        display_name="Pixel Art Editor",
        icon="🟦",
        description="Grid-based pixel drawing with palette and export.",
        category="Creative",
        capabilities=["pixel drawing", "palette", "export"],
        build_prompt=(
            "Build a Pixel Art Editor: configurable grid (16x16, 32x32, 64x64), "
            "click cells to paint, color palette with 16 colors + custom, "
            "fill tool, eyedropper, clear, zoom, export as PNG. "
            "Grid lines toggle. Dark theme #0a0e16."
        ),
    ),
    AppTemplate(
        name="flashcards",
        display_name="Flashcard App",
        icon="🃏",
        description="Create and study flashcard decks with flip animation and scoring.",
        category="Creative",
        capabilities=["create decks", "study mode", "scoring"],
        build_prompt=(
            "Build a Flashcard App: create decks with front/back text, study mode that "
            "shows front → click to reveal back, mark correct/incorrect, "
            "score tracking, shuffle. Save decks to JSON. "
            "Card flip animation (fade transition). Dark theme #0a0e16."
        ),
    ),
    AppTemplate(
        name="habit_tracker",
        display_name="Habit Tracker",
        icon="📅",
        description="Daily checkboxes with streak counting and calendar view.",
        category="Creative",
        capabilities=["habit tracking", "streaks", "calendar"],
        build_prompt=(
            "Build a Habit Tracker: add habits, daily checkbox grid (7-day view), "
            "streak counter per habit, calendar month view showing completed days. "
            "Save to JSON. Color-coded: green=completed, red=missed. Dark theme #0a0e16."
        ),
    ),
    AppTemplate(
        name="soundboard",
        display_name="Soundboard",
        icon="🔊",
        description="Play short audio clips on button press with customizable sounds.",
        category="Creative",
        capabilities=["audio playback", "custom sounds"],
        build_prompt=(
            "Build a Soundboard: grid of large buttons, each plays a sound. "
            "Use winsound.PlaySound or playsound. Let user assign .wav files to buttons. "
            "6x4 grid of buttons with custom labels. Right-click to assign sound file. "
            "Dark theme #0a0e16, colorful button backgrounds."
        ),
    ),

    # ── Developer Tools ───────────────────────────────────────────────
    AppTemplate(
        name="regex_tester",
        display_name="Regex Tester",
        icon="🔍",
        description="Test regex patterns with live highlighting of matches.",
        category="Dev Tools",
        capabilities=["regex testing", "match highlighting"],
        build_prompt=(
            "Build a Regex Tester: pattern input field, test string text area, "
            "live highlight all matches in the text area using text tags. "
            "Show match count, capture groups list, common regex reference sidebar. "
            "Flags checkboxes: IGNORECASE, MULTILINE, DOTALL. Dark theme #0a0e16."
        ),
    ),
    AppTemplate(
        name="base64_tool",
        display_name="Base64 Encoder",
        icon="🔄",
        description="Encode and decode text and files to/from Base64.",
        category="Dev Tools",
        capabilities=["base64 encoding", "base64 decoding", "file handling"],
        build_prompt=(
            "Build a Base64 Encoder/Decoder: two text areas (input/output), "
            "Encode and Decode buttons, swap button. Support text and file drag-drop "
            "(or file open dialog). Copy output to clipboard. Dark theme #0a0e16."
        ),
    ),
    AppTemplate(
        name="log_viewer",
        display_name="Log Viewer",
        icon="📜",
        description="Tail and filter log files with color-coded log levels.",
        category="Dev Tools",
        capabilities=["log viewing", "filtering", "color coding"],
        build_prompt=(
            "Build a Log Viewer: open log files, auto-tail (follow new lines), "
            "filter by text search and log level (DEBUG/INFO/WARNING/ERROR/CRITICAL). "
            "Color-code log levels. Line count display. Auto-scroll toggle. Dark theme #0a0e16."
        ),
    ),
    AppTemplate(
        name="api_tester",
        display_name="API Tester",
        icon="🌐",
        description="Send GET/POST requests and inspect responses with headers.",
        category="Dev Tools",
        capabilities=["HTTP requests", "response inspection"],
        build_prompt=(
            "Build an API Tester: URL input, method dropdown (GET/POST/PUT/DELETE), "
            "headers editor (key-value pairs), body text area for POST, "
            "Send button, response display with status code, headers, and body. "
            "Response time display. Uses urllib.request. Dark theme #0a0e16."
        ),
    ),
    AppTemplate(
        name="snippet_manager",
        display_name="Snippet Manager",
        icon="📎",
        description="Save, search, and copy code snippets organized by tags.",
        category="Dev Tools",
        capabilities=["snippet storage", "search", "tagging"],
        build_prompt=(
            "Build a Snippet Manager: create snippets with title, language, tags, and code. "
            "Search by title/tag, filter by language. Click to copy code to clipboard. "
            "Syntax highlighting for Python/JS/HTML. Save to JSON. Dark theme #0a0e16."
        ),
    ),

    # ── Games ─────────────────────────────────────────────────────────
    AppTemplate(
        name="tic_tac_toe",
        display_name="Tic-Tac-Toe",
        icon="❌",
        description="Classic Tic-Tac-Toe vs AI with minimax algorithm.",
        category="Games",
        capabilities=["game play", "AI opponent"],
        build_prompt=(
            "Build Tic-Tac-Toe: 3x3 grid of buttons, player X vs AI O. "
            "AI uses minimax algorithm (unbeatable). Show win/draw/loss with highlight. "
            "Score tracker, New Game button. Click cells to play. Dark theme #0a0e16, "
            "X=#00d4ff, O=#ff4466."
        ),
    ),
    AppTemplate(
        name="snake",
        display_name="Snake",
        icon="🐍",
        description="Classic snake game with score tracking and increasing speed.",
        category="Games",
        capabilities=["game play", "score tracking"],
        build_prompt=(
            "Build Snake game: Canvas-based, arrow keys to move, eat food to grow, "
            "wall/self collision = game over. Score display, high score (saved to file), "
            "speed increases with score. Start/restart with Space. "
            "Dark theme #0a0e16, snake=#00d4ff, food=#ff4466."
        ),
    ),
    AppTemplate(
        name="minesweeper",
        display_name="Minesweeper",
        icon="💣",
        description="Classic minesweeper with flag/reveal, multiple difficulties.",
        category="Games",
        capabilities=["game play", "flagging", "difficulty levels"],
        build_prompt=(
            "Build Minesweeper: grid of buttons, left-click to reveal, right-click to flag. "
            "Difficulty: Easy (9x9, 10 mines), Medium (16x16, 40), Hard (16x30, 99). "
            "Timer, mine counter, first click is always safe. "
            "Number colors: 1=blue, 2=green, 3=red, 4=purple. Dark theme #0a0e16."
        ),
    ),
    AppTemplate(
        name="memory_match",
        display_name="Memory Match",
        icon="🎴",
        description="Card-flipping pair matching game with move counter.",
        category="Games",
        capabilities=["game play", "memory challenge"],
        build_prompt=(
            "Build Memory Match: 4x4 grid (8 pairs) of face-down cards with emoji symbols. "
            "Click to flip, match pairs to clear them. Move counter, timer, "
            "best score tracking. Card flip animation (color change). "
            "New Game button. Dark theme #0a0e16."
        ),
    ),
    AppTemplate(
        name="typing_test",
        display_name="Typing Speed Test",
        icon="⌨️",
        description="Timed typing test with WPM calculation and accuracy tracking.",
        category="Games",
        capabilities=["typing test", "WPM tracking", "accuracy"],
        build_prompt=(
            "Build a Typing Speed Test: display a paragraph of text, user types in input area. "
            "Highlight correct (green) and incorrect (red) characters in real-time. "
            "30/60 second modes. Show WPM, accuracy %, characters typed. "
            "Multiple text samples. Dark theme #0a0e16."
        ),
    ),
]


def get_template(name: str) -> AppTemplate | None:
    """Get a template by its safe name."""
    for t in APP_TEMPLATES:
        if t.name == name:
            return t
    return None


def get_templates_by_category() -> dict[str, list[AppTemplate]]:
    """Group templates by category, in category order."""
    result = {cat: [] for cat in CATEGORIES}
    for t in APP_TEMPLATES:
        if t.category in result:
            result[t.category].append(t)
    return result
