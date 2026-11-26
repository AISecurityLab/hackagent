# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The screens the welcome screen's menu opens, besides the builder and
the results: the dataset presets, the settings, the web dashboard and the
queued runs.

Each says what the command line says for the same thing, from the same
place: the presets are :func:`~hackagent.interfaces.datasets.preset_rows`
(``hackagent datasets list``), the setup is
:mod:`~hackagent.interfaces.setup` (``hackagent doctor`` and ``hackagent
config set``), the dashboard :mod:`~hackagent.interfaces.dashboard`
(``hackagent web``), the queued runs :mod:`~hackagent.interfaces.queued`
(``hackagent run``).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Optional

from rich.markup import escape
from textual.containers import Horizontal, VerticalScroll
from textual.widget import Widget
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from hackagent.interfaces.palette import (
    ACCENT,
    FAILED,
    PASSED,
    SECONDARY,
    WARNING,
    paint,
)
from hackagent.interfaces.tui.frame import FramedScreen
from hackagent.interfaces.tui.keys import key
from hackagent.interfaces.tui.views.campaign.welcome import (
    menu_entry,
)

#: How to install what the dashboard needs, as Rich markup.
_INSTALL_WEB = paint("pip install 'hackagent[web]'", ACCENT)

#: How many of a dataset's goals Sample loads.
SAMPLE = 5


class _MenuScreen(FramedScreen[Any]):
    """A screen whose content is one list to choose from."""

    BINDINGS = [
        key("choose", "move('down')", priority=True),
        key("choose", "move('up')", show=False, priority=True, keys="up"),
        key("back", "dismiss(None)"),
    ]

    def action_move(self, direction: str) -> None:
        """Move to the next or the previous entry."""
        listing = self.query_one(OptionList)
        listing.focus()
        listing.action_cursor_down() if direction == "down" else listing.action_cursor_up()


class DatasetsScreen(_MenuScreen):
    """The dataset presets, as ``hackagent datasets list`` lists them; the
    highlighted one's details beside them, and Sample loads a few of its
    goals, as ``hackagent datasets sample`` does."""

    TITLE_TEXT = "Datasets"
    CONTEXT_TEXT = "the goals a campaign's dataset can start from"

    DEFAULT_CSS = """
    /* The names only: as wide as the longest, the rest for what it is. */
    DatasetsScreen #presets { width: 28; height: 1fr; padding: 0 1; }
    DatasetsScreen #about {
        width: 1fr; height: 1fr; padding: 0 2;
        border-left: solid $primary;
    }
    """

    BINDINGS = [*_MenuScreen.BINDINGS, key("sample", priority=True)]

    def __init__(self) -> None:
        super().__init__()
        from hackagent.client import presets

        self._presets = dict(presets())
        #: The goals loaded, by preset.
        self._goals: dict[str, list[str]] = {}

    def body(self) -> Iterable[Widget]:
        from hackagent.interfaces.datasets import preset_rows

        with Horizontal():
            yield OptionList(
                *(Option(text, id=name) for name, text in preset_rows(self._presets)),
                id="presets",
            )
            with VerticalScroll(id="about"):
                yield Static(id="details")

    def on_mount(self) -> None:
        listing = self.query_one(OptionList)
        listing.highlighted = 0
        listing.focus()

    def _chosen(self) -> Optional[str]:
        listing = self.query_one(OptionList)
        if listing.highlighted is None:
            return None
        return str(listing.get_option_at_index(listing.highlighted).id)

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        self._describe(str(event.option.id))

    def _describe(self, name: str, note: str = "") -> None:
        from hackagent.interfaces.datasets import in_a_campaign, source_of

        config = self._presets[name]
        lines = [
            paint(name, f"bold {ACCENT}"),
            escape(str(config.get("description", ""))),
            "",
            f"{paint('provider', SECONDARY)}  {escape(str(config.get('provider', '')))}",
            f"{paint('source', SECONDARY)}    {escape(source_of(config))}",
            f"{paint('field', SECONDARY)}     {escape(str(config.get('goal_field', '')))}",
            "",
            paint("In a campaign:", SECONDARY),
            paint(in_a_campaign(name), ACCENT),
            "",
        ]
        goals = self._goals.get(name)
        if goals:
            lines.append(paint(f"{len(goals)} of its goals", f"bold {ACCENT}"))
            lines += [
                f"{paint(f'{i}.', SECONDARY)} {escape(g)}"
                for i, g in enumerate(goals, 1)
            ]
        elif note:
            lines.append(note)
        else:
            lines.append(paint("enter loads some of its goals", SECONDARY))
        self.query_one("#details", Static).update("\n".join(lines))

    def action_sample(self) -> None:
        """Load a few goals of the highlighted preset, off the app's thread."""
        name = self._chosen()
        if name is None or name in self._goals:
            return
        self._describe(name, paint(f"loading {SAMPLE} goals…", SECONDARY))
        self.run_worker(lambda: self._load(name), thread=True, group="sample")

    def _load(self, name: str) -> None:
        from hackagent.client import load_goals

        try:
            goals = list(load_goals(preset=name, limit=SAMPLE))
        except Exception as exc:  # noqa: BLE001 - said on screen, not raised
            note = f"{paint('✗', FAILED)} {escape(str(exc))}"
            self.app.call_from_thread(self._describe, name, note)
            return
        self._goals[name] = goals
        self.app.call_from_thread(self._loaded, name)

    def _loaded(self, name: str) -> None:
        if self._chosen() == name:
            self._describe(name)


def _field(key: str, kind: str, default: Any, about: str, **more: Any) -> Any:
    """A field of one of these screens, as the builder describes its own."""
    from hackagent.interfaces.tui.views.campaign.schema import FieldDef

    return FieldDef(path=(key,), kind=kind, default=default, description=about, **more)


class _FormScreen(FramedScreen[None]):
    """A form like the builder's: one row per field (its key, its value and
    whether it is the default, edited or wrong), what the focused one is
    for in the title bar, then what is worth knowing below (:meth:`_say`)."""

    DEFAULT_CSS = """
    _FormScreen #form { padding: 1 1 0 1; }
    _FormScreen #said { padding: 1 2; }
    """

    def __init__(self) -> None:
        super().__init__()
        from hackagent.interfaces.tui.views.campaign.draft import Document

        self.document = Document()

    def fields(self) -> tuple[Any, ...]:
        """The form's fields."""
        return ()

    def body(self) -> Iterable[Widget]:
        from hackagent.interfaces.tui.views.campaign.form import FieldRow

        with VerticalScroll(id="form"):
            for field in self.fields():
                yield FieldRow(field, (), self.document)
            yield Static(id="said")

    def value(self, key: str) -> Any:
        """A field's value: what was typed, else its default."""
        found, value = self.document.get((key,))
        if found:
            return value
        return next(f.default for f in self.fields() if f.path == (key,))

    def rows(self) -> dict[str, Any]:
        from hackagent.interfaces.tui.views.campaign.form import FieldRow

        return {row.field.path[0]: row for row in self.query(FieldRow)}

    def mark(self, key: str, issue: Optional[str]) -> None:
        """Say on its row what is wrong with a field, or that nothing is."""
        row = self.rows().get(key)
        if row is not None:
            row.issue = issue
            row.refresh_state()

    def on_descendant_focus(self, _: Any) -> None:
        from hackagent.interfaces.tui.views.campaign.form import FieldRow

        widget = self.app.focused
        row = next(
            (
                n
                for n in (widget.ancestors if widget else [])
                if isinstance(n, FieldRow)
            ),
            None,
        )
        about = self.CONTEXT_TEXT
        if row is not None:
            about = f"{escape(row.field.label)}: {escape(row.field.description)}"
        self.title_bar.show(context=about)

    def _say(self, *lines: str) -> None:
        self.query_one("#said", Static).update("\n".join(lines))


class SettingsScreen(_FormScreen):
    """The settings ``hackagent config set`` changes, by the keys it and the
    configuration file call them, and whether HackAgent is ready to use, as
    ``hackagent doctor`` says it."""

    TITLE_TEXT = "Settings"
    CONTEXT_TEXT = "saved to the configuration file, as hackagent config set saves them"

    BINDINGS = [
        key("save_settings", "save"),
        key("refresh", "check"),
        key("back", "dismiss(None)"),
    ]

    #: Each setting's built-in value, which the form calls its default.
    _DEFAULTS = {"backend": "local", "ca_bundle": None, "verbosity": 0}

    def __init__(self, cli_config: Any) -> None:
        super().__init__()
        self._cli_config = cli_config
        # What is set now, where it differs from the default.
        for field in self.fields():
            current = getattr(cli_config, field.path[0], None)
            if current is not None and not field.is_default(current):
                self.document.set(field.path, current)

    def fields(self) -> tuple[Any, ...]:
        from hackagent import resolve_remote_base_url
        from hackagent.interfaces.setup import SETTINGS

        about = {setting.key: setting.help for setting in SETTINGS}
        return (
            _field(
                "backend",
                "choice",
                "local",
                about["backend"],
                choices=("local", "remote"),
            ),
            _field("base_url", "str", resolve_remote_base_url(), about["base_url"]),
            _field("ca_bundle", "str", None, about["ca_bundle"]),
            _field(
                "verbosity",
                "choice",
                0,
                about["verbosity"],
                choices=("0", "1", "2", "3"),
                choice_values=(0, 1, 2, 3),
            ),
        )

    def on_mount(self) -> None:
        self.action_check()

    def action_save(self) -> None:
        """Save the changed settings to the configuration file."""
        from hackagent.interfaces.setup import change_settings

        values: dict[str, Optional[str]] = {}
        for field in self.fields():
            key_ = field.path[0]
            value = self.value(key_)
            if value != getattr(self._cli_config, key_, None) and value is not None:
                values[key_] = str(value)
        if not values:
            self.app.notify("Nothing changed.", title="Settings")
            return
        changed, refused = change_settings(self._cli_config, values)
        for field in self.fields():
            self.mark(field.path[0], None)
        for problem in refused:
            # Each refusal names its setting; say it on that row.
            for key_, words in (
                ("backend", "backend"),
                ("ca_bundle", "CA bundle"),
                ("verbosity", "Verbosity"),
            ):
                if words in problem:
                    self.mark(key_, problem)
        if not changed:
            return
        try:
            self._cli_config.save()
            self._cli_config.reload()
        except Exception as exc:  # noqa: BLE001 - said on screen, not raised
            self.app.notify(str(exc), title="Settings", severity="error")
            return
        # The log level applies now, to this app's runs too: it is otherwise
        # read once, when hackagent starts.
        from hackagent.interfaces.cli.logging_setup import apply_verbosity

        apply_verbosity(self._cli_config.verbosity)
        self.app.notify("\n".join(changed), title="Settings saved")
        self.action_check()

    def action_check(self) -> None:
        """Check again: Graphviz, the database and the rest."""
        self.run_worker(self._check, thread=True, exclusive=True)

    def _check(self) -> None:
        from dataclasses import replace

        from hackagent.interfaces.setup import report_markup, setup_report

        try:
            sections, verdict = setup_report(self._cli_config)
            # What the fields above already say is not said again.
            sections = tuple(
                replace(
                    section,
                    checks=tuple(c for c in section.checks if c.kind != "info"),
                )
                for section in sections
            )
            text = "\n".join(report_markup(sections, verdict))
        except Exception as exc:  # noqa: BLE001 - said on screen, not raised
            text = f"{paint('✗', FAILED)} {escape(str(exc))}"
        try:
            self.app.call_from_thread(self._say, text)
        except Exception:  # the screen closed while checking
            pass


class DashboardScreen(_FormScreen):
    """The web dashboard, by the options ``hackagent web`` takes, served by
    this app while it is open. Leaving the screen keeps it served."""

    TITLE_TEXT = "Dashboard"
    CONTEXT_TEXT = "the options of hackagent web · served while HackAgent is open"

    BINDINGS = [
        key("serve", "serve"),
        key("browse", "browse"),
        key("stop_serving", "stop_serving"),
        key("back", "dismiss(None)"),
    ]

    def __init__(self, cli_config: Any) -> None:
        super().__init__()
        self._cli_config = cli_config

    def fields(self) -> tuple[Any, ...]:
        from hackagent.interfaces.dashboard import DEFAULT_DB, HOST, PORT, option_help

        return (
            _field("host", "str", HOST, option_help("host")),
            _field("port", "int", PORT, option_help("port")),
            _field("db-path", "str", DEFAULT_DB, option_help("db_path")),
            _field("local", "bool", False, option_help("local")),
        )

    def on_mount(self) -> None:
        self._show()

    @property
    def _served(self) -> Any:
        return getattr(self.app, "dashboard", None)

    def _options(self) -> dict[str, Any]:
        from hackagent.interfaces.dashboard import DEFAULT_DB

        db_path = self.value("db-path")
        return {
            "host": str(self.value("host")),
            "port": int(self.value("port")),
            "db_path": None if db_path == DEFAULT_DB else db_path,
            "force_local": bool(self.value("local")),
        }

    def _show(self) -> None:
        """Say whether it is served, and where; the fields wait for the next
        time while it is."""
        from hackagent.interfaces.dashboard import about

        served = self._served
        for editor in self.query(".value"):
            editor.disabled = served is not None
        if served is None:
            self._say(paint("ctrl+r serves it with these options", SECONDARY))
            return
        dashboard = served.dashboard
        self._say(
            f"{paint('✓', PASSED)} Serving at {paint(dashboard.url, ACCENT)}",
            *(
                f"  {paint(f'{label:<8}', SECONDARY)} {escape(value)}"
                for label, value in about(dashboard)
            ),
            "",
            paint(
                "o opens it in a browser, f3 stops it; it is served until then "
                "or until you leave HackAgent.",
                SECONDARY,
            ),
        )

    def action_serve(self) -> None:
        """Serve the dashboard with the options on screen."""
        from hackagent.interfaces.dashboard import Served, in_use, open_dashboard

        if self._served is not None:
            self._show()
            return
        options = self._options()
        host, port = options["host"], options["port"]
        self.mark("port", None)
        if not 0 < port < 65536:
            self.mark("port", "a port is a number from 1 to 65535")
            return
        if in_use(host, port):
            self.mark("port", "in use already: hackagent web, perhaps")
            return
        try:
            dashboard = open_dashboard(self._cli_config.settings, **options)
            self.app.dashboard = Served(dashboard, host, port)
        except ImportError as exc:
            self._say(
                f"{paint('✗', FAILED)} The dashboard needs its dependencies: "
                f"{escape(str(exc))}",
                f"  {paint('Install them:', SECONDARY)} {_INSTALL_WEB}",
            )
            return
        except Exception as exc:  # noqa: BLE001 - said on screen, not raised
            self._say(f"{paint('✗', FAILED)} {escape(str(exc))}")
            return
        self._show()
        self.action_browse()

    def action_browse(self) -> None:
        """Open the dashboard in a browser."""
        import webbrowser

        if self._served is None:
            self._say(paint("ctrl+r serves it first", SECONDARY))
            return
        url = self._served.dashboard.url
        if not webbrowser.open(url):
            self.app.notify(
                f"No browser to open here: open {url} yourself.", severity="warning"
            )

    def action_stop_serving(self) -> None:
        """Stop the dashboard."""
        if self._served is None:
            return
        self._served.stop()
        self.app.dashboard = None
        self._show()


class QueuedRunsScreen(_MenuScreen):
    """The runs queued from the dashboard for a local machine, as
    ``hackagent run`` lists them; Open claims the highlighted one and runs
    it here, with the same checks first, its log on the run view."""

    TITLE_TEXT = "Queued runs"
    CONTEXT_TEXT = "queued from the dashboard, for a local machine"

    DEFAULT_CSS = """
    QueuedRunsScreen #runs { height: auto; max-height: 1fr; padding: 0 1; }
    QueuedRunsScreen #said { padding: 1 2; }
    """

    BINDINGS = [
        key("choose", "move('down')", priority=True),
        key("choose", "move('up')", show=False, priority=True, keys="up"),
        key("open", priority=True),
        key("refresh", "list_runs"),
        # Not while a run is going: the run lives on this screen.
        key("back", "leave"),
    ]

    def action_leave(self) -> None:
        """Back to the menu; while a run is going, back to its log instead."""
        if self._busy and self._feed is not None:
            self.app.notify("The run is still going.", severity="warning")
            self._feed.watch(
                self.app,
                self._title,
                self._cannot_stop,
                context="leaving does not stop the run · stop it from the dashboard",
            )
            return
        self.dismiss(None)

    def __init__(self, cli_config: Any) -> None:
        super().__init__()
        self._cli_config = cli_config
        self._store: Any = None
        self._feed: Any = None
        self._busy = False
        self._title = "queued run"

    def body(self) -> Iterable[Widget]:
        yield OptionList(id="runs")
        yield Static(id="said")

    def on_mount(self) -> None:
        from hackagent.interfaces.tui.run_feed import DRAIN_S

        self.set_interval(DRAIN_S, self._drain)
        self.action_list_runs()

    def on_unmount(self) -> None:
        if self._store is not None and not self._busy:
            self._store.close(close_client=True)

    def _say(self, *lines: str) -> None:
        self.query_one("#said", Static).update("\n".join(lines))

    def _refused(self, refused: Any) -> None:
        self._say(
            f"{paint('✗', FAILED)} {escape(str(refused))}",
            *(paint(f"  export {name}=...", ACCENT) for name in refused.missing),
        )

    # -- listing -----------------------------------------------------------

    def action_list_runs(self) -> None:
        """List the queued runs again."""
        if self._busy:
            return
        self._say(paint("reading the queued runs…", SECONDARY))
        self.run_worker(self._list, thread=True, exclusive=True, group="queued")

    def _list(self) -> None:
        from hackagent.interfaces import queued

        settings = self._cli_config.settings
        if not settings.api_key:
            self.app.call_from_thread(
                self._say,
                f"{paint('!', WARNING)} Runs are queued on the HackAgent platform: "
                "this needs your API key.",
                f"  {paint('Set it:', SECONDARY)} "
                f"{paint('export HACKAGENT_API_KEY=...', ACCENT)}",
            )
            return
        try:
            if self._store is None:
                self._store = queued.connect(settings)
            runs = queued.queued_runs(self._store)
        except queued.Refused as refused:
            self.app.call_from_thread(self._refused, refused)
            return
        except Exception as exc:  # noqa: BLE001 - said on screen, not raised
            self.app.call_from_thread(
                self._say, f"{paint('✗', FAILED)} {escape(str(exc))}"
            )
            return
        self.app.call_from_thread(self._listed, runs)

    def _listed(self, runs: list[dict[str, Any]]) -> None:

        listing = self.query_one(OptionList)
        listing.clear_options()
        listing.add_options(
            Option(
                menu_entry(
                    str(run.get("agent_name") or "?"),
                    f"{str(run.get('timestamp', ''))[:16].replace('T', ' ')}  {run['id']}",
                ),
                id=run["id"],
            )
            for run in runs
        )
        if runs:
            listing.highlighted = 0
            listing.focus()
            self._say(paint("enter runs the highlighted one, here", SECONDARY))
        else:
            self._say(
                paint("No queued runs. Queue one from the dashboard first.", SECONDARY)
            )

    # -- running -----------------------------------------------------------

    def action_open(self) -> None:
        """Run the highlighted queued run here."""
        listing = self.query_one(OptionList)
        if self._busy or listing.highlighted is None:
            return
        run_id = str(listing.get_option_at_index(listing.highlighted).id)
        self._say(paint("checking the run…", SECONDARY))
        self.run_worker(
            lambda: self._prepare(run_id), thread=True, exclusive=True, group="queued"
        )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self.action_open()

    def _prepare(self, run_id: str) -> None:
        from hackagent.interfaces import queued

        try:
            ready = queued.prepare(self._store, run_id, self._cli_config.settings)
        except queued.Refused as refused:
            self.app.call_from_thread(self._refused, refused)
            return
        except Exception as exc:  # noqa: BLE001 - said on screen, not raised
            self.app.call_from_thread(
                self._say, f"{paint('✗', FAILED)} {escape(str(exc))}"
            )
            return
        self.app.call_from_thread(self._start, ready)

    def _start(self, ready: Any) -> None:
        import logging

        from hackagent.interfaces import queued
        from hackagent.interfaces.tui.run_feed import RunFeed

        self._busy = True
        self._title = ready.spec.campaign.name
        self._feed = RunFeed()
        for warning in ready.warnings:
            self._feed.note(self.app, logging.WARNING, warning)
        follow = queued.follow_url(self._cli_config.settings, ready.run_id)
        if follow:
            self._feed.note(self.app, logging.INFO, f"run · follow it at {follow}")
        self._feed.watch(
            self.app,
            self._title,
            self._cannot_stop,
            context="leaving does not stop the run · stop it from the dashboard",
        )
        self.run_worker(
            lambda: self._execute(ready), thread=True, exclusive=True, name="queued-run"
        )

    def _cannot_stop(self) -> None:
        self.app.notify(
            "A queued run is stopped from the dashboard.", severity="warning"
        )

    def _execute(self, ready: Any) -> None:
        import logging

        from hackagent.core.logging import capture
        from hackagent.interfaces import queued
        from hackagent.interfaces.cli.logging_setup import shown_level
        from hackagent.storage import RunNotClaimable

        settings = self._cli_config.settings
        with capture(self._feed.handler(), min(shown_level(), logging.INFO)):
            try:
                outcome = queued.execute(self._store, ready, settings)
            except RunNotClaimable as exc:
                self.app.call_from_thread(self._finish, logging.ERROR, exc.note)
                return
            except Exception as exc:  # noqa: BLE001 - said on screen, not raised
                self.app.call_from_thread(
                    self._finish, logging.ERROR, f"run failed: {exc}"
                )
                return
        status = outcome.status.lower()
        if outcome.status == "COMPLETED":
            self.app.call_from_thread(self._finish, logging.INFO, f"run · {status}")
        else:
            self.app.call_from_thread(
                self._finish, logging.ERROR, f"run · {status}: {outcome.note}"
            )

    def _drain(self) -> None:
        if self._feed is not None:
            self._feed.drain(self.app)

    def _finish(self, level: int, message: str) -> None:
        self._feed.drain(self.app, None)
        self._feed.note(self.app, level, message)
        self._busy = False
        self.action_list_runs()


__all__ = [
    "DashboardScreen",
    "DatasetsScreen",
    "QueuedRunsScreen",
    "SettingsScreen",
]
