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
    # Cache method & config lookup for speed
    config = item.config
    verbosity = config.get_verbosity(Config.VERBOSITY_ASSERTIONS)
    if verbosity < 2 and not util.running_on_ci():
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
    # Avoid method locals; use local names for tight loop performance
    max_lines = DEFAULT_MAX_LINES if max_lines is None else max_lines
    max_chars = DEFAULT_MAX_CHARS if max_chars is None else max_chars

    input_len = len(input_lines)
    tolerable_max_chars = max_chars + 70
    # The truncation explanation add two lines to the output
    tolerable_max_lines = max_lines + 2

    # Fast-path check directly on input_lines and length; avoids costly join if not needed
    if input_len <= tolerable_max_lines:
        # Only join if line count is below threshold
        if sum(len(s) for s in input_lines) <= tolerable_max_chars:
            return input_lines
    else:
        # More than tolerable lines, definitely need truncation
        pass

    # Truncate to line limit first
    # Truncate first to max_lines, and then truncate to max_chars if necessary
    truncated_explanation = input_lines[:max_lines]
    truncated_char = True

    # Optimize char count logic: use an incremental sum, don't re-join
    char_count = 0
    for s in truncated_explanation:
        char_count += len(s)
    if char_count > tolerable_max_chars:
        truncated_explanation = _truncate_by_char_count(
            truncated_explanation, max_chars
        )
    else:
        truncated_char = False

    truncated_line_count = input_len - len(truncated_explanation)
    last_idx = -1
    last_line = truncated_explanation[last_idx]
    if last_line:
        # Add ellipsis and take into account part-truncated final line
        truncated_explanation[last_idx] = last_line + "..."
        if truncated_char:
            # It's possible that we did not remove any char from this line
            truncated_line_count += 1
    else:
        # Add proper ellipsis when we were able to fit a full line exactly
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
        if iterated_char_count + len(input_line) > max_chars:
            break
        iterated_char_count += len(input_line)

    # Create truncated explanation with modified final line
    truncated_result = input_lines[:iterated_index]
    final_line = input_lines[iterated_index]
    if final_line:
        final_line_truncate_point = max_chars - iterated_char_count
        final_line = final_line[:final_line_truncate_point]
    truncated_result.append(final_line)
    return truncated_result
