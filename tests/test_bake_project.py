import datetime
import importlib
import os
import re
import shlex
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Tuple

import pytest
from click.testing import CliRunner
from cookiecutter.utils import rmtree
from pytest_cookies.plugin import Cookies, Result

from tests.utils import PROJECT_ROOT_DIR


@contextmanager
def inside_dir(dirpath):
    """
    Execute code from inside the given directory
    :param dirpath: String, path of the directory the command is being run.
    """
    old_path = os.getcwd()
    try:
        os.chdir(dirpath)
        yield
    finally:
        os.chdir(old_path)


@contextmanager
def bake_in_temp_dir(cookies: Cookies, *args, **kwargs) -> Result:
    """
    Delete the temporal directory that is created when executing the tests
    :param cookies: pytest_cookies.Cookies,
        cookie to be baked and its temporal files will be removed
    """
    result = cookies.bake(*args, template=str(PROJECT_ROOT_DIR), **kwargs)
    try:
        yield result
    finally:
        rmtree(str(result.project))


def run_inside_dir(command, dirpath):
    """
    Run a command from inside a given directory, returning the exit status
    :param command: Command that will be executed
    :param dirpath: String, path of the directory the command is being run.
    """
    with inside_dir(dirpath):
        return subprocess.check_call(shlex.split(command))


def check_output_inside_dir(command, dirpath):
    "Run a command from inside a given directory, returning the command output"
    with inside_dir(dirpath):
        return subprocess.check_output(shlex.split(command))


def project_info(result) -> Tuple[Path, str, Path, str]:
    """Get toplevel dir, project-slug, project dir and module_name from baked cookies"""
    project_path: Path = Path(result.project)
    project_slug: str = os.path.split(str(project_path))[-1]
    module_name: str = project_slug.replace("-", "_")
    project_dir: Path = project_path / "src" / module_name
    return project_path, project_slug, project_dir, module_name


@pytest.yield_fixture
def bake_result(request, cookies):
    param = request.param if hasattr(request, "param") else None
    with bake_in_temp_dir(cookies, extra_context=param) as result:
        yield result


# region Default output tests


def test_bake_with_defaults(bake_result: Result) -> None:
    assert bake_result.project.isdir()
    assert bake_result.exit_code == 0
    assert bake_result.exception is None

    assert run_inside_dir("poetry check", str(bake_result.project)) == 0

    found_toplevel_files = [f.basename for f in bake_result.project.listdir()]
    assert "pyproject.toml" in found_toplevel_files
    assert "src" in found_toplevel_files
    assert "tox.ini" in found_toplevel_files
    assert "tests" in found_toplevel_files
    assert "docs" in found_toplevel_files
    assert ".editorconfig" in found_toplevel_files
    assert ".gitignore" in found_toplevel_files
    assert "AUTHORS.rst" in found_toplevel_files
    assert "HISTORY.rst" in found_toplevel_files
    assert "LICENSE" in found_toplevel_files
    assert "README.rst" in found_toplevel_files

    assert "licenses" not in found_toplevel_files

    found_source_files = [f.basename for f in bake_result.project.join("src").listdir()]
    assert "python_boilerplate" in found_source_files


# endregion

# region pytest


def test_bake_and_run_tests(bake_result):
    assert bake_result.project.isdir()
    assert run_inside_dir("pytest", str(bake_result.project)) == 0


def test_using_pytest(bake_result):
    assert bake_result.project.isdir()
    test_file_path = bake_result.project.join("tests/test_python_boilerplate.py")
    lines = test_file_path.readlines()
    assert "import pytest" in "".join(lines)
    # Test the new pytest target
    assert run_inside_dir("pytest", str(bake_result.project)) == 0


# endregion


# region special characters


@pytest.mark.parametrize("bake_result", ([{"full_name": "O'connor"}]), indirect=True)
def test_bake_with_apostrophe(bake_result):
    """Ensure that a `full_name` with apostrophes does not break setup.py"""
    assert bake_result.project.isdir()
    assert run_inside_dir("poetry check", str(bake_result.project)) == 0


# endregion


# region Excluding files


@pytest.mark.parametrize("bake_result", ([{"create_author_file": "n"}]), indirect=True)
def test_bake_without_author_file(bake_result: Result) -> None:
    found_toplevel_files = [f.basename for f in bake_result.project.listdir()]
    assert "AUTHORS.rst" not in found_toplevel_files
    doc_files = [f.basename for f in bake_result.project.join("docs").listdir()]
    assert "authors.rst" not in doc_files

    # Assert there are no spaces in the toc tree
    docs_index_path = bake_result.project.join("docs/index.rst")
    with open(str(docs_index_path)) as index_file:
        assert "contributing\n   history" in index_file.read()


@pytest.mark.parametrize("bake_result", ([{"create_docs": "n"}]), indirect=True)
def test_bake_without_docs(bake_result: Result) -> None:
    found_toplevel_files = [f.basename for f in bake_result.project.listdir()]
    assert "docs" not in found_toplevel_files
    assert "Sphinx" not in bake_result.project.join("pyproject.toml").read()
    assert "* Documentation: " not in bake_result.project.join("README.rst").read()


# endregion


# region License


@pytest.mark.parametrize(
    "full_name,identifier,file_starts_with",
    [
        ("MIT license", "MIT", "MIT License"),
        ("Apache Software License 2.0", "Apache-2.0", "Apache License"),
        (
            "GNU General Public License v3.0",
            "GPL-3.0-only",
            "GNU GENERAL PUBLIC LICENSE",
        ),
        (
            "GNU General Public License v2.0",
            "GPL-2.0-only",
            "GNU GENERAL PUBLIC LICENSE",
        ),
        (
            "BSD 3-Clause 'New' or 'Revised' License",
            "BSD-3-Clause",
            f"Copyright (c) {datetime.date.today().year} Johan Vergeer",
        ),
        (
            "GNU Lesser General Public License v2.1",
            "LGPL-2.1-only",
            "GNU LESSER GENERAL PUBLIC LICENSE",
        ),
        (
            "BSD 2-Clause 'Simplified' License",
            "BSD-2-Clause",
            f"Copyright (c) {datetime.date.today().year} Johan Vergeer",
        ),
    ],
)
def test_bake_selecting_license(
    cookies: Cookies, full_name: str, identifier: str, file_starts_with: str
) -> None:
    with bake_in_temp_dir(
        cookies, extra_context={"open_source_license": full_name}
    ) as result:
        assert file_starts_with.lower() in result.project.join("LICENSE").read().lower()
        assert (
            f'license = "{identifier}"' in result.project.join("pyproject.toml").read()
        )


@pytest.mark.parametrize(
    "bake_result", ([{"open_source_license": "Not open source"}]), indirect=True
)
def test_bake_not_open_source(bake_result: Result) -> None:
    found_toplevel_files = [f.basename for f in bake_result.project.listdir()]
    assert "pyproject.toml" in found_toplevel_files
    assert "license = " not in bake_result.project.join("pyproject.toml").read()
    assert "LICENSE" not in found_toplevel_files
    assert "License" not in bake_result.project.join("README.rst").read()


# endregion

# region CLI tools


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


# region No Console script


@pytest.mark.parametrize(
    "bake_result",
    ([{"command_line_interface": "No command-line interface"}]),
    indirect=True,
)
def test_bake_with_no_console_script(bake_result: Result) -> None:
    _, _, project_dir, _ = project_info(bake_result)
    assert not (project_dir / "cli.py").exists()
    assert (
        f"tool.poetry.plugins." not in bake_result.project.join("pyproject.toml").read()
    )


# endregion

# region Click


@pytest.mark.parametrize(
    "bake_result", ([{"command_line_interface": "click"}]), indirect=True,
)
def test_bake_with_click_console_script_files(bake_result: Result) -> None:
    _, _, project_dir, _ = project_info(bake_result)

    assert (project_dir / "cli.py").exists()
    assert (
        f"import click"
        in bake_result.project.join("src")
        .join("python_boilerplate")
        .join("cli.py")
        .read()
    )
    assert f'Click = "^7.0"' in bake_result.project.join("pyproject.toml").read()
    assert (
        """[tool.poetry.plugins.\"console_scripts\"]
\"python_boilerplate\" = \"python_boilerplate.cli:main\""""
        in bake_result.project.join("pyproject.toml").read()
    )


@pytest.mark.parametrize(
    "bake_result", ([{"command_line_interface": "click"}]), indirect=True,
)
def test_bake_with_click_console_script(
    bake_result: Result, cli_runner: CliRunner
) -> None:
    _, _, project_dir, module_name = project_info(bake_result)
    module_path = project_dir / "cli.py"
    module_name = f"{module_name}.cli"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    noarg_result = cli_runner.invoke(cli.main)
    assert noarg_result.exit_code == 0
    noarg_output = f"Replace this message by putting your code into {module_name}"
    assert noarg_output in noarg_result.output
    help_result = cli_runner.invoke(cli.main, ["--help"])
    assert help_result.exit_code == 0
    assert "Show this message" in help_result.output


# endregion

# endregion

# region Versions


@pytest.mark.parametrize(
    "version,short_version",
    [
        ("0.0.1", "0.0.1"),
        ("0.1.0", "0.1.0"),
        ("1.0.0", "1.0.0"),
        ("1.0.0-dev0", "1.0.0"),
    ],
)
def test_version(cookies: Cookies, version: str, short_version: str) -> None:
    with bake_in_temp_dir(cookies, extra_context={"version": version}) as result:
        assert f'version = "{version}"' in result.project.join("pyproject.toml").read()
        assert f'release = "{version}"' in result.project.join("docs/conf.py").read()

        regex = r"^([0-9]+\.){2}[0-9]+"  # Same regex used in docs/conf.py
        assert (
            f'version = re.match(r"{regex}", release).group(0)'
            in result.project.join("docs/conf.py").read()
        )
        assert re.match(regex, version).group(0) == short_version


def test_bumpversion_config_file(bake_result: Result):
    """bumpversion config should be the same as the config for the main project,
    except for the initial version number"""
    expected_content = (PROJECT_ROOT_DIR / ".bumpversion.cfg").read_text()
    expected_content = re.sub(
        r"([0-9]+\.){2}[0-9]+(-(dev|prod)[0-9]+)?", "0.1.0", expected_content
    )

    assert bake_result.project.join(".bumpversion.cfg").read() == expected_content


# endregion
