"""Detail text of Frost error answers is bounded and free of control chars."""

import pytest

from machine_data_model.behavior.execution_error import (
    ExecutionError,
    ExecutionErrorCode,
    sanitize_detail,
)
from machine_data_model.protocols.frost_v1 import frost_protocol_mng
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage
from machine_data_model.protocols.frost_v1.frost_payload import (
    ErrorMessages,
    ErrorPayload,
)
from machine_data_model.protocols.frost_v1.frost_protocol_mng import (
    _MAX_ERROR_DETAIL,
    _sanitize_detail,
)
from tests.behavior import composite, failing_stub, frost_request, frost_setup

LINE_SEPARATOR = chr(0x2028)


def answer_text(detail: str) -> str:
    method = composite(
        "m",
        [
            failing_stub(
                ExecutionError(ExecutionErrorCode.PRECONDITION_NOT_MET, detail)
            )
        ],
    )
    manager, _ = frost_setup(method)
    response = manager.handle_request(frost_request("dm", "m"))
    assert isinstance(response, FrostMessage)
    assert isinstance(response.payload, ErrorPayload)
    return str(response.payload.error_message)


class TestSanitizeDetail:
    def test_short_text_is_unchanged(self) -> None:
        assert _sanitize_detail("mode == 2 not met") == "mode == 2 not met"

    def test_limit_is_a_module_constant(self) -> None:
        assert _MAX_ERROR_DETAIL == 256
        assert frost_protocol_mng._MAX_ERROR_DETAIL == _MAX_ERROR_DETAIL

    def test_text_at_the_limit_is_not_cut(self) -> None:
        text = "x" * _MAX_ERROR_DETAIL

        assert _sanitize_detail(text) == text

    def test_longer_text_is_cut_and_marked(self) -> None:
        result = _sanitize_detail("x" * 10_000)

        assert result == "x" * (_MAX_ERROR_DETAIL - 3) + "..."
        assert len(result) == _MAX_ERROR_DETAIL

    @pytest.mark.parametrize(
        "raw",
        [
            "a\nb",
            "a\r\nb",
            "a\tb",
            "a\x1b[31mb",
            "a\x00b",
            "a\x7fb",
            "a\x85b",
            "a" + LINE_SEPARATOR + "b",
            "a  \n\t  b",
        ],
    )
    def test_whitespace_and_control_runs_become_one_space(
        self, raw: str
    ) -> None:
        result = _sanitize_detail(raw)

        assert result.startswith("a")
        assert result.endswith("b")
        for char in "\n\r\t\x1b\x00\x7f\x85" + LINE_SEPARATOR:
            assert char not in result
        assert "  " not in result

    def test_leading_and_trailing_blanks_are_stripped(self) -> None:
        assert _sanitize_detail("\n  text \t") == "text"

    def test_non_ascii_survives(self) -> None:
        assert _sanitize_detail("è 日本語 🙂") == "è 日本語 🙂"

    def test_cut_never_splits_a_character(self) -> None:
        # A string cut on characters stays encodable; a byte cut would not.
        text = "🙂" * 1000

        result = _sanitize_detail(text)

        assert result == "🙂" * (_MAX_ERROR_DETAIL - 3) + "..."
        result.encode("utf-8")

    def test_lone_surrogates_are_removed(self) -> None:
        result = _sanitize_detail("a" + chr(0xD800) + "b" + chr(0xDFFF))

        assert result == "ab"
        result.encode("utf-8")

    @pytest.mark.parametrize(
        "char",
        [
            chr(0x202E),  # right-to-left override
            chr(0x2066),  # left-to-right isolate
            chr(0x200B),  # zero-width space
            chr(0x200D),  # zero-width joiner
            chr(0xFEFF),  # byte order mark
        ],
    )
    def test_format_characters_are_removed(self, char: str) -> None:
        assert _sanitize_detail(f"gnp{char}.exe") == "gnp.exe"

    @pytest.mark.parametrize("limit", [3, 4, 10, 50])
    def test_result_never_exceeds_the_limit(self, limit: int) -> None:
        result = sanitize_detail("y" * 1000, limit)

        assert len(result) == limit
        assert result.endswith("...")

    @pytest.mark.parametrize("limit", [0, 1, 2])
    def test_tiny_limit_cuts_without_ellipsis(self, limit: int) -> None:
        assert sanitize_detail("abcdef", limit) == "abcdef"[:limit]

    def test_text_at_a_small_limit_is_not_cut(self) -> None:
        assert sanitize_detail("abc", 3) == "abc"

    def test_cut_keeps_a_base_with_its_combining_marks(self) -> None:
        acute = chr(0x301)
        text = "ab" + "e" + acute + "cdef"

        # Budget keeps "abe" and would leave the accent behind: drop the base.
        result = sanitize_detail(text, 6)

        assert result == "ab..."
        assert acute not in result

    def test_empty_text(self) -> None:
        assert _sanitize_detail("") == ""
        assert _sanitize_detail(" \n ") == ""


class TestFrostAnswer:
    def test_generic_text_is_kept_whole(self) -> None:
        text = answer_text("x" * 10_000)

        generic = ErrorMessages.PRECONDITION_NOT_MET.value
        assert text.startswith(f"{generic}: ")
        detail = text[len(generic) + 2 :]
        assert detail == "x" * (_MAX_ERROR_DETAIL - 3) + "..."
        assert len(detail) == _MAX_ERROR_DETAIL

    def test_control_characters_never_reach_the_peer(self) -> None:
        text = answer_text("line1\nline2\r\n\tline3\x1b[0m")

        assert text.endswith("line1 line2 line3 [0m")
        for char in "\n\r\t\x1b":
            assert char not in text

    def test_non_ascii_detail_survives(self) -> None:
        assert answer_text("modalità 日本語").endswith("modalità 日本語")

    def test_short_detail_is_sent_as_it_was(self) -> None:
        text = answer_text("/plant/mode == 2 not met")

        assert text.endswith(": /plant/mode == 2 not met")

    def test_observed_value_is_never_sent(self) -> None:
        method = composite(
            "m",
            [
                failing_stub(
                    ExecutionError(
                        ExecutionErrorCode.PRECONDITION_NOT_MET,
                        "mode == 2 not met",
                        observed="'hunter2-secret'",
                    )
                )
            ],
        )
        manager, _ = frost_setup(method)

        response = manager.handle_request(frost_request("dm", "m"))

        assert isinstance(response, FrostMessage)
        assert isinstance(response.payload, ErrorPayload)
        assert "hunter2" not in str(response.payload.error_message)
        assert "hunter2" not in repr(response)
