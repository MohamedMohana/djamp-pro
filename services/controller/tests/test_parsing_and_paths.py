import shutil
import tempfile
from pathlib import Path

import pytest
from fastapi import HTTPException

from djamp_controller.main import (
    _extract_db_from_dotenv,
    _join_marked_sections,
    _join_without_section,
    _parse_dotenv_file,
    _parse_psql_result,
    _sanitize_user_project_path,
    _split_marked_sections,
)

BEGIN = "# BEGIN TEST MANAGED"
END = "# END TEST MANAGED"


@pytest.fixture
def home_sandbox() -> Path:
    sandbox = Path(tempfile.mkdtemp(prefix="djamp-controller-tests-", dir=str(Path.home())))
    try:
        yield sandbox
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


class TestSanitizeUserProjectPath:
    def test_accepts_directory_inside_home(self, home_sandbox: Path) -> None:
        project_dir = home_sandbox / "My Project 1.0"
        project_dir.mkdir()

        assert _sanitize_user_project_path(str(project_dir)) == project_dir.resolve()

    def test_expands_tilde(self, home_sandbox: Path) -> None:
        project_dir = home_sandbox / "tilde-project"
        project_dir.mkdir()
        raw = "~/" + str(project_dir.relative_to(Path.home()))

        assert _sanitize_user_project_path(raw) == project_dir.resolve()

    @pytest.mark.parametrize("raw", ["", "   ", "with\x00null"])
    def test_rejects_empty_or_nul(self, raw: str) -> None:
        with pytest.raises(HTTPException) as exc_info:
            _sanitize_user_project_path(raw)
        assert exc_info.value.status_code == 400

    def test_rejects_relative_path(self) -> None:
        with pytest.raises(HTTPException, match="absolute"):
            _sanitize_user_project_path("relative/path")

    def test_rejects_path_outside_home(self) -> None:
        with pytest.raises(HTTPException, match="inside your home directory"):
            _sanitize_user_project_path("/etc")

    def test_rejects_traversal_escaping_home(self) -> None:
        with pytest.raises(HTTPException, match="inside your home directory"):
            _sanitize_user_project_path(str(Path.home() / ".." / "etc"))

    def test_rejects_missing_directory(self, home_sandbox: Path) -> None:
        with pytest.raises(HTTPException, match="does not exist"):
            _sanitize_user_project_path(str(home_sandbox / "does-not-exist"))

    def test_rejects_unsupported_characters(self, home_sandbox: Path) -> None:
        weird_dir = home_sandbox / "bad$name"
        weird_dir.mkdir()

        with pytest.raises(HTTPException, match="unsupported characters"):
            _sanitize_user_project_path(str(weird_dir))


class TestMarkedSections:
    def test_split_and_join_roundtrip(self) -> None:
        content = "\n".join(["127.0.0.1 localhost", BEGIN, "127.0.0.1 demo.test", END, "::1 localhost"]) + "\n"

        before, managed, after = _split_marked_sections(content, BEGIN, END)

        assert before == ["127.0.0.1 localhost"]
        assert managed == [BEGIN, "127.0.0.1 demo.test", END]
        assert after == ["::1 localhost"]
        # Rejoining with the same block reproduces the original content
        # (modulo the blank separator lines the writer always inserts).
        rejoined = _join_marked_sections(before, managed, after)
        assert _split_marked_sections(rejoined, BEGIN, END)[1] == managed

    def test_split_without_markers_returns_everything_as_before(self) -> None:
        content = "127.0.0.1 localhost\n::1 localhost\n"

        before, managed, after = _split_marked_sections(content, BEGIN, END)

        assert before == ["127.0.0.1 localhost", "::1 localhost"]
        assert managed == []
        assert after == []

    def test_split_ignores_end_marker_before_begin(self) -> None:
        content = "\n".join([END, "middle", BEGIN]) + "\n"

        before, managed, after = _split_marked_sections(content, BEGIN, END)

        assert managed == []
        assert before == [END, "middle", BEGIN]
        assert after == []

    def test_join_without_section_drops_managed_block(self) -> None:
        content = "\n".join(["before", BEGIN, "managed", END, "after"]) + "\n"
        before, _managed, after = _split_marked_sections(content, BEGIN, END)

        result = _join_without_section(before, after)

        assert BEGIN not in result
        assert "managed" not in result
        assert result.startswith("before")
        assert result.rstrip().endswith("after")

    def test_join_marked_sections_ends_with_single_newline(self) -> None:
        result = _join_marked_sections(["a"], [BEGIN, END], ["b"])

        assert result.endswith("\n")
        assert not result.endswith("\n\n")


class TestParsePsqlResult:
    PSQL_OUTPUT = "\n".join(
        [
            " id | name",
            "----+-------",
            "  1 | alpha",
            "  2 | beta",
            "(2 rows)",
        ]
    )

    def test_parses_headers_rows_and_count(self) -> None:
        parsed = _parse_psql_result(self.PSQL_OUTPUT)

        assert parsed == {
            "headers": ["id", "name"],
            "rows": [["1", "alpha"], ["2", "beta"]],
            "row_count": 2,
        }

    def test_returns_none_without_table(self) -> None:
        assert _parse_psql_result("") is None
        assert _parse_psql_result("CREATE DATABASE") is None

    def test_merges_extra_pipes_into_last_column(self) -> None:
        output = "\n".join(
            [
                " id | value",
                "----+-------",
                "  1 | a | b",
                "(1 row)",
            ]
        )

        parsed = _parse_psql_result(output)

        assert parsed is not None
        assert parsed["rows"] == [["1", "a|b"]]

    def test_counts_rows_when_footer_missing(self) -> None:
        output = "\n".join([" id | name", "----+------", "  1 | alpha"])

        parsed = _parse_psql_result(output)

        assert parsed is not None
        assert parsed["row_count"] == 1


class TestDotenvParsing:
    def test_parse_dotenv_file_handles_comments_exports_and_quotes(self, home_sandbox: Path) -> None:
        env_file = home_sandbox / ".env"
        env_file.write_text(
            "\n".join(
                [
                    "# comment",
                    "",
                    "export DB_NAME=demo",
                    'DB_USER="alice"',
                    "DB_PASSWORD='s3cret'",
                    "NOT_A_PAIR",
                    "=missing-key",
                ]
            ),
            encoding="utf-8",
        )

        env = _parse_dotenv_file(env_file)

        assert env == {"DB_NAME": "demo", "DB_USER": "alice", "DB_PASSWORD": "s3cret"}

    def test_parse_dotenv_file_missing_returns_empty(self, home_sandbox: Path) -> None:
        assert _parse_dotenv_file(home_sandbox / "no-such.env") == {}

    def test_extract_db_from_direct_keys(self) -> None:
        out = _extract_db_from_dotenv(
            {
                "DB_NAME": "demo",
                "DB_USER": "alice",
                "DB_PASSWORD": "pw",
                "DB_HOST": "127.0.0.1",
                "DB_PORT": "54329",
            }
        )

        assert out == {
            "name": "demo",
            "username": "alice",
            "password": "pw",
            "host": "127.0.0.1",
            "port": 54329,
        }

    def test_extract_db_preserves_explicit_empty_password(self) -> None:
        out = _extract_db_from_dotenv({"DB_PASSWORD": ""})

        assert out == {"password": ""}

    def test_extract_db_from_database_url(self) -> None:
        out = _extract_db_from_dotenv({"DATABASE_URL": "postgres://alice:pw@127.0.0.1:54329/demo"})

        assert out["type"] == "postgres"
        assert out["host"] == "127.0.0.1"
        assert out["port"] == 54329
        assert out["username"] == "alice"
        assert out["password"] == "pw"
        assert out["name"] == "demo"

    def test_direct_keys_win_over_database_url(self) -> None:
        out = _extract_db_from_dotenv(
            {
                "DB_NAME": "direct",
                "DATABASE_URL": "mysql://bob:pw@db.internal:3306/from_url",
            }
        )

        assert out["name"] == "direct"
        assert out["type"] == "mysql"
        assert out["username"] == "bob"

    def test_extract_db_ignores_non_numeric_port(self) -> None:
        out = _extract_db_from_dotenv({"DB_PORT": "not-a-port"})

        assert "port" not in out
