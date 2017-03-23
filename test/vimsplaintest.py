import pytest
from subprocess import PIPE
from subprocess import check_output

SELECT_INNER_WORD = """v\tstart characterwise Visual mode selecting 1 characters
iW\textend highlighted area with "inner WORD\""""

LONG_EXAMPLE = """qa\trecord typed characters into named register {0-9a-zA-Z"} (uppercase to append)
3j\tcursor 3 lines downward
Y\tyank 1 lines [into buffer x]; synonym for "yy"
p\tput the text [from register x] after the cursor 1 times
J\tJoin 2 lines; default is 2
D\tdelete the characters under the cursor until the end of the line and 0 more lines [into buffer x]; synonym for "d$"
q\t(while recording) stops recording
2@a\texecute the contents of register {a-z} 2 times
ZZ\tstore current file if modified, and exit"""

@pytest.mark.parametrize(
    "input_,raw_expected",
    [
        ("a", "a\tappend text after the cursor 1 times"),
        ("viW", SELECT_INNER_WORD),
        ("qa3jYpJDq2@aZZ", LONG_EXAMPLE),
    ]
)
def test_examples(input_, raw_expected):
    command = "python vimsplain.py {}".format(input_)
    expected_output = raw_expected + "\n"
    actual_output = str(check_output(["python", "vimsplain.py", input_]), 'utf-8')
    assert actual_output == expected_output
