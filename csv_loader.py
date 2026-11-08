"""Stage 11: strictly read CTG's seven-column CSV files without losing records.

Parsing only: no duplicate detection, domain validation, or reconciliation yet.
"""

import csv
from dataclasses import dataclass
from pathlib import Path


EXPECTED_COLUMNS = (
    "security_id",
    "ticker",
    "security_name",
    "security_type",
    "currency",
    "market_value",
    "as_of_date",
)


class CSVLoadError(ValueError):
    """A CSV cannot be trusted as a complete, correctly parsed input."""


@dataclass(frozen=True)
class CSVRecord:
    line_start: int  # Physical line number in the original CSV (1-based).
    line_end: int
    values: dict[str, str]  # Preserve text exactly; type conversion comes later.


@dataclass(frozen=True)
class CSVData:
    path: str
    columns: tuple[str, ...]
    records: tuple[CSVRecord, ...]


def load_csv(path: str | Path) -> CSVData:
    """Read CTG-shaped CSV, or raise CSVLoadError instead of skipping bad rows.

    Supports quoted commas/newlines and optional UTF-8 BOM. Does not normalize
    cells or infer numeric/date types. A bad file does not produce partial output.
    """
    file_path = Path(path)
    records: list[CSVRecord] = []

    try:
        with file_path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream, strict=True)

            try:
                header = next(reader)
            except StopIteration as exc:
                raise CSVLoadError(f"{file_path}: empty CSV; header required") from exc

            if tuple(header) != EXPECTED_COLUMNS:
                raise CSVLoadError(
                    f"{file_path}: unexpected header at physical line 1; "
                    f"expected {EXPECTED_COLUMNS}, found {tuple(header)}"
                )

            previous_end_line = reader.line_num
            for cells in reader:
                start_line = previous_end_line + 1
                end_line = reader.line_num
                previous_end_line = end_line

                if len(cells) != len(EXPECTED_COLUMNS):
                    location = (
                        f"line {start_line}"
                        if start_line == end_line
                        else f"lines {start_line}-{end_line}"
                    )
                    raise CSVLoadError(
                        f"{file_path}: malformed row at physical {location}: "
                        f"expected {len(EXPECTED_COLUMNS)} fields, "
                        f"found {len(cells)}"
                    )

                records.append(
                    CSVRecord(
                        line_start=start_line,
                        line_end=end_line,
                        values=dict(zip(EXPECTED_COLUMNS, cells)),
                    )
                )

    except UnicodeDecodeError as exc:
        raise CSVLoadError(
            f"{file_path}: invalid UTF-8; decoding failed: {exc.reason}"
        ) from exc
    except csv.Error as exc:
        # With unclosed quotes the parser may know only where it stopped, not
        # the exact first problematic character. Do not pretend otherwise.
        raise CSVLoadError(
            f"{file_path}: CSV syntax error near physical line {reader.line_num}: {exc}"
        ) from exc

    return CSVData(
        path=str(file_path), columns=EXPECTED_COLUMNS, records=tuple(records)
    )
