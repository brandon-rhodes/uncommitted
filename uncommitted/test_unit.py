# -*- coding: utf-8 -*-
import sys

import pytest

import uncommitted.command


@pytest.mark.skipif(sys.platform == 'win32',
                    reason="does not run on windows")
def test_run_can_handle_badly_encoded_output():
    some_bytes = b'tsch\xfc\xdf'  # 'tschüß' in latin1, outside UTF-8
    output = uncommitted.command.run([b'echo', some_bytes])
    assert output == [some_bytes]
