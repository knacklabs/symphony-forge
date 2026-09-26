"""`forge spec payback`: one answer from the numbers, the same every time (Done when 4).

Each case runs the real command from a folder outside any repo, because it changes nothing.
"""
from __future__ import annotations

import pytest

STORY = "FORGE-FDE-1"

BUILD = ("--build-days", "10", "--day-rate", "600")  # a 6,000 build
NEXT = "Next: forge spec payback --help\n"

CASES = {
    # No value group: nothing to weigh yet, with or without the build numbers.
    "no numbers": ((), "find out first"),
    "only the build": (BUILD, "find out first"),
    # 6,000 over 2,000 a month is exactly three months; one more month of payback is not.
    "exactly three months": ((*BUILD, "--revenue-per-month", "2000", "--confidence", "measured"),
                             "build: 3.0 months"),
    "just over three": ((*BUILD, "--revenue-per-month", "1999", "--confidence", "measured"),
                        "smallest slice first: 3.0 months"),
    "exactly twelve months": ((*BUILD, "--revenue-per-month", "500", "--confidence", "measured"),
                              "smallest slice first: 12.0 months"),
    "just over twelve": ((*BUILD, "--revenue-per-month", "499", "--confidence", "measured"),
                         "don't build: 12.0 months"),
    # 6.3 days over 0.7 x 3 a month is exactly 3; floating point makes it 3.0000000000000004.
    "exact arithmetic": (("--build-days", "6.3", "--day-rate", "1", "--hours-per-month", "0.7",
                          "--people", "3", "--hourly-rate", "1", "--confidence", "measured"),
                         "build: 3.0 months"),
    # Guessed by default: 10 h x 2 people x 50 = 1,000 a month, weighed by 1/5 = 200; 600 / 200.
    "guessed by default": (("--build-days", "2", "--day-rate", "300", "--hours-per-month", "10",
                            "--people", "2", "--hourly-rate", "50"), "build: 3.0 months"),
    # Estimated weighs by 1/2: 600 / 500 = 1.2.
    "estimated": (("--build-days", "2", "--day-rate", "300", "--hours-per-month", "10",
                   "--people", "2", "--hourly-rate", "50", "--confidence", "estimated"),
                  "build: 1.2 months"),
    # The groups add up: 1,000 time + 1,000 revenue + 10,000 x 0.1 incidents = 3,000; 30,000 / 3,000.
    "groups add up": (("--build-days", "30", "--day-rate", "1000", "--hours-per-month", "10",
                       "--people", "2", "--hourly-rate", "50", "--revenue-per-month", "1000",
                       "--incident-cost", "10000", "--incident-chance", "0.1",
                       "--confidence", "measured"), "smallest slice first: 10.0 months"),
    # 6,000 / 7,000 = 0.857..., shown to one decimal.
    "rounded for display": ((*BUILD, "--revenue-per-month", "7000", "--confidence", "measured"),
                            "build: 0.9 months"),
    "no monthly value": ((*BUILD, "--revenue-per-month", "0"), "don't build: no monthly value"),
    # Refusals, each naming the flag to fix.
    "a partial group": ((*BUILD, "--hours-per-month", "10", "--people", "2"),
                        "A payback needs --hourly-rate.\n" + NEXT),
    "value without the build": (("--incident-cost", "5000", "--incident-chance", "0.2"),
                                "A payback needs --build-days and --day-rate.\n" + NEXT),
    "not a number": ((*BUILD, "--revenue-per-month", "lots"),
                     "--revenue-per-month is 'lots', and it needs a number of zero or more.\n"
                     + NEXT),
    "negative": (("--build-days", "10", "--day-rate", "-600", "--revenue-per-month", "100"),
                 "--day-rate is '-600', and it needs a number of zero or more.\n" + NEXT),
    "infinite": ((*BUILD, "--revenue-per-month", "inf"),
                 "--revenue-per-month is 'inf', and it needs a number of zero or more.\n" + NEXT),
    "chance over one": ((*BUILD, "--incident-cost", "5000", "--incident-chance", "1.5"),
                        "--incident-chance is 1.5, and it needs a chance from 0 to 1.\n" + NEXT),
}


@pytest.mark.parametrize("case", CASES)
def test_4_payback_answer(repo, tmp_path, case):
    flags, expected = CASES[case]
    anywhere = tmp_path / "anywhere"
    anywhere.mkdir()
    done = repo.forge("spec", "payback", *flags, cwd=anywhere)
    if expected.endswith(NEXT):
        assert (done.returncode, done.stdout, done.stderr) == (1, "", expected)
    else:
        assert (done.returncode, done.stdout, done.stderr) == (0, expected + "\n", "")
