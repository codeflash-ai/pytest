"""Utilities for truncating assertion output.

Current default behaviour is to truncate assertion explanations at
terminal lines, unless running with an assertions verbosity level of at least 2 or running on CI.
"""

from typing import List
from typing import Optional

from _pytest.assertion import util
from _pytest.config import Config
from _pytest.nodes import Item


DEFAULT_MAX_LINES = 8
DEFAULT_MAX_CHARS = 8 * 80
USAGE_MSG = "use '-vv' to show"


def truncate_if_required(
    explanation: List[str], item: Item, max_length: Optional[int] = None
) -> List[str]:
    """Truncate this assertion explanation if the given test item is eligible."""
    if _should_truncate_item(item):
        return _truncate_explanation(explanation)
    return explanation


def _should_truncate_item(item: Item) -> bool:
    """Whether or not this test item is eligible for truncation."""
    verbose = item.config.get_verbosity(Config.VERBOSITY_ASSERTIONS)
    return verbose < 2 and not util.running_on_ci()


def _truncate_explanation(
    input_lines: List[str],
    max_lines: Optional[int] = None,
    max_chars: Optional[int] = None,
) -> List[str]:
    """Truncate given list of strings that makes up the assertion explanation.

    Truncates to either 8 lines, or 640 characters - whichever the input reaches
    first, taking the truncation explanation into account. The remaining lines
    will be replaced by a usage message.
    """
    if max_lines is None:
        max_lines = DEFAULT_MAX_LINES
    if max_chars is None:
        max_chars = DEFAULT_MAX_CHARS

    input_len = len(input_lines)
    # Early exit for small lines/characters without ".join" cost
    # Compute tolerable_max_chars and tolerable_max_lines without allocating intermediary objects
    tolerable_max_chars = max_chars + 70
    # The truncation explanation add two lines to the output
    tolerable_max_lines = max_lines + 2
    # Fast path for line count only
    if input_len <= tolerable_max_lines:
        # Fast character counting - only sum up to tolerable_max_chars, no join
        char_count = 0
        for line in input_lines:
            char_count += len(line)
            if char_count > tolerable_max_chars:
                break
        if char_count <= tolerable_max_chars:
            return input_lines

    # Truncate first to max_lines, and then truncate to max_chars if necessary
    # Truncate first to max_lines, and then truncate to max_chars if necessary
    truncated_explanation = input_lines[:max_lines]
    truncated_char = True
    # Efficient character counting for truncated_explanation
    char_count = 0
    over_limit = False
    for line in truncated_explanation:
        char_count += len(line)
        if char_count > tolerable_max_chars:
            over_limit = True
            break
    if over_limit:
        truncated_explanation = _truncate_by_char_count(
            truncated_explanation, max_chars
        )
    else:
        truncated_char = False

    truncated_line_count = input_len - len(truncated_explanation)
    last_idx = len(truncated_explanation) - 1
    # Guarantee not to allocate one-off intermediary object for last line
    last_line = truncated_explanation[last_idx]
    if last_line:
        truncated_explanation[last_idx] = last_line + "..."
        if truncated_char:
            # It's possible that we did not remove any char from this line
            truncated_line_count += 1
    else:
        truncated_explanation[last_idx] = "..."
    return [
        *truncated_explanation,
        "",
        f"...Full output truncated ({truncated_line_count} line"
        f"{'' if truncated_line_count == 1 else 's'} hidden), {USAGE_MSG}",
    ]


def _truncate_by_char_count(input_lines: List[str], max_chars: int) -> List[str]:
    # Find point at which input length exceeds total allowed length
    iterated_char_count = 0
    for iterated_index, input_line in enumerate(input_lines):
        line_len = len(input_line)
        if iterated_char_count + line_len > max_chars:
            break
        iterated_char_count += line_len
    else:
        # No truncation necessary
        return input_lines

    # Create truncated explanation with modified final line
    truncated_result = input_lines[:iterated_index]
    final_line = input_lines[iterated_index]
    if final_line:
        final_line_truncate_point = max_chars - iterated_char_count
        final_line = final_line[:final_line_truncate_point]
    truncated_result.append(final_line)
    return truncated_result
