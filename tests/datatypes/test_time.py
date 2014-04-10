
from mock import Mock
import pytest

from chapter10.datatypes import time


@pytest.mark.parametrize(
    ('data_type',), [(t,) for t in range(0x12, 0x18)])
def test_reserved(data_type):
    with pytest.raises(NotImplementedError):
        t = time.Time(Mock(
            file=Mock(tell=Mock(return_value=0),
                      read=Mock(return_value='1234')),
            data_type=data_type,
            data_length=2))
        t.parse()
