# -*- coding: utf-8 -*-
import sys

import pytest

import uncommitted.command


def test_badly_encoded_output():
    some_bytes = b'tsch\xfc\xdf'  # 'tschüß' in latin1, outside UTF-8
    expected = [u'tsch\ufffd\ufffd']
    actual = uncommitted.command.replace_unknown_characters(some_bytes)
    assert actual == expected


@pytest.mark.skipif(sys.platform == 'win32',
                    reason="does not run on windows")
def test_run_can_handle_badly_encoded_output():
    some_bytes = b'tsch\xfc\xdf'  # 'tschüß' in latin1, outside UTF-8
    output = uncommitted.command.run(['echo', some_bytes])
    assert output == [u'tsch\ufffd\ufffd']
