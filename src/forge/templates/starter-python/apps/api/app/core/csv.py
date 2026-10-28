import csv
import io
from collections.abc import Callable, Sequence
from datetime import UTC, datetime

from fastapi import Response

type CsvValue = str | int | float | None
type CsvColumn[T] = tuple[str, Callable[[T], CsvValue]]


def utc_date_time(value: datetime) -> str:
    """The export's date column format, the same as formatDateTime(value, 'UTC') in @app/shared."""
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M")


def _cell(value: CsvValue) -> str:
    if value is None:
        return ""
    # A spreadsheet runs text that starts with one of these as a formula, so the export keeps it as text.
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return str(value)


def csv_response[T](
    filename: str, columns: Sequence[CsvColumn[T]], rows: Sequence[T]
) -> Response:
    """The one place that writes CSV. A date column uses utc_date_time and ends its header with " (UTC)"."""
    # ponytail: builds the whole file in memory, fine for the constitution's size of app;
    # stream it when a table passes about 50,000 rows.
    body = io.StringIO()
    writer = csv.writer(body, lineterminator="\r\n")
    writer.writerow(header for header, _ in columns)
    writer.writerows([_cell(value(row)) for _, value in columns] for row in rows)
    return Response(
        content=body.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
