import pytest
from annotate_socket_wall import board_points

def test_native_coordinates():
    assert board_points([[0,0],[50,0],[50,50],[0,50]],[3,305],5)==[[3,305],[13,305],[13,315],[3,315]]

@pytest.mark.parametrize('points', [[],[[0,0],[1,1]],[[0,0],[5,5],[0,5],[5,0]],[[0,0],[float('nan'),5],[5,0]]])
def test_invalid(points):
    with pytest.raises(ValueError): board_points(points,[0,0],1)
